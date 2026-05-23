with open('/home/pi/buell/CHANGELOG.md', encoding='utf-8') as f:
    content = f.read()

entry = """## [v2.6.6] — 2026-05-23
### Changed
- ecu/protocol.py: recalibración VSS_CPKM25 1368 → 1518 (~11% ajuste).
  Alinea velocidad del dash (VS_KPH) con GPS. Derivado de 3,029 períodos
  estables en rides 4-5 de sesión 47BF04.

"""

with open('/home/pi/buell/CHANGELOG.md', 'w', encoding='utf-8') as f:
    f.write(entry + content)

print('OK: v2.6.6 entry added')
