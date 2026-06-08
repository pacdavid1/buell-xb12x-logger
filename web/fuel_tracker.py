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
    if active:
        state['reserve_ts'] = datetime.now(timezone.utc).isoformat()  # reset km pivot
    else:
        state['reserve_ts'] = None
    _save(state)
    return state


def add_refuel(liters: float, octane: int, sessions_dir: str, full_tank: bool = False) -> dict:
    state = _load()
    cc = state['injector_cc_per_ms']
    reserve_ts = state.get('reserve_ts')
    consumed_est, km_est = (None, None)
    if reserve_ts:
        consumed_est, km_est = _calc_since(reserve_ts, sessions_dir, cc)

    # Discrepancy: how far off is our calculation?
    # If full_tank: the tank should be 16.7L after filling, so remaining was (16.7 - liters)
    # Compare that to what we calculated was remaining
    discrepancy_l = None
    calc_remaining = None
    if consumed_est is not None and state.get('refuels'):
        last = state['refuels'][-1]
        calc_remaining = round(max(0.0, last['liters'] - consumed_est), 2)
        if full_tank:
            expected_remaining = round(TANK_TOTAL_L - liters, 2)
            discrepancy_l = round(calc_remaining - expected_remaining, 2)

    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'liters': liters, 'octane': octane,
        'full_tank': full_tank,
        'reserve_ts': reserve_ts,
        'estimated_liters': round(consumed_est, 3) if consumed_est is not None else None,
        'km_since_reserve': round(km_est, 1) if km_est is not None else None,
        'calc_remaining_L': calc_remaining,
        'discrepancy_L': discrepancy_l,
    }

    # Calibration: only when not full_tank (full_tank resets rather than calibrates)
    if not full_tank and consumed_est and consumed_est > 0.5 and liters > 0.5:
        ratio = liters / consumed_est
        state['injector_cc_per_ms'] = round(cc * ratio * 0.3 + cc * 0.7, 6)
        entry['calibration_ratio'] = round(ratio, 4)

    # If full_tank: override calculated level to 16.7L on next status call
    entry['level_override_L'] = TANK_TOTAL_L if full_tank else None

    state['refuels'].append(entry)
    state['reserve_active'] = False
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
        base_l = last.get('level_override_L') or last['liters']
        level_l = max(0.0, base_l - consumed_fill)
        result['level_L']   = round(level_l, 2)
        result['level_pct'] = round(level_l / TANK_TOTAL_L * 100, 1)
        result['km_since_fill'] = round(km_fill, 1)
        result['consumed_since_fill'] = round(consumed_fill, 2)
        result['last_full_tank'] = last.get('full_tank', False)

    # --- Trip km counter (pivots at reserve activation, survives fill-up) ---
    if state.get('reserve_ts'):
        consumed_res, km_res = _calc_since(state['reserve_ts'], sessions_dir, cc)
        result['trip_km'] = round(km_res, 1)
        if state['reserve_active']:
            result['current_liters_used'] = round(consumed_res, 3)
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
                    rpm = float(row.get('RPM') or 0)
                    if prev_unix is not None:
                        dt_s = row_unix - prev_unix
                        kph  = float(row.get('VS_KPH') or 0)
                        total_km += kph * dt_s / 3600
                        inj = max(0.0, (rpm / 120.0) * dt_s)
                        total_cc += (pw1 + pw2) * cc_per_ms * inj
                    prev_unix = row_unix
        except Exception:
            continue
    return total_cc / 1000, total_km

def _calc_ride_from_csv(csv_path: str, cc_per_ms: float) -> dict | None:
    """Parse a single ride CSV and return consumption metrics, or None if insufficient data."""
    import os
    name = Path(csv_path).stem
    if name.endswith(('_p2', '_p3', '_p4', '_p5')):
        return None
    session = Path(csv_path).parent.name
    total_cc   = 0.0
    total_km   = 0.0
    rpm_max    = 0.0
    first_ts   = None
    last_ts    = None
    sample_cnt = 0
    prev_unix  = None
    try:
        with open(csv_path) as f:
            if f.readline().startswith('#'):
                pass
            else:
                f.seek(0)
            for row in csv.DictReader(f):
                ts = row.get('timestamp_iso', '')
                try:
                    row_unix = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                except Exception:
                    continue
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
                pw1 = float(row.get('pw1') or 0)
                pw2 = float(row.get('pw2') or 0)
                rpm = float(row.get('RPM') or 0)
                if rpm > rpm_max:
                    rpm_max = rpm
                if prev_unix is not None:
                    dt_s = row_unix - prev_unix
                    kph  = float(row.get('VS_KPH') or 0)
                    total_km += kph * dt_s / 3600
                    inj = max(0.0, (rpm / 120.0) * dt_s)
                    total_cc += (pw1 + pw2) * cc_per_ms * inj
                prev_unix = row_unix
                sample_cnt += 1
    except Exception:
        return None
    if sample_cnt < 10 or total_km < 0.1:
        return None
    liters = total_cc / 1000
    duration_s = None
    if first_ts and last_ts:
        try:
            t0 = datetime.fromisoformat(first_ts.replace('Z', '+00:00')).timestamp()
            t1 = datetime.fromisoformat(last_ts.replace('Z', '+00:00')).timestamp()
            duration_s = round(t1 - t0, 1)
        except Exception:
            pass
    return {
        'session':           session,
        'ride':              name,
        'date':              first_ts,
        'km':                round(total_km, 1),
        'liters':            round(liters, 3),
        'km_per_l':          round(total_km / liters, 2) if liters > 0 else None,
        'l_per_100':         round(liters / total_km * 100, 2) if total_km > 0 else None,
        'rpm_max':           round(rpm_max),
        'duration_s':        duration_s,
        'samples':           sample_cnt,
        'injector_cc_per_ms': cc_per_ms,
    }


def save_ride_consumption_cache(csv_path: str) -> dict | None:
    """Compute and persist <ride>_consumption.json. Called at ride close."""
    import os
    cc = _load()['injector_cc_per_ms']
    data = _calc_ride_from_csv(csv_path, cc)
    if data is None:
        return None
    cache_path = Path(csv_path).with_name(Path(csv_path).stem + '_consumption.json')
    tmp = str(cache_path) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, str(cache_path))
    return data


def calc_ride_consumption(sessions_dir: str, limit: int = 200) -> list:
    """Return per-ride consumption (newest first, capped at limit), reading from cache."""
    cc = _load()['injector_cc_per_ms']
    results = []
    for csv_path in sorted(glob.glob(f'{sessions_dir}/*/ride_*.csv')):
        name = Path(csv_path).stem
        if name.endswith(('_p2', '_p3', '_p4', '_p5')):
            continue
        cache_path = Path(csv_path).with_name(name + '_consumption.json')
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                if data.get('samples', 0) >= 10 and data.get('km', 0) >= 0.1:
                    results.append(data)
                    continue
            except Exception:
                pass
        data = _calc_ride_from_csv(csv_path, cc)
        if data is not None:
            results.append(data)
    results.sort(key=lambda r: r['date'], reverse=True)
    return results[:limit]
