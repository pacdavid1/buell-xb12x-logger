# DEV NOTE: All code, comments, and variable names must be in English.
from urllib.parse import urlparse, parse_qs
import os, csv, glob
from pathlib import Path
from web.utils import _get_version


class GpsHandlerMixin:
    def _handle_gps_fix(self, path=None):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return self._json({"error": "GPS not available"})
        return self._json(gps.get_fix().as_dict())

    def _handle_gps_config(self, path=None):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return self._json({"error": "GPS not available"})
        return self._json(gps.get_config().as_dict())

    def _handle_gps_config_update(self, path=None):
        gps = getattr(self.server_instance, 'gps', None)
        if not gps:
            return self._json({"error": "GPS not available"})
        qs = parse_qs(urlparse(self.path).query)
        kwargs = {}
        for k, vals in qs.items():
            if hasattr(gps.config, k):
                v = vals[0] if vals else ''
                try:
                    kwargs[k] = float(v)
                except ValueError:
                    kwargs[k] = v
        if kwargs:
            gps.set_config(**kwargs)
        return self._json({"status": "ok", "config": gps.get_config().as_dict()})

    def _handle_gps_track(self, path=None):
        qs = parse_qs(urlparse(self.path).query)
        session = qs.get('session', [None])[0]
        ride = qs.get('ride', [None])[0]
        if not session or not ride:
            return self._json({"error": "Missing session/ride params"}, 400)
        buell_dir = getattr(self.server_instance, 'buell_dir', None)
        if not buell_dir:
            return self._json({"error": "No buell_dir"})
        rides_dir = os.path.join(buell_dir, 'sessions', session)
        if not os.path.isdir(rides_dir):
            return self._json({"error": f"Session dir not found: {rides_dir}"})
        pat = os.path.join(rides_dir, f"ride_{session}_{int(ride):03d}*.csv")
        files = sorted(glob.glob(pat))
        if not files:
            return self._json({"error": f"No CSV found for {session} ride {ride}"})
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
            return self._json({"error": str(e)}, 500)
        return self._json({"points": points, "count": len(points)})

    def _handle_gps_analysis(self, path=None):
        """Serve the GPS analysis page."""
        try:
            html = (Path(__file__).parent.parent / 'templates' / 'gps_analysis.html').read_text(encoding='utf-8')
            self._html(html.replace('--LOGGER_VERSION--', _get_version()))
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _handle_gps_analysis_data(self, path=None):
        """Return aligned time-series arrays: GPS speed, VS_KPH, fix quality, for comparison chart."""
        qs = parse_qs(urlparse(self.path).query)
        session = qs.get('session', [None])[0]
        ride = qs.get('ride', [None])[0]
        if not session or not ride:
            return self._json({"error": "Missing session/ride params"}, 400)
        buell_dir = getattr(self.server_instance, 'buell_dir', None)
        if not buell_dir:
            return self._json({"error": "No buell_dir"})
        rides_dir = os.path.join(buell_dir, 'sessions', session)
        pat = os.path.join(rides_dir, f"ride_{session}_{int(ride):03d}*.csv")
        files = sorted(glob.glob(pat))
        if not files:
            return self._json({"error": f"No CSV found for {session} ride {ride}"})

        def _flt(v, default=None):
            try:
                return float(v) if v not in (None, '', 'None', 'nan') else default
            except (TypeError, ValueError):
                return default

        times, lats, lons, gps_spd, vs_kph, alts, valid_flags, sats, hdgs, tps_vals = (
            [] for _ in range(10)
        )
        try:
            with open(files[0]) as f:
                first = f.readline()
                if not first.startswith('#'):
                    f.seek(0)
                for row in csv.DictReader(f):
                    t = _flt(row.get('time_elapsed_s'))
                    if t is None:
                        continue
                    times.append(t)
                    lats.append(_flt(row.get('gps_lat')))
                    lons.append(_flt(row.get('gps_lon')))
                    gps_spd.append(_flt(row.get('gps_speed_kmh'), 0.0))
                    vs_kph.append(_flt(row.get('VS_KPH'), 0.0))
                    alts.append(_flt(row.get('gps_alt_m')))
                    # Fix quality: prefer gps_mode (0/2/3) else derive from gps_valid
                    mode = _flt(row.get('gps_mode'))
                    if mode is not None:
                        valid_flags.append(int(mode))
                    else:
                        valid_flags.append(3 if row.get('gps_valid') == 'True' else 0)
                    sats.append(int(_flt(row.get('gps_satellites'), 0) or 0))
                    hdgs.append(_flt(row.get('gps_heading'), 0.0))
                    tps_vals.append(_flt(row.get('TPS_pct'), 0.0))
        except Exception as e:
            return self._json({"error": str(e)}, 500)

        # Enrich with trusted reference altitude from route_reference (BL-GPS-04)
        ref_alts = [None] * len(times)
        try:
            from gps.route_reference import RouteReference
            ref = RouteReference(buell_dir)
            for i, (lat, lon) in enumerate(zip(lats, lons)):
                if lat is not None and lon is not None and abs(lat) > 0.001:
                    ref_alts[i] = ref.get_altitude(lat, lon)
        except Exception:
            pass

        duration = times[-1] - times[0] if len(times) > 1 else 0
        return self._json({
            "times": times, "lats": lats, "lons": lons,
            "gps_speed": gps_spd, "vs_kph": vs_kph,
            "alts": alts, "ref_alts": ref_alts, "valid": valid_flags, "sats": sats,
            "headings": hdgs, "tps": tps_vals,
            "count": len(times), "duration_s": duration,
        })
