# DEV NOTE: All code, comments, and variable names must be in English.
import csv
import urllib.parse
from pathlib import Path


class GpsHandlerMixin:
    def _handle_gps_fix(self, path=None):
        try:
            gps = self.server_instance.gps
            fix = gps.get_fix() if gps else None
            self._json(fix.as_dict() if fix else {'error': 'no gps'})
        except Exception as e:
            self._json({'error': str(e)})

    def _handle_gps_track(self, path=None):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            session_id = params.get('session', [''])[0]
            ride_num = int(params.get('ride', [0])[0])
            sessions_dir = Path(self.server_instance.buell_dir) / 'sessions'
            ride_files = sorted(sessions_dir.glob(f'{session_id}/ride_{session_id}_{ride_num:03d}*.csv'))
            if not ride_files:
                self._json({'error': 'ride not found', 'points': []})
                return
            points = []
            for rf in ride_files:
                with open(rf, newline='') as f:
                    filtered = (row for row in f if not row.startswith('#'))
                    reader = csv.DictReader(filtered)
                    for row in reader:
                        try:
                            lat = float(row.get('gps_lat') or 0)
                            lon = float(row.get('gps_lon') or 0)
                            if lat != 0.0 and lon != 0.0:
                                points.append({
                                    'lat': lat,
                                    'lon': lon,
                                    'spd': float(row.get('gps_speed_kmh') or 0),
                                    'alt': float(row.get('gps_alt_m') or 0),
                                    't': float(row.get('time_elapsed_s') or 0),
                                })
                        except (ValueError, TypeError):
                            continue
            self._json({'ok': True, 'points': points, 'count': len(points)})
        except Exception as e:
            self._json({'error': str(e), 'points': []}, 500)
