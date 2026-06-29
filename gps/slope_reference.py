# DEV NOTE: All code, comments, and variable names must be in English.
"""Slope reference — differential GPS altitude accumulator (BL-GPS-05).

Instead of accumulating absolute GPS altitude (unreliable due to ±10 m per-session
bias), we accumulate within-ride altitude deltas between consecutive GPS bucket
transitions.  The per-session altitude offset cancels in the difference, leaving a
slope estimate that converges across passes even when absolute altitude drifts.

For each consecutive pair of quality GPS fixes that cross a bucket boundary and
are 5–40 m apart, we compute:

    slope_pct = (alt_b - alt_a) / dist_ab * 100

We accumulate these per ordered segment, apply MAD outlier rejection across
sessions, and return the trusted median slope.

Storage: buell_dir/slope_reference.json
  {
    "bucket_a|bucket_b": {"slopes": [1.2, 1.1, 1.3, ...], "n": 42},
    ...
  }
Segments are stored in canonical order (lexicographic sort of the two bucket
keys).  A sign convention is applied so that positive slope = uphill when
traversing in the canonical direction.  get_slope_pct() reverses the sign
automatically when called in the opposite direction.
"""
import csv
import json
import math
import os
import statistics
from pathlib import Path

# Spatial resolution — must match route_reference.BUCKET_PRECISION
BUCKET_PRECISION: int = 4

# Segment distance gate (metres).  Too short: same-bucket GPS jitter.
# Too long: might span multiple buckets or an intersection.
SEG_MIN_M: float = 5.0
SEG_MAX_M: float = 40.0

# MAD multiplier for outlier rejection
MAD_FACTOR: float = 2.5

# Maximum slope samples stored per segment (oldest discarded beyond this)
MAX_SLOPE_HISTORY: int = 50

# Minimum passes before a segment is considered confident
MIN_CONFIDENT_PASSES: int = 3

# Minimum GPS satellites for a quality fix (proxy when epv/mode unavailable)
MIN_QUALITY_SATS: int = 6
EPV_MAX_M: float = 5.0

REFERENCE_NAME = "slope_reference.json"


# ── helpers ────────────────────────────────────────────────────────────────

def _bucket_key(lat: float, lon: float) -> str:
    return f"{round(lat, BUCKET_PRECISION)},{round(lon, BUCKET_PRECISION)}"


