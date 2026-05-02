#!/usr/bin/env python3
"""
classify_samples.py — Etiqueta cada muestra con su 'sabor' operativo.
Categorias: SWEET / SALTY_UP / SALTY_DOWN / SPICY_WOT / SPICY_TIPIN / SPICY_TIPOUT / BITTER
"""
import csv, sys, json
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
        if v is None or str(v).strip() == "": return default
        return float(v)
    except: return default

def safe_bool(v):
    return str(v).strip().lower() in ('1','true','yes')

def load(path):
    import os, glob as _glob
    rows = []
    if os.path.isdir(path):
        csv_files = sorted(_glob.glob(os.path.join(path, "ride_*.csv")))
        for cf in csv_files:
            with open(cf) as f:
                lines = [l for l in f if not l.startswith("#")]
            if not lines: continue
            for r in csv.DictReader(lines):
                try:
                    rpm = safe_float(r["RPM"])
                    if rpm < 100: continue
                    rows.append({
                        "t":        safe_float(r["time_elapsed_s"]),
                        "rpm":      rpm,
                        "tps":      safe_float(r.get("TPS_pct") or r.get("TPD", 0)),
                        "load":     safe_float(r.get("Load", 0)),
                        "clt":      safe_float(r["CLT"]),
                        "mat":      safe_float(r.get("MAT", 0)),
                        "pw1":      safe_float(r["pw1"]),
                        "pw2":      safe_float(r.get("pw2", 0)),
                        "spark":    safe_float(r["spark1"]),
                        "afv":      safe_float(r.get("AFV", 100)),
                        "ego":      safe_float(r.get("EGO_Corr", 100)),
                        "wue":      safe_float(r.get("WUE", 100)),
                        "ae":       safe_float(r.get("Accel_Corr", 100)),
                        "decel":    safe_float(r.get("Decel_Corr", 100)),
                        "gear":     safe_float(r.get("Gear", 0)),
                        "spd":      safe_float(r.get("VS_KPH", 0)),
                        "alt":      safe_float(r.get("gps_alt_m"), None) if r.get("gps_valid","").strip()=="True" else None,
                        "fl_wot":   safe_bool(r.get("fl_wot","0")),
                        "fl_decel": safe_bool(r.get("fl_decel","0")),
                        "fl_fc":    safe_bool(r.get("fl_fuel_cut","0")),
                        "fl_eng":   safe_bool(r.get("fl_engine_run","1")),
                        "fl_cl":    safe_bool(r.get("fl_closed_loop","0")),
                    })
                except: continue
    else:
        with open(path) as f:
            lines = [l for l in f if not l.startswith("#")]
        if not lines: return rows
        for r in csv.DictReader(lines):
            try:
                rpm = safe_float(r["RPM"])
                if rpm < 100: continue
                rows.append({
                    "t":        safe_float(r["time_elapsed_s"]),
                    "rpm":      rpm,
                    "tps":      safe_float(r.get("TPS_pct") or r.get("TPD", 0)),
                    "load":     safe_float(r.get("Load", 0)),
                    "clt":      safe_float(r["CLT"]),
                    "mat":      False,
                    "pw1":      safe_float(r["pw1"]),
                    "pw2":      safe_float(r.get("pw2", 0)),
                    "spark":    safe_float(r["spark1"]),
                    "afv":      safe_float(r.get("AFV", 100)),
                    "ego":      safe_float(r.get("EGO_Corr", 100)),
                    "wue":      safe_float(r.get("WUE", 100)),
                    "ae":       safe_float(r.get("Accel_Corr", 100)),
                    "decel":    safe_float(r.get("Decel_Corr", 100)),
                    "gear":     safe_float(r.get("Gear", 0)),
                    "spd":      safe_float(r.get("VS_KPH", 0)),
                    "alt":      None,
                    "fl_wot":   safe_bool(r.get("fl_wot","0")),
                    "fl_decel": safe_bool(r.get("fl_decel","0")),
                    "fl_fc":    safe_bool(r.get("fl_fuel_cut","0")),
                    "fl_eng":   safe_bool(r.get("fl_engine_run","1")),
                    "fl_cl":    safe_bool(r.get("fl_closed_loop","0")),
                })
            except: continue
    return rows

