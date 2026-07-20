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

    def _handle_eeprom_import_xpr(self, path=None, payload=None):
        """POST /eeprom/import_xpr
        Body: { filename, data_b64, note?, version? }
        Import an .xpr/EEPROM file as a new session. Pure filesystem --
        never touches the ECU. Used by the Map Editor's Import XPR button.
        """
        import base64
        from ecu.xpr_import import DEFAULT_VERSION, import_xpr_bytes
        body = payload or {}
        filename = body.get('filename', 'upload.xpr')
        data_b64 = body.get('data_b64')
        if not data_b64:
            self._json({'error': 'data_b64 is required'})
            return
        try:
            data = base64.b64decode(data_b64)
        except Exception as e:
            self._json({'error': f'invalid base64: {e}'})
            return
        if len(data) > 65536:
            self._json({'error': 'file too large for an EEPROM export'})
            return
        version = body.get('version') or DEFAULT_VERSION
        note = body.get('note', '')
        buell_dir = self.server_instance.buell_dir
        try:
            result = import_xpr_bytes(data, buell_dir / 'sessions', version, note, filename)
        except ValueError as e:
            self._json({'error': f'import failed: {e}'})
            return
        self._json({'ok': True, **result})

    def _handle_eeprom_burn(self, path=None, payload=None):
        """Burn proposed map changes to ECU EEPROM.
        POST body: { maps: { fuel_front?, fuel_rear?, spark_front?, spark_rear? } }
        Only allowed when no ride is active. Saves backup before burn.
        """
        import base64
        from ecu.eeprom import apply_map_changes, encode_eeprom_maps
        if getattr(self.server_instance, 'ride_active', False):
            self._json({'error': 'cannot burn while ride is active'})
            return
        body = payload or {}
        maps = body.get('maps', {})
        changes = body.get('changes', [])
        # GAP 6: ILC learning rate — scale delta by alpha before burning.
        # alpha=1.0 means apply 100% of proposed change (legacy default).
        # alpha=0.5 means apply 50%; new_val = orig + alpha*(proposed - orig).
        alpha = float(body.get('alpha', 1.0))
        alpha = max(0.1, min(1.0, alpha))
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
        version = _session_version(eeprom_path)
        try:
            if changes:
                proposed = apply_map_changes(current_bin, changes, alpha, version)
            else:
                proposed = encode_eeprom_maps(current_bin, maps, version)
        except ValueError as e:
            self._json({'error': str(e)})
            return
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
        result['alpha_used'] = round(alpha, 2)
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

    def _handle_eeprom_save_session(self, path=None, payload=None):
        """POST /eeprom/save_session
        Body: { session?, changes: [...], alpha?, note? }
        Apply staged cell edits and save the result as a NEW session --
        pure filesystem, never touches the ECU. Lets a map be edited and
        compared before deciding to actually burn it (see /eeprom/burn).
        """
        from ecu.eeprom import apply_map_changes
        from ecu.session import SessionManager
        body = payload or {}
        changes = body.get('changes', [])
        if not changes:
            self._json({'error': 'no changes provided'})
            return
        alpha = max(0.1, min(1.0, float(body.get('alpha', 1.0))))
        buell_dir = self.server_instance.buell_dir
        src_session = body.get('session') or getattr(self.server_instance.session, 'current_checksum', None)
        if not src_session:
            self._json({'error': 'no session specified and no active session'})
            return
        eeprom_path = buell_dir / 'sessions' / src_session / 'eeprom.bin'
        if not eeprom_path.exists():
            self._json({'error': 'eeprom.bin not found for session ' + src_session})
            return
        current_bin = eeprom_path.read_bytes()
        version = _session_version(eeprom_path)
        try:
            proposed = apply_map_changes(current_bin, changes, alpha, version)
        except ValueError as e:
            self._json({'error': str(e)})
            return

        session = SessionManager(buell_dir / 'sessions')
        is_new = session.open_session(version, proposed)
        session.save_eeprom(proposed)
        session.session_metadata['derived_from'] = {
            'session': src_session, 'changes': changes, 'alpha': round(alpha, 2)}
        session.session_metadata.setdefault('rider_notes', []).append({
            'source': 'map_edit', 'base_session': src_session,
            'note': body.get('note', '')})
        session._save_metadata()
        self._json({
            'ok': True, 'checksum': session.current_checksum,
            'base_session': src_session, 'is_new': is_new,
            'n_changes': len(changes),
        })

    def _handle_burns_list(self, path=None):
        """GET /burns — burn ledger entries, newest first."""
        from web.burn_ledger import load_burns
        burns = load_burns(self.server_instance.buell_dir)
        self._json({'ok': True, 'count': len(burns), 'burns': burns[::-1]})

    def _handle_convergence(self, path=None):
        """GET /convergence?sessions=A,B,C — GAP 5 residual variance convergence across session pairs."""
        import urllib.parse
        from web.vs_engine import compute_convergence
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        raw = qs.get('sessions', [''])[0].strip()
        session_ids = [s.strip() for s in raw.split(',') if s.strip()]
        if len(session_ids) < 2:
            self._json({'error': 'sessions param requires at least 2 session IDs (comma-separated)'}, 400)
            return
        try:
            result = compute_convergence(self.server_instance.buell_dir, session_ids)
            self._json(result)
        except Exception as e:
            import traceback
            self._json({'error': str(e), 'trace': traceback.format_exc()}, 500)

    def _handle_route_reference(self, path=None):
        """GET /route_reference — stats for the accumulated GPS altitude reference.
        GET /route_reference?update=all  — rebuild from all sessions.
        GET /route_reference?update=<session_id>  — ingest one session.
        GET /route_reference?lat=<f>&lon=<f>  — query trusted altitude for a coordinate.
        """
        from gps.route_reference import RouteReference
        import urllib.parse
        buell_dir = self.server_instance.buell_dir
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ref = RouteReference(buell_dir)

        update = params.get('update', [None])[0]
        if update == 'all':
            result = ref.update_all_sessions(buell_dir)
            self._json(result)
            return
        if update:
            session_dir = Path(buell_dir) / 'sessions' / update
            if not session_dir.is_dir():
                self._json({'error': f'session not found: {update}'})
                return
            result = ref.update_from_session(session_dir)
            self._json(result)
            return

        lat_raw = params.get('lat', [None])[0]
        lon_raw = params.get('lon', [None])[0]
        if lat_raw and lon_raw:
            try:
                lat, lon = float(lat_raw), float(lon_raw)
                alt = ref.get_altitude(lat, lon)
                self._json({'lat': lat, 'lon': lon, 'alt_m': alt})
            except ValueError:
                self._json({'error': 'invalid lat/lon'})
            return

        self._json(ref.stats())

    def _handle_slope_reference(self, path=None):
        """GET /slope_reference                         — stats.
        GET /slope_reference?update=all                 — rebuild from all sessions.
        GET /slope_reference?update=<session_id>        — ingest one session.
        GET /slope_reference?lat1=&lon1=&lat2=&lon2=    — query slope between two points.
        """
        from gps.slope_reference import SlopeReference
        buell_dir = self.server_instance.buell_dir
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ref = SlopeReference(buell_dir)

        update = params.get('update', [None])[0]
        if update == 'all':
            self._json(ref.update_all_sessions(buell_dir))
            return
        if update:
            session_dir = Path(buell_dir) / 'sessions' / update
            if not session_dir.is_dir():
                self._json({'error': f'session not found: {update}'})
                return
            self._json(ref.update_from_session(session_dir))
            return

        for key in ('lat1', 'lon1', 'lat2', 'lon2'):
            if not params.get(key):
                break
        else:
            try:
                lat1 = float(params['lat1'][0])
                lon1 = float(params['lon1'][0])
                lat2 = float(params['lat2'][0])
                lon2 = float(params['lon2'][0])
                slope = ref.get_slope_pct(lat1, lon1, lat2, lon2)
                self._json({'lat1': lat1, 'lon1': lon1, 'lat2': lat2, 'lon2': lon2,
                            'slope_pct': slope})
            except ValueError:
                self._json({'error': 'invalid coordinates'})
            return

        self._json(ref.stats())

    def _handle_gear_profile(self, path=None):
        """GET /gear_profile                  -- stats / current thresholds.
        GET /gear_profile?learn=1             -- relearn from all sessions.
        GET /gear_profile?learn=1&n_gears=6   -- relearn specifying gear count.
        """
        from web.gear_learner import GearLearner
        buell_dir = self.server_instance.buell_dir
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        learner = GearLearner(buell_dir)

        if params.get('learn', [None])[0]:
            try:
                n_gears = int(params.get('n_gears', ['5'])[0])
            except ValueError:
                n_gears = 5
            self._json(learner.learn(buell_dir, n_gears=n_gears))
            return

        self._json(learner.stats())

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
        """GET /eeprom/propose - DEPRECATED: log warning only.
        The POST variant (FASE 6 Phase 4) generates a real proposal --
        see _handle_eeprom_propose_post."""
        logging.getLogger("WebServer").warning(
            "DEPRECATED: /eeprom/propose was called from %s",
            self.client_address[0]
        )
        self._json({'error': 'endpoint deprecated', 'message': 'PROPOSAL tab was removed'}, 410)

    def _handle_eeprom_propose_post(self, path=None, payload=None):
        """POST /eeprom/propose - generate a map proposal from two sessions.
        Body: { session_a, session_b, mode?, reference?, save? }
        save=false (default) returns the proposal JSON only (dry run, no disk
        writes). save=true also persists it as a PROP_* session (per
        BACKLOG.md's FASE 6 spec) and returns its checksum.
        """
        from web.proposal import generate_proposal, save_proposal
        body = payload or {}
        sa = body.get('session_a')
        sb = body.get('session_b')
        if not sa or not sb:
            self._json({'error': 'session_a and session_b are required'})
            return
        params = {'mode': body.get('mode', 'BALANCE'), 'reference': body.get('reference', 'B')}
        buell_dir = self.server_instance.buell_dir
        try:
            result = generate_proposal(buell_dir, sa, sb, params)
        except Exception as e:
            self._json({'error': 'proposal generation failed: ' + str(e)})
            return
        if not result.get('ok'):
            self._json({'error': result.get('error', 'unknown error')})
            return
        response = {
            'ok': True, 'source_sessions': result['source_sessions'],
            'reference': result['reference'], 'mode': result['mode'],
            'proposed': result['proposed'], 'axes': result['axes'],
            'stats': result['stats'],
        }
        if body.get('save'):
            try:
                response['prop_session'] = save_proposal(buell_dir, result)
            except Exception as e:
                self._json({'error': 'save failed: ' + str(e)})
                return
        self._json(response)

    def _handle_maps(self, path=None):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        req_session = params.get('session', [''])[0]
        bins = []
        if req_session:
            ses_path = self.server_instance.buell_dir / 'sessions' / req_session / 'eeprom.bin'
            if ses_path.exists():
                bins = [ses_path]
        if not bins:
            try:
                bins = sorted(
                    (self.server_instance.buell_dir / 'sessions').glob('*/eeprom.bin'),
                    key=lambda p: p.stat().st_mtime)
            except Exception:
                bins = []
        if not bins:
            self._json({'maps': {}, 'axes': {}})
            return
        try:
            result = _decode_eeprom_maps_full(bins[-1].read_bytes(), _session_version(bins[-1]))
            self._json(result)
        except Exception as e:
            self._json({'error': str(e)}, 500)

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
