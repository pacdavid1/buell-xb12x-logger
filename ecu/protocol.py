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
import statistics
from typing import Any, final

import struct

# ── Constantes de protocolo ───────────────────────────────────
SOH            = 0x01
EOH            = 0xFF
SOT            = 0x02
EOT            = 0x03
ACK            = 0x06
RT_RESPONSE_SIZE = 107

# ── Variables RT: {nombre: (offset, nbytes, scale, val_offset)} ─
RT_VARIABLES: dict[str, tuple[int, int, float, float]] = {
    "RPM":          (11, 2, 1.0,    0.0),
    "Seconds":      ( 9, 2, 1.0,    0.0),
    "MilliSec":     ( 8, 1, 0.01,   0.0),
    "TPD":          (25, 2, 0.1,    0.0),
    "Load":         (27, 1, 1.0,    0.0),
    "TPS_10Bit":    (90, 2, 1.0,    0.0),
    "Batt_V":       (28, 2, 0.01,   0.0),
    "CLT":          (30, 2, 0.1,  -40.0),
    "MAT":          (32, 2, 0.1,  -40.0),
    "O2_ADC":       (34, 2, 1.0,    0.0),
    "WUE":          (38, 2, 0.1,    0.0),
    "IAT_Corr":     (40, 2, 0.1,    0.0),
    "Accel_Corr":   (42, 2, 0.1,    0.0),
    "Decel_Corr":   (44, 2, 0.1,    0.0),
    "WOT_Corr":     (46, 2, 0.1,    0.0),
    "Idle_Corr":    (48, 2, 0.1,    0.0),
    "OL_Corr":      (50, 2, 0.1,    0.0),
    "AFV":          (52, 2, 0.1,    0.0),
    "EGO_Corr":     (54, 2, 0.1,    0.0),
    "spark1":       (13, 2, 0.0025, 0.0),
    "spark2":       (15, 2, 0.0025, 0.0),
    "veCurr1_RAW":  (17, 2, 1.0,    0.0),
    "veCurr2_RAW":  (19, 2, 1.0,    0.0),
    "pw1":          (21, 2, 0.00133,0.0),
    "pw2":          (23, 2, 0.00133,0.0),
    "Flags0":       (56, 1, 1.0,    0.0),
    "Flags1":       (57, 1, 1.0,    0.0),
    "Flags2":       (58, 1, 1.0,    0.0),
    "Flags3":       (59, 1, 1.0,    0.0),
    "Flags4":       (60, 1, 1.0,    0.0),
    "Flags5":       (61, 1, 1.0,    0.0),
    "Flags6":       (62, 1, 1.0,    0.0),
    "Unk63":        (63, 1, 1.0,    0.0),
    "CDiag0":       (67, 1, 1.0,    0.0),
    "CDiag1":       (68, 1, 1.0,    0.0),
    "CDiag2":       (69, 1, 1.0,    0.0),
    "CDiag3":       (70, 1, 1.0,    0.0),
    "CDiag4":       (71, 1, 1.0,    0.0),
    "HDiag0":       (75, 1, 1.0,    0.0),
    "HDiag1":       (76, 1, 1.0,    0.0),
    "HDiag2":       (77, 1, 1.0,    0.0),
    "HDiag3":       (78, 1, 1.0,    0.0),
    "HDiag4":       (79, 1, 1.0,    0.0),
    "Unk80":        (80, 1, 1.0,    0.0),
    "Unk81":        (81, 1, 1.0,    0.0),
    "Unk82":        (82, 1, 1.0,    0.0),
    "Rides":        (83, 1, 1.0,    0.0),
    "DOut":         (84, 1, 1.0,    0.0),
    "DIn":          (85, 1, 1.0,    0.0),
    "ETS_ADC":      (94, 1, 1.0,    0.0),
    "IAT_ADC":      (95, 1, 1.0,    0.0),
    "SysConfig":    ( 7, 1, 1.0,    0.0),
    "BAS_ADC":      (65, 2, 1.0,    0.0),
    "VSS_Count":    (99, 1, 1.0,    0.0),
    "Fan_Duty_Pct": (98, 1, 1.0,    0.0),
    "VSS_RPM_Ratio":(100,1, 1.0,    0.0),
}

# ── VSS / Velocidad ───────────────────────────────────────────
VSS_CPKM25 = 1518.0  # counts por 25km/h — recalibrado vs GPS (ride_015 + rides 4-5 sesión 47BF04)

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
# Minimum VS_KPH per gear — physically impossible below these speeds.
# Calibrated from real ride data (47BF04 ride_009, mayo 2026).
MIN_KPH: list[float] = [0.0, 5.0, 15.0, 25.0, 35.0, 50.0]


