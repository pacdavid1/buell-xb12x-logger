# DEV NOTE: All code, comments, and variable names must be in English.
import json
import re
from pathlib import Path


def _session_version(bin_path):
    """Return the ECU version_string for a session given its eeprom.bin path.
    Reads session_metadata.json from the same directory. Returns None if absent.
    decode_eeprom_maps() falls back to BUEIB310 when version is None.
    """
    try:
        meta = json.loads((Path(bin_path).parent / 'session_metadata.json').read_text())
        return meta.get('version_string') or None
    except Exception:
        return None


def _get_version():
    try:
        # Derive path from this file's location (works on Windows + Pi alike).
        # Use utf-8 encoding explicitly (Windows default cp1252 can't decode CHANGELOG.md).
        cl = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding='utf-8')
        end_comment = cl.find("-->")
        if end_comment != -1:
            cl = cl[end_comment:]
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"
