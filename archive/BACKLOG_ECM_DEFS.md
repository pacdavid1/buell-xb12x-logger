<!-- DEV NOTE: planning doc (Spanish per project convention). All CODE remains English.
     Promoted from inbox/ecm_defs_refactor.md (freebuff) on 2026-06-14. Tracked in BACKLOG.md as BL-ECM-01. -->

🔍 **AUDITED 2026-07-03: PARTIALLY-DONE — mostly superseded by BL-ECM-01 (confirmed shipped: `ecu/ecm_defs.py`, `ecu/version_resolver.py`, `ecu/rt_defs.py`), but NOT fully.** Two sub-items from this file's own plan are still genuinely open: (1) 2nd fuel map not in `ecu/ecm_defs.py`'s `MAP_KEYS` — UI can't show/burn it, tracked separately under BL-ECM-02's "2nd Fuel Map" note in `BACKLOG.md`; (2) dynamic RPM/LOAD bins in `protocol.py`/`app.js` — still hardcoded BUEIB-only, tracked separately as BL-ECM-01-RESIDUAL in `BACKLOG.md`. Both residuals are already captured elsewhere, so nothing is lost — this file is safe to archive once confirmed those two entries stay tracked. Full detail in the AUDIT REPORT section at the top of `BACKLOG.md`.

# EcmDefs Refactor: Multi-ECU Support via EcmSpy XML

## Fecha
2026-06-14

## Contexto — Por qué esto es un GameChanger

Actualmente, el 100% de los offsets de la EEPROM y los RT parameters están
**hardcodeados para el firmware BUEIB** (la ECU de la XB12X).

Descubrimos que existen **14 XMLs de EcmSpy** en `ecu_defs/` que definen la
estructura COMPLETA de diferentes firmwares de ECU. Y resultó que:

**217 entradas críticas tienen diferentes offsets entre firmwares.**

Esto significa que si conectas cualquier otra ECU (BUE1D, BUEWD, etc.)
TODO el pipeline se rompe — desde los valores en vivo hasta los burns de EEPROM.

## Los 14 firmwares descubiertos

### Grupo A: 13×12 fuel maps (BUEIB-like) — 7 firmwares
| FW | Fuel Front | Fuel Rear | Load bins | RPM bins | Formato |
|:--:|:----------:|:---------:|:---------:|:--------:|:-------:|
| BUEIB | off=870 | off=1038 | 12 (1-byte) | 13 (2-byte) | stride=14 |
| B2RIB | off=870 | off=1038 | 12 | 13 | stride=14 |
| BUECB | off=802 | off=970 | 12 | 13 | stride=14 |
| BUEGB | off=862 | off=1030 | 12 | 13 | stride=14 |
| BUEGC | off=788 | off=944 | 12 | 13 | **stride=13 (denso)** |
| BUEIA | off=744 | off=900 | 12 | 13 | **stride=13 (denso)** |
| BUEKA | off=760 | off=916 | 12 | 13 | **stride=13 (denso)** |

### Grupo C: 20×16 fuel + 12×8 secondary — 7 firmwares
| FW | Fuel Front | Fuel Rear | Load bins | RPM bins | 2nd Fuel |
|:--:|:----------:|:---------:|:---------:|:--------:|:--------:|
| BUE1D | off=2072 | off=2392 | 16 | 20 | 12×8 |
| BUE2D | off=2328 | off=2648 | 16 | 20 | 12×8 |
| BUE3D | off=2408 | off=2728 | 16 | 20 | 12×8 |
| BUEWD | off=1816 | off=2136 | 16 | 20 | 12×8 |
| BUEYD | off=1816 | off=2136 | 16 | 20 | 12×8 |
| BUEZD | off=2072 | off=2392 | 16 | 20 | 12×8 |
| BUEOD | off=1816 | off=2136 | 16 | 20 | 12×8 |

## Inventario completo de hardcodeos a eliminar

### 1. ecu/eeprom.py — ~68 offsets hardcodeados

