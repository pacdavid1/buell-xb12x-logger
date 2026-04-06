#!/usr/bin/env python3
"""
analyze_session.py — Agrega rides de una sesión y genera reporte de tuning.
Uso: python3 analyze_session.py [CHECKSUM] [--rides 1,2,3] [--min-conf 0.3]
"""
import csv, bisect, json, sys, glob, argparse
from pathlib import Path
from datetime import datetime, timezone

RPM_BINS  = [0,800,1000,1350,1900,2400,2900,3400,4000,5000,6000,7000,8000]
LOAD_BINS = [10,15,20,30,40,50,60,80,100,125,175,255]
DT = 1.0 / 8.0

def cell_key(rpm, load):
    ri = max(0, bisect.bisect_right(RPM_BINS, rpm) - 1)
    li = max(0, bisect.bisect_right(LOAD_BINS, load) - 1)
    return f"{RPM_BINS[ri]}_{LOAD_BINS[li]}"

def is_valid(row, last_tps):
    wue   = float(row.get("WUE",       100) or 100)
    clt   = float(row.get("CLT",       999) or 999)
    rpm   = float(row.get("RPM",         0) or 0)
    afv   = float(row.get("AFV",       100) or 100)
    decel = float(row.get("fl_decel",    0) or 0)
    cut   = float(row.get("fl_fuel_cut", 0) or 0)
    tps   = float(row.get("TPS_pct",     0) or 0)
    delta = abs(tps - last_tps) if last_tps is not None else 0
    if wue   > 102:             return False, "WUE"
    if clt   < 70.0:            return False, "CLT_fria"
    if rpm   < 1200:            return False, "RPM_bajo"
    if afv < 80 or afv > 120:  return False, "AFV"
    if decel:                   return False, "decel"
    if cut:                     return False, "fuel_cut"
    if delta > 5.0:             return False, "TPS_delta"
    return True, ""

def process_csv(path):
    """Procesa un CSV y retorna acumuladores por celda + stats del ride."""
    cells = {}
    last_tps = None
    ride_stats = {"rows":0,"wot_rows":0,"max_rpm":0,"afv_vals":[],"clt_vals":[]}

    with open(path) as f:
        lines = [l for l in f if not l.startswith('#')]
    for row in csv.DictReader(lines):
        rpm  = float(row.get("RPM",  0) or 0)
        load = float(row.get("Load", 0) or 0)
        ego  = float(row.get("EGO_Corr", 100) or 100)
        clt  = float(row.get("CLT",  0) or 0)
        wue  = float(row.get("WUE",  100) or 100)
        afv  = float(row.get("AFV",  100) or 100)
        tps  = float(row.get("TPS_pct", 0) or 0)

        ride_stats["rows"] += 1
        if load > 80: ride_stats["wot_rows"] += 1
        if rpm > ride_stats["max_rpm"]: ride_stats["max_rpm"] = rpm
        if afv > 0: ride_stats["afv_vals"].append(afv)
        if clt > 0: ride_stats["clt_vals"].append(clt)

        if rpm < 300:
            last_tps = None
            continue
        key = cell_key(rpm, load)
        valid, reason = is_valid(row, last_tps)
        c = cells.setdefault(key, {
            "seconds":0.0,"ego_sum":0.0,"count":0,
            "valid_seconds":0.0,"valid_ego_sum":0.0,"valid_count":0,
            "clt_sum":0.0,"wue_sum":0.0,"afv_sum":0.0,"inv_reasons":{}
        })
        c["seconds"]  += DT; c["ego_sum"] += ego; c["count"] += 1
        c["clt_sum"]  += clt; c["wue_sum"] += wue; c["afv_sum"] += afv
        if valid:
            c["valid_seconds"] += DT
            c["valid_ego_sum"] += ego
            c["valid_count"]   += 1
        else:
            c["inv_reasons"][reason] = c["inv_reasons"].get(reason, 0) + 1
        last_tps = tps
    return cells, ride_stats

def merge_cells(agg, new):
    """Merge acumuladores de un ride en el agregado global."""
    for k, v in new.items():
        a = agg.setdefault(k, {
            "seconds":0.0,"ego_sum":0.0,"count":0,
            "valid_seconds":0.0,"valid_ego_sum":0.0,"valid_count":0,
            "clt_sum":0.0,"wue_sum":0.0,"afv_sum":0.0,"inv_reasons":{}
        })
        for f in ["seconds","ego_sum","count","valid_seconds","valid_ego_sum",
                  "valid_count","clt_sum","wue_sum","afv_sum"]:
            a[f] += v[f]
        for r, cnt in v["inv_reasons"].items():
            a["inv_reasons"][r] = a["inv_reasons"].get(r, 0) + cnt

