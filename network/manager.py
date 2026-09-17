"""
NetworkManager - Gestión de WiFi/Hotspot via nmcli
v2.1.0 - Switch con redirect URL + network_state.json
"""

import secrets
import subprocess
import threading
import time
import socket
import json
import logging
from pathlib import Path

# Default fallback path (overridden by buell_dir passed to __init__)
_DEFAULT_BUELL_DIR = Path(__file__).resolve().parent.parent
_STATE_FILE_DEFAULT = _DEFAULT_BUELL_DIR / 'network_state.json'

NETWORK_STATUS_CACHE_TTL_S = 3.0  # see _refresh_status_cache() for why


class NetworkManager:

    HOTSPOT_CON           = "buell-hotspot"
    HOTSPOT_IP            = "10.42.0.1"
    WIFI_TIMEOUT_S        = 35
    HOTSPOT_PASSWORD_FILE = "hotspot_password.txt"

    def __init__(self, buell_dir=None):
        self.logger          = logging.getLogger("NetworkManager")
        self._monitor_thread = None
        self._monitor_active = False
        self._switch_status  = {}
        self._state_lock     = threading.Lock()
        self._buell_dir      = Path(buell_dir) if buell_dir else _DEFAULT_BUELL_DIR
        state_file = Path(buell_dir) / 'network_state.json' if buell_dir else _STATE_FILE_DEFAULT
        self._state_file = state_file
        self._status_cache    = {"mode": "none", "ip": "0.0.0.0"}
        self._status_cache_ts = 0.0

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

    def _resolve_wifi_ip(self):
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
        return None

    def _refresh_status_cache(self):
        """Recompute mode+IP together and cache them.

        current_mode()/get_ip() are the dashboard's hot path -- /live.json
        calls both on every poll (up to 8/s), and each used to shell out to
        nmcli independently (2-3 subprocess spawns per poll on a Pi Zero).
        Network mode/IP don't change that fast, so cache with a short TTL.
        Internal callers (the wifi-switch state machine, the "sin red"
        monitor thread) keep calling _wifi_connected()/_hotspot_active()
        directly, uncached -- those need to observe real transitions, not a
        stale snapshot.
        """
        if self._wifi_connected():
            mode, ip = "wifi", (self._resolve_wifi_ip() or "0.0.0.0")
        elif self._hotspot_active():
            mode, ip = "hotspot", self.HOTSPOT_IP
        else:
            mode, ip = "none", "0.0.0.0"
        self._status_cache = {"mode": mode, "ip": ip}
        self._status_cache_ts = time.monotonic()

    def _get_status_cache(self) -> dict:
        if time.monotonic() - self._status_cache_ts > NETWORK_STATUS_CACHE_TTL_S:
            self._refresh_status_cache()
        return self._status_cache

    def current_mode(self):
        return self._get_status_cache()["mode"]

    def get_ip(self):
        return self._get_status_cache()["ip"]

    def get_wifi_ip(self):
        try:
            sf = self._state_file
            if sf.exists():
                s = json.loads(sf.read_text())
                if s.get("last_wifi_ip"):
                    return s["last_wifi_ip"]
        except Exception as e:
            self.logger.warning(f"get_wifi_ip: {e}")
        return None

    def _save_state(self, mode, ip, extra=None):
        with self._state_lock:
            try:
                state = {}
                sf = self._state_file
                if sf.exists():
                    state = json.loads(sf.read_text())
                state["mode"]            = mode
                state["ip"]              = ip
                state["last_switch_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                if mode == "wifi":
                    state["last_wifi_ip"] = ip
                if extra:
                    state.update(extra)
                sf.write_text(json.dumps(state, indent=2))
            except Exception as e:
                self.logger.warning(f"No se pudo guardar state: {e}")

    def load_state(self):
        try:
            with self._state_lock:
                sf = self._state_file
                if sf.exists():
                    return json.loads(sf.read_text())
        except Exception as e:
            self.logger.warning(f"load_state: {e}")
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

    def _get_hotspot_password(self) -> str:
        """Each install generates and persists its own random hotspot
        password on first use (gitignored) -- a public repo must not ship
        one shared default WiFi password for every fork/install."""
        pw_path = self._buell_dir / self.HOTSPOT_PASSWORD_FILE
        try:
            existing = pw_path.read_text().strip()
            if existing:
                return existing
        except FileNotFoundError:
            pass
        new_password = secrets.token_urlsafe(9)
        try:
            pw_path.write_text(new_password)
        except Exception as e:
            self.logger.warning(f"Could not persist hotspot password: {e}")
        return new_password

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
            "password", self._get_hotspot_password()
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

    def forget_wifi(self, profile_name) -> bool:
        """Delete a saved wifi profile, plus any other profile sharing the
        same SSID -- a netplan-managed connection (name prefixed
        "netplan-wlan0-...") and a plain nmcli one can both exist for the
        same network. Deleting only the clicked profile left the sibling
        behind, so the network reappeared in the saved list even though the
        user asked to remove it (found 2026-09-13 with a leftover
        "Totalplay-31AB" pair after a house move)."""
        saved = self.saved_wifi()
        target_ssid = next((e["ssid"] for e in saved if e["name"] == profile_name), None)
        names_to_delete = (
            [e["name"] for e in saved if e["ssid"] == target_ssid]
            if target_ssid else [profile_name]
        )
        all_ok = True
        for name in names_to_delete:
            ok, _ = self._run(["sudo", "nmcli", "con", "delete", name], timeout=10)
            all_ok = all_ok and ok
        return all_ok

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