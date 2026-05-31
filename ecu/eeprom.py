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


def _validate_eeprom(eeprom_bytes):
    """Sanity-check EEPROM bytes against known ranges.
    Returns True if data looks valid, False if likely corrupted.
    Offsets verified against BUEIB.xml 2026-05-31."""
    if not eeprom_bytes or len(eeprom_bytes) < 600:
        return False
    try:
        # Serial number (offset 12-13, uint16 LE): must be non-zero
        serial = int.from_bytes(eeprom_bytes[12:14], "little")
        if serial == 0:
            return False
        # ECM Manufacturing Year (offset 9): 0-99
        if not (0 <= eeprom_bytes[9] <= 99):
            return False
        # System Configuration (offset 8): non-zero for a programmed ECU
        if eeprom_bytes[8] == 0:
            return False
        # Fuel map axes (offset 632, 12 load bins): all > 0
        if any(eeprom_bytes[632 + i] == 0 for i in range(12)):
            return False
        return True
    except (IndexError, TypeError):
        return False


def decode_eeprom_params(eeprom_bytes):
    """Decodifica parámetros del dump EEPROM BUEIB.
    Retorna dict {varname: {val, raw, units, desc}}"""
    if not eeprom_bytes or len(eeprom_bytes) < 600:
        return {}
    if not _validate_eeprom(eeprom_bytes):
        import logging
        logging.getLogger(__name__).warning(f"EEPROM params: invalid data (len={len(eeprom_bytes)})")
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
    if not _validate_eeprom(eeprom_bytes):
        import logging
        logging.getLogger(__name__).warning(f"EEPROM maps: invalid data (len={len(eeprom_bytes)})")
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


def encode_eeprom_maps(eeprom_bytes, maps):
    """Apply decoded map tables back into EEPROM bytes.
    Inverse of decode_eeprom_maps(). Only modifies safe zone (670-1205).
    Returns modified copy of eeprom_bytes as bytes.
    maps keys: fuel_front, fuel_rear, spark_front, spark_rear (all optional).
    """
    result = bytearray(eeprom_bytes)

    def write_fuel_map(off, rows, cols, table):
        # table[r][c] ascending RPM; EEPROM stores descending with (cols+1) stride
        for r in range(min(rows, len(table))):
            row_desc = list(reversed(table[r]))
            row_off  = off + r * (cols + 1)
            for c in range(min(cols, len(row_desc))):
                result[row_off + c] = max(0, min(255, int(round(row_desc[c]))))
            # separator byte at row_off + cols is NOT touched

    def write_spark_map(off, rows, cols, table):
        # table[r][c] ascending RPM, values in degrees; raw = val * 4
        for r in range(min(rows, len(table))):
            row_desc = list(reversed(table[r]))
            for c in range(min(cols, len(row_desc))):
                result[off + r * cols + c] = max(0, min(255, int(round(row_desc[c] * 4))))

    if maps.get('fuel_front'):  write_fuel_map(870,  12, 13, maps['fuel_front'])
    if maps.get('fuel_rear'):   write_fuel_map(1038, 12, 13, maps['fuel_rear'])
    if maps.get('spark_front'): write_spark_map(670, 10, 10, maps['spark_front'])
    if maps.get('spark_rear'):  write_spark_map(770, 10, 10, maps['spark_rear'])
    return bytes(result)
