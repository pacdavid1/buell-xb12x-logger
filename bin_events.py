#!/usr/bin/env python3
"""Discovery v0.2 — Mostrar QUÉ condiciones existen, no buscar las que queremos"""
import csv, sys
from collections import defaultdict

RPM_BINS = [800,1200,1600,2000,2400,2800,3200,3600,4000,4400,4800,5200,5600,6000,6400,6800]
TPS_BINS = [0,5,10,15,20,25,30,35,40,50,60,70,80,90,100,101]

def bucket(val, bins):
    for i in range(len(bins)-1):
        if bins[i] <= val < bins[i+1]:
            return i
    return len(bins)-2

def safe_float(v, default=0.0):
    try:
        if v is None or str(v).strip() == "":
            return default
        return float(v)
    except:
        return default

def load(path):
    rows = []
    with open(path) as f:
        lines = [l for l in f if not l.startswith("#")]
    if not lines:
        return rows
    for r in csv.DictReader(lines):
        try:
            rpm = safe_float(r["RPM"])
            if rpm < 100:
                continue
            rows.append({
                "t":    safe_float(r["time_elapsed_s"]),
                "rpm":  rpm,
                "tps":  safe_float(r.get("TPS_pct") or r["TPD"]),
                "alt":  safe_float(r.get("gps_alt_m"), None),
                "gear": safe_float(r.get("Gear"), 0),
                "pw1":  safe_float(r["pw1"]),
                "spk":  safe_float(r["spark1"]),
                "clt":  safe_float(r["CLT"]),
                "eng":  safe_float(r.get("fl_engine_run"), 1),
                "wot":  safe_float(r.get("fl_wot"), 0),
                "cl":   safe_float(r.get("fl_closed_loop"), 1),
                "gps":  r.get("gps_valid","").strip() == "True",
            })
        except:
            continue
    return rows

def derivatives(rows):
    for i in range(1, len(rows)):
        dt = rows[i]["t"] - rows[i-1]["t"]
        if dt > 0:
            rows[i]["dr"] = (rows[i]["rpm"] - rows[i-1]["rpm"]) / dt
            rows[i]["dt"] = (rows[i]["tps"] - rows[i-1]["tps"]) / dt
            a0, a1 = rows[i-1]["alt"], rows[i]["alt"]
            rows[i]["da"] = (a1 - a0) / dt if a0 is not None and a1 is not None else None
        else:
            rows[i]["dr"] = rows[i-1].get("dr", 0)
            rows[i]["dt"] = rows[i-1].get("dt", 0)
            rows[i]["da"] = None
    if rows:
        rows[0]["dr"] = rows[0]["dt"] = 0
        rows[0]["da"] = None

def discover(rows):
    """Descubre todas las condiciones sin filtros predefinidos"""
    # Histograma 2D: cuantas muestras caen en cada celda
    hist = defaultdict(lambda: {"n":0, "dr":0, "dt":0, "da":0, "da_ok":0,
                                "pw":0, "clt":0, "gps":0})
    gear_hist = defaultdict(int)

    for r in rows:
        if r["eng"] == 0:
            continue
        bk = (bucket(r["rpm"], RPM_BINS), bucket(r["tps"], TPS_BINS))
        h = hist[bk]
        h["n"] += 1
        h["dr"] += r.get("dr", 0)
        h["dt"] += r.get("dt", 0)
        if r.get("da") is not None:
            h["da"] += abs(r["da"])
            h["da_ok"] += 1
        h["pw"] += r["pw1"]
        h["clt"] += r["clt"]
        if r["gps"]:
            h["gps"] += 1
        if r["gear"] >= 1:
            gear_hist[r["gear"]] += 1

    # Promedios
    result = {}
    for k, h in hist.items():
        n = h["n"]
        result[k] = {
            "n": n,
            "rpm_label": f"{RPM_BINS[k[0]]}-{RPM_BINS[k[0]+1]}",
            "tps_label": f"{TPS_BINS[k[1]]}-{TPS_BINS[k[1]+1]}",
            "avg_dr": h["dr"]/n,
            "avg_dt": h["dt"]/n,
            "avg_da": h["da"]/h["da_ok"] if h["da_ok"] > 0 else None,
            "avg_pw": h["pw"]/n,
            "avg_clt": h["clt"]/n,
            "gps_pct": h["gps"]/n*100,
        }
    return result, gear_hist

