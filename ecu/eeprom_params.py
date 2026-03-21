#!/usr/bin/env python3
"""
ecu/eeprom_params.py — Parser de parámetros EEPROM desde XMLs de EcmSpy.
Lee ecu_defs/XXXX.xml según version_string de la ECU y decodifica
todos los parámetros Value del blob de 1206 bytes leído por read_full_eeprom().

Offset mapping:
  XML offset = posición en archivo XPR (incluye 4 bytes de header)
  blob_Pi[i] = XPR[i + 4]
  → blob_Pi[offset_XML - 4]
"""
import xml.etree.ElementTree as ET
import logging
from pathlib import Path

logger = logging.getLogger("EepromParams")

ECU_DEFS_DIR = Path(__file__).parent.parent / "ecu_defs"
HEADER_OFFSET = 0  # blob_Pi ya no incluye header XPR — offsets XML son directos


def _find_xml(version_string):
    """
    Mapea version_string → archivo XML.
    'BUEIB310 12-11-03' → ecu_defs/BUEIB.xml
    Toma el prefijo alfabético del primer token.
    """
    token = version_string.strip().split()[0]  # 'BUEIB310'
    prefix = ''.join(c for c in token if c.isalpha())  # 'BUEIB'
    candidates = [
        ECU_DEFS_DIR / f"{prefix}.xml",
        ECU_DEFS_DIR / f"{token}.xml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def decode_params(blob, version_string):
    """
    Decodifica parámetros Value del blob EEPROM (1206 bytes).
    Retorna lista de dicts:
      {name, offset, raw, value, units, scale, translate, remark}
    Solo procesa type=Value con offset >= HEADER_OFFSET.
    """
    xml_path = _find_xml(version_string)
    if xml_path is None:
        logger.warning(f"No se encontró XML para: {version_string}")
        return []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Error parseando {xml_path}: {e}")
        return []

    # Detectar namespace del XML
    ns_tag = root.tag  # '{BUEIB}dataSet' o similar
    ns = ns_tag.split('}')[0].lstrip('{') if '}' in ns_tag else ''
    prefix = f'{{{ns}}}' if ns else ''

    results = []
    for e in root.findall(f'{prefix}eeoffsets'):
        ptype = e.findtext(f'{prefix}type', default='')
        if ptype != 'Value':
            continue

        offset_str = e.findtext(f'{prefix}offset', default='')
        size_str   = e.findtext(f'{prefix}size', default='1')
        if not offset_str:
            continue

        offset = int(offset_str)
        size   = int(size_str) if size_str else 1
        blob_i = offset - HEADER_OFFSET

        if blob_i < 0 or blob_i + size > len(blob):
            continue

        try:
            scale     = float(e.findtext(f'{prefix}scale',     default='1') or 1)
            translate = float(e.findtext(f'{prefix}translate', default='0') or 0)
        except ValueError:
            scale, translate = 1.0, 0.0

        # Leer raw — 1 o 2 bytes big-endian
        if size == 2:
            raw = blob[blob_i] | (blob[blob_i + 1] << 8)  # little-endian
        else:
            raw = blob[blob_i]

        value = round(raw * scale + translate, 4)

        results.append({
            'name':      e.findtext(f'{prefix}name',    default='?'),
            'offset':    offset,
            'size':      size,
            'raw':       raw,
            'value':     value,
            'units':     e.findtext(f'{prefix}units',   default=''),
            'remark':    e.findtext(f'{prefix}remarks', default='') or
                         e.findtext(f'{prefix}remark',  default=''),
        })

    logger.info(f"Decoded {len(results)} params from {xml_path.name}")
    return results


def decode_params_dict(blob, version_string):
    """
    Igual que decode_params pero retorna dict keyed por name.
    Para acceso rápido por nombre.
    """
    return {p['name']: p for p in decode_params(blob, version_string)}
