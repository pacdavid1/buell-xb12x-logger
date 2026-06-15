# Diagnóstico Completo: Estado Actual del Refactor Multi-ECU

## Fecha
2026-06-14

## ⚡ Hallazgo crítico: ¡Parte del trabajo YA ESTÁ HECHA!

### Lo que ya existe (y funciona)

| Archivo | Estado | Propósito |
|:--------|:------|:----------|
| **`ecu/eeprom_params.py`** | ✅ **LISTO** | Parsea XMLs dinámicamente, decodifica TODOS los parámetros type=Value del EEPROM según el firmware. Usado por main.py, web/server.py, web/handlers/eeprom.py |
| **`ecu/version_resolver.py`** | ✅ **LISTO** | Lee files.xml, resuelve version_string ("BUEIB310") → definición ECM (dbfile, poll_len, size, etc.) |
| **`ecu_defs/files.xml`** | ✅ **LISTO** | Catálogo de 20 ECMs con size, xsize, poll_len, dbfile, ddfi, category |
| **`ecu_defs/*.xml`** (14) | ✅ **LISTO** | Definiciones completas de EEPROM (parámetros, mapas, ejes) |

### Lo que SÍ hay que hacer

| Archivo | Qué falta | Impacto |
|:--------|:----------|:--------|
| **`ecu/eeprom.py`** | `decode/encode_eeprom_maps()` aún con offsets fijos | ❌ Crítico — con otra ECU los mapas se leen/escriben mal |
| **`ecu/protocol.py`** | `RPM_BINS`/`LOAD_BINS` hardcodeados (líneas 414-415) | ❌ Crítico — CellTracker usa bins equivocados |
| **`ecu/connection.py`** | `BUEIB_PAGES` fijas (líneas 43-50), `bytearray(1206)` fijo | ❌ Crítico — EEPROM de otro tamaño no funciona |
| **`ecu/session.py`** | `CellTracker` importa constantes de módulo (línea 28) | ❌ Medio — bins fijos desde import |
| **`ecu/protocol.py`** | `RT_VARIABLES` hardcodeado para 107 bytes | ⚠️ Bloqueado — sin .adx no sabemos offsets para otros tamaños |

### Lo que es código muerto

| Código | Evidencia |
|:-------|:----------|
| **`BUEIB_PARAMS`** en eeprom.py (líneas 15-51) | **NADIE** lo importa. Los web handlers ya usan `eeprom_params.decode_params()` en su lugar |
| **`decode_eeprom_params()`** en eeprom.py | **NADIE** lo importa desde eeprom.py. Todos importan `decode_params` desde `eeprom_params.py` |

## EEPROM bins en la Pi

Dumps de EEPROM en la Pi (verificado):
- **13 archivos** `eeprom.bin`; tamaños únicos: **1206** (válidos) y **0** (lecturas
  fallidas en esas sesiones → el decoder debe tolerar `len==0`, ya lo hace).
- Firmware: **BUEIB310** en todas. Solo una ECU conectada jamás.
- Tenemos golden master abundante para validar regresión BUEIB byte a byte.

## poll_len vs RT_VARIABLES

| Familia | poll_len | Variables RT | Estado |
|:--------|:--------:|:------------|:-------|
| DDFI-2 (BUEIB, B2RIB) | **107** | ~40 conocidas | ✅ Tenemos offsets |
| DDFI-2 (BUECB) | **103** | ? | ❌ Desconocido |
| DDFI (BUEIA, BUEGC) | **99-100** | ? | ❌ Desconocido |
| DDFI-3 (BUE1D, BUEWD) | **135** | ? muchas más | ❌ Desconocido |

No existen archivos .adx en ningún lado (ni Pi, ni repo, ni Windows).

## version_resolver.py — VERIFICADO CORRECTO (el "bug" reportado era FALSO POSITIVO)

Claude leyó el archivo real. La indentación es correcta — `row = {}` está dentro del
bloque, `for c in e:` y `rows.append(row)` al nivel correcto:

```python
    for e in root.iter():
        if strip_ns(e.tag) != "ecm":
            continue
        row = {}                                   # dentro del if, OK
        for c in e:                                # indentado bien
            row[strip_ns(c.tag)] = (c.text or "").strip()
        rows.append(row)                           # un row por <ecm>, OK
```

NO tocar este archivo. (Regla del proyecto: verificar claims de freebuff contra el
código real antes de actuar — este era un caso de falso positivo.)

## Plan ajustado (más pequeño de lo que pensábamos)

Dado que `eeprom_params.py` + `version_resolver.py` ya resuelven los parámetros
dinámicamente, el refactor real es:

1. **Extender `eeprom_params.py`** (o crear `ecm_defs.py`) para incluir:
   - decode_maps() / encode_maps() con stride dinámico
   - fuel_rpm_bins() / fuel_load_bins() desde los ejes del XML
   - derive_pages() para connection.py
   - safe_zone() para write_full_eeprom

2. **Migrar `eeprom.py`**:
   - Eliminar BUEIB_PARAMS (código muerto)
   - decode/encode_eeprom_maps() que reciban EcmDefs
   - read_map() con stride dinámico

3. **Migrar `connection.py`**:
   - Eliminar BUEIB_PAGES
   - read/write_full_eeprom con tamaño y páginas dinámicas

4. **Migrar `protocol.py` + `session.py`**:
   - Eliminar RPM_BINS/LOAD_BINS constantes
   - CellTracker recibe bins por constructor

5. **RT_VARIABLES**: Se queda como está, documentado "DDFI-2 only"

## ⚠️ Seguridad del burn (lo más delicado) y orden seguro

- `encode_eeprom_maps()` (eeprom.py:163) escribe en 870/1038/670/770 fijos (líneas
  187-190). Con otra ECU escribiría en el lugar equivocado → **corrupción de EEPROM al
  quemar**. Es el único fallo de verdad grave (puede brickear la calibración).
- `read_map()` (eeprom.py:121) **ya hardcodea `stride = cols + 1`** (formato separador)
  → no soporta el denso (BUEGC/BUE1D…). `decode_eeprom_maps` devuelve `{}` si
  `len < 1206` (tamaño BUEIB fijo).

**Reglas de seguridad para la migración (transversales):**
1. Migrar y validar TODA la lectura primero (reversible). El **burn va al final**.
2. El burn solo procede si los offsets vienen del XML del firmware **positivamente
   matcheado** y caen dentro de `safe_zone`. **Hard-refuse** si el firmware no matchea
   (fallback-a-BUEIB sirve para leer, NUNCA para escribir).
3. Guard barato e independiente: detectar `poll_len` desde files.xml; si `≠ 107`,
   rechazar/avisar en vez de malparsear un frame de 135 como 107.
4. Validación de regresión: `decode_*(snapshot, BUEIB) == salida actual` byte a byte
   sobre los .bin de la Pi, después de cada fase.

## NO se commiteó nada
Investigación y este doc NO tocaron git (instrucción: planear antes de codear).
Pendiente de decisión del usuario: (a) alcance EEPROM-only vs perseguir .adx para RT;
(b) capturar snapshot golden ahora; (c) revertir o dejar el código graf2 del commit
25075e5.

