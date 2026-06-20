#!/usr/bin/env python3
"""
ECU CSV logger — standalone subprocess, independent of the web server.

Run by main.py via subprocess.Popen. Never import from this module; run as __main__.

IPC directory (/tmp/buell, tmpfs):
  reads : sysmon.json   — CPU/baro/battery stats written by main process _sysmon_loop
          gps.json      — GPS fix dict written by main process _sysmon_loop
          burn_req.json — EEPROM burn request; subprocess deletes it after reading
          control.json  — one-shot command (e.g. {"cmd": "close_ride"})
  writes: live.json     — RT frame + ride/serial state (every LIVE_EVERY frames)
          cells.json    — CellTracker snapshot (every CELLS_EVERY frames)
          ecu_init.json — version + session_checksum (on ECU connect / post-burn)
          burn_res.json — EEPROM burn result (keyed by req_id)
"""
import argparse
import base64
import json
import logging
import os
import random
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ecu.connection import DDFI2Connection
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.protocol import (load_vss_calibration, save_vss_calibration,
                          update_vss_calibration, vss_changed_significantly)
from ecu.session import CellTracker, RideErrorLog, SessionManager

# ── Constants (mirror main.py) ────────────────────────────────────────────────
TARGET_HZ            = 8.0
INTERVAL             = 1.0 / TARGET_HZ
RPM_START            = 300
RPM_STOP             = 100
STOP_CONFIRM_S       = 5.0
MAX_CONSEC_ERRORS    = 30
SERIAL_TX_BYTES      = 9
SERIAL_RX_BYTES      = 107
MAX_FIFO_PCT         = 50
MAX_SERIAL_BPS       = 960.0
SESSION_OPEN_DELAY   = 0.5
ECU_RETRY_INTERVAL   = 5.0
ECU_READ_ERROR_DELAY = 0.2
HARD_RECONNECT_DELAY = 0.5
LIVE_EVERY           = 4    # frames between live.json writes  (~0.5 s at 8 Hz)
CELLS_EVERY          = 30   # frames between cells.json writes (~3.75 s at 8 Hz)

_running = True


