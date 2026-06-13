# DEV NOTE: All code, comments, and variable names must be in English.
"""Vdyno handler mixin -- VDYNO Phase V1 (BL-VD-01).

Endpoints:
  GET /vdyno?session=CS&ride=N        -> compute_ride result (cached)
  GET /vdyno/compare?a=CS_A&b=CS_B   -> compare_sessions result
  GET /vdyno_rows?session=CS&ride=N   -> sparse per-row HP/torque for ride chart
"""
import logging
import urllib.parse


class VdynoHandlerMixin:
    def _handle_vdyno(self, path=None):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            session_id = (qs.get('session') or [''])[0].strip().upper()
            ride_str   = (qs.get('ride')    or [''])[0].strip()

            if not session_id:
                self._json({'ok': False, 'error': 'session param required'}, 400)
                return

            from web.vdyno import compute_ride, session_bins, _build_result_bins

            buell_dir = self.server_instance.buell_dir

            if ride_str:
                try:
                    ride_num = int(ride_str)
                except ValueError:
                    self._json({'ok': False, 'error': 'ride must be integer'}, 400)
                    return
                result = compute_ride(buell_dir, session_id, ride_num)
                if result is None:
                    self._json({'ok': False, 'error': 'no WOT data for this ride'}, 404)
                    return
                self._json({'ok': True, **result})
            else:
                bins_map = session_bins(buell_dir, session_id)
                if not bins_map:
                    self._json({'ok': False, 'error': 'no WOT data for session'}, 404)
                    return
                self._json({'ok': True, 'session_id': session_id,
                            'bins': _build_result_bins(bins_map)})

        except Exception as e:
            logging.exception('/vdyno error')
            self._json({'ok': False, 'error': str(e)}, 500)

    def _handle_vdyno_compare(self, path=None):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sa = (qs.get('a') or [''])[0].strip().upper()
            sb = (qs.get('b') or [''])[0].strip().upper()

            if not sa or not sb:
                self._json({'ok': False, 'error': 'a and b params required'}, 400)
                return

            from web.vdyno import compare_sessions
            result = compare_sessions(self.server_instance.buell_dir, sa, sb)
            if not result['bins']:
                self._json({'ok': False, 'error': 'no overlapping RPM bins'}, 404)
                return
            self._json({'ok': True, **result})

        except Exception as e:
            logging.exception('/vdyno/compare error')
            self._json({'ok': False, 'error': str(e)}, 500)

    def _handle_vdyno_rows(self, path=None):
        """GET /vdyno_rows?session=X&ride=N
        Returns sparse per-row HP/torque for WOT rows only.
        Used by the ride chart in app.js to overlay HP/torque as plottable channels.
        """
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            session_id = (qs.get('session') or [''])[0].strip().upper()
            ride_str   = (qs.get('ride')    or [''])[0].strip()

            if not session_id or not ride_str:
                self._json({'ok': False, 'error': 'session and ride params required'}, 400)
                return
            try:
                ride_num = int(ride_str)
            except ValueError:
                self._json({'ok': False, 'error': 'ride must be integer'}, 400)
                return

            from web.vdyno import compute_ride_rows
            result = compute_ride_rows(self.server_instance.buell_dir, session_id, ride_num)
            if result is None:
                self._json({'ok': False, 'error': 'no WOT data'}, 404)
                return
            self._json({'ok': True, **result})

        except Exception as e:
            logging.exception('/vdyno_rows error')
            self._json({'ok': False, 'error': str(e)}, 500)
