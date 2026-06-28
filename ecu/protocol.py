#!/usr/bin/env python3
"""
ecu/protocol.py — Constantes y decodificación del protocolo DDFI2
Extraído de ddfi2_logger.py para modularización v2.0

Responsabilidades:
  - RT_VARIABLES: mapa de offsets/escala de cada parámetro
  - decode_rt_packet(): convierte frame raw → dict de parámetros
  - Constantes de gear detection y VSS
"""

import collections
import json
import logging
import statistics
import threading
from typing import Any

import struct

from ecu.rt_defs import load_rt_vars

# ── Constantes de protocolo ───────────────────────────────────
SOH            = 0x01
EOH            = 0xFF
SOT            = 0x02
EOT            = 0x03
ACK            = 0x06

# RT_VARIABLES and RT_RESPONSE_SIZE loaded from rtdata.xml at import time.
RT_VARIABLES, RT_RESPONSE_SIZE = load_rt_vars("DDFI-2")

# ── VSS / Velocidad ───────────────────────────────────────────
VSS_CPKM25 = 1518.0  # counts per 25km/h — recalibrated vs GPS (ride_015 + rides 4-5 session 47BF04)

# ── GearFilter: windowed statistical gear detection ──────────
# Internal ratio = RPM / KPH (inverted vs VSS_RPM_Ratio) for
# wider separation between gears. 3s window, outlier filter
# via median deviation, and cliff detector for fast transitions.
# VSS_RPM_Ratio in CSV remains unchanged.
# Calibrated centers: rpm / kph (empirical from real rides)
# Defined at module level because class-level list comprehensions
# cannot reference other class-level variables in Python 3.
CENTERS: list[float] = [0.0, 75.5, 53.8, 40.1, 33.3, 28.7]
THRESHOLDS: list[float] = [(CENTERS[i] + CENTERS[i+1]) / 2 for i in range(1, 5)]




