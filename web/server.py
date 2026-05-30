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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys as _sys
_sys.path.insert(0, '/home/pi/buell')
from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.eeprom_params import decode_params as _decode_eeprom_params
import datetime


def _get_version():
    try:
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        # Skip HTML comment block before searching for version
        end_comment = cl.find('-->')
        if end_comment != -1:
            cl = cl[end_comment:]
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
            '/sessions_launch': self._handle_sessions_launch,
            '/sessions_launch/data': self._handle_sessions_launch_data,
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
        }
        handler = _routes.get(path)
        if handler:
            handler(path, payload)
            return

        self._json({"error": "unknown endpoint"}, 404)

    def _handle_static(self, path=None):
        path = self.path.lstrip("/")
        base = os.path.realpath(os.path.dirname(__file__))
        fpath = os.path.realpath(os.path.join(base, path))
        if os.path.commonpath([base, fpath]) == base and os.path.isfile(fpath):
            mime, _ = mimetypes.guess_type(fpath)
            with open(fpath, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            return
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

    def _handle_sessions_vs_download(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get("a", [""])[0]
        sb = params.get("b", [""])[0]
        if not sa or not sb:
            self._json({"error": "Faltan sesiones"}, 400); return
        try:
            data = _compare_sessions_cached(self.server_instance.buell_dir, sa, sb)
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f"attachment; filename=sessions_vs_{sa}_{sb}.json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json({"error": str(e)}, 500)
        return

    def _handle_tuner_sessions(self, path=None):
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
                    except Exception: pass
                else:
                    continue
                sessions.append({'id': d.parent.name, 'version': meta.get('version_string', '?'), 'rides': meta.get('total_rides', 0), 'samples': meta.get('total_samples', 0), 'created': meta.get('created_utc', '')[:10], 'serial': serial})
            except Exception: pass
        sessions.sort(key=lambda s: s['created'], reverse=True)
        self._json({'sessions': sessions})
        return

    def _handle_tuner_maps(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sess = params.get('session', [''])[0]
        if not sess: self._json({'error': 'Falta session'}, 400); return
        blob_path = self.server_instance.buell_dir / 'sessions' / sess / 'eeprom.bin'
        if not blob_path.exists(): self._json({'error': 'No hay eeprom.bin'}, 404); return
        try:
            self._json(_decode_eeprom_maps(blob_path.read_bytes()))
        except Exception as e:
            self._json({'error': f'Error al leer mapa: {e}'})
        return

    def _handle_tuner_merge(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get('a', [''])[0]
        sb = params.get('b', [''])[0]
        mode = params.get('mode', ['BALANCE'])[0]
        if not sa or not sb:
            self._json({'error': 'Faltan sesiones'}, 400); return
        try:
            self._json(_merge_maps(self.server_instance.buell_dir, sa, sb, mode))
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return


    def _handle_sessions_launch(self, path=None):
        """Serve the Launch Analysis page."""
        try:
            f = Path(__file__).parent / 'templates' / 'sessions_launch.html'
            self._html(f.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_sessions_launch_data(self, path=None):
        """Return cluster comparison data for Launch Analysis."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        a = params.get('a', [''])[0]
        b = params.get('b', [''])[0]
        if not a or not b:
            self._json({'error': 'Faltan sesiones'}, 400); return
        try:
            data = _compare_sessions_cached(self.server_instance.buell_dir, a, b)
            result = {}
            if 'clusters_a' in data:
                result['clusters_a'] = data['clusters_a']
            if 'clusters_b' in data:
                result['clusters_b'] = data['clusters_b']
            if 'cluster_matches' in data:
                result['cluster_matches'] = data['cluster_matches']
            if 'error' in data:
                result['error'] = data['error']
            self._json(result)
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_sessions_vs(self, path=None):
        try:
            f = Path(__file__).parent / 'templates' / 'sessions_vs.html'
            self._html(f.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_sessions_vs_compare(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get('a', [''])[0]
        sb = params.get('b', [''])[0]
        if not sa or not sb:
            self._json({'error': 'Faltan sesiones'}, 400); return
        try:
            self._json(_compare_sessions_cached(self.server_instance.buell_dir, sa, sb))
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_tuner(self, path=None):
        try:
            tuner_file = Path(__file__).parent / 'templates' / 'tuner.html'
            if tuner_file.exists():
                self._html(tuner_file.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
            else:
                self._html("<h1>Buell Tuner - Página no encontrada</h1>")
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_index(self, path=None):
        self._html(self._load_html())
        return

    def _handle_live_json(self, path=None):
        self._json(self._get_live())
        return

    def _handle_ride_launch_event(self, path=None):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            evt = json.loads(body)
            session_dir = self.server_instance.session.current_session_dir if self.server_instance.session else None
            if session_dir and isinstance(evt, dict):
                evt['captured_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
                log_path = session_dir / 'launch_events.jsonl'
                with open(log_path, 'a') as f:
                    f.write(json.dumps(evt) + '\n')
            self._json({'ok': True})
        except Exception as e:
            logging.getLogger("WebServer").warning("launch_event save failed: %s" % e)
            self._json({'ok': False, 'error': str(e)})

    def _handle_coverage_json(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        fmt = params.get("format", [None])[0]
        report = self.server_instance._get_coverage()
        if fmt == "csv":
            cells = report.get("cells", {})
            flavors = list(report.get("summary", {}).keys())
            buf = io.StringIO()
            w = csv.writer(buf)
            header = ["cell", "seconds", "ego_avg", "confidence"]
            for f in flavors:
                header += [f + "_s", f + "_pct", f + "_done"]
            w.writerow(header)
            for key, cell in sorted(cells.items()):
                row = [key, cell.get("seconds", 0), cell.get("ego_avg", 100),
                       cell.get("confidence", 0)]
                for f in flavors:
                    fd = cell.get("flavors", {}).get(f, {})
                    row += [fd.get("seconds", 0), fd.get("pct", 0),
                            1 if fd.get("done") else 0]
                w.writerow(row)
            csv_out = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=coverage.csv")
            self.end_headers()
            self.wfile.write(csv_out.encode("utf-8"))
            return
        self._json(report)
        return

    def _handle_coverage_targets(self, path=None):
        try:
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if not isinstance(body, dict):
                self._json({'error': 'Expected JSON object'}, 400)
                return
            self.server_instance._set_coverage_targets(body)
            self._json({'ok': True})
        except Exception as e:
            self._json({'error': str(e)}, 400)
        return

    def _handle_csv(self, path=None):
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
            accept_enc = self.headers.get('Accept-Encoding', '')
            use_gzip = 'gzip' in accept_enc
            body = zlib.compress(raw, level=6, wbits=31) if use_gzip else raw
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

    def _handle_ride(self, path=None):
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

    def _handle_errorlog_viz(self, path=None):
        try:
            f = Path(__file__).parent / 'templates' / 'errorlog_viz.html'
            self._html(f.read_text(encoding='utf-8').replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)
        return

    def _handle_errorlog(self, path=None):
        parts = path.split('/errorlog/')[-1].split('?')[0].strip('/').split('/')
        if len(parts) >= 2:
            session = parts[0]
            fname = parts[1]
        else:
            fname = parts[0] if parts else ''
            session = None
        rides = self.server_instance._get_rides()
        ride_num = int(fname.replace('_errorlog.json','').replace('ride_','').replace('.csv','')) if fname else 0
        match = None
        if session:
            match = next((r for r in rides if r.get('ride_num')==ride_num and r.get('session')==session), None)
        if not match:
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

    def _handle_rides(self, path=None):
        rides = self.server_instance._get_rides()
        self._json({"rides": rides})
        return

    def _handle_suggested_msq(self, path=None):
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

    def _handle_eeprom_download(self, path=None):
        """Serve raw eeprom.bin for a given session (or active session if none specified)."""
        import urllib.parse, re
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'}); return
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({'error': 'no session specified and no active session'}); return
        bin_path = self.server_instance.buell_dir / 'sessions' / session / 'eeprom.bin'
        try:
            data = bin_path.read_bytes()
        except (OSError, IOError) as e:
            self._json({'error': 'could not read eeprom.bin: ' + str(e)}); return
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition',
            'attachment; filename="eeprom_' + session + '.bin"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_msq_download(self, path=None):
        """Serve suggested MSQ for a given session (or active session if none specified)."""
        import urllib.parse, re
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'}); return
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({'error': 'no session specified and no active session'}); return
        msq_path = (self.server_instance.buell_dir / 'sessions' / session /
                    ('suggested_' + session + '.msq'))
        try:
            data = msq_path.read_bytes()
        except (OSError, IOError) as e:
            self._json({'error': 'could not read msq file: ' + str(e)}); return
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Disposition',
            'attachment; filename="suggested_' + session + '.msq"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_maps(self, path=None):
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

    def _handle_eeprom(self, path=None):
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

    def _handle_wifi_saved(self, path=None):
        self._json({"saved": net.saved_wifi()})
        return

    def _handle_wifi_scan(self, path=None):
        self._json({"networks": net.scan_wifi()})
        return

    def _handle_wifi_status(self, path=None):
        self._json({
            "mode":          net.current_mode(),
            "ip":            net.get_ip(),
            "switch_status": net.get_switch_status(),
            "state":         net.load_state(),
        })
        return

    def _handle_wifi_redirect_url(self, path=None):
        action = self.path.split('action=')[-1] if 'action=' in self.path else ''
        url    = net.get_redirect_url(action)
        self._json({"url": url, "action": action})
        return

    def _handle_gps_fix(self, path=None):
        try:
            gps = self.server_instance.gps
            fix = gps.get_fix() if gps else None
            self._json(fix.as_dict() if fix else {"error": "no gps"})
        except Exception as e:
            self._json({"error": str(e)})
        return

    def _handle_gps_track(self, path=None):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            session_id = params.get('session', [''])[0]
            ride_num   = int(params.get('ride', [0])[0])
            sessions_dir = Path(self.server_instance.buell_dir) / 'sessions'
            # Buscar el archivo CSV del ride
            ride_files = sorted(sessions_dir.glob(f'{session_id}/ride_{session_id}_{ride_num:03d}*.csv'))
            if not ride_files:
                self._json({'error': 'ride not found', 'points': []}); return
            points = []
            for rf in ride_files:
                with open(rf, newline='') as f:
                    # Skip comment lines starting with #
                    filtered = (row for row in f if not row.startswith('#'))
                    reader = csv.DictReader(filtered)
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

    def _handle_ride_note(self, path=None):
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

    def _handle_post_network(self, path, payload):
        net    = self.server_instance.network
        action = payload.get('action', '')
        if action == 'wifi':
            net.switch_to_wifi()
        elif action == 'hotspot':
            net.switch_to_hotspot()
        self._json({"ok": True, "action": action})
        return

    def _handle_post_wifi_connect(self, path, payload):
        profile = payload.get('profile', '')
        if profile:
            net.connect_to_profile(profile)
        self._json({"ok": True})
        return

    def _handle_post_wifi_add(self, path, payload):
        ssid     = payload.get('ssid', '')
        password = payload.get('password', '')
        if ssid and password:
            net.add_and_connect(ssid, password)
        self._json({"ok": True})
        return

    def _handle_post_wifi_forget(self, path, payload):
        name = payload.get('name', '')
        ok   = net.forget_wifi(name) if name else False
        self._json({"ok": ok})
        return

    def _handle_post_shutdown(self, path, payload):
        self.server_instance.pending_shutdown = True
        self._json({"ok": True, "msg": "Apagando..."})
        return

    def _handle_post_keepalive(self, path, payload):
        now = time.time()
        if now - self.server_instance.last_keepalive >= 10:
            self.server_instance.last_keepalive = now
        self._json({"ok": True})
        return

    def _handle_post_git_pull(self, path, payload):
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

    def _handle_post_ride_note(self, path, payload):
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

    def _handle_post_close_ride(self, path, payload):
        session = getattr(self.server_instance, 'session', None)
        if session and session.current_csv_fh:
            checksum = session.current_checksum
            ride_num = session.current_ride_num
            session.close_current_ride(reason="dashboard_request")
            self._json({"ok": True, "msg": "Ride cerrado", "session": checksum, "ride_num": ride_num})
        else:
            self._json({"ok": False, "msg": "Sin ride activo"})
        return

    def _handle_post_restart_logger(self, path, payload):
        import subprocess
        subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
        self._json({"ok": True, "msg": "Reiniciando logger..."})
        return

    def _handle_post_reboot_pi(self, path, payload):
        import subprocess
        subprocess.Popen(['sudo', '/usr/sbin/reboot'])
        self._json({"ok": True, "msg": "Reiniciando Pi..."})
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
            "active_cell":    self.server_instance.cell_tracker.snapshot()[1] if self.server_instance.cell_tracker else None,
            "objectives":      [],
            "serial_stats":    self.server_instance.serial_stats,
            "bike_serial":     self.server_instance.bike_serial,
            "ecu_identity":    self.server_instance.ecu_identity,
        }


    def _handle_tuning_report(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        fmt = params.get("format", [None])[0]
        session = params.get("session", [None])[0]
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({"error": "no session specified and no active session"})
            return
        report_path = self.server_instance.buell_dir / "sessions" / session / f"tuning_report_{session}.json"
        if not report_path.exists():
            self._json({"error": "no tuning report for this session"})
            return
        report = json.loads(report_path.read_text())
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["rpm", "load", "seconds", "count", "ego_sum", "clt_sum",
                        "wue_sum", "afv_sum", "valid_seconds", "valid_ego_sum",
                        "valid_count", "inv_reasons"])
            for key, cell in sorted(report.get("agg_cells", {}).items()):
                parts = key.split("_")
                rpm = parts[0] if len(parts) == 2 else key
                load = parts[1] if len(parts) == 2 else ""
                inv_str = "; ".join(f"{k}:{v}" for k, v in cell.get("inv_reasons", {}).items())
                w.writerow([rpm, load, cell.get("seconds", 0), cell.get("count", 0),
                           cell.get("ego_sum", 0), cell.get("clt_sum", 0),
                           cell.get("wue_sum", 0), cell.get("afv_sum", 0),
                           cell.get("valid_seconds", 0), cell.get("valid_ego_sum", 0),
                           cell.get("valid_count", 0), inv_str])
            csv_out = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition",
                             f"attachment; filename=tuning_report_{session}.csv")
            self.end_headers()
            self.wfile.write(csv_out.encode("utf-8"))
            return
        self._json(report)
        return


class WebServer:

    # Targets de coverage por flavor (segundos validos requeridos)
    COVERAGE_TARGETS_DEFAULT = {
        "SWEET":  30.0,
        "TIPIN":  15.0,
        "TIPOUT": 15.0,
        "WOT":    10.0,
        "BITTER":  0.0,
    }

    def _set_coverage_targets(self, body):
        flavors = {"SWEET", "TIPIN", "TIPOUT", "WOT", "BITTER"}
        for k, v in body.items():
            if k in flavors:
                self._coverage_targets[k] = float(v)

    def _get_coverage(self):
        """Cobertura unificada: segundos, EGO, flavors por celda."""
        if not self.cell_tracker:
            return {"error": "tracker no disponible", "cells": {}, "summary": {}}
        snap, active = self.cell_tracker.snapshot()
        targets = self._coverage_targets
        flavors = [f for f in ("SWEET", "TIPIN", "TIPOUT", "WOT") if targets.get(f, 0) > 0]
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
        self.serial_stats     = {'bps': 0, 'pct': 0.0, 'tx': 0, 'rx': 0, 'buf_in': 0, 'buf_pct': 0.0, 'cpu_pct': 0.0, 'cpu_temp': 0.0, 'mem_pct': 0.0}
        self.bike_serial      = None
        self.ecu_identity     = {}   # {name, dbfile, ddfi, remark}
        self.cell_tracker     = None
        self._coverage_targets = dict(self.COVERAGE_TARGETS_DEFAULT)
        self._data_lock = threading.RLock()

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
        logging.getLogger("WebServer").info(f"HTTP en http://{self.host}:{self.port}")

    def stop(self):
        if self._server:
            self._server.shutdown()

# ── Sessions VS comparison engine ─────────────────────────────────────────
def _maps_differ(a,b):
    if len(a)!=len(b) or (a and len(a[0])!=len(b[0])): return True
    for i in range(len(a)):
        for j in range(len(a[0])):
            if abs(a[i][j]-b[i][j])>0.5: return True
    return False

def _merge_maps(buell_dir, sa, sb, mode='BALANCE'):
    RB=[800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
    TB=[0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]
    MN=10
    def bk(v,bs):
        for i in range(len(bs)-1):
            if bs[i]<=v<bs[i+1]: return i
        return len(bs)-2
    ep_a=buell_dir/'sessions'/sa/'eeprom.bin'
    ep_b=buell_dir/'sessions'/sb/'eeprom.bin'
    if not ep_a.exists() or not ep_b.exists():
        return {'error':'eeprom no encontrada','attributable':False}
    mA=_decode_eeprom_maps(ep_a.read_bytes())
    mB=_decode_eeprom_maps(ep_b.read_bytes())
    FK=['fuel_front','fuel_rear']
    SK=['spark_front','spark_rear']
    fc=[k for k in FK if k in mA and k in mB and _maps_differ(mA[k],mB[k])]
    sc=[k for k in SK if k in mA and k in mB and _maps_differ(mA[k],mB[k])]
    ac=fc+sc
    if not ac:
        return {'error':'Sin cambios entre sesiones','changed':[],'attributable':False}
    if fc and sc:
        attr=False
    else:
        attr=True
    try:
        vd=_compare_sessions_cached(buell_dir,sa,sb)
        delta=vd.get('delta',[])
    except Exception:
        delta=[]
    ci={}
    for r in delta:
        if r['na']<MN or r['nb']<MN: continue
        fl=r['flavor']
        if fl not in ('SWEET','SPICY_WOT'): continue
        key=(bk(r['rpm_lo'],RB),bk(r['tps_lo'],TB))
        if key not in ci: ci[key]={'eco':None,'sport':None}
        if fl=='SWEET': ci[key]['eco']='A' if r.get('dpw_eff',0)<0 else 'B'
        elif fl=='SPICY_WOT': ci[key]['sport']='A' if r['ddvss']<0 else 'B'
    def winner(key):
        info=ci.get(key)
        if not info: return None
        ew,sw=info['eco'],info['sport']
        if mode=='ECO': return ew
        if mode=='SPORT': return sw
        if ew and sw and ew!=sw: return 'AVG'
        return ew or sw
    def m2ck(i,j,ra,la):
        rv=ra[j];lv=la[i]
        if rv==0: return None
        rc=(rv+ra[j+1])/2 if j<len(ra)-1 else (rv+(rv-ra[j-1])/2 if j>0 else rv)
        lc=(lv+la[i+1])/2 if i<len(la)-1 else (lv+(lv-la[i-1])/2 if i>0 else lv)
        if rc<RB[0] or lc<TB[0]: return None
        return (bk(rc,RB),bk(lc,TB))
    result={}
    for ck in ac:
        if ck.startswith('fuel'): ra=mA['axes']['fuel_rpm'];la=mA['axes']['fuel_load']
        else: ra=mA['axes']['spark_rpm'];la=mA['axes']['spark_load']
        rows=len(la);cols=len(ra)
        merged=[];st={'A':0,'B':0,'AVG':0,'ORIG':0}
        for i in range(rows):
            row=[]
            for j in range(cols):
                ck_key=m2ck(i,j,ra,la)
                if ck_key is None:
                    row.append({'v':mA[ck][i][j],'s':'ORIG'});st['ORIG']+=1;continue
                w=winner(ck_key)
                if w is None or w=='AVG':
                    avg=round((mA[ck][i][j]+mB[ck][i][j])/2,1)
                    row.append({'v':avg,'s':'AVG'});st['AVG']+=1
                else:
                    row.append({'v':mA[ck][i][j] if w=='A' else mB[ck][i][j],'s':w});st[w]+=1
            merged.append(row)
        result[ck]={'merged':merged,'axes':{'rpm':ra,'load':la},'stats':st,'base':mA[ck],'mod':mB[ck]}
    return {
        'attributable':attr,'changed':ac,
        'unchanged':[k for k in FK+SK if k not in ac],
        'mode':mode,'cells_with_data':len(ci),'maps':result
    }

def _fmtk(n):
    if n >= 1000: return f"{n/1000:.1f}k"
    return str(n)
def _compare_sessions_cached(buell_dir, sa, sb):
    import json as _json
    def _meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        if mp.exists():
            with open(mp) as f: return json.load(f)
        return {}
    ma, mb = _meta(sa), _meta(sb)
    fname = f"sessions_vs_{sa}-{_fmtk(ma.get('total_samples',0))}_{sb}-{_fmtk(mb.get('total_samples',0))}.json"
    cache_dir = buell_dir / 'sessions' / '_cache'
    cache_file = cache_dir / fname
    if cache_file.exists():
        try:
            cached = json.load(open(cache_file))
            # Accept cached data even without clusters_a (legacy caches)
            if 'sa' in cached and 'sb' in cached and 'delta' in cached:
                return cached
        except Exception:
            pass
    result = _compare_sessions(buell_dir, sa, sb)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(result, f)
    return result


def detect_launches(rows, pre_window=3.0, post_window=5.0, min_dtps=15.0, min_rpm=1500):
    """Detect throttle tip-in events, classify as Type A (cruise) or Type B (moderate accel)."""
    if len(rows) < 30:
        return []
    launches = []
    def _s(v):
        n=len(v)
        if n<2: return 0.0
        m=sum(v)/n
        return (sum((x-m)**2 for x in v)/n)**0.5
    i = 1
    while i < len(rows):
        dtps = rows[i]['tps'] - rows[i-1]['tps']
        if dtps > min_dtps and rows[i]['rpm'] > min_rpm:
            t0 = rows[i]['t']
            pre = [r for r in rows if t0 - pre_window <= r['t'] <= t0 - 0.05]
            if len(pre) < 10:
                i += 1; continue
            tail = pre[-min(20, len(pre)):]
            rs = _s([r['rpm'] for r in tail])
            ts = _s([r['tps'] for r in tail])
            ss = _s([r['spd'] for r in tail])
            if ts < 5:
                lt = 'A'
            elif ts < 20 and rs < 500 and ss < 15:
                lt = 'B'
            else:
                i += 1; continue
            # Series: -pre to +post, sampled ~200ms
            t_start, t_end = t0 - pre_window, t0 + post_window
            series = []; last_t = -999
            for r in rows:
                if r['t'] < t_start: continue
                if r['t'] > t_end: break
                if r['t'] - last_t >= 0.18:
                    series.append({
                        'dt': round(r['t'] - t0, 2),
                        'rpm': round(r['rpm'], 0),
                        'tps': round(r['tps'], 1),
                        'spd': round(r['spd'], 1),
                        'pw1': round(r['pw1'], 3),
                        'pw2': round(r.get('pw2') or r['pw1'], 3),
                        'ae': round(r.get('ae', 100), 1),
                    })
                    last_t = r['t']
            post = [r for r in rows if t0 <= r['t'] <= t_end]
            launch = {
                'type': lt, 't': round(t0, 1),
                'gear': int(rows[i].get('gear', 0)),
                'dtps_raw': round(dtps, 1),
                'pre_rpm': round(sum(r['rpm'] for r in tail)/len(tail), 0),
                'pre_spd': round(sum(r['spd'] for r in tail)/len(tail), 1),
                'pre_tps': round(sum(r['tps'] for r in tail)/len(tail), 1),
                'pre_rpm_std': round(rs, 0),
                'pre_tps_std': round(ts, 1),
                'pre_spd_std': round(ss, 1),
                'series': series,
            }
            if post:
                launch['peak_rpm']  = round(max(r['rpm'] for r in post), 0)
                launch['peak_spd']  = round(max(r['spd'] for r in post), 1)
                launch['peak_pw']   = round(max((r['pw1']+(r.get('pw2') or r['pw1']))/2 for r in post), 3)
                launch['peak_ae']   = round(max(r.get('ae', 100) for r in post), 1)
                launch['rpm_gain']  = round(post[-1]['rpm'] - tail[-1]['rpm'], 0)
                launch['spd_gain']  = round(post[-1]['spd'] - tail[-1]['spd'], 1)
            launches.append(launch)
            # skip past post-window
            skip = t0 + post_window
            while i < len(rows) and rows[i]['t'] <= skip:
                i += 1
            continue
        i += 1
    return launches



def _s_std(vals):
    """Standard deviation"""
    n = len(vals)
    if n < 2: return 0.0
    m = sum(vals) / n
    return (sum((x - m) ** 2 for x in vals) / (n - 1)) ** 0.5

def cluster_launches(launches, rpm_tol=400, spd_tol=12, tps_tol=2.5):
    """
    Group similar launch events by initial conditions (RPM, speed, TPS, gear).
    Uses normalized Euclidean distance with adaptive centroid updates.
    Returns list of cluster dicts with statistical aggregations.
    """
    if not launches:
        return []

    clusters = []

    for l in launches:
        gear = l.get('gear')
        rpm = l.get('pre_rpm', 0)
        spd = l.get('pre_spd', 0)
        tps = l.get('pre_tps', 0)

        best_idx = -1
        best_dist = float('inf')

        for i, c in enumerate(clusters):
            if c['gear'] != gear:
                continue
            dr = abs(c['mean_rpm'] - rpm) / rpm_tol
            ds = abs(c['mean_spd'] - spd) / spd_tol
            dt = abs(c['mean_tps'] - tps) / max(tps_tol, 0.1)
            dist = dr + ds + dt
            if dist < 1.5 and dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx >= 0:
            c = clusters[best_idx]
            c['launches'].append(l)
            c['count'] += 1
            c['mean_rpm'] = sum(ll.get('pre_rpm',0) for ll in c['launches']) / c['count']
            c['mean_spd'] = sum(ll.get('pre_spd',0) for ll in c['launches']) / c['count']
            c['mean_tps'] = sum(ll.get('pre_tps',0) for ll in c['launches']) / c['count']
        else:
            newc = {
                'id': len(clusters), 'gear': gear, 'count': 1,
                'mean_rpm': rpm, 'mean_spd': spd, 'mean_tps': tps,
                'launches': [l],
            }
            clusters.append(newc)

    # Compute stats and mean series for each cluster
    for c in clusters:
        ll = c['launches']
        c['rpm_std'] = _s_std([x.get('pre_rpm',0) for x in ll])
        c['spd_std'] = _s_std([x.get('pre_spd',0) for x in ll])
        c['tps_std'] = _s_std([x.get('pre_tps',0) for x in ll])

        # Peak metrics stats
        pk_pw_vals = [x.get('peak_pw',0) for x in ll]
        pk_ae_vals = [x.get('peak_ae',0) for x in ll]
        rpm_g_vals = [x.get('rpm_gain',0) for x in ll]
        spd_g_vals = [x.get('spd_gain',0) for x in ll]
        dtps_vals = [x.get('dtps_raw',0) for x in ll]

        c['peak_pw_mean'] = sum(pk_pw_vals) / len(pk_pw_vals)
        c['peak_pw_std'] = _s_std(pk_pw_vals)
        c['peak_ae_mean'] = sum(pk_ae_vals) / len(pk_ae_vals)
        c['peak_ae_std'] = _s_std(pk_ae_vals)
        c['rpm_gain_mean'] = sum(rpm_g_vals) / len(rpm_g_vals)
        c['rpm_gain_std'] = _s_std(rpm_g_vals)
        c['spd_gain_mean'] = sum(spd_g_vals) / len(spd_g_vals)
        c['spd_gain_std'] = _s_std(spd_g_vals)
        c['dtps_mean'] = sum(dtps_vals) / len(dtps_vals)
        c['dtps_std'] = _s_std(dtps_vals)

        # Build mean curve at common time points
        dt_min = 0
        dt_max = 0
        for x in ll:
            pts = x.get('series', [])
            if pts:
                t0 = pts[0]['dt']
                t1 = pts[-1]['dt']
                if t0 < dt_min: dt_min = t0
                if t1 > dt_max: dt_max = t1

        # Interpolate each launch to 0.25s intervals
        time_points = []
        t = dt_min
        while t <= dt_max + 0.01:
            time_points.append(round(t, 2))
            t += 0.25

        if len(time_points) > 1:
            mean_rpm_curve = [0.0] * len(time_points)
            mean_tps_curve = [0.0] * len(time_points)
            mean_pw_curve = [0.0] * len(time_points)
            mean_ae_curve = [0.0] * len(time_points)
            mean_spd_curve = [0.0] * len(time_points)
            all_rpm_curves = []
            all_tps_curves = []
            all_pw_curves = []
            all_ae_curves = []
            all_spd_curves = []

            for x in ll:
                pts = x.get('series', [])
                rpm_vals = []
                tps_vals = []
                pw_vals = []
                ae_vals = []
                spd_vals = []
                for tp in time_points:
                    # Find nearest point in series
                    best = None
                    best_dt = 999
                    for p in pts:
                        d = abs(p['dt'] - tp)
                        if d < best_dt:
                            best_dt = d
                            best = p
                    if best and best_dt < 0.15:
                        rpm_vals.append(best.get('rpm', 0))
                        tps_vals.append(best.get('tps', 0))
                        pw_vals.append(best.get('pw1', 0) or best.get('pw2', 0) or 0)
                        ae_vals.append(best.get('ae', 0))
                        spd_vals.append(best.get('spd', 0))
                    else:
                        rpm_vals.append(None)
                        tps_vals.append(None)
                        pw_vals.append(None)
                        ae_vals.append(None)
                        spd_vals.append(None)

                all_rpm_curves.append(rpm_vals)
                all_tps_curves.append(tps_vals)
                all_pw_curves.append(pw_vals)
                all_ae_curves.append(ae_vals)
                all_spd_curves.append(spd_vals)

            for i in range(len(time_points)):
                r_vals = [cv[i] for cv in all_rpm_curves if cv[i] is not None]
                t_vals = [cv[i] for cv in all_tps_curves if cv[i] is not None]
                p_vals = [cv[i] for cv in all_pw_curves if cv[i] is not None]
                a_vals = [cv[i] for cv in all_ae_curves if cv[i] is not None]
                s_vals = [cv[i] for cv in all_spd_curves if cv[i] is not None]
                if r_vals:
                    mean_rpm_curve[i] = sum(r_vals) / len(r_vals)
                if t_vals:
                    mean_tps_curve[i] = sum(t_vals) / len(t_vals)
                if p_vals:
                    mean_pw_curve[i] = sum(p_vals) / len(p_vals)
                if a_vals:
                    mean_ae_curve[i] = sum(a_vals) / len(a_vals)
                    if s_vals:
                        mean_spd_curve[i] = sum(s_vals) / len(s_vals)

            # Std curves
            std_rpm_curve = [0.0] * len(time_points)
            std_tps_curve = [0.0] * len(time_points)
            std_spd_curve = [0.0] * len(time_points)
            for i in range(len(time_points)):
                r_vals = [cv[i] for cv in all_rpm_curves if cv[i] is not None]
                t_vals = [cv[i] for cv in all_tps_curves if cv[i] is not None]
                s_vals = [cv[i] for cv in all_spd_curves if cv[i] is not None]
                if r_vals:
                    std_rpm_curve[i] = _s_std(r_vals)
                if t_vals:
                    std_tps_curve[i] = _s_std(t_vals)
                if s_vals:
                    std_spd_curve[i] = _s_std(s_vals)

            c['mean_series'] = [{'dt': time_points[i], 'rpm': round(mean_rpm_curve[i], 1),
                                 'tps': round(mean_tps_curve[i], 1), 'pw': round(mean_pw_curve[i], 3),
                                 'ae': round(mean_ae_curve[i], 1), 'spd': round(mean_spd_curve[i], 1)} for i in range(len(time_points))]
            c['std_series'] = [{'dt': time_points[i], 'rpm': round(std_rpm_curve[i], 1),
                                'tps': round(std_tps_curve[i], 1), 'spd': round(std_spd_curve[i], 1)} for i in range(len(time_points))]
        else:
            c['mean_series'] = []
            c['std_series'] = []

        # Remove raw launches from cluster (keep in original arrays)
        del c['launches']

    # Sort clusters by gear, then count desc
    clusters.sort(key=lambda c: (c['gear'] if c['gear'] else 99, -c['count']))
    # Re-assign sequential IDs
    for i, c in enumerate(clusters):
        c['id'] = i
    return clusters


def match_clusters(clusters_a, clusters_b, rpm_tol=400, spd_tol=12, tps_tol=2.5):
    """
    Find matching clusters between sessions A and B.
    Returns list of (a_idx, b_idx, distance) for matched pairs.
    """
    matches = []
    used_b = set()
    for ca in clusters_a:
        best_b = None
        best_d = float('inf')
        for j, cb in enumerate(clusters_b):
            if j in used_b:
                continue
            if ca['gear'] != cb['gear']:
                continue
            dr = abs(ca['mean_rpm'] - cb['mean_rpm']) / rpm_tol
            ds = abs(ca['mean_spd'] - cb['mean_spd']) / spd_tol
            dt = abs(ca['mean_tps'] - cb['mean_tps']) / max(tps_tol, 0.1)
            d = dr + ds + dt
            if d < best_d:
                best_d = d
                best_b = j
        if best_b is not None and best_d < 2.0:
            matches.append((ca['id'], clusters_b[best_b]['id'], round(best_d, 2)))
            used_b.add(best_b)
    return matches

def _compare_sessions(buell_dir, sa, sb):
    from collections import defaultdict

    RPM_BINS = [800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
    TPS_BINS = [0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]

    def bucket(val, bins):
        for i in range(len(bins)-1):
            if bins[i] <= val < bins[i+1]: return i
        return len(bins)-2

    def sf(v, d=0.0):
        try: return float(v) if v and str(v).strip() else d
        except (ValueError, TypeError): return d

    def load_meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        meta = {}
        if mp.exists():
            with open(mp) as f: meta = json.load(f)
        # leer serial del eeprom.bin para identificar moto
        ep = buell_dir / 'sessions' / sid / 'eeprom.bin'
        if ep.exists():
            try:
                b = ep.read_bytes()
                if len(b) >= 14:
                    meta['bike_serial'] = int.from_bytes(b[12:14], 'little')
            except (OSError, TypeError):
                logging.getLogger("WebServer").debug("load_meta: could not read serial from %s" % ep)
        return meta

    def load_csv(sid):
        rows = []
        sdir = buell_dir / 'sessions' / sid
        csv_files = sorted(sdir.glob('ride_*.csv'))
        time_offset = 0.0
        last_ride_num = -1
        for cp in csv_files:
            with open(cp) as f:
                lines = [l for l in f if not l.startswith('#')]
            if not lines: continue
            # Peek ride number from first data row (lines[0] is header)
            if len(lines) < 2: continue
            peek = list(csv.DictReader(lines[:2]))
            if not peek: continue
            ride_num = int(sf(peek[0].get('ride_num', 0)))
            # Advance offset only when ride number changes (new ride, not continuation)
            if last_ride_num != -1 and ride_num != last_ride_num and rows:
                time_offset = rows[-1]['t'] + 0.001
            last_ride_num = ride_num
            for r in csv.DictReader(lines):
                try:
                    rpm = sf(r['RPM'])
                    if rpm < 100: continue
                    rows.append({
                        't':    sf(r['time_elapsed_s']) + time_offset,
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
                except Exception as e:
                    logging.getLogger("WebServer").debug("csv row skip: %s" % e)
                    continue
        return rows

    def derivatives(rows):
        for i in range(1, len(rows)):
            dt = rows[i]['t'] - rows[i-1]['t']
            if 0 < dt < 2.0:
                rows[i]['drpm'] = (rows[i]['rpm'] - rows[i-1]['rpm']) / dt
                rows[i]['dtps'] = (rows[i]['tps'] - rows[i-1]['tps']) / dt
                rows[i]['dvss'] = (rows[i]['spd'] - rows[i-1]['spd']) / dt
                a0, a1 = rows[i-1]['alt'], rows[i]['alt']
                if a0 is not None and a1 is not None:
                    dalt = a1 - a0
                    # slope = dAlt/dDist — pendiente real sin dimension
                    spd_ms = (rows[i]['spd'] + rows[i-1]['spd']) / 2 / 3.6
                    ddist = spd_ms * dt
                    rows[i]['dalt'] = dalt / dt  # m/s para clasificacion
                    rows[i]['slope'] = dalt / ddist if ddist > 0.1 else 0.0
                else:
                    rows[i]['dalt'] = None
                    rows[i]['slope'] = None
            else:
                rows[i]['drpm'] = rows[i]['dtps'] = rows[i]['dvss'] = 0.0
                rows[i]['dalt'] = None
                rows[i]['slope'] = None
        if rows:
            rows[0]['drpm'] = rows[0]['dtps'] = rows[0]['dvss'] = 0.0
            rows[0]['dalt'] = rows[0]['slope'] = None

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
        idx = defaultdict(lambda: {
            'n':0,'pw1':0,'pw2':0,'spark1':0,'spark2':0,'clt':0,'afv':0,
            'drpm':0,'spd':0,'dvss':0,'pw_eff':0,'gear':0,
            'dalt':0,'dalt_n':0,'slope':0,'slope_n':0,
            # Welford online para std_rpm y std_tps
            'rpm_m':0.0,'rpm_m2':0.0,'tps_m':0.0,'tps_m2':0.0,
        })
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
            c['gear']  += r.get('gear', 0)
            if r.get('dalt') is not None:
                c['dalt']   += r['dalt']
                c['dalt_n'] += 1
            if r.get('slope') is not None:
                c['slope']   += r['slope']
                c['slope_n'] += 1
            # Welford online std_rpm
            n2 = c['n']
            delta_rpm = r['rpm'] - c['rpm_m']
            c['rpm_m']  += delta_rpm / n2
            c['rpm_m2'] += delta_rpm * (r['rpm'] - c['rpm_m'])
            delta_tps = r['tps'] - c['tps_m']
            c['tps_m']  += delta_tps / n2
            c['tps_m2'] += delta_tps * (r['tps'] - c['tps_m'])
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
                'gear':  round(c['gear']/n, 1),
                'dalt':  round(c['dalt']/c['dalt_n'], 2) if c['dalt_n']>0 else None,
                'slope': round(c['slope']/c['slope_n'], 4) if c['slope_n']>0 else None,
                'std_rpm': round((c['rpm_m2']/n)**0.5, 1) if n>1 else 0.0,
                'std_tps': round((c['tps_m2']/n)**0.5, 2) if n>1 else 0.0,
            }
        return result, dict(fc)

    # Cargar ambas sesiones
    ma, mb = load_meta(sa), load_meta(sb)
    ra, rb = load_csv(sa), load_csv(sb)
    derivatives(ra); derivatives(rb)
    ia, fca = build_index(ra)
    ib, fcb = build_index(rb)
    launches_a = detect_launches(ra)
    launches_b = detect_launches(rb)

    # Cluster similar launches
    clusters_a = cluster_launches(launches_a)
    clusters_b = cluster_launches(launches_b)
    cluster_matches = match_clusters(clusters_a, clusters_b)

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
            'gear_a':   a['gear'],
            'gear_b':   b['gear'],
            'dalt_a':   a['dalt'],
            'dalt_b':   b['dalt'],
            'slope_a':  a['slope'],
            'slope_b':  b['slope'],
            'std_rpm_a':a['std_rpm'],
            'std_rpm_b':b['std_rpm'],
            'std_tps_a':a['std_tps'],
            'std_tps_b':b['std_tps'],
            'pw_eff_a': a['pw_eff'],
            'pw_eff_b': b['pw_eff'],
            'dpw_eff':  round(b['pw_eff'] - a['pw_eff'], 3),
        })
    delta.sort(key=lambda x: (x['flavor'], -(x['na']+x['nb'])))

    return {
        'sa': {'id': sa, 'checksum': ma.get('checksum','?'), 'version': ma.get('version_string','?'),
               'created': ma.get('created_utc','')[:10], 'rides': ma.get('total_rides',0),
               'samples': len(ra), 'flavors': fca,
               'launches_a': launches_a},
        'sb': {'id': sb, 'checksum': mb.get('checksum','?'), 'version': mb.get('version_string','?'),
               'created': mb.get('created_utc','')[:10], 'rides': mb.get('total_rides',0),
               'samples': len(rb), 'flavors': fcb,
               'launches_b': launches_b},
        'clusters_a': clusters_a,
        'clusters_b': clusters_b,
        'cluster_matches': cluster_matches,
        'same_bike': ma.get('bike_serial') is not None and ma.get('bike_serial') == mb.get('bike_serial'),
        'bike_serial_a': ma.get('bike_serial'),
        'bike_serial_b': mb.get('bike_serial'),
        'common': len(common),
        'delta': delta,
    }
    