# DEV NOTE: All code, comments, and variable names must be in English.
import json
import logging
import subprocess
import time
from pathlib import Path


class SystemHandlerMixin:
    def _handle_post_shutdown(self, path, payload):
        self.server_instance.pending_shutdown = True
        self._json({'ok': True, 'msg': 'Shutting down...'})

    def _handle_post_keepalive(self, path, payload):
        now = time.time()
        if now - self.server_instance.last_keepalive >= 10:
            self.server_instance.last_keepalive = now
        self._json({'ok': True})

    def _handle_post_git_pull(self, path, payload):
        buell = str(self.server_instance.buell_dir)
        result = subprocess.run(
            ['git', 'pull'],
            capture_output=True, text=True,
            cwd=buell
        )
        output = result.stdout.strip() + result.stderr.strip()
        ok = result.returncode == 0
        if ok:
            if 'Already up to date' not in output and 'up-to-date' not in output:
                subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
            else:
                output = 'Already up to date'
        self._json({'ok': ok, 'output': output})

    def _handle_post_close_ride(self, path, payload):
        if not getattr(self.server_instance, 'ride_active', False):
            self._json({'ok': False, 'msg': 'No active ride'})
            return
        checksum = getattr(self.server_instance.session, 'current_checksum', None)
        ride_num = getattr(self.server_instance.session, 'current_ride_num', 0)
        ipc_dir  = getattr(self.server_instance, '_ipc_dir', Path('/tmp/buell'))
        try:
            (ipc_dir / 'control.json').write_text(
                json.dumps({'cmd': 'close_ride', 'reason': 'dashboard_request'}))
        except Exception as e:
            self._json({'error': 'IPC write failed: ' + str(e)})
            return
        with self.server_instance._rides_cache_lock:
            self.server_instance._rides_cache = None
            self.server_instance._rides_cache_time = 0
        self._json({'ok': True, 'msg': 'Ride close requested',
                    'session': checksum, 'ride_num': ride_num})

    def _handle_post_restart_logger(self, path, payload):
        subprocess.Popen(['sudo', 'systemctl', 'restart', 'buell-logger'])
        self._json({'ok': True, 'msg': 'Restarting logger...'})

    def _handle_post_reboot_pi(self, path, payload):
        subprocess.Popen(['sudo', '/usr/sbin/reboot'])
        self._json({'ok': True, 'msg': 'Rebooting Pi...'})

    def _handle_post_tailscale(self, path, payload):
        action = payload.get("action", "status")
        import subprocess
        valid = {"start", "stop", "status"}
        if action not in valid:
            self._json({"ok": False, "error": f"Invalid action: {action}"})
            return
        try:
            if action == "status":
                r = subprocess.run(["systemctl", "is-active", "tailscaled"], capture_output=True, text=True, timeout=10)
                active = r.stdout.strip() == "active"
                ip = ""
                if active:
                    ip_r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=10)
                    ip = ip_r.stdout.strip()
                self._json({"ok": True, "active": active, "ip": ip})
            else:
                subprocess.run(["sudo", "systemctl", action, "tailscaled"], capture_output=True, timeout=30)
                r = subprocess.run(["systemctl", "is-active", "tailscaled"], capture_output=True, text=True, timeout=10)
                active = r.stdout.strip() == "active"
                self._json({"ok": True, "active": active})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