class GearFilter:

    '''Statistical gear filter using sliding window + cliff detection.'''

    WINDOW_S       = 3.0
    MIN_S          = 1.5
    OUTLIER_THR    = 3.0
    STD_THR        = 1.5
    MIN_SAMPLES    = 8

    CLIFF_TIME_S   = 0.5
    CLIFF_DIFF_THR = 3.0
    CLIFF_MIN_OLD  = 4
    CLIFF_MIN_NEW  = 3

    # THRESHOLDS now defined at module level (must be outside class
    # due to Python 3 class-level list comprehension scoping rules)

    def __init__(self) -> None:
        self.buffer = collections.deque()
        self.last_gear = 0

    def detect(self, rpm, kph, elapsed_s, di_neutral):
        if rpm < 1200 or kph < 5.0 or di_neutral:
            self.buffer.clear()
            if di_neutral or kph < 5.0:
                self.last_gear = 0
            return self.last_gear

        ratio = rpm / kph
        self.buffer.append((elapsed_s, ratio))

        cutoff = elapsed_s - self.WINDOW_S
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

        if len(self.buffer) < 2:
            return self.last_gear
        span = self.buffer[-1][0] - self.buffer[0][0]
        if span < self.MIN_S:
            return self.last_gear

        # Cliff detector: compare old vs new averages
        cliff_t = elapsed_s - self.CLIFF_TIME_S
        old = [r for t, r in self.buffer if t < cliff_t]
        new = [r for t, r in self.buffer if t >= cliff_t]
        if len(old) >= self.CLIFF_MIN_OLD and len(new) >= self.CLIFF_MIN_NEW:
            if abs(statistics.mean(new) - statistics.mean(old)) > self.CLIFF_DIFF_THR:
                self.buffer = collections.deque(
                    (t, r) for t, r in self.buffer if t >= cliff_t
                )
                if len(self.buffer) >= self.MIN_SAMPLES:
                    return self._median_gear(kph)
                return self.last_gear

        # Filter outliers
        values = [r for _, r in self.buffer]
        if len(values) < self.MIN_SAMPLES:
            return self.last_gear
        med = statistics.median(values)
        clean = [r for r in values if abs(r - med) < self.OUTLIER_THR]
        if len(clean) < self.MIN_SAMPLES:
            return self.last_gear

        # Stability check
        if statistics.stdev(clean) > self.STD_THR:
            return self.last_gear

        self.last_gear = self._ratio_to_gear(statistics.median(clean), kph)
        return self.last_gear

    def _ratio_to_gear(self, ratio, kph):
        # Nearest center wins — no overlap possible
        best_gear, best_dist = 1, float('inf')
        for g, center in enumerate(CENTERS[1:], start=1):
            d = abs(center - ratio)
            if d < best_dist:
                best_dist = d
                best_gear = g
        # Physical speed constraint — downshift until speed is valid
        while best_gear > 1 and kph < MIN_KPH[best_gear]:
            best_gear -= 1
        return best_gear

    def _median_gear(self, kph):
        ratios = [r for _, r in self.buffer]
        return self._ratio_to_gear(statistics.median(ratios), kph)

    def clear(self):
        self.buffer.clear()
        self.last_gear = 0


_gear_filter = GearFilter()


def decode_rt_packet(raw_bytes: bytes) -> dict[str, Any]:
    """Convierte frame RT raw (107 bytes) → dict de parámetros ECU.
    Retorna None si el frame es inválido o el checksum no coincide."""
    if len(raw_bytes) < RT_RESPONSE_SIZE:
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
    for name, (offset, nbytes, scale, val_offset) in RT_VARIABLES.items():
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

    # ── TPS calibrado ────────────────────────────────────────
    tps10   = result.get('TPS_10Bit') or 0
    tps_v   = round(tps10 * 0.004887585, 3)
    tps_pct = round(max(0.0, min(100.0, (tps_v - 0.66) / 3.88 * 100)), 1)
    result['TPS_V']   = tps_v
    result['TPS_pct'] = tps_pct

    # ── VS_KPH ───────────────────────────────────────────────
    vss = result.get('VSS_Count') or 0
    if vss > 0 and VSS_CPKM25 > 0:
        result['VS_KPH'] = round((vss / 0.039) * 3600 / (VSS_CPKM25 / 25 * 1000), 1)
    else:
        result['VS_KPH'] = 0.0

    # Gear — sliding window statistical detection
    kph = result['VS_KPH']
    result['VSS_RPM_Ratio'] = kph / (result['RPM'] / 1000.0) if result.get('RPM', 0) > 0 else 0  # unchanged for CSV
    result['Gear'] = _gear_filter.detect(
        rpm=result.get('RPM', 0),
        kph=kph,
        elapsed_s=result.get('Seconds', 0.0) + result.get('MilliSec', 0.0) / 1000.0,
        di_neutral=result.get('di_neutral', 0),
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
    "CDiag0", "CDiag1", "CDiag2", "CDiag3", "CDiag4",
    "HDiag0", "HDiag1", "HDiag2", "HDiag3", "HDiag4",
    "Unk80", "Unk81", "Unk82", "Rides", "DIn", "DOut", "ETS_ADC", "IAT_ADC", "BAS_ADC", "SysConfig",
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
    "baro_hPa", "baro_temp_c",
]