class VSSCalibrator:
    """IIR auto-calibration of VSS_CPKM25 against GPS speed.

    Slowly converges the VSS calibration constant toward GPS-verified
    values. Only updates during stable cruise (no WOT, no decel, both
    GPS and VSS > MIN_SPEED, ratio error < MAX_RATIO_ERR).

    VS_KPH is proportional to 1/VSS_CPKM25, so if GPS reads higher
    than VSS, we decrease VSS_CPKM25 to raise the speed output.
    """

    ALPHA          = 0.02   # IIR rate — ~50 samples to shift 1%
    MIN_SPEED      = 10.0   # km/h minimum for both GPS and VSS
    MAX_RATIO_ERR  = 0.20   # reject if GPS/VSS differs by > 20%
    SAVE_THRESHOLD = 0.005  # save to disk when value drifts > 0.5%

    def __init__(self, initial: float = 1518.0) -> None:
        self._value      = initial
        self._last_saved = initial
        self._updates    = 0
        self._lock       = threading.Lock()
        self._log        = logging.getLogger("VSSCal")

    def get(self) -> float:
        with self._lock:
            return self._value

    def update(self, gps_kph: float, vss_kph: float,
               fl_decel: int = 0, fl_wot: int = 0) -> None:
        if fl_decel or fl_wot:
            return
        if gps_kph < self.MIN_SPEED or vss_kph < self.MIN_SPEED:
            return
        ratio = gps_kph / vss_kph
        if abs(ratio - 1.0) > self.MAX_RATIO_ERR:
            return
        # corrected_CPKM25 = current / ratio  (ratio>1 means VSS reads low → decrease CPKM25)
        with self._lock:
            corrected     = self._value / ratio
            self._value   = self._value * (1.0 - self.ALPHA) + corrected * self.ALPHA
            self._updates += 1

    def changed_significantly(self) -> bool:
        with self._lock:
            return abs(self._value - self._last_saved) / self._last_saved > self.SAVE_THRESHOLD

    def save(self, path: str) -> None:
        with self._lock:
            val     = self._value
            updates = self._updates
        try:
            with open(path, "w") as f:
                json.dump({"vss_cpkm25": round(val, 2), "updates": updates}, f)
            with self._lock:
                self._last_saved = val
            self._log.info(f"VSS calibration saved: {val:.1f} ({updates} updates)")
        except Exception as e:
            self._log.warning(f"VSS calibration save failed: {e}")

    def load(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
            val = float(data.get("vss_cpkm25", self._value))
            if 800.0 < val < 3000.0:   # sanity bounds
                with self._lock:
                    self._value      = val
                    self._last_saved = val
                self._log.info(f"VSS calibration loaded: {val:.1f}")
        except FileNotFoundError:
            pass   # first run — use default
        except Exception as e:
            self._log.warning(f"VSS calibration load failed: {e}")

class GearFilter:

    '''Statistical gear filter using sliding window + cliff detection.'''

    WINDOW_S       = 3.0   # seconds of history to keep
    MIN_S          = 1.5   # minimum span before attempting detection
    OUTLIER_THR    = 3.0   # median-deviation threshold for outlier rejection
    STD_THR        = 1.0   # tighter: require more stable window (was 1.5)
    MIN_SAMPLES    = 12    # more data before confirming gear (was 8)

    CLIFF_TIME_S   = 0.5
    CLIFF_DIFF_THR = 3.0
    CLIFF_MIN_OLD  = 4
    CLIFF_MIN_NEW  = 3

    # Coasting detection — wheel freewheeling with clutch in
    COAST_RPM_MAX   = 1400   # rpm: below this near-idle RPM during decel = likely clutch-in
    COAST_KPH_MIN   = 15.0   # kph: wheel still spinning
    COAST_RATIO_MIN = CENTERS[5] * 0.80  # ratio physically impossible in any gear (~22.9)

    # THRESHOLDS now defined at module level (must be outside class
    # due to Python 3 class-level list comprehension scoping rules)

    def __init__(self) -> None:
        self.buffer = collections.deque()
        self.last_gear = 0

    def detect(self, rpm, kph, elapsed_s, di_neutral,
               di_clutch: int = 0, fl_decel: int = 0) -> int:

        # Neutral switch or clutch pressed → definitive zero
        if di_neutral or di_clutch:
            self.buffer.clear()
            self.last_gear = 0
            return 0

        # Not moving or RPM too low
        if rpm < 800 or kph < 5.0:
            self.buffer.clear()
            if kph < 5.0:
                self.last_gear = 0
            return self.last_gear

        ratio = rpm / kph

        # Coasting guard 1: ratio below physically possible minimum
        # Wheel is spinning faster than engine can explain in any gear
        if ratio < self.COAST_RATIO_MIN:
            return self.last_gear

        # Coasting guard 2: near-idle RPM while decelerating with speed
        # Most likely clutch-in with engine returning to idle
        if fl_decel and rpm < self.COAST_RPM_MAX and kph > self.COAST_KPH_MIN:
            return self.last_gear

        self.buffer.append((elapsed_s, ratio))

        # Evict samples outside the rolling window
        cutoff = elapsed_s - self.WINDOW_S
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

        if len(self.buffer) < 2:
            return self.last_gear
        span = self.buffer[-1][0] - self.buffer[0][0]
        if span < self.MIN_S:
            return self.last_gear

        # Cliff detector: sudden ratio shift = gear change
        cliff_t = elapsed_s - self.CLIFF_TIME_S
        seg_old = [r for t, r in self.buffer if t <  cliff_t]
        seg_new = [r for t, r in self.buffer if t >= cliff_t]
        if len(seg_old) >= self.CLIFF_MIN_OLD and len(seg_new) >= self.CLIFF_MIN_NEW:
            if abs(statistics.mean(seg_new) - statistics.mean(seg_old)) > self.CLIFF_DIFF_THR:
                # Discard pre-shift data
                self.buffer = collections.deque(
                    (t, r) for t, r in self.buffer if t >= cliff_t
                )
                # Only accept if new segment is already stable enough
                if len(self.buffer) >= self.MIN_SAMPLES:
                    new_vals = [r for _, r in self.buffer]
                    if len(new_vals) > 1 and statistics.stdev(new_vals) <= self.STD_THR:
                        return self._median_gear()
                return self.last_gear

        # Outlier filter: discard samples far from the median
        values = [r for _, r in self.buffer]
        if len(values) < self.MIN_SAMPLES:
            return self.last_gear
        med = statistics.median(values)
        clean = [r for r in values if abs(r - med) < self.OUTLIER_THR]
        if len(clean) < self.MIN_SAMPLES:
            return self.last_gear

        # Stability gate: window must be tight before we trust it
        if len(clean) > 1 and statistics.stdev(clean) > self.STD_THR:
            return self.last_gear

        self.last_gear = self._ratio_to_gear(statistics.median(clean))
        return self.last_gear

    def _ratio_to_gear(self, ratio):
        for g, thr in enumerate(THRESHOLDS, start=1):
            if ratio >= thr:
                return g
        return 5

    def _median_gear(self):
        ratios = [r for _, r in self.buffer]
        return self._ratio_to_gear(statistics.median(ratios))

    def clear(self):
        self.buffer.clear()
        self.last_gear = 0


_gear_filter    = GearFilter()
_vss_calibrator = VSSCalibrator(initial=VSS_CPKM25)


def update_vss_calibration(gps_kph: float, vss_kph: float,
                            fl_decel: int = 0, fl_wot: int = 0) -> None:
    _vss_calibrator.update(gps_kph, vss_kph, fl_decel, fl_wot)


def load_vss_calibration(path: str) -> None:
    _vss_calibrator.load(path)


def save_vss_calibration(path: str) -> None:
    _vss_calibrator.save(path)


def vss_changed_significantly() -> bool:
    return _vss_calibrator.changed_significantly()


def decode_rt_packet(raw_bytes: bytes,
                     rt_vars: dict | None = None,
                     frame_size: int | None = None) -> dict[str, Any] | None:
    """Decode raw RT frame to parameter dict.
    rt_vars/frame_size default to module-level DDFI-2 constants."""
    _vars = rt_vars if rt_vars is not None else RT_VARIABLES
    _size = frame_size if frame_size is not None else RT_RESPONSE_SIZE
    if len(raw_bytes) < _size:
        return None
    if raw_bytes[0] != SOH or raw_bytes[4] != EOH or raw_bytes[5] != SOT:
        return None
    if raw_bytes[6] != ACK or raw_bytes[-2] != EOT:
        return None
    cs = 0
    for b in raw_bytes[1:-1]:
        cs ^= b
    if (cs & 0xFF) != raw_bytes[-1]:
        return None

    result = {}
    for name, (offset, nbytes, scale, val_offset) in _vars.items():
        if offset + nbytes > len(raw_bytes):
            result[name] = None
            continue
        raw = struct.unpack_from('<H', raw_bytes, offset)[0] if nbytes == 2 else raw_bytes[offset]
        result[name] = round(raw * scale + val_offset, 4)

    # ── Flags decodificados ──────────────────────────────────
    f1   = int(result.get('Flags1', 0) or 0)
    f2   = int(result.get('Flags2', 0) or 0)
    f3   = int(result.get('Flags3', 0) or 0)
    f4   = int(result.get('Flags4', 0) or 0)
    f6   = int(result.get('Flags6', 0) or 0)
    dout = int(result.get('DOut',   0) or 0)
    din  = int(result.get('DIn',    0) or 0)

    result['fl_engine_run']  = (f1 >> 0) & 1
    result['fl_o2_active']   = (f1 >> 1) & 1
    result['fl_accel']       = (f1 >> 2) & 1
    result['fl_decel']       = (f1 >> 3) & 1
    result['fl_engine_stop'] = (f1 >> 4) & 1
    result['fl_wot']         = (f1 >> 5) & 1
    result['fl_ignition']    = (f1 >> 7) & 1
    result['fl_closed_loop'] = (f2 >> 7) & 1
    result['fl_rich']        = (f2 >> 6) & 1
    result['fl_learn']       = (f2 >> 4) & 1
    result['fl_cam_active']  = (f3 >> 3) & 1
    result['fl_kill']        = (f3 >> 4) & 1
    result['fl_immob']       = (f3 >> 5) & 1
    result['fl_fuel_cut']    = (f4 >> 4) & 1
    result['fl_hot']         = (f6 >> 3) & 1
    result['do_coil1']       = (dout >> 0) & 1
    result['do_coil2']       = (dout >> 1) & 1
    result['do_inj1']        = (dout >> 2) & 1
    result['do_inj2']        = (dout >> 3) & 1
    result['do_fuel_pump']   = (dout >> 4) & 1
    result['do_tacho']       = (dout >> 5) & 1
    result['do_cel']         = (dout >> 6) & 1
    result['do_fan']         = (dout >> 7) & 1
    result['di_cam']         = (din >> 0) & 1
    result['di_tacho_fb']    = (din >> 1) & 1
    result['di_vss']         = (din >> 2) & 1
    result['di_clutch']      = (din >> 4) & 1
    result['di_neutral']     = (din >> 5) & 1
    result['di_crank']       = (din >> 7) & 1

    # ── Unk63 bits (Flags7 candidate) ───────────────────────
    u63 = int(result.get('Unk63', 0) or 0)
    for _b in range(8):
        result[f'Unk63_b{_b}'] = (u63 >> _b) & 1

    # ── TPS calibrado ────────────────────────────────────────
    tps10   = result.get('TPS_10Bit') or 0
    tps_v   = round(tps10 * 0.004887585, 3)
    tps_pct = round(max(0.0, min(100.0, (tps_v - 0.66) / 3.88 * 100)), 1)
    result['TPS_V']   = tps_v
    result['TPS_pct'] = tps_pct

    # ── VS_KPH ───────────────────────────────────────────────
    vss = result.get('VSS_Count') or 0
    cpkm25 = _vss_calibrator.get()
    if vss > 0 and cpkm25 > 0:
        result['VS_KPH'] = round((vss / 0.039) * 3600 / (cpkm25 / 25 * 1000), 1)
    else:
        result['VS_KPH'] = 0.0

    # Gear — sliding window statistical detection
    kph = result['VS_KPH']
    result['VSS_RPM_Ratio'] = kph / (result['RPM'] / 1000.0) if result.get('RPM', 0) > 0 else 0
    result['Gear'] = _gear_filter.detect(
        rpm=result.get('RPM', 0),
        kph=kph,
        elapsed_s=result.get('Seconds', 0.0) + result.get('MilliSec', 0.0) / 1000.0,
        di_neutral=result.get('di_neutral', 0),
        di_clutch=result.get('di_clutch', 0),
        fl_decel=result.get('fl_decel', 0),
    )

    return result

# ── Bins para CellTracker (mapa VE) ─────────────────────────
RPM_BINS  = [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]
LOAD_BINS: list[float] = [10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]

# ── Columnas CSV — orden canónico del archivo de log ─────────
CSV_COLUMNS: list[str] = [
    "ride_num", "timestamp_iso", "time_elapsed_s",
    "RPM", "Load", "TPD", "TPS_10Bit", "CLT", "MAT", "Batt_V",
    "spark1", "spark2", "veCurr1_RAW", "veCurr2_RAW", "pw1", "pw2",
    "EGO_Corr", "WUE", "AFV", "IAT_Corr", "Accel_Corr", "Decel_Corr",
    "WOT_Corr", "Idle_Corr", "OL_Corr", "O2_ADC",
    "Flags0", "Flags1", "Flags2", "Flags3", "Flags4", "Flags5", "Flags6", "Unk63",
    "Unk63_b0", "Unk63_b1", "Unk63_b2", "Unk63_b3", "Unk63_b4", "Unk63_b5", "Unk63_b6", "Unk63_b7",
    "CDiag0", "CDiag1", "CDiag2", "CDiag3", "CDiag4",
    "HDiag0", "HDiag1", "HDiag2", "HDiag3", "HDiag4",
    "Rides", "DIn", "DOut", "ETS_ADC", "IAT_ADC", "BAS_ADC", "SysConfig",
    "TPS_V", "TPS_pct",
    "VSS_Count", "VS_KPH", "Fan_Duty_Pct", "VSS_RPM_Ratio", "Gear",
    "dirty_byte_hex", "dirty_byte_name", "forensic_event",
    "fl_engine_run", "fl_o2_active", "fl_accel", "fl_decel", "fl_engine_stop", "fl_wot", "fl_ignition",
    "fl_closed_loop", "fl_rich", "fl_learn",
    "fl_cam_active", "fl_kill", "fl_immob",
    "fl_fuel_cut",
    "fl_hot",
    "do_coil1", "do_coil2", "do_inj1", "do_inj2", "do_fuel_pump", "do_tacho", "do_cel", "do_fan",
    "di_cam", "di_tacho_fb", "di_vss", "di_clutch", "di_neutral", "di_crank",
    "buf_in",
    "ttl_pct", "cpu_pct", "cpu_temp", "mem_pct",
    "gps_lat", "gps_lon", "gps_alt_m", "gps_speed_kmh", "gps_heading", "gps_satellites", "gps_valid",
    "gps_mode", "gps_epx", "gps_epy", "gps_epv", "gps_snr_avg",
    "gps_heading_rate", "gps_turning", "gps_stale",
    "baro_hPa", "baro_temp_c",
        "humidity_pct",
]
