c = open('/home/pi/buell/CHANGELOG.md').read()
entry = '''## [v2.6.8] — 2026-05-23
### Changed
- ecu/protocol.py: gear detection — ring buffers envueltos en clase GearFilter.
  Elimina estado mutable a nivel modulo, permite testeo independiente
  y uso de instancias aisladas.
- BACKLOG.md: marcado P2 completado.

'''
open('/home/pi/buell/CHANGELOG.md', 'w').write(entry + c)
print('OK')
