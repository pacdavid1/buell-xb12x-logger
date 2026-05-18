#!/usr/bin/env python3
from pathlib import Path, sys

BASE = Path('/home/pi/buell')

def patch_cell_tracker():
    fp = BASE / 'ddfi2_logger.py'
    src = fp.read_text()
    i = src.index('class CellTracker:')
    j = src.index('\n\nclass LiveHandler:', i)
    new = '''class CellTracker:
    """Acumula tiempo, EGO y flavor por celda VE 13x12."""
    FLAVORS = ("SWEET", "TIPIN", "TIPOUT", "WOT", "BITTER")

    def __init__(self):
        self.cells     = {}
        self.active    = None
        self._lock     = threading.Lock()
        self._dt       = 1.0 / 8.0
        self._prev_tps = None

    def reset(self):
        with self._lock:
            self.cells     = {}
            self.active    = None
            self._prev_tps = None

    def _classify_flavor(self, tps_10bit):
        tps_pct = (tps_10bit or 0) / 10.23
        if tps_pct > 80: return "WOT"
        if tps_pct < 10: return "BITTER"
        if self._prev_tps is not None:
            delta = (tps_10bit - self._prev_tps) / 10.23
            if delta > 1.5: return "TIPIN"
            if delta < -1.5: return "TIPOUT"
        return "SWEET"

    def update(self, data):
        rpm  = data.get("RPM",  0) or 0
        load = data.get("Load", 0) or 0
        ego  = data.get("EGO_Corr", 100) or 100
        tps  = data.get("TPS_10Bit", 0) or 0
        if rpm < 300:
            with self._lock:
                self.active = None
                self._prev_tps = None
            return
        key = cell_key(rpm, load)
        flavor = self._classify_flavor(tps)
        with self._lock:
            self.active = key
            self._prev_tps = tps
            c = self.cells.setdefault(key, {
                "seconds": 0.0, "ego_sum": 0.0, "count": 0,
                "flavor_seconds": {f: 0.0 for f in self.FLAVORS}
            })
            c["seconds"] += self._dt
            c["ego_sum"] += ego
            c["count"]   += 1
            c["flavor_seconds"][flavor] += self._dt

    def snapshot(self):
        with self._lock:
            snap = {}
            for k, v in self.cells.items():
                avg = round(v["ego_sum"]/v["count"], 1) if v["count"] else 100.0
                sweet = v["flavor_seconds"].get("SWEET", 0.0)
                conf = min(1.0, sweet / 20.0)
                snap[k] = {
                    "seconds":       round(v["seconds"], 1),
                    "ego_avg":       avg,
                    "confidence":    round(conf, 2),
                    "flavor_counts": {f: round(s, 1) for f, s in v["flavor_seconds"].items()},
                }
            return snap, self.active

'''
    src = src[:i] + new + src[j:]
    fp.write_text(src)
    print("  OK CellTracker")

def patch_get_coverage():
    fp = BASE / 'web' / 'server.py'
    src = fp.read_text()
    i = src.index('    def _get_coverage(self):')
    j = src.index('\n    def ', i + 10)
    new = '''    def _get_coverage(self):
        """Cobertura unificada: segundos, EGO, flavors por celda."""
        if not self.cell_tracker:
            return {"error": "tracker no disponible", "cells": {}, "summary": {}}
        snap, active = self.cell_tracker.snapshot()
        targets = self._coverage_targets
        flavors = [f for f in ("SWEET", "TIPIN", "TIPOUT", "WOT") if targets.get(f, 0) > 0]
        cells_out = {}
        summary = {f: {"done": 0, "total": 0, "pct": 0.0} for f in flavors}
        for key, c in snap.items():
            fc   = c.get("flavor_counts", {})
            conf = c.get("confidence", 0.0)
            entry = {
                "seconds": c.get("seconds", 0.0),
                "ego_avg": c.get("ego_avg", 100.0),
                "confidence": conf,
                "flavors": {},
            }
            for f in flavors:
                ts = targets[f]
                actual = fc.get(f, 0.0)
                conv = conf >= 0.8
                done = actual >= ts and conv
                pct = round(min(100.0, actual / ts * 100), 1) if ts > 0 else 0.0
                entry["flavors"][f] = {
                    "seconds": round(actual, 1), "target_s": ts,
                    "pct": pct, "converged": conv, "done": done
                }
                summary[f]["total"] += 1
                if done: summary[f]["done"] += 1
            cells_out[key] = entry
        for f in flavors:
            t, d = summary[f]["total"], summary[f]["done"]
            summary[f]["pct"] = round(d/t*100, 1) if t > 0 else 0.0
        return {
            "targets": targets, "cells": cells_out, "summary": summary,
            "active_cell": active, "n_cells": len(cells_out),
        }

'''
    src = src[:i] + new + src[j:]
    fp.write_text(src)
    print("  OK _get_coverage")

if __name__ == '__main__':
    print("Parcheando backend...")
    patch_cell_tracker()
    patch_get_coverage()
    print("Backend listo.")
