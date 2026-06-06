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
from pathlib import Path

from web.vs_engine import _compare_sessions_cached

log = logging.getLogger('Proposal')

MAX_DELTA     = 0.15   # ±15% per iteration safety clamp
MIN_SAMPLES   = 5      # minimum rows per VS cell to trust the signal
MIN_DELTA_PCT = 0.005  # ignore deltas smaller than 0.5% (noise floor)
SWEET_FLAVORS = {'SWEET', 'SPICY_WOT'}


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

    # Load EEPROM axes from session A
    ep_path = buell_dir / 'sessions' / session_a / 'eeprom_decoded.json'
    if not ep_path.exists():
        return {'error': f'No eeprom_decoded.json for session {session_a}'}

    with open(ep_path) as f:
        eeprom = json.load(f)

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

        def _clamp(v):
            return max(-max_delta, min(max_delta, v))

        dpct_ff = _clamp(dpw1 / pw1_a) if pw1_a > 0 else 0.0
        dpct_fr = _clamp(dpw2 / pw2_a) if pw2_a > 0 else 0.0

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

    cells_with_signal = sum(1 for r in range(n_rows) for c in range(n_cols) if source[r][c] != 'none')

    log.info(f'Proposal {session_a} vs {session_b}: {mapped} VS rows mapped, '
             f'{cells_with_signal}/{n_rows*n_cols} EEPROM cells with signal')

    return {
        'session_a':        session_a,
        'session_b':        session_b,
        'delta_fuel_front': delta_ff,
        'delta_fuel_rear':  delta_fr,
        'confidence':       confidence,
        'source':           source,
        'coverage':         coverage,
        'axes': {
            'fuel_rpm':  fuel_rpm,
            'fuel_load': fuel_load,
        },
        'summary': {
            'cells_total':       n_rows * n_cols,
            'cells_with_signal': cells_with_signal,
            'vs_rows_mapped':    mapped,
            'skipped_low_n':     skipped_samples,
            'skipped_noise':     skipped_noise,
            'max_delta_pct':     max_delta,
            'min_samples':       min_samples,
        },
    }
