# DEV NOTE: All code, comments, and variable names must be in English.
"""Battery discharge detection for the UPS low-battery shutdown.

Why this exists: the UPS-Lite v1.3 charge indication read from CW2015
register 0x08 bit4 is NOT a charge indicator -- per the CW2015 datasheet,
0x08 is RRT_ALERT (remaining-run-time / alert), so that bit can sit high
indefinitely. On 2026-07-14 it reported "charging" while the pack drained
30% -> 14%, which vetoed the low-battery shutdown in main._sysmon_loop and
the Pi never powered off. A pack whose SOC or voltage is falling over a
long-enough window is discharging, whatever the bit claims.
"""
from __future__ import annotations

BAT_DISCHARGE_HORIZON_S = 600.0  # look-back window (s) for discharge detection
BAT_DISCHARGE_MIN_SPAN_S = 300.0  # minimum history span (s) before judging
BAT_DISCHARGE_SOC_DROP = 2.0     # % SOC drop over the window = discharging
BAT_DISCHARGE_V_DROP = 0.03      # voltage drop (V) over the window = discharging


def prune_history(history: list, now: float,
                  horizon_s: float = BAT_DISCHARGE_HORIZON_S) -> list:
    """Return history clipped to the detection horizon (oldest first)."""
    cutoff = now - horizon_s
    return [h for h in history if h[0] >= cutoff]


def battery_discharging(history: list, now: float,
                        min_span_s: float = BAT_DISCHARGE_MIN_SPAN_S,
                        soc_drop: float = BAT_DISCHARGE_SOC_DROP,
                        v_drop: float = BAT_DISCHARGE_V_DROP) -> bool:
    """True when the battery demonstrably LOST charge over the history window.

    history: list of (monotonic_t, voltage_or_None, soc_or_None), oldest
    first, already pruned to the horizon. Returns False until the window
    spans at least min_span_s -- a slow drain needs look-back to show up.
    """
    if len(history) < 2:
        return False
    t0, v0, s0 = history[0]
    t1, v1, s1 = history[-1]
    if t1 - t0 < min_span_s:
        return False
    if s0 is not None and s1 is not None and (s0 - s1) >= soc_drop:
        return True
    if v0 is not None and v1 is not None and (v0 - v1) >= v_drop:
        return True
    return False
