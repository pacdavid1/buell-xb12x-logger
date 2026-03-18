"""
NetworkManager - Gestión de WiFi/Hotspot via nmcli
Extraído y limpiado desde ddfi2_logger.py
"""

import subprocess
import threading
import time
import socket
import logging
from pathlib import Path


class NetworkManager:
    """Gestiona WiFi cliente y Hotspot AP usando NetworkManager (nmcli)."""
    
    HOTSPOT_CON = "buell-hotspot"
    WIFI_TIMEOUT_S = 60
    DEFAULT_SSID_PREFIX = "buell"
    DEFAULT_PASSWORD = "buell2024"
    
    def __init__(self):
        self.logger = logging.getLogger("NetworkManager")
        self._monitor_thread = None
        self._monitor_active = False
    
    # ─────────────────────────────────────────────────────────────────
    # Utilidades nmcli
    # ─────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _run(cmd, timeout=10):
        """Ejecuta comando nmcli, retorna (ok, stdout)."""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)
    
    # ─────────────────────────────────────────────────────────────────
    # Estado actual
    # ─────────────────────────────────────────────────────────────────
    
    def _wifi_connected(self):
        """True si wlan0 está conectado a una red WiFi (no hotspot)."""
        ok, out = self._run([
            "nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", 
            "dev", "status"
        ])
        if not ok:
            return False
        
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 4:
                device, dev_type, state, connection = parts[0], parts[1], parts[2], parts[3]
                if device == "wlan0" and "wifi" in dev_type and state == "connected":
                    if connection != self.HOTSPOT_CON:
                        return True
        return False
    
    def _hotspot_active(self):
        """True si el perfil hotspot está activo."""
        ok, out = self._run([
            "nmcli", "-t", "-f", "NAME,STATE", 
            "con", "show", "--active"
        ])
        return ok and self.HOTSPOT_CON in out
    
    def current_mode(self):
        """Retorna 'wifi', 'hotspot' o 'none'."""
        if self._wifi_connected():
            return "wifi"
        if self._hotspot_active():
            return "hotspot"
        return "none"
    
    def get_ip(self):
        """Retorna IP actual de wlan0."""
        ok, out = self._run([
            "nmcli", "-t", "-f", "IP4.ADDRESS", 
            "dev", "show", "wlan0"
        ])
        if ok and out:
            # Formato: IP/24
            ip = out.split("/")[0] if "/" in out else out
            return ip
        return "10.42.0.1"  # fallback hotspot
    
    # ─────────────────────────────────────────────────────────────────
    # Gestión de perfiles
    # ─────────────────────────────────────────────────────────────────
    
    def ensure_hotspot_profile(self):
        """Crea el perfil hotspot si no existe."""
        ok, _ = self._run(["nmcli", "con", "show", self.HOTSPOT_CON])
        if ok:
            self.logger.debug("Perfil hotspot ya existe")
            return True
        
        # Generar SSID único basado en hostname
        hostname = socket.gethostname()
        suffix = hostname[-4:] if len(hostname) >= 4 else "0000"
        ssid = f"{self.DEFAULT_SSID_PREFIX}-{suffix}"
        
        self.logger.info(f"Creando perfil hotspot: SSID={ssid}")
        
        # Crear conexión tipo WiFi AP
        ok, out = self._run([
            "sudo", "nmcli", "con", "add", "type", "wifi",
            "ifname", "wlan0", "mode", "ap",
            "con-name", self.HOTSPOT_CON,
            "ssid", ssid,
            "password", self.DEFAULT_PASSWORD
        ], timeout=20)
        
        if not ok:
            self.logger.error(f"No se pudo crear hotspot: {out}")
            return False
        
        # Configurar banda 2.4GHz y método IP compartido
        self._run([
            "sudo", "nmcli", "con", "modify", self.HOTSPOT_CON,
            "802-11-wireless.band", "bg"
        ])
        self._run([
            "sudo", "nmcli", "con", "modify", self.HOTSPOT_CON,
            "ipv4.method", "shared"
        ])
        
        self.logger.info(f"Hotspot creado: {ssid} / {self.DEFAULT_PASSWORD}")
        return True
    
    # ─────────────────────────────────────────────────────────────────
    # Acciones principales
    # ─────────────────────────────────────────────────────────────────
    
    def setup(self):
        """Configuración inicial al arrancar."""
        self.ensure_hotspot_profile()
        
        # Si ya hay WiFi conectado, mantenerlo
        if self._wifi_connected():
            self.logger.info("WiFi ya conectado - manteniendo")
            return
        
        # Si hotspot ya activo, todo bien
        if self._hotspot_active():
            self.logger.info("Hotspot ya activo")
            return
        
        # Activar hotspot por defecto
        self.logger.info("Activando hotspot...")
        ok, out = self._run([
            "sudo", "nmcli", "con", "up", self.HOTSPOT_CON
        ], timeout=15)
        
        if ok:
            ip = self.get_ip()
            self.logger.info(f"Hotspot activo en {ip}:8080")
        else:
            self.logger.error(f"No se pudo activar hotspot: {out}")
    
    def switch_to_wifi(self, profile_name=None):
        """
        Cambia a modo WiFi cliente.
        Si profile_name=None, intenta conectar al perfil 'casa' o escanea.
        """
        def _do_switch():
            self.logger.info("Cambiando a modo WiFi...")
            
            # Bajar hotspot
            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)
            
            # Intentar conectar
            if profile_name:
                ok, out = self._run([
                    "sudo", "nmcli", "con", "up", profile_name
                ], timeout=35)
            else:
                # Intentar perfil 'casa' o escanear
                ok, out = self._run([
                    "sudo", "nmcli", "con", "up", "casa"
                ], timeout=35)
            
            time.sleep(4)
            
            if self._wifi_connected():
                ip = self.get_ip()
                self.logger.info(f"Conectado a WiFi - IP: {ip}")
            else:
                self.logger.warning("No se conectó - volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
        
        threading.Thread(target=_do_switch, daemon=True).start()
    
    def switch_to_hotspot(self):
        """Vuelve a modo hotspot."""
        def _do_switch():
            self.logger.info("Cambiando a modo hotspot...")
            
            if self._wifi_connected():
                self._run(["sudo", "nmcli", "dev", "disconnect", "wlan0"])
                time.sleep(1)
            
            self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
            self.logger.info("Hotspot activo")
        
        threading.Thread(target=_do_switch, daemon=True).start()
    
    def scan_wifi(self):
        """Escanea redes disponibles."""
        # Forzar rescan
        self._run(["sudo", "nmcli", "dev", "wifi", "rescan"], timeout=8)
        time.sleep(1)
        
        ok, out = self._run([
            "nmcli", "--terse", "--fields", "SSID,SIGNAL,SECURITY",
            "dev", "wifi", "list"
        ], timeout=8)
        
        networks = []
        seen = set()
        
        if ok:
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    ssid = parts[0].strip()
                    signal_str = parts[1].strip()
                    security = parts[2].strip() if len(parts) > 2 else ""
                    
                    if not ssid or ssid in seen:
                        continue
                    if ssid.startswith(self.DEFAULT_SSID_PREFIX):
                        continue  # ignorar otros buell-*
                    
                    seen.add(ssid)
                    try:
                        signal = int(signal_str)
                    except:
                        signal = 0
                    
                    networks.append({
                        "ssid": ssid,
                        "signal": signal,
                        "security": security
                    })
        
        networks.sort(key=lambda x: -x["signal"])
        return networks
    
    def saved_wifi(self):
        """Lista perfiles WiFi guardados."""
        ok, out = self._run([
            "nmcli", "--terse", "--fields", "NAME,TYPE",
            "con", "show"
        ], timeout=8)
        
        saved = []
        if ok:
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and "wifi" in parts[1].lower():
                    name = parts[0].strip()
                    if name == self.HOTSPOT_CON:
                        continue
                    
                    # Obtener SSID real
                    ok2, out2 = self._run([
                        "nmcli", "--terse", "--fields", "802-11-wireless.ssid",
                        "con", "show", name
                    ], timeout=5)
                    
                    ssid = name  # fallback
                    if ok2 and ":" in out2:
                        ssid = out2.split(":")[-1].strip()
                    
                    saved.append({"name": name, "ssid": ssid})
        
        return saved
    
    def connect_to_profile(self, profile_name):
        """Conecta a un perfil guardado."""
        def _do_connect():
            self.logger.info(f"Conectando a: {profile_name}")
            
            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)
            
            ok, out = self._run([
                "sudo", "nmcli", "con", "up", profile_name
            ], timeout=35)
            
            time.sleep(4)
            
            if self._wifi_connected():
                self.logger.info(f"Conectado a {profile_name}")
            else:
                self.logger.warning(f"Falló conexión - volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
        
        threading.Thread(target=_do_connect, daemon=True).start()
    
    def add_and_connect(self, ssid, password):
        """Agrega nueva red y conecta."""
        def _do_add():
            self.logger.info(f"Agregando red: {ssid}")
            
            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)
            
            # Escanear primero
            self._run(["sudo", "nmcli", "dev", "wifi", "rescan"], timeout=8)
            time.sleep(2)
            
            # Conectar (crea perfil automáticamente)
            ok, out = self._run([
                "sudo", "nmcli", "dev", "wifi", "connect", ssid,
                "password", password
            ], timeout=35)
            
            time.sleep(4)
            
            if self._wifi_connected():
                self.logger.info(f"Conectado a {ssid}")
            else:
                self.logger.warning(f"No conectó - volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
        
        threading.Thread(target=_do_add, daemon=True).start()
    
    def forget_wifi(self, profile_name):
        """Elimina un perfil guardado."""
        ok, _ = self._run([
            "sudo", "nmcli", "con", "delete", profile_name
        ], timeout=10)
        return ok
    
    # ─────────────────────────────────────────────────────────────────
    # Monitor de red (opcional)
    # ─────────────────────────────────────────────────────────────────
    
    def start_monitor(self):
        """Inicia thread que vigila la conexión."""
        self._monitor_active = True
        
        def _monitor():
            time.sleep(90)  # esperar arranque
            while self._monitor_active:
                try:
                    if not self._wifi_connected() and not self._hotspot_active():
                        self.logger.warning("Sin red - activando hotspot")
                        self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
                except Exception as e:
                    self.logger.debug(f"Monitor error: {e}")
                time.sleep(30)
        
        self._monitor_thread = threading.Thread(
            target=_monitor, 
            daemon=True, 
            name="net-monitor"
        )
        self._monitor_thread.start()
        self.logger.info("Monitor de red iniciado")
    
    def stop_monitor(self):
        """Detiene el monitor."""
        self._monitor_active = False
    
    def ssh_active(self):
        """True si hay conexiones SSH activas."""
        ok, out = self._run([
            "ss", "-tn", "state", "established", "sport", "=", ":22"
        ])
        if not ok:
            return False
        return any(
            line.strip() and not line.startswith("Recv") 
            for line in out.splitlines()
        )
