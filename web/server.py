"""
WebServer - HTTP server con endpoints para red y status
Versión mínima para prueba de concepto.
"""

import json
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path


class DashboardHandler(BaseHTTPRequestHandler):
    """Handler HTTP - endpoints para red y status."""
    
    # Referencia estática al WebServer (se asigna en start)
    server_instance = None
    
    def log_message(self, format, *args):
        """Silenciar logs de acceso."""
        pass
    
    def _json_response(self, data, code=200):
        """Envía respuesta JSON."""
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    
    def _html_response(self, html, code=200):
        """Envía respuesta HTML."""
        body = html.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def do_GET(self):
        """Maneja GET requests."""
        path = self.path.split('?')[0]  # quitar query string
        
        # Dashboard principal
        if path == '/' or path == '/index.html':
            html = self._load_html()
            self._html_response(html)
            return
        
        # Status en vivo (para el header)
        if path == '/live.json':
            self._json_response(self._get_live_status())
            return
        
        # Redes guardadas
        if path == '/wifi/saved':
            saved = self.server_instance.network.saved_wifi()
            self._json_response({"saved": saved})
            return
        
        # Escaneo de redes (devuelve caché o escanea)
        if path == '/wifi/scan':
            networks = self.server_instance.network.scan_wifi()
            self._json_response({"networks": networks})
            return
        
        # 404
        self._json_response({"error": "not found"}, 404)
    
    def do_POST(self):
        """Maneja POST requests."""
        path = self.path
        
        # Leer body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        
        try:
            payload = json.loads(body)
        except:
            payload = {}
        
        # Cambiar modo red
        if path == '/network':
            action = payload.get('action', '')
            if action == 'wifi':
                self.server_instance.network.switch_to_wifi()
            elif action == 'hotspot':
                self.server_instance.network.switch_to_hotspot()
            self._json_response({"ok": True, "action": action})
            return
        
        # Conectar a perfil guardado
        if path == '/wifi/connect':
            profile = payload.get('profile', '')
            if profile:
                self.server_instance.network.connect_to_profile(profile)
            self._json_response({"ok": True})
            return
        
        # Agregar nueva red
        if path == '/wifi/add':
            ssid = payload.get('ssid', '')
            password = payload.get('password', '')
            if ssid and password:
                self.server_instance.network.add_and_connect(ssid, password)
            self._json_response({"ok": True})
            return
        
        # Olvidar red
        if path == '/wifi/forget':
            name = payload.get('name', '')
            ok = self.server_instance.network.forget_wifi(name) if name else False
            self._json_response({"ok": ok})
            return
        
        # Shutdown
        if path == '/shutdown':
            self.server_instance.pending_shutdown = True
            self._json_response({"ok": True, "msg": "Apagando..."})
            return
        
        # Keepalive (anti-poweroff)
        if path == '/keepalive':
            self.server_instance.last_keepalive = time.time()
            self._json_response({"ok": True})
            return
        
        self._json_response({"error": "unknown endpoint"}, 404)
    
    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _load_html(self):
        """Carga el HTML del template."""
        template_path = Path(__file__).parent / 'templates' / 'index.html'
        
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        
        # HTML mínimo de fallback si no existe archivo
        return self._fallback_html()
    
    def _get_live_status(self):
        """Genera status para live.json."""
        net = self.server_instance.network
        
        return {
            "ts": time.time(),
            "logger_version": "v2.0.0-MODULAR",
            "network_mode": net.current_mode(),
            "ip": net.get_ip(),
            "ride_active": False,  # TODO: conectar con ECU después
            "waiting": True,
            "ride_num": 0,
            "elapsed_s": 0,
            "live": {},  # TODO: datos de ECU después
            "cells": {},
            "objectives": [],
        }
    
    def _fallback_html(self):
        """HTML mínimo si no existe template."""
        return """<!DOCTYPE html>
<html>
<head><title>Buell Logger</title></head>
<body>
<h1>Buell Logger v2.0.0-MODULAR</h1>
<p>Modo: RED+WEB (sin ECU)</p>
<p>El archivo templates/index.html no existe.</p>
</body>
</html>"""


class WebServer:
    """Servidor HTTP para el dashboard."""
    
    def __init__(self, host='0.0.0.0', port=8080, buell_dir=None):
        self.host = host
        self.port = port
        self.buell_dir = Path(buell_dir) if buell_dir else Path('/home/pi/buell')
        self.network = None  # Se asigna desde main
        self._server = None
        self._thread = None
        self.pending_shutdown = False
        self.last_keepalive = time.time()
    
    def start(self):
        """Inicia el servidor en thread separado."""
        DashboardHandler.server_instance = self
        
        self._server = ThreadingHTTPServer((self.host, self.port), DashboardHandler)
        
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="web-server"
        )
        self._thread.start()
        
        # Log
        import logging
        logging.getLogger("WebServer").info(f"HTTP server en http://{self.host}:{self.port}")
    
    def stop(self):
        """Detiene el servidor."""
        if self._server:
            self._server.shutdown()
