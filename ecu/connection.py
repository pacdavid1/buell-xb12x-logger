#!/usr/bin/env python3
"""
ecu/connection.py — Conexión serial DDFI2 ECU
Extraído de ddfi2_logger.py (DDFI2Connection) para modularización v2.0

Responsabilidades:
  - Abrir/cerrar puerto serial FT232RL
  - Toggle DTR (reset estado ECU)
  - Enviar PDUs y leer respuestas
  - get_version(), get_rt_data(), read_full_eeprom()
  - USB reset via sysfs como último recurso
"""

import glob
import logging
import os
import time

import serial
import threading

from typing import Any

from ecu.protocol import decode_rt_packet, RT_RESPONSE_SIZE, SOH

# ── Protocolo DDFI2 ──────────────────────────────────────────
SOH: int      = 0x01
EOH: int      = 0xFF
SOT: int      = 0x02
EOT: int      = 0x03
ACK: int      = 0x06
DROID_ID: int  = 0x00
STOCK_ECM_ID: int = 0x42
CMD_GET: int   = 0x52
CMD_SET: int   = 0x57  # confirmed 2026-05-31: write EEPROM page
RT_RESPONSE_SIZE: int = 107

PDU_VERSION = bytes([0x01, 0x00, 0x42, 0x02, 0xFF, 0x02, 0x56, 0x03, 0xE8])
# PDU_RT_DATA importado localmente — no está en protocol.py
PDU_RT_DATA = bytes([0x01, 0x00, 0x42, 0x02, 0xFF, 0x02, 0x43, 0x03, 0xFD])

# (page_nr, start, length)
BUEIB_PAGES: list[tuple[int, int, int]] = [
    (1,    0, 256),
    (2,  256, 256),
    (3,  512, 158),
    (4,  670, 256),
    (5,  926, 256),
    (6, 1182,  24),
]


def build_pdu(payload_bytes: bytes) -> bytes:
    length = len(payload_bytes) + 1
    frame = bytes([SOH, DROID_ID, STOCK_ECM_ID, length, EOH, SOT]) + bytes(payload_bytes) + bytes([EOT])
    cs = 0
    for b in frame[1:]:
        cs ^= b
    return frame + bytes([cs & 0xFF])


