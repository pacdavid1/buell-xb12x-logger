# DEV NOTE: All code, comments, and variable names must be in English.
"""web/proposal.py — FASE 6 Phase 4: generate a burnable EEPROM map proposal
from two compared sessions, and optionally save it as a PROP_* session.

Scope decisions (deviate from BACKLOG_PROPOSAL_V2.md's original task 4.3):

1. The plan described converting the smoothed dpw_eff delta into a percentage
   correction applied to a reference map ("proposed = current * (1 + delta)").
   That requires knowing, with certainty, which direction (more or less PW)
   counts as the "winning" one for a given flavor/zone -- reverse-engineering
   that sign convention wrong would silently propose a WRONG-directioned
   change into something that can eventually be burned to the ECU. Instead,
   every proposed value here is either session A's or session B's OWN
   already-driven map value at that cell -- never a synthesized new number.
   A percentage-delta synthesis path is a legitimate future upgrade, but
   needs the winner-direction semantics confirmed by a human first.

2. Cells with NO real decision (no vs_delta vote, no F7 fusion, no GP fill --
   i.e. genuinely untested) are left at the REFERENCE map's own value,
   unchanged. vs_engine._merge_maps() instead averages A/B for its own
   interactive-comparison use case, which is reasonable for a human looking
   at a display. It is NOT reasonable for this automated pipeline: per
   BACKLOG_VDYNO.md rule 1, the system should not change what the data
   doesn't support. Same logic for BALANCE-mode conflicts (eco and sport
   disagree): stay at reference rather than blend, since a conflict is not
   evidence to act on automatically.

3. Spark maps are NOT adjusted -- this pipeline (dpw_eff, F7 delta_pw) is a
   fuel/PW signal only; there is no spark-timing correction computed
   anywhere upstream. Spark maps always carry the reference session's own
   values unchanged.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ecu.eeprom import decode_eeprom_maps as _decode_eeprom_maps, encode_eeprom_maps as _encode_eeprom_maps
from web.utils import _session_version
from web.vs_engine import _build_ci, _maps_differ, RPM_BINS, TPS_BINS, _bin_index

MAX_CHANGE_PCT = 0.15
FUEL_KEYS = ('fuel_front', 'fuel_rear')
SPARK_KEYS = ('spark_front', 'spark_rear')


def _clamp_to_reference(value, reference, max_pct=MAX_CHANGE_PCT):
    """Cap a proposed cell value to within max_pct of the reference value
    (BACKLOG_VDYNO.md safety rule: no cell change >15% per iteration)."""
    if not reference:
        return value
    lo, hi = reference * (1 - max_pct), reference * (1 + max_pct)
    return max(lo, min(hi, value))


def _propose_grid(ci, mode, ra, la, mA_grid, mB_grid, reference_grid):
    """Build one map's proposed grid. Only cells with a real ci decision get
    changed (clamped to +/-15% of the reference); everything else stays at
    the reference value, untouched."""
    def m2ck(i, j):
        rv = ra[j]; lv = la[i]
        if rv == 0:
            return None
        rc = (rv + ra[j + 1]) / 2 if j < len(ra) - 1 else (rv + (rv - ra[j - 1]) / 2 if j > 0 else rv)
        lc = (lv + la[i + 1]) / 2 if i < len(la) - 1 else (lv + (lv - la[i - 1]) / 2 if i > 0 else lv)
        if rc < RPM_BINS[0] or lc < TPS_BINS[0]:
            return None
        return (_bin_index(rc, RPM_BINS), _bin_index(lc, TPS_BINS))

    def winner(key):
        info = ci.get(key)
        if not info:
            return None
        ew, sw = info.get('eco'), info.get('sport')
        if mode == 'ECO':
            return ew
        if mode == 'SPORT':
            return sw
        if ew and sw and ew != sw:
            return None  # conflicting signals -- not evidence to act on automatically
        return ew or sw

    rows = len(la)
    cols = len(ra)
    out = []
    changed = 0
    max_pct = 0.0
    for i in range(rows):
        row = []
        for j in range(cols):
            ref_v = reference_grid[i][j] if i < len(reference_grid) and j < len(reference_grid[i]) else None
            key = m2ck(i, j)
            w = winner(key) if key else None
            if w is None or ref_v is None:
                row.append(ref_v)
                continue
            picked = mA_grid[i][j] if w == 'A' else mB_grid[i][j]
            v = _clamp_to_reference(picked, ref_v)
            if ref_v and round(v, 1) != round(ref_v, 1):
                changed += 1
                max_pct = max(max_pct, abs(v - ref_v) / ref_v)
            row.append(round(v, 1))
        out.append(row)
    return out, changed, max_pct


def generate_proposal(buell_dir, sa, sb, params=None):
    """Build a proposed map set from sessions sa/sb. Dry run -- no disk writes.

    params: {'mode': 'ECO'/'SPORT'/'BALANCE', 'reference': 'A'/'B' (default 'B')}
    Returns {'ok': False, 'error': ...} on failure, else {'ok': True, ...}.
    """
    params = params or {}
    mode = params.get('mode', 'BALANCE')
    reference = 'A' if params.get('reference') == 'A' else 'B'
    buell_dir = Path(buell_dir)

    ep_a = buell_dir / 'sessions' / sa / 'eeprom.bin'
    ep_b = buell_dir / 'sessions' / sb / 'eeprom.bin'
    if not ep_a.exists() or not ep_b.exists():
        return {'ok': False, 'error': 'eeprom.bin not found for one or both sessions'}
    ver_a, ver_b = _session_version(ep_a), _session_version(ep_b)
    mA = _decode_eeprom_maps(ep_a.read_bytes(), ver_a)
    mB = _decode_eeprom_maps(ep_b.read_bytes(), ver_b)
    changed_maps = [k for k in FUEL_KEYS + SPARK_KEYS
                    if k in mA and k in mB and _maps_differ(mA[k], mB[k])]
    if not changed_maps:
        return {'ok': False, 'error': 'No changes between sessions'}

    ref_maps, ref_ver, ref_bin = (mA, ver_a, ep_a) if reference == 'A' else (mB, ver_b, ep_b)
    ci, _delta, stats = _build_ci(buell_dir, sa, sb)

    proposed = {}
    cells_changed = 0
    max_delta_pct = 0.0
    for ck in FUEL_KEYS:
        if ck not in ref_maps:
            continue
        if ck not in changed_maps:
            proposed[ck] = [row[:] for row in ref_maps[ck]]
            continue
        ra = mA['axes']['fuel_rpm']
        la = mA['axes']['fuel_load']
        grid, changed, pct = _propose_grid(ci, mode, ra, la, mA[ck], mB[ck], ref_maps[ck])
        proposed[ck] = grid
        cells_changed += changed
        max_delta_pct = max(max_delta_pct, pct)
    for ck in SPARK_KEYS:
        if ck in ref_maps:
            proposed[ck] = [row[:] for row in ref_maps[ck]]

    return {
        'ok': True,
        'source_sessions': [sa, sb],
        'reference': reference,
        'mode': mode,
        'proposed': proposed,
        'axes': ref_maps.get('axes', {}),
        'reference_version': ref_ver,
        'stats': {
            'cells_with_data': len(ci),
            'skipped_insignificant': stats['skipped_insignificant'],
            'fused_with_f7': stats['fused_with_f7'],
            'filled_by_gp': stats['filled_by_gp'],
            'cells_changed': cells_changed,
            'max_delta_pct': round(max_delta_pct * 100, 2),
        },
        '_ref_bin_bytes': ref_bin.read_bytes(),
        '_ref_version': ref_ver,
    }


def save_proposal(buell_dir, result):
    """Persist a generate_proposal() result as sessions/PROP_YYYYMMDD_HHMMSS/.

    Format matches BACKLOG.md's FASE 6 spec: session_metadata.json (checksum=
    PROP_*, version_string='proposal', total_rides=0 so Tuner lists it without
    ride data), eeprom_decoded.json (maps + axes, for display),
    eeprom.bin (encoded, for burning), proposal_metadata.json (provenance),
    current_eeprom_decoded.json (the reference map, for before/after diffing).
    """
    if not result.get('ok'):
        raise ValueError('cannot save a failed proposal result')
    buell_dir = Path(buell_dir)
    ts = time.strftime('%Y%m%d_%H%M%S')
    prop_id = f'PROP_{ts}'
    sdir = buell_dir / 'sessions' / prop_id
    sdir.mkdir(parents=True, exist_ok=False)

    ref_maps = _decode_eeprom_maps(result['_ref_bin_bytes'], result['_ref_version'])
    eeprom_bytes = _encode_eeprom_maps(result['_ref_bin_bytes'], result['proposed'], result['_ref_version'])

    (sdir / 'session_metadata.json').write_text(json.dumps({
        'checksum': prop_id,
        'version_string': result['_ref_version'] or 'proposal',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'total_rides': 0,
        'total_samples': 0,
        'total_runtime_seconds': 0,
    }, indent=2))
    (sdir / 'eeprom_decoded.json').write_text(json.dumps({
        'params': {},
        'maps': {**result['proposed'], 'axes': result['axes']},
    }, indent=2))
    (sdir / 'eeprom.bin').write_bytes(eeprom_bytes)
    (sdir / 'current_eeprom_decoded.json').write_text(json.dumps({
        'params': {},
        'maps': ref_maps,
    }, indent=2))
    (sdir / 'proposal_metadata.json').write_text(json.dumps({
        'source_sessions': result['source_sessions'],
        'reference': result['reference'],
        'mode': result['mode'],
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'stats': result['stats'],
    }, indent=2))
    return prop_id
