#!/usr/bin/env python3
"""
ecu/protocol.py — Constantes y decodificación del protocolo DDFI2
Extraído de ddfi2_logger.py para modularización v2.0

Responsabilidades:
  - RT_VARIABLES: mapa de offsets/escala de cada parámetro
  - decode_rt_packet(): convierte frame raw → dict de parámetros
  - Constantes de gear detection y VSS
"""

import struct

# ── Constantes de protocolo ───────────────────────────────────
SOH            = 0x01
EOH            = 0xFF
SOT            = 0x02
EOT            = 0x03
ACK            = 0x06
RT_RESPONSE_SIZE = 107

# ── Variables RT: {nombre: (offset, nbytes, scale, val_offset)} ─
RT_VARIABLES = {
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
VSS_CPKM25 = 1368.0  # counts por 25km/h — calibrado con ride_015

# ── Gear detection XB12X (5 velocidades, transmisión stock) ──
GEAR_KPH_PER_KRPM = [0.0, 7.0, 11.8, 15.4, 19.1, 23.0]  # [0=neutro, 1-5]
GEAR_THRESHOLDS = [
    (GEAR_KPH_PER_KRPM[1] + GEAR_KPH_PER_KRPM[2]) / 2,  # entre 1a y 2a
    (GEAR_KPH_PER_KRPM[2] + GEAR_KPH_PER_KRPM[3]) / 2,  # entre 2a y 3a
    (GEAR_KPH_PER_KRPM[3] + GEAR_KPH_PER_KRPM[4]) / 2,  # entre 3a y 4a
    (GEAR_KPH_PER_KRPM[4] + GEAR_KPH_PER_KRPM[5]) / 2,  # entre 4a y 5a
]  # = [9.4, 13.6, 17.25, 21.05]


def decode_rt_packet(raw_bytes):
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

    # ── Gear ─────────────────────────────────────────────────
    rpm_k = (result.get('RPM') or 0) / 1000.0
    kph   = result['VS_KPH']
    if rpm_k > 0.5 and kph > 3.0:
        ratio = kph / rpm_k
        gear  = 1
        for thr in GEAR_THRESHOLDS:
            if ratio > thr:
                gear += 1
            else:
                break
        result['Gear'] = gear
    else:
        result['Gear'] = 0

    return result

# ── Bins para CellTracker (mapa VE) ─────────────────────────
RPM_BINS  = [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]
LOAD_BINS = [10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]

# ── Columnas CSV — orden canónico del archivo de log ─────────
CSV_COLUMNS = [
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
