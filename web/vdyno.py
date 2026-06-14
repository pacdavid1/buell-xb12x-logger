# DEV NOTE: All code, comments, and variable names must be in English.
"""Virtual dyno engine -- VDYNO Phase V1 (BL-VD-01).

Computes wheel power from VS_KPH + RPM for stable WOT segments.
Instrument is DIFFERENTIAL: absolute HP values are approximate, but A-vs-B
comparisons on the same bike with the same rider are meaningful.

No baro/GPS per CSV row (BL-LOGGER-01 pending) -- rho defaults to constant
configurable in vdyno_config.json at the buell root.

See docs/11_VDYNO_PLAN.md and BACKLOG_VDYNO.md.
"""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

_CACHE_V = 1
_G = 9.81           # m/s^2
_KPH_TO_MS = 1.0 / 3.6
_HP_PER_KW = 1.34102

_DEFAULT_CFG = {
    'mass_kg': 295,         # bike wet + average rider (kg)
    'CdA': 0.60,            # drag area (m^2)
    'Crr': 0.015,           # rolling resistance coefficient
    'rho': 1.10,            # air density kg/m^3 (~940 hPa / 25 C, Mexico City)
    'drivetrain_eff': 0.91,
    'tps_min_pct': 70.0,    # minimum TPS to count as WOT segment
    'rpm_min': 1500,        # minimum RPM to exclude idle/engine-off fl_wot noise
    'min_seg_s': 1.5,       # minimum segment duration (s)
    'smooth_s': 1.0,        # VS_KPH smoothing window (s)
    'rpm_bin': 250,         # RPM bin width for output curve
}


def _load_cfg(buell_dir):
    path = Path(buell_dir) / 'vdyno_config.json'
    cfg = dict(_DEFAULT_CFG)
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text()))
        except Exception:
            pass
    return cfg


def _smooth(arr, window):
    """Rolling mean with edge-padding to avoid boundary artifacts."""
    if window <= 1 or len(arr) < window:
        return arr.copy()
    pad = window // 2
    padded = np.pad(arr, pad, mode='edge')
    smoothed = np.convolve(padded, np.ones(window) / window, mode='valid')
    return smoothed[:len(arr)]


def _read_csv(path):
    rows = []
    with open(path) as f:
        first = f.readline()
        if not first.startswith('#'):
            f.seek(0)
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def _extract_segments(rows, cfg):
    """Slice rows into stable WOT pulls (fl_wot or TPS >= tps_min, no decel)."""
    segs, start = [], None
    for i, r in enumerate(rows):
        tps = float(r.get('TPS_pct') or 0)
        rpm = float(r.get('RPM') or 0)
        on = (
            (int(r.get('fl_wot') or 0) or tps >= cfg['tps_min_pct'])
            and not int(r.get('fl_decel') or 0)
            and int(float(r.get('Gear') or 0)) >= 1
            and float(r.get('VS_KPH') or 0) > 20
            and rpm >= cfg.get('rpm_min', 1500)
        )
        if on and start is None:
            start = i
        elif not on and start is not None:
            seg = rows[start:i]
            t0 = float(seg[0].get('time_elapsed_s') or 0)
            if float(seg[-1].get('time_elapsed_s') or 0) - t0 >= cfg['min_seg_s']:
                segs.append(seg)
            start = None
    if start is not None:
        seg = rows[start:]
        if seg:
            t0 = float(seg[0].get('time_elapsed_s') or 0)
            if float(seg[-1].get('time_elapsed_s') or 0) - t0 >= cfg['min_seg_s']:
                segs.append(seg)
    return segs


def _seg_physics(seg, cfg):
    """Compute per-row physics arrays for one WOT segment.

    Returns (times, rpms, vss_s, P_w) or None if segment is too short.
    P_w is in watts.
    """
    times = np.array([float(r.get('time_elapsed_s') or 0) for r in seg])
    vss   = np.array([float(r.get('VS_KPH') or 0) for r in seg]) * _KPH_TO_MS
    rpms  = np.array([float(r.get('RPM') or 0) for r in seg])

    if len(times) < 4:
        return None

    dt_med = float(np.median(np.diff(times))) or 0.125
    window = max(3, int(cfg['smooth_s'] / dt_med))
    vss_s  = _smooth(vss, window)

    dt = np.diff(times)
    dt[dt == 0] = dt_med
    a = np.append(np.diff(vss_s) / dt, 0.0)

    m   = cfg['mass_kg']
    F   = m * a + 0.5 * cfg['rho'] * cfg['CdA'] * vss_s ** 2 + cfg['Crr'] * m * _G
    P_w = F * vss_s  # watts

    return times, rpms, vss_s, P_w


