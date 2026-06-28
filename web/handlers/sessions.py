# DEV NOTE: All code, comments, and variable names must be in English.
import json
import urllib.parse
from pathlib import Path

from web.utils import _get_version
from web.f7 import _f7_load_session_clusters
from web.vs_engine import _compare_sessions_cached

_TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


class SessionsHandlerMixin:
    def _handle_session_events(self, path=None):
        try:
            html = (_TEMPLATES / 'session_events.html').read_text(encoding='utf-8')
            self._html(html)
        except Exception as e:
            self._html(f'<pre>Error: {e}</pre>', 500)

    def _handle_session_events_data(self, path=None):
        buell_dir = self.server_instance.buell_dir
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = (qs.get('session', [''])[0]).strip().upper()
        threshold = float(qs.get('threshold', ['0.85'])[0])
        if not sid:
            self._json({'error': 'missing session param'}, 400)
            return
        if not (buell_dir / 'sessions' / sid).is_dir():
            self._json({'error': f'session {sid} not found'}, 404)
            return
        try:
            self._json(_f7_load_session_clusters(buell_dir, sid, threshold))
        except Exception as e:
            import traceback
            self._json({'error': str(e), 'trace': traceback.format_exc()}, 500)

    def _handle_session_events_download(self, path=None):
        buell_dir = self.server_instance.buell_dir
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = (qs.get('session', [''])[0]).strip().upper()
        threshold = float(qs.get('threshold', ['0.85'])[0])
        if not sid:
            self._json({'error': 'missing session param'}, 400)
            return
        if not (buell_dir / 'sessions' / sid).is_dir():
            self._json({'error': f'session {sid} not found'}, 404)
            return
        try:
            data = _f7_load_session_clusters(buell_dir, sid, threshold)
            body = json.dumps(data, indent=2).encode('utf-8')
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
        try:
            html = (_TEMPLATES / 'sessions_launch.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_sessions_launch_data(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        a = params.get('a', [''])[0]
        b = params.get('b', [''])[0]
        if not a or not b:
            self._json({'error': 'missing session params'}, 400)
            return
        try:
            data = _compare_sessions_cached(self.server_instance.buell_dir, a, b)
            result = {k: data[k] for k in ('clusters_a', 'clusters_b', 'cluster_matches', 'error') if k in data}
            self._json(result)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_sessions_vs(self, path=None):
        try:
            html = (_TEMPLATES / 'sessions_vs.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_sessions_vs_compare(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get('a', [''])[0]
        sb = params.get('b', [''])[0]
        if not sa or not sb:
            self._json({'error': 'missing session params'}, 400)
            return
        try:
            self._json(_compare_sessions_cached(self.server_instance.buell_dir, sa, sb))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_sessions_vs_download(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get('a', [''])[0]
        sb = params.get('b', [''])[0]
        if not sa or not sb:
            self._json({'error': 'missing session params'}, 400)
            return
        try:
            data = _compare_sessions_cached(self.server_instance.buell_dir, sa, sb)
            body = json.dumps(data, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', f'attachment; filename=sessions_vs_{sa}_{sb}.json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json({'error': str(e)}, 500)
