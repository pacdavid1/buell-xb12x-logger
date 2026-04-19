#!/usr/bin/env python3
"""Reemplaza getSpeedColor por getGradientColor con stops fijos"""

import pathlib

path = pathlib.Path("/home/pi/buell/web/templates/index.html")
backup = path.with_suffix(".bak_grad")
path.replace(backup)
print(f"Respaldo en {backup}")

text = backup.read_text(encoding="utf-8")

gradient_func = """
function getGradientColor(speed) {
  if (speed <= 20)  return '#0000FF'; // Azul
  if (speed <= 60)  return '#00FF00'; // Verde
  if (speed <= 120) return '#FFFF00'; // Amarillo
  if (speed <= 160) return '#FF0000'; // Rojo
  return '#FF00FF';                   // Magenta
}
"""

# Reemplazar getSpeedColor por getGradientColor
text = text.replace("getSpeedColor(d.points[i].spd)", "getGradientColor(d.points[i].spd)")

# Insertar la función al inicio del <script>
text = text.replace("<script>", "<script>\n" + gradient_func)

path.write_text(text, encoding="utf-8")
print("OK")
