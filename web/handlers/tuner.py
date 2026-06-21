# DEV NOTE: All code, comments, and variable names must be in English.
import json
import logging
import urllib.parse
from pathlib import Path

from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.eeprom import decode_eeprom_maps_full as _decode_eeprom_maps_full
from web.utils import _get_version, _session_version
from web.vs_engine import _merge_maps

_TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


class TunerHandlerMixin:
    def _handle_tuner(self, path=None):
        try:
            html = (_TEMPLATES / 'tuner.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_tuner_sessions(self, path=None):
        sessions = []
        for d in self.server_instance.buell_dir.glob('sessions/*/session_metadata.json'):
            try:
                with open(d) as mf:
                    meta = json.load(mf)
                ep = d.parent / 'eeprom.bin'
                serial = None
                if ep.exists() and ep.stat().st_size >= 1206:
                    try:
                        b = ep.read_bytes()
                        if len(b) >= 14:
                            serial = int.from_bytes(b[12:14], 'little')
                    except Exception as e:
                        logging.debug(f"ignored: {e}")
                else:
                    continue
                sessions.append({
                    'id': d.parent.name,
                    'version': meta.get('version_string', '?'),
                    'rides': meta.get('total_rides', 0),
                    'samples': meta.get('total_samples', 0),
                    'created': meta.get('created_utc', '')[:10],
                    'serial': serial,
                })
            except Exception as e:
                logging.debug(f"ignored: {e}")
        sessions.sort(key=lambda s: s['created'], reverse=True)
        self._json({'sessions': sessions})

    def _handle_tuner_maps(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sess = params.get('session', [''])[0]
        if not sess:
            self._json({'error': 'missing session'}, 400)
            return
        blob_path = self.server_instance.buell_dir / 'sessions' / sess / 'eeprom.bin'
        if not blob_path.exists():
            self._json({'error': 'eeprom.bin not found'}, 404)
            return
        try:
            self._json(_decode_eeprom_maps_full(blob_path.read_bytes(), _session_version(blob_path)))
        except Exception as e:
            self._json({'error': f'map read failed: {e}'})

    def _handle_tuner_maps_file(self, path=None):
        """Load and decode maps from an arbitrary .xpr or .bin file on the Pi filesystem."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        file_path = params.get('path', [''])[0]
        version = params.get('version', [''])[0] or None

        buell_dir = str(self.server_instance.buell_dir)
        allowed = ('/tmp/', buell_dir + '/', '/home/pi/')
        if not any(file_path.startswith(a) for a in allowed):
            self._json({'error': 'path not in allowed directories'}, 403)
            return

        fp = Path(file_path)
        if not fp.exists():
            self._json({'error': 'file not found: ' + file_path}, 404)
            return

        if version is None:
            stem = fp.stem.upper()
            for candidate in ('BUE3D', 'BUE2D', 'BUE1D', 'BUEZD', 'BUEYD', 'BUEWD', 'BUEOD',
                              'BUEIB', 'B2RIB', 'BUEGB', 'BUECB', 'BUEGC', 'BUEKA', 'BUEIA'):
                if candidate in stem:
                    version = candidate
                    break
            if version is None:
                version = 'BUEIB'

        try:
            blob = fp.read_bytes()
            result = _decode_eeprom_maps_full(blob, version)
            if result is None:
                self._json({'error': 'decode failed for version ' + version}, 500)
                return
            result['_source'] = {'path': file_path, 'version': version, 'size': len(blob)}
            self._json(result)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_tuner_merge(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sa = params.get('a', [''])[0]
        sb = params.get('b', [''])[0]
        mode = params.get('mode', ['BALANCE'])[0]
        if not sa or not sb:
            self._json({'error': 'missing session params'}, 400)
            return
        try:
            self._json(_merge_maps(self.server_instance.buell_dir, sa, sb, mode))
        except Exception as e:
            self._json({'error': str(e)}, 500)
