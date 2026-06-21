# DEV NOTE: All code, comments, and variable names must be in English.
import json
import logging
import re
import time
import urllib.parse
from pathlib import Path

from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps
from ecu.eeprom import decode_eeprom_maps_full as _decode_eeprom_maps_full
from ecu.eeprom_params import decode_params as _decode_eeprom_params
from ecu.version_resolver import resolve_ecu as _resolve_ecu
from web.utils import _session_version
from web.vs_engine import _eeprom_to_msq


class EepromHandlerMixin:
    def _handle_suggested_msq(self, path=None):
        cs = self.server_instance.session.current_checksum
        if not cs:
            self._json({'error': 'no active session'})
            return
        msq_path = self.server_instance.buell_dir / 'sessions' / cs / ('suggested_' + cs + '.msq')
        if not msq_path.exists():
            self._json({'error': 'no MSQ generated yet'})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Disposition', 'attachment; filename="suggested_' + cs + '.msq"')
        self.end_headers()
        self.wfile.write(msq_path.read_bytes())

    def _handle_eeprom_download(self, path=None):
        """Serve raw eeprom.bin for a given session (or active session if none specified)."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'})
            return
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({'error': 'no session specified and no active session'})
            return
        bin_path = self.server_instance.buell_dir / 'sessions' / session / 'eeprom.bin'
        try:
            data = bin_path.read_bytes()
        except (OSError, IOError) as e:
            self._json({'error': 'could not read eeprom.bin: ' + str(e)})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', 'attachment; filename="eeprom_' + session + '.bin"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_eeprom_msq(self, path=None):
        """Generate MSQ from eeprom data for a session (no tuning modifications)."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'})
            return
        buell_dir = self.server_instance.buell_dir
        if not session:
            session = getattr(self.server_instance.session, 'current_checksum', None)
        if not session:
            decoded_files = sorted(
                (buell_dir / 'sessions').glob('*/eeprom_decoded.json'),
                key=lambda p: p.stat().st_mtime)
            if not decoded_files:
                self._json({'error': 'no eeprom_decoded.json found in any session'})
                return
            session = decoded_files[-1].parent.name
        decoded_path = buell_dir / 'sessions' / session / 'eeprom_decoded.json'
        bin_path = buell_dir / 'sessions' / session / 'eeprom.bin'
        eeprom_maps = None
        if decoded_path.exists():
            try:
                with open(decoded_path) as f:
                    eeprom_maps = json.load(f).get('maps', {})
            except Exception as e:
                self._json({'error': 'could not read eeprom_decoded.json: ' + str(e)})
                return
        elif bin_path.exists():
            try:
                eeprom_maps = _decode_eeprom_maps(bin_path.read_bytes(), _session_version(bin_path))
            except Exception as e:
                self._json({'error': 'could not decode eeprom.bin: ' + str(e)})
                return
        else:
            self._json({'error': 'no eeprom data found for session ' + session})
            return
        msq_xml = _eeprom_to_msq({'maps': eeprom_maps}, session)
        data = msq_xml.encode('utf-8')
        fname = 'eeprom_' + session + '.msq'
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Disposition', 'attachment; filename="' + fname + '"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_eeprom_sessions_list(self, path=None):
        """Return list of sessions that have an eeprom.bin, sorted newest first."""
        import datetime
        buell_dir = self.server_instance.buell_dir
        current_cs = getattr(self.server_instance.session, 'current_checksum', None)
        rows = []
        for sid in (buell_dir / 'sessions').iterdir():
            eeprom_file = sid / 'eeprom.bin'
            if not eeprom_file.exists():
                continue
            meta_file = sid / 'session_metadata.json'
            rides = 0
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    rides = meta.get('total_rides', 0)
                except Exception as e:
                    logging.debug(f"ignored: {e}")
            mtime = eeprom_file.stat().st_mtime
            rows.append({
                'id': sid.name,
                'mtime': mtime,
                'date': datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M'),
                'rides': rides,
                'current': sid.name == current_cs,
            })
        rows.sort(key=lambda r: r['mtime'], reverse=True)
        self._json(rows)

    def _handle_eeprom_revert(self, path=None, payload=None):
        """Revert ECU EEPROM to a previous session's eeprom.bin."""
        import base64
        body = payload or {}
        target_id = body.get('session', '').strip()
        if not target_id or not re.match(r'^[A-Fa-f0-9]{6}$', target_id):
            self._json({'error': 'invalid session id'})
            return
        if getattr(self.server_instance, 'ride_active', False):
            self._json({'error': 'cannot revert while ride is active'})
            return
        buell_dir = self.server_instance.buell_dir
        target_path = buell_dir / 'sessions' / target_id / 'eeprom.bin'
        if not target_path.exists():
            self._json({'error': 'eeprom.bin not found for session ' + target_id})
            return
        proposed = target_path.read_bytes()
        # Version guard: donor EEPROM layout must match live ECU (DDFI tier)
        live_identity = getattr(self.server_instance, 'ecu_identity', {}) or {}
        live_ddfi = live_identity.get('ddfi')
        if live_ddfi:
            donor_ver = _session_version(target_path)
            if donor_ver and donor_ver not in ('cached', 'unknown'):
                donor_info = _resolve_ecu(donor_ver)
                donor_ddfi = donor_info.get('ddfi') if donor_info else None
                if donor_ddfi and donor_ddfi != live_ddfi:
                    live_name = live_identity.get('name', 'unknown')
                    donor_name = donor_ver.split()[0]
                    self._json({'error': (
                        'EEPROM layout mismatch: donor is ' + donor_ddfi + ' (' + donor_name + '), '
                        'live ECU is ' + live_ddfi + ' (' + live_name + ')'
                        ' — revert blocked to prevent ECU corruption'
                    )})
                    return
        cs = getattr(self.server_instance.session, 'current_checksum', None)
        if cs:
            backup_dir = buell_dir / 'sessions' / cs
            backup_path = backup_dir / ('eeprom_backup_revert_' + time.strftime('%Y%m%d_%H%M%S') + '.bin')
            try:
                backup_path.write_bytes((backup_dir / 'eeprom.bin').read_bytes())
            except Exception as e:
                logging.debug(f"ignored: {e}")
        ipc_dir = getattr(self.server_instance, '_ipc_dir', None)
        if ipc_dir is None:
            self._json({'error': 'IPC directory not available'})
            return
        req_id = int(time.time() * 1000) & 0xFFFFFFFF
        req = {'eeprom_b64': base64.b64encode(proposed).decode(), 'req_id': req_id}
        try:
            (ipc_dir / 'burn_req.json').write_text(json.dumps(req))
        except Exception as e:
            self._json({'error': 'IPC write failed: ' + str(e)})
            return
        # Poll burn_res.json for matching req_id (90s timeout for revert)
        deadline = time.time() + 90
        result = None
        while time.time() < deadline:
            res_path = ipc_dir / 'burn_res.json'
            if res_path.exists():
                try:
                    res = json.loads(res_path.read_text())
                    if res.get('req_id') == req_id:
                        result = res
                        res_path.unlink(missing_ok=True)
                        break
                except Exception:
                    pass
            time.sleep(0.5)
        if result is None:
            try:
                (ipc_dir / 'burn_req.json').unlink(missing_ok=True)
            except Exception:
                pass
            self._json({'error': 'revert timeout (90s) — ECU may be busy'})
            return
        result['reverted_to'] = target_id
        self._json(result)

    def _handle_eeprom_burn(self, path=None, payload=None):
        """Burn proposed map changes to ECU EEPROM.
        POST body: { maps: { fuel_front?, fuel_rear?, spark_front?, spark_rear? } }
        Only allowed when no ride is active. Saves backup before burn.
        """
        import base64
        from ecu.eeprom import encode_eeprom_maps
        if getattr(self.server_instance, 'ride_active', False):
            self._json({'error': 'cannot burn while ride is active'})
            return
        body = payload or {}
        maps = body.get('maps', {})
        changes = body.get('changes', [])
        if not maps and not changes:
            self._json({'error': 'no maps or changes provided'})
            return
        buell_dir = self.server_instance.buell_dir
        cs = getattr(self.server_instance.session, 'current_checksum', None)
        if not cs:
            bins = sorted((buell_dir / 'sessions').glob('*/eeprom.bin'),
                          key=lambda p: p.stat().st_mtime)
            if not bins:
                self._json({'error': 'no eeprom.bin found'})
                return
            eeprom_path = bins[-1]
        else:
            eeprom_path = buell_dir / 'sessions' / cs / 'eeprom.bin'
        if not eeprom_path.exists():
            self._json({'error': 'eeprom.bin not found for session ' + str(cs)})
            return
        current_bin = eeprom_path.read_bytes()
        try:
            if changes:
                if len(changes) > 20:
                    self._json({'error': 'too many changes: ' + str(len(changes)) + ' (max 20 per burn)'})
                    return
                full = _decode_eeprom_maps_full(current_bin, _session_version(eeprom_path))
                current_maps = full.get('maps', {})
                for ch in changes:
                    mk  = ch.get('map')
                    ri  = int(ch.get('ri', 0))
                    ci  = int(ch.get('ci', 0))
                    val = float(ch.get('val', 0))
                    entry = current_maps.get(mk)
                    if not entry or not isinstance(entry.get('data'), list):
                        continue
                    data = entry['data']
                    if ri >= len(data) or ci >= len(data[ri]):
                        continue
                    orig = data[ri][ci]
                    if orig > 0 and abs(val - orig) > orig * 0.15:
                        self._json({'error': 'cell [' + str(ri) + ',' + str(ci) + '] exceeds +-15%: '
                                    + str(round(orig, 1)) + ' to ' + str(round(val, 1))})
                        return
                    if mk not in maps:
                        maps[mk] = [row[:] for row in data]
                    maps[mk][ri][ci] = val
            proposed = encode_eeprom_maps(current_bin, maps, _session_version(eeprom_path))
        except Exception as e:
            self._json({'error': 'encode failed: ' + str(e)})
            return
        ts = time.strftime('%Y%m%d_%H%M%S')
        backup_path = eeprom_path.parent / ('eeprom_backup_' + ts + '.bin')
        backup_path.write_bytes(current_bin)
        ipc_dir = getattr(self.server_instance, '_ipc_dir', None)
        if ipc_dir is None:
            self._json({'error': 'IPC directory not available'})
            return
        req_id = int(time.time() * 1000) & 0xFFFFFFFF
        req = {'eeprom_b64': base64.b64encode(proposed).decode(), 'req_id': req_id}
        try:
            (ipc_dir / 'burn_req.json').write_text(json.dumps(req))
        except Exception as e:
            self._json({'error': 'IPC write failed: ' + str(e)})
            return
        # Poll burn_res.json for matching req_id (30s timeout)
        deadline = time.time() + 30
        result = None
        while time.time() < deadline:
            res_path = ipc_dir / 'burn_res.json'
            if res_path.exists():
                try:
                    res = json.loads(res_path.read_text())
                    if res.get('req_id') == req_id:
                        result = res
                        res_path.unlink(missing_ok=True)
                        break
                except Exception:
                    pass
            time.sleep(0.5)
        if result is None:
            try:
                (ipc_dir / 'burn_req.json').unlink(missing_ok=True)
            except Exception:
                pass
            self._json({'error': 'burn timeout (30s)'})
            return
        result['backup'] = backup_path.name
        # Burn ledger (VDYNO V0): record lineage parent -> child with the
        # exact cell diff. Must never block the burn response.
        try:
            from web.burn_ledger import build_entry, record_burn
            entry = build_entry(
                current_bin, proposed,
                _decode_eeprom_maps(current_bin, _session_version(eeprom_path)),
                _decode_eeprom_maps(proposed, _session_version(eeprom_path)),
                source_session=str(cs) if cs else eeprom_path.parent.name,
                verified=bool(result.get('verified')),
                backup_name=backup_path.name)
            record_burn(buell_dir, entry)
            result['ledger'] = {'parent': entry['parent'],
                                'child': entry['child'],
                                'n_cells': entry['n_cells']}
        except Exception as e:
            result['ledger_error'] = str(e)
        self._json(result)

    def _handle_burns_list(self, path=None):
        """GET /burns — burn ledger entries, newest first."""
        from web.burn_ledger import load_burns
        burns = load_burns(self.server_instance.buell_dir)
        self._json({'ok': True, 'count': len(burns), 'burns': burns[::-1]})

    def _handle_msq_download(self, path=None):
        """Serve suggested MSQ for a given session (or active session if none specified)."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = params.get('session', [None])[0]
        if session and not re.match(r'^[A-Fa-f0-9]+$', session):
            self._json({'error': 'invalid session id'})
            return
        if not session:
            session = self.server_instance.session.current_checksum
        if not session:
            self._json({'error': 'no session specified and no active session'})
            return
        msq_path = (self.server_instance.buell_dir / 'sessions' / session /
                    ('suggested_' + session + '.msq'))
        try:
            data = msq_path.read_bytes()
        except (OSError, IOError) as e:
            self._json({'error': 'could not read msq file: ' + str(e)})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Disposition', 'attachment; filename="suggested_' + session + '.msq"')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_eeprom_propose(self, path=None):
        """GET /eeprom/propose - DEPRECATED: log warning only."""
        logging.getLogger("WebServer").warning(
            "DEPRECATED: /eeprom/propose was called from %s",
            self.client_address[0]
        )
        self._json({'error': 'endpoint deprecated', 'message': 'PROPOSAL tab was removed'}, 410)

    def _handle_maps(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        req_session = params.get('session', [''])[0]
        if req_session:
            ses_path = self.server_instance.buell_dir / 'sessions' / req_session / 'eeprom.bin'
            if ses_path.exists():
                try:
                    maps = _decode_eeprom_maps(ses_path.read_bytes(), _session_version(ses_path))
                    if maps and maps.get('fuel_front'):
                        self._json(maps)
                        return
                except Exception as e:
                    self._json({'error': str(e)}, 500)
                    return
        maps = self.server_instance.eeprom_maps
        if not maps or not maps.get('fuel_front'):
            try:
                bins = sorted(
                    (self.server_instance.buell_dir / 'sessions').glob('*/eeprom.bin'),
                    key=lambda p: p.stat().st_mtime)
                if bins:
                    maps = _decode_eeprom_maps(bins[-1].read_bytes(), _session_version(bins[-1]))
            except Exception as e:
                maps = {'error': str(e)}
        self._json(maps)

    def _handle_eeprom(self, path=None):
        params = self.server_instance.eeprom_params
        if not params:
            try:
                bins = sorted(
                    (self.server_instance.buell_dir / 'sessions').glob('*/eeprom.bin'),
                    key=lambda p: p.stat().st_mtime)
                if bins:
                    blob = bins[-1].read_bytes()
                    meta_path = bins[-1].parent / 'session_metadata.json'
                    ver_str = None
                    if meta_path.exists():
                        try:
                            with open(meta_path) as mf:
                                ver_str = json.load(mf).get('version_string')
                        except Exception:
                            pass
                    if not ver_str:
                        ver_str = 'unknown'
                    params = _decode_eeprom_params(blob, ver_str)
                    if not params:
                        params = {'error': f'decode_params failed (version: {ver_str})'}
            except Exception as e:
                params = {'error': str(e)}
        self._json(params)
