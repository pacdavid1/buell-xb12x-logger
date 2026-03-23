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
        """Calculate session checksum from full EEPROM blob.
        Detects any change including fuel/spark map modifications."""
        return hashlib.md5(blob).hexdigest()[:6].upper()

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
            except Exception as e:
                self.logger.warning(f"Error guardando summary: {e}")
        self._save_metadata()
        self._generate_consolidated()

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
    """Acumula tiempo y EGO promedio por celda del mapa VE 13x12."""
    def __init__(self):
        self.cells  = {}
        self.active = None
        self._lock  = threading.Lock()
        self._dt    = 1.0 / 8.0

    def reset(self):
        with self._lock:
            self.cells  = {}
            self.active = None

    def update(self, data):
        rpm  = data.get("RPM",  0) or 0
        load = data.get("Load", 0) or 0
        ego  = data.get("EGO_Corr", 100) or 100
        if rpm < 300:
            with self._lock:
                self.active = None
            return
        key = cell_key(rpm, load)
        with self._lock:
            self.active = key
            c = self.cells.setdefault(key, {"seconds": 0.0, "ego_sum": 0.0, "count": 0})
            c["seconds"] += self._dt
            c["ego_sum"] += ego
            c["count"]   += 1

    def snapshot(self):
        """Retorna copia thread-safe del estado."""
        with self._lock:
            snap = {}
            for k, v in self.cells.items():
                avg = round(v["ego_sum"] / v["count"], 1) if v["count"] else 100.0
                snap[k] = {"seconds": round(v["seconds"], 1), "ego_avg": avg}
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