def derivatives(rows):
    for i in range(1, len(rows)):
        dt = rows[i]["t"] - rows[i-1]["t"]
        if 0 < dt < 2.0:
            rows[i]["drpm"] = (rows[i]["rpm"]  - rows[i-1]["rpm"]) / dt
            rows[i]["dtps"] = (rows[i]["tps"]  - rows[i-1]["tps"]) / dt
            a0, a1 = rows[i-1]["alt"], rows[i]["alt"]
            rows[i]["dalt"] = (a1 - a0) / dt if a0 is not None and a1 is not None else None
        else:
            rows[i]["drpm"] = 0.0
            rows[i]["dtps"] = 0.0
            rows[i]["dalt"] = None
    if rows:
        rows[0]["drpm"] = rows[0]["dtps"] = 0.0
        rows[0]["dalt"] = None

def classify(r):
    """Retorna el sabor de la muestra."""
    # BITTER — condiciones no analizables
    if not r["fl_eng"]:                    return "BITTER"
    if r["fl_fc"]:                         return "BITTER"
    if r["clt"] < 170:                     return "BITTER"  # motor frio
    if r["wue"] > 102:                     return "BITTER"  # WUE activo
    if r["ae"] > 105:                      return "BITTER"  # AE activo

    drpm = abs(r.get("drpm", 0))
    dtps = abs(r.get("dtps", 0))
    dalt = r.get("dalt")
    tps  = r["tps"]

    # SPICY_WOT — aceleracion plena
    if r["fl_wot"] or tps >= 80:
        if dtps > 15: return "SPICY_TIPIN"
        if dtps < -15: return "SPICY_TIPOUT"
        return "SPICY_WOT"

    # SPICY_TIPIN / TIPOUT — transitorios
    if dtps > 15:  return "SPICY_TIPIN"
    if dtps < -15: return "SPICY_TIPOUT"

    # Para SWEET y SALTY necesitamos estabilidad
    if drpm > 150 or abs(r.get("dtps", 0)) > 3:
        return "BITTER"  # transitorio no clasificado

    # Clasificar por pendiente
    if dalt is None:
        return "SWEET"  # sin GPS de altitud, asumir plano si pasa todo lo demas

    if dalt > 0.8:   return "SALTY_UP"
    if dalt < -0.8:  return "SALTY_DOWN"
    return "SWEET"

def bin_key(r):
    rb = bucket(r["rpm"], RPM_BINS)
    tb = bucket(r["tps"], TPS_BINS)
    return (rb, tb)

def build_index(rows):
    """Construye indice por (sabor, celda) con metricas promediadas."""
    idx = defaultdict(lambda: {
        "n":0, "pw":0, "spark":0, "clt":0, "afv":0, "ego":0,
        "drpm":0, "dalt_sum":0, "dalt_n":0, "spd":0, "gear_hist":defaultdict(int)
    })
    flavor_count = defaultdict(int)

    for r in rows:
        flavor = classify(r)
        flavor_count[flavor] += 1
        if flavor == "BITTER": continue

        k = (flavor, bin_key(r))
        c = idx[k]
        c["n"]    += 1
        c["pw"]   += r["pw1"]
        c["spark"]+= r["spark"]
        c["clt"]  += r["clt"]
        c["afv"]  += r["afv"]
        c["ego"]  += r["ego"]
        c["drpm"] += abs(r.get("drpm",0))
        c["spd"]  += r["spd"]
        if r.get("dalt") is not None:
            c["dalt_sum"] += r["dalt"]
            c["dalt_n"]   += 1
        if r["gear"] >= 1:
            c["gear_hist"][int(r["gear"])] += 1

    # Promediar
    result = {}
    for k, c in idx.items():
        n = c["n"]
        result[k] = {
            "flavor":     k[0],
            "rpm_label":  f"{RPM_BINS[k[1][0]]}-{RPM_BINS[k[1][0]+1]}",
            "tps_label":  f"{TPS_BINS[k[1][1]]}-{TPS_BINS[k[1][1]+1]}",
            "n":          n,
            "pw":         round(c["pw"]/n, 3),
            "spark":      round(c["spark"]/n, 2),
            "clt":        round(c["clt"]/n, 1),
            "afv":        round(c["afv"]/n, 1),
            "ego":        round(c["ego"]/n, 1),
            "drpm":       round(c["drpm"]/n, 1),
            "dalt":       round(c["dalt_sum"]/c["dalt_n"],2) if c["dalt_n"]>0 else None,
            "spd":        round(c["spd"]/n, 1),
            "top_gear":   max(c["gear_hist"], key=c["gear_hist"].get) if c["gear_hist"] else 0,
        }
    return result, flavor_count

