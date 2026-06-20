"""RT variable definitions parsed from ecu_defs/rtdata.xml."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

_XML_PATH = Path(__file__).parent.parent / "ecu_defs" / "rtdata.xml"
_NS = "rtdata"

# Maps normalized export name → legacy key name used throughout the codebase.
# Only entries where normalization alone produces a different name are listed.
_NAME_OVERRIDES: dict[str, str] = {
    "Batt_Voltg": "Batt_V",
    "Baro_ADC": "Unk63",      # offset 63, 1-byte baro sensor — legacy name used in callers
    "unknown_79": "Unk79",
    "unknown_80": "Unk80",
    "unknown_81": "Unk81",
    "unknown_82": "Unk82",
    "Fan_Duty": "Fan_Duty_Pct",
    "VSS": "VSS_Count",
    "VSS_RPM": "VSS_RPM_Ratio",
}


def _normalize(export: str) -> str:
    return export.strip().replace(" ", "_").replace(".", "").replace("-", "_")


@lru_cache(maxsize=4)
def load_rt_vars(
    ddfi_family: str,
) -> tuple[dict[str, tuple[int, int, float, float]], int]:
    """Parse rtdata.xml for the given DDFI family.

    ddfi_family: 'DDFI-2' or 'DDFI-3'
    Returns (variables, frame_size) where variables = {key: (offset, nbytes, scale, translate)}.
    """
    if not _XML_PATH.exists():
        return {}, 0

    tree = ET.parse(_XML_PATH)
    root = tree.getroot()

    frame_size = 0
    entries: dict[str, tuple[int, int, float, float]] = {}

    def _f(el: ET.Element, field: str, default: str = "") -> str:
        return el.findtext(f"{{{_NS}}}{field}", default) or default

    rtoffsets_tag = f"{{{_NS}}}rtoffsets"
    for ns in ("DDFI", ddfi_family):
        for el in root.iter(rtoffsets_tag):
            if _f(el, "ddfi").strip() != ns:
                continue
            raw_offset = _f(el, "offset")
            raw_size = _f(el, "size")
            if not raw_offset or not raw_size:
                continue
            offset = int(raw_offset)
            size = int(raw_size)

            # Update frame_size from all entries (framing bytes included)
            frame_size = max(frame_size, offset + size)

            # Skip protocol framing (SOH/SRC/DST/Len/EOH/SOT/ACK = offsets 0-6)
            if offset < 7:
                continue
            if _f(el, "secret", "0").strip() == "1":
                continue
            export = _f(el, "export").strip()
            if not export:
                continue

            scale = float(_f(el, "scale", "1.0"))
            translate = float(_f(el, "translate", "0.0"))

            key = _normalize(export)
            key = _NAME_OVERRIDES.get(key, key)

            # Family-specific entries override shared DDFI entries for the same key
            if key not in entries or ns == ddfi_family:
                entries[key] = (offset, size, scale, translate)

    return entries, frame_size
