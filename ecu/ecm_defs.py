#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""ecu/ecm_defs.py — XML-driven EEPROM map/axis decoder (EcmSpy defs).

Replaces the hardcoded BUEIB offsets in eeprom.decode_eeprom_maps() with
definitions read from ecu_defs/<firmware>.xml, resolved by ECU version.

Phase A goal: reproduce the legacy decoder output BYTE-FOR-BYTE so it can be
validated against golden eeprom.bin dumps before it replaces the legacy path.
Stride is derived dynamically (size // rows): cols+1 = separator format,
cols = dense format. Multi-firmware support comes for free once validated.
"""

import struct
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ecu.version_resolver import resolve_ecu

ECU_DEFS_DIR = Path(__file__).parent.parent / "ecu_defs"

# Map XML entry names to the legacy output keys the app already consumes.
MAP_KEYS = {
    "Fuel Map Front": "fuel_front",
    "Fuel Map Rear": "fuel_rear",
    "Timing Table Front": "spark_front",
    "Timing Table Rear": "spark_rear",
}
AXIS_KEYS = {
    "Timing Table Load Axis": "spark_load",
    "Timing Table RPM Axis": "spark_rpm",
    "Fuel Map Load Axis": "fuel_load",
    "Fuel Map RPM Axis": "fuel_rpm",
}


def _norm(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def _xml_path(version_string):
    ecu = resolve_ecu(version_string)
    if ecu and ecu.get("dbfile"):
        return ECU_DEFS_DIR / f"{ecu['dbfile']}.xml"
    return None


def _entries(xml_path):
    root = ET.parse(xml_path).getroot()
    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    def num(e, tag, default, cast):
        return cast(e.findtext(f"{p}{tag}", default) or default)

    out = []
    for e in root.findall(f"{p}eeoffsets"):
        out.append({
            "name": e.findtext(f"{p}name", ""),
            "type": e.findtext(f"{p}type", ""),
            "offset": num(e, "offset", "0", int),
            "size": num(e, "size", "0", int),
            "rows": num(e, "rows", "0", int),
            "cols": num(e, "cols", "0", int),
            "scale": num(e, "scale", "1", float),
            "xaxis": e.findtext(f"{p}xaxis", "") or "",
            "yaxis": e.findtext(f"{p}yaxis", "") or "",
            "units": e.findtext(f"{p}units", "") or "",
        })
    return out


def _decode_axis(blob, d):
    # Byte width = size // rows. 2-byte axes (RPM) are stored descending in the
    # EEPROM -> reverse to ascending. 1-byte axes (Load) are stored ascending.
    width = d["size"] // d["rows"] if d["rows"] else 1
    if width == 2:
        vals = [struct.unpack_from("<H", blob, d["offset"] + i * 2)[0]
                for i in range(d["rows"])]
        return list(reversed(vals))
    return [blob[d["offset"] + i] for i in range(d["rows"])]


def _decode_map(blob, d):
    # stride = size // rows: cols+1 = separator format, cols = dense. Each row
    # holds `cols` data bytes stored descending RPM -> reverse to ascending.
    rows, cols, scale = d["rows"], d["cols"], d["scale"]
    stride = d["size"] // rows if rows else cols
    table = []
    for r in range(rows):
        row_off = d["offset"] + r * stride
        row = [round(v * scale, 2) for v in blob[row_off:row_off + cols]]
        table.append(list(reversed(row)))
    return table


def _min_blob_size(entries):
    """Minimum valid blob size = highest (offset + size) across all entries."""
    if not entries:
        return 0
    return max(d["offset"] + d["size"] for d in entries)


def decode_maps(blob, version_string):
    """Return legacy-compatible {axes:{...}, fuel_front, fuel_rear, spark_*}."""
    if not blob:
        return {}
    xml_path = _xml_path(version_string)
    if not xml_path or not xml_path.exists():
        return {}
    entries = _entries(xml_path)
    if len(blob) < _min_blob_size(entries):
        return {}
    axes, maps = {}, {}
    for d in entries:
        if d["type"] == "Axis" and d["name"] in AXIS_KEYS:
            axes[AXIS_KEYS[d["name"]]] = _decode_axis(blob, d)
        elif d["type"] == "Map" and d["name"] in MAP_KEYS:
            maps[MAP_KEYS[d["name"]]] = _decode_map(blob, d)
    return {"axes": axes, **maps}


def decode_maps_full(blob: bytes, version_string: str) -> dict:
    """Return all maps and axes from XML as XML-driven nested dict.

    Format: {maps: {norm_key: {label, data, rows, cols, xaxis, yaxis, units}},
             axes: {norm_key: {label, data, units}}}
    """
    if not blob:
        return {"maps": {}, "axes": {}}
    xml_path = _xml_path(version_string)
    if not xml_path or not xml_path.exists():
        return {"maps": {}, "axes": {}}
    entries = _entries(xml_path)
    if len(blob) < _min_blob_size(entries):
        return {"maps": {}, "axes": {}}
    axes_out = {}
    for d in entries:
        if d["type"] == "Axis":
            key = _norm(d["name"])
            axes_out[key] = {
                "label": d["name"],
                "data": _decode_axis(blob, d),
                "units": d["units"],
            }
    maps_out = {}
    for d in entries:
        if d["type"] == "Map":
            key = _norm(d["name"])
            maps_out[key] = {
                "label": d["name"],
                "data": _decode_map(blob, d),
                "rows": d["rows"],
                "cols": d["cols"],
                "xaxis": _norm(d["xaxis"]) if d["xaxis"] else None,
                "yaxis": _norm(d["yaxis"]) if d["yaxis"] else None,
                "units": d["units"],
            }
    return {"maps": maps_out, "axes": axes_out}


# EEPROM page tables: (page_nr, absolute_start, length).
# Derived from ECU firmware protocol paging — NOT derivable from XML offsets alone.
# BUEIB page structure confirmed on live hardware (XB12X, DDFI-2).
_BUEIB_PAGES: list[tuple[int, int, int]] = [
    (1,    0, 256),
    (2,  256, 256),
    (3,  512, 158),
    (4,  670, 256),
    (5,  926, 256),
    (6, 1182,  24),
]

_PAGES_BY_FIRMWARE: dict[str, list[tuple[int, int, int]]] = {
    "BUEIB": _BUEIB_PAGES,
}


def get_eeprom_pages(version_string: str) -> list[tuple[int, int, int]]:
    """Return (page_nr, start, length) tuples covering the full EEPROM.

    Falls back to sequential 256-byte pages for unrecognized firmware.
    Sequential pages are safe for reads; burns on unknown firmware should
    be avoided until the page structure is confirmed on real hardware.
    """
    ecu = resolve_ecu(version_string)
    dbfile = (ecu or {}).get("dbfile", "")
    if dbfile in _PAGES_BY_FIRMWARE:
        return _PAGES_BY_FIRMWARE[dbfile]
    xml_p = _xml_path(version_string)
    total = _min_blob_size(_entries(xml_p)) if xml_p and xml_p.exists() else 1206
    pages, nr, start = [], 1, 0
    while start < total:
        length = min(256, total - start)
        pages.append((nr, start, length))
        nr += 1
        start += length
    return pages
