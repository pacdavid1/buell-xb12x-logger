# DEV NOTE: All code, comments, and variable names must be in English.
import json
import logging
import urllib.parse
from pathlib import Path

from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from web.utils import _get_version
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
            self._json(_decode_eeprom_maps(blob_path.read_bytes()))
        except Exception as e:
            self._json({'error': f'map read failed: {e}'})

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
