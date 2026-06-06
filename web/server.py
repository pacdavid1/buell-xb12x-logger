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
            '/eeprom/sessions-list': self._handle_eeprom_sessions_list,
            '/eeprom/msq':      self._handle_eeprom_msq,
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


    def _handle_session_events(self, path=None):
        """Serve the Session Events (FASE7) page."""
        try:
            buell_dir = self.server_instance.buell_dir
            tmpl = (buell_dir / 'web' / 'templates' / 'session_events.html').read_text()
            self._html(tmpl)
        except Exception as e:
            self._html(f'<pre>Error: {e}</pre>', 500)

    def _handle_session_events_data(self, path=None):
        """Return cluster JSON for a session. ?session=<checksum>&threshold=0.85"""
        from urllib.parse import urlparse, parse_qs
        buell_dir = self.server_instance.buell_dir
        qs        = parse_qs(urlparse(self.path).query)
        sid       = (qs.get('session', [''])[0]).strip().upper()
        threshold = float((qs.get('threshold', ['0.85'])[0]))
        if not sid:
            self._json({'error': 'missing session param'}, 400)
            return
        sdir = buell_dir / 'sessions' / sid
        if not sdir.is_dir():
            self._json({'error': f'session {sid} not found'}, 404)
            return
        try:
            data = _f7_load_session_clusters(buell_dir, sid, threshold)
            self._json(data)
        except Exception as e:
            import traceback
            self._json({'error': str(e), 'trace': traceback.format_exc()}, 500)

    def _handle_session_events_download(self, path=None):
        """Return cluster JSON as downloadable file."""
        from urllib.parse import urlparse, parse_qs
        buell_dir = self.server_instance.buell_dir
        qs        = parse_qs(urlparse(self.path).query)
        sid       = (qs.get('session', [''])[0]).strip().upper()
        threshold = float((qs.get('threshold', ['0.85'])[0]))
        if not sid:
            self._json({'error': 'missing session param'}, 400); return
        sdir = buell_dir / 'sessions' / sid
        if not sdir.is_dir():
            self._json({'error': f'session {sid} not found'}, 404); return
        try:
            data  = _f7_load_session_clusters(buell_dir, sid, threshold)
            body  = json.dumps(data, indent=2).encode('utf-8')
            fname = f'session_events_{sid}_{threshold}.json'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', f'attachment; filename={fname}')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json({'error': str(e)}, 500)

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
                    if not first:
                        fh.readline()  # skip comment line
                        fh.readline()  # skip CSV header
                    chunks.append(fh.read())
                first = False
            if not chunks:
                self._json({'error': 'CSV file not found for this ride'}, 404)
                return
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
        msq_path = self.server_instance.buell_dir / 'sessions' / cs / ('suggested_' + cs + '.msq')
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

    def _handle_eeprom_msq(self, path=None):
        """Generate MSQ from eeprom_decoded.json for a session (no tuning modifications)."""
        import urllib.parse, re
        params  = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'}); return
        buell_dir = self.server_instance.buell_dir
        if not session:
            cs = getattr(self.server_instance.session, 'current_checksum', None)
            session = cs
        if not session:
            decoded_files = sorted(
                (buell_dir / 'sessions').glob('*/eeprom_decoded.json'),
                key=lambda p: p.stat().st_mtime)
            if not decoded_files:
                self._json({'error': 'no eeprom_decoded.json found in any session'}); return
            session = decoded_files[-1].parent.name
        decoded_path = buell_dir / 'sessions' / session / 'eeprom_decoded.json'
        bin_path     = buell_dir / 'sessions' / session / 'eeprom.bin'
        eeprom_maps  = None
        if decoded_path.exists():
            try:
                with open(decoded_path) as f:
                    eeprom_maps = json.load(f).get('maps', {})
            except Exception as e:
                self._json({'error': 'could not read eeprom_decoded.json: ' + str(e)}); return
        elif bin_path.exists():
            try:
                from ecu.eeprom import decode_eeprom_maps
                eeprom_maps = decode_eeprom_maps(bin_path.read_bytes())
            except Exception as e:
                self._json({'error': 'could not decode eeprom.bin: ' + str(e)}); return
        else:
            self._json({'error': 'no eeprom data found for session ' + session}); return
        msq_xml = _eeprom_to_msq({'maps': eeprom_maps}, session)
        data    = msq_xml.encode('utf-8')
        fname   = 'eeprom_' + session + '.msq'
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Disposition', 'attachment; filename="' + fname + '"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


    def _handle_eeprom_sessions_list(self, path=None):
        """Return list of sessions that have an eeprom.bin, sorted newest first."""
        import datetime
        buell_dir = self.server_instance.buell_dir
        current_cs = getattr(self.server_instance.session, 'current_checksum', None)
        rows = []
        for sid in (buell_dir / 'sessions').iterdir():
            eeprom_file = sid / 'eeprom.bin'
            if not eeprom_file.exists(): continue
            meta_file = sid / 'session_metadata.json'
            rides = 0
            if meta_file.exists():
                try:
                    import json as _json
                    meta = _json.loads(meta_file.read_text())
                    rides = meta.get('total_rides', 0)
                except Exception: pass
            mtime = eeprom_file.stat().st_mtime
            rows.append({
                'id':      sid.name,
                'mtime':   mtime,
                'date':    datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M'),
                'rides':   rides,
                'current': sid.name == current_cs,
            })
        rows.sort(key=lambda r: r['mtime'], reverse=True)
        self._json(rows)

    def _handle_eeprom_revert(self, path=None, payload=None):
        """Revert ECU EEPROM to a previous session's eeprom.bin."""
        import queue as _queue
        body      = payload or {}
        target_id = body.get('session', '').strip()
        import re as _re
        if not target_id or not _re.match(r'^[A-Fa-f0-9]{6}$', target_id):
            self._json({'error': 'invalid session id'}); return
        if getattr(self.server_instance, 'ride_active', False):
            self._json({'error': 'cannot revert while ride is active'}); return
        buell_dir   = self.server_instance.buell_dir
        target_path = buell_dir / 'sessions' / target_id / 'eeprom.bin'
        if not target_path.exists():
            self._json({'error': 'eeprom.bin not found for session ' + target_id}); return
        proposed = target_path.read_bytes()
        import time as _time
        cs  = getattr(self.server_instance.session, 'current_checksum', None)
        if cs:
            backup_dir  = buell_dir / 'sessions' / cs
            backup_path = backup_dir / ('eeprom_backup_revert_' + _time.strftime('%Y%m%d_%H%M%S') + '.bin')
            try:
                current_eeprom = (backup_dir / 'eeprom.bin').read_bytes()
                backup_path.write_bytes(current_eeprom)
            except Exception: pass
        result_q = _queue.Queue()
        main_app = getattr(self.server_instance, '_main_app', None)
        if main_app is None:
            self._json({'error': 'main app not available'}); return
        main_app.pending_burn = (proposed, result_q)
        try:
            result = result_q.get(timeout=90)
        except _queue.Empty:
            main_app.pending_burn = None
            self._json({'error': 'revert timeout (90s) — ECU may be busy'}); return
        result['reverted_to'] = target_id
        self._json(result)

    def _handle_eeprom_burn(self, path=None, payload=None):
        """Burn proposed map changes to ECU EEPROM.
        POST body: { maps: { fuel_front?, fuel_rear?, spark_front?, spark_rear? } }
        Only allowed when no ride is active. Saves backup before burn.
        """
        import queue as _queue
        if getattr(self.server_instance, 'ride_active', False):
            self._json({'error': 'cannot burn while ride is active'}); return

        body = payload or {}
        maps = body.get('maps', {})
        changes = body.get('changes', [])
        if not maps and not changes:
            self._json({'error': 'no maps or changes provided'}); return

        # Load current EEPROM from active session or most recent
        buell_dir = self.server_instance.buell_dir
        cs = getattr(self.server_instance.session, 'current_checksum', None)
        if not cs:
            bins = sorted((buell_dir/'sessions').glob('*/eeprom.bin'),
                          key=lambda p: p.stat().st_mtime)
            if not bins:
                self._json({'error': 'no eeprom.bin found'}); return
            eeprom_path = bins[-1]
        else:
            eeprom_path = buell_dir / 'sessions' / cs / 'eeprom.bin'
        if not eeprom_path.exists():
            self._json({'error': 'eeprom.bin not found for session ' + str(cs)}); return

        current_bin = eeprom_path.read_bytes()

        # Apply staged cell changes to current EEPROM
        from ecu.eeprom import encode_eeprom_maps, decode_eeprom_maps
        try:
            if changes:
                current_maps = decode_eeprom_maps(current_bin)
                for ch in changes:
                    mk = ch.get('map'); ri = int(ch.get('ri',0)); ci = int(ch.get('ci',0)); val = float(ch.get('val',0))
                    if mk not in current_maps or not isinstance(current_maps[mk], list): continue
                    if ri >= len(current_maps[mk]) or ci >= len(current_maps[mk][ri]): continue
                    if mk not in maps:
                        maps[mk] = [row[:] for row in current_maps[mk]]
                    maps[mk][ri][ci] = val
            proposed = encode_eeprom_maps(current_bin, maps)
        except Exception as e:
            self._json({'error': 'encode failed: ' + str(e)}); return

        # Save backup before burn
        import time as _time
        ts = _time.strftime('%Y%m%d_%H%M%S')
        backup_path = eeprom_path.parent / ('eeprom_backup_' + ts + '.bin')
        backup_path.write_bytes(current_bin)

        # Queue burn request to ECU loop
        result_q = _queue.Queue()
        main_app = getattr(self.server_instance, '_main_app', None)
        if main_app is None:
            self._json({'error': 'main app not available'}); return
        main_app.pending_burn = (proposed, result_q)
        try:
            result = result_q.get(timeout=30)
        except _queue.Empty:
            main_app.pending_burn = None
            self._json({'error': 'burn timeout (30s)'}); return

        result['backup'] = backup_path.name
        self._json(result)

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
                sessions_dir = self.server_instance.buell_dir / 'sessions'
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
                sessions_dir = self.server_instance.buell_dir / 'sessions'
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
            # Only restart logger if there are actual changes
            if 'Already up to date' not in output and 'up-to-date' not in output:
                subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
            else:
                output = 'Already up to date'
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
            # Invalidate rides cache
            with self.server_instance._rides_cache_lock:
                self.server_instance._rides_cache = None
                self.server_instance._rides_cache_time = 0
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
CACHE_VERSION = 5  # bump when detect_launches, cluster_launches, or f7_matches schema changes
_cache_lock = threading.Lock()

