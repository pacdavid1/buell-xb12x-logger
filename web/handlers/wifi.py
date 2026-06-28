# DEV NOTE: All code, comments, and variable names must be in English.
import urllib.parse


class WifiHandlerMixin:
    def _handle_wifi_saved(self, path=None):
        net = self.server_instance.network
        self._json({'saved': net.saved_wifi()})

    def _handle_wifi_scan(self, path=None):
        net = self.server_instance.network
        self._json({'networks': net.scan_wifi()})

    def _handle_wifi_status(self, path=None):
        net = self.server_instance.network
        self._json({
            'mode': net.current_mode(),
            'ip': net.get_ip(),
            'switch_status': net.get_switch_status(),
            'state': net.load_state(),
        })

    def _handle_wifi_redirect_url(self, path=None):
        net = self.server_instance.network
        action = self.path.split('action=')[-1] if 'action=' in self.path else ''
        self._json({'url': net.get_redirect_url(action), 'action': action})

    def _handle_post_network(self, path, payload):
        net = self.server_instance.network
        action = payload.get('action', '')
        if action == 'wifi':
            net.switch_to_wifi()
        elif action == 'hotspot':
            net.switch_to_hotspot()
        self._json({'ok': True, 'action': action})

    def _handle_post_wifi_connect(self, path, payload):
        net = self.server_instance.network
        profile = payload.get('profile', '')
        if profile:
            net.connect_to_profile(profile)
        self._json({'ok': True})

    def _handle_post_wifi_add(self, path, payload):
        net = self.server_instance.network
        ssid = payload.get('ssid', '')
        password = payload.get('password', '')
        if ssid and password:
            net.add_and_connect(ssid, password)
        self._json({'ok': True})

    def _handle_post_wifi_forget(self, path, payload):
        net = self.server_instance.network
        name = payload.get('name', '')
        self._json({'ok': net.forget_wifi(name) if name else False})
