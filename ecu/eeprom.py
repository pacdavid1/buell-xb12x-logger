#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""ecu/eeprom.py — EEPROM decode/encode for DDFI2.

Both decode_eeprom_maps() and encode_eeprom_maps() are XML-driven via ecm_defs.
Unknown firmware versions fall back safely: decode returns {}, encode returns bytes unchanged.
"""

import logging

_log = logging.getLogger(__name__)


def _validate_eeprom(eeprom_bytes):
    """Sanity-check EEPROM bytes. Returns True if data looks valid.
    Checks use firmware-independent offsets (serial/year/config at 8-13)."""
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



def decode_eeprom_maps_full(eeprom_bytes, version=None):
    """Return all maps and axes from XML — XML-driven, no hardcoded keys."""
    if not _validate_eeprom(eeprom_bytes):
        return {"maps": {}, "axes": {}}
    from ecu.ecm_defs import decode_maps_full
    return decode_maps_full(eeprom_bytes, version or "BUEIB310")

def encode_eeprom_maps(eeprom_bytes: bytes, maps: dict,
                       version: str | None = None) -> bytes:
    """Apply decoded map tables back into EEPROM bytes.

    Inverse of decode_eeprom_maps(). Offsets, dimensions, and scales come
    from the XML for the given firmware version — no hardcoded BUEIB values.
    If the XML cannot be found for the version, returns eeprom_bytes unchanged
    (burn guard: unknown firmware → no write).

    maps keys: fuel_front, fuel_rear, spark_front, spark_rear (all optional).
    """
    from ecu.ecm_defs import _entries, _xml_path, MAP_KEYS
    xml_p = _xml_path(version or "BUEIB310")
    if not xml_p or not xml_p.exists():
        _log.warning("encode_eeprom_maps: no XML for version %r — not encoding", version)
        return bytes(eeprom_bytes)
    from ecu.ecm_defs import _norm
    key_to_entry = {}
    for e in _entries(xml_p):
        if e['name'] in MAP_KEYS:
            key_to_entry[MAP_KEYS[e['name']]] = e   # legacy keys
        key_to_entry[_norm(e['name'])] = e          # new XML-driven keys
    result = bytearray(eeprom_bytes)
    for map_key, table in maps.items():
        if not table:
            continue
        d = key_to_entry.get(map_key)
        if d is None:
            continue
        off   = d['offset']
        rows  = d['rows']
        cols  = d['cols']
        scale = d['scale']
        stride = d['size'] // rows if rows else cols
        for r in range(min(rows, len(table))):
            row_desc = list(reversed(table[r]))
            row_off  = off + r * stride
            for c in range(min(cols, len(row_desc))):
                raw = round(row_desc[c] / scale) if scale else int(row_desc[c])
                result[row_off + c] = max(0, min(255, raw))
    return bytes(result)