def show(path, index, flavor_count, min_n=5):
    cs = os.path.basename(os.path.dirname(path))
    print(f"\n{'='*72}")
    print(f"  {path}  [checksum: {session_checksum(path)}]")
    total = sum(flavor_count.values())
    total = sum(flavor_count.values())
    print(f"\n{'='*72}")
    print(f"  {path}")
    print(f"  Total: {total} | " + " | ".join(f"{k}:{v}" for k,v in sorted(flavor_count.items())))
    print(f"{'='*72}")

    flavors = ["SWEET","SALTY_UP","SALTY_DOWN","SPICY_WOT","SPICY_TIPIN","SPICY_TIPOUT"]
    for flavor in flavors:
        cells = {k:v for k,v in index.items() if k[0]==flavor and v["n"]>=min_n}
        if not cells: continue
        print(f"\n  [{flavor}]  {len(cells)} celdas con N>={min_n}")
        print(f"  {'RPM':>10} {'TPS':>8} {'N':>5} {'PW':>6} {'SPK':>6} {'CLT':>5} {'AFV':>5} {'dAlt':>6} {'Gear':>5}")
        print(f"  {'-'*70}")
        for k in sorted(cells, key=lambda x: cells[x]["n"], reverse=True):
            c = cells[k]
            da = f"{c['dalt']:+.2f}" if c['dalt'] is not None else "N/A"
            print(f"  {c['rpm_label']:>10} {c['tps_label']:>8} {c['n']:>5} "
                  f"{c['pw']:>6.3f} {c['spark']:>6.2f} {c['clt']:>5.0f} "
                  f"{c['afv']:>5.1f} {da:>6} {c['top_gear']:>5}")

def compare(path_a, idx_a, path_b, idx_b, min_n=5):
    cs_a = os.path.basename(os.path.dirname(path_a))
    cs_b = os.path.basename(os.path.dirname(path_b))
    warn = ""
    try:
        mp_a = os.path.join(os.path.dirname(path_a), "session_metadata.json")
        mp_b = os.path.join(os.path.dirname(path_b), "session_metadata.json")
        with open(mp_a) as f: ca = _json.load(f).get("checksum","?")
        with open(mp_b) as f: cb = _json.load(f).get("checksum","?")
        if ca != cb:
            warn = f"  ⚠️ CHECKSUM DIFERENTE: {ca} vs {cb}"
    except: pass
    print(f"\n{'='*72}")
    print(f"  DELTA: {cs_a} VS {cs_b}{warn}")
    print(f"{'='*72}")

    flavors = ["SWEET","SPICY_WOT"]
    for flavor in flavors:
        ka = {k[1]:v for k,v in idx_a.items() if k[0]==flavor and v["n"]>=min_n}
        kb = {k[1]:v for k,v in idx_b.items() if k[0]==flavor and v["n"]>=min_n}
        common = set(ka) & set(kb)
        if not common: continue
        print(f"\n  [{flavor}]  {len(common)} celdas comunes")
        print(f"  {'RPM':>10} {'TPS':>8} {'N_A':>5} {'N_B':>5} {'dPW':>8} {'dSPK':>7} {'dCLT':>6}")
        print(f"  {'-'*65}")
        for cell in sorted(common, key=lambda x: ka[x]["n"], reverse=True):
            a, b = ka[cell], kb[cell]
            dpw  = b["pw"]    - a["pw"]
            dspk = b["spark"] - a["spark"]
            dclt = b["clt"]   - a["clt"]
            sign_pw  = "+" if dpw  >= 0 else ""
            sign_spk = "+" if dspk >= 0 else ""
            sign_clt = "+" if dclt >= 0 else ""
            print(f"  {a['rpm_label']:>10} {a['tps_label']:>8} {a['n']:>5} {b['n']:>5} "
                  f"{sign_pw}{dpw:>6.3f}  {sign_spk}{dspk:>5.2f}  {sign_clt}{dclt:>5.1f}")

if __name__ == "__main__":
    import json as _json
    def session_checksum(path):
        mp = os.path.join(path, "session_metadata.json")
        if os.path.exists(mp):
            with open(mp) as f: return _json.load(f).get("checksum","?")
        return os.path.basename(path)
    if len(sys.argv) < 2:
        print("Uso: python3 classify_samples.py <ride.csv> [ride2.csv]")
        sys.exit(1)

    results = []
    for path in sys.argv[1:]:
        rows = load(path)
        if len(rows) < 10:
            print(f"SKIP: {path}")
            continue
        derivatives(rows)
        idx, fc = build_index(rows)
        show(path, idx, fc)
        results.append((path, idx))

    if len(results) == 2:
        compare(results[0][0], results[0][1], results[1][0], results[1][1])
