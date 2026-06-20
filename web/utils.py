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
        cl = open("/home/pi/buell/CHANGELOG.md").read()
        end_comment = cl.find("-->")
        if end_comment != -1:
            cl = cl[end_comment:]
        m = re.search(r"## \[([^\]]+)\]", cl)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"
