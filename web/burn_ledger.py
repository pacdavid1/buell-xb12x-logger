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
