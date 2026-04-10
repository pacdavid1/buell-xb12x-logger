#!/usr/bin/env python3
"""
ecu/session.py — SessionManager: grabación de rides en CSV + summaries JSON
Extraído de ddfi2_logger.py para modularización v2.0

Responsabilidades:
  - Agrupar rides por checksum de versión ECU (sesión)
  - Grabar CSV por ride con todos los parámetros RT
  - Generar summary JSON al cerrar cada ride
  - Evaluar objetivos de cobertura de celdas VE
  - Generar consolidated.csv por sesión
"""

import bisect
import csv
import hashlib
import json
import logging
import time
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ecu.protocol import CSV_COLUMNS, RPM_BINS, LOAD_BINS

LOGGER_VERSION = "v2.3.0-MODULAR"
MAX_CSV_ROWS   = 10000  # ~20 min a 8Hz


class SessionManager:
    def __init__(self, sessions_dir):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("Session")
        self.current_checksum    = None
        self.current_session_dir = None
        self.current_ride_num    = 0
        self.current_csv_fh      = None
        self.current_writer      = None
        self.ride_start_time     = None
        self.ride_sample_count   = 0
        self.session_metadata    = {}
        self.last_elapsed_s      = 0
        self.current_part        = 1
        self.current_part_rows   = 0

    def _checksum(self, blob):
        """Calculate session checksum from tune region of EEPROM blob.
        Excludes volatile bytes (offsets 0-326) — counters, DTCs, boot state.
        Only hashes tune data (offset 327+) so checksum is stable across restarts."""
        return hashlib.md5(blob[327:]).hexdigest()[:6].upper()

    def _load_or_create(self, cs, version_str):
        sdir = self.sessions_dir / cs
        meta_file = sdir / "session_metadata.json"
        if sdir.exists() and meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)
            self.logger.info(f"Sesión existente: {cs} ({meta.get('total_rides',0)} rides)")
        else:
            sdir.mkdir(parents=True, exist_ok=True)
            meta = {
                "checksum": cs, "version_string": version_str,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "total_rides": 0, "total_samples": 0,
                "total_runtime_seconds": 0,
                "rpm_min_seen": 99999, "rpm_max_seen": 0
            }
            self.logger.info(f"Nueva sesión: {cs} firmware={version_str}")
        return sdir, meta

    def open_session(self, version_str, blob):
        """Open or resume session based on EEPROM blob checksum.
        A new session is created whenever ECU parameters change."""
        new_cs = self._checksum(blob)
        if new_cs == self.current_checksum:
            return False
        if self.current_checksum is not None:
            self.logger.info(f"Checksum changed {self.current_checksum}→{new_cs} — new session")
            self.close_current_ride("eeprom_changed")
        self.current_checksum = new_cs
        self.current_session_dir, self.session_metadata = self._load_or_create(new_cs, version_str)
        self.logger.info(f"Session active: {new_cs} | firmware={version_str}")
        self._generate_consolidated()
        eeprom_file = self.current_session_dir / "eeprom.bin"
        return not eeprom_file.exists()

    def save_eeprom(self, blob):
        """Guarda blob EEPROM en sessions/CHECKSUM/eeprom.bin."""
        if not self.current_session_dir or not blob:
            return
        eeprom_file = self.current_session_dir / "eeprom.bin"
        tmp = eeprom_file.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(blob)
        tmp.replace(eeprom_file)
        self.logger.info(f"EEPROM guardada: {eeprom_file.name} ({len(blob)} bytes)")

    def load_eeprom(self):
        """Carga eeprom.bin de la sesión actual. Retorna bytes o None."""
        if not self.current_session_dir:
            return None
        eeprom_file = self.current_session_dir / "eeprom.bin"
        if not eeprom_file.exists():
            return None
        with open(eeprom_file, "rb") as f:
            return f.read()


    def start_ride(self):
        if not self.current_session_dir:
            raise RuntimeError("Sin sesión activa")
        self.session_metadata["total_rides"] = self.session_metadata.get("total_rides", 0) + 1
        self.current_ride_num  = self.session_metadata["total_rides"]
        self.current_part      = 1
        self.current_part_rows = 0
        self._open_csv_part()
        self.ride_start_time   = time.monotonic()
        self.ride_sample_count = 0
        self._ride_start_utc   = datetime.now(timezone.utc).isoformat()
        self._save_metadata()
        self.logger.info(f"Ride {self.current_ride_num:03d} iniciado")

    def _open_csv_part(self):
        """Abre el archivo CSV de la parte actual del ride."""
        suffix    = f"_p{self.current_part}" if self.current_part > 1 else ""
        ride_file = self.current_session_dir / f"ride_{self.current_checksum}_{self.current_ride_num:03d}{suffix}.csv"
        if self.current_csv_fh:
            self.current_csv_fh.close()
        self.current_csv_fh = open(ride_file, "w", newline="", buffering=1)
        self.current_csv_fh.write(f"# logger={LOGGER_VERSION}\n")
        self.current_writer = csv.DictWriter(
            self.current_csv_fh, fieldnames=CSV_COLUMNS, extrasaction="ignore"
        )
        self.current_writer.writeheader()
        self.current_part_rows = 0
        if self.current_part > 1:
            self.logger.info(f"Ride {self.current_ride_num:03d} parte {self.current_part} ({ride_file.name})")

    def write_sample(self, data_dict, wall_time):
        if not self.current_writer:
            return
        row = dict(data_dict)
        row["ride_num"]       = self.current_ride_num
        row["timestamp_iso"]  = datetime.fromtimestamp(wall_time, tz=timezone.utc).isoformat()
        row["time_elapsed_s"] = round(time.monotonic() - self.ride_start_time, 3)
        self.last_elapsed_s   = row["time_elapsed_s"]
        self.current_writer.writerow(row)
        self.ride_sample_count  += 1
        self.current_part_rows  += 1
        rpm = data_dict.get("RPM", 0) or 0
        if rpm > self.session_metadata.get("rpm_max_seen", 0):
            self.session_metadata["rpm_max_seen"] = rpm
        if 0 < rpm < self.session_metadata.get("rpm_min_seen", 99999):
            self.session_metadata["rpm_min_seen"] = rpm
        if self.current_part_rows >= MAX_CSV_ROWS:
            self.current_part += 1
            self._open_csv_part()

    def close_current_ride(self, reason="", tracker_snapshot=None,
                           objectives_cfg=None, dtc_log=None):
        if not self.current_csv_fh:
            return
        dur = self.last_elapsed_s if self.last_elapsed_s else (
            time.monotonic() - self.ride_start_time if self.ride_start_time else 0
        )
        self.current_csv_fh.close()
        self.current_csv_fh = None
        self.current_writer = None
        self.session_metadata["total_samples"] = (
            self.session_metadata.get("total_samples", 0) + self.ride_sample_count
        )
        self.session_metadata["total_runtime_seconds"] = (
            self.session_metadata.get("total_runtime_seconds", 0) + dur
        )
        self.logger.info(
            f"Ride {self.current_ride_num:03d} cerrado — "
            f"{self.ride_sample_count} muestras, {dur:.0f}s, "
            f"{self.current_part} parte(s)" + (f" ({reason})" if reason else "")
        )
        if tracker_snapshot is not None and self.current_session_dir:
            cells, _ = tracker_snapshot
            objectives_out = []
            for ct in (objectives_cfg or {}).get("cell_targets", []):
                rpm_min  = ct.get("rpm_min", 0);  rpm_max  = ct.get("rpm_max", 9999)
                load_min = ct.get("load_min", 0); load_max = ct.get("load_max", 255)
                target_s = ct.get("seconds", 5)
                matching = [
                    f"{r}_{l}" for r in RPM_BINS for l in LOAD_BINS
                    if rpm_min <= r <= rpm_max and load_min <= l <= load_max
                ]
                done = sum(1 for k in matching if cells.get(k, {}).get("seconds", 0) >= target_s)
                pct  = (done / len(matching) * 100) if matching else 0
                objectives_out.append({
                    "label": ct.get("label", ""), "target_s": target_s,
                    "done_cells": done, "total_cells": len(matching),
                    "pct": round(pct, 1)
                })
            summary = {
                "ride_num":   self.current_ride_num,
                "session":    self.current_checksum,
                "samples":    self.ride_sample_count,
                "parts":      self.current_part,
                "duration_s": round(dur, 1),
                "opened_utc": getattr(self, "_ride_start_utc", ""),
                "closed_utc": datetime.now(timezone.utc).isoformat(),
                "reason":     reason,
                "cells":      cells,
                "objectives": objectives_out,
                "dtc_events": dtc_log or [],
            }
            sfile = self.current_session_dir / f"ride_{self.current_checksum}_{self.current_ride_num:03d}_summary.json"
            try:
                tmp = sfile.with_suffix(".tmp")
                with open(tmp, "w") as f:
                    json.dump(summary, f)
                tmp.replace(sfile)
                self.logger.info(f"Summary guardado: {sfile.name}")
                self._update_tuning_report(summary)
            except Exception as e:
                self.logger.warning(f"Error guardando summary: {e}")
        self._save_metadata()
        self._generate_consolidated()

    def _update_tuning_report(self, summary):
        """Actualiza tuning_report incremental con el summary del ride recién cerrado.
        Solo procesa rides con el nuevo formato (valid_seconds en cells).
        Ignora rides viejos silenciosamente."""
        if not self.current_session_dir:
            return
        cells = summary.get("cells", {})
        # Verificar que es formato nuevo — tiene valid_seconds
        sample = next(iter(cells.values()), {}) if cells else {}
        if "valid_seconds" not in sample:
            self.logger.debug("Tuning report: summary formato viejo, ignorado")
            return

        report_path = self.current_session_dir / f"tuning_report_{self.current_checksum}.json"

        # Cargar reporte existente o inicializar
        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)
            except Exception:
                report = {}
        else:
            report = {}

        agg = report.get("agg_cells", {})
        rides_included = report.get("rides_included", [])
        ride_num = summary.get("ride_num")

        if ride_num in rides_included:
            self.logger.debug(f"Tuning report: ride {ride_num} ya incluido")
            return

        # Merge cells del ride nuevo en el agregado
        for k, v in cells.items():
            a = agg.setdefault(k, {
                "seconds":0.0, "ego_sum":0.0, "count":0,
                "valid_seconds":0.0, "valid_ego_sum":0.0, "valid_count":0,
                "clt_sum":0.0, "wue_sum":0.0, "afv_sum":0.0, "inv_reasons":{}
            })
            vs  = v.get("valid_seconds", 0.0)
            vn  = v.get("valid_count",   v.get("count", 0))
            vea = v.get("valid_ego_avg")
            ea  = v.get("ego_avg", 100.0)
            s   = v.get("seconds", 0.0)
            n   = v.get("count",   int(s * 8))
            a["seconds"]       += s
            a["ego_sum"]       += ea * n
            a["count"]         += n
            a["valid_seconds"] += vs
            a["valid_ego_sum"] += (vea * vn) if vea and vn else 0.0
            a["valid_count"]   += vn
            a["clt_sum"]       += (v.get("clt_avg") or 0.0) * n
            a["wue_sum"]       += (v.get("wue_avg") or 0.0) * n
            a["afv_sum"]       += (v.get("afv_avg") or 0.0) * n
            for r, cnt in v.get("inv_reasons", {}).items():
                a["inv_reasons"][r] = a["inv_reasons"].get(r, 0) + cnt

        rides_included.append(ride_num)

        # Calcular vista procesada
        cells_out = {}
        for k, a in agg.items():
            n, vn = a["count"], a["valid_count"]
            conf     = round(min(1.0, a["valid_seconds"] / 10.0), 2)
            ego_avg  = round(a["ego_sum"]       / n,  2) if n  else 100.0
            v_ego    = round(a["valid_ego_sum"] / vn, 2) if vn else None
            clt_avg  = round(a["clt_sum"]  / n, 1) if n else None
            afv_avg  = round(a["afv_sum"]  / n, 1) if n else None
            rpm_v    = int(k.split("_")[0])
            load_v   = int(k.split("_")[1])
            if load_v >= 80:
                zone, target = "WOT",     95.0
            elif load_v >= 40:
                zone, target = "crucero", 100.0
            else:
                zone, target = "parcial", 100.0
            suggestion = None
            if conf >= 0.3 and v_ego is not None and abs(v_ego - target) > 2.0:
                factor = round(target / v_ego, 4)
                factor = max(0.95, min(1.05, factor))
                suggestion = {
                    "factor":     factor,
                    "error_pct":  round(v_ego - target, 2),
                    "target_ego": target,
                    "action":     "subir VE" if factor > 1 else "bajar VE",
                }
            cells_out[k] = {
                "zone":          zone,
                "seconds":       round(a["seconds"], 1),
                "valid_seconds": round(a["valid_seconds"], 1),
                "confidence":    conf,
                "ego_avg":       ego_avg,
                "valid_ego_avg": v_ego,
                "clt_avg":       clt_avg,
                "afv_avg":       afv_avg,
                "inv_reasons":   a["inv_reasons"],
                "suggestion":    suggestion,
            }

        # AFV global
        afv_vals = [a["afv_sum"]/a["count"] for a in agg.values() if a["count"]]
        afv_global = round(sum(afv_vals)/len(afv_vals), 2) if afv_vals else 100.0
        afv_action = "OK"
        if afv_global > 105:
            afv_action = f"bajar mapa VE ~{afv_global-100:.0f}%"
        elif afv_global < 95:
            afv_action = f"subir mapa VE ~{100-afv_global:.0f}%"

        # Cargar eeprom_decoded si existe — viaja junto con el reporte
        eeprom_snapshot = None
        eeprom_path = self.current_session_dir / "eeprom_decoded.json"
        if eeprom_path.exists():
            try:
                with open(eeprom_path) as f:
                    eeprom_snapshot = json.load(f)
            except Exception:
                pass

        report = {
            "generated_utc":  summary.get("closed_utc", ""),
            "session":         self.current_checksum,
            "rides_included":  sorted(rides_included),
            "agg_cells":       agg,
            "global": {
                "afv_avg":               afv_global,
                "afv_action":            afv_action,
                "cells_total":           len(cells_out),
                "cells_conf_ok":         sum(1 for v in cells_out.values() if v["confidence"] >= 0.3),
                "cells_with_suggestion": sum(1 for v in cells_out.values() if v["suggestion"]),
            },
            "cells":  cells_out,
            "eeprom": eeprom_snapshot,
        }

        tmp = report_path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(report, f)
            tmp.replace(report_path)
            self.logger.info(
                f"Tuning report actualizado: ride {ride_num} | "
                f"{len(cells_out)} celdas | "
                f"{report['global']['cells_with_suggestion']} sugerencias"
            )
            self._generate_suggested_msq(report)
        except Exception as e:
            self.logger.warning(f"Error guardando tuning report: {e}")

    def _generate_suggested_msq(self, report):
        """Genera MSQ con sugerencias aplicadas sobre el EEPROM actual."""
        if not self.current_session_dir:
            return
        eeprom_path = self.current_session_dir / "eeprom_decoded.json"
        if not eeprom_path.exists():
            return
        try:
            with open(eeprom_path) as f:
                eeprom = json.load(f)
        except Exception as e:
            self.logger.warning(f"MSQ gen: no se pudo leer eeprom_decoded: {e}")
            return
        import copy
        maps       = eeprom.get("maps", {})
        axes       = maps.get("axes", {})
        cells      = report.get("cells", {})
        fuel_front = copy.deepcopy(maps.get("fuel_front", []))
        fuel_rear  = copy.deepcopy(maps.get("fuel_rear",  []))
        spark_front= copy.deepcopy(maps.get("spark_front",[]))
        spark_rear = copy.deepcopy(maps.get("spark_rear", []))
        fuel_rpm   = axes.get("fuel_rpm",  [])
        fuel_load  = axes.get("fuel_load", [])
        applied = 0
        for key, cell in cells.items():
            sug = cell.get("suggestion")
            if not sug:
                continue
            try:
                rpm_v  = int(key.split("_")[0])
                load_v = int(key.split("_")[1])
                if rpm_v not in fuel_rpm or load_v not in fuel_load:
                    continue
                ri = fuel_rpm.index(rpm_v)
                li = fuel_load.index(load_v)
                if fuel_front and li < len(fuel_front) and ri < len(fuel_front[li]):
                    ve_old = fuel_front[li][ri]
                    if ve_old is not None:
                        fuel_front[li][ri] = max(10, min(250, round(ve_old * sug["factor"])))
                        applied += 1
            except Exception:
                continue
        if applied == 0:
            self.logger.debug("MSQ gen: sin sugerencias que aplicar")
            return

        def ax1b(vals):
            return "\n".join("      " + str(v) for v in vals)
        def ax2b(vals):
            return "\n".join("    " + str(v) for v in vals)
        def mapfuel(table):
            return "\n".join("      " + " ".join(
                str(int(v)) if v is not None else "0" for v in row
            ) for row in table)
        def mapspark(table):
            return "\n".join("      " + " ".join(
                "{:.2f}".format(v) if v is not None else "0.00" for v in row
            ) for row in table)

        from datetime import datetime, timezone
        now   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        rides = ",".join(str(r) for r in report.get("rides_included", []))
        sl    = axes.get("spark_load", [])
        sr    = axes.get("spark_rpm",  [])

        lines = [
            '<?xml version="1.0"?>',
            '<msq xmlns="http://www.ecmspy.com/">',
            '  <bibliography author="BuellLogger/' + now + ' rides=' + rides + '" writeDate="' + now + '" />',
            '  <versionInfo fileFormat="4" nPages="1" signature="BUEIB" />',
            '  <page number="0">',
            '    <constant name="z_factor">4.00</constant>',
            '    <constant name="tpsBins1" rows="12" units="TPS">',
            ax1b(fuel_load),
            '</constant>',
            '    <constant name="rpmBins1" rows="13" units="RPM">',
            ax2b(fuel_rpm),
            '</constant>',
            '    <constant name="veBins1" rows="12" cols="13" units="fuel">',
            mapfuel(fuel_front),
            '',
            '</constant>',
            '    <constant name="tpsBins2" rows="12" units="TPS">',
            ax1b(fuel_load),
            '</constant>',
            '    <constant name="rpmBins2" rows="13" units="RPM">',
            ax2b(fuel_rpm),
            '</constant>',
            '    <constant name="veBins2" rows="12" cols="13" units="fuel">',
            mapfuel(fuel_rear),
            '',
            '</constant>',
            '    <constant name="tpsBins3" rows="10" units="TPS">',
            ax1b(sl),
            '</constant>',
            '    <constant name="rpmBins3" rows="10" units="RPM">',
            ax2b(sr),
            '</constant>',
            '    <constant name="advTable1" rows="10" cols="10" units="deg BTDC">',
            mapspark(spark_front),
            '',
            '</constant>',
            '    <constant name="tpsBins4" rows="10" units="TPS">',
            ax1b(sl),
            '</constant>',
            '    <constant name="rpmBins4" rows="10" units="RPM">',
            ax2b(sr),
            '</constant>',
            '    <constant name="advTable2" rows="10" cols="10" units="deg BTDC">',
            mapspark(spark_rear),
            '',
            '</constant>',
            '  </page>',
            '</msq>',
        ]
        msq_path = self.current_session_dir / ("suggested_" + self.current_checksum + ".msq")
        tmp = msq_path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                f.write("\n".join(lines))
            tmp.replace(msq_path)
            self.logger.info(
                "MSQ sugerido generado: " + msq_path.name +
                " (" + str(applied) + " celdas modificadas)"
            )
        except Exception as e:
            self.logger.warning("Error guardando MSQ: " + str(e))

    def _save_metadata(self):
        if not self.current_session_dir:
            return
        meta_file = self.current_session_dir / "session_metadata.json"
        tmp = meta_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self.session_metadata, f, indent=2)
        tmp.replace(meta_file)

    def _generate_consolidated(self):
        if not self.current_session_dir:
            return
        ride_files = sorted(self.current_session_dir.glob("ride_*.csv"))
        if not ride_files:
            return
        consolidated = self.current_session_dir / "consolidated.csv"
        tmp          = self.current_session_dir / "consolidated.tmp"
        try:
            with open(tmp, "w", newline="") as out_fh:
                writer = None
                for rf in ride_files:
                    with open(rf, newline="") as in_fh:
                        filtered = (l for l in in_fh if not l.startswith('#'))
                        reader   = csv.DictReader(filtered)
                        if writer is None:
                            writer = csv.DictWriter(
                                out_fh, fieldnames=reader.fieldnames, extrasaction="ignore"
                            )
                            writer.writeheader()
                        for row in reader:
                            writer.writerow(row)
            tmp.replace(consolidated)
            self.logger.debug("consolidated.csv regenerado")
        except Exception as e:
            self.logger.warning(f"Error consolidated: {e}")

