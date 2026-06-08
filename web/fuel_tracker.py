# DEV NOTE: All code, comments, and variable names must be in English.
"""Fuel tracking module — manual reserve activation + fill-up logging + consumption estimate."""
import csv
import glob
import json
import time
from datetime import datetime, timezone
from pathlib import Path

INJECTOR_CC_PER_MS = 0.00533   # 320cc/min / 60000ms per injector
FUEL_FILE = '/home/pi/buell/fuel_tracking.json'


def _load() -> dict:
    try:
        with open(FUEL_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            'reserve_active': False,
            'reserve_ts': None,
            'refuels': [],
            'injector_cc_per_ms': INJECTOR_CC_PER_MS,
        }


def _save(state: dict) -> None:
    tmp = FUEL_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    import os; os.replace(tmp, FUEL_FILE)


def toggle_reserve(active: bool) -> dict:
    state = _load()
    state['reserve_active'] = active
    state['reserve_ts'] = datetime.now(timezone.utc).isoformat() if active else state.get('reserve_ts')
    if not active:
        state['reserve_ts'] = None
    _save(state)
    return state


def add_refuel(liters: float, octane: int, sessions_dir: str) -> dict:
    state = _load()
    reserve_ts = state.get('reserve_ts')
    consumed_est = None
    km_est = None
    if reserve_ts:
        consumed_est, km_est = _calc_since(reserve_ts, sessions_dir, state['injector_cc_per_ms'])
    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'liters': liters,
        'octane': octane,
        'reserve_ts': reserve_ts,
        'estimated_liters': round(consumed_est, 3) if consumed_est is not None else None,
        'km_since_reserve': round(km_est, 1) if km_est is not None else None,
    }
    # Iterative calibration: if we have both real and estimated, refine constant
    if consumed_est and consumed_est > 0.5 and liters > 0.5:
        ratio = liters / consumed_est
        old = state['injector_cc_per_ms']
        state['injector_cc_per_ms'] = round(old * ratio * 0.3 + old * 0.7, 6)
        entry['calibration_ratio'] = round(ratio, 4)
    state['refuels'].append(entry)
    state['reserve_active'] = False
    state['reserve_ts'] = None
    _save(state)
    return entry


def get_status(sessions_dir: str) -> dict:
    state = _load()
    result = {'reserve_active': state['reserve_active'], 'reserve_ts': state.get('reserve_ts'),
              'refuels': state.get('refuels', []), 'injector_cc_per_ms': state['injector_cc_per_ms']}
    if state['reserve_active'] and state.get('reserve_ts'):
        consumed, km = _calc_since(state['reserve_ts'], sessions_dir, state['injector_cc_per_ms'])
        result['current_liters_used'] = round(consumed, 3)
        result['current_km'] = round(km, 1)
    return result


def _calc_since(from_ts: str, sessions_dir: str, cc_per_ms: float):
    """Sum PW injection and km from from_ts to now across all CSVs."""
    from_unix = datetime.fromisoformat(from_ts.replace('Z', '+00:00')).timestamp()
    total_cc = 0.0
    total_km = 0.0
    for csv_path in sorted(glob.glob(f'{sessions_dir}/*/ride_*.csv')):
        if '_p' in Path(csv_path).stem.replace(Path(csv_path).stem.split('_')[0], '')[1:]:
            pass  # include all parts
        try:
            with open(csv_path) as f:
                first = f.readline()
                if not first.startswith('#'):
                    f.seek(0)
                reader = csv.DictReader(f)
                prev_t = None
                for row in reader:
                    ts_str = row.get('timestamp_iso', '')
                    if not ts_str:
                        continue
                    try:
                        row_unix = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).timestamp()
                    except Exception:
                        continue
                    if row_unix < from_unix:
                        prev_t = None
                        continue
                    pw1 = float(row.get('pw1') or 0)
                    pw2 = float(row.get('pw2') or 0)
                    total_cc += (pw1 + pw2) * cc_per_ms
                    kph = float(row.get('VS_KPH') or 0)
                    if prev_t is not None:
                        elapsed = row_unix - prev_t
                        total_km += kph * elapsed / 3600
                    prev_t = row_unix
        except Exception:
            continue
    return total_cc / 1000, total_km