def _seg_bins(seg, cfg):
    """Power bins {rpm_center: [kw]} for one WOT segment."""
    result = _seg_physics(seg, cfg)
    if result is None:
        return {}
    times, rpms, vss_s, P_w = result

    bw = cfg['rpm_bin']
    bins = {}
    for i, p_w in enumerate(P_w):
        if vss_s[i] < 5:
            continue
        center = int(rpms[i] / bw) * bw + bw // 2
        bins.setdefault(center, []).append(p_w / 1000.0)
    return bins


def _build_result_bins(all_bins):
    result = []
    for rpm in sorted(all_bins):
        arr    = np.array(all_bins[rpm])
        p_med  = float(np.median(arr))
        omega  = rpm * 2 * math.pi / 60
        result.append({
            'rpm':        rpm,
            'p_kw_med':   round(p_med, 2),
            'p_kw_p25':   round(float(np.percentile(arr, 25)), 2),
            'p_kw_p75':   round(float(np.percentile(arr, 75)), 2),
            'hp_med':     round(p_med * _HP_PER_KW, 1),
            'torque_nm':  round((p_med * 1000 / omega) if omega else 0.0, 1),
            'n':          len(arr),
        })
    return result


def compute_ride(buell_dir, session_id, ride_num):
    """Compute or load cached vdyno curve for one ride. Returns None if no WOT data."""
    session_dir = Path(buell_dir) / 'sessions' / session_id
    csv_path    = session_dir / 'ride_{}_{:03d}.csv'.format(session_id, ride_num)
    if not csv_path.exists():
        return None

    cache = session_dir / 'ride_{}_{:03d}_vdyno.json'.format(session_id, ride_num)
    if cache.exists():
        try:
            c = json.loads(cache.read_text())
            if c.get('vdyno_v') == _CACHE_V:
                return c
        except Exception:
            pass

    cfg  = _load_cfg(buell_dir)
    rows = _read_csv(csv_path)
    if not rows:
        return None

    segs = _extract_segments(rows, cfg)
    if not segs:
        return None

    all_bins = {}
    for seg in segs:
        for rpm_c, vals in _seg_bins(seg, cfg).items():
            all_bins.setdefault(rpm_c, []).extend(vals)

    if not all_bins:
        return None

    result = {
        'vdyno_v':    _CACHE_V,
        'session_id': session_id,
        'ride_num':   ride_num,
        'n_segments': len(segs),
        'cfg':        {k: cfg[k] for k in ('mass_kg', 'CdA', 'Crr', 'rho')},
        'bins':       _build_result_bins(all_bins),
    }
    tmp = cache.with_suffix('.tmp')
    tmp.write_text(json.dumps(result))
    os.replace(tmp, cache)
    return result


def compute_ride_rows(buell_dir, session_id, ride_num):
    """Sparse per-row HP/torque for WOT rows only (null elsewhere).

    Returns {vdyno_v, session_id, ride_num, rows: [{time_s, p_kw, hp, torque_nm}]}
    or None if no usable WOT data. Result is cached to _vdyno_rows.json.
    Only WOT rows are included -- non-WOT rows are absent (treated as null in JS).
    """
    session_dir = Path(buell_dir) / 'sessions' / session_id
    csv_path    = session_dir / 'ride_{}_{:03d}.csv'.format(session_id, ride_num)
    if not csv_path.exists():
        return None

    cache = session_dir / 'ride_{}_{:03d}_vdyno_rows.json'.format(session_id, ride_num)
    if cache.exists():
        try:
            c = json.loads(cache.read_text())
            if c.get('vdyno_v') == _CACHE_V:
                return c
        except Exception:
            pass

    cfg  = _load_cfg(buell_dir)
    rows = _read_csv(csv_path)
    if not rows:
        return None

    segs = _extract_segments(rows, cfg)
    if not segs:
        return None

    result_rows = []
    rpm_min = cfg.get('rpm_min', 1500)
    for seg in segs:
        phys = _seg_physics(seg, cfg)
        if phys is None:
            continue
        times, rpms, vss_s, P_w = phys
        for i, row in enumerate(seg):
            if vss_s[i] < 5 or rpms[i] < rpm_min:
                continue
            omega = rpms[i] * 2 * math.pi / 60
            p_kw  = P_w[i] / 1000.0
            result_rows.append({
                'time_s':    round(float(times[i]), 3),
                'p_kw':      round(p_kw, 2),
                'hp':        round(p_kw * _HP_PER_KW, 1),
                'torque_nm': round((P_w[i] / omega) if omega else 0.0, 1),
            })

    if not result_rows:
        return None

    result = {
        'vdyno_v':    _CACHE_V,
        'session_id': session_id,
        'ride_num':   ride_num,
        'rows':       result_rows,
    }
    tmp = cache.with_suffix('.tmp')
    tmp.write_text(json.dumps(result))
    os.replace(tmp, cache)
    return result


