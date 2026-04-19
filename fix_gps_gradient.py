#!/usr/bin/env python3
"""Reemplaza colores por gradiente continuo en el mapa"""

import pathlib, re

path = pathlib.Path("/home/pi/buell/web/templates/index.html")
backup = path.with_suffix(".bak2")
path.replace(backup)
print(f"Respaldo en {backup}")

text = backup.read_text(encoding="utf-8")

gradient_func = """
function getGradientColor(speed) {
  const min = 0, max = 200;
  const ratio = Math.min(Math.max(speed, min), max) / max;
  const r = Math.round(255 * ratio);
  const g = Math.round(255 * (1 - ratio));
  const b = Math.round(255 * (1 - ratio));
  return `rgb(${r},${g},${b})`;
}
"""

# Reemplazar llamada a getSpeedColor por getGradientColor
text = text.replace("getSpeedColor(d.points[i].spd)", "getGradientColor(d.points[i].spd)")

# Insertar la función al inicio del <script>
text = text.replace("<script>", "<script>\n" + gradient_func)

path.write_text(text, encoding="utf-8")
print("OK")