class DDFI2Connection:
    def __init__(self, port: str) -> None:
        self.port: str = port
        self.ser: serial.Serial | None = None
        self.last_dirty_byte: str | None = None
        self.logger = logging.getLogger("DDFI2")
        self._lock = threading.RLock()

    def connect(self) -> None:
        deadline = time.monotonic() + 15.0
        while not os.path.exists(self.port):
            if time.monotonic() > deadline:
                raise serial.SerialException(f"{self.port} no aparece")
            time.sleep(0.5)
        self.ser = serial.Serial(
            port=self.port, baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            xonxoff=False, rtscts=False, dsrdtr=False
        )
        # Toggle DTR para resetear estado serial de la ECU
        self.ser.dtr = False; time.sleep(0.05)
        self.ser.dtr = True;  time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.1)  # settle
        # Intentar bajar latency timer FT232RL de 16ms → 2ms via sysfs
        try:
            lt_paths = glob.glob('/sys/bus/usb-serial/devices/ttyUSB*/latency_timer')
            if not lt_paths:
                lt_paths = glob.glob('/sys/bus/usb/drivers/ftdi_sio/*/latency_timer')
            if lt_paths:
                with open(lt_paths[0], 'w') as f:
                    f.write('2')
                self.logger.info(f"Latency timer FT232RL → 2ms ({lt_paths[0]})")
            else:
                self.logger.debug("Latency timer: path sysfs no encontrado (normal en este kernel)")
        except Exception as e:
            self.logger.debug(f"Latency timer no configurable: {e}")
        self.logger.info(f"Puerto serial abierto: {self.port}")

    def disconnect(self) -> None:
        with self._lock:
            self._disconnect_impl()

    def _disconnect_impl(self) -> None:
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            self.logger.warning(f"disconnect: {e}")

    def usb_power_cycle(self) -> bool:
        """Power cycle del hub USB via sysfs autosuspend.
        Mas efectivo que authorized toggle cuando dwc2 queda hung."""
        try:
            # Find the USB root hub dynamically instead of hardcoding usb1
            hubs = [p for p in glob.glob('/sys/bus/usb/devices/usb*')
                    if os.path.basename(p).startswith('usb') and p[-1].isdigit()][:5]
            hub = hubs[0] if hubs else '/sys/bus/usb/devices/usb1'
            for h in [hub]:  # try primary hub
                try:
                    with open(f'{h}/power/autosuspend_delay_ms', 'w') as f: f.write('0')
                    time.sleep(1.0)
                    with open(f'{h}/power/level', 'w') as f: f.write('on')
                    self.logger.info(f"USB power cycle completado en {h}")
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            self.logger.warning(f"USB power cycle falló: {e}")
            return False
    def _send(self, pdu: bytes) -> None:
        with self._lock:
            if not self.ser:
                raise RuntimeError("Serial port not connected")
            self.ser.reset_input_buffer()
            self.ser.write(pdu)
            self.ser.flush()

    def _read_exact(self, n: int, timeout_s: float = 1.0) -> bytes:
        if not self.ser:
            raise RuntimeError("Serial port not connected")
        buf = bytearray()
        deadline = time.monotonic() + timeout_s
        while len(buf) < n:
            rem = deadline - time.monotonic()
            if rem <= 0:
                raise TimeoutError(f"{len(buf)}/{n}")
            self.ser.timeout = min(rem, 0.1)
            chunk = self.ser.read(n - len(buf))
            if chunk:
                buf.extend(chunk)
        return bytes(buf)

    def get_version(self) -> str | None:
        """Reintentar hasta 5 veces con flush — ECU puede estar en modo RT."""
        with self._lock:
            return self._get_version_impl()

    def _get_version_impl(self) -> str | None:
        """Internal — called under self._lock."""
        for attempt in range(5):
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self._send(PDU_VERSION)
                h = self._read_exact(6, 2.0)
                if h[0] != SOH:
                    self.logger.debug(f"get_version intento {attempt+1}: byte0=0x{h[0]:02x}, flush+retry")
                    time.sleep(0.3)
                    continue
                rest = self._read_exact(h[3] - 1 + 2, 2.0)
                full = h + rest
                if full[6] != ACK:
                    time.sleep(0.3)
                    continue
                ver = full[7:-2].decode("ascii", errors="replace").strip()
                if ver:
                    return ver
            except Exception as e:
                self.logger.debug(f"get_version intento {attempt+1}: {e}")
                time.sleep(0.3)
        return None

    def _sync_to_soh(self, timeout_s: float = 0.5) -> bool:
        if not self.ser:
            return False
        """Descarta basura del buffer hasta encontrar SOH (0x01)."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.ser.timeout = 0.05
            b = self.ser.read(1)
            if b and b[0] == SOH:
                return True
        return False

    def _flush_and_retry_soh(self, timeout_s: float = 0.4) -> bool:
        """Segundo intento: vacía el buffer, reenvía PDU_RT_DATA y busca SOH."""
        try:
            self.ser.reset_input_buffer()
            self._send(PDU_RT_DATA)
            return self._sync_to_soh(timeout_s)
        except Exception:
            return False

    def get_rt_data(self) -> dict[str, Any] | None:
        """Lee un frame RT de la ECU. Retorna dict de parametros o None."""
        with self._lock:
            return self._get_rt_data_impl()

    def _get_rt_data_impl(self) -> dict[str, Any] | None:
        """Lee un frame RT de la ECU. Retorna dict de parámetros o None."""
        self.last_dirty_byte = None
        try:
            self._send(PDU_RT_DATA)
            self.ser.timeout = 0.3
            first = self.ser.read(1)
            if not first:
                return None
            if first[0] != SOH:
                self.last_dirty_byte = f"0x{first[0]:02x}"
                self.logger.debug(f"get_rt: byte0={self.last_dirty_byte} — sincronizando SOH")
                recovered = self._sync_to_soh()
                if not recovered:
                    recovered = self._flush_and_retry_soh()
                    if not recovered:
                        return None
                raw = bytes([SOH]) + self._read_exact(RT_RESPONSE_SIZE - 1, 0.3)
            else:
                raw = first + self._read_exact(RT_RESPONSE_SIZE - 1, 0.3)
            return decode_rt_packet(raw)
        except TimeoutError:
            return None
        except Exception as e:
            self.logger.debug(f"get_rt: {e}")
            return None

    def read_eeprom_page(self, page_nr: int, offset: int, length: int) -> bytes | None:
        try:
            payload = bytes([CMD_GET, offset & 0xFF, page_nr & 0xFF, length & 0xFF])
            self._send(build_pdu(payload))
            h = self._read_exact(6, 2.0)
            if h[0] != SOH or h[4] != EOH or h[5] != SOT:
                return None
            rest = self._read_exact(h[3] - 1 + 2, 2.0)
            full = h + rest
            return bytes(full[7:-2]) if full[6] == ACK else None
        except Exception as e:
            self.logger.error(f"eeprom page {page_nr}: {e}")
            return None

    def read_full_eeprom(self) -> bytes | None:
        """Lee las 6 páginas del BUEIB/DDFI-2 → 1206 bytes."""
        eeprom = bytearray(1206)
        try:
            for page_nr, start, length in BUEIB_PAGES:
                i = 0
                while i < length:
                    chunk = min(16, length - i)
                    data = self.read_eeprom_page(page_nr, i, chunk)
                    if data is None:
                        self.logger.error(f"EEPROM: fallo page {page_nr} offset {i}")
                        return None
                    eeprom[start + i: start + i + len(data)] = data
                    i += chunk
                self.logger.debug(f"EEPROM page {page_nr} leida ({length} bytes)")
            self.logger.info("EEPROM leida completa (1206 bytes)")
            return bytes(eeprom)
        except Exception as e:
            self.logger.error(f"read_full_eeprom: {e}")
            return None

    def write_eeprom_page(self, page_nr: int, offset: int, data: bytes) -> bool:
        """Write data bytes to ECU EEPROM at page/offset. Returns True on ACK.
        Payload format: [CMD_SET, offset, page, data...] — no length field.
        """
        try:
            payload = bytes([CMD_SET, offset & 0xFF, page_nr & 0xFF]) + bytes(data)
            self._send(build_pdu(payload))
            h = self._read_exact(6, 2.0)
            if h[0] != SOH:
                return False
            rest = self._read_exact(h[3] - 1 + 2, 2.0)
            return (h + rest)[6] == ACK
        except Exception as e:
            self.logger.error(f"write_eeprom_page page={page_nr} offset={offset}: {e}")
            return False

    def write_full_eeprom(self, proposed: bytes,
                          safe_start: int = 670,
                          safe_end:   int = 1205) -> dict:
        """Locked wrapper — prevents concurrent serial access during EEPROM burn."""
        with self._lock:
            return self._write_full_eeprom_impl(proposed, safe_start, safe_end)

    def _write_full_eeprom_impl(self, proposed: bytes,
                          safe_start: int = 670,
                          safe_end:   int = 1205) -> dict:
        """Burn proposed EEPROM to ECU using BurnDiffs approach.

        Only writes bytes that differ from the current ECU state, and only
        within safe_start..safe_end (fuel + spark maps). Never touches the
        DTC / factory-config area (offsets 0-669).

        Returns dict: {written, verified, diffs_found, errors}
        """
        if len(proposed) != 1206:
            return {'written': 0, 'verified': False, 'diffs_found': 0,
                    'errors': [f'proposed length {len(proposed)} != 1206']}

        # Read current EEPROM before any write
        current = self.read_full_eeprom()
        if current is None:
            return {'written': 0, 'verified': False, 'diffs_found': 0,
                    'errors': ['pre-burn read failed']}

        # Collect absolute offsets that differ within safe zone
        diffs = [i for i in range(safe_start, safe_end + 1)
                 if proposed[i] != current[i]]

        if not diffs:
            self.logger.info("write_full_eeprom: no changes in safe zone — nothing to write")
            return {'written': 0, 'verified': True, 'diffs_found': 0, 'errors': []}

        self.logger.info(
            f"write_full_eeprom: {len(diffs)} bytes differ in range {safe_start}-{safe_end}")

        # Map absolute offset → (page_nr, page_offset)
        def abs_to_page(abs_off):
            for pnr, start, length in BUEIB_PAGES:
                if start <= abs_off < start + length:
                    return pnr, abs_off - start
            return None, None

        # Group consecutive diffs into chunks (max 16 bytes, same page)
        # Spans of up to 4 unchanged bytes between diffs are merged into one
        # chunk to reduce the number of write PDUs.
        errors  = []
        written = 0
        i = 0
        while i < len(diffs):
            abs_off  = diffs[i]
            page_nr, page_off = abs_to_page(abs_off)
            if page_nr is None:
                errors.append(f'offset {abs_off} not mapped to any page')
                i += 1
                continue

            # Extend chunk: keep adding while same page, gap <= 4, total <= 16
            chunk_end = abs_off
            j = i + 1
            while j < len(diffs) and (chunk_end - abs_off + 1) < 16:
                next_abs = diffs[j]
                next_page, _ = abs_to_page(next_abs)
                if next_page != page_nr:
                    break
                if next_abs - chunk_end > 4:  # gap too large — new chunk
                    break
                chunk_end = next_abs
                j += 1

            # Write proposed bytes from abs_off to chunk_end (inclusive)
            chunk_len  = chunk_end - abs_off + 1
            chunk_data = proposed[abs_off:chunk_end + 1]
            ok = self.write_eeprom_page(page_nr, page_off, chunk_data)
            if ok:
                written += chunk_len
                self.logger.debug(
                    f"  wrote {chunk_len}B at page={page_nr} off={page_off}")
            else:
                errors.append(
                    f'write failed page={page_nr} offset={page_off} len={chunk_len}')
                self.logger.error(errors[-1])

            # Advance past all diffs within this chunk
            i = j if j > i + 1 else i + 1
            while i < len(diffs) and diffs[i] <= chunk_end:
                i += 1

        # Verify: read back and compare safe zone
        verify = self.read_full_eeprom()
        verified = (verify is not None and
                    all(verify[k] == proposed[k]
                        for k in range(safe_start, safe_end + 1)))

        if verified:
            self.logger.info(
                f"write_full_eeprom: verified OK ({written} bytes written)")
        else:
            self.logger.error("write_full_eeprom: verification FAILED")

        return {
            'written':     written,
            'verified':    verified,
            'diffs_found': len(diffs),
            'errors':      errors,
        }
