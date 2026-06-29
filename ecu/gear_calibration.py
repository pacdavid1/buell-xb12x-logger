# DEV NOTE: All code, comments, and variable names must be in English.
"""
ecu/gear_calibration.py — Shared gear detection thresholds.

Learned from 6,328 real samples across 6 sessions (D7B333, 248AE2, 917900,
9ECD1E, C49C2D, E8D511). Optimal split points computed by brute-force
minimization of cross-domain classification errors.

Usage:
  from ecu.gear_calibration import ratio_to_gear, GEAR_THRESHOLDS_DETECT

Both protocol.py (live GearFilter) and gear_detect.py (post-ride) import
from this single source of truth.
"""

# ── Thresholds for GearFilter (protocol.py) ───────────────────────────────────
# Logic: if ratio >= THRESHOLD then gear = g
# Higher ratio = lower gear (e.g. ratio 106+ = Gear 1, ratio 48-58 = Gear 4)
GEAR_THRESHOLDS_LIVE: list[float] = [106.0, 74.0, 58.0, 48.0]
# Maps to: Gear 1 if ratio >= 106, Gear 2 if >= 74, Gear 3 if >= 58, Gear 4 if >= 48, else Gear 5

# ── Thresholds for detect_gear (gear_detect.py) ──────────────────────────────
# Logic: if ratio < LIMIT then gear = g
# Lower ratio = higher gear (e.g. ratio < 48 = Gear 5, ratio < 58 = Gear 4)
# These are the inverse of GEAR_THRESHOLDS_LIVE
GEAR_THRESHOLDS_DETECT: list[tuple[float, int]] = [(48.0, 5), (58.0, 4), (74.0, 3), (106.0, 2)]
# Maps to: Gear 5 if ratio < 48, Gear 4 if < 58, Gear 3 if < 74, Gear 2 if < 106, else Gear 1

# ── Coasting guard ────────────────────────────────────────────────────────────
# Minimum physically possible ratio (RPM/VSS) for this bike.
# Below this, the wheel is spinning faster than the engine can explain in any gear.
COAST_RATIO_MIN: float = 19.0


def ratio_to_gear(ratio: float) -> int:
    """Convert RPM/VSS ratio to gear (1-5).

    Args:
        ratio: RPM / VS_KPH

    Returns:
        Gear number (1-5). 1 = lowest gear (highest ratio), 5 = highest gear (lowest ratio).
    """
    for thr, g in zip(GEAR_THRESHOLDS_LIVE, [1, 2, 3, 4]):
        if ratio >= thr:
            return g
    return 5
