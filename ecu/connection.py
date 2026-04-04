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

from ecu.protocol import decode_rt_packet, RT_RESPONSE_SIZE, SOH

# ── Protocolo DDFI2 ──────────────────────────────────────────
SOH            = 0x01
EOH            = 0xFF
SOT            = 0x02
EOT            = 0x03
ACK            = 0x06
DROID_ID       = 0x00
STOCK_ECM_ID   = 0x42
CMD_GET        = 0x52
RT_RESPONSE_SIZE = 107

PDU_VERSION = bytes([0x01, 0x00, 0x42, 0x02, 0xFF, 0x02, 0x56, 0x03, 0xE8])
# PDU_RT_DATA importado localmente — no está en protocol.py
PDU_RT_DATA = bytes([0x01, 0x00, 0x42, 0x02, 0xFF, 0x02, 0x43, 0x03, 0xFD])

BUEIB_PAGES = [
    (1,    0, 256),
    (2,  256, 256),
    (3,  512, 158),
    (4,  670, 256),
    (5,  926, 256),
    (6, 1182,  24),
]


def build_pdu(payload_bytes):
    length = len(payload_bytes) + 1
    frame = bytes([SOH, DROID_ID, STOCK_ECM_ID, length, EOH, SOT]) + bytes(payload_bytes) + bytes([EOT])
    cs = 0
    for b in frame[1:]:
        cs ^= b
    return frame + bytes([cs & 0xFF])


class DDFI2Connection:
    def __init__(self, port):
        self.port = port
        self.ser = None
        self.last_dirty_byte = None
        self.logger = logging.getLogger("DDFI2")

    def connect(self):
        deadline = time.time() + 15.0
        while not os.path.exists(self.port):
            if time.time() > deadline:
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

    def disconnect(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def usb_power_cycle(self):
        """Power cycle del hub USB via sysfs autosuspend.
        Mas efectivo que authorized toggle cuando dwc2 queda hung."""
        try:
            hub = '/sys/bus/usb/devices/usb1'
            open(f'{hub}/power/autosuspend_delay_ms', 'w').write('0')
            time.sleep(2.0)
            open(f'{hub}/power/level', 'w').write('on')
            time.sleep(3.0)
            self.logger.info("USB power cycle completado")
            return True
        except Exception as e:
            self.logger.warning(f"USB power cycle falló: {e}")
            return False

    def usb_reset(self):
        """Fuerza reset USB del FT232RL via sysfs (authorized toggle).
        Usar cuando DTR toggle no alcanza y el chip queda hung.
        Retorna True si el device fue reseteado, False si no se encontró."""
        KNOWN_ADAPTERS = [
            ('0403', '6001', 'FT232RL'),
            ('1a86', '55d3', 'CH343P'),
        ]
        try:
            for path in glob.glob('/sys/bus/usb/devices/*/idVendor'):
                vendor  = open(path).read().strip()
                product = open(path.replace('idVendor', 'idProduct')).read().strip()
                match = next((n for v,p,n in KNOWN_ADAPTERS if v==vendor and p==product), None)
                if match:
                    auth = path.replace('idVendor', 'authorized')
                    open(auth, 'w').write('0')
                    time.sleep(0.8)
                    open(auth, 'w').write('1')
                    time.sleep(2.0)
                    self.logger.info(f"USB reset {match} completado via sysfs")
                    return True
            self.logger.warning("USB reset: ningún adaptador conocido encontrado en sysfs")
            return False
        except Exception as e:
            self.logger.warning(f"USB reset falló: {e}")
            return False

    def _send(self, pdu):
        self.ser.reset_input_buffer()
        self.ser.write(pdu)
        self.ser.flush()

    def _read_exact(self, n, timeout_s=1.0):
        buf = bytearray()
        deadline = time.time() + timeout_s
        while len(buf) < n:
            rem = deadline - time.time()
            if rem <= 0:
                raise TimeoutError(f"{len(buf)}/{n}")
            self.ser.timeout = min(rem, 0.1)
            chunk = self.ser.read(n - len(buf))
            if chunk:
                buf.extend(chunk)
        return bytes(buf)

    def get_version(self):
        """Reintentar hasta 5 veces con flush — ECU puede estar en modo RT."""
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

    def _sync_to_soh(self, timeout_s=0.5):
        """Descarta basura del buffer hasta encontrar SOH (0x01)."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            self.ser.timeout = 0.05
            b = self.ser.read(1)
            if b and b[0] == SOH:
                return True
        return False

    def _flush_and_retry_soh(self, timeout_s=0.4):
        """Segundo intento: vacía el buffer, reenvía PDU_RT_DATA y busca SOH."""
        try:
            self.ser.reset_input_buffer()
            self._send(PDU_RT_DATA)
            return self._sync_to_soh(timeout_s)
        except Exception:
            return False

    def get_rt_data(self):
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

    def read_eeprom_page(self, page_nr, offset, length):
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

    def read_full_eeprom(self):
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
