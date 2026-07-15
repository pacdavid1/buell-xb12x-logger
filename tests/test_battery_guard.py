# DEV NOTE: All code, comments, and variable names must be in English.
"""Golden tests for the UPS discharge detector (sensors/battery_guard.py).

Reproduces the 2026-07-14 failure: CW2015 charge bit claimed "charging"
while the pack drained 30% -> 14%, vetoing the low-battery shutdown.
Runnable with pytest or directly: python tests/test_battery_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sensors.battery_guard import (BAT_DISCHARGE_HORIZON_S, battery_discharging,
                                   prune_history)


def _drain(t0: float, seconds: float, soc0: float, soc1: float,
           v0: float = 3.9, v1: float = 3.9, step: float = 2.0) -> list:
    """Linear (t, v, soc) ramp sampled every `step` seconds (sysmon cadence)."""
    n = int(seconds / step) + 1
    out = []
    for i in range(n):
        f = i / max(1, n - 1)
        out.append((t0 + i * step, v0 + (v1 - v0) * f, soc0 + (soc1 - soc0) * f))
    return out


def test_empty_and_short_history_are_not_discharging() -> None:
    assert battery_discharging([], 1000.0) is False
    # 60 s of steep drain: real, but below the minimum span -- not judged yet
    assert battery_discharging(_drain(0, 60, 30, 25), 60.0) is False


def test_slow_drain_2026_07_14_is_detected() -> None:
    # ~16% lost over ~1 h => ~1.6%/600 s. Use the last 600 s of that drain:
    # 30.0 -> 28.4% with voltage sagging 3.70 -> 3.67. SOC alone is borderline
    # (1.6 < 2.0) but the voltage drop (0.03) catches it.
    hist = _drain(0, 600, 30.0, 28.4, v0=3.70, v1=3.67)
    assert battery_discharging(hist, 600.0) is True


def test_clear_soc_drop_is_detected_without_voltage() -> None:
    hist = _drain(0, 600, 30.0, 25.0, v0=3.7, v1=3.7)
    assert battery_discharging(hist, 600.0) is True


def test_stable_or_charging_pack_is_not_discharging() -> None:
    assert battery_discharging(_drain(0, 600, 50.0, 50.0), 600.0) is False
    assert battery_discharging(_drain(0, 600, 50.0, 55.0, v0=3.8, v1=3.9), 600.0) is False


def test_none_readings_do_not_crash_or_trigger() -> None:
    hist = [(0.0, None, None), (400.0, None, None)]
    assert battery_discharging(hist, 400.0) is False


def test_prune_keeps_only_horizon() -> None:
    hist = _drain(0, 1200, 40.0, 20.0)
    pruned = prune_history(hist, 1200.0)
    assert pruned[0][0] >= 1200.0 - BAT_DISCHARGE_HORIZON_S
    assert pruned[-1][0] == hist[-1][0]


if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS {name}')
            except AssertionError as e:
                fails += 1
                print(f'FAIL {name}: {e}')
    sys.exit(1 if fails else 0)
