#!/usr/bin/env python3
"""
ecu/version_resolver.py

Resuelve version_string de la ECU usando ecu_defs/files.xml
y devuelve la definición correcta de ECM (name, dbfile, ddfi, etc.).
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import logging

logger = logging.getLogger("VersionResolver")

ECU_DEFS_DIR = Path(__file__).parent.parent / "ecu_defs"
FILES_XML = ECU_DEFS_DIR / "files.xml"

_ECM_TABLE = None


def _load_ecm_table():
    if not FILES_XML.exists():
        logger.error("files.xml no encontrado en ecu_defs/")
        return []

    try:
        tree = ET.parse(FILES_XML)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Error parseando files.xml: {e}")
        return []

    def strip_ns(tag):
        return tag.split('}', 1)[-1]

    rows = []
    for e in root.iter():
        if strip_ns(e.tag) != "ecm":
            continue

        row = {}
        for c in e:
            row[strip_ns(c.tag)] = (c.text or "").strip()
        rows.append(row)

    return rows


def resolve_ecu(version_string):
    """
    Dado un version_string (ej. 'BUEIB310'), retorna un dict con la
    definición correcta de ECM basada en files.xml, o None.
    """
    global _ECM_TABLE

    if not version_string:
        return None

    token = version_string.strip().split()[0]

    if _ECM_TABLE is None:
        _ECM_TABLE = _load_ecm_table()

    # 1) Match exacto
    for e in _ECM_TABLE:
        if e.get("name") == token:
            return e

    # 2) Match por prefijo alfabético (BUEIB310 → BUEIB)
    alpha = ''.join(c for c in token if c.isalpha())
    for e in _ECM_TABLE:
        if e.get("name") == alpha:
            return e

    logger.warning(f"No match en files.xml para '{version_string}'")
    return None
