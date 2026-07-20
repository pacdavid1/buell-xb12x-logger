#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
Import an ECMSpy .xpr EEPROM export as a Buell Logger session — no ECU
connection required. Once imported, the session shows up in every
session-based tool (3D map view, tuner, sessions list, replay_sim.py)
exactly like a session opened from a live ECU read.

Usage:
  py tools/import_xpr.py path/to/file.xpr
  py tools/import_xpr.py path/to/file.xpr --note "OEM baseline before tuning"
  py tools/import_xpr.py path/to/file.xpr --version "BUEIB310 12-11-03"

This only writes to sessions/<checksum>/ on disk. It never talks to the
ECU -- burning an imported map to the live bike is a separate, explicit
step via POST /eeprom/burn (or the Map Editor's BURN button).
"""
import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from ecu.xpr_import import DEFAULT_VERSION, import_xpr_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xpr_path", help="Path to the .xpr (or raw .bin) file")
    parser.add_argument("--version", default=DEFAULT_VERSION,
                         help=f"ECU firmware string, used to size/decode the EEPROM (default: {DEFAULT_VERSION})")
    parser.add_argument("--note", default="", help="Rider note to attach to the imported session")
    parser.add_argument("--sessions-dir", default=str(BASE / "sessions"))
    args = parser.parse_args()

    src = Path(args.xpr_path)
    if not src.exists():
        print(f"File not found: {src}")
        return 1

    try:
        result = import_xpr_bytes(src.read_bytes(), Path(args.sessions_dir),
                                   args.version, args.note, src.name)
    except ValueError as e:
        print(f"Import failed: {e}")
        return 1

    if result["trimmed_bytes"]:
        print(f"Trimmed {result['trimmed_bytes']} trailing bytes (ECMSpy export padding)")
    print(f"Decoded OK. bike_serial={result['bike_serial']}, maps={result['map_keys'][:6]}")
    print(f"{'New' if result['is_new'] else 'Existing'} session: {result['checksum']}")
    print(f"  -> {result['session_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
