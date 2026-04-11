#!/usr/bin/env python3
"""
Buell Logger - Main Entry Point (Modular v1.0)
Solo red + web por ahora. ECU logging viene después.
"""

import argparse
import json
import logging
import time
import signal
import sys
import subprocess
import threading
from pathlib import Path

# Añadir paths para imports
sys.path.insert(0, str(Path(__file__).parent))

from network.manager import NetworkManager
from web.server import WebServer
from ecu.connection import DDFI2Connection
from ecu.eeprom import decode_eeprom_maps, decode_eeprom_params
from ecu.eeprom_params import decode_params
from ecu.version_resolver import resolve_ecu
from ecu.session import SessionManager, CellTracker, cell_key, RideErrorLog


def _get_version():
    try:
        import re
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"

LOGGER_VERSION = _get_version()


class BuellLogger:
    """Orquestador principal - versión mínima para prueba de red."""
    
    def __init__(self, port="/dev/ttyUSB0", sessions_dir="/home/pi/buell/sessions", 
                 buell_dir="/home/pi/buell", no_poweroff=False):
        self.port = port
        self.sessions_dir = Path(sessions_dir)
        self.buell_dir = Path(buell_dir)
        self.no_poweroff = no_poweroff
        self.logger = logging.getLogger("BuellLogger")
        
        # Crear dirs si no existen
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.buell_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._shutting_down = False
        self._poweroff_requested = False
        self._ecu_thread = None
        
        # Componentes modulares
        self.network = NetworkManager()
        self.web = WebServer(host='0.0.0.0', port=8080, buell_dir=self.buell_dir)
        self.web.network      = self.network
        self.ecu     = DDFI2Connection(self.port)
        self.session = SessionManager(self.sessions_dir)
        self.tracker = CellTracker()
        self.web.cell_tracker = self.tracker
        self.web.session      = self.session
        self.error_log = RideErrorLog()
        obj_path = self.buell_dir / 'objectives.json'
        self.objectives_cfg = json.load(open(obj_path)) if obj_path.exists() else {}
        
        # Señales
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida - deteniendo...")
        self._running = False
    
    def _sysmon_loop(self):
        """System monitor thread — runs always, independent of ECU.
        Updates cpu_pct and cpu_temp in web.serial_stats every 2s."""
        _cpu_prev = None
        while self._running:
            try:
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    cpu_temp = round(int(f.read().strip()) / 1000.0, 1)
            except Exception:
                cpu_temp = 0.0
            try:
                with open('/proc/stat') as f:
                    _cpu = list(map(int, f.readline().split()[1:]))
                _idle = _cpu[3]
                _total = sum(_cpu)
                if _cpu_prev is not None:
                    _di = _idle - _cpu_prev[0]
                    _dt = _total - _cpu_prev[1]
                    cpu_pct = round((1.0 - _di / _dt) * 100, 1) if _dt else 0.0
                else:
                    cpu_pct = 0.0
                _cpu_prev = (_idle, _total)
            except Exception:
                cpu_pct = 0.0
            ss = self.web.serial_stats or {}
            ss['cpu_pct'] = cpu_pct
            ss['cpu_temp'] = cpu_temp
            self.web.serial_stats = ss
            time.sleep(2.0)

    def _ecu_loop(self):
        """Thread de lectura RT — 8Hz, actualiza web.ecu_live y graba rides.
        Reconexión escalada: hard reconnect a 30s, USB reset a 60s."""
        TARGET_HZ      = 8.0
        INTERVAL       = 1.0 / TARGET_HZ
        RPM_START      = 300
        RPM_STOP       = 100
        STOP_CONFIRM_S = 5.0
        MAX_CONSEC     = 30

        ride_active      = False
        ecu_version      = None
        rpm_zero_since   = None
        consecutive_errors = 0
        ecu_lost_since   = None
        last_lost_interval = -1
        _serial_bytes    = 0
        _serial_window   = time.monotonic()

        self.logger.info("ECU loop iniciado")

        while self._running:
            t0 = time.monotonic()

            # ── Conectar si el puerto no está abierto ──────────────────────
            if self.ecu.ser is None or not self.ecu.ser.is_open:
                try:
                    self.logger.info("ECU loop — intentando conectar...")
                    self.ecu.connect()
                    ecu_version = self.ecu.get_version()
                    if ecu_version:
                        self.logger.info(f"ECU reconnected: {ecu_version}")
                        # If no session active (e.g. logger started before bike) —
                        # Always read EEPROM on connect — detect bike swap via checksum.
                        self.logger.info("Reading EEPROM to detect bike identity...")
                        _blob = self.ecu.read_full_eeprom()
                        if _blob is None:
                            # Fallback 1: use most recent cached blob on disk
                            _bins = sorted(self.sessions_dir.glob("*/eeprom.bin"),
                                           key=lambda p: p.stat().st_mtime)
                            if _bins:
                                _blob = open(_bins[-1], 'rb').read()
                                self.logger.warning("EEPROM fetch failed — using cached blob from disk")
                            else:
                                # Fallback 2: version string as checksum seed
                                _blob = ecu_version.encode().ljust(64, b'\x00')
                                self.logger.warning("EEPROM fetch failed — using version string as checksum")
                        self.session.open_session(ecu_version, _blob)
                        if not (self.session.current_session_dir / 'eeprom.bin').exists():
                            self.session.save_eeprom(_blob)
                        self.web.eeprom_maps   = decode_eeprom_maps(_blob)
                        self.web.eeprom_params = decode_params(_blob, ecu_version)
                        self.web.bike_serial   = int.from_bytes(_blob[12:14], 'little')
                        self.web.ecu_identity  = resolve_ecu(ecu_version) or {}
                        self.logger.info(f"Session opened from reconnect: {self.session.current_checksum}")
                        consecutive_errors = 0
                        ecu_lost_since = None
                    else:
                        self.logger.warning("ECU no respondió — reintento en 5s")
                        # If no session and cached EEPROM exists, open session anyway
                        if self.session.current_checksum is None:
                            import glob as _glob
                            _bins = sorted(_glob.glob(str(self.sessions_dir / '*' / 'eeprom.bin')),
                                           key=lambda p: __import__('os').path.getmtime(p))
                            if _bins:
                                _blob = open(_bins[-1], 'rb').read()
                                _ver  = 'cached'
                                self.session.open_session(_ver, _blob)
                                self.web.eeprom_maps   = decode_eeprom_maps(_blob)
                                self.web.eeprom_params = decode_params(_blob, _ver)
                                self.web.bike_serial   = int.from_bytes(_blob[12:14], 'little')
                                self.web.ecu_identity  = resolve_ecu(_ver) or {}
                                self.logger.warning(f"Session opened from cached EEPROM: {self.session.current_checksum}")
                        time.sleep(5)
                        continue
                except Exception as e:
                    self.logger.debug(f"ECU no disponible: {e} — reintento en 5s")
                    if ecu_lost_since is None:
                        ecu_lost_since = time.monotonic()
                    no_ecu_s = time.monotonic() - ecu_lost_since
                    if no_ecu_s >= 10.0 and int(no_ecu_s) % 10 == 0:
                        self.logger.info(f"USB power cycle — {no_ecu_s:.0f}s sin ECU")
                        self.ecu.usb_power_cycle()
                    time.sleep(5)
                    continue

            # ── Leer frame RT ──────────────────────────────────────────────
            elapsed_s = 0.0
            if ride_active and self.session.ride_start_time:
                elapsed_s = time.monotonic() - self.session.ride_start_time

            try:
                data = self.ecu.get_rt_data()
            except Exception as e:
                self.logger.warning(f"SerialException: {e}")
                if ride_active:
                    self.error_log.serial_exception(
                        elapsed_s=elapsed_s,
                        exc_msg=e,
                        consecutive_before=consecutive_errors)
                data = None
                consecutive_errors += 1
                if ecu_lost_since is None:
                    ecu_lost_since = time.monotonic()
                time.sleep(0.2)

            if data is None:
                consecutive_errors += 1
                if ecu_lost_since is None:
                    ecu_lost_since = time.monotonic()
                    self.logger.warning("ECU sin respuesta — esperando recuperación")

                lost_total = time.monotonic() - ecu_lost_since
                self.web.ecu_connected = False
                self.web.ecu_lost_s = lost_total

                # Loguear timeout cada 10s
                lost_interval = int(lost_total) // 10
                if lost_interval != last_lost_interval:
                    last_lost_interval = lost_interval
                    self.logger.info(f"ECU sin respuesta {lost_total:.0f}s")
                    if ride_active:
                        self.error_log.ecu_timeout(
                            elapsed_s=elapsed_s,
                            lost_s=lost_total,
                            last_valid_t=elapsed_s - lost_total)

                # Sin ride activo: salir si supera MAX_CONSEC
                if not ride_active and consecutive_errors >= MAX_CONSEC:
                    self.logger.info("ECU no responde — cerrando puerto")
                    self.ecu.disconnect()
                    time.sleep(5)
                    consecutive_errors = 0
                    ecu_lost_since = None

                # Hard reconnect cada 30s
                if ecu_lost_since is not None and lost_total >= 30.0 and consecutive_errors % 30 == 0:
                    self.logger.info(f"Hard reconnect — {lost_total:.0f}s sin ECU")
                    if ride_active:
                        self.error_log.reconnect_attempt(
                            elapsed_s=elapsed_s,
                            trigger="auto_30s",
                            attempt_n=consecutive_errors // 30,
                            success=False,
                            time_s=lost_total)
                    # USB power cycle tras 15s, USB reset tras 30s
                    if lost_total >= 15.0 and consecutive_errors % 15 == 0:
                        self.logger.info(f"USB power cycle — {lost_total:.0f}s sin ECU")
                        self.ecu.usb_power_cycle()
                    elif lost_total >= 30.0 and consecutive_errors % 30 == 0:
                        self.logger.info(f"USB reset — {lost_total:.0f}s sin ECU")
                        self.ecu.usb_reset()
                        time.sleep(0.5)
                    try:
                        self.ecu.disconnect()
                        time.sleep(0.5)
                        self.ecu.connect()
                        ver = self.ecu.get_version()
                        if ver:
                            self.logger.info("ECU responde tras hard reconnect")
                            consecutive_errors = 0
                            ecu_lost_since = None
                            last_lost_interval = -1
                            if ride_active:
                                self.error_log.reconnect_attempt(
                                    elapsed_s=elapsed_s,
                                    trigger="auto_30s",
                                    attempt_n=consecutive_errors // 30,
                                    success=True,
                                    time_s=lost_total)
                    except Exception as e:
                        self.logger.warning(f"Hard reconnect falló: {e}")

                elapsed = time.monotonic() - t0
                sleep_t = INTERVAL - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)
                continue

            # ── Frame válido ───────────────────────────────────────────────
            consecutive_errors = 0
            ecu_lost_since = None
            last_lost_interval = -1

            self.web.ecu_live = data
            self.web.ecu_connected = True
            self.web.ecu_lost_s = 0.0
            self.web.ride_active = ride_active
            self.web.elapsed_s = elapsed_s
            if ride_active:
                self.error_log.update_last_sample(data)
            rpm = data.get("RPM", 0) or 0

            # Abrir ride
            if not ride_active and rpm >= RPM_START:
                if self.session.current_checksum is None:
                    self.logger.warning("RPM detected but no active session — skipping ride start")
                else:
                    ride_active    = True
                    rpm_zero_since = None
                    self.session.start_ride()
                    self.error_log.start(
                        ride_num=self.session.current_ride_num,
                        session_checksum=self.session.current_checksum,
                        session_dir=str(self.session.current_session_dir))
                    self.logger.info(f"Ride {self.session.current_ride_num:03d} iniciado")

            # Grabar sample
            if ride_active:
                data['buf_in'] = self.ecu.ser.in_waiting if self.ecu.ser and self.ecu.ser.is_open else 0
                if data['buf_in'] > 192 and self.ecu.ser and self.ecu.ser.is_open:
                    self.ecu.ser.reset_input_buffer()
                    self.logger.warning(f"AUTO-FLUSH FIFO buf_in={data['buf_in']}b >50% — flushed")
                ss = self.web.serial_stats or {}
                data['ttl_pct']  = ss.get('pct', 0)
                data['cpu_pct']  = ss.get('cpu_pct', 0)
                data['cpu_temp'] = ss.get('cpu_temp', 0)
                data['mem_pct']  = ss.get('mem_pct', 0)
                self.session.write_sample(data, time.time())
            self.tracker.update(data)

            # Detectar parada
            if ride_active and rpm < RPM_STOP:
                if rpm_zero_since is None:
                    rpm_zero_since = time.monotonic()
                elif time.monotonic() - rpm_zero_since >= STOP_CONFIRM_S:
                    snap = self.tracker.snapshot()
                    self.session.close_current_ride(
                        f"RPM=0 por {STOP_CONFIRM_S:.0f}s",
                        tracker_snapshot=snap,
                        objectives_cfg=self.objectives_cfg)
                    self.error_log.flush()
                    self.tracker.reset()
                    ride_active    = False
                    rpm_zero_since = None
            elif rpm >= RPM_STOP:
                rpm_zero_since = None

            # ── Conteo de bytes seriales ───────────────────────────
            if data is not None:
                _serial_bytes += 9 + 107  # PDU_RT_DATA TX + frame RX
            _now = time.monotonic()
            if _now - _serial_window >= 1.0:
                bps = _serial_bytes
                pct = round(min(bps / 960.0 * 100, 100.0), 1)
                in_w = self.ecu.ser.in_waiting if self.ecu.ser and self.ecu.ser.is_open else 0
                buf_pct = round(in_w / 384.0 * 100, 1)
                try:
                    with open('/proc/meminfo') as _f:
                        _mem = {}
                        for _l in _f:
                            _k,_v = _l.split(':')
                            _mem[_k.strip()] = int(_v.split()[0])
                    _mt = _mem['MemTotal']; _mf = _mem['MemAvailable']
                    mem_pct = round((_mt-_mf)/_mt*100, 1)
                except Exception:
                    mem_pct = 0.0
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp') as _f:
                        cpu_temp = round(int(_f.read().strip()) / 1000.0, 1)
                except Exception:
                    cpu_temp = 0.0
                try:
                    with open('/proc/stat') as _f:
                        _cpu = list(map(int, _f.readline().split()[1:]))
                    _idle = _cpu[3]
                    _total = sum(_cpu)
                    if hasattr(self, '_cpu_prev'):
                        _di = _idle - self._cpu_prev[0]
                        _dt = _total - self._cpu_prev[1]
                        cpu_pct = round((1.0 - _di / _dt) * 100, 1) if _dt else 0.0
                    else:
                        cpu_pct = 0.0
                    self._cpu_prev = (_idle, _total)
                except Exception:
                    cpu_pct = 0.0
                self.web.serial_stats = {'bps': bps, 'pct': pct, 'tx': 9*8, 'rx': 107*8, 'buf_in': in_w, 'buf_pct': buf_pct, 'mem_pct': mem_pct, 'cpu_pct': cpu_pct, 'cpu_temp': cpu_temp}
                _serial_bytes  = 0
                _serial_window = _now
            elapsed = time.monotonic() - t0
            sleep_t = INTERVAL - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        # ── Cierre al detener el servicio ──────────────────────────────────
        if ride_active:
            self.session.close_current_ride(
                "servicio detenido",
                tracker_snapshot=self.tracker.snapshot(),
                objectives_cfg=self.objectives_cfg)
            self.error_log.flush()
        self.logger.info("ECU loop detenido")


    def run(self):
        """Loop principal."""
        self._running = True
        self.logger.info(f"Buell Logger {LOGGER_VERSION}")
        self.logger.info(f"Sessions: {self.sessions_dir}")
        self.logger.info(f"Buell dir: {self.buell_dir}")
        
        # 1. Conectar ECU
        self.logger.info("Conectando a ECU...")
        try:
            self.ecu.connect()
            ver = self.ecu.get_version()
            if ver:
                self.logger.info(f"ECU connected: {ver}")
                # Wait for ECU to stabilize before reading EEPROM
                self.logger.info("Waiting 3s for ECU to stabilize...")
                time.sleep(3.0)
                # Fetch EEPROM first — checksum derived from blob
                self.logger.info("Reading EEPROM from ECU...")
                blob = self.ecu.read_full_eeprom()
                if blob is None:
                    # Fallback 1: use most recent eeprom.bin from any existing session
                    self.logger.warning("EEPROM fetch failed — looking for cached blob on disk...")
                    import glob as _glob
                    _bins = sorted(_glob.glob(str(self.sessions_dir / '*' / 'eeprom.bin')))
                    if _bins:
                        blob = open(_bins[-1], 'rb').read()
                        self.logger.warning(f"Using cached EEPROM from {_bins[-1]}")
                    else:
                        # Fallback 2: no blob anywhere — use version string as checksum
                        self.logger.warning("No cached EEPROM found — opening session with version string checksum")
                        blob = ver.encode().ljust(64, b'\x00')
                if blob:
                    self.session.open_session(ver, blob)
                    # Save blob if not already stored for this checksum
                    if not (self.session.current_session_dir / 'eeprom.bin').exists():
                        self.session.save_eeprom(blob)
                        self.logger.info("EEPROM saved to session")
                    else:
                        self.logger.info("EEPROM already stored for this checksum")
                    self.web.eeprom_maps   = decode_eeprom_maps(blob)
                    self.web.eeprom_params = decode_params(blob, ver)
                    self.web.bike_serial   = int.from_bytes(blob[12:14], 'little')
                    self.web.ecu_identity  = resolve_ecu(ver) or {}
                    self.logger.info(f"EEPROM ready — {len(self.web.eeprom_params)} params | Serial={self.web.bike_serial} | ECU={self.web.ecu_identity.get('name','?')} ({self.web.ecu_identity.get('ddfi','?')})")
                else:
                    self.logger.warning("EEPROM could not be read — session not opened")
            else:
                self.logger.warning("ECU did not respond — continuing without ECU")
        except Exception as e:
            self.logger.warning(f"ECU no disponible: {e}")

        # 2. Start RT and sysmon threads
        self._ecu_thread = threading.Thread(
            target=self._ecu_loop, daemon=True, name="ecu-rt"
        )
        self._ecu_thread.start()
        self._sysmon_thread = threading.Thread(
            target=self._sysmon_loop, daemon=True, name="sysmon"
        )
        self._sysmon_thread.start()

        # 3. Configurar red (hotspot por defecto)
        self.logger.info("Iniciando NetworkManager...")
        self.network.setup()
        
        # 2. Iniciar servidor web
        self.logger.info("Iniciando servidor web...")
        self.web.start()
        
        # 3. Loop principal (solo mantiene vivo + status)
        self.logger.info("Sistema listo. Esperando conexiones...")
        self.logger.info(f"Accede al dashboard en: http://{self.network.get_ip()}:8080")
        
        last_status = 0
        while self._running:
            time.sleep(1)
            
            # Log de status cada 30 segundos
            now = time.time()
            if now - last_status > 30:
                mode = self.network.current_mode()
                ip = self.network.get_ip()
                self.logger.info(f"Status: modo={mode} ip={ip}")
                last_status = now
            
            # Check shutdown desde web
            if self.web.pending_shutdown:
                self.logger.info("Shutdown solicitado desde web")
                self._poweroff_requested = True
                self._running = False
        
        # Cleanup
        self.shutdown()
    
    def shutdown(self):
        """Limpieza al salir."""
        self.logger.info("Deteniendo servicios...")
        self.web.stop()
        self.network.stop_monitor()
        
        if self._poweroff_requested and not self.no_poweroff:
            self.logger.info("Apagando sistema...")
            subprocess.run(["sudo", "/usr/sbin/poweroff"], check=False)
        else:
            self.logger.info("Logger detenido (sin apagar)")


def main():
    parser = argparse.ArgumentParser(description=f"Buell Logger {LOGGER_VERSION}")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Puerto serial ECU")
    parser.add_argument("--sessions-dir", default="/home/pi/buell/sessions", help="Directorio de sesiones")
    parser.add_argument("--buell-dir", default="/home/pi/buell", help="Directorio de configuración")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--no-poweroff", action="store_true", help="No apagar al salir")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger = BuellLogger(
        port=args.port,
        sessions_dir=args.sessions_dir,
        buell_dir=args.buell_dir,
        no_poweroff=args.no_poweroff
    )
    logger.run()


if __name__ == "__main__":
    main()
