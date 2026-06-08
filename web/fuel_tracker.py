# DEV NOTE: All code, comments, and variable names must be in English.
"""Fuel tracking — reserve activation, fill-up logging, consumption estimate, fuel gauge."""
import csv
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

INJECTOR_CC_PER_MS = 0.00533  # 320cc/min / 60000ms per injector
TANK_TOTAL_L       = 16.7     # XB12X Ulysses total tank capacity
RESERVE_L          = 3.1      # level at which reserve light activates
FUEL_FILE = '/home/pi/buell/fuel_tracking.json'


def _load() -> dict:
    try:
        with open(FUEL_FILE) as f:
            return json.load(f)
    except Exception:
        return {'reserve_active': False, 'reserve_ts': None, 'refuels': [],
                'injector_cc_per_ms': INJECTOR_CC_PER_MS}


def _save(state: dict) -> None:
    tmp = FUEL_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    import os; os.replace(tmp, FUEL_FILE)


def toggle_reserve(active: bool) -> dict:
    state = _load()
    state['reserve_active'] = active
    state['reserve_ts'] = datetime.now(timezone.utc).isoformat() if active else None
    _save(state)
    return state


def add_refuel(liters: float, octane: int, sessions_dir: str) -> dict:
    state = _load()
    cc = state['injector_cc_per_ms']
    reserve_ts = state.get('reserve_ts')
    consumed_est, km_est = (None, None)
    if reserve_ts:
        consumed_est, km_est = _calc_since(reserve_ts, sessions_dir, cc)
    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'liters': liters, 'octane': octane,
        'reserve_ts': reserve_ts,
        'estimated_liters': round(consumed_est, 3) if consumed_est is not None else None,
        'km_since_reserve': round(km_est, 1) if km_est is not None else None,
    }
    if consumed_est and consumed_est > 0.5 and liters > 0.5:
        ratio = liters / consumed_est
        state['injector_cc_per_ms'] = round(cc * ratio * 0.3 + cc * 0.7, 6)
        entry['calibration_ratio'] = round(ratio, 4)
    state['refuels'].append(entry)
    state['reserve_active'] = False
    state['reserve_ts'] = None
    _save(state)
    return entry


def get_status(sessions_dir: str) -> dict:
    state = _load()
    cc = state['injector_cc_per_ms']
    refuels = state.get('refuels', [])
    result = {
        'reserve_active': state['reserve_active'],
        'reserve_ts': state.get('reserve_ts'),
        'refuels': refuels,
        'injector_cc_per_ms': cc,
    }

    # --- Fuel level estimate from last fill-up ---
    if refuels:
        last = refuels[-1]
        consumed_fill, km_fill = _calc_since(last['ts'], sessions_dir, cc)
        level_l = max(0.0, last['liters'] - consumed_fill)
        result['level_L']   = round(level_l, 2)
        result['level_pct'] = round(level_l / TANK_TOTAL_L * 100, 1)
        result['km_since_fill'] = round(km_fill, 1)
        result['consumed_since_fill'] = round(consumed_fill, 2)

    # --- Reserve counter ---
    if state['reserve_active'] and state.get('reserve_ts'):
        consumed_res, km_res = _calc_since(state['reserve_ts'], sessions_dir, cc)
        result['current_liters_used'] = round(consumed_res, 3)
        result['current_km'] = round(km_res, 1)
        # If no fill-up yet, estimate level from reserve baseline
        if 'level_L' not in result:
            level_l = max(0.0, RESERVE_L - consumed_res)
            result['level_L']   = round(level_l, 2)
            result['level_pct'] = round(level_l / TANK_TOTAL_L * 100, 1)

    return result


def _calc_since(from_ts: str, sessions_dir: str, cc_per_ms: float):
    """Sum PW-based consumption and km across all ride CSVs since from_ts."""
    from_unix = datetime.fromisoformat(from_ts.replace('Z', '+00:00')).timestamp()
    total_cc = 0.0
    total_km = 0.0
    for csv_path in sorted(glob.glob(f'{sessions_dir}/*/ride_*.csv')):
        try:
            with open(csv_path) as f:
                if f.readline().startswith('#'):
                    pass
                else:
                    f.seek(0)
                reader = csv.DictReader(f)
                prev_unix = None
                for row in reader:
                    ts_str = row.get('timestamp_iso', '')
                    if not ts_str:
                        continue
                    try:
                        row_unix = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).timestamp()
                    except Exception:
                        continue
                    if row_unix < from_unix:
                        prev_unix = None
                        continue
                    pw1 = float(row.get('pw1') or 0)
                    pw2 = float(row.get('pw2') or 0)
                    total_cc += (pw1 + pw2) * cc_per_ms
                    if prev_unix is not None:
                        kph = float(row.get('VS_KPH') or 0)
                        total_km += kph * (row_unix - prev_unix) / 3600
                    prev_unix = row_unix
        except Exception:
            continue
    return total_cc / 1000, total_km
