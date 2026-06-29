# DEV NOTE: All code, comments, and variable names must be in English.
"""Gear ratio auto-learner — discovers gear thresholds from ECU-reported gear data.

The ECU already reports the current gear in the `Gear` CSV column. This module
reads (ratio, gear) pairs from all ride CSVs and finds the optimal RPM/VSS ratio
threshold between each adjacent gear pair by brute-force minimisation of
misclassification errors.

This approach is data-driven and bike-agnostic: it works for any bike whose ECU
reports gear position (XB12X, 1125CR, etc.) without any hardcoded constants.

Thresholds are stored in buell_dir/gear_profile.json and are compatible with
the GEAR_THRESHOLDS format used by gear_detect.detect_gear().

Storage format:
  {
    "n_gears": 5,
    "n_samples": 6328,
    "samples_per_gear": {"1": 127, "2": 648, "3": 247, "4": 787, "5": 4519},
    "thresholds": [
      {"limit": 48, "gear": 5},
      {"limit": 58, "gear": 4},
      {"limit": 74, "gear": 3},
      {"limit": 106, "gear": 2}
    ]
  }
"""

import csv
import json
import os
from pathlib import Path

# Quality gates -- must match gear_detect.py MIN_RPM / MIN_VSS
MIN_RPM: float = 1500.0
MIN_VSS: float = 5.0

# Gear 1 at very low speed can produce ratios above 200; cap at 600 to avoid
# pathological outliers (stalled engine, sensor glitch).
RATIO_MAX_ABS: float = 600.0

# A gear must have at least this many samples to compute a reliable boundary.
MIN_GEAR_SAMPLES: int = 50

PROFILE_NAME = "gear_profile.json"


class GearLearner:
    """Learn and serve gear detection thresholds from ECU-reported gear data."""

    def __init__(self, buell_dir) -> None:
        self._path = Path(buell_dir) / PROFILE_NAME
        self._data: dict = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def learn(self, buell_dir, n_gears: int = 5) -> dict:
        """Ingest all sessions and learn optimal ratio thresholds per gear boundary.

        Uses the ECU-reported Gear column as ground truth. For each adjacent gear
        pair (G, G-1) scans integer ratio thresholds and picks the one with the
        fewest misclassified samples.

        Returns the learned profile dict (also saved to disk).
        """
        pairs = self._collect_ratio_gear_pairs(Path(buell_dir) / "sessions")
        if not pairs:
            return {"error": "No labeled samples found (Gear column missing or all zero)"}

        profile = self._fit(pairs, n_gears)
        self._data = profile
        self._save()
        return profile

    def get_thresholds(self):
        """Return [(limit, gear), ...] compatible with GEAR_THRESHOLDS, or None."""
        if not self._data or "thresholds" not in self._data:
            return None
        return [(t["limit"], t["gear"]) for t in self._data["thresholds"]]

    def stats(self) -> dict:
        return {**self._data, "path": str(self._path), "exists": self._path.exists()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_ratio_gear_pairs(self, sessions_root: Path) -> list:
        """Return list of (ratio, gear) from all ride CSVs that have a Gear column."""
        pairs = []
        for sdir in sorted(sessions_root.iterdir()):
            if not sdir.is_dir() or sdir.name.startswith("_"):
                continue
            for csv_path in sorted(sdir.glob("ride_*.csv")):
                try:
                    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
                        first = f.readline()
                        if not first.startswith("#"):
                            f.seek(0)
                        for row in csv.DictReader(f):
                            try:
                                rpm = float(row.get("RPM") or 0)
                                vss = float(row.get("VS_KPH") or 0)
                                gear_raw = row.get("Gear")
                                if gear_raw is None:
                                    continue
                                gear = int(float(gear_raw))
                                neutral = int(float(row.get("di_neutral") or 0))
                                clutch = int(float(row.get("di_clutch") or 0))
                            except (ValueError, TypeError):
                                continue
                            if (
                                gear < 1
                                or rpm < MIN_RPM
                                or vss < MIN_VSS
                                or neutral
                                or clutch
                            ):
                                continue
                            ratio = rpm / vss
                            if ratio < 1.0 or ratio > RATIO_MAX_ABS:
                                continue
                            pairs.append((ratio, gear))
                except Exception:
                    pass
        return pairs

    def _fit(self, pairs: list, n_gears: int) -> dict:
        """Find optimal ratio threshold between each adjacent gear pair.

        For gears G and G-1, scans integer ratio values from the minimum of the
        higher-gear distribution to the maximum of the lower-gear distribution and
        picks the threshold that minimises total misclassifications.
        """
        by_gear: dict = {}
        for ratio, gear in pairs:
            by_gear.setdefault(gear, []).append(ratio)

        samples_per_gear = {g: len(v) for g, v in by_gear.items()}
        thresholds = []

        for gear_high in range(n_gears, 1, -1):
            gear_low = gear_high - 1
            high = by_gear.get(gear_high, [])
            low = by_gear.get(gear_low, [])

            if len(high) < MIN_GEAR_SAMPLES or len(low) < MIN_GEAR_SAMPLES:
                continue

            # Candidate thresholds: every integer from just above min(high)
            # to just below max(low), covering the overlap zone.
            t_min = int(min(high)) - 1
            t_max = int(max(low)) + 2

            best_t, best_err = t_min, len(pairs) + 1
            for t in range(t_min, t_max + 1):
                err = sum(1 for r in high if r >= t) + sum(1 for r in low if r < t)
                if err < best_err:
                    best_err = err
                    best_t = t

            thresholds.append({
                "limit": float(best_t),
                "gear": gear_high,
                "boundary_errors": best_err,
            })

        thresholds.sort(key=lambda x: x["limit"])

        return {
            "n_gears": n_gears,
            "n_samples": len(pairs),
            "samples_per_gear": samples_per_gear,
            "thresholds": thresholds,
        }

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except Exception:
            return {}

    def _save(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, separators=(",", ":")))
        os.replace(tmp, self._path)
