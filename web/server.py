"""
WebServer - HTTP server con endpoints para red y status
v2.1.0 - Fix scan GET, redirect URL, switch status polling
"""

import json
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path


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

        self._json({"error": "unknown endpoint"}, 404)

    def _load_html(self):
        template = Path(__file__).parent / 'templates' / 'index.html'
        if template.exists():
            return template.read_text(encoding='utf-8')
        return "<h1>Buell Logger</h1><p>templates/index.html no encontrado</p>"

    def _get_live(self):
        net = self.server_instance.network
        return {
            "ts":              time.time(),
            "logger_version":  "v2.1.0",
            "network_mode":    net.current_mode(),
            "ip":              net.get_ip(),
            "switch_status":   net.get_switch_status(),
            "ride_active":     False,
            "waiting":         True,
            "ride_num":        0,
            "elapsed_s":       0,
            "live":            {},
            "cells":           {},
            "objectives":      [],
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
