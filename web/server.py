"""
WebServer - HTTP server con endpoints para red y status
v2.1.0 - Fix scan GET, redirect URL, switch status polling
"""

import json
import urllib.parse
import re
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys as _sys
_sys.path.insert(0, '/home/pi/buell')
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.eeprom_params import decode_params as _decode_eeprom_params


def _get_version():
    try:
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"

class DashboardHandler(BaseHTTPRequestHandler):

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
        net  = self.server_instance.network

        if path == '/tuner/sessions':
            import glob as _glob
            sessions = []
            for d in self.server_instance.buell_dir.glob('sessions/*/session_metadata.json'):
                try:
                    with open(d) as mf: meta = json.load(mf)
                    ep = d.parent / 'eeprom.bin'
                    serial = None
                    if ep.exists() and ep.stat().st_size >= 1206:
                        try:
                            b = ep.read_bytes()
                            if len(b) >= 14: serial = int.from_bytes(b[12:14], 'little')
                        except: pass
                    else:
                        continue
                    sessions.append({'id': d.parent.name, 'version': meta.get('version_string', '?'), 'rides': meta.get('total_rides', 0), 'created': meta.get('created_utc', '')[:10], 'serial': serial})
                except Exception: pass
            sessions.sort(key=lambda s: s['created'], reverse=True)
            self._json({'sessions': sessions})
            return

        if path == '/tuner/maps':
            import urllib.parse as _up
            params = _up.parse_qs(_up.urlparse(self.path).query)
            sess = params.get('session', [''])[0]
            if not sess: self._json({'error': 'Falta session'}, 400); return
            blob_path = self.server_instance.buell_dir / 'sessions' / sess / 'eeprom.bin'
            if not blob_path.exists(): self._json({'error': 'No hay eeprom.bin'}, 404); return
            try:
                self._json(_decode_eeprom_maps(blob_path.read_bytes()))
            except Exception as e:
                self._json({'error': f'Error al leer mapa: {e}'})
            return

        if path == '/sessions_vs':
            try:
                f = Path(__file__).parent / 'templates' / 'sessions_vs.html'
                self._html(f.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return
        if path == '/sessions_vs/compare':
            import urllib.parse as _up
            params = _up.parse_qs(_up.urlparse(self.path).query)
            sa = params.get('a', [''])[0]
            sb = params.get('b', [''])[0]
            if not sa or not sb:
                self._json({'error': 'Faltan sesiones'}, 400); return
            try:
                self._json(_compare_sessions(self.server_instance.buell_dir, sa, sb))
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return
        if path == '/tuner' or path == '/tuner.html':
            try:
                tuner_file = Path(__file__).parent / 'templates' / 'tuner.html'
                if tuner_file.exists():
                    self._html(tuner_file.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
                else:
                    self._html("<h1>Buell Tuner - Página no encontrada</h1>")
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return

        if path in ('/', '/index.html'):
            self._html(self._load_html())
            return

        if path == '/live.json':
            self._json(self._get_live())
            return

        if path.startswith('/csv/'):
            fname = path.split('/csv/')[-1].split('?')[0]
            rides = self.server_instance._get_rides()
            fname_summary = fname.replace('.csv', '_summary.json')
            match = next((r for r in rides if r['filename']==fname or r['filename']==fname_summary), None)
            if not match:
                self._json({'error': 'not found'}, 404)
                return
            try:
                sdir = self.server_instance.buell_dir / 'sessions' / match['session']
                ride_num = match.get('ride_num', 0)
                parts = match.get('parts', 1)
                chunks = []
                first = True
                for part in range(1, parts+1):
                    suffix = f'_p{part}' if part > 1 else ''
                    csv_stem = match['filename'].replace('_summary.json','').replace('.csv','')
                    csv_path = sdir / f'{csv_stem}{suffix}.csv'
                    if not csv_path.exists(): continue
                    with open(csv_path, 'rb') as fh:
                        if not first: fh.readline()
                        chunks.append(fh.read())
                    first = False
                raw = b''.join(chunks)
                import zlib as _zlib
                accept_enc = self.headers.get('Accept-Encoding', '')
                use_gzip = 'gzip' in accept_enc
                body = _zlib.compress(raw, level=6, wbits=31) if use_gzip else raw
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                if use_gzip: self.send_header('Content-Encoding', 'gzip')
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return
        if path.startswith('/ride/'):
            fname = path.split('/ride/')[-1].split('?')[0]
            rides = self.server_instance._get_rides()
            fname_summary = fname.replace('.csv', '_summary.json')
            match = next((r for r in rides if r['filename']==fname or r['filename']==fname_summary), None)
            if not match:
                self._json({'error': 'not found'}, 404)
                return
            sdir = self.server_instance.buell_dir / 'sessions' / match['session']
            fpath = sdir / fname
            if not fpath.exists():
                fpath = sdir / fname.replace('_summary.json', '.csv')
            try:
                if fpath.suffix == '.json':
                    with open(fpath) as fh:
                        s = json.load(fh)
                    self._json({'cells': s.get('cells', {}), 'objectives': s.get('objectives', [])})
                else:
                    self._json({'cells': {}, 'objectives': []})
            except Exception as e:
                self._json({'error': str(e)}, 500)
            return
        if path.startswith('/errorlog/'):
            fname = path.split('/errorlog/')[-1].split('?')[0]
            rides = self.server_instance._get_rides()
            ride_num = int(fname.replace('_errorlog.json','').replace('ride_','').replace('.csv','')) if fname else 0
            match = next((r for r in rides if r.get('ride_num')==ride_num), None)
            if not match:
                self._json({'error': 'not found'}, 404)
                return
            sdir = self.server_instance.buell_dir / 'sessions' / match['session']
            el_path = sdir / f'ride_{ride_num:03d}_errorlog.json'
            if el_path.exists():
                try:
                    with open(el_path) as fh:
                        self._json(json.load(fh))
                except Exception as e:
                    self._json({'error': str(e)}, 500)
            else:
                self._json({'has_errorlog': False, 'events': [], 'summary': {}})
            return
        if path == '/rides':

            rides = self.server_instance._get_rides()
            self._json({"rides": rides})
            return
        if path == '/suggested_msq':
            cs = self.server_instance.session.current_checksum
            if not cs:
                self._json({"error": "sin sesion activa"}); return
            msq_path = Path('/home/pi/buell/sessions') / cs / ('suggested_' + cs + '.msq')
            if not msq_path.exists():
                self._json({"error": "sin MSQ generado aun"}); return
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml')
            self.send_header('Content-Disposition',
                'attachment; filename="suggested_' + cs + '.msq"')
            self.end_headers()
            self.wfile.write(msq_path.read_bytes())
            return
        if path == '/maps':
            # Soporte para pedir mapa de una sesion especifica: /maps?session=XXXX
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            req_session = params.get('session', [''])[0]
            if req_session:
                ses_path = self.server_instance.buell_dir / 'sessions' / req_session / 'eeprom.bin'
                if ses_path.exists():
                    try:
                        blob = ses_path.read_bytes()
                        maps = _decode_eeprom_maps(blob)
                        if maps and maps.get('fuel_front'):
                            self._json(maps)
                            return
                    except Exception as e:
                        self._json({'error': str(e)}, 500)
                        return
            # Fallback a logica original (Live o mas reciente)
            maps = self.server_instance.eeprom_maps
            if not maps or not maps.get('fuel_front'):
                try:
                    sessions_dir = Path('/home/pi/buell/sessions')
                    bins = sorted(sessions_dir.glob('*/eeprom.bin'),
                                  key=lambda p: p.stat().st_mtime)
                    if bins:
                        blob = bins[-1].read_bytes()
                        maps = _decode_eeprom_maps(blob)
                except Exception as e:
                    maps = {'error': str(e)}
            self._json(maps)
            return
        if path == '/eeprom':
            params = self.server_instance.eeprom_params
            if not params:
                try:
                    sessions_dir = Path('/home/pi/buell/sessions')
                    bins = sorted(sessions_dir.glob('*/eeprom.bin'), key=lambda p: p.stat().st_mtime)
                    if bins:
                        blob = bins[-1].read_bytes()
                        meta_path = bins[-1].parent / 'session_metadata.json'
                        ver_str = None
                        if meta_path.exists():
                            try:
                                with open(meta_path) as mf:
                                    ver_str = json.load(mf).get('version_string')
                            except Exception:
                                pass
                        if not ver_str:
                            ver_str = 'desconocida'
                        params = _decode_eeprom_params(blob, ver_str)
                        if not params:
                            params = {'error': f'Fallo decode_params (version: {ver_str})'}
                except Exception as e:
                    params = {'error': str(e)}
            self._json(params)
            return
        if path == '/wifi/saved':
            self._json({"saved": net.saved_wifi()})
            return

        # FIX: scan es GET, no POST
        if path == '/wifi/scan':
            self._json({"networks": net.scan_wifi()})
            return

        if path == '/wifi/status':
            self._json({
                "mode":          net.current_mode(),
                "ip":            net.get_ip(),
                "switch_status": net.get_switch_status(),
                "state":         net.load_state(),
            })
            return

        # Redirect URL antes de ejecutar switch
        if path.startswith('/wifi/redirect_url'):
            action = self.path.split('action=')[-1] if 'action=' in self.path else ''
            url    = net.get_redirect_url(action)
            self._json({"url": url, "action": action})
            return

        if path == '/gps_fix':
            try:
                gps = self.server_instance.gps
                fix = gps.get_fix() if gps else None
                self._json(fix.as_dict() if fix else {"error": "no gps"})
            except Exception as e:
                self._json({"error": str(e)})
            return
        if path == '/gps_track':
            try:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                session_id = params.get('session', [''])[0]
                ride_num   = int(params.get('ride', [0])[0])
                import csv as _csv
                sessions_dir = Path('/home/pi/buell/sessions')
                # Buscar el archivo CSV del ride
                ride_files = sorted(sessions_dir.glob(f'{session_id}/ride_{session_id}_{ride_num:03d}*.csv'))
                if not ride_files:
                    self._json({'error': 'ride not found', 'points': []}); return
                points = []
                for rf in ride_files:
                    with open(rf, newline='') as f:
                        # Skip comment lines starting with #
                        filtered = (row for row in f if not row.startswith('#'))
                        reader = _csv.DictReader(filtered)
                        for row in reader:
                            try:
                                lat  = float(row.get('gps_lat') or 0)
                                lon  = float(row.get('gps_lon') or 0)
                                valid = row.get('gps_valid', 'False') == 'True'
                                if lat != 0.0 and lon != 0.0:
                                    points.append({
                                        'lat': lat,
                                        'lon': lon,
                                        'spd': float(row.get('gps_speed_kmh') or 0),
                                        'alt': float(row.get('gps_alt_m') or 0),
                                        't':   float(row.get('time_elapsed_s') or 0),
                                    })
                            except (ValueError, TypeError):
                                continue
                self._json({'ok': True, 'points': points, 'count': len(points)})
            except Exception as e:
                self._json({'error': str(e), 'points': []}, 500)
            return
        if path == '/ride_note':
            try:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                session_id = params.get('session', [''])[0]
                ride_num = int(params.get('ride', [0])[0])
                note_path = self.server_instance.buell_dir / 'sessions' / session_id / f'ride_{session_id}_{ride_num:03d}_notes.txt'
                note = note_path.read_text(encoding='utf-8') if note_path.exists() else ''
                self._json({"ok": True, "note": note})
            except Exception as e:
                self._json({"ok": False, "note": "", "error": str(e)})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        path   = self.path
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length) if length else b'{}'
        net    = self.server_instance.network

        try:
            payload = json.loads(body)
        except Exception as e:
            import logging
            logging.warning(f"Invalid JSON: {e} — body={body[:80]!r}")
            payload = {}

        if path == '/network':
            action = payload.get('action', '')
            if action == 'wifi':
                net.switch_to_wifi()
            elif action == 'hotspot':
                net.switch_to_hotspot()
            self._json({"ok": True, "action": action})
            return

        if path == '/wifi/connect':
            profile = payload.get('profile', '')
            if profile:
                net.connect_to_profile(profile)
            self._json({"ok": True})
            return

        if path == '/wifi/add':
            ssid     = payload.get('ssid', '')
            password = payload.get('password', '')
            if ssid and password:
                net.add_and_connect(ssid, password)
            self._json({"ok": True})
            return

        if path == '/wifi/forget':
            name = payload.get('name', '')
            ok   = net.forget_wifi(name) if name else False
            self._json({"ok": ok})
            return

        if path == '/shutdown':
            self.server_instance.pending_shutdown = True
            self._json({"ok": True, "msg": "Apagando..."})
            return

        if path == '/keepalive':
            now = time.time()
            if now - self.server_instance.last_keepalive >= 10:
                self.server_instance.last_keepalive = now
            self._json({"ok": True})
            return

        if path == '/git_pull':
            import subprocess
            result = subprocess.run(
                ['git', 'pull'],
                capture_output=True, text=True,
                cwd='/home/pi/buell'
            )
            output = result.stdout.strip() + result.stderr.strip()
            ok = result.returncode == 0
            if ok:
                subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
            self._json({"ok": ok, "output": output})
            return
        if path == '/ride_note':
            try:
                session_id = payload.get('session', '')
                ride_num = int(payload.get('ride_num', 0))
                note = payload.get('note', '').strip()
                note_path = self.server_instance.buell_dir / 'sessions' / session_id / f'ride_{session_id}_{ride_num:03d}_notes.txt'
                note_path.write_text(note, encoding='utf-8')
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
            return
        if path == '/close_ride':
            session = getattr(self.server_instance, 'session', None)
            if session and session.current_csv_fh:
                checksum = session.current_checksum
                ride_num = session.current_ride_num
                session.close_current_ride(reason="dashboard_request")
                self._json({"ok": True, "msg": "Ride cerrado", "session": checksum, "ride_num": ride_num})
            else:
                self._json({"ok": False, "msg": "Sin ride activo"})
            return
        if path == '/restart_logger':
            import subprocess
            subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
            self._json({"ok": True, "msg": "Reiniciando logger..."})
            return
        if path == '/reboot_pi':
            import subprocess
            subprocess.Popen(['sudo', '/usr/sbin/reboot'])
            self._json({"ok": True, "msg": "Reiniciando Pi..."})
            return
        self._json({"error": "unknown endpoint"}, 404)

    def _load_html(self):
        template = Path(__file__).parent / 'templates' / 'index.html'
        if template.exists():
            return template.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version())
        return "<h1>Buell Logger</h1><p>templates/index.html no encontrado</p>"


    def _get_live_data(self):
        live = dict(self.server_instance.ecu_live or {})
        try:
            gps = getattr(self.server_instance, 'gps', None)
            if gps:
                fix = gps.get_fix().as_dict()
                for k, v in fix.items():
                    if v is not None or k not in live:
                        live[k] = v
        except Exception:
            pass
        return live

    def _get_live(self):
        net = self.server_instance.network
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
            "ecu_connected":   self.server_instance.ecu_connected,
            "ecu_lost_s":      self.server_instance.ecu_lost_s,
            "live":            self._get_live_data(),
            "cells":           self.server_instance.cell_tracker.snapshot()[0] if self.server_instance.cell_tracker else {},
            "objectives":      [],
            "serial_stats":    self.server_instance.serial_stats,
            "bike_serial":     self.server_instance.bike_serial,
            "ecu_identity":    self.server_instance.ecu_identity,
        }


