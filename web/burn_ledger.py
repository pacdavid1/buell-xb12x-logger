# DEV NOTE: All code, comments, and variable names must be in English.
"""Burn ledger — append-only record of every EEPROM burn (VDYNO phase V0).

Each entry links a parent map (tune checksum the bike was running) to the
child map (tune checksum of the proposed EEPROM), with the exact cells that
changed. After a verified burn the logger opens a new session from the
proposed blob, so a child checksum equals the future session ID — lineage
joins against existing session data with no extra mapping.

This module only RECORDS burns. It never writes to the ECU.
See docs/11_VDYNO_PLAN.md and BACKLOG_VDYNO.md.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LEDGER_NAME = 'burns.json'
# Tune region starts here — volatile bytes before it (counters, DTCs, boot
# state) are excluded. Must match SessionManager._checksum in ecu/session.py.
TUNE_REGION_OFFSET = 327
MAX_CELLS_STORED = 200
_CELL_EPSILON = 1e-6


def tune_checksum(blob: bytes) -> str:
    """Map identity — same hash as SessionManager._checksum (session IDs)."""
    return hashlib.md5(blob[TUNE_REGION_OFFSET:]).hexdigest()[:6].upper()


def diff_maps(old_maps: dict, new_maps: dict) -> list:
    """List cells that differ between two decoded map dicts.

    Both dicts come from decode_eeprom_maps: {map_key: [[float]]}.
    Returns [{'map', 'ri', 'ci', 'old', 'new'}] in stable iteration order.
    """
    cells = []
    for map_key in sorted(new_maps):
        new_table = new_maps[map_key]
        old_table = old_maps.get(map_key)
        if not isinstance(new_table, list) or not isinstance(old_table, list):
            continue
        for ri, new_row in enumerate(new_table):
            if ri >= len(old_table):
                break
            old_row = old_table[ri]
            for ci, new_val in enumerate(new_row):
                if ci >= len(old_row):
                    break
                old_val = old_row[ci]
                if old_val is None or new_val is None:
                    if old_val is not new_val:
                        cells.append({'map': map_key, 'ri': ri, 'ci': ci,
                                      'old': old_val, 'new': new_val})
                    continue
                if abs(float(new_val) - float(old_val)) > _CELL_EPSILON:
                    cells.append({'map': map_key, 'ri': ri, 'ci': ci,
                                  'old': round(float(old_val), 3),
                                  'new': round(float(new_val), 3)})
    return cells


def build_entry(current_bin: bytes, proposed_bin: bytes, decoded_old: dict,
                decoded_new: dict, source_session: str, verified: bool,
                backup_name: str) -> dict:
    """Assemble one ledger entry from a burn's inputs and outcome."""
    cells = diff_maps(decoded_old, decoded_new)
    return {
        'ts_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'parent': tune_checksum(current_bin),
        'child': tune_checksum(proposed_bin),
        'source_session': source_session,
        'verified': bool(verified),
        'n_cells': len(cells),
        'cells': cells[:MAX_CELLS_STORED],
        'maps_touched': sorted({c['map'] for c in cells}),
        'backup': backup_name,
    }


def load_burns(buell_dir) -> list:
    """Read the ledger; missing or corrupt file yields an empty list."""
    path = Path(buell_dir) / LEDGER_NAME
    if not path.exists():
        return []
    try:
        burns = json.loads(path.read_text())
        return burns if isinstance(burns, list) else []
    except Exception:
        return []


def record_burn(buell_dir, entry: dict) -> None:
    """Append one entry to burns.json atomically (tmp file + os.replace)."""
    path = Path(buell_dir) / LEDGER_NAME
    burns = load_burns(buell_dir) + [entry]
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(burns, indent=1))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# GAP 5 — Map convergence metric
# A cell is "converged" when its last delta is < 1% of its current value.
# Global score = % of active cells (touched in ≥1 burn) that are converged.
# Status thresholds: converged ≥80%, converging ≥40%, else diverging.
# ---------------------------------------------------------------------------
_CONVERGE_REL   = 0.01   # 1% of cell value = converged threshold
_CONVERGE_ABS   = 0.05   # absolute floor so near-zero cells aren't trivial
_CONVERGE_BURNS = 3      # number of recent burns used to evaluate trend


def _delta_trend(deltas: list) -> str:
    """Qualitative trend: improving / stable / worsening based on last 4 deltas."""
    if len(deltas) < 3:
        return 'unknown'
    recent = deltas[-4:]
    if recent[-1] < recent[0] * 0.6:
        return 'improving'
    if recent[-1] > recent[0] * 1.4:
        return 'worsening'
    return 'stable'


def convergence_report(buell_dir) -> dict:
    """GAP 5: summarise how close the map is to convergence.

    Returns::
        {
          'status':         'converged' | 'converging' | 'diverging' | 'no_data',
          'score':          int (% of active cells converged) or None,
          'burns':          int,
          'n_active_cells': int,
          'n_converged':    int,
          'cells':          [per-cell detail, sorted worst-first],
        }
    """
    burns = load_burns(buell_dir)
    if not burns:
        return {'status': 'no_data', 'score': None, 'burns': 0,
                'n_active_cells': 0, 'n_converged': 0, 'cells': []}

    # Collect delta history per cell key across all burns (chronological).
    cell_hist: dict = {}
    for burn in burns:
        ts = burn.get('ts_utc', '')
        for cell in burn.get('cells', []):
            key = f"{cell['map']}:{cell['ri']},{cell['ci']}"
            old_v = cell.get('old')
            new_v = cell.get('new')
            if old_v is None or new_v is None:
                continue
            delta = abs(float(new_v) - float(old_v))
            cell_hist.setdefault(key, []).append(
                {'ts': ts, 'delta': delta, 'val': float(new_v)})

    if not cell_hist:
        return {'status': 'no_data', 'score': None, 'burns': len(burns),
                'n_active_cells': 0, 'n_converged': 0, 'cells': []}

    cells_out = []
    n_converged = 0

    for key, history in cell_hist.items():
        last_val = history[-1]['val']
        threshold = max(_CONVERGE_ABS, abs(last_val) * _CONVERGE_REL)
        recent = history[-_CONVERGE_BURNS:]
        all_deltas = [h['delta'] for h in history]
        converged = all(h['delta'] < threshold for h in recent)
        map_name, rc = key.split(':')
        ri, ci = rc.split(',')
        cells_out.append({
            'key':        key,
            'map':        map_name,
            'ri':         int(ri),
            'ci':         int(ci),
            'n_burns':    len(history),
            'last_delta': round(history[-1]['delta'], 4),
            'threshold':  round(threshold, 4),
            'converged':  converged,
            'trend':      _delta_trend(all_deltas),
        })
        if converged:
            n_converged += 1

    n_active = len(cells_out)
    score = round(100 * n_converged / n_active) if n_active else None

    if score is None or n_active == 0:
        status = 'no_data'
    elif score >= 80:
        status = 'converged'
    elif score >= 40:
        status = 'converging'
    else:
        status = 'diverging'

    return {
        'status':         status,
        'score':          score,
        'burns':          len(burns),
        'n_active_cells': n_active,
        'n_converged':    n_converged,
        'cells':          sorted(cells_out, key=lambda c: c['last_delta'], reverse=True),
    }