def show_discovered(path, rows, hist, gears):
    print(f"\n{'='*70}")
    print(f"  {path}")
    print(f"  {len(rows)} muestras | {rows[-1]['t']:.0f}s | gears: {dict(gears)}")
    print(f"{'='*70}")
    print(f"  {'RPM':>10} {'TPS':>8} {'N':>5} {'dRPM/s':>8} {'dTPS/s':>7} {'dAlt':>6} {'PW':>6} {'CLT':>5} {'GPS%':>5}")
    print(f"  {'-'*70}")

    # Ordenar por N descendente
    for k in sorted(hist.keys(), key=lambda x: hist[x]["n"], reverse=True):
        h = hist[k]
        da = f"{h['avg_da']:.1f}" if h['avg_da'] is not None else "N/A"
        # Etiquetas de tipo de condición
        tags = []
        if abs(h['avg_dr']) < 100 and abs(h['avg_dt']) < 3:
            tags.append("SS")
        if h['avg_dt'] > 15:
            tags.append("TIP-IN")
        if h['avg_dt'] < -15:
            tags.append("TIP-OUT")
        if TPS_BINS[k[1]] >= 80:
            tags.append("WOT")
        tag_str = " ".join(tags) if tags else ""

        print(f"  {h['rpm_label']:>10} {h['tps_label']:>8} {h['n']:>5} "
              f"{h['avg_dr']:>8.0f} {h['avg_dt']:>7.1f} {da:>6} {h['avg_pw']:>6.2f} "
              f"{h['avg_clt']:>5.0f} {h['gps_pct']:>4.0f}%  {tag_str}")

    # Resumen por tipo
    ss = sum(1 for h in hist.values() if abs(h['avg_dr'])<100 and abs(h['avg_dt'])<3 and h['n']>=5)
    wot = sum(1 for k,h in hist.items() if TPS_BINS[k[1]]>=80 and h['n']>=5)
    tip = sum(1 for h in hist.values() if h['avg_dt']>15 and h['n']>=5)
    print(f"\n  Resumen: {ss} steady-state, {wot} WOT, {tip} tip-in  (celdas con N>=5)")

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 bin_events.py <ride.csv> [ride2.csv ...]")
        sys.exit(1)

    all_results = {}
    for path in sys.argv[1:]:
        rows = load(path)
        if len(rows) < 10:
            print(f"SKIP: {path} ({len(rows)} muestras)")
            continue
        derivatives(rows)
        hist, gears = discover(rows)
        show_discovered(path, rows, hist, gears)
        all_results[path] = hist

    if len(all_results) == 2:
        p1, p2 = list(all_results.keys())
        h1, h2 = all_results[p1], all_results[p2]
        common = set(h1.keys()) & set(h2.keys())
        print(f"\n{'='*70}")
        print(f"  DELTA: {p1} VS {p2}")
        print(f"  {len(common)} celdas compartidas de {len(h1)} + {len(h2)}")
        print(f"{'='*70}")
        print(f"  {'RPM':>10} {'TPS':>8} {'N':>5} {'dRPM/s':>12} {'PW':>12} {'dAlt':>12}")
        print(f"  {'-'*70}")
        for k in sorted(common, key=lambda x: h1[x]["n"], reverse=True):
            a, b = h1[k], h2[k]
            dr = b["avg_dr"] - a["avg_dr"]
            dp = b["avg_pw"] - a["avg_pw"]
            da_a = a["avg_da"] if a["avg_da"] else 0
            da_b = b["avg_da"] if b["avg_da"] else 0
            dda = da_b - da_a
            print(f"  {a['rpm_label']:>10} {a['tps_label']:>8} "
                  f"{min(a['n'],b['n']):>5} "
                  f"{a['avg_dr']:>5.0f}->{b['avg_dr']:<5.0f} "
                  f"{a['avg_pw']:>5.2f}->{b['avg_pw']:<5.2f} "
                  f"{da_a:>5.1f}->{da_b:<5.1f}")

if __name__ == "__main__":
    main()
