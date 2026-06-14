# DEV NOTE: All code, comments, and variable names must be in English.
"""Vdyno handler mixin -- VDYNO Phase V1 (BL-VD-01).

Endpoints:
  GET /vdyno?session=CS&ride=N        -> compute_ride result (cached)
  GET /vdyno/compare?a=CS_A&b=CS_B   -> compare_sessions result
  GET /vdyno_rows?session=CS&ride=N   -> sparse per-row HP/torque for ride chart
"""
import logging
import urllib.parse
import csv
from pathlib import Path
from web.launch import detect_launches, cluster_launches
from web.vdyno import compute_launch_cluster_power, _load_cfg


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

            from web.vdyno import compare_sessions, _load_cfg

            # WOT-based comparison (existing)
            result = compare_sessions(self.server_instance.buell_dir, sa, sb)
            if not result['bins']:
                self._json({'ok': False, 'error': 'no overlapping RPM bins'}, 404)
                return

            # Launch-event power comparison (new)
            cfg = _load_cfg(self.server_instance.buell_dir)
            launch_a, _ = _session_launch_power(self.server_instance.buell_dir, sa, cfg, max_rides=10)
            launch_b, _ = _session_launch_power(self.server_instance.buell_dir, sb, cfg, max_rides=10)

            self._json({
                'ok': True,
                **result,
                'launch_a': launch_a,
                'launch_b': launch_b,
            })

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

    def _handle_vdyno_launch(self, path=None):
        """GET /vdyno/launch?session=X"""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        session = (qs.get("session") or [""])[0].strip().upper()
        if not session:
            return self._json({"ok": False, "error": "session param required"}, 400)

        from web.vdyno import _load_cfg

        try:
            cfg = _load_cfg(self.server_instance.buell_dir)
            clusters, rides_data = _session_launch_power(
                self.server_instance.buell_dir, session, cfg, max_rides=10
            )
            n_launches = sum(cl.get("count", 1) for cl in clusters)
            return self._json({
                "ok": True,
                "session": session,
                "cfg": {k: cfg[k] for k in ("mass_kg", "CdA", "Crr", "rho")},
                "n_launches": n_launches,
                "n_clusters": len(clusters),
                "clusters": clusters,
                "rides": rides_data,
            })
        except Exception as e:
            import logging
            logging.exception("vdyno_launch error")
            return self._json({"ok": False, "error": str(e)}, 500)


# ─── Helper: compute launch-cluster power for a session ───

def _session_launch_power(buell_dir, session_id, cfg, max_rides=10):
    """Load CSV rides for *session_id*, detect launches, cluster, and
    compute HP/torque per cluster.  Returns the list of cluster dicts
    (same format as /vdyno/launch) or an empty list.

    This is the shared helper used by both ``_handle_vdyno_launch``
    and ``_handle_vdyno_compare``.
    """
    import csv
    from pathlib import Path
    from web.launch import detect_launches, cluster_launches
    from web.vdyno import compute_launch_cluster_power

    session_dir = Path(buell_dir) / "sessions" / session_id
    if not session_dir.is_dir():
        return []

    csv_files = sorted(session_dir.glob("ride_{}_*.csv".format(session_id)))[-max_rides:]
    if not csv_files:
        return []

    all_launches = []

    for csv_path in csv_files:
        try:
            ride_num = int(csv_path.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue

        ride_rows = []
        with open(csv_path) as f:
            first = f.readline()
            if not first.startswith('#'):
                f.seek(0)
            reader = csv.DictReader(f)
            for r in reader:
                if not r:
                    continue
                row = {}
                for k, v in r.items():
                    if k is None:
                        continue
                    k = k.strip()
                    if not k:
                        continue
                    if v is None or v.strip() == "":
                        continue
                    try:
                        val = float(v)
                    except (ValueError, TypeError):
                        continue
                    if k == "time_elapsed_s":
                        row["t"] = val
                    elif k == "RPM":
                        row["rpm"] = val
                    elif k == "TPS_pct":
                        row["tps"] = val
                    elif k == "CLT":
                        row["clt"] = val
                    elif k == "VS_KPH":
                        row["spd"] = val
                    elif k == "Gear":
                        row["gear"] = val
                    elif k == "pw1":
                        row["pw1"] = val
                    elif k == "Accel_Corr":
                        row["ae"] = val
                    elif k == "fl_wot":
                        row["fl_wot"] = val
                    elif k == "fl_decel":
                        row["fl_decel"] = val
                    elif k == "fl_fuel_cut":
                        row["fl_fc"] = val
                    elif k == "Altimeter":
                        row["alt"] = val
                    else:
                        row[k] = val
                if row.get("t") is not None:
                    row["ride_num"] = ride_num
                    ride_rows.append(row)

        if ride_rows:
            ride_launches = detect_launches(ride_rows)
            for launch in ride_launches:
                if "ride_num" not in launch:
                    launch["ride_num"] = ride_num
            all_launches.extend(ride_launches)

    if not all_launches:
        return [], []

    # Per-ride clusters
    rides_data = {}
    for ride_num in sorted(set(l.get("ride_num") for l in all_launches if l.get("ride_num"))):
        ride_launches = [l for l in all_launches if l.get("ride_num") == ride_num]
        if not ride_launches:
            continue
        ride_clusters = cluster_launches(ride_launches)
        ride_results = []
        for cl in ride_clusters:
            bins = compute_launch_cluster_power(cl, cfg)
            ride_results.append({
                "gear": cl.get("gear"),
                "count": cl.get("count"),
                "mean_rpm": round(cl.get("mean_rpm", 0), 0),
                "mean_spd": round(cl.get("mean_spd", 0), 1),
                "peak_hp": round(max(b.get("hp_med", 0) for b in bins), 1) if bins else 0,
                "peak_rpm": max(bins, key=lambda b: b.get("hp_med", 0)).get("rpm", 0) if bins else 0,
                "bins": bins,
            })
        rides_data[str(ride_num)] = {
            "ride_num": ride_num,
            "n_launches": len(ride_launches),
            "clusters": ride_results,
        }

    # Global clusters
    clusters = cluster_launches(all_launches)
    results = []
    for i, cl in enumerate(clusters):
        bins = compute_launch_cluster_power(cl, cfg)
        d = {
            "cluster_idx": i,
            "gear": cl.get("gear"),
            "count": cl.get("count"),
            "mean_rpm": round(cl.get("mean_rpm", 0), 0),
            "mean_spd": round(cl.get("mean_spd", 0), 1),
        }
        if bins:
            pk = max(bins, key=lambda b: b.get("hp_med", 0))
            d["bins"] = bins
            d["peak_hp"] = pk.get("hp_med", 0)
            d["peak_rpm"] = pk.get("rpm", 0)
        else:
            d["bins"] = []
            d["peak_hp"] = None
        results.append(d)

    return results, rides_data
