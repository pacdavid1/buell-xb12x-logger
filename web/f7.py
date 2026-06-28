# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.

import csv as _csv
from web.gear_detect import detect_gear as _detect_gear
import json
import math as _math
from pathlib import Path

# Inverse-order algorithm: cluster by PW curve (DTW) first, validate Bucket A second.


_F7_N       = 20    # resample points
_F7_WINDOW  = 3     # Sakoe-Chiba window
_F7_THRESH  = 0.85  # default DTW threshold
_F7_EVENTS_V = 7
_F7_PRE_N       = 10    # pre-break context resample points     # bump when event struct fields change


def _f7_resample(series, n=_F7_N):
    L = len(series)
    if L == 0:
        return [0.0] * n
    if L >= n:
        idx = [int(round(i * (L - 1) / (n - 1))) for i in range(n)]
        return [series[i] for i in idx]
    x_old = [i / (L - 1) for i in range(L)] if L > 1 else [0.0]
    x_new = [i / (n - 1) for i in range(n)]
    out = []
    for x in x_new:
        lo = max((i for i, v in enumerate(x_old) if v <= x), default=0)
        hi = min((i for i, v in enumerate(x_old) if v >= x), default=L - 1)
        if lo == hi:
            out.append(series[lo])
        else:
            t = (x - x_old[lo]) / (x_old[hi] - x_old[lo])
            out.append(series[lo] + t * (series[hi] - series[lo]))
    return out


def _f7_dtw(a, b, window=_F7_WINDOW):
    """DTW similarity 0-1 with Sakoe-Chiba window, normalized by combined range."""
    n = len(a)
    INF = float('inf')
    mat = [[INF] * (n + 1) for _ in range(n + 1)]
    mat[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - window), min(n, i + window) + 1):
            cost = abs(a[i - 1] - b[j - 1])
            mat[i][j] = cost + min(mat[i-1][j], mat[i][j-1], mat[i-1][j-1])
    raw = mat[n][n]
    cr = max(max(a), max(b)) - min(min(a), min(b))
    if cr == 0:
        return 1.0
    return max(0.0, 1.0 - raw / (n * cr))