def session_bins(buell_dir, session_id):
    """Merge all rides in a session -> {rpm_center: [median_kw_per_ride]}."""
    merged = {}
    session_dir = Path(buell_dir) / 'sessions' / session_id
    for csv_path in sorted(session_dir.glob('ride_{}_*.csv'.format(session_id))):
        stem = csv_path.stem
        try:
            ride_num = int(stem.rsplit('_', 1)[-1])
        except ValueError:
            continue
        result = compute_ride(buell_dir, session_id, ride_num)
        if result:
            for b in result['bins']:
                merged.setdefault(b['rpm'], []).append(b['p_kw_med'])
    return merged


def compare_sessions(buell_dir, session_a, session_b):
    """Return per-RPM-bin delta between two sessions' merged power curves."""
    bins_a = session_bins(buell_dir, session_a)
    bins_b = session_bins(buell_dir, session_b)
    all_rpms = sorted(set(bins_a) | set(bins_b))
    rows = []
    for rpm in all_rpms:
        va = bins_a.get(rpm, [])
        vb = bins_b.get(rpm, [])
        if not va or not vb:
            continue
        med_a  = float(np.median(va))
        med_b  = float(np.median(vb))
        omega  = rpm * 2 * math.pi / 60
        rows.append({
            'rpm':          rpm,
            'p_kw_a':       round(med_a, 2),
            'p_kw_b':       round(med_b, 2),
            'hp_a':         round(med_a * _HP_PER_KW, 1),
            'hp_b':         round(med_b * _HP_PER_KW, 1),
            'torque_nm_a':  round((med_a * 1000 / omega) if omega else 0.0, 1),
            'torque_nm_b':  round((med_b * 1000 / omega) if omega else 0.0, 1),
            'delta_kw':     round(med_b - med_a, 2),
            'delta_hp':     round((med_b - med_a) * _HP_PER_KW, 1),
            'delta_pct':    round(100 * (med_b - med_a) / med_a, 1) if med_a else None,
            'n_a':          len(va),
            'n_b':          len(vb),
        })
    return {'session_a': session_a, 'session_b': session_b, 'bins': rows}

def compute_launch_cluster_power(cluster, cfg=None):
    """Compute HP/torque from a launch cluster mean_series.

    Uses same physics as _seg_physics but on pre-averaged
    mean_series from a launch event cluster.

    Returns list of dicts compatible with _build_result_bins format
    or None if no usable data.
    """
    if cfg is None:
        cfg = dict(_DEFAULT_CFG)

    ms = cluster.get("mean_series")
    if not ms or len(ms) < 4:
        return None

    times   = np.array([float(x.get("dt") or 0) for x in ms])
    vss_kph = np.array([float(s) if s is not None else 0.0 for s in (x.get("spd") for x in ms)])
    rpms    = np.array([float(x.get("rpm") or 0) for x in ms])

    mask = vss_kph > 8
    if mask.sum() < 4:
        return None
    times, vss_kph, rpms = times[mask], vss_kph[mask], rpms[mask]

    vss = vss_kph * _KPH_TO_MS

    dt_vals = np.diff(times)
    dt_vals = dt_vals[dt_vals > 0]
    dt_med  = float(np.median(dt_vals)) if len(dt_vals) > 0 else 0.25
    window = max(3, int(round(cfg["smooth_s"] / dt_med)))
    vss_s = _smooth(vss, window)

    dt_arr = np.diff(times)
    dt_arr[dt_arr <= 0] = dt_med
    a = np.append(np.diff(vss_s) / dt_arr, 0.0)

    m = cfg["mass_kg"]
    F = m * a + 0.5 * cfg["rho"] * cfg["CdA"] * vss_s ** 2 + cfg["Crr"] * m * _G
    P_w = F * vss_s

    bw = cfg["rpm_bin"]
    rpm_min = cfg.get("rpm_min", 1500)
    all_bins = {}
    for i, p_w in enumerate(P_w):
        if vss_s[i] < 5 or rpms[i] < rpm_min:
            continue
        center = int(rpms[i] / bw) * bw + bw // 2
        all_bins.setdefault(center, []).append(p_w / 1000.0)

    if not all_bins:
        return None

    return _build_result_bins(all_bins)

