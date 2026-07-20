# DEV NOTE: All code, comments, and variable names must be in English.
"""Shared import logic for ECMSpy .xpr / raw EEPROM blobs.

An .xpr file is a raw EEPROM image (same layout ecu.eeprom.decode_eeprom_maps
already reads) plus a few trailing bytes ECMSpy appends (checksum/padding,
not used by this project). Trimming to the expected EEPROM size is enough --
no XPR-specific parsing needed.

Used by both tools/import_xpr.py (CLI) and web/handlers/eeprom.py (the Map
Editor's "Import XPR" button), so the two stay in sync.
"""
from pathlib import Path

from ecu.connection import get_eeprom_pages
from ecu.eeprom import decode_eeprom_maps
from ecu.session import SessionManager

DEFAULT_VERSION = "BUEIB310 12-11-03"


def import_xpr_bytes(data: bytes, sessions_dir: Path, version: str = DEFAULT_VERSION,
                     note: str = "", source_name: str = "") -> dict:
    """Trim, decode, and save an EEPROM blob as a session. Pure filesystem --
    never touches the ECU. Raises ValueError on a blob that doesn't decode."""
    pages = get_eeprom_pages(version)
    total_size = sum(ln for _, _, ln in pages)
    if len(data) < total_size:
        raise ValueError(f"file too small: {len(data)} bytes, need at least {total_size}")
    blob = data[:total_size]

    maps = decode_eeprom_maps(blob, version)
    bike_serial = int.from_bytes(blob[12:14], "little")

    session = SessionManager(Path(sessions_dir))
    is_new = session.open_session(version, blob)
    session.save_eeprom(blob)
    session.session_metadata.setdefault("rider_notes", []).append({
        "source": "xpr_import",
        "source_file": source_name,
        "note": note or f"Imported from {source_name}",
    })
    session._save_metadata()

    return {
        "checksum": session.current_checksum,
        "session_dir": str(session.current_session_dir),
        "bike_serial": bike_serial,
        "is_new": is_new,
        "trimmed_bytes": len(data) - total_size,
        "map_keys": list(maps.get("maps", maps).keys()),
    }