def _f7_rolling_std(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return _math.sqrt(sum((x - m) ** 2 for x in vals) / n)


def _f7_detect_events(rows):
    """Detect acceleration events: stable bucket A >= 3s, then break, then PW rises."""
    STABLE_S    = 3.0
    RPM_STD_MAX = 150
    TPS_STD_MAX = 2.0
    TPS_BREAK   = 2.0
    MIN_VSS     = 5.0
    MAX_DUR     = 5.0
    MIN_SAMPLES = 4
    WINDOW      = 24  # ~3s at 8Hz

    events = []
    stable_buf = []
    stable_t   = 0.0
    in_stable  = False

    for i, row in enumerate(rows):
        if row.get('spd', 0) < MIN_VSS or (row.get('gear_detected') or row.get('gear', 0)) < 1 or not row.get('fl_eng', True):
            stable_buf = []
            stable_t   = 0.0
            in_stable  = False
            continue

        stable_buf.append(row)
        if len(stable_buf) > WINDOW:
            stable_buf.pop(0)
        if len(stable_buf) < WINDOW // 2:
            continue

        rpm_s = _f7_rolling_std([r['rpm'] for r in stable_buf])
        tps_s = _f7_rolling_std([r['tps'] for r in stable_buf])
        dt    = (row['t'] - rows[i - 1]['t']) if i > 0 else 0.13

        if rpm_s < RPM_STD_MAX and tps_s < TPS_STD_MAX:
            stable_t += dt
            if stable_t >= STABLE_S:
                in_stable = True
        else:
            if in_stable:
                tail_tps = sum(r['tps'] for r in stable_buf[-5:]) / min(5, len(stable_buf))
                _tps_delta = row['tps'] - tail_tps
                if abs(_tps_delta) >= TPS_BREAK:
                    _ev_type = 'accel' if _tps_delta > 0 else 'decel'
                    win = stable_buf[-WINDOW:]
                    bucket_a = {
                        'gear':    int(round(sum(r.get('gear_detected') or r['gear'] for r in win) / len(win))),
                        'rpm_avg': round(sum(r['rpm'] for r in win) / len(win), 0),
                        'tps_avg': round(sum(r['tps'] for r in win) / len(win), 1),
                        'vss_avg': round(sum(r['spd'] for r in win) / len(win), 1),
                        'clt_avg': round(sum(r['clt'] for r in win) / len(win), 1),
                    }
                    t0     = row['t']
                    gear0  = bucket_a['gear']
                    tps0   = bucket_a['tps_avg']
                    phase_b = []
                    tps_ret = 0
                    for r2 in rows[i:]:
                        if r2['t'] - t0 > MAX_DUR:
                            break
                        if int(round(r2.get('gear_detected') or r2.get('gear', 0))) != gear0:
                            break
                        if r2.get('fl_fc', False):
                            break
                        if abs(r2['tps'] - tps0) < TPS_BREAK:
                            tps_ret += 1
                            if tps_ret >= 16:
                                break
                        else:
                            tps_ret = 0
                        phase_b.append(r2)

                    if len(phase_b) >= MIN_SAMPLES:
                        pw_s = [(r['pw1'] + r.get('pw2', r['pw1'])) / 2 for r in phase_b]

                        # Trim at fuel cut: PW < 2ms means injector off
                        fc_cut = next((k for k, pw in enumerate(pw_s) if pw < 2.0), len(pw_s))
                        if fc_cut < len(pw_s):
                            phase_b = phase_b[:fc_cut]
                            pw_s    = pw_s[:fc_cut]

                        # Trim when PW drops >35% below peak for 2+ consecutive samples
                        if pw_s:
                            pk     = pw_s[0]
                            drop_n = 0
                            drop_cut = len(pw_s)
                            for k, pw in enumerate(pw_s):
                                if pw > pk:
                                    pk     = pw
                                    drop_n = 0
                                elif pk >= pw_s[0] * 1.3 and pw < pk * 0.65:
                                    drop_n += 1
                                    if drop_n >= 2:
                                        drop_cut = max(k - 1, 1)
                                        break
                                else:
                                    drop_n = 0
                            if drop_cut < len(pw_s):
                                phase_b = phase_b[:drop_cut]
                                pw_s    = pw_s[:drop_cut]

                        if len(phase_b) < MIN_SAMPLES:
                            in_stable = False
                            stable_buf = [row]
                            stable_t   = 0.0
                            continue

                        pw1_s  = [r['pw1'] for r in phase_b]
                        pw2_s  = [r.get('pw2', r['pw1']) for r in phase_b]
                        tps_s2 = [r['tps'] for r in phase_b]
                        vss_s  = [r['spd'] for r in phase_b]
                        rpm_s  = [r['rpm'] for r in phase_b]
                        dur    = phase_b[-1]['t'] - phase_b[0]['t']
                        vss_d  = vss_s[-1] - vss_s[0]

                        # accel: PW must rise; decel: any pattern allowed
                        if _ev_type == 'accel' and max(pw_s) <= pw_s[0] * 1.05:
                            in_stable = False
                            stable_buf = [row]
                            stable_t   = 0.0
                            continue

                        # Pre-break series: resample last WINDOW samples to PRE_N points
                        _PRE_N = 10
                        pre_pw_c  = _f7_resample([(r['pw1']+r.get('pw2',r['pw1']))/2 for r in win], _PRE_N)
                        pre_rpm_c = _f7_resample([r['rpm'] for r in win], _PRE_N)
                        pre_vss_c = _f7_resample([r['spd'] for r in win], _PRE_N)
                        pre_tps_c = _f7_resample([r['tps'] for r in win], _PRE_N)

                        # tps_curve_norm: Phase A tail (3 samples) + Phase B, normalized [0,1]
                        # Captures start of rider gesture for cross-session DTW matching
                        _tail_tps = [r['tps'] for r in stable_buf[-3:]]
                        _full_tps = _tail_tps + tps_s2
                        _mx = max(_full_tps) if max(_full_tps) > 0 else 1.0
                        tps_curve_norm = _f7_resample([v / _mx for v in _full_tps])

                        # GPS slope from stable window (Bucket A terrain context)
                        _gw = [r for r in win if r.get('gps_valid') and r.get('gps_alt', 0) != 0]
                        if len(_gw) >= 4:
                            _alt_d = _gw[-1]['gps_alt'] - _gw[0]['gps_alt']
                            _t_sp  = _gw[-1]['t'] - _gw[0]['t']
                            _vavg  = sum(r['spd'] for r in _gw) / len(_gw)
                            _dist  = _vavg * _t_sp * 1000 / 3600
                            gps_slope = round(_alt_d / _dist * 100, 2) if _dist > 5 else 0.0
                        else:
                            gps_slope = 0.0

                        # Environmental context from Bucket A window
                        _baro_vals = [r['baro']      for r in win if r.get('baro',     0) > 0]
                        _temp_vals = [r['temp_amb']  for r in win if r.get('temp_amb', 0) != 0]
                        _clt_vals  = [r['clt']       for r in win if r.get('clt',      0) > 0]
                        _mat_vals  = [r['mat']       for r in win if r.get('mat',      0) > 0]
                        _spark_vals= [r['spark']     for r in win if r.get('spark',    0) > 0]
                        _iat_vals  = [r['iat_corr']  for r in win if r.get('iat_corr', 0) > 0]
                        _hum_vals  = [r['humidity']  for r in win if r.get('humidity', 0) > 0]
                        _alt_vals  = [r['gps_alt']   for r in win if r.get('gps_valid') and r.get('gps_alt', 0) != 0]
                        _gd_vals   = [r['gear_detected'] for r in win if r.get('gear_detected', 0) > 0]

                        events.append({
                            'event_type': _ev_type,
                            'break_t':    round(t0, 2),
                            'duration':   round(dur, 2),
                            'n_raw':      len(phase_b),
                            'bucket_a':   bucket_a,
                            'pw_curve':   _f7_resample(pw_s),
                            'pw1_curve':  _f7_resample(pw1_s),
                            'pw2_curve':  _f7_resample(pw2_s),
                            'rpm_curve':  _f7_resample(rpm_s),
                            'vss_curve':  _f7_resample(vss_s),
                            'tps_curve':      _f7_resample(tps_s2),
                            'tps_curve_norm': tps_curve_norm,
                            'pre_pw_curve':  pre_pw_c,
                            'pre_rpm_curve': pre_rpm_c,
                            'pre_vss_curve': pre_vss_c,
                            'pre_tps_curve': pre_tps_c,
                            'pw_start':   round(pw_s[0], 2),
                            'pw_peak':    round(max(pw_s), 2),
                            'pw_delta':   round(max(pw_s) - pw_s[0], 2),
                            'tps_start':  round(tps_s2[0], 1),
                            'tps_peak':   round(max(tps_s2), 1),
                            'vss_delta':  round(vss_d, 1),
                            'very_short': dur < 0.5,
                            'gps_slope':  gps_slope,
                            'baro_hpa':    round(sum(_baro_vals)/len(_baro_vals),  1) if _baro_vals  else None,
                            'temp_amb_c':  round(sum(_temp_vals)/len(_temp_vals),  1) if _temp_vals  else None,
                            'clt_avg':     round(sum(_clt_vals)/len(_clt_vals),    1) if _clt_vals   else None,
                            'mat_avg':     round(sum(_mat_vals)/len(_mat_vals),    1) if _mat_vals   else None,
                            'spark_avg':   round(sum(_spark_vals)/len(_spark_vals),2) if _spark_vals else None,
                            'iat_corr_avg':round(sum(_iat_vals)/len(_iat_vals),    1) if _iat_vals   else None,
                            'humidity_avg':round(sum(_hum_vals)/len(_hum_vals),    1) if _hum_vals   else None,
                            'gps_alt_avg': round(sum(_alt_vals)/len(_alt_vals),    1) if _alt_vals   else None,
                            'gear_detected': max(set(_gd_vals), key=_gd_vals.count) if _gd_vals else 0,
                        })
            in_stable = False
            stable_buf = [row]
            stable_t   = 0.0

    return events


def _f7_ba_consistent(events):
    """True if all events share compatible Bucket A conditions."""
    if len(events) <= 1:
        return True
    gears = [e['bucket_a']['gear'] for e in events]
    rpms  = [e['bucket_a']['rpm_avg'] for e in events]
    tpss  = [e['bucket_a']['tps_avg'] for e in events]
    vsss  = [e['bucket_a']['vss_avg'] for e in events]
    return (
        len(set(gears)) == 1 and
        max(rpms) - min(rpms) <= 400 and
        max(tpss) - min(tpss) <= 5.0 and
        max(vsss) - min(vsss) <= 10.0
    )


def _f7_sub_divide_by_bucket_a(events):
    """Split a PW-similar group into Bucket-A-consistent sub-groups.
    Level 1: gear + 200-RPM bucket. Level 2: 10 km/h VSS bucket. Level 3: 3%-TPS bucket.
    """
    from collections import defaultdict
    if _f7_ba_consistent(events):
        return [events]
    sub1 = defaultdict(list)
    for e in events:
        key = (e['bucket_a']['gear'], int(e['bucket_a']['rpm_avg'] / 200) * 200)
        sub1[key].append(e)
    result = []
    for sg in sub1.values():
        if _f7_ba_consistent(sg):
            result.append(sg)
        else:
            sub2 = defaultdict(list)
            for e in sg:
                sub2[int(e['bucket_a']['vss_avg'] / 10) * 10].append(e)
            for sg2 in sub2.values():
                if _f7_ba_consistent(sg2):
                    result.append(sg2)
                else:
                    sub3 = defaultdict(list)
                    for e in sg2:
                        sub3[int(e['bucket_a']['tps_avg'] / 3) * 3].append(e)
                    result.extend(sub3.values())
    return result


def _f7_cluster(events, threshold=_F7_THRESH):
    """Complete-linkage DTW clustering, then sub-divide by Bucket A consistency."""
    n = len(events)
    if n == 0:
        return []

    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            s = _f7_dtw(events[i]['pw_curve'], events[j]['pw_curve'])
            mat[i][j] = mat[j][i] = s

    # Agglomerative complete linkage: merge only when min cross-pair DTW >= threshold
    clusters_idx = [{i} for i in range(n)]
    while True:
        best_score = threshold - 0.001
        best_pair  = None
        for a in range(len(clusters_idx)):
            for b in range(a + 1, len(clusters_idx)):
                min_cross = min(mat[i][j] for i in clusters_idx[a] for j in clusters_idx[b])
                if min_cross > best_score:
                    best_score = min_cross
                    best_pair  = (a, b)
        if best_pair is None:
            break
        a, b = best_pair
        merged = clusters_idx[a] | clusters_idx[b]
        clusters_idx = [c for idx, c in enumerate(clusters_idx) if idx not in (a, b)]
        clusters_idx.append(merged)

    clusters_idx.sort(key=lambda c: -len(c))

    # Sub-divide each DTW cluster by Bucket A consistency, tracking original indices
    final_groups = []  # list of (ev_list, idx_set)
    for members in clusters_idx:
        ev = [events[i] for i in sorted(members)]
        if len(ev) == 1:
            final_groups.append((ev, members))
        else:
            sub_groups = _f7_sub_divide_by_bucket_a(ev)
            if len(sub_groups) == 1:
                final_groups.append((ev, members))
            else:
                ev_to_idx = {id(events[i]): i for i in sorted(members)}
                for sg in sub_groups:
                    sg_idxs = frozenset(ev_to_idx[id(e)] for e in sg)
                    final_groups.append((sg, sg_idxs))

    final_groups.sort(key=lambda x: -len(x[0]))

    clusters = []
    cid = 1
    for ev, idx_set in final_groups:
        gears = [e['bucket_a']['gear'] for e in ev]
        rpms  = [e['bucket_a']['rpm_avg'] for e in ev]
        tpss  = [e['bucket_a']['tps_avg'] for e in ev]
        vsss  = [e['bucket_a']['vss_avg'] for e in ev]
        ba_ok = _f7_ba_consistent(ev)
        idxs  = sorted(idx_set)
        scores = [mat[ii][jj] for ii in idxs for jj in idxs if ii < jj]
        ba_summary = {
            'gear':       int(round(sum(gears) / len(gears))),
            'rpm_center': round(sum(rpms) / len(rpms), 0),
            'rpm_range':  round(max(rpms) - min(rpms), 0),
            'tps_center': round(sum(tpss) / len(tpss), 1),
            'tps_range':  round(max(tpss) - min(tpss), 1),
            'vss_center': round(sum(vsss) / len(vsss), 1),
            'vss_range':  round(max(vsss) - min(vsss), 1),
        }
        clusters.append({
            'cluster_id':     f'C{cid:03d}',
            'n':              len(ev),
            'orphan':         len(ev) == 1,
            'bucket_a_ok':    ba_ok,
            'bucket_a':       ba_summary,
            'dtw_min':        round(min(scores), 3) if scores else 1.0,
            'dtw_max':        round(max(scores), 3) if scores else 1.0,
            'has_very_short': any(e['very_short'] for e in ev),
            'members':        ev,
        })
        cid += 1
    return clusters


def _f7_temporal_stats(cluster, n=_F7_N):
    """Compute per-slice PW/VSS stats and confidence for a cluster."""
    members = cluster['members']
    if len(members) < 2:
        cluster['stats'] = None
        return

    import numpy as _np

    def _safe_mat(key):
        rows = [m[key] for m in members if m.get(key)]
        return _np.array(rows) if rows else None

    pw_mat  = _safe_mat('pw_curve')
    pw1_mat = _safe_mat('pw1_curve')
    pw2_mat = _safe_mat('pw2_curve')
    rpm_mat = _safe_mat('rpm_curve')
    vss_mat = _safe_mat('vss_curve')
    tps_mat = _safe_mat('tps_curve')

    if pw_mat is None:
        cluster['stats'] = None
        return

    pw_avg  = pw_mat.mean(axis=0).tolist()
    pw_std  = pw_mat.std(axis=0).tolist()
    pw1_avg = pw1_mat.mean(axis=0).tolist() if pw1_mat is not None else pw_avg
    pw2_avg = pw2_mat.mean(axis=0).tolist() if pw2_mat is not None else pw_avg
    pw_diff = [abs(pw1_avg[t] - pw2_avg[t]) for t in range(n)]

    k = len(members)
    confidence = []
    for t in range(n):
        n_f = min(k / 5.0, 1.0)
        s_f = max(0.0, 1.0 - pw_std[t] / 2.0)
        confidence.append(round(n_f * s_f, 2))

    def _safe_pre(key):
        rows2 = [m[key] for m in members if m.get(key)]
        if not rows2:
            return []
        mat2 = _np.array(rows2)
        return [round(v, 3) for v in mat2.mean(axis=0).tolist()]

    cluster['stats'] = {
        'pw_avg':      [round(v, 3) for v in pw_avg],
        'pw_std':      [round(v, 3) for v in pw_std],
        'pw1_avg':     [round(v, 3) for v in pw1_avg],
        'pw2_avg':     [round(v, 3) for v in pw2_avg],
        'pw_diff_avg': [round(v, 3) for v in pw_diff],
        'pw_diff_max': round(max(pw_diff), 3),
        'confidence':  confidence,
        'rpm_avg':     [round(v, 1) for v in rpm_mat.mean(axis=0).tolist()] if rpm_mat is not None else [],
        'vss_avg':     [round(v, 2) for v in vss_mat.mean(axis=0).tolist()] if vss_mat is not None else [],
        'tps_avg':     [round(v, 2) for v in tps_mat.mean(axis=0).tolist()] if tps_mat is not None else [],
        'pre_pw_avg':  _safe_pre('pre_pw_curve'),
        'pre_rpm_avg': _safe_pre('pre_rpm_curve'),
        'pre_vss_avg': _safe_pre('pre_vss_curve'),
        'pre_tps_avg': _safe_pre('pre_tps_curve'),
    }


def _f7_match_cross_session(clusters_a, clusters_b, threshold=0.85):
    """Match FASE7 accel clusters across sessions using TPS-curve DTW.

    Within-session clustering uses PW DTW (same map = deterministic PW).
    Cross-session matching uses TPS DTW: rider gesture is the common input;
    PW differs because the map changed and that difference is the signal.
    """
    matches = []
    for ca in clusters_a:
        if ca.get('orphan') or ca.get('cluster_type') != 'accel':
            continue
        sa = ca.get('stats') or {}
        if not sa.get('pw_avg'):
            continue
        for cb in clusters_b:
            if cb.get('orphan') or cb.get('cluster_type') != 'accel':
                continue
            sb = cb.get('stats') or {}
            if not sb.get('pw_avg'):
                continue

            # Bucket A compatibility
            ba_a, ba_b = ca['bucket_a'], cb['bucket_a']
            if ba_a['gear'] != ba_b['gear']:
                continue
            if abs(ba_a['rpm_center'] - ba_b['rpm_center']) > 300:
                continue
            if abs(ba_a['tps_center'] - ba_b['tps_center']) > 5:
                continue
            if abs(ba_a['vss_center'] - ba_b['vss_center']) > 15:
                continue

            # Average tps_curve_norm across members (falls back to raw tps_curve)
            def _avg_norm(cluster):
                curves = [m.get('tps_curve_norm') or m.get('tps_curve', [])
                          for m in cluster['members']]
                curves = [c for c in curves if c]
                if not curves:
                    return []
                n = len(curves[0])
                return [sum(c[i] for c in curves) / len(curves) for i in range(n)]

            tps_a = _avg_norm(ca)
            tps_b = _avg_norm(cb)
            if not tps_a or not tps_b:
                continue

            def _norm01(v):
                mx = max(v) if max(v) > 0 else 1.0
                return [x / mx for x in v]

            tps_sim = _f7_dtw(_norm01(tps_a), _norm01(tps_b))
            if tps_sim < threshold:
                continue

            pw_a    = sa['pw_avg']
            pw_b    = sb['pw_avg']
            vss_a   = sa.get('vss_avg', [])
            vss_b   = sb.get('vss_avg', [])
            conf_a  = sa.get('confidence', [])
            conf_b  = sb.get('confidence', [])
            pd_a    = sa.get('pw_diff_avg', [])
            pd_b    = sb.get('pw_diff_avg', [])

            n = min(len(pw_a), len(pw_b))
            if n == 0:
                continue

            delta_pw  = [round(pw_b[i] - pw_a[i], 3) for i in range(n)]
            pw1_a = sa.get('pw1_avg', pw_a); pw1_b = sb.get('pw1_avg', pw_b)
            pw2_a = sa.get('pw2_avg', pw_a); pw2_b = sb.get('pw2_avg', pw_b)
            n1 = min(len(pw1_a), len(pw1_b)); n2 = min(len(pw2_a), len(pw2_b))
            delta_pw1 = [round(pw1_b[i] - pw1_a[i], 3) for i in range(n1)]
            delta_pw2 = [round(pw2_b[i] - pw2_a[i], 3) for i in range(n2)]
            delta_vss = [round(vss_b[i] - vss_a[i], 2)
                         for i in range(min(n, len(vss_a), len(vss_b)))]
            if not delta_vss:
                delta_vss = [0.0] * n
            conf_match = [round(min(conf_a[i] if i < len(conf_a) else 0,
                                    conf_b[i] if i < len(conf_b) else 0), 2)
                          for i in range(n)]

            sum_pw_a   = sum(pw_a[:n]) or 1e-6
            efficiency = round(sum(delta_vss) / sum_pw_a, 4)

            nb = min(len(pd_a), len(pd_b))
            balance_shift = round(
                sum(pd_b[:nb]) / nb - sum(pd_a[:nb]) / nb, 3
            ) if nb > 0 else 0.0

            avg_conf   = sum(conf_match) / len(conf_match) if conf_match else 0
            sort_score = round(avg_conf * tps_sim * min(ca['n'], cb['n']), 4)

            matches.append({
                'cluster_a_id':     ca['cluster_id'],
                'cluster_b_id':     cb['cluster_id'],
                'n_a':              ca['n'],
                'n_b':              cb['n'],
                'tps_dtw':          round(tps_sim, 3),
                'bucket_a':         ba_a,
                'bucket_b':         ba_b,
                'delta_pw':         delta_pw,
                'delta_vss':        delta_vss,
                'conf_match':       conf_match,
                'efficiency_delta': efficiency,
                'balance_shift':    balance_shift,
                'pw_diff_max_a':    sa.get('pw_diff_max', 0),
                'pw_diff_max_b':    sb.get('pw_diff_max', 0),
                'sort_score':       sort_score,
                'delta_pw1':        delta_pw1,
                'delta_pw2':        delta_pw2,
            })

    matches.sort(key=lambda m: -m['sort_score'])
    return matches



def _f7_events_from_annotations(sdir, csv_path_map, load_csv_rows_fn):
    """Build F7 events from 'launch' type annotations (F7 Phase 2.2).

    Reads ride_*_annotations.json from sdir, filters annotations where
    type == 'launch', extracts CSV rows in [t0_s, t1_s], and builds
    event dicts with the same shape as _f7_detect_events output.
    Bucket A comes from rows in [t0_s - 3s, t0_s).
    Extra fields: annotation_id, annotation_note.
    """
    _PRE_S = 3.0
    events = []

    for ann_file in sorted(sdir.glob('ride_*_annotations.json')):
        try:
            data = json.loads(ann_file.read_text())
        except Exception:
            continue

        launch_anns = [a for a in data.get('annotations', []) if a.get('type') == 'launch']
        if not launch_anns:
            continue

        ride_stem = ann_file.stem.replace('_annotations', '')
        csv_path  = csv_path_map.get(ride_stem)
        if csv_path is None or not csv_path.exists():
            continue

        rows = load_csv_rows_fn(csv_path)
        if not rows:
            continue

        for ann in launch_anns:
            t0  = ann.get('t0_s', 0)
            t1  = ann.get('t1_s', 0)
            if t1 <= t0:
                continue

            phase_b = [r for r in rows if t0 <= r['t'] <= t1]
            if len(phase_b) < 4:
                continue

            pre_win = [r for r in rows if t0 - _PRE_S <= r['t'] < t0]
            if not pre_win:
                pre_win = phase_b[:min(5, len(phase_b))]

            pw_s  = [(r['pw1'] + r.get('pw2', r['pw1'])) / 2 for r in phase_b]
            pw1_s = [r['pw1'] for r in phase_b]
            pw2_s = [r.get('pw2', r['pw1']) for r in phase_b]
            tps_s = [r['tps'] for r in phase_b]
            rpm_s = [r['rpm'] for r in phase_b]
            vss_s = [r['spd'] for r in phase_b]
            dur   = phase_b[-1]['t'] - phase_b[0]['t']

            _gd_pre = [r['gear_detected'] for r in pre_win if r.get('gear_detected', 0) > 0]
            gear = (max(set(_gd_pre), key=_gd_pre.count) if _gd_pre
                    else int(round(sum(r.get('gear', 0) for r in pre_win) / len(pre_win))))

            bucket_a = {
                'gear':    gear,
                'rpm_avg': round(sum(r['rpm'] for r in pre_win) / len(pre_win), 0),
                'tps_avg': round(sum(r['tps'] for r in pre_win) / len(pre_win), 1),
                'vss_avg': round(sum(r['spd'] for r in pre_win) / len(pre_win), 1),
                'clt_avg': round(sum(r['clt'] for r in pre_win) / len(pre_win), 1),
            }

            _tail_tps = [r['tps'] for r in pre_win[-3:]]
            _full_tps = _tail_tps + tps_s
            _mx = max(_full_tps) if max(_full_tps) > 0 else 1.0
            tps_curve_norm = _f7_resample([v / _mx for v in _full_tps])

            _gw = [r for r in pre_win if r.get('gps_valid') and r.get('gps_alt', 0) != 0]
            if len(_gw) >= 4:
                _alt_d = _gw[-1]['gps_alt'] - _gw[0]['gps_alt']
                _t_sp  = _gw[-1]['t'] - _gw[0]['t']
                _vavg  = sum(r['spd'] for r in _gw) / len(_gw)
                _dist  = _vavg * _t_sp * 1000 / 3600
                gps_slope = round(_alt_d / _dist * 100, 2) if _dist > 5 else 0.0
            else:
                gps_slope = 0.0

            _baro  = [r['baro']      for r in pre_win if r.get('baro',      0) > 0]
            _temp  = [r['temp_amb']  for r in pre_win if r.get('temp_amb',  0) != 0]
            _clt   = [r['clt']       for r in pre_win if r.get('clt',       0) > 0]
            _mat   = [r['mat']       for r in pre_win if r.get('mat',       0) > 0]
            _spark = [r['spark']     for r in pre_win if r.get('spark',     0) > 0]
            _iat   = [r['iat_corr']  for r in pre_win if r.get('iat_corr',  0) > 0]
            _hum   = [r['humidity']  for r in pre_win if r.get('humidity',  0) > 0]
            _alt   = [r['gps_alt']   for r in pre_win
                      if r.get('gps_valid') and r.get('gps_alt', 0) != 0]

            def _pre_rs(vals):
                return _f7_resample(vals, _F7_PRE_N) if vals else [0.0] * _F7_PRE_N

            events.append({
                'event_type':      'accel',
                'break_t':         round(t0, 2),
                'duration':        round(dur, 2),
                'n_raw':           len(phase_b),
                'bucket_a':        bucket_a,
                'pw_curve':        _f7_resample(pw_s),
                'pw1_curve':       _f7_resample(pw1_s),
                'pw2_curve':       _f7_resample(pw2_s),
                'rpm_curve':       _f7_resample(rpm_s),
                'vss_curve':       _f7_resample(vss_s),
                'tps_curve':       _f7_resample(tps_s),
                'tps_curve_norm':  tps_curve_norm,
                'pre_pw_curve':    _pre_rs([(r['pw1']+r.get('pw2',r['pw1']))/2 for r in pre_win]),
                'pre_rpm_curve':   _pre_rs([r['rpm'] for r in pre_win]),
                'pre_vss_curve':   _pre_rs([r['spd'] for r in pre_win]),
                'pre_tps_curve':   _pre_rs([r['tps'] for r in pre_win]),
                'pw_start':        round(pw_s[0], 2),
                'pw_peak':         round(max(pw_s), 2),
                'pw_delta':        round(max(pw_s) - pw_s[0], 2),
                'tps_start':       round(tps_s[0], 1),
                'tps_peak':        round(max(tps_s), 1),
                'vss_delta':       round(vss_s[-1] - vss_s[0], 1),
                'very_short':      dur < 0.5,
                'gps_slope':       gps_slope,
                'baro_hpa':        round(sum(_baro)/len(_baro), 1)  if _baro  else None,
                'temp_amb_c':      round(sum(_temp)/len(_temp), 1)  if _temp  else None,
                'clt_avg':         round(sum(_clt)/len(_clt),   1)  if _clt   else None,
                'mat_avg':         round(sum(_mat)/len(_mat),   1)  if _mat   else None,
                'spark_avg':       round(sum(_spark)/len(_spark),2) if _spark else None,
                'iat_corr_avg':    round(sum(_iat)/len(_iat),   1)  if _iat   else None,
                'humidity_avg':    round(sum(_hum)/len(_hum),   1)  if _hum   else None,
                'gps_alt_avg':     round(sum(_alt)/len(_alt),   1)  if _alt   else None,
                'gear_detected':   gear,
                'ride_file':       ride_stem,
                'annotation_id':   ann['id'],
                'annotation_note': ann.get('note', ''),
            })
    return events

def _f7_load_session_clusters(buell_dir, session_id, threshold=_F7_THRESH):
    """
    Load or compute clusters for a session.
    Per-ride events are cached as ride_*_f7events.json.
    Session clusters cached as session_f7clusters.json.
    Recomputed when any events file is newer than the cluster cache.
    """
    import csv as _csv
    buell_dir = Path(buell_dir)
    sdir      = buell_dir / 'sessions' / session_id

    def _sf(v, default=0.0):
        try:
            return float(v)
        except Exception:
            return default

    def _load_csv_rows(csv_path):
        rows = []
        with open(csv_path) as f:
            lines = [l for l in f if not l.startswith('#')]
        for r in _csv.DictReader(lines):
            try:
                rpm = _sf(r['RPM'])
                if rpm < 100:
                    continue
                _baro = _sf(r.get('baro_hPa', 0))
                _baro_valid = 900 < _baro < 1100
                _baro_factor = 1013.25 / _baro if _baro_valid else 1.0
                rows.append({
                    't':      _sf(r['time_elapsed_s']),
                    'rpm':    rpm,
                    'tps':    _sf(r.get('TPS_pct') or r.get('TPD', 0)),
                    'spd':    _sf(r.get('VS_KPH', 0)),
                    'pw1':    _sf(r['pw1']) * _baro_factor,
                    'pw2':    _sf(r.get('pw2', 0)) * _baro_factor,
                    'gear':          _sf(r.get('Gear', 0)),
                    'gear_detected':  _detect_gear(rpm, _sf(r.get("VS_KPH", 0)), _sf(r.get("di_neutral", 0))),
                    'clt':    _sf(r['CLT']),
                    'ae':      _sf(r.get('Accel_Corr', 100)),
                    'mat':     _sf(r.get('MAT', 0)),
                    'spark':   (_sf(r.get('spark1', 0)) + _sf(r.get('spark2', 0))) / 2,
                    'iat_corr': _sf(r.get('IAT_Corr', 100)),
                    'humidity': _sf(r.get('humidity_pct', 0)),
                    'baro':   _baro,
                    'baro_valid': _baro_valid,
                    'temp_amb':  _sf(r.get('baro_temp_c', 0)),
                    'gps_alt':   _sf(r.get('gps_alt_m', 0)),
                    'gps_valid': r.get('gps_valid', '').strip().lower() in ('true', '1'),
                    'fl_fc':  r.get('fl_fuel_cut', '0').strip() in ('1', 'True', 'true'),
                    'fl_eng': r.get('fl_engine_run', '1').strip() in ('1', 'True', 'true'),
                })
            except Exception:
                continue
        return rows

    # --- Step 1: detect events per ride (incremental cache) ---
    csv_files   = sorted(sdir.glob('ride_*.csv'))
    event_files = []
    for cp in csv_files:
        ef = cp.with_name(cp.stem + '_f7events.json')
        _regen = not ef.exists() or ef.stat().st_mtime < cp.stat().st_mtime
        if not _regen:
            try:
                _s = json.loads(ef.read_text())
                if not _s or 'pre_pw_curve' not in _s[0] or 'mat_avg' not in _s[0]:
                    _regen = True
            except Exception:
                _regen = True
        if _regen:
            rows = _load_csv_rows(cp)
            evs  = _f7_detect_events(rows)
            # strip pw_curve arrays to save space (will re-compute from pw1/pw2)
            ef.write_text(json.dumps(evs, separators=(',', ':')))
        event_files.append(ef)

    csv_path_map = {cp.stem: cp for cp in csv_files}

    # --- Step 2: check cluster cache staleness ---
    thr_tag = str(threshold).replace('.', '_')
    cluster_file = sdir / f'session_f7clusters_{thr_tag}.json'
    ann_files = list(sdir.glob('ride_*_annotations.json'))
    stale = (
        not cluster_file.exists() or
        any(ef.stat().st_mtime > cluster_file.stat().st_mtime for ef in event_files) or
        any(af.stat().st_mtime > cluster_file.stat().st_mtime for af in ann_files)
    )

    if not stale:
        cached = json.loads(cluster_file.read_text())
        if cached.get('threshold') == threshold and cached.get('events_v') == _F7_EVENTS_V:
            return cached
        stale = True

    # --- Step 3: pool all events and cluster ---
    all_events = []
    for ef in event_files:
        try:
            evs = json.loads(ef.read_text())
            for e in evs:
                e['ride_file'] = ef.stem.replace('_f7events', '')
            all_events.extend(evs)
        except Exception:
            continue

    # Cluster accel and decel separately so type-mixed DTW is avoided
    _accel_evs = [e for e in all_events if e.get('event_type', 'accel') == 'accel']
    _decel_evs = [e for e in all_events if e.get('event_type') == 'decel']
    _accel_cls = _f7_cluster(_accel_evs, threshold=threshold)
    _decel_cls = _f7_cluster(_decel_evs, threshold=threshold)
    for i, c in enumerate(_accel_cls):
        c['cluster_id']   = f'A{i+1:03d}'
        c['cluster_type'] = 'accel'
    for i, c in enumerate(_decel_cls):
        c['cluster_id']   = f'D{i+1:03d}'
        c['cluster_type'] = 'decel'
    clusters = _accel_cls + _decel_cls
    for c in clusters:
        _f7_temporal_stats(c)

    # --- Step 4: pilot-marked events from 'launch' annotations ---
    pilot_events = _f7_events_from_annotations(sdir, csv_path_map, _load_csv_rows)
    _pilot_cls = _f7_cluster(pilot_events, threshold=threshold)
    for i, c in enumerate(_pilot_cls):
        c['cluster_id']   = f'P{i+1:03d}'
        c['cluster_type'] = 'pilot-marked'
    for c in _pilot_cls:
        _f7_temporal_stats(c)

    result = {
        'session_id':     session_id,
        'events_v':       _F7_EVENTS_V,
        'n_events':       len(all_events),
        'n_accel':        len(_accel_evs),
        'n_decel':        len(_decel_evs),
        'n_clusters':     len(clusters),
        'n_pilot':        len(pilot_events),
        'n_rides':        len(event_files),
        'threshold':      threshold,
        'clusters':       clusters,
        'pilot_clusters': _pilot_cls,
    }
    cluster_file.write_text(json.dumps(result, separators=(',', ':')))
    return result


