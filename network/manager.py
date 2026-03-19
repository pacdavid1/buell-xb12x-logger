"""
NetworkManager - Gestión de WiFi/Hotspot via nmcli
v2.1.0 - Switch con redirect URL + network_state.json
"""

import subprocess
import threading
import time
import socket
import json
import logging
from pathlib import Path

STATE_FILE = Path("/home/pi/buell/network_state.json")

class NetworkManager:

    HOTSPOT_CON      = "buell-hotspot"
    HOTSPOT_IP       = "10.42.0.1"
    WIFI_TIMEOUT_S   = 35
    DEFAULT_PASSWORD = "buell2024"

    def __init__(self):
        self.logger          = logging.getLogger("NetworkManager")
        self._monitor_thread = None
        self._monitor_active = False
        self._switch_status  = {}

    @staticmethod
    def _run(cmd, timeout=10):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip()
        except Exception as e:
            return False, str(e)

    def _wifi_connected(self):
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
        ok, out = self._run([
            "nmcli", "-t", "-f", "NAME,STATE",
            "con", "show", "--active"
        ])
        return ok and self.HOTSPOT_CON in out

    def current_mode(self):
        if self._wifi_connected():
            return "wifi"
        if self._hotspot_active():
            return "hotspot"
        return "none"

    def get_ip(self):
        ok, out = self._run([
            "nmcli", "-t", "-f", "IP4.ADDRESS",
            "dev", "show", "wlan0"
        ])
        if ok and out:
            for line in out.splitlines():
                if "/" in line:
                    ip = line.split(":")[-1].split("/")[0].strip()
                    if ip:
                        return ip
        if self._hotspot_active():
            return self.HOTSPOT_IP
        return "0.0.0.0"

    def get_wifi_ip(self):
        try:
            if STATE_FILE.exists():
                s = json.loads(STATE_FILE.read_text())
                if s.get("last_wifi_ip"):
                    return s["last_wifi_ip"]
        except Exception:
            pass
        return None

    def _save_state(self, mode, ip, extra=None):
        try:
            state = {}
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text())
            state["mode"]            = mode
            state["ip"]              = ip
            state["last_switch_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if mode == "wifi":
                state["last_wifi_ip"] = ip
            if extra:
                state.update(extra)
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            self.logger.warning(f"No se pudo guardar state: {e}")

    def load_state(self):
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
        return {}

    def get_redirect_url(self, target_action, port=8080):
        if target_action == "hotspot":
            return f"http://{self.HOTSPOT_IP}:{port}"
        if target_action == "wifi":
            last_ip = self.get_wifi_ip()
            if last_ip:
                return f"http://{last_ip}:{port}"
            return None
        return None

    def get_switch_status(self):
        return dict(self._switch_status)

    def _set_switch_status(self, stage, ok=None, ip=None, error=None):
        self._switch_status = {
            "stage": stage,
            "ok":    ok,
            "ip":    ip,
            "error": error,
            "ts":    time.time()
        }

    def ensure_hotspot_profile(self):
        ok, _ = self._run(["nmcli", "con", "show", self.HOTSPOT_CON])
        if ok:
            return True

        hostname = socket.gethostname()
        suffix   = hostname[-4:] if len(hostname) >= 4 else "0000"
        ssid     = f"buell-{suffix}"

        self.logger.info(f"Creando perfil hotspot: SSID={ssid}")
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

        self._run(["sudo", "nmcli", "con", "modify", self.HOTSPOT_CON,
                   "802-11-wireless.band", "bg"])
        self._run(["sudo", "nmcli", "con", "modify", self.HOTSPOT_CON,
                   "ipv4.method", "shared"])
        self._run(["sudo", "nmcli", "con", "modify", self.HOTSPOT_CON,
                   "connection.autoconnect-priority", "-1"])
        return True

    def setup(self):
        self.ensure_hotspot_profile()

        if self._wifi_connected():
            ip = self.get_ip()
            self.logger.info(f"WiFi ya conectado — IP: {ip}")
            self._save_state("wifi", ip)
            self.start_monitor()
            return

        if self._hotspot_active():
            self.logger.info("Hotspot ya activo")
            self._save_state("hotspot", self.HOTSPOT_IP)
            self.start_monitor()
            return

        self.logger.info("Activando hotspot por defecto...")
        ok, out = self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON], timeout=15)
        if ok:
            self._save_state("hotspot", self.HOTSPOT_IP)
            self.logger.info(f"Hotspot activo en {self.HOTSPOT_IP}:8080")
        else:
            self.logger.error(f"No se pudo activar hotspot: {out}")

        self.start_monitor()
    def switch_to_wifi(self, profile_name=None):
        def _do():
            self._set_switch_status("switching")
            self.logger.info("Cambiando a modo WiFi...")

            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)

            profiles_to_try = []
            if profile_name:
                profiles_to_try.append(profile_name)
            profiles_to_try.append("casa")
            for s in self.saved_wifi():
                if s["name"] not in profiles_to_try:
                    profiles_to_try.append(s["name"])

            connected = False
            for profile in profiles_to_try:
                self.logger.info(f"Intentando perfil: {profile}")
                self._run(["sudo", "nmcli", "con", "up", profile], timeout=self.WIFI_TIMEOUT_S)
                time.sleep(3)
                if self._wifi_connected():
                    connected = True
                    break

            if connected:
                ip = self.get_ip()
                self._save_state("wifi", ip)
                self._set_switch_status("connected", ok=True, ip=ip)
                self.logger.info(f"WiFi conectado — IP: {ip}")
            else:
                self.logger.warning("No conectó — volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
                self._save_state("hotspot", self.HOTSPOT_IP)
                self._set_switch_status("fallback", ok=False, error="No se pudo conectar al WiFi")

        threading.Thread(target=_do, daemon=True, name="switch-wifi").start()

    def switch_to_hotspot(self):
        def _do():
            self._set_switch_status("switching")
            self.logger.info("Cambiando a modo hotspot...")

            if self._wifi_connected():
                self._run(["sudo", "nmcli", "dev", "disconnect", "wlan0"])
                time.sleep(1)

            ok, out = self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON], timeout=15)

            if ok or self._hotspot_active():
                self._save_state("hotspot", self.HOTSPOT_IP)
                self._set_switch_status("connected", ok=True, ip=self.HOTSPOT_IP)
                self.logger.info("Hotspot activo")
            else:
                self._set_switch_status("failed", ok=False, error=out)
                self.logger.error(f"No se pudo activar hotspot: {out}")

        threading.Thread(target=_do, daemon=True, name="switch-hotspot").start()

    def connect_to_profile(self, profile_name):
        def _do():
            self._set_switch_status("switching")
            self.logger.info(f"Conectando a perfil: {profile_name}")

            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)

            self._run(["sudo", "nmcli", "con", "up", profile_name], timeout=self.WIFI_TIMEOUT_S)
            time.sleep(3)

            if self._wifi_connected():
                ip = self.get_ip()
                self._save_state("wifi", ip)
                self._set_switch_status("connected", ok=True, ip=ip)
                self.logger.info(f"Conectado a {profile_name} — IP: {ip}")
            else:
                self.logger.warning(f"Falló {profile_name} — volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
                self._save_state("hotspot", self.HOTSPOT_IP)
                self._set_switch_status("fallback", ok=False, error=f"No conectó a {profile_name}")

        threading.Thread(target=_do, daemon=True, name="connect-profile").start()

    def add_and_connect(self, ssid, password):
        def _do():
            self._set_switch_status("switching")
            self.logger.info(f"Agregando red: {ssid}")

            if self._hotspot_active():
                self._run(["sudo", "nmcli", "con", "down", self.HOTSPOT_CON])
                time.sleep(2)

            self._run(["sudo", "nmcli", "dev", "wifi", "rescan"], timeout=8)
            time.sleep(2)

            self._run([
                "sudo", "nmcli", "dev", "wifi", "connect", ssid,
                "password", password
            ], timeout=self.WIFI_TIMEOUT_S)
            time.sleep(3)

            if self._wifi_connected():
                ip = self.get_ip()
                self._save_state("wifi", ip)
                self._set_switch_status("connected", ok=True, ip=ip)
                self.logger.info(f"Conectado a {ssid} — IP: {ip}")
            else:
                self.logger.warning(f"No conectó a {ssid} — volviendo a hotspot")
                self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
                self._save_state("hotspot", self.HOTSPOT_IP)
                self._set_switch_status("fallback", ok=False, error=f"No conectó a {ssid}")

        threading.Thread(target=_do, daemon=True, name="add-wifi").start()

    def scan_wifi(self):
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
                if len(parts) < 2:
                    continue
                ssid     = parts[0].strip()
                signal   = parts[1].strip()
                security = parts[2].strip() if len(parts) > 2 else ""
                if not ssid or ssid in seen:
                    continue
                if ssid.startswith("buell-"):
                    continue
                seen.add(ssid)
                try:
                    sig = int(signal)
                except Exception:
                    sig = 0
                networks.append({"ssid": ssid, "signal": sig, "security": security})

        networks.sort(key=lambda x: -x["signal"])
        return networks

    def saved_wifi(self):
        ok, out = self._run([
            "nmcli", "--terse", "--fields", "NAME,TYPE",
            "con", "show"
        ], timeout=8)

        saved = []
        if ok:
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and ("wifi" in parts[1].lower() or "802-11" in parts[1]):
                    name = parts[0].strip()
                    if name == self.HOTSPOT_CON:
                        continue
                    ok2, out2 = self._run([
                        "nmcli", "--terse", "--fields", "802-11-wireless.ssid",
                        "con", "show", name
                    ], timeout=5)
                    ssid = name
                    if ok2 and ":" in out2:
                        ssid = out2.split(":")[-1].strip()
                    saved.append({"name": name, "ssid": ssid})
        return saved

    def forget_wifi(self, profile_name):
        ok, _ = self._run(["sudo", "nmcli", "con", "delete", profile_name], timeout=10)
        return ok

    def start_monitor(self):
        if self._monitor_active:
            return
        self._monitor_active = True

        def _monitor():
            time.sleep(90)
            while self._monitor_active:
                try:
                    if not self._wifi_connected() and not self._hotspot_active():
                        self.logger.warning("Sin red — activando hotspot")
                        self._run(["sudo", "nmcli", "con", "up", self.HOTSPOT_CON])
                        self._save_state("hotspot", self.HOTSPOT_IP)
                except Exception as e:
                    self.logger.debug(f"Monitor error: {e}")
                time.sleep(30)

        self._monitor_thread = threading.Thread(
            target=_monitor, daemon=True, name="net-monitor"
        )
        self._monitor_thread.start()

    def stop_monitor(self):
        self._monitor_active = False

    def ssh_active(self):
        ok, out = self._run(["ss", "-tn", "state", "established", "sport", "=", ":22"])
        if not ok:
            return False
        return any(
            line.strip() and not line.startswith("Recv")
            for line in out.splitlines()
        )
