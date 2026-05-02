#!/usr/bin/env python3
"""
ecu/eeprom.py — Decodificación del EEPROM BUEIB/DDFI2
Extraído de ddfi2_logger.py para modularización v2.0

Responsabilidades:
  - BUEIB_PARAMS: parámetros de calibración y configuración
  - decode_eeprom_params(): valores escalados del EEPROM
  - decode_eeprom_maps(): 4 mapas VE/spark listos para JSON
"""

import struct

# ── Parámetros BUEIB (offset, scale, translate, units, desc) ─
BUEIB_PARAMS = {
    "KTemp_Fan_On":      (498, 1.0,  50.0, "°C",  "Fan ON temperatura (key-on)"),
    "KTemp_Fan_Off":     (499, 1.0,  50.0, "°C",  "Fan OFF temperatura (key-on)"),
    "KTemp_Soft_Hi":     (488, 1.0, 200.0, "°C",  "Soft limit trigger (EGO baja)"),
    "KTemp_Soft_Lo":     (489, 1.0, 200.0, "°C",  "Soft limit release"),
    "KTemp_Hard_Hi":     (490, 1.0, 200.0, "°C",  "Hard limit trigger (corta chispa)"),
    "KTemp_Hard_Lo":     (491, 1.0, 200.0, "°C",  "Hard limit release"),
    "KTemp_Kill_Hi":     (494, 1.0, 200.0, "°C",  "Kill limit trigger (apaga motor)"),
    "KTemp_Kill_Lo":     (495, 1.0, 200.0, "°C",  "Kill limit release"),
    "KTemp_CEL_Flash_Hi":(496, 1.0, 200.0, "°C",  "CEL encendido temperatura"),
    "KTemp_Fan_KO_On":   (521, 1.0,   0.0, "°C",  "Fan key-off ON temp"),
    "KTemp_Fan_KO_Off":  (522, 1.0,   0.0, "°C",  "Fan key-off OFF temp"),
    "KTemp_RPM_Soft":    (485, 50.0,  0.0, "RPM", "RPM min para soft limit temp"),
    "KTemp_RPM_Hard":    (487, 50.0,  0.0, "RPM", "RPM min para hard limit temp"),
    "KTemp_TP_Soft":     (484, 1.0,   0.0, "TPS", "TPS min para soft limit temp"),
    "KTemp_TP_Hard":     (486, 1.0,   0.0, "TPS", "TPS min para hard limit temp"),
    "KRPM_Soft_Hi":      (458, 50.0,  0.0, "RPM", "RPM soft limit trigger"),
    "KRPM_Soft_Lo":      (459, 50.0,  0.0, "RPM", "RPM soft limit release"),
    "KRPM_Hard_Hi":      (460, 50.0,  0.0, "RPM", "RPM hard limit trigger"),
    "KRPM_Hard_Lo":      (461, 50.0,  0.0, "RPM", "RPM hard limit release"),
    "KRPM_Kill_Hi":      (464, 50.0,  0.0, "RPM", "RPM kill limit trigger"),
    "KRPM_Kill_Lo":      (465, 50.0,  0.0, "RPM", "RPM kill limit release"),
    "KO2_Midpoint":      (186, 0.00196, 0.0, "V", "O2 target voltage"),
    "KO2_Rich":          (187, 0.00196, 0.0, "V", "O2 rich threshold"),
    "KO2_Lean":          (188, 0.00196, 0.0, "V", "O2 lean threshold"),
    "KO2_Min_RPM":       (190, 50.0,    0.0, "RPM", "Closed loop min RPM"),
    "KFBFuel_Max":       (379, 0.4,     0.0, "%",   "EGO correction max"),
    "KFBFuel_Min":       (380, 0.4, -102.0,  "%",   "EGO correction min"),
    "KLFuel_Max":        (395, 0.4,     0.0, "%",   "AFV max"),
    "KLFuel_Min":        (396, 0.4, -102.0,  "%",   "AFV min"),
    "KTPS0":             (200, 0.00244, 0.0, "V",   "TPS cerrado voltage"),
    "KTPSV_Range":       (201, 0.00244, 0.0, "V",   "TPS voltage range"),
    "KMFG_Year":         (3,   1.0,   0.0, "",    "Anio fabricacion ECM"),
    "KMFG_Day":          (4,   1.0,   0.0, "",    "Dia fabricacion ECM"),
    "KEngineRun":        (6,   50.0,  0.0, "RPM", "RPM minimo motor encendido"),
    "Ride_Counter":      (1,   1.0,   0.0, "",    "Contador de rides"),
}


def decode_eeprom_params(eeprom_bytes):
    """Decodifica parámetros del dump EEPROM BUEIB.
    Retorna dict {varname: {val, raw, units, desc}}"""
    if not eeprom_bytes or len(eeprom_bytes) < 600:
        return {}
    result = {}
    for varname, (offset, scale, translate, units, desc) in BUEIB_PARAMS.items():
        if offset >= len(eeprom_bytes):
            continue
        raw = eeprom_bytes[offset]
        val = round(raw * scale + translate, 3)
        result[varname] = {"val": val, "raw": raw, "units": units, "desc": desc}
    return result


def decode_eeprom_maps(eeprom_bytes):
    """Decodifica los 4 mapas principales del EEPROM BUEIB.
    Offsets verificados contra ecmdroid.db cat=8.
    Retorna dict con axes y tables listos para JSON."""
    if not eeprom_bytes or len(eeprom_bytes) < 1206:
        return {}

    def read_axis_1b(off, count):
        return [eeprom_bytes[off + i] for i in range(count)]

    def read_axis_2b(off, count):
        # EEPROM stores RPM axes in descending order — read as little-endian and reverse
        axis = [struct.unpack_from('<H', eeprom_bytes, off + i*2)[0] for i in range(count)]
        return list(reversed(axis))

    def read_map(off, rows, cols, scale):
        # Map is stored as fixed-stride rows: cols data bytes + 1 zero separator.
        # Stride is always (cols + 1) bytes regardless of cell values.
        # Reading by offset is robust against any data byte being 0x00.
        # Values are stored in descending RPM order — reverse to get ascending.
        table = []
        for r in range(rows):
            row_off = off + r * (cols + 1)
            row_raw = eeprom_bytes[row_off : row_off + cols]
            row = list(reversed([round(v * scale, 2) for v in row_raw]))
            table.append(row)
        return table

    def read_map_spark(off, rows, cols, scale):
        # Spark maps are dense rectangular grids (no zero separators).
        # Each row contains exactly `cols` values.
        # RPM axis is stored in descending order → reverse per row.
        raw = eeprom_bytes[off : off + rows * cols]
        table = []
        for r in range(rows):
            row_raw = raw[r*cols:(r+1)*cols]
            row = [round(v * scale, 2) for v in row_raw]
            table.append(list(reversed(row)))
        return table

    try:
        return {
            "axes": {
                "spark_load": read_axis_1b(602, 10),
                "spark_rpm":  read_axis_2b(612, 10),
                "fuel_load":  read_axis_1b(632, 12),
                "fuel_rpm":   read_axis_2b(644, 13),
            },
            "fuel_front":  read_map(870,  12, 13, 1.0),
            "fuel_rear":   read_map(1038, 12, 13, 1.0),
            "spark_front": read_map_spark(670, 10, 10, 0.25),
            "spark_rear":  read_map_spark(770, 10, 10, 0.25),
        }
    except Exception as e:
        return {"error": str(e)}
