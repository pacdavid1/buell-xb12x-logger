import os
"""
WebServer - HTTP server con endpoints para red y status
v2.1.0 - Fix scan GET, redirect URL, switch status polling
"""

import csv
import io
import json
import logging
import urllib.parse
import re
import subprocess
import threading
import mimetypes
import time
import zlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys as _sys
_sys.path.insert(0, '/home/pi/buell')
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.eeprom_params import decode_params as _decode_eeprom_params
import datetime


from web.utils import _get_version
from web.handlers.fuel import FuelHandlerMixin
from web.handlers.sessions import SessionsHandlerMixin
from web.handlers.eeprom import EepromHandlerMixin
from web.handlers.wifi import WifiHandlerMixin
from web.handlers.gps import GpsHandlerMixin
from web.handlers.tuner import TunerHandlerMixin
from web.handlers.system import SystemHandlerMixin
from web.handlers.rides import RidesHandlerMixin

class DashboardHandler(
    FuelHandlerMixin, SessionsHandlerMixin, EepromHandlerMixin,
    WifiHandlerMixin, GpsHandlerMixin, TunerHandlerMixin,
    SystemHandlerMixin, RidesHandlerMixin,
    BaseHTTPRequestHandler
):

    server_instance = None

    def log_message(self, format, *args):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, code=200):
        body = html.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]

        # Static files
        if self.path.startswith("/static/"):
            self._handle_static(self.path)
            return

        _routes = {
            '/tuner/sessions': self._handle_tuner_sessions,
            '/tuner/maps': self._handle_tuner_maps,
            '/tuner/merge': self._handle_tuner_merge,
            '/sessions_vs': self._handle_sessions_vs,
            '/sessions_vs/compare': self._handle_sessions_vs_compare,
            '/sessions_vs/download': self._handle_sessions_vs_download,
            '/tuner': self._handle_tuner,
            '/': self._handle_index,
            '/index.html': self._handle_index,
            '/live.json': self._handle_live_json,
            '/coverage.json': self._handle_coverage_json,
            '/rides': self._handle_rides,
            '/suggested_msq': self._handle_suggested_msq,
            '/eeprom/download': self._handle_eeprom_download,
            '/eeprom/sessions-list': self._handle_eeprom_sessions_list,
            "/eeprom/propose":  self._handle_eeprom_propose,
            '/eeprom/msq':      self._handle_eeprom_msq,
            '/burns':           self._handle_burns_list,
            '/msq/download':    self._handle_msq_download,
            '/tuning_report': self._handle_tuning_report,
            '/maps': self._handle_maps,
            '/eeprom': self._handle_eeprom,
            '/wifi/saved': self._handle_wifi_saved,
            '/wifi/scan': self._handle_wifi_scan,
            '/wifi/status': self._handle_wifi_status,
            '/gps_fix': self._handle_gps_fix,
            '/gps_track': self._handle_gps_track,
            '/ride_note': self._handle_ride_note,
            '/session_events': self._handle_session_events,
            '/session_events/data':     self._handle_session_events_data,
            '/session_events/download': self._handle_session_events_download,
            '/sessions_launch': self._handle_sessions_launch,
            '/sessions_launch/data': self._handle_sessions_launch_data,
            '/fuel': self._handle_fuel,
            '/fuel/status': self._handle_fuel_status,
            '/fuel/reserve': self._handle_fuel_reserve,
            '/fuel/refuel': self._handle_fuel_refuel,
            '/fuel/consumption': self._handle_fuel_consumption,
        }
        handler = _routes.get(path)
        if handler:
            handler(path)
            return

        if path.startswith('/csv/'):
            self._handle_csv(path)
            return

        if path.startswith('/ride/'):
            self._handle_ride(path)
            return

        if path.startswith('/errorlog/viz'):
            self._handle_errorlog_viz(path)
            return
        if path.startswith('/errorlog/'):
            self._handle_errorlog(path)
            return

        if path.startswith('/wifi/redirect_url'):
            self._handle_wifi_redirect_url(path)
            return


        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'

        try:
            payload = json.loads(body)
        except Exception as e:
            logging.warning(f"Invalid JSON: {e} -- body={body[:80]!r}")
            payload = {}

        _routes = {
            '/network': self._handle_post_network,
            '/wifi/connect': self._handle_post_wifi_connect,
            '/wifi/add': self._handle_post_wifi_add,
            '/wifi/forget': self._handle_post_wifi_forget,
            '/shutdown': self._handle_post_shutdown,
            '/keepalive': self._handle_post_keepalive,
            '/git_pull': self._handle_post_git_pull,
            '/ride_note': self._handle_post_ride_note,
            '/close_ride': self._handle_post_close_ride,
            '/restart_logger': self._handle_post_restart_logger,
            '/reboot_pi': self._handle_post_reboot_pi,
            '/ride/launch_event': self._handle_ride_launch_event,
            '/coverage/targets': self._handle_coverage_targets,
            '/eeprom/burn':       self._handle_eeprom_burn,
            '/eeprom/revert':     self._handle_eeprom_revert,
        }
        handler = _routes.get(path)
        if handler:
            handler(path, payload)
            return

        self._json({"error": "unknown endpoint"}, 404)

    def _handle_static(self, path=None):
        path = self.path.split("?", 1)[0].removeprefix("/")
        base = os.path.realpath(os.path.dirname(__file__))
        fpath = os.path.realpath(os.path.join(base, path))
        if os.path.commonpath([base, fpath]) == base and os.path.isfile(fpath):
            mime, _ = mimetypes.guess_type(fpath)
            with open(fpath, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
            return
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

    def _load_html(self):
        template = Path(__file__).parent / 'templates' / 'index.html'
        if template.exists():
            return template.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version())
        return "<h1>Buell Logger</h1><p>templates/index.html no encontrado</p>"


    def _get_live_data(self):
        data = dict(self.server_instance.ecu_live or {})
        gps = self.server_instance.gps
        if gps:
            fix = gps.get_fix()
            data.update(fix.as_dict())
        return data

    def _get_live(self):
        net = self.server_instance.network
        _snap = self.server_instance.cell_tracker.snapshot() if self.server_instance.cell_tracker else (None, None)
        _ecu_ok = self.server_instance.ecu_connected
        _ss = self.server_instance.serial_stats or {}
        _bat_v = _ss.get("bat_voltage")
        _bat_soc = _ss.get("bat_soc")
        if not _ecu_ok:
            _sys = "ecu_lost"
        elif (_bat_soc is not None and _bat_soc < 10) or (_bat_v is not None and _bat_v < 3.15):
            _sys = "bat_crit"
        elif (_bat_soc is not None and _bat_soc < 30) or (_bat_v is not None and _bat_v < 3.5):
            _sys = "bat_low"
        else:
            _sys = "ok"
        return {

            "ts":              time.time(),
            "logger_version":  _get_version(),
            "network_mode":    net.current_mode(),
            "ip":              net.get_ip(),
            "switch_status":   net.get_switch_status(),
            "ride_active":     self.server_instance.ride_active,
            "waiting":         not self.server_instance.ride_active,
            "ride_num":        self.server_instance.session.current_ride_num if self.server_instance.session else 0,
            "elapsed_s":       self.server_instance.elapsed_s,
            "ecu_connected":   _ecu_ok,
            "ecu_lost_s":      self.server_instance.ecu_lost_s,
            "live":            self._get_live_data(),
            "cells":           _snap[0] or {},
            "active_cell":     _snap[1],
            "objectives":      [],
            "serial_stats":    self.server_instance.serial_stats,
            "bike_serial":     self.server_instance.bike_serial,
            "ecu_identity":    self.server_instance.ecu_identity,
            "sys_status":      _sys,
        }



