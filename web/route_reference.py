#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
route_reference.py -- Averaged road-grade profile from repeated passes.

Key finding (Phase 1 analysis): averaging GPS *altitude* across passes does NOT
converge -- the M8N vertical error has a large systematic component (std rose
with more passes instead of falling). So we pivot:

  - SLOPE comes from the barometer (BMP280), not GPS altitude. The baro has
    ~0.1 m relative resolution; its absolute offset drifts with weather day to
    day, but SLOPE is the derivative (dAlt/dDist) so the offset cancels. Slope
    should converge across passes even when absolute altitude does not.
  - POSITION comes from GPS horizontal (lat/lon, ~2.5 m, far better than its
    vertical).

For each ride: convert baro -> relative altitude, accumulate horizontal distance
from GPS, compute centered slope over a ~75 m window, bucket each point into a
spatial grid by GPS position, average slope per cell across all passes.

Pure stdlib so it runs identically on the Pi Zero.
"""
import csv
import glob
import math
import os
from collections import defaultdict

DEFAULT_CELL_M = 30.0    # grid cell size in meters
SLOPE_WINDOW_M = 75.0    # half-window each side for centered slope
MIN_SATS_POS = 4         # horizontal position needs a usable fix
EARTH_M_PER_DEG_LAT = 111320.0
SEA_LEVEL_HPA = 1013.25


def _sf(v, d=None):
    try:
        return float(v) if v is not None and str(v).strip() != '' else d
    except (ValueError, TypeError):
        return d


def _baro_to_alt(hpa):
    """Barometric altitude (m) via the international hypsometric formula.
    Absolute value depends on sea-level pressure (weather); only differences
    within a ride are used, so the offset is irrelevant for slope."""
    return 44330.0 * (1.0 - (hpa / SEA_LEVEL_HPA) ** 0.1903)


def _grid_steps(lat_deg, cell_m):
    dlat = cell_m / EARTH_M_PER_DEG_LAT
    dlon = cell_m / (EARTH_M_PER_DEG_LAT * max(0.1, math.cos(math.radians(lat_deg))))
    return dlat, dlon


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _load_ride_points(cp):
    """Return ordered list of points with cumulative distance and baro altitude
    for one ride: [{lat, lon, alt_b, dist}], filtered to usable position rows."""
    pts = []
    with open(cp) as fh:
        rd = csv.DictReader(l for l in fh if not l.startswith('#'))
        prev = None
        dist = 0.0
        for row in rd:
            if row.get('gps_valid', '').strip().lower() not in ('true', '1'):
                continue
            lat = _sf(row.get('gps_lat'))
            lon = _sf(row.get('gps_lon'))
            hpa = _sf(row.get('baro_hPa'))
            sats = _sf(row.get('gps_satellites'), 0)
            if lat is None or lon is None or hpa is None:
                continue
            if abs(lat) < 0.01 or sats < MIN_SATS_POS:
                continue
            if not (800 < hpa < 1100):
                continue
            if prev is not None:
                d = _haversine_m(prev[0], prev[1], lat, lon)
                if d > 50:           # gap (signal loss) -> break continuity
                    prev = (lat, lon)
                    continue
                dist += d
            else:
                dist = 0.0
            pts.append({'lat': lat, 'lon': lon, 'alt_b': _baro_to_alt(hpa), 'dist': dist})
            prev = (lat, lon)
    return pts


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Compass bearing (0-360) from point 1 to point 2."""
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.cos(math.radians(lon2 - lon1)))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _ride_slopes(pts, window_m=SLOPE_WINDOW_M):
    """Centered slope (%) and travel-direction sector per point.

    Slope carries sign by travel direction (uphill +, downhill -), so a cell
    driven both ways would average to ~0 with inflated spread. We tag each point
    with a heading sector (4 x 90 deg) so the grid separates directions."""
    out = []
    n = len(pts)
    j_lo = 0
    j_hi = 0
    for i in range(n):
        d0 = pts[i]['dist']
        while j_lo < n and pts[j_lo]['dist'] < d0 - window_m:
            j_lo += 1
        while j_hi < n and pts[j_hi]['dist'] < d0 + window_m:
            j_hi += 1
        lo = max(0, j_lo)
        hi = min(n - 1, j_hi)
        span = pts[hi]['dist'] - pts[lo]['dist']
        if span < window_m:          # not enough road on both sides
            continue
        dalt = pts[hi]['alt_b'] - pts[lo]['alt_b']
        slope_pct = 100.0 * dalt / span
        brg = _bearing_deg(pts[lo]['lat'], pts[lo]['lon'], pts[hi]['lat'], pts[hi]['lon'])
        sector = int(brg // 90)      # 0=NE,1=SE,2=SW,3=NW quadrant
        out.append((pts[i]['lat'], pts[i]['lon'], slope_pct, sector))
    return out


def build_slope_grid(buell_dir, sessions, cell_m=DEFAULT_CELL_M):
    """Average baro-derived road grade per spatial cell across all passes."""
    all_slopes = []   # (lat, lon, slope, sector, ride_id)
    for sid in sessions:
        for cp in sorted(glob.glob(os.path.join(buell_dir, 'sessions', sid, 'ride_*.csv'))):
            pts = _load_ride_points(cp)
            if len(pts) < 10:
                continue
            for lat, lon, slope, sector in _ride_slopes(pts):
                all_slopes.append((lat, lon, slope, sector, cp))
    if not all_slopes:
        return {}, {'rows': 0}

    ref_lat = sum(s[0] for s in all_slopes) / len(all_slopes)
    dlat, dlon = _grid_steps(ref_lat, cell_m)

    cells = defaultdict(lambda: {'sum': 0.0, 'sqsum': 0.0, 'n': 0, 'rides': set(),
                                 'lat_sum': 0.0, 'lon_sum': 0.0})
    for lat, lon, slope, sector, rid in all_slopes:
        gi = round(lat / dlat)
        gj = round(lon / dlon)
        c = cells[(gi, gj, sector)]
        c['sum'] += slope
        c['sqsum'] += slope * slope
        c['n'] += 1
        c['rides'].add(rid)
        c['lat_sum'] += lat
        c['lon_sum'] += lon

    grid = {}
    for k, c in cells.items():
        n = c['n']
        mean = c['sum'] / n
        var = max(0.0, c['sqsum'] / n - mean * mean)
        grid[k] = {
            'slope_mean': round(mean, 2),
            'slope_std': round(var ** 0.5, 2),
            'n_samples': n,
            'n_passes': len(c['rides']),
            'lat': round(c['lat_sum'] / n, 6),
            'lon': round(c['lon_sum'] / n, 6),
        }
    meta = {'rows': len(all_slopes), 'cells': len(grid), 'cell_m': cell_m,
            'window_m': SLOPE_WINDOW_M, 'ref_lat': round(ref_lat, 5)}
    return grid, meta


def convergence_report(grid, meta):
    """Does slope spread fall as passes accumulate? (the convergence test)."""
    by_passes = defaultdict(list)
    for cell in grid.values():
        by_passes[cell['n_passes']].append(cell['slope_std'])
    lines = [f"rows={meta['rows']}  cells={meta['cells']}  cell={meta['cell_m']}m  window={meta['window_m']}m"]
    multi = sum(1 for c in grid.values() if c['n_passes'] >= 2)
    lines.append(f"cells with >=2 passes: {multi} ({100*multi/max(1,len(grid)):.0f}%)")
    lines.append("")
    lines.append(f"{'passes':>6} {'cells':>6} {'avg_slope_std(%)':>17} {'median':>8}")
    for np_ in sorted(by_passes):
        stds = sorted(by_passes[np_])
        avg = sum(stds) / len(stds)
        med = stds[len(stds) // 2]
        lines.append(f"{np_:>6} {len(stds):>6} {avg:>17.2f} {med:>8.2f}")
    return "\n".join(lines)


if __name__ == '__main__':
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else '.'
    routes = ['47BF04', '653DC0', '91B225', '1E447A', '00210A']
    grid, meta = build_slope_grid(base, routes)
    print(convergence_report(grid, meta))
