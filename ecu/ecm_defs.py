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


# Injector dead-time (Battery Voltage Correction) table.
# The XML entry gives the ms scale, but NOT the voltage-axis scale (no xaxis).
# 0.125 V/count is inferred from the "Fan Key-Off Minimum Battery Voltage" entry
# (same units, scale 0.125) and empirically validated: with this scale the table's
# dead-time gradient (~0.16 ms/V near 14V) matches the measured pw-vs-Batt_V slope
# at steady cruise cells (~0.19-0.20 ms/V, within noise). See CHANGELOG v2.7.277.
_BATT_AXIS_SCALE = 0.125  # Volts per axis count
_BATT_TABLE_NAME = "Battery Voltage Correction"


def decode_batt_correction(blob: bytes, version_string: str) -> list[tuple[float, float]] | None:
    """Decode the injector dead-time table (voltage -> PW offset in ms).

    Returns a list of (volts, ms) breakpoints sorted ascending by voltage, or
    None when the firmware lacks the table or the blob is too short. The 12
    bytes are 6 interleaved (axis_byte, value_byte) pairs.
    """
    xml_p = _xml_path(version_string)
    if not xml_p or not xml_p.exists():
        return None
    entry = next((e for e in _entries(xml_p) if e["name"] == _BATT_TABLE_NAME), None)
    if not entry:
        return None
    off, size, rows, scale = entry["offset"], entry["size"], entry["rows"], entry["scale"]
    if not rows or off + size > len(blob):
        return None
    stride = size // rows  # 2: one axis byte + one value byte per row
    points = []
    for r in range(rows):
        base = off + r * stride
        volts = blob[base] * _BATT_AXIS_SCALE
        ms = blob[base + 1] * scale
        points.append((volts, ms))
    points.sort()
    return points


def deadtime_ms(points: list[tuple[float, float]] | None, volts: float) -> float:
    """Linear-interpolate injector dead-time (ms) at a battery voltage.
    Clamps to the table's endpoints; returns 0.0 when no table is available."""
    if not points:
        return 0.0
    if volts <= points[0][0]:
        return points[0][1]
    if volts >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        v0, m0 = points[i]
        v1, m1 = points[i + 1]
        if v0 <= volts <= v1:
            return m0 + (m1 - m0) * (volts - v0) / (v1 - v0) if v1 > v0 else m0
    return points[-1][1]


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
