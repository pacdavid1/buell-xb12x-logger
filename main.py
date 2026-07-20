#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
Buell Logger — main process.

Owns: GPS reader, sysmon (BMP280/AHT20/CW2015), web server, network manager.
Spawns: ecu/logger_process.py as a subprocess that owns ECU serial + CSV writing.
IPC: /tmp/buell/*.json (tmpfs, atomic rename writes).
"""

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import subprocess
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from network.manager import NetworkManager
from web.server import WebServer
from ecu.eeprom import decode_eeprom_maps
from ecu.eeprom_params import decode_params
from ecu.version_resolver import resolve_ecu
from ecu.session import SessionManager, CellTracker
from gps.reader import GPSReader
from sensors.battery_guard import battery_discharging, prune_history
try:
    import smbus2 as _smbus2
    from bmp280 import BMP280 as _BMP280
    _BMP280_OK = True
except ImportError:
    _BMP280_OK = False

try:
    from sensors.aht20 import AHT20 as _AHT20
    _AHT20_OK = True
except ImportError:
    _AHT20_OK = False

from tools.health_journal import check as _health_check

try:
    from sensors.cw2015 import CW2015 as _CW2015
    _CW2015_OK = True
except ImportError:
    _CW2015_OK = False

# ── Constants ──────────────────────────────────────────────────────────────────
GPS_RESTART_DELAY   = 2.0
SENSOR_FAIL_BACKOFF_N = 5      # consecutive I2C failures before backing off
SENSOR_FAIL_BACKOFF_S = 300.0  # a doomed I2C read costs ~0.8 s kernel CPU (measured 2026-07-15)
MAIN_LOOP_HEARTBEAT = 1.0
IPC_DIR             = Path('/tmp/buell')
IPC_POLL_S          = 0.25   # how often IPC reader polls live.json
DISK_WARN_PCT       = 85.0   # dashboard badge turns yellow
DISK_STOP_PCT       = 95.0   # auto-stop ECU logger to avoid writing to a full disk


def _get_version():
    try:
        import re
        cl = (Path(__file__).parent / "CHANGELOG.md").read_text(encoding='utf-8')
        # Skip the instruction block; real entries start after PROMPT_END.
        marker = cl.find("PROMPT_END -->")
        if marker != -1:
            cl = cl[marker:]
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


LOGGER_VERSION = _get_version()


def _ipc_write(path: Path, data: dict):
    """Atomic IPC write via temp file replace (Path.rename does not
    overwrite an existing destination on Windows; Path.replace does)."""
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
    except Exception:
        pass


class BuellLogger:
    """Main orchestrator — web server + sensors; ECU logging in subprocess."""

    def __init__(self, port="/dev/ttyUSB0", sessions_dir="/home/pi/buell/sessions",
                 buell_dir="/home/pi/buell", no_poweroff=False):
        self.port         = port
        self.sessions_dir = Path(sessions_dir)
        self.buell_dir    = Path(buell_dir)
        self.no_poweroff  = no_poweroff
        self.logger       = logging.getLogger("BuellLogger")

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.buell_dir.mkdir(parents=True, exist_ok=True)

        self._running         = False
        self._shutting_down   = False
        self._poweroff_requested = False
        self._logger_proc     = None
        self._ipc_dir         = IPC_DIR
        self._ipc_reader_thread  = None
        self._sysmon_thread      = None
        self._ipc_reader_heartbeat  = float('inf')  # set inside thread, not here
        self._sysmon_heartbeat      = float('inf')
        self._bat_voltages    = []
        self._bat_socs        = []
        self._bat_history     = []   # (monotonic_t, voltage, smoothed_soc) over BAT_DISCHARGE_HORIZON_S
        self._boot_soc        = None
        self._last_veto_log   = 0.0
        self._disk_stop_triggered = False

        self.network = NetworkManager(buell_dir=self.buell_dir)
        self.web     = WebServer(host='0.0.0.0', port=8080, buell_dir=self.buell_dir)
        # SessionManager in main process is a sync target only (IPC reader writes attrs).
        self.session = SessionManager(self.sessions_dir)
        self.tracker = CellTracker()
        self.gps     = GPSReader()
        self._bmp280 = None
        self._aht20  = None
        self._bmp_fail = 0
        self._bmp_retry_at = 0.0
        self._aht_fail = 0
        self._aht_retry_at = 0.0
        self._cw2015 = None
        self._smbus  = None

        if _BMP280_OK or _AHT20_OK or _CW2015_OK:
            try:
                self._smbus = _smbus2.SMBus(2)
                if _BMP280_OK:
                    self._bmp280 = _BMP280(i2c_dev=self._smbus, i2c_addr=0x77)
                    self.logger.info("BMP280 initialized OK (0x77)")
            except Exception as e:
                self.logger.warning(f"BMP280 unavailable: {e}")

        if _AHT20_OK and self._smbus:
            try:
                _aht = _AHT20(i2c_dev=self._smbus)
                if _aht.begin():
                    self._aht20 = _aht
                    self.logger.info("AHT20 initialized OK (0x38)")
                else:
                    self.logger.warning("AHT20 did not respond to begin()")
            except Exception as e:
                self.logger.warning(f"AHT20 unavailable: {e}")

        if _CW2015_OK:
            try:
                self._ups_bus = _smbus2.SMBus(1)
                self._cw2015 = _CW2015(i2c_dev=self._ups_bus)
                self.logger.info("CW2015 (UPS-Lite) initialized OK i2c-1 (0x62)")
            except Exception as e:
                self.logger.warning(f"CW2015 unavailable: {e}")

        self.web.network      = self.network
        self.web.cell_tracker = self.tracker
        self.web.gps          = self.gps
        self.web.session      = self.session
        self.web._ipc_dir     = self._ipc_dir

        obj_path = self.buell_dir / 'objectives.json'
        self.objectives_cfg = {}
        if obj_path.exists():
            with open(obj_path) as f:
                self.objectives_cfg = json.load(f)

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        self.logger.info(f"Signal {signum} received — stopping...")
        self._running = False

    def _update_web_ecu_state(self, blob: bytes, ecu_version: str):
        """Reload EEPROM maps into web server state."""
        self.web.eeprom_maps   = decode_eeprom_maps(blob, ecu_version)
        self.web.eeprom_params = decode_params(blob, ecu_version)
        self.web.bike_serial   = int.from_bytes(blob[12:14], 'little')
        self.web.ecu_identity  = resolve_ecu(ecu_version) or {}
        axes = self.web.eeprom_maps.get('axes', {})
        if axes.get('fuel_rpm') and axes.get('fuel_load'):
            self.tracker.set_bins(axes['fuel_rpm'], axes['fuel_load'])

    # ── IPC helpers ───────────────────────────────────────────────────────────

    def _start_logger_subprocess(self):
        """Spawn ECU logger subprocess, killing any stale instance first."""
        self._ipc_dir.mkdir(parents=True, exist_ok=True)
        pid_file = self._ipc_dir / 'logger.pid'
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(0.5)
            except Exception:
                pass
            try:
                pid_file.unlink(missing_ok=True)
            except Exception:
                pass
        cmd = [
            sys.executable,
            str(Path(__file__).parent / 'ecu' / 'logger_process.py'),
            '--port',         self.port,
            '--sessions-dir', str(self.sessions_dir),
            '--buell-dir',    str(self.buell_dir),
            '--ipc-dir',      str(self._ipc_dir),
        ]
        self._logger_proc = subprocess.Popen(cmd)
        self.logger.info(f"ECU logger subprocess started (PID={self._logger_proc.pid})")

    def _stop_logger_subprocess(self, timeout: float = 10.0):
        """SIGTERM the logger subprocess and wait."""
        if self._logger_proc is None or self._logger_proc.poll() is not None:
            return
        self.logger.info("Sending SIGTERM to ECU logger subprocess...")
        self._logger_proc.terminate()
        try:
            self._logger_proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.logger.warning("ECU logger did not stop in time — killing")
            self._logger_proc.kill()

    def _ipc_reader_loop(self):
        """Thread: reads IPC files from ECU subprocess, updates web state."""
        live_path  = self._ipc_dir / 'live.json'
        cells_path = self._ipc_dir / 'cells.json'
        init_path  = self._ipc_dir / 'ecu_init.json'
        _last_checksum   = None
        _last_cells_mtime = 0.0

        self._ipc_reader_heartbeat = time.monotonic()  # init at thread start
        while self._running:
            t0 = time.monotonic()

            # ecu_init.json: EEPROM reload when ECU connects or post-burn
            try:
                if init_path.exists():
                    init = json.loads(init_path.read_text())
                    cs = init.get('session_checksum')
                    if cs and cs != _last_checksum:
                        _last_checksum = cs
                        eeprom_path = self.sessions_dir / cs / 'eeprom.bin'
                        if eeprom_path.exists():
                            blob = eeprom_path.read_bytes()
                            ver  = init.get('version', 'unknown')
                            self._update_web_ecu_state(blob, ver)
                            self.logger.info(f"IPC: EEPROM reloaded for session {cs}")
                    if cs:
                        self.session.current_checksum   = cs
                        sd = init.get('session_dir')
                        self.session.current_session_dir = Path(sd) if sd else None
                        self.session.current_ride_num   = init.get('ride_num', 0)
            except Exception as e:
                self.logger.debug(f"IPC ecu_init: {e}")

            # live.json: RT state
            try:
                if live_path.exists():
                    live = json.loads(live_path.read_text())
                    with self.web._data_lock:
                        self.web.ecu_live      = live
                        self.web.ecu_connected = live.get('ecu_connected', False)
                    self.web.ecu_lost_s  = live.get('ecu_lost_s', 0.0)
                    self.web.ride_active = live.get('ride_active', False)
                    self.web.elapsed_s   = live.get('elapsed_s', 0.0)
                    # Sync serial stats from subprocess (bps/pct/buf)
                    serial_update = {k: live[k] for k in
                                     ('bps', 'pct', 'tx', 'rx', 'buf_in', 'buf_pct')
                                     if k in live}
                    if serial_update:
                        with self.web._data_lock:
                            existing = self.web.serial_stats or {}
                            existing.update(serial_update)
                            self.web.serial_stats = existing
                    # Sync session attributes (most current source)
                    if live.get('session_checksum'):
                        self.session.current_checksum = live['session_checksum']
                    if live.get('session_dir'):
                        self.session.current_session_dir = Path(live['session_dir'])
                    if live.get('ride_num') is not None:
                        self.session.current_ride_num = live['ride_num']
            except Exception as e:
                self.logger.debug(f"IPC live: {e}")

            # cells.json: CellTracker state (mtime-gated)
            try:
                if cells_path.exists():
                    mtime = cells_path.stat().st_mtime
                    if mtime > _last_cells_mtime:
                        _last_cells_mtime = mtime
                        cells_data = json.loads(cells_path.read_text())
                        self.tracker.set_snapshot(
                            cells_data.get('cells', {}),
                            cells_data.get('active_cell'))
            except Exception as e:
                self.logger.debug(f"IPC cells: {e}")

            self._ipc_reader_heartbeat = time.monotonic()
            time.sleep(max(0, IPC_POLL_S - (time.monotonic() - t0)))

    # ── Sysmon thread ──────────────────────────────────────────────────────────

    def _sysmon_loop(self):
        self._sysmon_heartbeat = time.monotonic()  # init at thread start
        """System monitor thread — reads sensors, writes sysmon.json + gps.json for subprocess."""
        _cpu_prev = None
        while self._running:
            stats = {'cpu_pct': 0.0, 'cpu_temp': 0.0, 'mem_pct': 0.0}

            try:
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    stats['cpu_temp'] = round(int(f.read().strip()) / 1000.0, 1)
            except Exception as e:
                self.logger.debug(f"sysmon: {e}")

            try:
                with open('/proc/stat') as f:
                    _cpu = list(map(int, f.readline().split()[1:]))
                _idle, _total = _cpu[3], sum(_cpu)
                if _cpu_prev is not None:
                    _di = _idle - _cpu_prev[0]
                    _dt = _total - _cpu_prev[1]
                    stats['cpu_pct'] = round((1.0 - _di / _dt) * 100, 1) if _dt else 0.0
                _cpu_prev = (_idle, _total)
            except Exception as e:
                self.logger.debug(f"sysmon: {e}")

            try:
                with open('/proc/meminfo') as f:
                    _mem = {k.strip(): int(v.split()[0]) for line in f for k, v in [line.split(':')]}
                _mt, _mf = _mem['MemTotal'], _mem['MemAvailable']
                stats['mem_pct'] = round((_mt - _mf) / _mt * 100, 1)
                if stats['mem_pct'] > 90:
                    self.logger.error(f"MEM {stats['mem_pct']}% — restarting to avoid OOM crash")
                    # SIGTERM subprocess so it can close the ride cleanly before we execv
                    # Give subprocess time to flush CSV + close ride before execv replaces us
                    self._stop_logger_subprocess(timeout=10.0)
                    time.sleep(0.5)  # extra margin for filesystem sync
                    os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                self.logger.debug(f"sysmon: {e}")

            try:
                du = shutil.disk_usage('/')
                stats['disk_free_gb']  = round(du.free / 1073741824, 1)
                stats['disk_used_pct'] = round(100 - du.free / du.total * 100, 1)
                if stats['disk_used_pct'] > DISK_STOP_PCT and not self._disk_stop_triggered:
                    self.logger.error(
                        f"DISK {stats['disk_used_pct']}% used ({stats['disk_free_gb']}GB free) "
                        "— stopping ECU logger to avoid writing to a full disk")
                    self._stop_logger_subprocess(timeout=10.0)
                    self._disk_stop_triggered = True
            except Exception as e:
                self.logger.debug(f"sysmon: {e}")

            # A read against a dead I2C device burns ~0.8 s of kernel CPU
            # (measured 2026-07-15: BMP280 off the bus made sysmon eat ~30%
            # CPU). After N consecutive failures, back off instead of
            # hammering the bus every cycle.
            if self._bmp280 and time.monotonic() >= self._bmp_retry_at:
                try:
                    _p = round(self._bmp280.get_pressure(),    2)
                    _t = round(self._bmp280.get_temperature(), 2)
                    stats['baro_hPa']    = _p if 650 <= _p <= 1100 else None
                    stats['baro_temp_c'] = _t if -10 <= _t <= 60  else None
                    self._bmp_fail = 0
                except Exception:
                    stats['baro_hPa']    = None
                    stats['baro_temp_c'] = None
                    self._bmp_fail += 1
                    if self._bmp_fail >= SENSOR_FAIL_BACKOFF_N:
                        self._bmp_retry_at = time.monotonic() + SENSOR_FAIL_BACKOFF_S
                        self.logger.warning(
                            f"BMP280 unreachable x{self._bmp_fail} — backing off "
                            f"{SENSOR_FAIL_BACKOFF_S:.0f}s (dead I2C read costs ~0.8s CPU)")

            if self._aht20 and time.monotonic() >= self._aht_retry_at:
                try:
                    _hum, _tmp = self._aht20.read()
                    stats['humidity_pct'] = _hum
                    self._aht_fail = 0
                except Exception:
                    stats['humidity_pct'] = None
                    self._aht_fail += 1
                    if self._aht_fail >= SENSOR_FAIL_BACKOFF_N:
                        self._aht_retry_at = time.monotonic() + SENSOR_FAIL_BACKOFF_S
                        self.logger.warning(
                            f"AHT20 unreachable x{self._aht_fail} — backing off "
                            f"{SENSOR_FAIL_BACKOFF_S:.0f}s (dead I2C read costs ~0.8s CPU)")

            if self._cw2015:
                try:
                    _bat = self._cw2015.read_all()
                    stats['bat_voltage']  = _bat.get('bat_voltage')
                    stats['bat_soc']      = _bat.get('bat_soc')
                    _hw_charging          = _bat.get('bat_charging')
                except Exception:
                    stats['bat_voltage']  = None
                    stats['bat_soc']      = None
                    _hw_charging          = None
            else:
                _hw_charging = None

            _v_now = stats.get('bat_voltage')
            if _v_now is not None:
                self._bat_voltages.append(_v_now)
                if len(self._bat_voltages) > 15:
                    self._bat_voltages.pop(0)

            _soc_raw = stats.get('bat_soc')
            if _soc_raw is not None:
                self._bat_socs.append(_soc_raw)
                if len(self._bat_socs) > 5:
                    self._bat_socs.pop(0)
                stats['bat_soc'] = sum(self._bat_socs) / len(self._bat_socs)

            if self._boot_soc is None and len(self._bat_socs) >= 3:
                _candidate = stats['bat_soc']
                if _candidate is not None and _candidate > 0:
                    self._boot_soc = _candidate
                    self.logger.info(f"Boot SOC captured: {self._boot_soc:.1f}%")
                else:
                    self.logger.warning("Boot SOC skipped: reading is 0 or None (sensor not ready)")

            # Hardware CHG_IND pin is authoritative; fall back to voltage trend
            if _hw_charging is not None:
                stats['bat_charging'] = _hw_charging
                stats['bat_trend']    = 'up' if _hw_charging else 'stable'
            elif len(self._bat_voltages) >= 3:
                _early = sum(self._bat_voltages[:2]) / 2
                _late  = sum(self._bat_voltages[-2:]) / 2
                _diff  = _late - _early
                if _diff > 0.005:
                    stats['bat_charging'] = True
                    stats['bat_trend']    = 'up'
                elif _diff < -0.005:
                    stats['bat_charging'] = False
                    stats['bat_trend']    = 'down'
                else:
                    _prev = stats.get('bat_charging', False)
                    stats['bat_trend']    = 'stable'
                    stats['bat_charging'] = _prev
            else:
                stats['bat_trend']    = 'stable'
                stats['bat_charging'] = False

            _health_check(stats, True, buell_dir=str(self.buell_dir))

            _soc = stats.get('bat_soc')
            _v   = stats.get('bat_voltage')
            _is_charging = stats.get('bat_charging', False)

            # Discharge detector: the CW2015 "charging" bit is unreliable
            # (reg 0x08 is RRT_ALERT, not a charge indicator) and vetoed the
            # shutdown on 2026-07-14 while the pack drained 30%->14%. A pack
            # losing SOC/voltage over 10 min is discharging, whatever it says.
            _mono = time.monotonic()
            if _v is not None or _soc is not None:
                self._bat_history.append((_mono, _v, _soc))
                self._bat_history = prune_history(self._bat_history, _mono)
            _discharging = battery_discharging(self._bat_history, _mono)

            if (_discharging or not _is_charging) and self._boot_soc is not None:
                _threshold, _v_threshold = self._get_shutdown_threshold()
                _v_crit  = _threshold <= 0
                _soc_low = _soc is not None and _soc < (_threshold if _threshold > 0 else 10.0)
                _v_low   = _v is not None and _v < _v_threshold
                if _v_crit or _soc_low or _v_low:
                    _v_s   = f'{_v:.2f}V'   if _v   is not None else '--V'
                    _soc_s = f'{_soc:.0f}%' if _soc is not None else '--%'
                    self.logger.warning(
                        f"BATTERY: {_v_s} / {_soc_s} "
                        f"(boot={self._boot_soc:.0f}%, soc_thr={_threshold:.0f}%, "
                        f"v_thr={_v_threshold:.2f}V, chg_claim={_is_charging}, "
                        f"discharging={_discharging}) — shutting down")
                    self._poweroff_requested = True
                    self._running = False
                    return
            elif _is_charging and self._boot_soc is not None:
                # Shutdown vetoed by the charge claim: make the veto visible
                # so a lying CHG_IND is diagnosable from the journal.
                _threshold, _ = self._get_shutdown_threshold()
                if (_soc is not None and _threshold > 0 and _soc < _threshold
                        and _mono - self._last_veto_log > 300):
                    self._last_veto_log = _mono
                    self.logger.info(
                        f"BATTERY: SOC {_soc:.0f}% below threshold "
                        f"{_threshold:.0f}% but charge claimed and no "
                        f"discharge trend — shutdown deferred")

            # Merge cpu/baro/battery into web serial_stats (bps/pct come from IPC reader)
            with self.web._data_lock:
                existing = self.web.serial_stats if self.web.serial_stats else {}
                existing.update(stats)
                self.web.serial_stats = existing

            # Write sysmon.json for subprocess (injected into CSV rows)
            _ipc_write(self._ipc_dir / 'sysmon.json', stats)

            # Write gps.json for subprocess
            try:
                _ipc_write(self._ipc_dir / 'gps.json', self.gps.get_fix().as_dict())
            except Exception as e:
                self.logger.debug(f"gps.json: {e}")

            # GPS watchdog
            if not self.gps.is_alive():
                now_gps = time.monotonic()
                if getattr(self, '_last_gps_restart', 0) and now_gps - self._last_gps_restart < 30:
                    self.logger.warning("GPS thread dead, skipping restart (cooldown)")
                else:
                    self.logger.warning("GPS thread dead — restarting...")
                    self._last_gps_restart = now_gps
                    try:
                        self.gps.stop()
                        self.gps = GPSReader()
                        self.gps.start()
                        self.web.gps = self.gps
                    except Exception as e:
                        self.logger.warning(f"GPS restart failed: {e}")

            self._sysmon_heartbeat = time.monotonic()
            time.sleep(GPS_RESTART_DELAY)

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _get_shutdown_threshold(self):
        """Return (soc_threshold, voltage_threshold) based on boot SOC tier."""
        boot = self._boot_soc if self._boot_soc is not None else 100.0
        if boot >= 30:   return 30.0, 3.50
        elif boot >= 20: return 20.0, 3.40
        elif boot >= 10: return 10.0, 3.30
        else:            return -1.0, 3.20

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        self.logger.info(f"Buell Logger {LOGGER_VERSION}")
        self.logger.info(f"Sessions: {self.sessions_dir} | Buell dir: {self.buell_dir}")

        # 1. Load EEPROM from disk for initial web state (subprocess refreshes after ECU connect)
        bins = sorted(self.sessions_dir.glob('*/eeprom.bin'), key=lambda p: p.stat().st_mtime)
        if bins:
            try:
                blob = bins[-1].read_bytes()
                ver = 'unknown'
                meta = bins[-1].parent / 'session_metadata.json'
                if meta.exists():
                    try:
                        with open(meta) as f:
                            ver = json.load(f).get('version_string', 'unknown') or 'unknown'
                    except Exception:
                        pass
                self._update_web_ecu_state(blob, ver)
                self.session.current_checksum    = bins[-1].parent.name
                self.session.current_session_dir = bins[-1].parent
                self.logger.info(f"Initial EEPROM loaded from disk: {self.session.current_checksum}")
            except Exception as e:
                self.logger.warning(f"Initial EEPROM load failed: {e}")

        # 2. Start GPS reader
        self.gps.start()

        # 3. Start sysmon thread
        self._sysmon_thread = threading.Thread(target=self._sysmon_loop, daemon=True, name="sysmon")
        self._sysmon_thread.start()

        # 4. Spawn ECU logger subprocess
        self._ipc_dir.mkdir(parents=True, exist_ok=True)
        self._start_logger_subprocess()

        # 5. Start IPC reader thread
        self._ipc_reader_thread = threading.Thread(
            target=self._ipc_reader_loop, daemon=True, name="ipc-reader")
        self._ipc_reader_thread.start()

        # 6. Configure network
        self.logger.info("Starting NetworkManager...")
        self.network.setup()

        # 7. Start web server
        self.logger.info("Starting web server...")
        self.web._main_app = self
        self.web.start()

        # 8. Main loop
        self.logger.info(f"System ready. Dashboard: http://{self.network.get_ip()}:8080")
        last_status = 0
        while self._running:
            try:
                self._check_threads()
                time.sleep(MAIN_LOOP_HEARTBEAT)
                now = time.time()
                if now - last_status > 30:
                    self.logger.info(
                        f"Status: mode={self.network.current_mode()} ip={self.network.get_ip()}")
                    last_status = now
                if self.web.pending_shutdown:
                    self.logger.info("Shutdown requested from web")
                    self._poweroff_requested = True
                    self._running = False
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                time.sleep(1)

        self.shutdown()

    def _check_threads(self):
        """Watchdog: restart dead or hung background threads and subprocess."""
        now = time.monotonic()
        heartbeats    = {"ipc-reader": self._ipc_reader_heartbeat, "sysmon": self._sysmon_heartbeat}
        stale_limits  = {"ipc-reader": 10.0,                       "sysmon": 15.0}
        thread_map    = {"ipc-reader": "_ipc_reader_thread",       "sysmon": "_sysmon_thread"}
        thread_targets= {"ipc-reader": (self._ipc_reader_loop, "ipc-reader"),
                         "sysmon":     (self._sysmon_loop,     "sysmon")}

        for name in ("ipc-reader", "sysmon"):
            thread = getattr(self, thread_map[name])
            if thread is None:
                continue
            last_hb = heartbeats[name]
            stale   = now - last_hb > stale_limits[name]
            dead    = not thread.is_alive()
            if not dead and not stale:
                continue
            last_restart = getattr(self, f"_last_{name.replace('-','_')}_restart", 0)
            if now - last_restart < 30:
                self.logger.warning(
                    f"Thread {name} dead/hung, cooldown {now-last_restart:.0f}s < 30s")
                continue
            self.logger.critical(f"Thread {name} is {'hung' if stale else 'dead'} — restarting")
            setattr(self, f"_last_{name.replace('-','_')}_restart", now)
            target, tname = thread_targets[name]
            new_thread = threading.Thread(target=target, daemon=True, name=tname)
            new_thread.start()
            setattr(self, thread_map[name], new_thread)

        # ECU logger subprocess watchdog
        if self._logger_proc is not None and self._logger_proc.poll() is not None:
            exit_code = self._logger_proc.returncode
            last = getattr(self, '_last_logger_proc_restart', 0)
            if now - last >= 30:
                self.logger.critical(
                    f"ECU logger subprocess exited (code={exit_code}) — restarting")
                setattr(self, '_last_logger_proc_restart', now)
                self._start_logger_subprocess()
            else:
                self.logger.warning(
                    f"ECU logger exited (code={exit_code}), cooldown {now-last:.0f}s")

    def _sleep_gps(self):
        """Send UBX-RXM-PMREQ to put M8N into backup mode (~15uA).
        Must be called while UART is still accessible (before poweroff).
        M8N wakes automatically on first UART byte from gpsd at next boot.
        On a plain service restart (no poweroff) we skip the M8N sleep and
        gpsd stop so gpsd.socket stays alive for the next start."""
        if self.gps:
            self.gps.stop()
        if not self._poweroff_requested:
            return
        import serial as _serial, struct as _struct
        GPS_PORT = '/dev/ttyS0'
        GPS_BAUD = 9600
        try:
            subprocess.run(['sudo', 'systemctl', 'stop', 'gpsd', 'gpsd.socket'],
                           capture_output=True, timeout=3)
            import time as _time
            _time.sleep(0.5)
            # UBX-RXM-PMREQ: duration=0 (indefinite), flags=0x02 (backup)
            payload = _struct.pack('<II', 0, 0x02)
            body    = bytes([0x02, 0x41]) + _struct.pack('<H', len(payload)) + payload
            ck_a = ck_b = 0
            for b in body:
                ck_a = (ck_a + b) & 0xFF
                ck_b = (ck_b + ck_a) & 0xFF
            pkt = b'\xb5\x62' + body + bytes([ck_a, ck_b])
            with _serial.Serial(GPS_PORT, GPS_BAUD, timeout=0.5) as ser:
                ser.write(pkt)
                ser.flush()
                _time.sleep(0.2)
            self.logger.info("GPS M8N sent to backup mode (15uA)")
        except Exception as e:
            self.logger.warning(f"GPS sleep failed (non-critical): {e}")

    def shutdown(self):
        self.logger.info("Stopping services...")

        # Each step is fenced: a failure here must never prevent the
        # poweroff below (the UI already told the user we are shutting down).
        # Stop ECU logger subprocess first — it closes the ride and
        # disconnects the ECU.
        steps = (
            ("gps-sleep",         self._sleep_gps),
            ("logger-subprocess", lambda: self._stop_logger_subprocess(timeout=10.0)),
            ("web-server",        self.web.stop),
            ("network-monitor",   self.network.stop_monitor),
        )
        for step_name, step in steps:
            try:
                step()
            except Exception as e:
                self.logger.error(f"Shutdown step {step_name} failed: {e}")

        if self._poweroff_requested and not self.no_poweroff:
            self.logger.info("Powering off system...")
            result = subprocess.run(["sudo", "-n", "/usr/sbin/poweroff"],
                                    capture_output=True, text=True, check=False)
            if result.returncode != 0:
                self.logger.error(
                    f"poweroff failed rc={result.returncode}: {result.stderr.strip()}")
        else:
            self.logger.info("Logger stopped (no poweroff)")


def main():
    parser = argparse.ArgumentParser(description=f"Buell Logger {LOGGER_VERSION}")
    parser.add_argument("--port",         default="/dev/ttyUSB0",          help="ECU serial port")
    parser.add_argument("--sessions-dir", default="/home/pi/buell/sessions", help="Sessions directory")
    parser.add_argument("--buell-dir",    default="/home/pi/buell",          help="Config directory")
    parser.add_argument("--log-level",    default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--no-poweroff",  action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    BuellLogger(
        port=args.port,
        sessions_dir=args.sessions_dir,
        buell_dir=args.buell_dir,
        no_poweroff=args.no_poweroff,
    ).run()


if __name__ == "__main__":
    main()
