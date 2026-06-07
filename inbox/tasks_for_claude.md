# Tasks for Claude

## BUGS PENDIENTES

### BUG-A: Cobertura incompleta de RLock en ecu/connection.py
Archivo: ecu/connection.py
Que falta: _read_exact() y disconnect() no tienen with self._lock:
Contexto: Ya agregaste RLock a _send, get_rt_data y write_full_eeprom en v2.7.63.
Pero _read_exact se llama desde metodos no lockeados (read_eeprom_page, etc.)
y disconnect() puede cerrar el serial mientras otro hilo esta operando.
Fix: Agregar with self._lock: a _read_exact() y disconnect()

### BUG-B: ZeroDivisionError potencial en VSS calculation
Archivo: ecu/protocol.py - decode_rt_packet()
Problema: cpkm25 puede ser 0 si el VSS calibrator no se ha inicializado.
Linea: (vss / 0.039) * 3600 / (cpkm25 / 25 * 1000)
Fix: Validar cpkm25 > 0 antes de la division

### BUG-C: fetch() sin AbortSignal en app.js
Archivo: web/static/app.js (37 fetch calls)
Problema: Si el server se cuelga, las requests quedan colgadas para siempre.
Fix: Usar AbortController con timeout de 10s

## CLEANUP PENDIENTE

### CLEANUP-1: Eliminar archivos .bak
- gps/reader.py.bak
- web/templates/index.html.bak.grid
- web/templates/sessions_launch.html.bak

### CLEANUP-2: Eliminar tools/test_ecu.py.save (si aun existe)

## MEJORAS PENDIENTES DEL BACKLOG

### BL-UX-03: Baro como estadistica del ride
Contexto: El BMP280 ya existe como sensor separado en la Pi.
No se busca compensacion (DDFI2 no tiene KBaro).
Solo medir y mostrar presion barometrica como estadistica.

### BL-LOGGER-01: Grabar humidity_pct y gps_alt_m en CSV
Archivo: ecu/session.py - write_sample()
Fix: Agregar humidity_pct y gps_alt_m al CSV_COLUMNS y al row dict

---
Prioridad sugerida: BUG-A > BUG-B > CLEANUP-1 > BL-LOGGER-01 > BL-UX-03 > BUG-C
