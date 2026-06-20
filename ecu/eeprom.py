#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""ecu/eeprom.py — EEPROM decode/encode for DDFI2.

decode_eeprom_maps() delegates to ecm_defs (XML-driven, multi-firmware ready).
encode_eeprom_maps() remains BUEIB-hardcoded until Phase C adds the burn guard.
"""

import logging

_log = logging.getLogger(__name__)


def _validate_eeprom(eeprom_bytes):
    """Sanity-check EEPROM bytes. Returns True if data looks valid.
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
        # Fuel map load axes (offset 632, 12 bins): all non-zero
        if any(eeprom_bytes[632 + i] == 0 for i in range(12)):
            return False
        return True
    except (IndexError, TypeError):
        return False


def decode_eeprom_maps(eeprom_bytes, version=None):
    """Decode the 4 main EEPROM maps via XML-driven offsets/dims.

    Delegates to ecm_defs.decode_maps() for the given firmware version.
    Default BUEIB310 is backward-compatible: all existing callers omitting
    version continue to work and produce byte-identical output (validated
    12/12 golden BUEIB bins in Phase A).
    """
    if not _validate_eeprom(eeprom_bytes):
        if eeprom_bytes:
            _log.warning("EEPROM maps: invalid data (len=%d)", len(eeprom_bytes))
        return {}
    from ecu.ecm_defs import decode_maps
    return decode_maps(eeprom_bytes, version or "BUEIB310")


def encode_eeprom_maps(eeprom_bytes, maps):
    """Apply decoded map tables back into EEPROM bytes.
    Inverse of decode_eeprom_maps(). Only modifies safe zone (670-1205).
    Returns modified copy of eeprom_bytes as bytes.
    maps keys: fuel_front, fuel_rear, spark_front, spark_rear (all optional).
    Phase C will make offsets/safe_zone firmware-aware with a burn guard.
    """
    result = bytearray(eeprom_bytes)

    def write_fuel_map(off, rows, cols, table):
        # table[r][c] ascending RPM; EEPROM stores descending with (cols+1) stride
        for r in range(min(rows, len(table))):
            row_desc = list(reversed(table[r]))
            row_off = off + r * (cols + 1)
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