class WebServer:

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
        self.serial_stats     = {'bps': 0, 'pct': 0.0, 'tx': 0, 'rx': 0, 'buf_in': 0, 'buf_pct': 0.0, 'cpu_pct': 0.0, 'cpu_temp': 0.0, 'mem_pct': 0.0}
        self.bike_serial      = None
        self.ecu_identity     = {}   # {name, dbfile, ddfi, remark}
        self.cell_tracker     = None

    def _get_rides(self):
        rides = []
        sessions_path = self.buell_dir / 'sessions'
        if not sessions_path.exists():
            return rides
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
                    })
                except Exception:
                    pass
            for rf in sorted(session_dir.glob('ride_[0-9]*.csv')):
                try:
                    rnum = int(rf.stem.split('_')[-1])
                    if rnum in summary_nums:
                        continue
                    opened_utc = ''
                    n = 0
                    with open(rf) as f:
                        header = None
                        for line in f:
                            if line.startswith('#'): continue
                            if header is None: header = line.strip().split(','); continue
                            n += 1
                            if opened_utc: continue
                            try:
                                idx = header.index('timestamp_iso')
                                opened_utc = line.strip().split(',')[idx]
                            except Exception:
                                pass
                    rides.append({
                        'session': session_dir.name, 'firmware': fw,
                        'filename': rf.name, 'ride_num': rnum,
                        'samples': n, 'duration_s': 0, 'parts': 1,
                        'opened_utc': opened_utc,
                    })
                except Exception:
                    pass
        return sorted(rides, key=lambda r: (r['session'], r.get('ride_num', 0)))

    def start(self):
        DashboardHandler.server_instance = self
        self._server = ThreadingHTTPServer((self.host, self.port), DashboardHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="web-server"
        )
        self._thread.start()
        import logging
        logging.getLogger("WebServer").info(f"HTTP en http://{self.host}:{self.port}")

    def stop(self):
        if self._server:
            self._server.shutdown()