**BUEIB_PARAMS (~50 parámetros):**
```
"KTemp_Fan_On":      (498, 1.0,  50.0, "°C",  "Fan ON temp"),
"KTemp_Fan_Off":     (499, 1.0,  50.0, "°C",  "Fan OFF temp"),
"KO2_Midpoint":      (186, 0.00196, 0.0, "V", "O2 target"),
"KO2_Rich":          (187, 0.00196, 0.0, "V", "O2 rich thr"),
"KTPS0":             (200, 0.00244, 0.0, "V", "TPS cerrado"),
... ~45 más ...
```

**decode_eeprom_maps() — 12 offsets:**
```
"spark_load": read_axis_1b(602, 10),
"spark_rpm":  read_axis_2b(612, 10),
"fuel_load":  read_axis_1b(632, 12),
"fuel_rpm":   read_axis_2b(644, 13),
"fuel_front": read_map(870,  12, 13, 1.0),
"fuel_rear":  read_map(1038, 12, 13, 1.0),
"spark_front": read_map_spark(670, 10, 10, 0.25),
"spark_rear":  read_map_spark(770, 10, 10, 0.25),
```

**encode_eeprom_maps() — 6 offsets:**
```
write_fuel_map(870,  12, 13, ...)
write_fuel_map(1038, 12, 13, ...)
write_spark_map(670, 10, 10, ...)
write_spark_map(770, 10, 10, ...)
```

### 2. ecu/connection.py — 6 EEPROM page definitions
```python
BUEIB_PAGES = [
    (1,    0, 256),
    (2,  256, 256),
    (3,  512, 158),
    (4,  670, 256),
    (5,  926, 256),
    (6, 1182,  24),
]
```

### 3. ecu/protocol.py — 2 arrays + ~40 RT parameters

**RPM_BINS / LOAD_BINS:**
```python
RPM_BINS  = [0, 800, ..., 8000]    # 13 valores (BUE1D tiene 20)
LOAD_BINS = [10, 15, ..., 255]      # 12 valores (BUE1D tiene 16)
```

**RT_VARIABLES (~40 parámetros):**
```python
RT_VARIABLES = {
    "RPM":          (11, 2, 1.0,    0.0),
    "Seconds":      ( 9, 2, 1.0,    0.0),
    "CLT":          (30, 2, 0.1,  -40.0),
    "EGO_Corr":     (54, 2, 0.1,    0.0),
    ... ~35 más ...
}
```

## Impacto de conectar otra ECU

| Componente | BUEIB (hoy) | BUE1D (20×16) | Consecuencia |
|-----------|:-----------:|:-------------:|-------------|
| RPM_BINS | 13 valores | **20 valores** | 7 celdas del mapa nunca se tocan |
| LOAD_BINS | 12 valores | **16 valores** | 4 filas del mapa ignoradas |
| fuel_front offset | 870 | **2072** | Lee datos de DTC/factory config |
| fuel_rear offset | 1038 | **2392** | Lee datos incorrectos |
| EEPROM page 4 start | 670 | **?** | Write falla o escribe en area incorrecta |
| KTemp_Fan_On | 498 | **?** | Web muestra temp de ventilador erronea |
| RT: RPM offset | 11 | **?** | Dashboard muestra RPM incorrecto |

**Riesgo máximo:** `encode_eeprom_maps()` escribe en offset 870, que
en BUE1D NO es fuel_front. Podría **corromper la EEPROM**.

## Solución propuesta

### Nuevo archivo: `ecu/ecm_defs.py`

```
ecu/ecm_defs.py
├── EcmDefs class
│   ├── __init__(xml_path)     → parsea el XML
│   ├── get_param(name)        → (offset, size, scale, translate, units)
│   ├── get_map(name)          → (offset, rows, cols, scale, stride)
│   ├── get_axis(name)         → offset, size, element_size
│   ├── fuel_maps()            → lista de mapas de combustible
│   ├── spark_maps()           → lista de mapas de chispa
│   ├── all_params()           → dict {name: info} para web UI
│   ├── eeprom_pages()         → lista de (page, start, length)
│   └── rt_variables()         → dict de RT variable definitions
│
├── load_for_version(ver)     → factory: busca el XML por version
├── guess_format(rows, cols, size) → detecta stride (separador vs denso)
└── SUPPORTED_VERSIONS        → lista de firmwares con XML disponible
```

