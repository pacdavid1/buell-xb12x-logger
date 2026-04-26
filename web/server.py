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
            if match:
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
                        with open(csv_path, 'rb') as f:
                            if not first: f.readline()
                            chunks.append(f.read())
                        first = False
                    raw = b''.join(chunks)
                    accept_enc = self.headers.get('Accept-Encoding', '')
                    use_gzip = 'gzip' in accept_enc
                    import zlib as _zlib
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
            else:
                self._json({'error': 'not found'}, 404)
            return
        if path.startswith('/ride/'):
            fname = path.split('/ride/')[-1].split('?')[0]
            rides = self.server_instance._get_rides()
            fname_summary = fname.replace('.csv', '_summary.json')
            match = next((r for r in rides if r['filename']==fname or r['filename']==fname_summary), None)
            if match:
                sdir = self.server_instance.buell_dir / 'sessions' / match['session']
                fpath = sdir / fname
                if not fpath.exists():
                    fpath = sdir / fname.replace('_summary.json', '.csv')
                try:
                    if fpath.suffix == '.json':
                        with open(fpath) as f:
                            s = json.load(f)
                        self._json({'cells': s.get('cells', {}), 'objectives': s.get('objectives', [])})
                    else:
                        self._json({'cells': {}, 'objectives': []})
                except Exception as e:
                    self._json({'error': str(e)}, 500)
            else:
                self._json({'error': 'not found'}, 404)
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
            from pathlib import Path
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
            maps = self.server_instance.eeprom_maps
            if not maps or not maps.get('fuel_front'):
                # No live maps — try most recent eeprom.bin from disk
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
            self._json(self.server_instance.eeprom_params)
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
                from pathlib import Path
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
            "live":            self.server_instance.ecu_live,
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
        self.serial_stats     = {'bps': 0, 'pct': 0.0, 'tx': 0, 'rx': 0}
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
