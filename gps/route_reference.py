# DEV NOTE: All code, comments, and variable names must be in English.
"""Route reference — multi-pass averaged GPS altitude profile (BL-GPS-04).

GPS altitude error averages down by sqrt(N) across passes taken at different
times (different satellite geometry decorrelates the bias).  We bucket GPS
points by spatial grid (~11 m at 32° lat), accumulate altitudes from every
ride, apply MAD outlier rejection, and return the trusted median altitude for
any coordinate.  This feeds GAP 4 slope normalisation.

Storage: buell_dir/route_reference.json
  {
    "lat,lon": {"alts": [100.1, 100.4, ...], "n": 12},
    ...
  }
"""
import csv
import json
import os
import statistics
from pathlib import Path

# Spatial resolution: round(lat, 4) ≈ 11 m grid at 32° latitude
BUCKET_PRECISION: int = 4
# Minimum satellites for a quality fix (proxy when epv/mode not available)
MIN_QUALITY_SATS: int = 6
# Maximum estimated vertical error in metres (used when gps_epv is present)
EPV_MAX_M: float = 5.0
# MAD multiplier for outlier rejection (2.5 ≈ 99% of normally distributed data)
MAD_FACTOR: float = 2.5
# Maximum altitude readings stored per bucket (oldest discarded beyond this)
MAX_ALT_HISTORY: int = 50
# Minimum passes before a bucket is considered confident
MIN_CONFIDENT_PASSES: int = 3

REFERENCE_NAME = "route_reference.json"


def _bucket_key(lat: float, lon: float) -> str:
    return f"{round(lat, BUCKET_PRECISION)},{round(lon, BUCKET_PRECISION)}"


def _reject_outliers(alts: list[float]) -> list[float]:
    """MAD-based outlier rejection.  Returns cleaned list (may be empty)."""
    if len(alts) < 3:
        return alts
    median = statistics.median(alts)
    mad = statistics.median([abs(a - median) for a in alts])
    if mad == 0:
        return alts
    return [a for a in alts if abs(a - median) <= MAD_FACTOR * mad]


def _is_quality_fix(row: dict) -> bool:
    """Return True when a CSV row represents a trustworthy GPS fix."""
    if row.get("gps_valid", "").strip().lower() not in ("true", "1"):
        return False
    # epv gate — present in newer CSVs only
    epv_raw = row.get("gps_epv", "").strip()
    if epv_raw:
        try:
            if float(epv_raw) > EPV_MAX_M:
                return False
        except ValueError:
            pass
    # 3D-fix gate — present in newer CSVs only
    mode_raw = row.get("gps_mode", "").strip()
    if mode_raw:
        try:
            if int(float(mode_raw)) < 3:
                return False
        except ValueError:
            pass
    # Satellite count gate — available in all CSVs
    sats_raw = row.get("gps_satellites", "").strip()
    if sats_raw:
        try:
            if int(float(sats_raw)) < MIN_QUALITY_SATS:
                return False
        except ValueError:
            pass
    return True


class RouteReference:
    """Accumulates and queries trusted GPS altitude by spatial bucket."""

    def __init__(self, buell_dir: str | Path) -> None:
        self._path = Path(buell_dir) / REFERENCE_NAME
        self._data: dict[str, dict] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_from_session(self, session_dir: str | Path) -> dict:
        """Ingest all ride CSVs in a session directory.

        Returns {'added': int, 'buckets': int, 'buckets_confident': int}.
        """
        session_dir = Path(session_dir)
        added = 0
        for csv_path in sorted(session_dir.glob("ride_*.csv")):
            added += self._ingest_csv(csv_path)
        self._save()
        return {
            "added":              added,
            "buckets":            len(self._data),
            "buckets_confident":  self._count_confident(),
        }

    def update_all_sessions(self, buell_dir: str | Path) -> dict:
        """Ingest every session under buell_dir/sessions/.

        Returns aggregate stats.
        """
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
            "added":              total_added,
            "buckets":            len(self._data),
            "buckets_confident":  self._count_confident(),
        }

    def get_altitude(self, lat: float, lon: float) -> float | None:
        """Trusted median altitude for a coordinate after outlier rejection.

        Returns None when the bucket has no data or fewer than 2 readings.
        """
        key = _bucket_key(lat, lon)
        bucket = self._data.get(key)
        if not bucket or len(bucket["alts"]) < 2:
            return None
        cleaned = _reject_outliers(bucket["alts"])
        if not cleaned:
            return None
        return round(statistics.median(cleaned), 1)

    def get_slope_pct(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        dist_m: float,
    ) -> float | None:
        """Slope percentage between two coordinates using trusted altitudes.

        Returns None when either point lacks reference altitude.
        dist_m is the distance between the two points in metres.
        """
        if dist_m < 5:
            return None
        alt1 = self.get_altitude(lat1, lon1)
        alt2 = self.get_altitude(lat2, lon2)
        if alt1 is None or alt2 is None:
            return None
        return round((alt2 - alt1) / dist_m * 100, 2)

    def stats(self) -> dict:
        """Summary stats for the accumulated route reference."""
        total_points = sum(b["n"] for b in self._data.values())
        return {
            "buckets":            len(self._data),
            "buckets_confident":  self._count_confident(),
            "total_gps_points":   total_points,
            "path":               str(self._path),
            "exists":             self._path.exists(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest_csv(self, csv_path: Path) -> int:
        """Add quality GPS points from one ride CSV to the in-memory store."""
        added = 0
        try:
            with open(csv_path, newline="") as fh:
                first = fh.readline()
                if not first.startswith("#"):
                    fh.seek(0)
                reader = csv.DictReader(fh)
                for row in reader:
                    if not _is_quality_fix(row):
                        continue
                    try:
                        lat = float(row["gps_lat"])
                        lon = float(row["gps_lon"])
                        alt = float(row["gps_alt_m"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if lat == 0.0 or lon == 0.0 or alt == 0.0:
                        continue
                    key = _bucket_key(lat, lon)
                    if key not in self._data:
                        self._data[key] = {"alts": [], "n": 0}
                    bucket = self._data[key]
                    bucket["alts"].append(round(alt, 1))
                    # Cap history to avoid unbounded growth
                    if len(bucket["alts"]) > MAX_ALT_HISTORY:
                        bucket["alts"] = bucket["alts"][-MAX_ALT_HISTORY:]
                    bucket["n"] += 1
                    added += 1
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