def _stop(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


# ── IPC helpers ───────────────────────────────────────────────────────────────

def _read(path: Path, default=None):
    """Read JSON file; return default on any error."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {} if default is None else default


def _write(path: Path, data):
    """Atomic write via rename (safe on tmpfs)."""
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data))
        tmp.rename(path)
    except Exception:
        pass


# ── EEPROM helpers ─────────────────────────────────────────────────────────────

def _load_eeprom(ecu: DDFI2Connection, sessions_dir: Path, log) -> bytes:
    try:
        blob = ecu.read_full_eeprom()
        if blob:
            return blob
    except Exception as e:
        log.warning(f"EEPROM read failed: {e}")
    bins = sorted(sessions_dir.glob("*/eeprom.bin"), key=lambda p: p.stat().st_mtime)
    if bins:
        with open(bins[-1], 'rb') as f:
            log.warning("Using cached EEPROM blob")
            return f.read()
    log.warning("No EEPROM available — stub")
    return b'\x00' * 64


def _try_cached_session(session: SessionManager, sessions_dir: Path, log):
    if session.current_checksum is None:
        bins = sorted(sessions_dir.glob("*/eeprom.bin"), key=lambda p: p.stat().st_mtime)
        if bins:
            with open(bins[-1], 'rb') as f:
                blob = f.read()
            session.open_session('cached', blob)
            log.warning("Session opened from cached EEPROM")


def _publish_ecu_init(ipc_dir: Path, ecu_version: str, session: SessionManager):
    _write(ipc_dir / 'ecu_init.json', {
        'version': ecu_version,
        'session_checksum': session.current_checksum,
        'session_dir': str(session.current_session_dir) if session.current_session_dir else None,
        'ride_num': session.current_ride_num,
    })


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(port: str, sessions_dir: Path, buell_dir: Path, ipc_dir: Path):
    global _running

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [EcuLogger] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("EcuLogger")
    ipc_dir.mkdir(parents=True, exist_ok=True)
    (ipc_dir / 'logger.pid').write_text(str(os.getpid()))

    ecu       = DDFI2Connection(port)
    session   = SessionManager(sessions_dir)
    tracker   = CellTracker()
    error_log = RideErrorLog()

    load_vss_calibration(str(buell_dir / 'vss_cal.json'))
    session.recover_orphan_rides()
    log.info(f"ECU logger started — port={port}")

    ride_active       = False
    ecu_version       = None
    rpm_zero_since    = None
    consecutive_errors = 0
    ecu_lost_since    = None
    last_lost_interval = -1
    _frame            = 0
    _last_reconnect_t = 0.0
    _last_fifo_flush  = 0.0
    _serial_bytes     = 0
    _serial_window    = time.monotonic()
    _serial_stats: dict = {}

    while _running:
        t0 = time.monotonic()

        # ── Control commands (close_ride etc.) ────────────────────────
        ctrl_path = ipc_dir / 'control.json'
        if ctrl_path.exists():
            try:
                ctrl = _read(ctrl_path)
                ctrl_path.unlink(missing_ok=True)
                if ctrl.get('cmd') == 'close_ride' and ride_active:
                    elapsed_s = (time.monotonic() - session.ride_start_time
                                 if session.ride_start_time else 0.0)
                    objectives_cfg = _read(buell_dir / 'objectives.json', {})
                    session.close_current_ride(
                        ctrl.get('reason', 'web_request'),
                        tracker_snapshot=tracker.snapshot(),
                        objectives_cfg=objectives_cfg)
                    error_log.flush()
                    tracker.reset()
                    ride_active = False
                    rpm_zero_since = None
                    log.info("Ride closed by web request")
            except Exception as e:
                log.warning(f"control cmd: {e}")

        # ── Connect ECU ───────────────────────────────────────────────
        if ecu.ser is None or not ecu.ser.is_open:
            try:
                ecu.connect()
                ecu_version = ecu.get_version()
                if ecu_version:
                    log.info(f"ECU: {ecu_version}")
                    blob = _load_eeprom(ecu, sessions_dir, log)
                    session.open_session(ecu_version, blob)
                    time.sleep(SESSION_OPEN_DELAY)
                    session.save_eeprom(blob)
                    _publish_ecu_init(ipc_dir, ecu_version, session)
                    _axes = _decode_eeprom_maps(blob, ecu_version).get('axes', {})
                    if _axes.get('fuel_rpm') and _axes.get('fuel_load'):
                        tracker.set_bins(_axes['fuel_rpm'], _axes['fuel_load'])
                    log.info(f"Session: {session.current_checksum}")
                    consecutive_errors = 0
                    ecu_lost_since = None
                else:
                    _try_cached_session(session, sessions_dir, log)
                    time.sleep(ECU_RETRY_INTERVAL + random.uniform(0, 1.5))
                    continue
            except Exception as e:
                log.debug(f"ECU unavailable: {e}")
                if ecu_lost_since is None:
                    ecu_lost_since = time.monotonic()
                if time.monotonic() - ecu_lost_since >= 10.0:
                    ecu.usb_power_cycle()
                time.sleep(ECU_RETRY_INTERVAL + random.uniform(0, 1.5))
                continue

        # ── Burn request ──────────────────────────────────────────────
        burn_req_path = ipc_dir / 'burn_req.json'
        if not ride_active and burn_req_path.exists():
            try:
                req = _read(burn_req_path)
                burn_req_path.unlink(missing_ok=True)
                proposed = bytes(base64.b64decode(req['eeprom_b64']))
                req_id   = req.get('req_id', 0)
                try:
                    result = ecu.write_full_eeprom(proposed)
                except Exception as be:
                    result = {'written': 0, 'verified': False, 'diffs_found': 0, 'errors': [str(be)]}
                result['req_id'] = req_id
                _write(ipc_dir / 'burn_res.json', result)
                if result.get('verified'):
                    session.open_session(ecu_version or 'post-burn', proposed)
                    session.save_eeprom(proposed)
                    _publish_ecu_init(ipc_dir, ecu_version or 'post-burn', session)
                    _axes = _decode_eeprom_maps(proposed, ecu_version or '').get('axes', {})
                    if _axes.get('fuel_rpm') and _axes.get('fuel_load'):
                        tracker.set_bins(_axes['fuel_rpm'], _axes['fuel_load'])
                log.info(f"Burn req_id={req_id}: verified={result.get('verified')}")
            except Exception as e:
                log.warning(f"Burn error: {e}")

        # ── Read RT frame ─────────────────────────────────────────────
        elapsed_s = (time.monotonic() - session.ride_start_time
                     if ride_active and session.ride_start_time else 0.0)
        try:
            data = ecu.get_rt_data()
        except Exception as e:
            log.warning(f"RT read: {e}")
            if ride_active:
                error_log.serial_exception(elapsed_s=elapsed_s, exc_msg=e,
                                           consecutive_before=consecutive_errors)
            data = None
            # consecutive_errors incremented once below in data is None check
            if ecu_lost_since is None:
                ecu_lost_since = time.monotonic()
            time.sleep(ECU_READ_ERROR_DELAY)

        if data is None:
            consecutive_errors += 1
            if ecu_lost_since is None:
                ecu_lost_since = time.monotonic()
            lost = time.monotonic() - ecu_lost_since
            interval = int(lost) // 3
            if interval != last_lost_interval:
                last_lost_interval = interval
                log.info(f"ECU silent {lost:.0f}s")
                if ride_active:
                    error_log.ecu_timeout(elapsed_s=elapsed_s, lost_s=lost,
                                          last_valid_t=elapsed_s - lost)
            if not ride_active and consecutive_errors >= MAX_CONSEC_ERRORS:
                ecu.disconnect()
                time.sleep(ECU_RETRY_INTERVAL + random.uniform(0, 1.5))
                consecutive_errors = 0
                ecu_lost_since = None
            if ecu_lost_since and lost >= 3.0 and time.monotonic() - _last_reconnect_t >= 5.0:
                log.info(f"Hard reconnect at {lost:.0f}s")
                try:
                    ecu.disconnect()
                    time.sleep(HARD_RECONNECT_DELAY)
                    ecu.connect()
                    ver = ecu.get_version()
                    if ver:
                        log.info("ECU back after hard reconnect")
                        ecu_version = ver
                        consecutive_errors = 0
                        ecu_lost_since = None
                        last_lost_interval = -1
                        _last_reconnect_t = 0.0
                except Exception as re_e:
                    log.warning(f"Hard reconnect failed: {re_e}")
                    _last_reconnect_t = time.monotonic()
            _write(ipc_dir / 'live.json', {
                'ecu_connected': False, 'ecu_lost_s': lost,
                'ride_active': ride_active, 'elapsed_s': elapsed_s,
                'session_checksum': session.current_checksum,
                'session_dir': str(session.current_session_dir) if session.current_session_dir else None,
                'ride_num': session.current_ride_num,
            })
            time.sleep(max(0, INTERVAL - (time.monotonic() - t0)))
            continue

        # ── Valid frame ───────────────────────────────────────────────
        consecutive_errors = 0
        ecu_lost_since = None
        last_lost_interval = -1
        rpm = data.get('RPM', 0) or 0

        # Ride start
        if not ride_active and rpm >= RPM_START:
            if session.current_checksum is None:
                log.warning("RPM but no session — skipping ride start")
            else:
                try:
                    session.start_ride()
                    ride_active = True
                    rpm_zero_since = None
                    error_log.start(
                        ride_num=session.current_ride_num,
                        session_checksum=session.current_checksum,
                        session_dir=str(session.current_session_dir))
                    log.info(f"Ride {session.current_ride_num:03d} started")
                except RuntimeError as e:
                    log.warning(f"start_ride: {e}")

        if ride_active:
            data['buf_in'] = ecu.ser.in_waiting if ecu.ser and ecu.ser.is_open else 0
            if data['buf_in'] > 384 * MAX_FIFO_PCT / 100 and ecu.ser and ecu.ser.is_open:
                now = time.monotonic()
                if now - _last_fifo_flush > 5:
                    ecu.ser.reset_input_buffer()
                    _last_fifo_flush = now
                    log.warning(f"FIFO flush: {data['buf_in']}b")

            # Sysmon injection (non-critical — CSV still written if this fails)
            try:
                ss = _read(ipc_dir / 'sysmon.json')
                data['cpu_pct']      = ss.get('cpu_pct', 0)
                data['cpu_temp']     = ss.get('cpu_temp', 0)
                data['mem_pct']      = ss.get('mem_pct', 0)
                data['ttl_pct']      = ss.get('pct', 0)
                data['baro_hPa']     = ss.get('baro_hPa')
                data['baro_temp_c']  = ss.get('baro_temp_c')
                data['humidity_pct'] = ss.get('humidity_pct')
                data['bat_voltage']  = ss.get('bat_voltage')
                data['bat_soc']      = ss.get('bat_soc')
            except Exception as e:
                log.debug(f"sysmon IPC: {e}")

            # GPS injection (non-critical)
            try:
                data.update(_read(ipc_dir / 'gps.json'))
            except Exception as e:
                log.debug(f"gps IPC: {e}")

            # VSS calibration (non-critical)
            try:
                if (data.get('gps_valid')
                        and (data.get('gps_speed_kmh') or 0) > 10
                        and (data.get('VS_KPH') or 0) > 10):
                    update_vss_calibration(
                        gps_kph=data['gps_speed_kmh'], vss_kph=data['VS_KPH'],
                        fl_decel=data.get('fl_decel', 0), fl_wot=data.get('fl_wot', 0),
                    )
                    if vss_changed_significantly():
                        save_vss_calibration(str(buell_dir / 'vss_cal.json'))
            except Exception as e:
                log.debug(f"VSS cal: {e}")

            session.write_sample(data, time.time())

        tracker.update(data)

        # Ride stop
        if ride_active and rpm < RPM_STOP:
            if rpm_zero_since is None:
                rpm_zero_since = time.monotonic()
            elif time.monotonic() - rpm_zero_since >= STOP_CONFIRM_S:
                try:
                    objectives_cfg = _read(buell_dir / 'objectives.json', {})
                    session.close_current_ride(
                        f"RPM=0 por {STOP_CONFIRM_S:.0f}s",
                        tracker_snapshot=tracker.snapshot(),
                        objectives_cfg=objectives_cfg)
                    error_log.flush()
                    tracker.reset()
                    ride_active = False
                    rpm_zero_since = None
                    log.info(f"Ride {session.current_ride_num:03d} closed")
                except Exception as e:
                    log.error(f"close_ride: {e}")
                    ride_active = False
                    rpm_zero_since = None
        elif rpm >= RPM_STOP:
            rpm_zero_since = None

        # Serial stats (1 Hz)
        _serial_bytes += SERIAL_TX_BYTES + SERIAL_RX_BYTES
        _now_s = time.monotonic()
        if _now_s - _serial_window >= 1.0:
            bps = _serial_bytes
            in_w = ecu.ser.in_waiting if ecu.ser and ecu.ser.is_open else 0
            _serial_stats = {
                'bps': bps,
                'pct': round(min(bps / MAX_SERIAL_BPS * 100, 100.0), 1),
                'tx': SERIAL_TX_BYTES * 8,
                'rx': SERIAL_RX_BYTES * 8,
                'buf_in': in_w,
                'buf_pct': round(in_w / 384.0 * 100, 1),
            }
            _serial_bytes = 0
            _serial_window = _now_s

        # IPC writes
        _frame += 1
        if _frame % LIVE_EVERY == 0:
            try:
                live = {k: v for k, v in data.items()
                        if isinstance(v, (int, float, str, bool, type(None)))}
                live.update(_serial_stats)
                live.update({
                    'ecu_connected': True, 'ecu_lost_s': 0.0,
                    'ride_active': ride_active, 'elapsed_s': elapsed_s,
                    'session_checksum': session.current_checksum,
                    'session_dir': str(session.current_session_dir) if session.current_session_dir else None,
                    'ride_num': session.current_ride_num,
                    'active_cell': tracker.active,
                })
                _write(ipc_dir / 'live.json', live)
            except Exception as e:
                log.debug(f"live.json: {e}")

        if _frame % CELLS_EVERY == 0:
            try:
                snap, active = tracker.snapshot()
                _write(ipc_dir / 'cells.json', {'cells': snap, 'active_cell': active})
            except Exception as e:
                log.debug(f"cells.json: {e}")

        time.sleep(max(0, INTERVAL - (time.monotonic() - t0)))

    # ── Clean shutdown ────────────────────────────────────────────────
    if ride_active:
        try:
            objectives_cfg = _read(buell_dir / 'objectives.json', {})
            session.close_current_ride(
                "service stopped",
                tracker_snapshot=tracker.snapshot(),
                objectives_cfg=objectives_cfg)
            error_log.flush()
        except Exception as e:
            log.error(f"shutdown close_ride: {e}")
    try:
        ecu.disconnect()
    except Exception:
        pass
    try:
        (ipc_dir / 'logger.pid').unlink(missing_ok=True)
    except Exception:
        pass
    log.info("ECU logger stopped")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Buell ECU CSV logger subprocess')
    p.add_argument('--port',         default='/dev/ttyUSB0')
    p.add_argument('--sessions-dir', default='/home/pi/buell/sessions')
    p.add_argument('--buell-dir',    default='/home/pi/buell')
    p.add_argument('--ipc-dir',      default='/tmp/buell')
    a = p.parse_args()
    run(port=a.port,
        sessions_dir=Path(a.sessions_dir),
        buell_dir=Path(a.buell_dir),
        ipc_dir=Path(a.ipc_dir))