def _seg_key(key1: str, key2: str) -> tuple[str, float]:
    """Return (canonical_segment_key, direction_sign).

    sign=+1.0 → request direction matches canonical direction (key1 → key2).
    sign=-1.0 → request direction is reverse; caller must negate result.
    """
    if key1 <= key2:
        return f"{key1}|{key2}", 1.0
    return f"{key2}|{key1}", -1.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres."""
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(max(0.0, a)))


def _reject_outliers(values: list[float]) -> list[float]:
    """MAD-based outlier rejection.  Returns cleaned list (may be empty)."""
    if len(values) < 3:
        return values
    median = statistics.median(values)
    mad = statistics.median([abs(v - median) for v in values])
    if mad == 0:
        return values
    return [v for v in values if abs(v - median) <= MAD_FACTOR * mad]


def _is_quality_fix(row: dict) -> bool:
    """Return True when a CSV row represents a trustworthy GPS fix."""
    if row.get("gps_valid", "").strip().lower() not in ("true", "1"):
        return False
    epv_raw = row.get("gps_epv", "").strip()
    if epv_raw:
        try:
            if float(epv_raw) > EPV_MAX_M:
                return False
        except ValueError:
            pass
    mode_raw = row.get("gps_mode", "").strip()
    if mode_raw:
        try:
            if int(float(mode_raw)) < 3:
                return False
        except ValueError:
            pass
    sats_raw = row.get("gps_satellites", "").strip()
    if sats_raw:
        try:
            if int(float(sats_raw)) < MIN_QUALITY_SATS:
                return False
        except ValueError:
            pass
    return True


# ── main class ─────────────────────────────────────────────────────────────

class SlopeReference:
    """Accumulates and queries trusted road slope by spatial segment pair."""

    def __init__(self, buell_dir: str | Path) -> None:
        self._path = Path(buell_dir) / REFERENCE_NAME
        self._data: dict[str, dict] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_from_session(self, session_dir: str | Path) -> dict:
        """Ingest all ride CSVs in a session directory.

        Returns {'added': int, 'segments': int, 'segments_confident': int}.
        """
        session_dir = Path(session_dir)
        added = 0
        for csv_path in sorted(session_dir.glob("ride_*.csv")):
            added += self._ingest_csv(csv_path)
        self._save()
        return {
            "added":               added,
            "segments":            len(self._data),
            "segments_confident":  self._count_confident(),
        }

    def update_all_sessions(self, buell_dir: str | Path) -> dict:
        """Ingest every session under buell_dir/sessions/."""
        sessions_root = Path(buell_dir) / "sessions"
        total_added = 0
        sessions_processed = 0
        for sdir in sorted(sessions_root.iterdir()):
            if not sdir.is_dir() or sdir.name.startswith("_"):
                continue
            for csv_path in sorted(sdir.glob("ride_*.csv")):
                total_added += self._ingest_csv(csv_path)
            sessions_processed += 1
        self._save()
        return {
            "sessions_processed": sessions_processed,
            "added":               total_added,
            "segments":            len(self._data),
            "segments_confident":  self._count_confident(),
        }

    def get_slope_pct(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float | None:
        """Trusted median slope (%) from (lat1,lon1) to (lat2,lon2).

        Positive = uphill in the requested traversal direction.
        Returns None when the segment has insufficient data.
        """
        key1 = _bucket_key(lat1, lon1)
        key2 = _bucket_key(lat2, lon2)
        if key1 == key2:
            return None
        seg, sign = _seg_key(key1, key2)
        bucket = self._data.get(seg)
        if not bucket or len(bucket["slopes"]) < 2:
            return None
        cleaned = _reject_outliers(bucket["slopes"])
        if not cleaned:
            return None
        # sign converts stored canonical slope back to requested direction
        return round(statistics.median(cleaned) * sign, 2)

    def stats(self) -> dict:
        """Summary stats for the accumulated slope reference."""
        total_samples = sum(b["n"] for b in self._data.values())
        return {
            "segments":            len(self._data),
            "segments_confident":  self._count_confident(),
            "total_slope_samples": total_samples,
            "path":                str(self._path),
            "exists":              self._path.exists(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest_csv(self, csv_path: Path) -> int:
        """Accumulate within-ride slope deltas from one ride CSV."""
        added = 0
        prev_key = None
        prev_lat = prev_lon = prev_alt = None

        try:
            with open(csv_path, newline="") as fh:
                first = fh.readline()
                if not first.startswith("#"):
                    fh.seek(0)
                reader = csv.DictReader(fh)
                for row in reader:
                    if not _is_quality_fix(row):
                        # Break the chain on bad fix — don't bridge across gaps
                        prev_key = prev_lat = prev_lon = prev_alt = None
                        continue
                    try:
                        lat = float(row["gps_lat"])
                        lon = float(row["gps_lon"])
                        alt = float(row["gps_alt_m"])
                    except (ValueError, KeyError, TypeError):
                        prev_key = prev_lat = prev_lon = prev_alt = None
                        continue

                    if lat == 0.0 or lon == 0.0 or alt == 0.0:
                        prev_key = prev_lat = prev_lon = prev_alt = None
                        continue

                    key = _bucket_key(lat, lon)

                    if prev_key is not None and key != prev_key:
                        dist = _haversine_m(prev_lat, prev_lon, lat, lon)
                        if SEG_MIN_M <= dist <= SEG_MAX_M:
                            delta_alt = alt - prev_alt
                            slope_pct = delta_alt / dist * 100
                            seg, sign = _seg_key(prev_key, key)
                            # Store relative to canonical direction
                            stored = round(slope_pct * sign, 2)
                            if seg not in self._data:
                                self._data[seg] = {"slopes": [], "n": 0}
                            bucket = self._data[seg]
                            bucket["slopes"].append(stored)
                            if len(bucket["slopes"]) > MAX_SLOPE_HISTORY:
                                bucket["slopes"] = bucket["slopes"][-MAX_SLOPE_HISTORY:]
                            bucket["n"] += 1
                            added += 1

                    prev_key = key
                    prev_lat, prev_lon, prev_alt = lat, lon, alt
        except Exception:
            pass
        return added

    def _count_confident(self) -> int:
        return sum(
            1 for b in self._data.values()
            if b["n"] >= MIN_CONFIDENT_PASSES
        )

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
