#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
tools/build_xpr_viewer.py — bundle ecu_defs/*.xml into the standalone XPR viewer.

tools/xpr_viewer_template.html has the viewer's HTML/CSS/JS (a JS port of
ecu/ecm_defs.py + ecu/eeprom_params.py's decode logic, plus the report
renderer from web/static/report_export.js) but no embedded data. This script
reads every ecu_defs/*.xml definition file, embeds them as a JS object, and
writes the result to tools/xpr_viewer.html -- a single file with zero
external references that decodes an .xpr entirely in the browser, no Pi
or server involved at any point (not even to fetch the page).

Run after any ecu_defs/*.xml change:
    python tools/build_xpr_viewer.py
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ECU_DEFS_DIR = BASE / "ecu_defs"
TEMPLATE_PATH = BASE / "tools" / "xpr_viewer_template.html"
OUTPUT_PATH = BASE / "tools" / "xpr_viewer.html"

# rtdata.xml is RT telemetry field definitions, unrelated to EEPROM maps/config.
SKIP_FILES = {"files.xml", "rtdata.xml"}


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def load_ecm_list() -> list[dict]:
    """Parse ecu_defs/files.xml into [{name, dbfile, remark, size}, ...]."""
    root = ET.parse(ECU_DEFS_DIR / "files.xml").getroot()
    out = []
    for e in root.iter():
        if _strip_ns(e.tag) != "ecm":
            continue
        row = {_strip_ns(c.tag): (c.text or "").strip() for c in e}
        out.append({
            "name": row.get("name", ""),
            "dbfile": row.get("dbfile", ""),
            "remark": row.get("remark", ""),
            "size": row.get("size", "?"),
        })
    return out


def main() -> int:
    ecm_list = load_ecm_list()
    known_dbfiles = {e["dbfile"] for e in ecm_list if e["dbfile"]}

    xml_by_dbfile = {}
    for xml_path in sorted(ECU_DEFS_DIR.glob("*.xml")):
        if xml_path.name in SKIP_FILES:
            continue
        dbfile = xml_path.stem
        xml_by_dbfile[dbfile] = xml_path.read_text(encoding="utf-8")

    missing = known_dbfiles - set(xml_by_dbfile)
    if missing:
        print(f"WARNING: files.xml references dbfiles with no matching XML: {sorted(missing)}")

    data = {"ecmList": ecm_list, "xml": xml_by_dbfile}
    # JSON is valid JS; </script>-safe escaping matters since this gets inlined
    # inside a real <script> tag.
    data_json = json.dumps(data, ensure_ascii=False).replace("</script", "<\\/script")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "__ECU_DEFS_DATA__" not in template:
        print("ERROR: template is missing the __ECU_DEFS_DATA__ placeholder")
        return 1
    output = template.replace("__ECU_DEFS_DATA__", data_json)
    OUTPUT_PATH.write_text(output, encoding="utf-8")

    size_mb = len(output.encode("utf-8")) / (1024 * 1024)
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB, {len(xml_by_dbfile)} ECU definitions embedded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
