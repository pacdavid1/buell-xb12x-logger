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
            '/session_events/data': self._handle_session_events_data,
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
CACHE_VERSION = 4  # bump when detect_launches or cluster_launches schema changes
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




# ── FASE7: Event detection & PW similarity clustering ────────────────────────
# Inverse-order algorithm: cluster by PW curve (DTW) first, validate Bucket A second.

import math as _math

_F7_N       = 20    # resample points
_F7_WINDOW  = 3     # Sakoe-Chiba window
_F7_THRESH  = 0.85  # default DTW threshold
_F7_EVENTS_V = 4     # bump when event struct fields change


def _f7_resample(series, n=_F7_N):
    L = len(series)
    if L == 0:
        return [0.0] * n
    if L >= n:
        idx = [int(round(i * (L - 1) / (n - 1))) for i in range(n)]
        return [series[i] for i in idx]
    x_old = [i / (L - 1) for i in range(L)] if L > 1 else [0.0]
    x_new = [i / (n - 1) for i in range(n)]
    out = []
    for x in x_new:
        lo = max((i for i, v in enumerate(x_old) if v <= x), default=0)
        hi = min((i for i, v in enumerate(x_old) if v >= x), default=L - 1)
        if lo == hi:
            out.append(series[lo])
        else:
            t = (x - x_old[lo]) / (x_old[hi] - x_old[lo])
            out.append(series[lo] + t * (series[hi] - series[lo]))
    return out


def _f7_dtw(a, b, window=_F7_WINDOW):
    """DTW similarity 0-1 with Sakoe-Chiba window, normalized by combined range."""
    n = len(a)
    INF = float('inf')
    mat = [[INF] * (n + 1) for _ in range(n + 1)]
    mat[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - window), min(n, i + window) + 1):
            cost = abs(a[i - 1] - b[j - 1])
            mat[i][j] = cost + min(mat[i-1][j], mat[i][j-1], mat[i-1][j-1])
    raw = mat[n][n]
    cr = max(max(a), max(b)) - min(min(a), min(b))
    if cr == 0:
        return 1.0
    return max(0.0, 1.0 - raw / (n * cr))


