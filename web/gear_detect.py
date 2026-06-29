# DEV NOTE: All code, comments, and variable names must be in English.
"""
gear_detect.py -- Post-ride gear detection from RPM/VSS ratio.

Default thresholds come from ecu/gear_calibration.py (single source of truth,
learned from 313k samples). Pass an optional thresholds list from GearLearner
to use per-fleet refined thresholds instead.
"""
from ecu.gear_calibration import GEAR_THRESHOLDS_DETECT

GEAR_THRESHOLDS = list(GEAR_THRESHOLDS_DETECT)
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