def _eeprom_to_msq(eeprom, session=''):
    """Serialize eeprom_decoded.json dict to MSQ XML (EcmSpy format, no modifications)."""
    from datetime import datetime, timezone
    maps       = eeprom.get('maps', {})
    axes       = maps.get('axes', {})
    fuel_front = maps.get('fuel_front', [])
    fuel_rear  = maps.get('fuel_rear',  [])
    spark_front= maps.get('spark_front',[])
    spark_rear = maps.get('spark_rear', [])
    fuel_load  = axes.get('fuel_load', [])
    fuel_rpm   = axes.get('fuel_rpm',  [])
    sl         = axes.get('spark_load',[])
    sr         = axes.get('spark_rpm', [])

    def ax1b(v): return '\n'.join('      '+str(x) for x in v)
    def ax2b(v): return '\n'.join('    '+str(x)   for x in v)
    def mapfuel(t):
        return '\n'.join('      '+' '.join(str(int(c)) if c is not None else '0' for c in row) for row in t)
    def mapspark(t):
        return '\n'.join('      '+' '.join('{:.2f}'.format(c) if c is not None else '0.00' for c in row) for row in t)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    nfl = len(fuel_load); nfr = len(fuel_rpm)
    nsl = len(sl);        nsr = len(sr)
    nff_c = len(fuel_front[0]) if fuel_front else 0
    nfr_c = len(fuel_rear[0])  if fuel_rear  else 0
    nsf_c = len(spark_front[0])if spark_front else 0
    nsr_c = len(spark_rear[0]) if spark_rear  else 0

    lines = [
        '<?xml version="1.0"?>',
        '<msq xmlns="http://www.ecmspy.com/">',
        '  <bibliography author="BuellLogger/'+now+' session='+session+'" writeDate="'+now+'" />',
        '  <versionInfo fileFormat="4" nPages="1" signature="BUEIB" />',
        '  <page number="0">',
        '    <constant name="z_factor">4.00</constant>',
        '    <constant name="tpsBins1" rows="'+str(nfl)+'" units="TPS">',
        ax1b(fuel_load),'</constant>',
        '    <constant name="rpmBins1" rows="'+str(nfr)+'" units="RPM">',
        ax2b(fuel_rpm),'</constant>',
        '    <constant name="veBins1" rows="'+str(len(fuel_front))+'" cols="'+str(nff_c)+'" units="fuel">',
        mapfuel(fuel_front),'','</constant>',
        '    <constant name="tpsBins2" rows="'+str(nfl)+'" units="TPS">',
        ax1b(fuel_load),'</constant>',
        '    <constant name="rpmBins2" rows="'+str(nfr)+'" units="RPM">',
        ax2b(fuel_rpm),'</constant>',
        '    <constant name="veBins2" rows="'+str(len(fuel_rear))+'" cols="'+str(nfr_c)+'" units="fuel">',
        mapfuel(fuel_rear),'','</constant>',
        '    <constant name="tpsBins3" rows="'+str(nsl)+'" units="TPS">',
        ax1b(sl),'</constant>',
        '    <constant name="rpmBins3" rows="'+str(nsr)+'" units="RPM">',
        ax2b(sr),'</constant>',
        '    <constant name="advTable1" rows="'+str(len(spark_front))+'" cols="'+str(nsf_c)+'" units="deg BTDC">',
        mapspark(spark_front),'','</constant>',
        '    <constant name="tpsBins4" rows="'+str(nsl)+'" units="TPS">',
        ax1b(sl),'</constant>',
        '    <constant name="rpmBins4" rows="'+str(nsr)+'" units="RPM">',
        ax2b(sr),'</constant>',
        '    <constant name="advTable2" rows="'+str(len(spark_rear))+'" cols="'+str(nsr_c)+'" units="deg BTDC">',
        mapspark(spark_rear),'','</constant>',
        '  </page>',
        '</msq>',
    ]
    return '\n'.join(lines)


def _compare_sessions_cached(buell_dir, sa, sb):
    import json as _json
    def _meta(sid):
        mp = buell_dir / 'sessions' / sid / 'session_metadata.json'
        if mp.exists():
            with open(mp) as f: return json.load(f)
        return {}
    ma, mb = _meta(sa), _meta(sb)
    fname = f"sessions_vs_v{CACHE_VERSION}_{sa}-{_fmtk(ma.get('total_samples',0))}_{sb}-{_fmtk(mb.get('total_samples',0))}.json"
    cache_dir = buell_dir / 'sessions' / '_cache'
    cache_file = cache_dir / fname
    if cache_file.exists():
        try:
            with _cache_lock:
                if not cache_file.exists():
                    raise FileNotFoundError
                with open(cache_file) as _cf:
                    cached = json.load(_cf)
            # Accept cached data even without clusters_a (legacy caches)
            if 'sa' in cached and 'clusters_a' in cached and cached.get('_cache_version') == CACHE_VERSION:
                return cached
        except Exception:
            pass
    result = _compare_sessions(buell_dir, sa, sb)
    result["_cache_version"] = CACHE_VERSION
    cache_dir.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        with open(cache_file, 'w') as f:
            json.dump(result, f)
    return result




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
