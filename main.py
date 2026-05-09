#!/usr/bin/env python3
"""
Buell Logger - Main Entry Point (Modular v1.1)
Refactorizado: Limpieza de duplicidades y separación de responsabilidades.
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

sys.path.insert(0, str(Path(__file__).parent))

from network.manager import NetworkManager
from web.server import WebServer
from ecu.connection import DDFI2Connection
from ecu.eeprom import decode_eeprom_maps, decode_eeprom_params
from ecu.eeprom_params import decode_params
from ecu.version_resolver import resolve_ecu
from ecu.session import SessionManager, CellTracker, cell_key, RideErrorLog
from gps.reader import GPSReader
try:
    import smbus2 as _smbus2
    from bmp280 import BMP280 as _BMP280
    _BMP280_OK = True
except ImportError:
    _BMP280_OK = False

# ── Constantes de configuración (Adiós a los "números mágicos") ───────────
TARGET_HZ = 8.0
INTERVAL = 1.0 / TARGET_HZ
RPM_START = 300
RPM_STOP = 100
STOP_CONFIRM_S = 5.0
MAX_CONSEC_ERRORS = 30
SERIAL_TX_BYTES = 9
SERIAL_RX_BYTES = 107
MAX_FIFO_PCT = 50  # 192 bytes es el 50% de 384
MAX_SERIAL_BPS = 960.0


def _get_version():
    try:
        import re
        with open("/home/pi/buell/CHANGELOG.md") as f:
            cl = f.read()
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"

LOGGER_VERSION = _get_version()


class BuellLogger:
    """Orquestador principal."""
    
    def __init__(self, port="/dev/ttyUSB0", sessions_dir="/home/pi/buell/sessions", 
                 buell_dir="/home/pi/buell", no_poweroff=False):
        self.port = port
        self.sessions_dir = Path(sessions_dir)
        self.buell_dir = Path(buell_dir)
        self.no_poweroff = no_poweroff
        self.logger = logging.getLogger("BuellLogger")
        
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.buell_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._shutting_down = False
        self._poweroff_requested = False
        self._ecu_thread = None
        self._sysmon_thread = None
        
        # Componentes modulares
        self.network = NetworkManager()
        self.web = WebServer(host='0.0.0.0', port=8080, buell_dir=self.buell_dir)
        self.ecu = DDFI2Connection(self.port)
        self.session = SessionManager(self.sessions_dir)
        self.tracker = CellTracker()
        self.gps = GPSReader()
        self._bmp280 = None
        if _BMP280_OK:
            try:
                _bus = _smbus2.SMBus(2)
                self._bmp280 = _BMP280(i2c_dev=_bus, i2c_addr=0x77)
                self.logger.info("BMP280 inicializado OK (0x77)")
            except Exception as e:
                self.logger.warning(f"BMP280 no disponible: {e}")
        self.error_log = RideErrorLog()

        # Inyección de dependencias para el servidor web
        self.web.network = self.network
        self.web.cell_tracker = self.tracker
        self.web.gps = self.gps
        self.web.session = self.session
        
        # Carga segura de objetivos
        obj_path = self.buell_dir / 'objectives.json'
        self.objectives_cfg = {}
        if obj_path.exists():
            with open(obj_path, 'r') as f:
                self.objectives_cfg = json.load(f)
        
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        self.logger.info(f"Señal {signum} recibida - deteniendo...")
        self._running = False

    # ── Métodos auxiliares extraídos (DRY - Don't Repeat Yourself) ─────

    def _load_eeprom_blob(self, ecu_version):
        """Intenta leer la EEPROM del ECU, con fallback a disco o versión."""
        self.logger.info("Reading EEPROM to detect bike identity...")
        blob = self.ecu.read_full_eeprom()
        
        if blob is not None:
            return blob
            
        # Fallback 1: cached blob on disk
        _bins = sorted(self.sessions_dir.glob("*/eeprom.bin"), key=lambda p: p.stat().st_mtime)
        if _bins:
            with open(_bins[-1], 'rb') as f:
                blob = f.read()
            self.logger.warning("EEPROM fetch failed — using cached blob from disk")
            return blob
            
        # Fallback 2: version string as checksum seed
        self.logger.warning("EEPROM fetch failed — using version string as checksum")
        return ecu_version.encode().ljust(64, b'\x00')

    def _update_web_ecu_state(self, blob, ecu_version):
        """Actualiza el estado de la web con los datos de la EEPROM y ECU."""
        self.web.eeprom_maps = decode_eeprom_maps(blob)
        self.web.eeprom_params = decode_params(blob, ecu_version)
        self.web.bike_serial = int.from_bytes(blob[12:14], 'little')
        self.web.ecu_identity = resolve_ecu(ecu_version) or {}

    # ── Hilos de ejecución ────────────────────────────────────────────

    def _sysmon_loop(self):
        """System monitor thread — Único lugar donde se leen stats del SO."""
        _cpu_prev = None
        while self._running:
            stats = {'cpu_pct': 0.0, 'cpu_temp': 0.0, 'mem_pct': 0.0}
            
            try:
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    stats['cpu_temp'] = round(int(f.read().strip()) / 1000.0, 1)
            except Exception: pass
            
            try:
                with open('/proc/stat') as f:
                    _cpu = list(map(int, f.readline().split()[1:]))
                _idle, _total = _cpu[3], sum(_cpu)
                if _cpu_prev is not None:
                    _di = _idle - _cpu_prev[0]
                    _dt = _total - _cpu_prev[1]
                    stats['cpu_pct'] = round((1.0 - _di / _dt) * 100, 1) if _dt else 0.0
                _cpu_prev = (_idle, _total)
            except Exception: pass
            
            try:
                with open('/proc/meminfo') as f:
                    _mem = {k.strip(): int(v.split()[0]) for line in f for k, v in [line.split(':')]}
                _mt, _mf = _mem['MemTotal'], _mem['MemAvailable']
                stats['mem_pct'] = round((_mt - _mf) / _mt * 100, 1)
            except Exception: pass

            if self._bmp280:
                try:
                    _p = round(self._bmp280.get_pressure(),    2)
                    _t = round(self._bmp280.get_temperature(), 2)
                    stats['baro_hPa']   = _p if 650 <= _p <= 1100 else None
                    stats['baro_temp_c']= _t if -10 <= _t <= 60  else None
                except Exception:
                    stats['baro_hPa']   = None
                    stats['baro_temp_c']= None
            self.web.serial_stats = stats

            # GPS watchdog
            if not self.gps._thread.is_alive():
                self.logger.warning("GPS thread muerto — reiniciando...")
                try:
                    self.gps = GPSReader()
                    self.gps.start()
                    self.web.gps = self.gps # Mantener referencia actualizada
                except Exception as e:
                    self.logger.warning(f"GPS restart failed: {e}")
                    
            time.sleep(2.0)

    def _ecu_loop(self):
        """Thread de lectura RT — Limpio, solo se centra en el protocolo serie."""
        ride_active = False
        ecu_version = None
        rpm_zero_since = None
        consecutive_errors = 0
        ecu_lost_since = None
        last_lost_interval = -1
        _serial_bytes = 0
        _serial_window = time.monotonic()

        self.logger.info("ECU loop iniciado")

        while self._running:
            t0 = time.monotonic()

            # ── Conectar si el puerto no está abierto ──────────────────
            if self.ecu.ser is None or not self.ecu.ser.is_open:
                try:
                    self.ecu.connect()
                    ecu_version = self.ecu.get_version()
                    if ecu_version:
                        self.logger.info(f"ECU reconnected: {ecu_version}")
                        
                        blob = self._load_eeprom_blob(ecu_version)
                        self.session.open_session(ecu_version, blob)
                        time.sleep(0.5)
                        
                        if not (self.session.current_session_dir / 'eeprom.bin').exists():
                            self.session.save_eeprom(blob)
                            
                        self._update_web_ecu_state(blob, ecu_version)
                        self.logger.info(f"Session opened from reconnect: {self.session.current_checksum}")
                        consecutive_errors = 0
                        ecu_lost_since = None
                    else:
                        self.logger.warning("ECU no respondió — reintento en 5s")
                        if self.session.current_checksum is None:
                            _bins = sorted(self.sessions_dir.glob("*/eeprom.bin"), key=lambda p: p.stat().st_mtime)
                            if _bins:
                                with open(_bins[-1], 'rb') as f: blob = f.read()
                                self.session.open_session('cached', blob)
                                self._update_web_ecu_state(blob, 'cached')
                                self.logger.warning(f"Session opened from cached EEPROM")
                        time.sleep(5)
                        continue
                except Exception as e:
                    self.logger.debug(f"ECU no disponible: {e} — reintento en 5s")
                    if ecu_lost_since is None: ecu_lost_since = time.monotonic()
                    no_ecu_s = time.monotonic() - ecu_lost_since
                    if no_ecu_s >= 10.0 and int(no_ecu_s) % 10 == 0:
                        self.logger.info(f"USB power cycle — {no_ecu_s:.0f}s sin ECU")
                        self.ecu.usb_power_cycle()
                    time.sleep(5)
                    continue

            # ── Leer frame RT ──────────────────────────────────────────
            elapsed_s = time.monotonic() - self.session.ride_start_time if (ride_active and self.session.ride_start_time) else 0.0

            try:
                data = self.ecu.get_rt_data()
            except Exception as e:
                self.logger.warning(f"SerialException: {e}")
                if ride_active: self.error_log.serial_exception(elapsed_s=elapsed_s, exc_msg=e, consecutive_before=consecutive_errors)
                data = None
                consecutive_errors += 1
                if ecu_lost_since is None: ecu_lost_since = time.monotonic()
                time.sleep(0.2)

            if data is None:
                consecutive_errors += 1
                if ecu_lost_since is None: ecu_lost_since = time.monotonic()
                lost_total = time.monotonic() - ecu_lost_since
                
                self.web.ecu_connected = False
                self.web.ecu_lost_s = lost_total

                lost_interval = int(lost_total) // 10
                if lost_interval != last_lost_interval:
                    last_lost_interval = lost_interval
                    self.logger.info(f"ECU sin respuesta {lost_total:.0f}s")
                    if ride_active: self.error_log.ecu_timeout(elapsed_s=elapsed_s, lost_s=lost_total, last_valid_t=elapsed_s - lost_total)

                if not ride_active and consecutive_errors >= MAX_CONSEC_ERRORS:
                    self.logger.info("ECU no responde — cerrando puerto")
                    self.ecu.disconnect()
                    time.sleep(5)
                    consecutive_errors = 0
                    ecu_lost_since = None

                if ecu_lost_since is not None and lost_total >= 30.0 and consecutive_errors % 30 == 0:
                    self.logger.info(f"Hard reconnect — {lost_total:.0f}s sin ECU")
                    if ride_active: self.error_log.reconnect_attempt(elapsed_s=elapsed_s, trigger="auto_30s", attempt_n=consecutive_errors // 30, success=False, time_s=lost_total)
                    
                    if lost_total >= 15.0 and consecutive_errors % 15 == 0: self.ecu.usb_power_cycle()
                    elif lost_total >= 30.0 and consecutive_errors % 30 == 0: self.ecu.usb_reset(); time.sleep(0.5)
                    
                    try:
                        self.ecu.disconnect(); time.sleep(0.5); self.ecu.connect()
                        if self.ecu.get_version():
                            self.logger.info("ECU responde tras hard reconnect")
                            consecutive_errors = 0; ecu_lost_since = None; last_lost_interval = -1
                            if ride_active: self.error_log.reconnect_attempt(elapsed_s=elapsed_s, trigger="auto_30s", attempt_n=consecutive_errors // 30, success=True, time_s=lost_total)
                    except Exception as e: self.logger.warning(f"Hard reconnect falló: {e}")

                time.sleep(max(0, INTERVAL - (time.monotonic() - t0)))
                continue

            # ── Frame válido ───────────────────────────────────────────
            consecutive_errors = 0; ecu_lost_since = None; last_lost_interval = -1

            self.web.ecu_live = data
            self.web.ecu_connected = True
            self.web.ecu_lost_s = 0.0
            self.web.ride_active = ride_active
            self.web.elapsed_s = elapsed_s
            if ride_active: self.error_log.update_last_sample(data)
            
            rpm = data.get("RPM", 0) or 0

            if not ride_active and rpm >= RPM_START:
                if self.session.current_checksum is None:
                    self.logger.warning("RPM detected but no active session — skipping ride start")
                else:
                    try:
                        self.session.start_ride()
                        ride_active = True; rpm_zero_since = None
                        self.error_log.start(ride_num=self.session.current_ride_num, session_checksum=self.session.current_checksum, session_dir=str(self.session.current_session_dir))
                        self.logger.info(f"Ride {self.session.current_ride_num:03d} iniciado")
                    except RuntimeError as e:
                        self.logger.warning(f"start_ride falló: {e}")

            if ride_active:
                data['buf_in'] = self.ecu.ser.in_waiting if self.ecu.ser and self.ecu.ser.is_open else 0
                if data['buf_in'] > (384 * (MAX_FIFO_PCT / 100)) and self.ecu.ser and self.ecu.ser.is_open:
                    self.ecu.ser.reset_input_buffer()
                    self.logger.warning(f"AUTO-FLUSH FIFO buf_in={data['buf_in']}b >{MAX_FIFO_PCT}% — flushed")
                
                # Inyectar stats del sistema (que ya calculó el hilo _sysmon_loop)
                ss = self.web.serial_stats or {}
                data['ttl_pct'] = ss.get('pct', 0)
                data['cpu_pct'] = ss.get('cpu_pct', 0)
                data['cpu_temp'] = ss.get('cpu_temp', 0)
                data['mem_pct']     = ss.get('mem_pct', 0)
                data['baro_hPa']    = ss.get('baro_hPa')
                data['baro_temp_c'] = ss.get('baro_temp_c')
                
                data.update(self.gps.get_fix().as_dict())
                self.session.write_sample(data, time.time())
                
            self.tracker.update(data)

            if ride_active and rpm < RPM_STOP:
                if rpm_zero_since is None: rpm_zero_since = time.monotonic()
                elif time.monotonic() - rpm_zero_since >= STOP_CONFIRM_S:
                    self.session.close_current_ride(f"RPM=0 por {STOP_CONFIRM_S:.0f}s", tracker_snapshot=self.tracker.snapshot(), objectives_cfg=self.objectives_cfg)
                    self.error_log.flush(); self.tracker.reset()
                    ride_active = False; rpm_zero_since = None
            elif rpm >= RPM_STOP: rpm_zero_since = None

            # ── Conteo de bytes seriales (Simplificado) ───────────────
            _serial_bytes += SERIAL_TX_BYTES + SERIAL_RX_BYTES
            _now = time.monotonic()
            if _now - _serial_window >= 1.0:
                bps = _serial_bytes
                pct = round(min(bps / MAX_SERIAL_BPS * 100, 100.0), 1)
                in_w = self.ecu.ser.in_waiting if self.ecu.ser and self.ecu.ser.is_open else 0
                buf_pct = round(in_w / 384.0 * 100, 1)
                
                # Aquí solo actualizamos BPS y Buffer, el resto viene de sysmon
                current_stats = self.web.serial_stats or {}
                current_stats.update({'bps': bps, 'pct': pct, 'tx': SERIAL_TX_BYTES*8, 'rx': SERIAL_RX_BYTES*8, 'buf_in': in_w, 'buf_pct': buf_pct})
                self.web.serial_stats = current_stats
                
                _serial_bytes = 0; _serial_window = _now

            time.sleep(max(0, INTERVAL - (time.monotonic() - t0)))

        # ── Cierre al detener el servicio ──────────────────────────────
        if ride_active:
            self.session.close_current_ride("servicio detenido", tracker_snapshot=self.tracker.snapshot(), objectives_cfg=self.objectives_cfg)
            self.error_log.flush()
        self.logger.info("ECU loop detenido")


    def run(self):
        """Loop principal."""
        self._running = True
        self.logger.info(f"Buell Logger {LOGGER_VERSION}")
        self.logger.info(f"Sessions: {self.sessions_dir} | Buell dir: {self.buell_dir}")
        
        # 1. Conectar ECU
        self.logger.info("Conectando a ECU...")
        try:
            self.ecu.connect()
            ver = self.ecu.get_version()
            if ver:
                self.logger.info(f"ECU connected: {ver}")
                time.sleep(3.0) # Wait for ECU to stabilize
                
                blob = self._load_eeprom_blob(ver)
                if blob:
                    self.session.open_session(ver, blob)
                    if not (self.session.current_session_dir / 'eeprom.bin').exists():
                        self.session.save_eeprom(blob)
                        self.logger.info("EEPROM saved to session")
                    
                    self._update_web_ecu_state(blob, ver)
                    self.logger.info(f"EEPROM ready — {len(self.web.eeprom_params)} params | Serial={self.web.bike_serial} | ECU={self.web.ecu_identity.get('name','?')} ({self.web.ecu_identity.get('ddfi','?')})")
                else:
                    self.logger.warning("EEPROM could not be read — session not opened")
            else:
                self.logger.warning("ECU did not respond — continuing without ECU")
        except Exception as e:
            import traceback
            self.logger.warning(f"ECU no disponible: {e}\n{traceback.format_exc()}")

        # 2. Iniciar hilos de fondo
        self.gps.start()
        self._ecu_thread = threading.Thread(target=self._ecu_loop, daemon=True, name="ecu-rt")
        self._ecu_thread.start()
        self._sysmon_thread = threading.Thread(target=self._sysmon_loop, daemon=True, name="sysmon")
        self._sysmon_thread.start()

        # 3. Configurar red
        self.logger.info("Iniciando NetworkManager...")
        self.network.setup()
        
        # 4. Iniciar servidor web
        self.logger.info("Iniciando servidor web...")
        self.web.start()
        
        # 5. Loop principal
        self.logger.info(f"Sistema listo. Accede al dashboard en: http://{self.network.get_ip()}:8080")
        
        last_status = 0
        while self._running:
            time.sleep(1)
            now = time.time()
            if now - last_status > 30:
                self.logger.info(f"Status: modo={self.network.current_mode()} ip={self.network.get_ip()}")
                last_status = now
            
            if self.web.pending_shutdown:
                self.logger.info("Shutdown solicitado desde web")
                self._poweroff_requested = True
                self._running = False
        
        self.shutdown()
    
    def shutdown(self):
        """Limpieza al salir."""
        self.logger.info("Deteniendo servicios...")
        try:
            if self.session and self.session.current_csv_fh:
                self.logger.info("Cerrando ride activo por shutdown...")
                self.session.close_current_ride("shutdown", tracker_snapshot=self.tracker.snapshot(), objectives_cfg=self.objectives_cfg)
        except Exception as e:
            self.logger.warning(f"Error cerrando ride en shutdown: {e}")
            
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
