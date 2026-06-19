<!-- INST
purpose: reference prompt for EcmDefs architecture analysis (BL-ECM-01)
action:  read-only reference; use when starting Phase B of BL-ECM-01
delete:  after Phase B is implemented and merged to main
INST_END -->
# Prompt para Claude — Análisis de Arquitectura EcmDefs

Copia y pega esto en una sesión de Claude (codebuff, claude.ai, etc.) para
que analice el problema y proponga la arquitectura ideal.

---

## Contexto

Eres un arquitecto de software especializado en sistemas embebidos para
motocicletas Buell con ECU DDFI2. Necesito tu ayuda para diseñar un sistema
que permita que el logger ECU funcione con MÚLTIPLES firmwares de ECU,
no solo con el BUEIB actual.

## El problema

Actualmente, TODO está hardcodeado para el firmware BUEIB (ECU de la XB12X):
- **~50 parámetros escalares** con offsets fijos en BUEIB_PARAMS
- **8 mapas/ejes** con offsets y dimensiones fijas en decode_eeprom_maps
- **6 páginas EEPROM** fijas en BUEIB_PAGES
- **RPM_BINS (13) y LOAD_BINS (12)** fijos en protocol.py
- **~40 RT_VARIABLES** con offsets fijos dentro del frame serial de 107 bytes

Además, las funciones de **escritura** (encode_eeprom_maps, write_full_eeprom)
también usan estos offsets fijos, lo que significa que con otra ECU podrían
**corromper la EEPROM** escribiendo en áreas incorrectas.

## El hallazgo

Existen 14 archivos XML de EcmSpy en ecu_defs/ que definen la estructura
COMPLETA de la EEPROM para diferentes firmwares. Estos XMLs
contienen TODA la información necesaria para reemplazar los hardcodeos.

### Estructura del XML (ejemplo de BUEIB.xml)

```xml
<eeoffsets>
  <name>Fuel Map Front</name>
  <type>3D</type>
  <offset>870</offset>
  <size>168</size>
  <cols>13</cols>
  <rows>12</rows>
  <scale>1.0000000</scale>
  <translate>0.0000000</translate>
  <units></units>
  <format>0</format>
  <xaxis>Fuel Map RPM Axis</xaxis>
  <yaxis>Fuel Map Load Axis</yaxis>
</eeoffsets>
```

Para parámetros escalares el mismo formato pero sin xaxis/yaxis.

### 3 familias de ECU descubiertas

#### Grupo 1: 13×12 con separador (4 firmwares)
BUEIB, B2RIB, BUECB, BUEGB
- Fuel map: 13 cols × 12 rows, **stride=14** (13 datos + 1 separador 0x00 por fila)
- size = 168 = 12 × 14
- RPM axis: 13 valores (2 bytes c/u, little-endian, almacenados descendentes)
- Load axis: 12 valores (1 byte c/u)
- **OFFSETS VARÍAN** entre los 4 firmwares

#### Grupo 2: 13×12 denso (3 firmwares)
BUEGC, BUEIA, BUEKA
- Fuel map: 13 cols × 12 rows, **stride=13** (denso, SIN separador)
- size = 156 = 12 × 13
- Mismas dimensiones pero **diferente formato de almacenamiento**

#### Grupo 3: 20×16 + 12×8 secondary (7 firmwares)
BUE1D, BUE2D, BUE3D, BUEWD, BUEYD, BUEZD, BUEOD
- Fuel map: **20 cols × 16 rows** (vs 13×12 de BUEIB!)
- RPM axis: **20 valores** (vs 13)
- Load axis: **16 valores** (vs 12)
- **2nd Fuel Map**: 12 cols × 8 rows (NO existe en BUEIB)
- Todos los OFFSETS son completamente diferentes a BUEIB

#### Dato crítico
De las entradas que aparecen en 3+ firmwares, **217 tienen OFFSETS DIFERENTES**
y solo **10 comparten el mismo offset** entre todos los firmwares.

## Archivos a modificar

### NUEVO: ecu/ecm_defs.py
Parser de XML EcmSpy + loader + factory. Este archivo debe:
- Parsear el XML y extraer TODAS las definiciones (parámetros, mapas, ejes)
- Detectar automáticamente el stride (size ÷ rows = stride)
- Proveer métodos para obtener offsets, dimensiones, escalas
- Tener un cache de definiciones cargadas
- Tener fallback a BUEIB si no se encuentra el XML

