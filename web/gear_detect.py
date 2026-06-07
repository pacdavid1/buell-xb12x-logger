# DEV NOTE: All code, comments, and variable names must be in English.
"""
gear_detect.py — Post-ride gear detection from RPM/VSS ratio.

Thresholds calibrated from session 248AE2 (1104 rows, 96.9% accuracy).
Confusion only between adjacent gears — no non-adjacent errors observed.
"""

# (ratio_upper_limit, gear) — checked in order; first match wins
# ratio = RPM / VS_KPH
GEAR_THRESHOLDS = [(44, 5), (62, 4), (74, 3), (90, 2)]
MIN_RPM = 1500
MIN_VSS = 5.0


def detect_gear(rpm, vss_kph):
    """Return detected gear (1-5) or 0 if uncertain (idle, neutral, clutch in)."""
    if rpm < MIN_RPM or vss_kph < MIN_VSS:
        return 0
    ratio = rpm / vss_kph
    for limit, gear in GEAR_THRESHOLDS:
        if ratio < limit:
            return gear
    return 1
