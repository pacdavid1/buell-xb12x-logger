#!/usr/bin/env python3
import json, os, csv, glob
class GpsHandlerMixin:
    def _handle_gps_fix(self):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return {"error": "GPS not available"}
        return gps.get_fix().as_dict()
    def _handle_gps_config(self):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return {"error": "GPS not available"}
        return gps.get_config().as_dict()
    def _handle_gps_config_update(self):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return {"error": "GPS not available"}
        kwargs = {}
        for k, v in self.query.items():
            if hasattr(gps.config, k):
                try:
                    kwargs[k] = float(v)
                except ValueError:
                    kwargs[k] = v
        if kwargs:
            gps.set_config(**kwargs)
        return {"status": "ok", "config": gps.get_config().as_dict()}
    def _handle_gps_track(self, path=None):
        session = self.query.get('session')
        ride = self.query.get('ride')
        if not session or not ride:
            return {"error": "Missing session/ride params"}
        buell_dir = getattr(self.server_instance, 'buell_dir', None)
        if not buell_dir:
            return {"error": "No buell_dir"}
        rides_dir = os.path.join(buell_dir, 'sessions', session)
        if not os.path.isdir(rides_dir):
            return {"error": f"Session dir not found: {rides_dir}"}
        pat = os.path.join(rides_dir, f"ride_{session}_{int(ride):03d}*.csv")
        files = sorted(glob.glob(pat))
        if not files:
            return {"error": f"No CSV found for {session} ride {ride}"}
        points = []
        try:
            with open(files[0]) as f:
                first = f.readline()
                if not first.startswith('#'):
                    f.seek(0)
                for row in csv.DictReader(f):
                    lat = row.get('gps_lat')
                    lon = row.get('gps_lon')
                    if lat and lon:
                        try:
                            lat_f = float(lat)
                            lon_f = float(lon)
                        except ValueError:
                            continue
                        if abs(lat_f) < 90 and abs(lon_f) < 180:
                            pt = {'lat': lat_f, 'lon': lon_f,
                                  'spd': float(row.get('gps_speed_kmh') or 0),
                                  'alt': float(row.get('gps_alt_m') or 0),
                                  't': float(row.get('time_elapsed_s') or 0)}
                            if row.get('gps_heading'):
                                pt['hdg'] = float(row['gps_heading'])
                            if row.get('gps_mode'):
                                pt['mode'] = int(float(row['gps_mode']))
                            if row.get('gps_snr_avg'):
                                pt['snr'] = round(float(row['gps_snr_avg']), 1)
                            points.append(pt)
        except Exception as e:
            return {"error": str(e)}
        return {"points": points, "count": len(points)}