### ecu/eeprom.py
- **ELIMINAR** BUEIB_PARAMS (se lee del XML)
- **ELIMINAR** offsets fijos en decode_eeprom_maps()
- **ELIMINAR** offsets fijos en encode_eeprom_maps()
- _validate_eeprom() debe usar rangos dinámicos

### ecu/connection.py
- **ELIMINAR** BUEIB_PAGES
- Derivar páginas EEPROM desde el offset máximo en el XML

### ecu/protocol.py
- **ELIMINAR** RPM_BINS, LOAD_BINS como constantes de módulo
- Convertir en funciones que reciben versión o EcmDefs
- RT_VARIABLES: INVESTIGAR si cambian entre firmwares

### ecu/session.py
- CellTracker.__init__(rpm_bins, load_bins) — ya no importa del módulo
- _rebuild_summary() — usar bins del tracker (no constantes)
- _generate_suggested_msq() — usar bins del XML + EEPROM

### web/server.py + handlers/tuner.py + static/app.js
- Heatmap VE con dimensiones DINÁMICAS
- Ejes de gráficas desde bins reales
- Mostrar/ocultar 2nd fuel maps según firmware

## Lo que necesito que analices

1. **Diseño de EcmDefs** — estructura de clases, métodos, factory. ¿Una clase
   plana o jerarquía? ¿Cómo modelar la diferencia entre mapas con separador
   y densos? ¿Cómo manejar RT_VARIABLES si no están en el XML?

2. **Arquitectura de datos** — flujo desde que se detecta la versión de la ECU
   (get_version()) hasta que se usan los offsets correctos en cada componente.
   ¿Quién crea el EcmDefs? ¿Cómo se propaga a CellTracker, decode_eeprom_maps,
   connection.py? ¿Singleton, inyección de dependencias, variable global?

3. **RT_VARIABLES** — los XMLs definen la EEPROM (memoria no volátil), pero el
   frame RT son 107 bytes que llegan en tiempo real por serial. Los XMLs de
   EcmSpy NO parecen contener las definiciones RT. ¿Cómo investigar si el
   layout del frame RT cambia entre firmwares? ¿Estrategia si SÍ cambia?

4. **Riesgo de burn** — encode_eeprom_maps() escribe en offsets fijos. Con
   una ECU BUE1D (20×16), escribiría en offset 870 cuando el mapa real está
   en 2072. **Podría corromper la EEPROM.** ¿Cómo mitigar esto durante la
   migración? ¿Validación previa al write?

5. **UI dinámica** — el heatmap del tuner debe adaptarse a:
   - 13×12 (BUEIB, 156 celdas)
   - 20×16 (BUE1D, 320 celdas)
   - 12×8 (2nd map, 96 celdas)
   - Además mostrar/ocultar el 2nd map según firmware
   ¿Cómo diseñar el frontend para que sea agnóstico de dimensiones?

6. **Migración sin riesgo** — orden de implementación para:
   - No romper la funcionalidad con BUEIB (la ECU actual)
   - Agregar soporte multi-firmware gradualmente
   - Validar contra EEPROM real después de cada cambio
   - Pruebas unitarias con los 14 XMLs

7. **Compatibilidad hacia atrás** — rides viejos se guardaron con los bins
   hardcodeados de BUEIB. Si cambiamos los bins, _rebuild_summary podría
   producir resultados inconsistentes. ¿Estrategia?

## Archivos de referencia

Los 14 XMLs están en **ecu_defs/** y la documentación completa del análisis
está en **inbox/ecm_defs_refactor.md**.

El código actual que MUESTRA cómo se usan estos hardcodeos está en:
- ecu/eeprom.py (BUEIB_PARAMS, decode_eeprom_maps, encode_eeprom_maps)
- ecu/connection.py (BUEIB_PAGES, read_full_eeprom)
- ecu/protocol.py (RPM_BINS, LOAD_BINS, RT_VARIABLES)
- ecu/session.py (CellTracker, _cell_key, _rebuild_summary)
- ecu/logger_process.py (cómo se crea el CellTracker hoy)
- main.py (cómo se crea el CellTracker sync target)