def cell_key(rpm, load):
    import bisect
    ri = bisect.bisect_right(RPM_BINS, rpm) - 1
    li = bisect.bisect_right(LOAD_BINS, load) - 1
    ri = max(0, min(ri, len(RPM_BINS) - 1))
    li = max(0, min(li, len(LOAD_BINS) - 1))
    return f"{RPM_BINS[ri]}_{LOAD_BINS[li]}"


class CellTracker:
    """Acumula tiempo y EGO promedio por celda del mapa VE 13x12.
    También acumula campos de calidad para análisis de tuning:
    CLT, WUE, AFV promedios; segundos válidos vs totales."""
    def __init__(self):
        self.cells  = {}
        self.active = None
        self._lock  = threading.Lock()
        self._dt    = 1.0 / 8.0
        self._last_tps = None  # Para delta TPS

    def reset(self):
        with self._lock:
            self.cells  = {}
            self.active = None

    def _is_valid(self, data, tps_now):
        """Retorna (bool, str) — si el sample es válido para tuning y por qué no."""
        wue      = data.get("WUE",       100) or 100
        clt      = data.get("CLT",       999) or 999
        rpm      = data.get("RPM",         0) or 0
        afv      = data.get("AFV",       100) or 100
        fl_decel = data.get("fl_decel",    0) or 0
        fl_cut   = data.get("fl_fuel_cut", 0) or 0
        # Delta TPS: transitorio de aceleración
        tps_delta = abs(tps_now - self._last_tps) if self._last_tps is not None else 0
        if wue > 102:           return False, "WUE"
        if clt < 70.0:          return False, "CLT_fria"
        if rpm < 1200:          return False, "RPM_bajo"
        if afv < 80 or afv > 120: return False, "AFV"
        if fl_decel:            return False, "decel"
        if fl_cut:              return False, "fuel_cut"
        if tps_delta > 5.0:     return False, "TPS_delta"
        return True, ""

    HARDNESS = 0.3  # Velocidad de aprendizaje IIR (0.1=lento, 0.5=rapido)

    def _empty_cell(self):
        return {
            "seconds": 0.0, "ego_sum": 0.0, "count": 0.0,
            "valid_seconds": 0.0, "valid_ego_sum": 0.0, "valid_count": 0.0,
            "ego_iir": None,
            "clt_sum": 0.0, "wue_sum": 0.0, "afv_sum": 0.0,
            "inv_reasons": {}
        }

    def _bilinear_weights(self, rpm, load):
        """Distribuye un sample entre los 4 vecinos del mapa VE con pesos bilineales.
        Consistente con la interpolacion que usa el ECU al aplicar el mapa."""
        ri = max(0, min(bisect.bisect_right(RPM_BINS, rpm) - 1, len(RPM_BINS) - 2))
        li = max(0, min(bisect.bisect_right(LOAD_BINS, load) - 1, len(LOAD_BINS) - 2))
        r0, r1 = RPM_BINS[ri], RPM_BINS[ri + 1]
        l0, l1 = LOAD_BINS[li], LOAD_BINS[li + 1]
        tr = (rpm  - r0) / (r1 - r0) if r1 != r0 else 0.0
        tl = (load - l0) / (l1 - l0) if l1 != l0 else 0.0
        return [
            (f"{r0}_{l0}", (1 - tr) * (1 - tl)),
            (f"{r0}_{l1}", (1 - tr) *      tl ),
            (f"{r1}_{l0}",      tr  * (1 - tl)),
            (f"{r1}_{l1}",      tr  *      tl ),
        ]

    def update(self, data):
        rpm  = data.get("RPM",    0) or 0
        load = data.get("Load",   0) or 0
        ego  = data.get("EGO_Corr", 100) or 100
        clt  = data.get("CLT",    0) or 0
        wue  = data.get("WUE",  100) or 100
        afv  = data.get("AFV",  100) or 100
        tps  = data.get("TPS_pct", 0) or 0
        if rpm < 300:
            with self._lock:
                self.active = None
            self._last_tps = None
            return
        valid, inv_reason = self._is_valid(data, tps)
        primary_key = cell_key(rpm, load)
        neighbors   = self._bilinear_weights(rpm, load)
        with self._lock:
            self.active = primary_key
            for key, weight in neighbors:
                if weight < 0.01:
                    continue
                c = self.cells.setdefault(key, self._empty_cell())
                c["seconds"]  += self._dt * weight
                c["ego_sum"]  += ego * weight
                c["count"]    += weight
                c["clt_sum"]  += clt * weight
                c["wue_sum"]  += wue * weight
                c["afv_sum"]  += afv * weight
                if valid:
                    c["valid_seconds"] += self._dt * weight
                    c["valid_ego_sum"] += ego * weight
                    c["valid_count"]   += weight
                    # IIR adaptivo: alfa depende del peso bilineal,
                    # hardness y confianza acumulada
                    conf  = min(1.0, c["valid_seconds"] / 10.0)
                    alpha = weight * self.HARDNESS * (1.0 - 0.8 * conf)
                    alpha = max(0.01, min(0.5, alpha))
                    if c["ego_iir"] is None:
                        c["ego_iir"] = ego
                    else:
                        c["ego_iir"] = (1 - alpha) * c["ego_iir"] + alpha * ego
                else:
                    c["inv_reasons"][inv_reason] = (
                        c["inv_reasons"].get(inv_reason, 0) + weight
                    )
        self._last_tps = tps

    def snapshot(self):
        """Retorna copia thread-safe del estado con campos de calidad."""
        with self._lock:
            snap = {}
            for k, v in self.cells.items():
                n     = v["count"]
                vn    = v["valid_count"]
                avg   = round(v["ego_sum"]       / n,  1) if n  else 100.0
                vavg  = round(v["valid_ego_sum"] / vn, 1) if vn else None
                clt_a = round(v["clt_sum"] / n, 1) if n else None
                wue_a = round(v["wue_sum"] / n, 1) if n else None
                afv_a = round(v["afv_sum"] / n, 1) if n else None
                # Confianza: necesita 10s válidos para 100%
                conf  = round(min(1.0, v["valid_seconds"] / 10.0), 2)
                snap[k] = {
                    "seconds":        round(v["seconds"], 1),
                    "ego_avg":        avg,
                    "valid_seconds":  round(v["valid_seconds"], 1),
                    "valid_ego_avg":  vavg,
                    "ego_iir":        round(v["ego_iir"], 2) if v.get("ego_iir") is not None else None,
                    "confidence":     conf,
                    "clt_avg":        clt_a,
                    "wue_avg":        wue_a,
                    "afv_avg":        afv_a,
                    "inv_reasons":    dict(v["inv_reasons"]),
                }
            return snap, self.active

