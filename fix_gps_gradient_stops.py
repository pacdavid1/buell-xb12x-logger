#!/usr/bin/env python3
"""Reemplaza getGradientColor con stops azul→verde→amarillo→rojo→magenta"""

import pathlib, re

path = pathlib.Path("/home/pi/buell/web/templates/index.html")
backup = path.with_suffix(".bak_stops")
path.replace(backup)
print(f"Respaldo en {backup}")

text = backup.read_text(encoding="utf-8")

gradient_func = """
function getGradientColor(speed) {
  const min = 0, max = 200;
  const ratio = Math.min(Math.max(speed, min), max) / max;

  const stops = [
    {pos: 0.0, r:0,   g:0,   b:255},   // Azul
    {pos: 0.3, r:0,   g:255, b:0},     // Verde
    {pos: 0.6, r:255, g:255, b:0},     // Amarillo
    {pos: 0.8, r:255, g:0,   b:0},     // Rojo
    {pos: 1.0, r:255, g:0,   b:255}    // Magenta
  ];

  let lower = stops[0], upper = stops[stops.length-1];
  for (let i=0; i<stops.length-1; i++) {
    if (ratio >= stops[i].pos && ratio <= stops[i+1].pos) {
      lower = stops[i];
      upper = stops[i+1];
      break;
    }
  }

  const t = (ratio - lower.pos) / (upper.pos - lower.pos);
  const r = Math.round(lower.r + t*(upper.r - lower.r));
  const g = Math.round(lower.g + t*(upper.g - lower.g));
  const b = Math.round(lower.b + t*(upper.b - lower.b));

  return `rgb(${r},${g},${b})`;
}
"""

# Sustituir la función anterior por esta
text = re.sub(r"function getGradientColor[\s\S]*?\}", gradient_func, text)

path.write_text(text, encoding="utf-8")
print("OK")