class WebServer:

    # Targets de coverage por flavor (segundos validos requeridos)
    COVERAGE_TARGETS_DEFAULT = {
        "SWEET":  30.0,
        "TIPOUT": 15.0,
        "WOT":    10.0,
        "BITTER":  0.0,
    }

    def _set_coverage_targets(self, body):
        flavors = {"SWEET", "TIPOUT", "WOT", "BITTER"}
        for k, v in body.items():
            if k in flavors:
                self._coverage_targets[k] = float(v)

    def _get_coverage(self):
        """Cobertura unificada: segundos, EGO, flavors por celda."""
        if not self.cell_tracker:
            return {"error": "tracker no disponible", "cells": {}, "summary": {}}
        snap, active = self.cell_tracker.snapshot()
        targets = self._coverage_targets
        flavors = [f for f in ("SWEET", "TIPOUT", "WOT") if targets.get(f, 0) > 0]
        cells_out = {}
        summary = {f: {"done": 0, "total": 0, "pct": 0.0} for f in flavors}
        for key, c in snap.items():
            fc   = c.get("flavor_counts", {})
            conf = c.get("confidence", 0.0)
            entry = {
                "seconds": c.get("seconds", 0.0),
                "ego_avg": c.get("ego_avg", 100.0),
                "confidence": conf,
                "o2_adc_avg": c.get("o2_adc_avg", None),
                "flavors": {},
            }
            for f in flavors:
                ts = targets[f]
                actual = fc.get(f, 0.0)
                conv = conf >= 0.8
                done = actual >= ts and conv
                pct = round(min(100.0, actual / ts * 100), 1) if ts > 0 else 0.0
                entry["flavors"][f] = {
                    "seconds": round(actual, 1), "target_s": ts,
                    "pct": pct, "converged": conv, "done": done
                }
                summary[f]["total"] += 1
                if done: summary[f]["done"] += 1
            cells_out[key] = entry
        for f in flavors:
            t, d = summary[f]["total"], summary[f]["done"]
            summary[f]["pct"] = round(d/t*100, 1) if t > 0 else 0.0
        return {
            "targets": targets, "cells": cells_out, "summary": summary,
            "active_cell": active, "n_cells": len(cells_out),
        }

    def __init__(self, host='0.0.0.0', port=8080, buell_dir=None):
        self.host             = host
        self.port             = port
        self.buell_dir        = Path(buell_dir) if buell_dir else Path('/home/pi/buell')
        self.network          = None
        self._server          = None
        self._thread          = None
        self.pending_shutdown = False
        self.last_keepalive   = time.time()
        self.ecu_live         = {}
        self.ecu_connected    = False
        self.ecu_lost_s       = 0.0
        self.ride_active      = False
        self.elapsed_s        = 0.0
        self.eeprom_maps      = {}
        self.eeprom_params    = {}
        self.serial_stats     = {'bps': 0, 'pct': 0.0, 'tx': 0, 'rx': 0, 'buf_in': 0, 'buf_pct': 0.0, 'cpu_pct': 0.0, 'cpu_temp': 0.0, 'mem_pct': 0.0, 'humidity_pct': None, 'bat_voltage': None, 'bat_soc': None, 'bat_charging': False}
        self.bike_serial      = None
        self.ecu_identity     = {}   # {name, dbfile, ddfi, remark}
        self.cell_tracker     = None
        self._coverage_targets = dict(self.COVERAGE_TARGETS_DEFAULT)
        self._data_lock = threading.RLock()
        self._rides_cache = None          # cache for _get_rides()
        self._rides_cache_time = 0        # timestamp of cache
        self._rides_cache_lock = threading.Lock()

    def _get_rides(self):
        # Cache: serve from cache if < 5 seconds old
        with self._rides_cache_lock:
            if self._rides_cache is not None and time.time() - self._rides_cache_time < 5:
                return self._rides_cache
        rides = []
        sessions_path = self.buell_dir / 'sessions'
        if not sessions_path.exists():            return rides
        for session_dir in sorted(sessions_path.iterdir()):
            if not session_dir.is_dir():
                continue
            meta_file = session_dir / 'session_metadata.json'
            fw = ''
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        fw = json.load(f).get('version_string', '')
                except Exception:
                    pass
            summary_nums = set()
            for sf in sorted(session_dir.glob('ride_*_summary.json')):
                try:
                    with open(sf) as f:
                        summary = json.load(f)
                    ride_num = summary.get('ride_num', 0)
                    summary_nums.add(ride_num)
                    note_path = session_dir / f'ride_{ride_num:03d}_notes.txt'
                    has_note = note_path.exists()
                    note_preview = ''
                    if has_note:
                        try:
                            note_preview = note_path.read_text(encoding='utf-8').split('\n')[0][:60]
                        except Exception:
                            pass
                    el_path = session_dir / f'ride_{ride_num:03d}_errorlog.json'
                    has_errorlog = el_path.exists()
                    errorlog_events = 0
                    if has_errorlog:
                        try:
                            with open(el_path) as ef:
                                el = json.load(ef)
                            errorlog_events = el.get('summary', {}).get('total_events', len(el.get('events', [])))
                        except Exception:
                            pass
                    rides.append({
                        'session': session_dir.name,
                        'firmware': fw,
                        'filename': sf.name,
                        'ride_num': ride_num,
                        'samples': summary.get('samples', 0),
                        'duration_s': summary.get('duration_s', 0),
                        'parts': summary.get('parts', 1),
                        'close_reason': summary.get('reason', ''),
                        'opened_utc': summary.get('opened_utc', ''),
                        'closed_utc': summary.get('closed_utc', ''),
                        'has_note': has_note,
                        'note_preview': note_preview,
                        'dtc_events': summary.get('dtc_events', []),
                        'has_errorlog': has_errorlog,
                        'errorlog_events': errorlog_events,
                    })
                except Exception:
                    pass
            for rf in sorted(session_dir.glob('ride_[0-9]*.csv')):
                # Skip continuation parts (_p2, _p3, etc.)
                if re.search(r'_p\d+$', rf.stem):
                    continue
                try:
                    rnum = int(rf.stem.split('_')[-1])
                    if rnum in summary_nums:
                        continue
                    opened_utc = ''
                    n = 0
                    # Fast path: read header + first data line only, then count with sum()
                    with open(rf) as f:
                        line = f.readline()
                        while line and line.startswith('#'):
                            line = f.readline()
                        if not line:
                            continue
                        header = line.strip().split(',')
                        first_data = f.readline()
                        if first_data and not first_data.startswith('#'):
                            try:
                                idx = header.index('timestamp_iso')
                                opened_utc = first_data.strip().split(',')[idx]
                            except Exception:
                                pass
                    # Count data lines efficiently (C-optimized sum)
                    n = sum(1 for _ in open(rf) if not _.startswith('#')) - 1
                    rides.append({
                        'session': session_dir.name, 'firmware': fw,
                        'filename': rf.name, 'ride_num': rnum,
                        'samples': n, 'duration_s': 0, 'parts': 1,
                        'opened_utc': opened_utc,
                    })
                except Exception:
                    pass
        result = sorted(rides, key=lambda r: (r['session'], r.get('ride_num', 0)))
        # Update cache
        with self._rides_cache_lock:
            self._rides_cache = result
            self._rides_cache_time = time.time()
        return result

    def start(self):
        DashboardHandler.server_instance = self
        self._server = ThreadingHTTPServer((self.host, self.port), DashboardHandler)
        self._server.daemon_threads = True  # reclaim threads after each request
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="web-server"
        )
        self._thread.start()
        logging.getLogger("WebServer").info(f"HTTP en http://{self.host}:{self.port}")

    def stop(self):
        if self._server:
            self._server.shutdown()


# ── Sessions VS engine ───────────────────────────────────────────────────────
from web.vs_engine import (
    _maps_differ, _merge_maps, _fmtk, CACHE_VERSION, _cache_lock,
    _eeprom_to_msq, _compare_sessions_cached,
)
# ── end Sessions VS engine ────────────────────────────────────────────────────
# ── FASE7 ───────────────────────────────────────────────────────────────────
from web.f7 import (
    _F7_N, _F7_WINDOW, _F7_THRESH, _F7_EVENTS_V,
    _f7_resample, _f7_dtw, _f7_rolling_std, _f7_detect_events,
    _f7_ba_consistent, _f7_sub_divide_by_bucket_a, _f7_cluster,
    _f7_temporal_stats, _f7_match_cross_session, _f7_load_session_clusters,
)
# ── end FASE7 ────────────────────────────────────────────────────────────────

# ── Launch analysis ─────────────────────────────────────────────────────────
from web.launch import (
    detect_launches, _s_std, cluster_launches,
    match_clusters, _compare_sessions,
)
# ── end Launch analysis ───────────────────────────────────────────────────────