def build_report(agg_cells, ride_list, session, min_conf):
    """Genera el reporte final de tuning."""
    cells_out = {}
    needs_more = []
    for k, v in agg_cells.items():
        n, vn = v["count"], v["valid_count"]
        conf = round(min(1.0, v["valid_seconds"] / 10.0), 2)
        ego_avg   = round(v["ego_sum"] / n, 2) if n else 100.0
        v_ego_avg = round(v["valid_ego_sum"] / vn, 2) if vn else None
        clt_avg   = round(v["clt_sum"] / n, 1) if n else None
        afv_avg   = round(v["afv_sum"] / n, 1) if n else None

        # Zona de operación
        rpm_s, load_s = k.split("_")
        rpm_v, load_v = int(rpm_s), int(load_s)
        if load_v >= 80:
            zone = "WOT"
            target_ego = 95.0   # Rico en WOT para proteger pistón
        elif load_v >= 40:
            zone = "crucero"
            target_ego = 100.0
        else:
            zone = "parcial"
            target_ego = 100.0

        # Sugerencia de corrección (solo si hay confianza)
        suggestion = None
        if conf >= min_conf and v_ego_avg is not None:
            error = v_ego_avg - target_ego
            if abs(error) > 2.0:  # Solo si error > 2%
                factor = round(target_ego / v_ego_avg, 4)
                # Limitar a 5% por iteración
                factor = max(0.95, min(1.05, factor))
                suggestion = {
                    "factor":     factor,
                    "error_pct":  round(error, 2),
                    "target_ego": target_ego,
                    "action":     "subir VE" if factor > 1 else "bajar VE",
                }
            if conf < 0.5:
                needs_more.append(k)

        cells_out[k] = {
            "zone":          zone,
            "seconds":       round(v["seconds"], 1),
            "valid_seconds": round(v["valid_seconds"], 1),
            "confidence":    conf,
            "ego_avg":       ego_avg,
            "valid_ego_avg": v_ego_avg,
            "clt_avg":       clt_avg,
            "afv_avg":       afv_avg,
            "inv_reasons":   v["inv_reasons"],
            "suggestion":    suggestion,
        }

    # Ordenar por zona + valid_seconds desc
    zone_order = {"WOT":0,"crucero":1,"parcial":2}
    cells_sorted = dict(sorted(cells_out.items(),
        key=lambda x: (zone_order.get(x[1]["zone"],3), -x[1]["valid_seconds"])))

    # Stats globales de AFV
    all_afv = []
    for v in agg_cells.values():
        if v["count"]: all_afv.append(v["afv_sum"]/v["count"])
    afv_global = round(sum(all_afv)/len(all_afv), 2) if all_afv else 100.0
    afv_action = "OK"
    if afv_global > 105: afv_action = f"⚠ AFV {afv_global:.1f}% — bajar mapa VE ~{afv_global-100:.0f}%"
    elif afv_global < 95: afv_action = f"⚠ AFV {afv_global:.1f}% — subir mapa VE ~{100-afv_global:.0f}%"

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "session":        session,
        "rides_analyzed": ride_list,
        "min_confidence": min_conf,
        "global": {
            "afv_avg":       afv_global,
            "afv_action":    afv_action,
            "cells_total":   len(cells_out),
            "cells_conf_ok": sum(1 for v in cells_out.values() if v["confidence"] >= min_conf),
            "cells_need_more": needs_more,
            "cells_with_suggestion": sum(1 for v in cells_out.values() if v["suggestion"]),
        },
        "cells": cells_sorted,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("session", nargs="?", default="248AE2")
    p.add_argument("--rides", help="Lista de rides ej: 1,8,9,27")
    p.add_argument("--min-conf", type=float, default=0.3)
    args = p.parse_args()

    sessions_dir = Path(__file__).parent / "sessions"
    sdir = sessions_dir / args.session
    if not sdir.exists():
        print(f"Sesión no encontrada: {sdir}"); sys.exit(1)

    # Buscar CSVs
    all_csvs = sorted(sdir.glob(f"ride_{args.session}_*.csv"))
    all_csvs = [f for f in all_csvs if "_p" not in f.stem]  # excluir partes
    if args.rides:
        nums = set(int(x) for x in args.rides.split(","))
        all_csvs = [f for f in all_csvs
                    if int(f.stem.split("_")[-1]) in nums]

    print(f"Procesando {len(all_csvs)} rides de sesión {args.session}...")
    agg = {}
    ride_list = []
    total_rows = 0

    for csv_path in all_csvs:
        ride_num = int(csv_path.stem.split("_")[-1])
        cells, stats = process_csv(csv_path)
        merge_cells(agg, cells)
        ride_list.append(ride_num)
        total_rows += stats["rows"]
        valid_pct = sum(c["valid_seconds"] for c in cells.values())
        total_s   = sum(c["seconds"]       for c in cells.values())
        pct = 100*valid_pct/total_s if total_s else 0
        print(f"  ride {ride_num:03d}: {stats['rows']:5} rows  "
              f"WOT={stats['wot_rows']:3}  maxRPM={stats['max_rpm']:.0f}  "
              f"válidos={pct:.0f}%")

    report = build_report(agg, ride_list, args.session, args.min_conf)
    out = sdir / f"tuning_report_{args.session}.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReporte generado: {out}")
    print(f"Total rows procesados: {total_rows:,}")
    print(f"Celdas analizadas:     {report['global']['cells_total']}")
    print(f"Con confianza OK:      {report['global']['cells_conf_ok']}")
    print(f"Con sugerencia:        {report['global']['cells_with_suggestion']}")
    print(f"AFV global:            {report['global']['afv_avg']} — {report['global']['afv_action']}")

if __name__ == "__main__":
    main()
