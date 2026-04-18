#!/usr/bin/env python3
"""
tools/recover_summaries.py — Genera summaries JSON para rides huérfanos.
Un ride huérfano es un CSV sin su correspondiente _summary.json.
Uso: python3 tools/recover_summaries.py
"""

import csv
import json
import sys
from datetime import timezone, datetime
from pathlib import Path

SESSIONS_DIR = Path("/home/pi/buell/sessions")

def recover_session(session_dir):
    cs = session_dir.name
    csvs = sorted(session_dir.glob(f"ride_{cs}_???.csv"))
    recovered = 0
    for csv_path in csvs:
        # Extraer ride_num del nombre
        stem = csv_path.stem  # ride_248AE2_001
        parts = stem.split("_")
        try:
            ride_num = int(parts[-1])
        except ValueError:
            continue

        summary_path = session_dir / f"ride_{cs}_{ride_num:03d}_summary.json"
        if summary_path.exists():
            continue  # ya tiene summary

        print(f"  Recuperando {csv_path.name}...")
        rows = []
        opened_utc = ""
        try:
            with open(csv_path, newline="") as f:
                filtered = (r for r in f if not r.startswith("#"))
                reader = csv.DictReader(filtered)
                for row in reader:
                    rows.append(row)
        except Exception as e:
            print(f"    ERROR leyendo CSV: {e}")
            continue

        if not rows:
            print(f"    CSV vacío, saltando")
            continue

        # Extraer metadata básica
        samples = len(rows)
        try:
            dur = float(rows[-1].get("time_elapsed_s", 0))
        except (ValueError, TypeError):
            dur = 0.0
        opened_utc = rows[0].get("timestamp_iso", "")
        closed_utc  = rows[-1].get("timestamp_iso", "")

        # RPM stats
        rpms = []
        for r in rows:
            try:
                rpms.append(int(r.get("RPM", 0) or 0))
            except (ValueError, TypeError):
                pass
        rpm_max = max(rpms) if rpms else 0
        rpm_avg = round(sum(rpms) / len(rpms), 1) if rpms else 0

        summary = {
            "ride_num":   ride_num,
            "session":    cs,
            "samples":    samples,
            "parts":      1,
            "duration_s": round(dur, 1),
            "opened_utc": opened_utc,
            "closed_utc": closed_utc,
            "reason":     "recovered_from_csv",
            "rpm_max":    rpm_max,
            "rpm_avg":    rpm_avg,
            "cells":      {},
            "objectives": [],
            "dtc_events": [],
        }

        try:
            tmp = summary_path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(summary, f, indent=2)
            tmp.replace(summary_path)
            print(f"    OK — {samples} samples, {dur:.0f}s")
            recovered += 1
        except Exception as e:
            print(f"    ERROR guardando summary: {e}")

    return recovered

def main():
    total = 0
    for session_dir in sorted(SESSIONS_DIR.iterdir()):
        if not session_dir.is_dir():
            continue
        print(f"Sesión {session_dir.name}:")
        n = recover_session(session_dir)
        print(f"  → {n} summaries recuperados")
        total += n
    print(f"\nTotal: {total} summaries recuperados")

if __name__ == "__main__":
    main()