class RideErrorLog:
    """Registra eventos de error durante un ride.
    Solo escribe archivo si ocurrieron eventos — ride limpio = sin archivo.
    Archivo: ride_NNN_errorlog.json junto al CSV del ride.
    """

    def __init__(self):
        self._events = []
        self._ride_num = None
        self._session = None
        self._session_dir = None
        self._opened_utc = None
        self._last_data = {}
        self.logger = logging.getLogger("ErrorLog")

    def start(self, ride_num, session_checksum, session_dir):
        self._events = []
        self._ride_num = ride_num
        self._session = session_checksum
        self._session_dir = session_dir
        self._opened_utc = datetime.now(timezone.utc).isoformat()
        self._last_data = {}

    def update_last_sample(self, data):
        if data:
            self._last_data = {
                "rpm":      data.get("RPM"),
                "clt":      data.get("CLT"),
                "tps":      data.get("TPS_pct"),
                "ego":      data.get("EGO_Corr"),
                "afv":      data.get("AFV"),
                "batt":     data.get("Batt_V"),
                "vss":      data.get("VS_KPH"),
                "seconds":  data.get("Seconds"),
                "fl_learn": data.get("fl_learn"),
            }

    def _event(self, elapsed_s, etype, **kwargs):
        evt = {
            "t":    round(elapsed_s, 2),
            "ts":   datetime.now(timezone.utc).isoformat(),
            "type": etype,
        }
        evt.update(kwargs)
        if self._last_data:
            evt["ctx"] = dict(self._last_data)
        self._events.append(evt)
        self.logger.info(f"[R{self._ride_num:03d} t={elapsed_s:.1f}s] ERROR: {etype} — {kwargs}")

    def serial_exception(self, elapsed_s, exc_msg, consecutive_before=0):
        self._event(elapsed_s, "serial_exception",
                    msg=str(exc_msg)[:120],
                    consecutive_errors_before=consecutive_before)

    def dirty_bytes(self, elapsed_s, byte0_hex, sync_recovered):
        self._event(elapsed_s, "dirty_bytes",
                    byte0_hex=byte0_hex,
                    sync_recovered=sync_recovered)

    def bad_checksum(self, elapsed_s, cs_got, cs_expected):
        self._event(elapsed_s, "bad_checksum",
                    cs_got=f"0x{cs_got:02x}",
                    cs_expected=f"0x{cs_expected:02x}")

    def ecu_timeout(self, elapsed_s, lost_s, last_valid_t):
        self._event(elapsed_s, "ecu_timeout",
                    lost_s=round(lost_s, 1),
                    last_valid_t=round(last_valid_t, 2))

    def ecu_reset(self, elapsed_s, seconds_prev, seconds_now):
        self._event(elapsed_s, "ecu_reset",
                    seconds_prev=seconds_prev,
                    seconds_now=seconds_now)

    def reconnect_attempt(self, elapsed_s, trigger, attempt_n, success, time_s):
        self._event(elapsed_s, "reconnect",
                    trigger=trigger,
                    attempt=attempt_n,
                    success=success,
                    time_s=round(time_s, 1))

    def flush(self, closed_utc=None):
        if not self._events or not self._session_dir or self._ride_num is None:
            return None
        try:
            type_counts = Counter(e["type"] for e in self._events)
            payload = {
                "ride_num":   self._ride_num,
                "session":    self._session,
                "opened_utc": self._opened_utc,
                "closed_utc": closed_utc or datetime.now(timezone.utc).isoformat(),
                "events":     self._events,
                "summary": {
                    "total_events":      len(self._events),
                    "serial_exceptions": type_counts.get("serial_exception", 0),
                    "dirty_bytes":       type_counts.get("dirty_bytes", 0),
                    "bad_checksums":     type_counts.get("bad_checksum", 0),
                    "ecu_timeouts":      type_counts.get("ecu_timeout", 0),
                    "ecu_resets":        type_counts.get("ecu_reset", 0),
                    "reconnects":        type_counts.get("reconnect", 0),
                },
            }
            path = Path(self._session_dir) / f"ride_{self._ride_num:03d}_errorlog.json"
            tmp  = path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2)
            tmp.replace(path)
            self.logger.info(f"ErrorLog guardado: {path.name} ({len(self._events)} eventos)")
            return path
        except Exception as e:
            self.logger.warning(f"Error guardando errorlog: {e}")
            return None

    def counts(self):
        from collections import Counter
        c = Counter(e["type"] for e in self._events)
        return dict(c)

    def has_events(self):
        return len(self._events) > 0

    def clear(self):
        self._events = []
        self._last_data = {}
