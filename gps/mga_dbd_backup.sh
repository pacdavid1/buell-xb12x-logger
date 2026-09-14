#!/usr/bin/env bash
# Respaldo periodico de la base de datos de navegacion del M8N (UBX-MGA-DBD:
# almanaque + efemeride) para poder restaurarla despues de un coldboot en vez
# de esperar a que el receptor vuelva a buscar todo desde cero.
#
# CAVEAT (sin resolver aun, ver BL-GPS-MGA en BACKLOG.md): "ubxtool -R" graba
# TODO el trafico crudo recibido durante el poll (incluye NAV-PVT/NAV-DOP/etc,
# no solo los mensajes UBX-MGA-DBD). Para restaurar hace falta primero filtrar
# el archivo y quedarse solo con las tramas clase 0x13 id 0x80 -- ese script
# de restore todavia no existe. Este script SOLO hace el respaldo (lectura,
# sin tocar el receptor de forma que pueda romper algo).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/mga_dbd_backup.ubx"
TMP="$OUT.tmp"

sudo ubxtool -R "$TMP" -p MGA-DBD >/dev/null 2>&1 || true

if [ -s "$TMP" ]; then
    mv "$TMP" "$OUT"
    logger -t buell-gps-mga "MGA-DBD backup OK ($(stat -c%s "$OUT") bytes)"
else
    rm -f "$TMP"
    logger -t buell-gps-mga "MGA-DBD backup FAILED -- no data captured"
    exit 1
fi
