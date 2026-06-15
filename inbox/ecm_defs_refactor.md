# EcmDefs Refactor: Eliminar hardcodeos de EEPROM → XML dinámico

## Fecha
2026-06-14

## Contexto

Actualmente `protocol.py` tiene hardcodeados `RPM_BINS` y `LOAD_BINS` para el CellTracker,
y `eeprom.py` tiene hardcodeados todos los offsets de mapas y ejes.

Esto funciona SOLO para el firmware BUEIB (la ECU actual). Si se conecta cualquier otra ECU
con diferente firmware, los offsets y dimensiones no coinciden y el código lee/escribe basura.

## Hallazgo: 3 familias de ECU en los XMLs de EcmSpy

Se analizaron los 14 XMLs en `ecu_defs/` y se descubrieron TRES grupos con estructuras
totalmente diferentes:

### Grupo A: 13×12 con separador (BUEIB-like)

| FW | Fuel Front | Fuel Rear | Load bins | RPM bins | Formato |
|:--:|:----------:|:---------:|:---------:|:--------:|:-------:|
| BUEIB | off=870 | off=1038 | 12 (1-byte) | 13 (2-byte) | stride=14 (13+1 sep) |
| B2RIB | off=870 | off=1038 | 12 | 13 | stride=14 |
| BUECB | off=802 | off=970 | 12 | 13 | stride=14 |
| BUEGB | off=862 | off=1030 | 12 | 13 | stride=14 |

### Grupo B: 13×12 denso (sin separadores)

| FW | Fuel Front | Fuel Rear | Size | Formato |
|:--:|:----------:|:---------:|:----:|:-------:|
| BUEGC | off=788 | off=944 | 156 | stride=13 (denso) |
| BUEIA | off=744 | off=900 | 156 | stride=13 (denso) |
| BUEKA | off=760 | off=916 | 156 | stride=13 (denso) |

### Grupo C: 20×16 fuel + 12×8 secondary

| FW | Fuel Front | Fuel Rear | Load bins | RPM bins | 2nd Fuel Front |
|:--:|:----------:|:---------:|:---------:|:--------:|:--------------:|
| BUE1D | off=2072 | off=2392 | 16 | 20 | off=2712, 12×8 |
| BUE2D | off=2328 | off=2648 | 16 | 20 | off=2968, 12×8 |
| BUE3D | off=2408 | off=2728 | 16 | 20 | off=3048, 12×8 |
| BUEWD | off=1816 | off=2136 | 16 | 20 | off=2456, 12×8 |
| BUEYD | off=1816 | off=2136 | 16 | 20 | off=2456, 12×8 |
| BUEZD | off=2072 | off=2392 | 16 | 20 | off=2712, 12×8 |
| BUEOD | off=1816 | off=2136 | 16 | 20 | off=2456, 12×8 |

## Impacto

Si alguien conecta una ECU BUE1D (20×16):
- RPM_BINS tiene 13 valores → la ECU tiene 20 valores
- LOAD_BINS tiene 12 valores → la ECU tiene 16 valores
- `decode_eeprom_maps` lee offset 870 → el mapa real está en 2072
- `encode_eeprom_maps` escribe en offset 870 → escribe en área de DTC/factory config
- CellTracker acumula en 13×12=156 celdas → el mapa real es 20×16=320 celdas
- Las sugerencias VE del tuning report apuntan a offsets completamente equivocados

**Todo el pipeline de tuning (CellTracker → decode → encode → burn) produce resultados
incorrectos silenciosamente.**

## Solución propuesta

Crear `ecu/ecm_defs.py` que parsea los XMLs de EcmSpy y extrae dinámicamente:
- Offsets de cada mapa y eje
- Dimensiones (rows, cols)
- Escalas
- Formato (con/sin separador)

Luego modificar:
1. `protocol.py` → `get_rpm_bins(version)` / `get_load_bins(version)`
2. `session.py` → CellTracker recibe bins por constructor
3. `eeprom.py` → decode/encode reciben `ecm_defs` en vez de valores hardcodeados
4. `main.py` / `logger_process.py` → pasar los bins al crear CellTracker
5. `version_resolver.py` → integrar selección de XML por versión de firmware

## Plan de implementación detallado

Ver `BACKLOG.md` o la conversación del 2026-06-14 para el plan paso a paso.

## Archivos a modificar

- `ecu/ecm_defs.py` (NUEVO) — parser XML de EcmSpy
- `ecu/protocol.py` — eliminar RPM_BINS, LOAD_BINS constantes
- `ecu/session.py` — CellTracker con bins dinámicos
- `ecu/eeprom.py` — decode/encode con defs
- `ecu/logger_process.py` — pasar bins al crear CellTracker
- `main.py` — pasar bins al CellTracker sync
- `ecu/version_resolver.py` — integrar selección de XML
- `web/launch.py` — tiene su propio RPM_BINS (independiente, para análisis de lanzadas)