# ── Sessions VS comparison engine ─────────────────────────────────────────
def _compare_sessions(buell_dir, sa, sb):
    import csv as _csv
    from collections import defaultdict

    RPM_BINS = [800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
    TPS_BINS = [0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]

    def bucket(val, bins):
        for i in range(len(bins)-1):
            if bins[i] <= val < bins[i+1]: return i
        return len(bins)-2

    def sf(v, d=0.0):
        try: return float(v) if v and str(v).strip() else d
        except: return d

    def load_meta(sid):
        import json as _json
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        meta = {}
        if mp.exists():
            with open(mp) as f: meta = _json.load(f)
        # leer serial del eeprom.bin para identificar moto
        ep = buell_dir / 'sessions' / sid / 'eeprom.bin'
        if ep.exists():
            try:
                b = ep.read_bytes()
                if len(b) >= 14:
                    meta['bike_serial'] = int.from_bytes(b[12:14], 'little')
            except: pass
        return meta

    def load_csv(sid):
        rows = []
        sdir = buell_dir / 'sessions' / sid
        csv_files = sorted(sdir.glob('ride_*.csv'))
        for cp in csv_files:
            with open(cp) as f:
                lines = [l for l in f if not l.startswith('#')]
            if not lines: continue
            for r in _csv.DictReader(lines):
                try:
                    rpm = sf(r['RPM'])
                    if rpm < 100: continue
                    rows.append({
                        't':    sf(r['time_elapsed_s']),
                        'rpm':  rpm,
                        'tps':  sf(r.get('TPS_pct') or r.get('TPD', 0)),
                        'clt':  sf(r['CLT']),
                        'pw1':  sf(r['pw1']),
                        'pw2':  sf(r.get('pw2', 0)),
                        'spark1':sf(r['spark1']),
                        'spark2':sf(r.get('spark2', sf(r['spark1']))),
                        'afv':  sf(r.get('AFV', 100)),
                        'wue':  sf(r.get('WUE', 100)),
                        'ae':   sf(r.get('Accel_Corr', 100)),
                        'gear': sf(r.get('Gear', 0)),
                        'spd':  sf(r.get('VS_KPH', 0)),
                        'alt':  sf(r.get('gps_alt_m'), None) if r.get('gps_valid','').strip()=='TRUE' else None,
                        'fl_wot':  r.get('fl_wot','0').strip() in ('1','True','true'),
                        'fl_decel':r.get('fl_decel','0').strip() in ('1','True','true'),
                        'fl_fc':   r.get('fl_fuel_cut','0').strip() in ('1','True','true'),
                        'fl_eng':  r.get('fl_engine_run','1').strip() in ('1','True','true'),
                    })
                except: continue
        return rows

    def derivatives(rows):
        for i in range(1, len(rows)):
            dt = rows[i]['t'] - rows[i-1]['t']
            if 0 < dt < 2.0:
                rows[i]['drpm'] = (rows[i]['rpm'] - rows[i-1]['rpm']) / dt
                rows[i]['dtps'] = (rows[i]['tps'] - rows[i-1]['tps']) / dt
                rows[i]['dvss'] = (rows[i]['spd'] - rows[i-1]['spd']) / dt
                a0, a1 = rows[i-1]['alt'], rows[i]['alt']
                rows[i]['dalt'] = (a1-a0)/dt if a0 is not None and a1 is not None else None
            else:
                rows[i]['drpm'] = rows[i]['dtps'] = rows[i]['dvss'] = 0.0
                rows[i]['dalt'] = None
        if rows: rows[0]['drpm'] = rows[0]['dtps'] = rows[0]['dvss'] = 0.0; rows[0]['dalt'] = None

    def classify(r):
        if not r['fl_eng'] or r['fl_fc']: return 'BITTER'
        if r['clt'] < 170: return 'BITTER'
        if r['wue'] > 102: return 'BITTER'
        if r['ae'] > 105:  return 'BITTER'
        drpm = abs(r.get('drpm', 0))
        dtps = r.get('dtps', 0)
        dalt = r.get('dalt')
        if r['fl_wot'] or r['tps'] >= 80:
            if dtps > 15:  return 'SPICY_TIPIN'
            if dtps < -15: return 'SPICY_TIPOUT'
            return 'SPICY_WOT'
        if dtps > 15:  return 'SPICY_TIPIN'
        if dtps < -15: return 'SPICY_TIPOUT'
        if drpm > 150 or abs(dtps) > 3: return 'BITTER'
        if dalt is None: return 'SWEET'
        if dalt > 0.8:   return 'SALTY_UP'
        if dalt < -0.8:  return 'SALTY_DOWN'
        return 'SWEET'

    def build_index(rows):
        idx = defaultdict(lambda: {'n':0,'pw1':0,'pw2':0,'spark1':0,'spark2':0,'clt':0,'afv':0,'drpm':0,'spd':0,'dvss':0,'pw_eff':0})
        fc  = defaultdict(int)
        for r in rows:
            fl = classify(r)
            fc[fl] += 1
            if fl == 'BITTER': continue
            rb = bucket(r['rpm'], RPM_BINS)
            tb = bucket(r['tps'], TPS_BINS)
            k  = (fl, rb, tb)
            c  = idx[k]
            c['n']    += 1
            c['pw1']  += r['pw1']
            c['pw2']  += r['pw2']
            c['spark1']+= r['spark1']
            c['spark2']+= r['spark2']
            c['clt']  += r['clt']
            c['afv']  += r['afv']
            c['drpm'] += abs(r.get('drpm',0))
            c['spd']  += r['spd']
            c['dvss'] += r.get('dvss', 0)
            c['pw_eff'] += ((r['pw1']+r['pw2'])/2) * r['afv'] / 100.0
        result = {}
        for k,c in idx.items():
            n = c['n']
            result[k] = {
                'flavor': k[0],
                'rpm_lo': RPM_BINS[k[1]], 'rpm_hi': RPM_BINS[k[1]+1],
                'tps_lo': TPS_BINS[k[2]], 'tps_hi': TPS_BINS[k[2]+1],
                'n': n,
                'pw1':   round(c['pw1']/n, 3),
                'pw2':   round(c['pw2']/n, 3),
                'spark1':round(c['spark1']/n, 2),
                'spark2':round(c['spark2']/n, 2),
                'clt':   round(c['clt']/n, 1),
                'afv':   round(c['afv']/n, 1),
                'drpm':  round(c['drpm']/n, 1),
                'spd':   round(c['spd']/n, 1),
                'dvss':  round(c['dvss']/n, 3),
                'pw_eff':round(c['pw_eff']/n, 3),
            }
        return result, dict(fc)

    # Cargar ambas sesiones
    ma, mb = load_meta(sa), load_meta(sb)
    ra, rb = load_csv(sa), load_csv(sb)
    derivatives(ra); derivatives(rb)
    ia, fca = build_index(ra)
    ib, fcb = build_index(rb)

    # Comparar celdas comunes por flavor
    MIN_N = 5
    delta = []
    keys_a = {k for k,v in ia.items() if v['n'] >= MIN_N}
    keys_b = {k for k,v in ib.items() if v['n'] >= MIN_N}
    common = keys_a & keys_b
    for k in common:
        a, b = ia[k], ib[k]
        delta.append({
            'flavor':   a['flavor'],
            'rpm':      f"{a['rpm_lo']}-{a['rpm_hi']}",
            'tps':      f"{a['tps_lo']}-{a['tps_hi']}",
            'rpm_lo':   a['rpm_lo'],
            'tps_lo':   a['tps_lo'],
            'na':       a['n'],
            'nb':       b['n'],
            'pw1_a':    a['pw1'],   'pw1_b':    b['pw1'],   'dpw1':   round(b['pw1']-a['pw1'],3),
            'pw2_a':    a['pw2'],   'pw2_b':    b['pw2'],   'dpw2':   round(b['pw2']-a['pw2'],3),
            'spk1_a':   a['spark1'],'spk1_b':   b['spark1'],'dspk1':  round(b['spark1']-a['spark1'],2),
            'spk2_a':   a['spark2'],'spk2_b':   b['spark2'],'dspk2':  round(b['spark2']-a['spark2'],2),
            'clt_a':    a['clt'],
            'clt_b':    b['clt'],
            'dclt':     round(b['clt'] - a['clt'], 1),
            'afv_a':    a['afv'],
            'afv_b':    b['afv'],
            'dvss_a':   a['dvss'],
            'dvss_b':   b['dvss'],
            'ddvss':    round(b['dvss'] - a['dvss'], 3),
            'spd_a':    a['spd'],
            'spd_b':    b['spd'],
            'dspd':     round(b['spd'] - a['spd'], 1),
            'pw_eff_a': a['pw_eff'],
            'pw_eff_b': b['pw_eff'],
            'dpw_eff':  round(b['pw_eff'] - a['pw_eff'], 3),
        })
    delta.sort(key=lambda x: (x['flavor'], -(x['na']+x['nb'])))

    return {
        'sa': {'id': sa, 'checksum': ma.get('checksum','?'), 'version': ma.get('version_string','?'),
               'created': ma.get('created_utc','')[:10], 'rides': ma.get('total_rides',0),
               'samples': len(ra), 'flavors': fca},
        'sb': {'id': sb, 'checksum': mb.get('checksum','?'), 'version': mb.get('version_string','?'),
               'created': mb.get('created_utc','')[:10], 'rides': mb.get('total_rides',0),
               'samples': len(rb), 'flavors': fcb},
        'same_bike': ma.get('bike_serial') is not None and ma.get('bike_serial') == mb.get('bike_serial'),
        'bike_serial_a': ma.get('bike_serial'),
        'bike_serial_b': mb.get('bike_serial'),
        'common': len(common),
        'delta': delta,
    }

