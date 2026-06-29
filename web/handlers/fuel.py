# DEV NOTE: All code, comments, and variable names must be in English.
import json
from pathlib import Path

from web.utils import _get_version
import web.fuel_tracker as fuel_tracker

_TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


class FuelHandlerMixin:
    def _handle_fuel(self, path=None):
        html = (_TEMPLATES / 'fuel.html').read_text(encoding='utf-8')
        self._html(html.replace('--LOGGER_VERSION--', _get_version()))

    def _handle_fuel_status(self, path=None):
        buell = self.server_instance.buell_dir
        sessions_dir = str(buell / 'sessions')
        self._json(fuel_tracker.get_status(sessions_dir, buell_dir=str(buell)))

    def _handle_fuel_reserve(self, path=None):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            active = bool(body.get('active', True))
        except Exception:
            active = True
        buell = self.server_instance.buell_dir
        sessions_dir = str(buell / 'sessions')
        self._json(fuel_tracker.toggle_reserve(active, sessions_dir, buell_dir=str(buell)))

    def _handle_fuel_refuel(self, path=None):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            liters = float(body.get('liters', 0))
            octane = int(body.get('octane', 91))
            full_tank = bool(body.get('full_tank', False))
        except Exception:
            self._json({'error': 'invalid body'}, 400)
            return
        if liters <= 0:
            self._json({'error': 'liters must be > 0'}, 400)
            return
        buell = self.server_instance.buell_dir
        sessions_dir = str(buell / 'sessions')
        self._json(fuel_tracker.add_refuel(liters, octane, sessions_dir, full_tank, buell_dir=str(buell)))

    def _handle_fuel_consumption(self, path=None):
        buell = self.server_instance.buell_dir
        sessions_dir = str(buell / 'sessions')
        self._json(fuel_tracker.calc_ride_consumption(sessions_dir, buell_dir=str(buell)))
