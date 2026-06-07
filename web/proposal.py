# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.
"""
proposal.py — FASE 6: unified map proposal engine.

Generates per-EEPROM-cell fuel deltas by mapping Sessions VS dpw_eff
onto the nearest EEPROM cell. v1: VS signal only, fuel maps only.
v2 will add F7 cross-session events and zone arbitration.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from web.smoothing import smooth_all_maps
from web.vs_engine import _compare_sessions_cached

log = logging.getLogger('Proposal')

MAX_DELTA     = 0.15   # ±15% per iteration safety clamp
MIN_SAMPLES   = 5      # minimum rows per VS cell to trust the signal
MIN_DELTA_PCT = 0.005  # ignore deltas smaller than 0.5% (noise floor)
SWEET_FLAVORS  = {'SWEET', 'SPICY_WOT'}
ZONE_WOT_THRESH = 85.0   # tps_center >= 85%: VS only (rare F7 WOT events)
ZONE_MID_THRESH = 40.0   # tps_center 40-85%: F7 + VS weighted fusion


def _clamp(v, max_delta=MAX_DELTA):
    return max(-max_delta, min(max_delta, v))


def _find_cell(value, axis):
    """Return EEPROM bin index. bin[i] covers axis[i] <= value < axis[i+1]."""
    import bisect
    idx = bisect.bisect_right(axis, value) - 1
    return max(0, min(idx, len(axis) - 1))


def _vs_bin_center(lo, step=None, axis_values=None):
    """Return the center of a VS bin given its lower edge."""
    # VS bins are roughly 400 RPM wide for RPM, 5 wide for TPS
    if step:
        return lo + step / 2
    return lo  # fallback


def _classify_zone(tps_center):
    if tps_center >= ZONE_WOT_THRESH:
        return 'WOT'
    if tps_center >= ZONE_MID_THRESH:
        return 'Mid'
    return 'Light'


def _compute_f7_delta(buell_dir, session_a, session_b, fuel_rpm, fuel_load):
    """Compute per-EEPROM-cell fuel deltas from F7 cross-session cluster matching.
    Returns (f7_ff, f7_fr, f7_conf, f7_src) or None if no clusters available.
    """
    from web.f7 import _f7_load_session_clusters, _f7_match_cross_session

    data_a = _f7_load_session_clusters(buell_dir, session_a)
    data_b = _f7_load_session_clusters(buell_dir, session_b)
    if not data_a or not data_b:
        return None
    clusters_a = data_a.get('clusters', [])
    clusters_b = data_b.get('clusters', [])
    if not clusters_a or not clusters_b:
        return None

    ca_by_id = {cl['cluster_id']: cl for cl in clusters_a}
    matches  = _f7_match_cross_session(clusters_a, clusters_b)

    n_rows, n_cols = len(fuel_load), len(fuel_rpm)
    f7_ff   = [[0.0]    * n_cols for _ in range(n_rows)]
    f7_fr   = [[0.0]    * n_cols for _ in range(n_rows)]
    f7_conf = [[0.0]    * n_cols for _ in range(n_rows)]
    f7_src  = [['none'] * n_cols for _ in range(n_rows)]
    f7_tpk  = [[0.0]    * n_cols for _ in range(n_rows)]

    for match in matches:
        ba = match['bucket_a']
        ca = ca_by_id.get(match['cluster_a_id'])
        if not ca:
            continue
        tps_pk = max((m.get('tps_peak', 0) for m in ca.get('members', []) if m.get('tps_peak', 0) > 0), default=0)
        ri = _find_cell(tps_pk if tps_pk > 0 else ba['tps_center'], fuel_load)
        ci = _find_cell(ba['rpm_center'], fuel_rpm)
        sa     = ca.get('stats', {})
        pw1_a  = sa.get('pw1_avg', sa.get('pw_avg', []))
        pw2_a  = sa.get('pw2_avg', sa.get('pw_avg', []))
        dpw1   = match.get('delta_pw1', match['delta_pw'])
        dpw2   = match.get('delta_pw2', match['delta_pw'])

        mean_pw1  = sum(pw1_a) / len(pw1_a) if pw1_a else 0
        mean_pw2  = sum(pw2_a) / len(pw2_a) if pw2_a else 0
        mean_dpw1 = sum(dpw1)  / len(dpw1)  if dpw1  else 0
        mean_dpw2 = sum(dpw2)  / len(dpw2)  if dpw2  else 0

        dpct_ff = _clamp(mean_dpw1 / mean_pw1) if mean_pw1 > 0 else 0.0
        dpct_fr = _clamp(mean_dpw2 / mean_pw2) if mean_pw2 > 0 else 0.0

        if abs(dpct_ff) < MIN_DELTA_PCT and abs(dpct_fr) < MIN_DELTA_PCT:
            continue

        conf = match['tps_dtw'] * min((match['n_a'] + match['n_b']) / 4.0, 1.0)
        if conf > f7_conf[ri][ci]:
            f7_ff[ri][ci]   = dpct_ff
            f7_fr[ri][ci]   = dpct_fr
            f7_conf[ri][ci] = conf
            f7_src[ri][ci]  = 'f7'
            f7_tpk[ri][ci]  = tps_pk

    return f7_ff, f7_fr, f7_conf, f7_src, f7_tpk


def save_proposal(buell_dir, session_a, session_b,
                  smoothed_front_pct, smoothed_rear_pct,
                  current_eeprom_decoded, summary):
    """
    Save a PROPOSAL session to disk.
    smoothed_front_pct / smoothed_rear_pct: 12x13 arrays in PERCENTAGE units (15 = 15%).
    Creates PROP_YYYYMMDD_HHMMSS/ with session_metadata, eeprom_decoded,
    eeprom.bin, and proposal_metadata.
    Returns path to PROP_* directory or None on failure.
    """
    try:
        ff_cur = np.array(current_eeprom_decoded['maps']['fuel_front'], dtype=float)
        fr_cur = np.array(current_eeprom_decoded['maps']['fuel_rear'],  dtype=float)
        d_ff   = np.array(smoothed_front_pct, dtype=float)
        d_fr   = np.array(smoothed_rear_pct,  dtype=float)

        prop_ff = np.clip(np.round(ff_cur * (1.0 + d_ff / 100.0)), 0, 250).astype(int)
        prop_fr = np.clip(np.round(fr_cur * (1.0 + d_fr / 100.0)), 0, 250).astype(int)

        proposed_maps = {
            'axes':        current_eeprom_decoded['maps']['axes'],
            'fuel_front':  prop_ff.tolist(),
            'fuel_rear':   prop_fr.tolist(),
            'spark_front': current_eeprom_decoded['maps']['spark_front'],
            'spark_rear':  current_eeprom_decoded['maps']['spark_rear'],
        }
        proposed_eeprom = {
            'params': current_eeprom_decoded.get('params', {}),
            'maps':   proposed_maps,
        }

        ts = datetime.now(timezone.utc)
        prop_name = 'PROP_' + ts.strftime('%Y%m%d_%H%M%S')
        prop_path = str(Path(buell_dir) / 'sessions' / prop_name)
        os.makedirs(prop_path, exist_ok=True)

        meta = {
            'checksum': prop_name, 'version_string': 'proposal',
            'created_utc': ts.isoformat(),
            'total_rides': 0, 'total_samples': 0,
            'total_runtime_seconds': 0,
            'rpm_min_seen': 0, 'rpm_max_seen': 0,
            'rider_notes': [],
        }
        with open(os.path.join(prop_path, 'session_metadata.json'), 'w') as f:
            json.dump(meta, f, indent=2)

        with open(os.path.join(prop_path, 'eeprom_decoded.json'), 'w') as f:
            json.dump(proposed_eeprom, f, indent=2)

        # Generate eeprom.bin from session_a's original binary
        orig_bin = Path(buell_dir) / 'sessions' / session_a / 'eeprom.bin'
        if orig_bin.exists():
            from ecu.eeprom import encode_eeprom_maps
            proposed_binary = encode_eeprom_maps(orig_bin.read_bytes(), proposed_maps)
            with open(os.path.join(prop_path, 'eeprom.bin'), 'wb') as f:
                f.write(proposed_binary)

        prop_meta = {
            'type': 'proposal', 'generated_utc': ts.isoformat(),
            'source_sessions': [session_a, session_b],
            'cells_with_signal':  summary.get('cells_with_signal', 0),
            'cells_interpolated': summary.get('cells_interpolated', 0),
            'smoothing_applied':  summary.get('smoothing', 'IDW + Laplacian'),
            'max_delta_pct':      summary.get('max_delta_pct', MAX_DELTA * 100),
        }
        with open(os.path.join(prop_path, 'proposal_metadata.json'), 'w') as f:
            json.dump(prop_meta, f, indent=2)

        log.info(f'Proposal saved: {prop_name} ({summary.get("cells_with_signal",0)} signal cells)')
        return prop_path

    except Exception as e:
        log.error(f'save_proposal failed: {e}')
        return None



def generate_fuel_proposal(buell_dir, session_a, session_b, config=None):
    """
    Generate a fuel map proposal for session_a's EEPROM using Sessions VS data.

    Returns a dict with:
      - delta_fuel_front[row][col]: fractional delta to apply to fuel_front
      - delta_fuel_rear[row][col]:  fractional delta to apply to fuel_rear
      - confidence[row][col]:       0.0-1.0 per cell
      - source[row][col]:           'vs_sweet' | 'vs_wot' | 'none'
      - axes: fuel_rpm and fuel_load bin edges from the EEPROM
      - coverage: count of VS rows mapped per EEPROM cell
      - summary: stats for the proposal
    """
    buell_dir = Path(buell_dir)
    config = config or {}
    max_delta   = config.get('max_delta_pct', MAX_DELTA)
    min_samples = config.get('min_samples', MIN_SAMPLES)

    # Load EEPROM axes — decode from eeprom.bin directly (always present)
    # eeprom_decoded.json may not exist in older sessions; don't require it
    from ecu.eeprom import decode_eeprom_maps
    bin_path = buell_dir / 'sessions' / session_a / 'eeprom.bin'
    if not bin_path.exists():
        bin_path = buell_dir / 'sessions' / session_b / 'eeprom.bin'
    if not bin_path.exists():
        return {'error': f'No eeprom.bin found for sessions {session_a} or {session_b}'}
    eeprom = {'maps': decode_eeprom_maps(bin_path.read_bytes()), 'params': {}}

    axes      = eeprom['maps']['axes']
    fuel_rpm  = axes['fuel_rpm']   # list of RPM edges, len=13
    fuel_load = axes['fuel_load']  # list of TPS/load edges, len=12
    n_rows = len(fuel_load)
    n_cols = len(fuel_rpm)

    # Initialize grids
    delta_ff   = [[0.0]    * n_cols for _ in range(n_rows)]
    delta_fr   = [[0.0]    * n_cols for _ in range(n_rows)]
    confidence = [[0.0]    * n_cols for _ in range(n_rows)]
    source     = [['none'] * n_cols for _ in range(n_rows)]
    coverage   = [[0]      * n_cols for _ in range(n_rows)]

    # Get Sessions VS delta for this pair (already baro-normalized)
    vs = _compare_sessions_cached(buell_dir, session_a, session_b)
    delta_rows = vs.get('delta', [])

    mapped = 0
    skipped_samples = 0
    skipped_noise = 0

    for row in delta_rows:
        flavor = row.get('flavor', '')
        if flavor not in SWEET_FLAVORS:
            continue
        if row['na'] < min_samples or row['nb'] < min_samples:
            skipped_samples += 1
            continue

        # VS bin center → EEPROM cell
        rpm_center = row['rpm_lo'] + 200   # VS RPM bins are ~400 wide
        tps_center = row['tps_lo'] + 2.5   # VS TPS bins are ~5 wide

        ri = _find_cell(tps_center, fuel_load)
        ci = _find_cell(rpm_center, fuel_rpm)

        # Front (pw1) and rear (pw2) deltas computed independently
        pw1_a = row.get('pw1_a', 0)
        pw2_a = row.get('pw2_a', row.get('pw1_a', 0))
        if pw1_a <= 0 and pw2_a <= 0:
            continue

        dpw1 = row.get('dpw1', row.get('dpw_eff', 0))
        dpw2 = row.get('dpw2', dpw1)

        dpct_ff = _clamp(dpw1 / pw1_a, max_delta) if pw1_a > 0 else 0.0
        dpct_fr = _clamp(dpw2 / pw2_a, max_delta) if pw2_a > 0 else 0.0

        if abs(dpct_ff) < MIN_DELTA_PCT and abs(dpct_fr) < MIN_DELTA_PCT:
            skipped_noise += 1
            continue

        n_total = row['na'] + row['nb']
        conf = min(1.0, n_total / 200.0)

        if conf > confidence[ri][ci]:
            delta_ff[ri][ci]   = dpct_ff
            delta_fr[ri][ci]   = dpct_fr
            confidence[ri][ci] = conf
            source[ri][ci]     = f'vs_{flavor.lower()}'

        coverage[ri][ci] += 1
        mapped += 1

    # F7 delta + zone-based fusion (FASE 6 v2)
    f7_result = _compute_f7_delta(buell_dir, session_a, session_b, fuel_rpm, fuel_load)
    if f7_result:
        f7_ff, f7_fr, f7_conf, f7_src, f7_tpk = f7_result
        for ri in range(n_rows):
            tps_lo = fuel_load[ri]
            tps_hi = fuel_load[ri + 1] if ri + 1 < len(fuel_load) else tps_lo + 10
            cell_tps_mid = (tps_lo + tps_hi) / 2
            for ci in range(n_cols):
                has_vs = source[ri][ci] != 'none'
                has_f7 = f7_src[ri][ci] != 'none'
                zone   = _classify_zone(f7_tpk[ri][ci] if has_f7 and f7_tpk[ri][ci] > 0 else cell_tps_mid)
                if not has_f7 or zone == 'WOT':
                    continue
                if zone == 'Mid' and has_vs:
                    vs_w, f7_w = confidence[ri][ci], f7_conf[ri][ci]
                    total_w = vs_w + f7_w
                    if total_w > 0:
                        if delta_ff[ri][ci] * f7_ff[ri][ci] < 0:
                            fused_ff = max(delta_ff[ri][ci], f7_ff[ri][ci])
                        else:
                            fused_ff = (delta_ff[ri][ci] * vs_w + f7_ff[ri][ci] * f7_w) / total_w
                        if delta_fr[ri][ci] * f7_fr[ri][ci] < 0:
                            fused_fr = max(delta_fr[ri][ci], f7_fr[ri][ci])
                        else:
                            fused_fr = (delta_fr[ri][ci] * vs_w + f7_fr[ri][ci] * f7_w) / total_w
                        delta_ff[ri][ci]   = _clamp(fused_ff)
                        delta_fr[ri][ci]   = _clamp(fused_fr)
                        confidence[ri][ci] = max(vs_w, f7_w)
                        source[ri][ci]     = 'f7_vs_fusion'
                else:
                    if not has_vs or f7_conf[ri][ci] > confidence[ri][ci]:
                        delta_ff[ri][ci]   = f7_ff[ri][ci]
                        delta_fr[ri][ci]   = f7_fr[ri][ci]
                        confidence[ri][ci] = f7_conf[ri][ci]
                        source[ri][ci]     = 'f7'

    cells_with_signal = sum(1 for r in range(n_rows) for c in range(n_cols) if source[r][c] != 'none')

    log.info(f'Proposal {session_a} vs {session_b}: {mapped} VS rows mapped, '
             f'{cells_with_signal}/{n_rows*n_cols} EEPROM cells with signal')

    # Apply smoothing: IDW interpolation + Laplacian
    # smoothing.py works in percentage units (e.g. 15 = 15%)
    # our deltas are fractions (e.g. 0.15 = 15%) -> scale up, then back
    delta_front_np = np.array(delta_ff, dtype=float) * 100
    delta_rear_np  = np.array(delta_fr, dtype=float) * 100
    signal_mask    = np.array([[s != 'none' for s in row] for row in source])
    smoothed_front_pct, smoothed_rear_pct = smooth_all_maps(
        delta_front_np, delta_rear_np, signal_mask, map_type='fuel'
    )
    smoothed_front = smoothed_front_pct / 100
    smoothed_rear  = smoothed_rear_pct  / 100

    # Store pct versions for save_proposal (expects % not fractions)
    smoothed_ff_pct = (smoothed_front * 100).tolist()
    smoothed_fr_pct = (smoothed_rear  * 100).tolist()

    return {
        'session_a': session_a,
        'session_b': session_b,
        'axes': {'fuel_rpm': fuel_rpm, 'fuel_load': fuel_load},
        'smoothed_pct': {
            'delta_fuel_front': smoothed_ff_pct,
            'delta_fuel_rear':  smoothed_fr_pct,
        },
        'raw': {
            'delta_fuel_front': delta_ff,
            'delta_fuel_rear':  delta_fr,
            'confidence':       confidence,
            'source':           source,
            'coverage':         coverage,
        },
        'smoothed': {
            'delta_fuel_front': smoothed_front.tolist(),
            'delta_fuel_rear':  smoothed_rear.tolist(),
            'signal_mask':      signal_mask.tolist(),
        },
        'summary': {
            'cells_total':       n_rows * n_cols,
            'cells_with_signal': cells_with_signal,
            'vs_rows_mapped':    mapped,
            'skipped_low_n':     skipped_samples,
            'skipped_noise':     skipped_noise,
            'max_delta_pct':     max_delta,
            'min_samples':       min_samples,
            'f7_available':      f7_result is not None,
            'smoothing':         'IDW + Laplacian',
        },
    }