def _f7_rolling_std(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return _math.sqrt(sum((x - m) ** 2 for x in vals) / n)


def _f7_detect_events(rows):
    """Detect acceleration events: stable bucket A >= 3s, then break, then PW rises."""
    STABLE_S    = 3.0
    RPM_STD_MAX = 150
    TPS_STD_MAX = 2.0
    TPS_BREAK   = 2.0
    MIN_VSS     = 5.0
    MAX_DUR     = 5.0
    MIN_SAMPLES = 4
    WINDOW      = 24  # ~3s at 8Hz

    events = []
    stable_buf = []
    stable_t   = 0.0
    in_stable  = False

    for i, row in enumerate(rows):
        if row.get('spd', 0) < MIN_VSS or row.get('gear', 0) < 1 or not row.get('fl_eng', True):
            stable_buf = []
            stable_t   = 0.0
            in_stable  = False
            continue

        stable_buf.append(row)
        if len(stable_buf) > WINDOW:
            stable_buf.pop(0)
        if len(stable_buf) < WINDOW // 2:
            continue

        rpm_s = _f7_rolling_std([r['rpm'] for r in stable_buf])
        tps_s = _f7_rolling_std([r['tps'] for r in stable_buf])
        dt    = (row['t'] - rows[i - 1]['t']) if i > 0 else 0.13

        if rpm_s < RPM_STD_MAX and tps_s < TPS_STD_MAX:
            stable_t += dt
            if stable_t >= STABLE_S:
                in_stable = True
        else:
            if in_stable:
                tail_tps = sum(r['tps'] for r in stable_buf[-5:]) / min(5, len(stable_buf))
                _tps_delta = row['tps'] - tail_tps
                if abs(_tps_delta) >= TPS_BREAK:
                    _ev_type = 'accel' if _tps_delta > 0 else 'decel'
                    win = stable_buf[-WINDOW:]
                    bucket_a = {
                        'gear':    int(round(sum(r['gear'] for r in win) / len(win))),
                        'rpm_avg': round(sum(r['rpm'] for r in win) / len(win), 0),
                        'tps_avg': round(sum(r['tps'] for r in win) / len(win), 1),
                        'vss_avg': round(sum(r['spd'] for r in win) / len(win), 1),
                        'clt_avg': round(sum(r['clt'] for r in win) / len(win), 1),
                    }
                    t0     = row['t']
                    gear0  = bucket_a['gear']
                    tps0   = bucket_a['tps_avg']
                    phase_b = []
                    tps_ret = 0
                    for r2 in rows[i:]:
                        if r2['t'] - t0 > MAX_DUR:
                            break
                        if int(round(r2.get('gear', 0))) != gear0:
                            break
                        if r2.get('fl_fc', False):
                            break
                        if abs(r2['tps'] - tps0) < TPS_BREAK:
                            tps_ret += 1
                            if tps_ret >= 16:
                                break
                        else:
                            tps_ret = 0
                        phase_b.append(r2)

                    if len(phase_b) >= MIN_SAMPLES:
                        pw_s = [(r['pw1'] + r.get('pw2', r['pw1'])) / 2 for r in phase_b]

                        # Trim at fuel cut: PW < 2ms means injector off
                        fc_cut = next((k for k, pw in enumerate(pw_s) if pw < 2.0), len(pw_s))
                        if fc_cut < len(pw_s):
                            phase_b = phase_b[:fc_cut]
                            pw_s    = pw_s[:fc_cut]

                        # Trim when PW drops >35% below peak for 2+ consecutive samples
                        if pw_s:
                            pk     = pw_s[0]
                            drop_n = 0
                            drop_cut = len(pw_s)
                            for k, pw in enumerate(pw_s):
                                if pw > pk:
                                    pk     = pw
                                    drop_n = 0
                                elif pk >= pw_s[0] * 1.3 and pw < pk * 0.65:
                                    drop_n += 1
                                    if drop_n >= 2:
                                        drop_cut = max(k - 1, 1)
                                        break
                                else:
                                    drop_n = 0
                            if drop_cut < len(pw_s):
                                phase_b = phase_b[:drop_cut]
                                pw_s    = pw_s[:drop_cut]

                        if len(phase_b) < MIN_SAMPLES:
                            in_stable = False
                            stable_buf = [row]
                            stable_t   = 0.0
                            continue

                        pw1_s  = [r['pw1'] for r in phase_b]
                        pw2_s  = [r.get('pw2', r['pw1']) for r in phase_b]
                        tps_s2 = [r['tps'] for r in phase_b]
                        vss_s  = [r['spd'] for r in phase_b]
                        rpm_s  = [r['rpm'] for r in phase_b]
                        dur    = phase_b[-1]['t'] - phase_b[0]['t']
                        vss_d  = vss_s[-1] - vss_s[0]

                        # accel: PW must rise; decel: any pattern allowed
                        if _ev_type == 'accel' and max(pw_s) <= pw_s[0] * 1.05:
                            in_stable = False
                            stable_buf = [row]
                            stable_t   = 0.0
                            continue

                        # Pre-break series: resample last WINDOW samples to PRE_N points
                        _PRE_N = 10
                        pre_pw_c  = _f7_resample([(r['pw1']+r.get('pw2',r['pw1']))/2 for r in win], _PRE_N)
                        pre_rpm_c = _f7_resample([r['rpm'] for r in win], _PRE_N)
                        pre_vss_c = _f7_resample([r['spd'] for r in win], _PRE_N)
                        pre_tps_c = _f7_resample([r['tps'] for r in win], _PRE_N)

                        # tps_curve_norm: Phase A tail (3 samples) + Phase B, normalized [0,1]
                        # Captures start of rider gesture for cross-session DTW matching
                        _tail_tps = [r['tps'] for r in stable_buf[-3:]]
                        _full_tps = _tail_tps + tps_s2
                        _mx = max(_full_tps) if max(_full_tps) > 0 else 1.0
                        tps_curve_norm = _f7_resample([v / _mx for v in _full_tps])

                        # GPS slope from stable window (Bucket A terrain context)
                        _gw = [r for r in win if r.get('gps_valid') and r.get('gps_alt', 0) != 0]
                        if len(_gw) >= 4:
                            _alt_d = _gw[-1]['gps_alt'] - _gw[0]['gps_alt']
                            _t_sp  = _gw[-1]['t'] - _gw[0]['t']
                            _vavg  = sum(r['spd'] for r in _gw) / len(_gw)
                            _dist  = _vavg * _t_sp * 1000 / 3600
                            gps_slope = round(_alt_d / _dist * 100, 2) if _dist > 5 else 0.0
                        else:
                            gps_slope = 0.0

                        # Environmental context from Bucket A window
                        _baro_vals = [r['baro'] for r in win if r.get('baro', 0) > 0]
                        _temp_vals = [r['temp_amb'] for r in win if r.get('temp_amb', 0) != 0]
                        _clt_vals  = [r['clt'] for r in win if r.get('clt', 0) > 0]

                        events.append({
                            'event_type': _ev_type,
                            'break_t':    round(t0, 2),
                            'duration':   round(dur, 2),
                            'n_raw':      len(phase_b),
                            'bucket_a':   bucket_a,
                            'pw_curve':   _f7_resample(pw_s),
                            'pw1_curve':  _f7_resample(pw1_s),
                            'pw2_curve':  _f7_resample(pw2_s),
                            'rpm_curve':  _f7_resample(rpm_s),
                            'vss_curve':  _f7_resample(vss_s),
                            'tps_curve':      _f7_resample(tps_s2),
                            'tps_curve_norm': tps_curve_norm,
                            'pre_pw_curve':  pre_pw_c,
                            'pre_rpm_curve': pre_rpm_c,
                            'pre_vss_curve': pre_vss_c,
                            'pre_tps_curve': pre_tps_c,
                            'pw_start':   round(pw_s[0], 2),
                            'pw_peak':    round(max(pw_s), 2),
                            'pw_delta':   round(max(pw_s) - pw_s[0], 2),
                            'tps_start':  round(tps_s2[0], 1),
                            'tps_peak':   round(max(tps_s2), 1),
                            'vss_delta':  round(vss_d, 1),
                            'very_short': dur < 0.5,
                            'gps_slope':  gps_slope,
                            'baro_hpa':   round(sum(_baro_vals)/len(_baro_vals), 1) if _baro_vals else None,
                            'temp_amb_c': round(sum(_temp_vals)/len(_temp_vals), 1) if _temp_vals else None,
                            'clt_avg':    round(sum(_clt_vals)/len(_clt_vals), 1) if _clt_vals else None,
                        })
            in_stable = False
            stable_buf = [row]
            stable_t   = 0.0

    return events


def _f7_ba_consistent(events):
    """True if all events share compatible Bucket A conditions."""
    if len(events) <= 1:
        return True
    gears = [e['bucket_a']['gear'] for e in events]
    rpms  = [e['bucket_a']['rpm_avg'] for e in events]
    tpss  = [e['bucket_a']['tps_avg'] for e in events]
    vsss  = [e['bucket_a']['vss_avg'] for e in events]
    return (
        len(set(gears)) == 1 and
        max(rpms) - min(rpms) <= 250 and
        max(tpss) - min(tpss) <= 3.0 and
        max(vsss) - min(vsss) <= 10.0
    )


def _f7_sub_divide_by_bucket_a(events):
    """Split a PW-similar group into Bucket-A-consistent sub-groups.
    Level 1: gear + 200-RPM bucket. Level 2: 10 km/h VSS bucket. Level 3: 3%-TPS bucket.
    """
    from collections import defaultdict
    if _f7_ba_consistent(events):
        return [events]
    sub1 = defaultdict(list)
    for e in events:
        key = (e['bucket_a']['gear'], int(e['bucket_a']['rpm_avg'] / 200) * 200)
        sub1[key].append(e)
    result = []
    for sg in sub1.values():
        if _f7_ba_consistent(sg):
            result.append(sg)
        else:
            sub2 = defaultdict(list)
            for e in sg:
                sub2[int(e['bucket_a']['vss_avg'] / 10) * 10].append(e)
            for sg2 in sub2.values():
                if _f7_ba_consistent(sg2):
                    result.append(sg2)
                else:
                    sub3 = defaultdict(list)
                    for e in sg2:
                        sub3[int(e['bucket_a']['tps_avg'] / 3) * 3].append(e)
                    result.extend(sub3.values())
    return result


def _f7_cluster(events, threshold=_F7_THRESH):
    """Complete-linkage DTW clustering, then sub-divide by Bucket A consistency."""
    n = len(events)
    if n == 0:
        return []

    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            s = _f7_dtw(events[i]['pw_curve'], events[j]['pw_curve'])
            mat[i][j] = mat[j][i] = s

    # Agglomerative complete linkage: merge only when min cross-pair DTW >= threshold
    clusters_idx = [{i} for i in range(n)]
    while True:
        best_score = threshold - 0.001
        best_pair  = None
        for a in range(len(clusters_idx)):
            for b in range(a + 1, len(clusters_idx)):
                min_cross = min(mat[i][j] for i in clusters_idx[a] for j in clusters_idx[b])
                if min_cross > best_score:
                    best_score = min_cross
                    best_pair  = (a, b)
        if best_pair is None:
            break
        a, b = best_pair
        merged = clusters_idx[a] | clusters_idx[b]
        clusters_idx = [c for idx, c in enumerate(clusters_idx) if idx not in (a, b)]
        clusters_idx.append(merged)

    clusters_idx.sort(key=lambda c: -len(c))

    # Sub-divide each DTW cluster by Bucket A consistency, tracking original indices
    final_groups = []  # list of (ev_list, idx_set)
    for members in clusters_idx:
        ev = [events[i] for i in sorted(members)]
        if len(ev) == 1:
            final_groups.append((ev, members))
        else:
            sub_groups = _f7_sub_divide_by_bucket_a(ev)
            if len(sub_groups) == 1:
                final_groups.append((ev, members))
            else:
                ev_to_idx = {id(events[i]): i for i in sorted(members)}
                for sg in sub_groups:
                    sg_idxs = frozenset(ev_to_idx[id(e)] for e in sg)
                    final_groups.append((sg, sg_idxs))

    final_groups.sort(key=lambda x: -len(x[0]))

    clusters = []
    cid = 1
    for ev, idx_set in final_groups:
        gears = [e['bucket_a']['gear'] for e in ev]
        rpms  = [e['bucket_a']['rpm_avg'] for e in ev]
        tpss  = [e['bucket_a']['tps_avg'] for e in ev]
        vsss  = [e['bucket_a']['vss_avg'] for e in ev]
        ba_ok = _f7_ba_consistent(ev)
        idxs  = sorted(idx_set)
        scores = [mat[ii][jj] for ii in idxs for jj in idxs if ii < jj]
        ba_summary = {
            'gear':       int(round(sum(gears) / len(gears))),
            'rpm_center': round(sum(rpms) / len(rpms), 0),
            'rpm_range':  round(max(rpms) - min(rpms), 0),
            'tps_center': round(sum(tpss) / len(tpss), 1),
            'tps_range':  round(max(tpss) - min(tpss), 1),
            'vss_center': round(sum(vsss) / len(vsss), 1),
            'vss_range':  round(max(vsss) - min(vsss), 1),
        }
        clusters.append({
            'cluster_id':     f'C{cid:03d}',
            'n':              len(ev),
            'orphan':         len(ev) == 1,
            'bucket_a_ok':    ba_ok,
            'bucket_a':       ba_summary,
            'dtw_min':        round(min(scores), 3) if scores else 1.0,
            'dtw_max':        round(max(scores), 3) if scores else 1.0,
            'has_very_short': any(e['very_short'] for e in ev),
            'members':        ev,
        })
        cid += 1
    return clusters


def _f7_temporal_stats(cluster, n=_F7_N):
    """Compute per-slice PW/VSS stats and confidence for a cluster."""
    members = cluster['members']
    if len(members) < 2:
        cluster['stats'] = None
        return

    import numpy as _np

    def _safe_mat(key):
        rows = [m[key] for m in members if m.get(key)]
        return _np.array(rows) if rows else None

    pw_mat  = _safe_mat('pw_curve')
    pw1_mat = _safe_mat('pw1_curve')
    pw2_mat = _safe_mat('pw2_curve')
    rpm_mat = _safe_mat('rpm_curve')
    vss_mat = _safe_mat('vss_curve')
    tps_mat = _safe_mat('tps_curve')

    if pw_mat is None:
        cluster['stats'] = None
        return

    pw_avg  = pw_mat.mean(axis=0).tolist()
    pw_std  = pw_mat.std(axis=0).tolist()
    pw1_avg = pw1_mat.mean(axis=0).tolist() if pw1_mat is not None else pw_avg
    pw2_avg = pw2_mat.mean(axis=0).tolist() if pw2_mat is not None else pw_avg
    pw_diff = [abs(pw1_avg[t] - pw2_avg[t]) for t in range(n)]

    k = len(members)
    confidence = []
    for t in range(n):
        n_f = min(k / 5.0, 1.0)
        s_f = max(0.0, 1.0 - pw_std[t] / 2.0)
        confidence.append(round(n_f * s_f, 2))

    def _safe_pre(key):
        rows2 = [m[key] for m in members if m.get(key)]
        if not rows2:
            return []
        mat2 = _np.array(rows2)
        return [round(v, 3) for v in mat2.mean(axis=0).tolist()]

    cluster['stats'] = {
        'pw_avg':      [round(v, 3) for v in pw_avg],
        'pw_std':      [round(v, 3) for v in pw_std],
        'pw1_avg':     [round(v, 3) for v in pw1_avg],
        'pw2_avg':     [round(v, 3) for v in pw2_avg],
        'pw_diff_avg': [round(v, 3) for v in pw_diff],
        'pw_diff_max': round(max(pw_diff), 3),
        'confidence':  confidence,
        'rpm_avg':     [round(v, 1) for v in rpm_mat.mean(axis=0).tolist()] if rpm_mat is not None else [],
        'vss_avg':     [round(v, 2) for v in vss_mat.mean(axis=0).tolist()] if vss_mat is not None else [],
        'tps_avg':     [round(v, 2) for v in tps_mat.mean(axis=0).tolist()] if tps_mat is not None else [],
        'pre_pw_avg':  _safe_pre('pre_pw_curve'),
        'pre_rpm_avg': _safe_pre('pre_rpm_curve'),
        'pre_vss_avg': _safe_pre('pre_vss_curve'),
        'pre_tps_avg': _safe_pre('pre_tps_curve'),
    }


def _f7_match_cross_session(clusters_a, clusters_b, threshold=0.85):
    """Match FASE7 accel clusters across sessions using TPS-curve DTW.

    Within-session clustering uses PW DTW (same map = deterministic PW).
    Cross-session matching uses TPS DTW: rider gesture is the common input;
    PW differs because the map changed and that difference is the signal.
    """
    matches = []
    for ca in clusters_a:
        if ca.get('orphan') or ca.get('cluster_type') != 'accel':
            continue
        sa = ca.get('stats') or {}
        if not sa.get('pw_avg'):
            continue
        for cb in clusters_b:
            if cb.get('orphan') or cb.get('cluster_type') != 'accel':
                continue
            sb = cb.get('stats') or {}
            if not sb.get('pw_avg'):
                continue

            # Bucket A compatibility
            ba_a, ba_b = ca['bucket_a'], cb['bucket_a']
            if ba_a['gear'] != ba_b['gear']:
                continue
            if abs(ba_a['rpm_center'] - ba_b['rpm_center']) > 300:
                continue
            if abs(ba_a['tps_center'] - ba_b['tps_center']) > 5:
                continue
            if abs(ba_a['vss_center'] - ba_b['vss_center']) > 15:
                continue

            # Average tps_curve_norm across members (falls back to raw tps_curve)
            def _avg_norm(cluster):
                curves = [m.get('tps_curve_norm') or m.get('tps_curve', [])
                          for m in cluster['members']]
                curves = [c for c in curves if c]
                if not curves:
                    return []
                n = len(curves[0])
                return [sum(c[i] for c in curves) / len(curves) for i in range(n)]

            tps_a = _avg_norm(ca)
            tps_b = _avg_norm(cb)
            if not tps_a or not tps_b:
                continue

            def _norm01(v):
                mx = max(v) if max(v) > 0 else 1.0
                return [x / mx for x in v]

            tps_sim = _f7_dtw(_norm01(tps_a), _norm01(tps_b))
            if tps_sim < threshold:
                continue

            pw_a    = sa['pw_avg']
            pw_b    = sb['pw_avg']
            vss_a   = sa.get('vss_avg', [])
            vss_b   = sb.get('vss_avg', [])
            conf_a  = sa.get('confidence', [])
            conf_b  = sb.get('confidence', [])
            pd_a    = sa.get('pw_diff_avg', [])
            pd_b    = sb.get('pw_diff_avg', [])

            n = min(len(pw_a), len(pw_b))
            if n == 0:
                continue

            delta_pw  = [round(pw_b[i] - pw_a[i], 3) for i in range(n)]
            delta_vss = [round(vss_b[i] - vss_a[i], 2)
                         for i in range(min(n, len(vss_a), len(vss_b)))]
            if not delta_vss:
                delta_vss = [0.0] * n
            conf_match = [round(min(conf_a[i] if i < len(conf_a) else 0,
                                    conf_b[i] if i < len(conf_b) else 0), 2)
                          for i in range(n)]

            sum_pw_a   = sum(pw_a[:n]) or 1e-6
            efficiency = round(sum(delta_vss) / sum_pw_a, 4)

            nb = min(len(pd_a), len(pd_b))
            balance_shift = round(
                sum(pd_b[:nb]) / nb - sum(pd_a[:nb]) / nb, 3
            ) if nb > 0 else 0.0

            avg_conf   = sum(conf_match) / len(conf_match) if conf_match else 0
            sort_score = round(avg_conf * tps_sim * min(ca['n'], cb['n']), 4)

            matches.append({
                'cluster_a_id':     ca['cluster_id'],
                'cluster_b_id':     cb['cluster_id'],
                'n_a':              ca['n'],
                'n_b':              cb['n'],
                'tps_dtw':          round(tps_sim, 3),
                'bucket_a':         ba_a,
                'bucket_b':         ba_b,
                'delta_pw':         delta_pw,
                'delta_vss':        delta_vss,
                'conf_match':       conf_match,
                'efficiency_delta': efficiency,
                'balance_shift':    balance_shift,
                'pw_diff_max_a':    sa.get('pw_diff_max', 0),
                'pw_diff_max_b':    sb.get('pw_diff_max', 0),
                'sort_score':       sort_score,
            })

    matches.sort(key=lambda m: -m['sort_score'])
    return matches


def _f7_load_session_clusters(buell_dir, session_id, threshold=_F7_THRESH):
    """
    Load or compute clusters for a session.
    Per-ride events are cached as ride_*_f7events.json.
    Session clusters cached as session_f7clusters.json.
    Recomputed when any events file is newer than the cluster cache.
    """
    import csv as _csv
    buell_dir = Path(buell_dir)
    sdir      = buell_dir / 'sessions' / session_id

    def _sf(v, default=0.0):
        try:
            return float(v)
        except Exception:
            return default

    def _load_csv_rows(csv_path):
        rows = []
        with open(csv_path) as f:
            lines = [l for l in f if not l.startswith('#')]
        for r in _csv.DictReader(lines):
            try:
                rpm = _sf(r['RPM'])
                if rpm < 100:
                    continue
                rows.append({
                    't':      _sf(r['time_elapsed_s']),
                    'rpm':    rpm,
                    'tps':    _sf(r.get('TPS_pct') or r.get('TPD', 0)),
                    'spd':    _sf(r.get('VS_KPH', 0)),
                    'pw1':    _sf(r['pw1']),
                    'pw2':    _sf(r.get('pw2', 0)),
                    'gear':   _sf(r.get('Gear', 0)),
                    'clt':    _sf(r['CLT']),
                    'ae':     _sf(r.get('Accel_Corr', 100)),
                    'baro':      _sf(r.get('baro_hPa', 0)),
                    'temp_amb':  _sf(r.get('baro_temp_c', 0)),
                    'gps_alt':   _sf(r.get('gps_alt_m', 0)),
                    'gps_valid': r.get('gps_valid', '').strip() == 'TRUE',
                    'fl_fc':  r.get('fl_fuel_cut', '0').strip() in ('1', 'True', 'true'),
                    'fl_eng': r.get('fl_engine_run', '1').strip() in ('1', 'True', 'true'),
                })
            except Exception:
                continue
        return rows

    # --- Step 1: detect events per ride (incremental cache) ---
    csv_files   = sorted(sdir.glob('ride_*.csv'))
    event_files = []
    for cp in csv_files:
        ef = cp.with_name(cp.stem + '_f7events.json')
        _regen = not ef.exists() or ef.stat().st_mtime < cp.stat().st_mtime
        if not _regen:
            try:
                _s = json.loads(ef.read_text())
                if not _s or 'pre_pw_curve' not in _s[0]:
                    _regen = True
            except Exception:
                _regen = True
        if _regen:
            rows = _load_csv_rows(cp)
            evs  = _f7_detect_events(rows)
            # strip pw_curve arrays to save space (will re-compute from pw1/pw2)
            ef.write_text(json.dumps(evs, separators=(',', ':')))
        event_files.append(ef)

    # --- Step 2: check cluster cache staleness ---
    thr_tag = str(threshold).replace('.', '_')
    cluster_file = sdir / f'session_f7clusters_{thr_tag}.json'
    stale = (
        not cluster_file.exists() or
        any(ef.stat().st_mtime > cluster_file.stat().st_mtime for ef in event_files)
    )

    if not stale:
        cached = json.loads(cluster_file.read_text())
        if cached.get('threshold') == threshold and cached.get('events_v') == _F7_EVENTS_V:
            return cached
        stale = True

    # --- Step 3: pool all events and cluster ---
    all_events = []
    for ef in event_files:
        try:
            evs = json.loads(ef.read_text())
            for e in evs:
                e['ride_file'] = ef.stem.replace('_f7events', '')
            all_events.extend(evs)
        except Exception:
            continue

    # Cluster accel and decel separately so type-mixed DTW is avoided
    _accel_evs = [e for e in all_events if e.get('event_type', 'accel') == 'accel']
    _decel_evs = [e for e in all_events if e.get('event_type') == 'decel']
    _accel_cls = _f7_cluster(_accel_evs, threshold=threshold)
    _decel_cls = _f7_cluster(_decel_evs, threshold=threshold)
    for i, c in enumerate(_accel_cls):
        c['cluster_id']   = f'A{i+1:03d}'
        c['cluster_type'] = 'accel'
    for i, c in enumerate(_decel_cls):
        c['cluster_id']   = f'D{i+1:03d}'
        c['cluster_type'] = 'decel'
    clusters = _accel_cls + _decel_cls
    for c in clusters:
        _f7_temporal_stats(c)

    result = {
        'session_id':  session_id,
        'events_v':    _F7_EVENTS_V,
        'n_events':    len(all_events),
        'n_accel':     len(_accel_evs),
        'n_decel':     len(_decel_evs),
        'n_clusters':  len(clusters),
        'n_rides':     len(event_files),
        'threshold':   threshold,
        'clusters':    clusters,
    }
    cluster_file.write_text(json.dumps(result, separators=(',', ':')))
    return result


# ── end FASE7 ────────────────────────────────────────────────────────────────

def detect_launches(rows, pre_window=3.0, post_window=5.0, min_dtps=8.0, min_rpm=1500):
    """Detect WOT tip-in events from CSV rows.

    Changes vs previous:
    - min_dtps lowered 15.0->8.0 to capture smoother throttle openings
    - gear taken from pre-window mode, not the exact launch sample
    - discards event if gear=0 or gear changed during pre-window
    - adds environmental metadata: pre_clt, pre_alt_m, pre_baro_hpa
    - adds gear_stable flag
    """
    if len(rows) < 30:
        return []
    launches = []

    def _std(vals):
        n = len(vals)
        if n < 2: return 0.0
        m = sum(vals) / n
        return (sum((x - m) ** 2 for x in vals) / n) ** 0.5

    def _mode_gear(samples):
        counts = {}
        for r in samples:
            g = int(r.get('gear', 0))
            if g > 0:
                counts[g] = counts.get(g, 0) + 1
        return max(counts, key=counts.get) if counts else 0

    i = 1
    while i < len(rows):
        dtps = rows[i]['tps'] - rows[i-1]['tps']
        if dtps > min_dtps and rows[i]['rpm'] > min_rpm:
            t0 = rows[i]['t']
            pre = [r for r in rows if t0 - pre_window <= r['t'] <= t0 - 0.05]
            if len(pre) < 10:
                i += 1; continue

            tail = pre[-min(20, len(pre)):]

            # Gear: use mode of pre-window, not the exact launch sample
            gear = _mode_gear(tail)
            if gear == 0:
                i += 1; continue

            # Gear stability: discard if gear changed during pre-window
            gear_vals = [int(r.get('gear', 0)) for r in tail if int(r.get('gear', 0)) > 0]
            gear_stable = bool(gear_vals) and all(g == gear for g in gear_vals)
            if not gear_stable:
                i += 1; continue

            rs = _std([r['rpm'] for r in tail])
            ts = _std([r['tps'] for r in tail])
            ss = _std([r['spd'] for r in tail])

            if ts < 5:
                lt = 'A'
            elif ts < 20 and rs < 500 and ss < 15:
                lt = 'B'
            else:
                i += 1; continue

            # Environmental metadata averaged over pre-window
            clt_vals  = [r['clt']      for r in tail if r.get('clt')]
            alt_vals  = [r['alt']      for r in tail if r.get('alt') is not None]
            baro_vals = [r['baro_hpa'] for r in tail if r.get('baro_hpa')]
            pre_clt  = round(sum(clt_vals)  / len(clt_vals),  1) if clt_vals  else None
            pre_alt  = round(sum(alt_vals)  / len(alt_vals),  1) if alt_vals  else None
            pre_baro = round(sum(baro_vals) / len(baro_vals), 1) if baro_vals else None

            # Time series around the event
            t_start, t_end = t0 - pre_window, t0 + post_window
            series = []; last_t = -999
            for r in rows:
                if r['t'] < t_start: continue
                if r['t'] > t_end:   break
                if r['t'] - last_t >= 0.18:
                    series.append({
                        'dt':  round(r['t'] - t0, 2),
                        'rpm': round(r['rpm'], 0),
                        'tps': round(r['tps'], 1),
                        'spd': round(r['spd'], 1),
                        'pw1': round(r['pw1'], 3),
                        'pw2': round(r.get('pw2') or r['pw1'], 3),
                        'ae':  round(r.get('ae', 100), 1),
                        'alt': round(r['alt'], 1) if r.get('alt') is not None else None,
                    })
                    last_t = r['t']

            post = [r for r in rows if t0 <= r['t'] <= t_end]
            launch = {
                'type':         lt,
                't':            round(t0, 1),
                'gear':         gear,
                'gear_stable':  gear_stable,
                'dtps_raw':     round(dtps, 1),
                'pre_rpm':      round(sum(r['rpm'] for r in tail) / len(tail), 0),
                'pre_spd':      round(sum(r['spd'] for r in tail) / len(tail), 1),
                'pre_tps':      round(sum(r['tps'] for r in tail) / len(tail), 1),
                'pre_rpm_std':  round(rs, 0),
                'pre_tps_std':  round(ts, 1),
                'pre_spd_std':  round(ss, 1),
                'pre_clt':      pre_clt,
                'pre_alt_m':    pre_alt,
                'pre_baro_hpa': pre_baro,
                'series':       series,
            }
            if post:
                launch['peak_rpm'] = round(max(r['rpm'] for r in post), 0)
                launch['peak_spd'] = round(max(r['spd'] for r in post), 1)
                launch['peak_pw']  = round(max((r['pw1']+(r.get('pw2') or r['pw1']))/2 for r in post), 3)
                launch['peak_ae']  = round(max(r.get('ae', 100) for r in post), 1)
                launch['rpm_gain'] = round(post[-1]['rpm'] - tail[-1]['rpm'], 0)
                launch['spd_gain'] = round(post[-1]['spd'] - tail[-1]['spd'], 1)
            launches.append(launch)

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

def cluster_launches(launches, rpm_tol=250, tps_tol=2.5):
    # IMPORTANT: clustering uses pre-launch conditions only (rpm, tps, gear, spd).
    # Outcome metrics (rpm_gain, spd_gain, peak_pw, mean_series) are intentionally
    # excluded to avoid bias — we group by initial conditions, then compare results.
    if not launches:
        return []

    def _assign(launches, clusters, rpm_tol, tps_tol):
        assignments = []
        for l in launches:
            gear = l.get("gear", 0)
            rpm  = l.get("pre_rpm", 0)
            tps  = l.get("pre_tps", 0)
            best_idx  = -1
            best_dist = float("inf")
            for i, c in enumerate(clusters):
                if c["gear"] != gear: continue
                dr   = abs(c["mean_rpm"] - rpm) / rpm_tol
                dt   = abs(c["mean_tps"] - tps) / max(tps_tol, 0.1)
                dist = (dr**2 + dt**2) ** 0.5
                if dist < 1.0 and dist < best_dist:
                    best_dist = dist
                    best_idx  = i
            assignments.append(best_idx)
        return assignments

    clusters = []
    for l in launches:
        gear = l.get("gear", 0)
        rpm  = l.get("pre_rpm", 0)
        tps  = l.get("pre_tps", 0)
        spd  = l.get("pre_spd", 0)
        best_idx  = -1
        best_dist = float("inf")
        for i, c in enumerate(clusters):
            if c["gear"] != gear: continue
            dr   = abs(c["mean_rpm"] - rpm) / rpm_tol
            dt   = abs(c["mean_tps"] - tps) / max(tps_tol, 0.1)
            dist = (dr**2 + dt**2) ** 0.5
            if dist < 1.0 and dist < best_dist:
                best_dist = dist
                best_idx  = i
        if best_idx >= 0:
            clusters[best_idx]["_items"].append(l)
        else:
            clusters.append({"gear":gear,"mean_rpm":rpm,"mean_tps":tps,"mean_spd":spd,"_items":[l]})
    for c in clusters:
        items = c["_items"]
        c["mean_rpm"] = sum(x.get("pre_rpm",0) for x in items)/len(items)
        c["mean_tps"] = sum(x.get("pre_tps",0) for x in items)/len(items)
        c["mean_spd"] = sum(x.get("pre_spd",0) for x in items)/len(items)
    assignments = _assign(launches, clusters, rpm_tol, tps_tol)
    for c in clusters: c["_items"] = []
    for l, idx in zip(launches, assignments):
        if idx >= 0: clusters[idx]["_items"].append(l)
        else: clusters.append({"gear":l.get("gear",0),"mean_rpm":l.get("pre_rpm",0),"mean_tps":l.get("pre_tps",0),"mean_spd":l.get("pre_spd",0),"_items":[l]})
    clusters = [c for c in clusters if c["_items"]]
    for c in clusters:
        ll = c["_items"]; n = len(ll)
        c["count"]    = n
        c["mean_rpm"] = sum(x.get("pre_rpm",0) for x in ll)/n
        c["mean_spd"] = sum(x.get("pre_spd",0) for x in ll)/n
        c["mean_tps"] = sum(x.get("pre_tps",0) for x in ll)/n
        c["rpm_std"]  = _s_std([x.get("pre_rpm",0) for x in ll])
        c["spd_std"]  = _s_std([x.get("pre_spd",0) for x in ll])
        c["tps_std"]  = _s_std([x.get("pre_tps",0) for x in ll])
        clt_v  = [x["pre_clt"]      for x in ll if x.get("pre_clt")      is not None]
        alt_v  = [x["pre_alt_m"]    for x in ll if x.get("pre_alt_m")    is not None]
        baro_v = [x["pre_baro_hpa"] for x in ll if x.get("pre_baro_hpa") is not None]
        c["pre_clt_mean"]  = round(sum(clt_v) /len(clt_v), 1)  if clt_v  else None
        c["pre_alt_mean"]  = round(sum(alt_v) /len(alt_v), 1)  if alt_v  else None
        c["pre_baro_mean"] = round(sum(baro_v)/len(baro_v),1) if baro_v else None
        for key,src in [("peak_pw","peak_pw"),("peak_ae","peak_ae"),("rpm_gain","rpm_gain"),("spd_gain","spd_gain"),("dtps","dtps_raw")]:
            vals = [x.get(src,0) for x in ll]
            c[key+"_mean"] = round(sum(vals)/len(vals),3)
            c[key+"_std"]  = round(_s_std(vals),3)
        dt_min = min((x.get("series",[{}])[0].get("dt",0)  for x in ll if x.get("series")),default=0)
        dt_max = max((x.get("series",[{}])[-1].get("dt",0) for x in ll if x.get("series")),default=0)
        tpts=[]; t=dt_min
        while t<=dt_max+0.01: tpts.append(round(t,2)); t+=0.25
        if len(tpts)>1:
            all_c={k:[] for k in ("rpm","tps","spd","pw1","ae","alt")}
            for x in ll:
                pts=x.get("series",[])
                for k in all_c:
                    curve=[]
                    for tp in tpts:
                        best,bd=None,999
                        for p in pts:
                            d=abs(p["dt"]-tp)
                            if d<bd: bd,best=d,p
                        curve.append(best.get(k) if best and bd<0.15 else None)
                    all_c[k].append(curve)
            ms,ss=[],[]
            for idx in range(len(tpts)):
                rm,rs={"dt":tpts[idx]},{"dt":tpts[idx]}
                for k in ("rpm","tps","spd"):
                    vals=[all_c[k][ci][idx] for ci in range(n) if all_c[k][ci][idx] is not None]
                    rm[k]=round(sum(vals)/len(vals),1) if vals else None
                    rs[k]=round(_s_std(vals),1) if len(vals)>1 else 0.0
                pw_v=[all_c["pw1"][ci][idx] for ci in range(n) if all_c["pw1"][ci][idx] is not None]
                rm["pw"]=round(sum(pw_v)/len(pw_v),3) if pw_v else None
                ae_v=[all_c["ae"][ci][idx]  for ci in range(n) if all_c["ae"][ci][idx]  is not None]
                rm["ae"]=round(sum(ae_v)/len(ae_v),1) if ae_v else None
                alt_v=[all_c["alt"][ci][idx] for ci in range(n) if all_c["alt"][ci][idx] is not None]
                rm["alt"]=round(sum(alt_v)/len(alt_v),1) if alt_v else None
                rs["alt"]=round(_s_std(alt_v),1) if len(alt_v)>1 else 0.0
                ms.append(rm); ss.append(rs)
            c["mean_series"]=ms; c["std_series"]=ss
        else:
            c["mean_series"]=[]; c["std_series"]=[]
        del c["_items"]
    clusters.sort(key=lambda c:(c["gear"] if c["gear"] else 99,-c["count"]))
    for i,c in enumerate(clusters): c["id"]=i
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
            d = (dr**2 + ds**2 + dt**2) ** 0.5  # Euclidean, same geometry as cluster_launches
            if d < best_d:
                best_d = d
                best_b = j
        if best_b is not None and best_d < 1.5:
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

    # Same-map detection
    ep_a = Path(buell_dir) / 'sessions' / sa / 'eeprom.bin'
    ep_b = Path(buell_dir) / 'sessions' / sb / 'eeprom.bin'
    result['same_map'] = (ep_a.exists() and ep_b.exists() and ep_a.read_bytes() == ep_b.read_bytes())

    # FASE7 cross-session matching
    try:
        _f7a = _f7_load_session_clusters(buell_dir, sa)
        _f7b = _f7_load_session_clusters(buell_dir, sb)
        _f7m = _f7_match_cross_session(_f7a.get('clusters',[]), _f7b.get('clusters',[]))
        result['f7_session_a'] = _f7a
        result['f7_session_b'] = _f7b
        result['f7_matches']   = _f7m
        result['f7_n_matches'] = len(_f7m)
    except Exception as _e:
        import logging as _lg
        _lg.warning(f'FASE7 cross-session: {_e}')
        result['f7_matches']   = []
        result['f7_n_matches'] = 0
        result['f7_error']     = str(_e)
    