### Pipeline de carga al detectar ECU

```
ECU conecta → get_version() → "BUE1D"
                    ↓
         EcmDefs.load_for_version("BUE1D")
                    ↓
         Busca ecu_defs/BUE1D.xml
                    ↓
         Extrae: parámetros, mapas, ejes, páginas, RT vars
                    ↓
         CellTracker recibe (rpm_bins, load_bins) del XML
         decode_eeprom_maps recibe (ecm_defs)
         encode_eeprom_maps recibe (ecm_defs)
         connection.py recibe (eeprom_pages)
         protocol.py ya no tiene constantes fijas
```

### UI Dinámica — Las gráficas también

Si los mapas pueden ser 13×12, 20×16, 12×8, etc., la UI del tuner debe
adaptarse automáticamente:

- Heatmap de VE: dimensiones dinámicas (no fijas)
- Ejes RPM/Load: labels dinámicos desde el XML
- Colores y escalas: consistentes sin importar dimensiones
- 2nd Fuel maps: mostrar/ocultar según el firmware

Esto toca tanto backend (`/tuner/maps`, `/coverage.json`) como frontend
(`tuner.html`, `app.js`).

### Orden de implementación

```
FASE 1: ecu/ecm_defs.py
  [1.1] Parser XML genérico
  [1.2] load_for_version()
  [1.3] Tests con BUEIB.xml vs EEPROM real

FASE 2: Reemplazar hardcodeos (back-end)
  [2.1] protocol.py → get_rpm_bins() get_load_bins()
  [2.2] session.py → CellTracker recibe bins
  [2.3] eeprom.py → decode/encode reciben ecm_defs
  [2.4] connection.py → páginas desde ecm_defs
  [2.5] logger_process.py + main.py → pasar defs al crear tracker

FASE 3: RT_VARIABLES dinámicos
  [3.1] Investigar si el frame RT cambia entre firmwares
  [3.2] Si sí, mover RT_VARIABLES al XML también
  [3.3] Verificar con EEPROM real de la Pi

FASE 4: UI Dinámica
  [4.1] Tuner heatmap adaptativo (dimensiones dinámicas)
  [4.2] Ejes de gráficas desde los bins reales
  [4.3] Mostrar/ocultar 2nd fuel maps según firmware
```

## Archivos a modificar (completo)

- `ecu/ecm_defs.py` — NUEVO
- `ecu/protocol.py` — eliminar RPM_BINS, LOAD_BINS, RT_VARIABLES fijos
- `ecu/eeprom.py` — eliminar BUEIB_PARAMS, decode/encode con defs
- `ecu/connection.py` — eliminar BUEIB_PAGES, páginas desde defs
- `ecu/session.py` — CellTracker con bins dinámicos
- `ecu/logger_process.py` — pasar defs al crear tracker
- `main.py` — pasar defs en _update_web_ecu_state
- `ecu/version_resolver.py` — integrar selección de XML
- `web/server.py` — endpoints /tuner/maps con dimensiones dinámicas
- `web/handlers/tuner.py` — usar defs para decode/encode
- `web/static/app.js` — heatmap dinámico (13×12 vs 20×16 vs 12×8)
- `web/templates/tuner.html` — adaptarse a dimensiones variables

## Notas técnicas

### Formato de mapas (separador vs denso)

Diferentes firmwares almacenan los mapas de forma distinta:
- **Con separador (stride=cols+1):** BUEIB, B2RIB, BUECB, BUEGB
  - Cada fila tiene `cols` datos + 1 byte separador (0x00)
  - size = rows × (cols + 1)
- **Denso (stride=cols):** BUEGC, BUEIA, BUEKA
  - Cada fila tiene solo `c
