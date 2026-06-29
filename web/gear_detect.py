# DEV NOTE: All code, comments, and variable names must be in English.
"""
gear_detect.py -- Post-ride gear detection from RPM/VSS ratio.

Default thresholds are the hardcoded XB12X values (calibrated from session
248AE2, 96.9% accuracy). Pass a learned thresholds list from GearLearner to
use data-driven thresholds instead -- preferred when gear_profile.json exists.
"""

# Fallback thresholds for XB12X #248AE2 -- used when no profile is loaded.
# (ratio_upper_limit, gear) checked in order; first match wins. ratio = RPM/VSS.
GEAR_THRESHOLDS = [(44, 5), (62, 4), (74, 3), (90, 2)]
MIN_RPM = 1500
MIN_VSS = 5.0


def detect_gear(rpm, vss_kph, di_neutral=None, thresholds=None):
    """Return detected gear (1-N) or 0 if uncertain (idle, neutral, clutch in).

    thresholds: optional list of (ratio_upper_limit, gear) tuples from
      GearLearner.get_thresholds(). Falls back to GEAR_THRESHOLDS when None.
    di_neutral: neutral switch state from ECU -- overrides ratio heuristic.
    """
    if di_neutral:
        return 0
    if rpm < MIN_RPM or vss_kph < MIN_VSS:
        return 0
    ratio = rpm / vss_kph
    active = thresholds if thresholds is not None else GEAR_THRESHOLDS
    for limit, gear in active:
        if ratio < limit:
            return gear
    return 1
