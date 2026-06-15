<!-- DEV NOTE: planning doc (Spanish per project convention). All CODE remains English.
     Hallazgos VERIFICADOS leyendo los archivos reales (no claims de freebuff sin validar).
     Fecha: 2026-06-14. Relacionado: BACKLOG_ECM_DEFS.md (BL-ECM-01). NO commiteado aún. -->

# BACKLOG — Lógica de lectura/escritura del EEPROM (refactor multi-firmware)

> Documento de hallazgos para el refactor EcmDefs visto desde la **lógica de read/write
> del EEPROM**. Complementa BACKLOG_ECM_DEFS.md (plan macro) y el diagnóstico del inbox.
> Todo lo de abajo está verificado contra el código en `main`.

## TL;DR
El refactor está **~40% hecho**: los parámetros escalares ya se leen del XML. Falta
migrar **mapas (read+write), bins VE, páginas, y el grid VE del Dashboard**. El **frame
RT (logging en vivo) está bloqueado** sin archivos `.adx`. Hay **código muerto** para
borrar. El plan macro de 6 fases se reduce a **~3 fases reales**.

---

## ⭐ START HERE (para el siguiente chat) — estado al 2026-06-14

**Modelo de datos:** el pipeline trabaja sobre `eeprom.bin` (1206 bytes) guardado por
sesión en `sessions/<sid>/eeprom.bin`. Hay 13 dumps, todos BUEIB310 → **golden masters
de regresión ya existentes, no hace falta capturar nada** (decisión #5 resuelta).

**Decisiones tomadas:**
1. **Alcance = EEPROM-only** (leer + quemar multi-firmware sobre `.bin`). El RT/`.adx`
   (logging en vivo) queda BLOQUEADO/futuro, NO en este refactor. El usuario es
   transparente a perseguir `.adx` luego, pero respetando toda la lógica que ya existe
   alrededor del `.bin`.
2. Snapshot golden: **ya está OK** (los `.bin` por sesión son el baseline).
3. Trabajo en rama **`feat/ecm-defs`** (desde `main`); si algo sale mal → `git checkout main`.
   OJO: la rama protege el código, NO la EEPROM física — el burn (Fase C) va desactivado
   /guardado hasta validar. (`origin/refactor/safe-cleanup` es vieja/stale, NO usar.)

**Tipos reales en los XML EcmSpy** (verificado en BUEIB.xml, NO es "type=3D"):
- Escalares = `type=Value` (ya los lee `eeprom_params.py`).
- Mapas = `type=Map` (ej. Fuel Map Front off=870 size=168 rows=12 cols=13 → stride 14 = separador).
- Ejes = `type=Axis` (Fuel Map RPM Axis off=644 size=26 rows=13 → 2 bytes/val; Load Axis off=632 size=12 → 1 byte/val).
- Otros tags presentes: `Table`, `Array`, `Bits` (revisar a qué corresponde cada uno al construir el parser).

**Pendiente de freebuff (research read-only):** tabla maestra de offsets/dims/stride por
los 14 firmwares, `safe_zone` por firmware, caza de `.adx`, naming del 2nd fuel map.

**Por dónde empezar a codear:** Fase A (parser `ecm_defs.py`) → validar contra los `.bin`
BUEIB byte a byte → Fase B (lectura) → Fase C (burn con guard). Detalle abajo.

---

## 1. YA dinámico — NO tocar ✅

| Componente | Archivo | Cómo |
|:-----------|:--------|:-----|
| Resolver versión ECU | `ecu/version_resolver.py` | `resolve_ecu("BUEIB310")` → `files.xml` → dict ECM (dbfile, ddfi, poll_len, size). **Verificado correcto** (el "bug de indentación" reportado por freebuff es FALSO). |
| Parámetros escalares | `ecu/eeprom_params.py` | `decode_params(blob, version)` lee todos los `type=Value` del XML. Usado por `main.py:27`, `server.py:23`, `handlers/eeprom.py:10,390`. |
| Heatmap/3D del **Tuner** | `web/templates/tuner.html` | `rpm=mB.axes[..]; rows=lod.length; cols=rpm.length` (líneas 212-213, 302, 397). Se adapta a CUALQUIER dimensión que llegue. |
| Web server | `web/server.py` | Pasamanos: `eeprom_maps={}` (390), `ecu_identity={}` (394, poblado dinámico, expuesto en `/live` línea 314). Sin dims hardcodeadas. |
| Burn ledger | `web/burn_ledger.py` | `diff_maps()` (32) itera `sorted(new_maps)` + enumera rows/cols dinámicamente. **Caveat:** `TUNE_REGION_OFFSET = 327` (22) hardcodeado en `tune_hash` (`blob[327:]`) — suposición BUEIB, revisar para otros firmwares. |

---

## 2. SIGUE hardcodeado — migrar ❌

### 2.1 Mapas VE/Spark — `ecu/eeprom.py` (NÚCLEO del trabajo)
`decode_eeprom_maps()` (línea 102) y `encode_eeprom_maps()` (línea 163):

| Tabla | Offset fijo | Dims | Stride |
|:------|:-----------:|:----:|:------:|
| spark_load (eje 1b) | 602 | 10 | — |
| spark_rpm (eje 2b) | 612 | 10 | — |
| fuel_load (eje 1b) | 632 | 12 | — |
| fuel_rpm (eje 2b) | 644 | 13 | — |
| fuel_front | 870 | 12×13 | **cols+1 (separador)** |
| fuel_rear | 1038 | 12×13 | **cols+1 (separador)** |
| spark_front | 670 | 10×10 | cols (denso), ×0.25 |
| spark_rear | 770 | 10×10 | cols (denso), ×0.25 |

- `read_map()` (121) **hardcodea `stride = cols+1`** → no soporta formato denso
  (BUEGC/BUEIA/BUEKA y todo el grupo 20×16). `decode_eeprom_maps` retorna `{}` si
  `len < 1206` (tamaño BUEIB fijo).
- Consumidores: `main.py:173` (live), `handlers/eeprom.py` (decode + **encode/burn** :246),
  `handlers/tuner.py:63`, `server.py:22`, `vs_engine.py:35-36`.

### 2.2 Escritura/Burn — `ecu/eeprom.py:163` + `web/handlers/eeprom.py:198,246` (PELIGRO 🔴)
`encode_eeprom_maps()` escribe en 870/1038/670/770 fijos (líneas 187-190); "safe zone
670-1205" hardcodeada. **Con otra ECU corrompe la EEPROM al quemar.** Único fallo
realmente grave (puede arruinar la calibración de la moto).

### 2.3 Páginas + tamaño — `ecu/connection.py`
`BUEIB_PAGES` (6 tuplas fijas), `RT_RESPONSE_SIZE=107` (36), `read_full_eeprom()` arma
`bytearray(1206)` fijo, `write_full_eeprom()` con safe-zone fija.

### 2.4 Bins VE — `ecu/protocol.py:414`
`RPM_BINS` (13) y `LOAD_BINS` (12) constantes; los usa `CellTracker` en `ecu/session.py`
y `_rebuild_summary`. Con 20×16 el grid cambia a 320 celdas.

### 2.5 Frontend del **Dashboard** — `web/static/app.js` + `web/templates/index.html`
- **Grid de cobertura VE (`cobertGrid`)** HARDCODEADO 13×12: `RPM_BINS`/`LOAD_BINS`
  (app.js:37-38, mismos valores que protocol.py), usados en `buildCobertGrid()` (161),
  total de celdas (306), objectives (1801), arranque (3184). **NO dinámico** (a diferencia
  de tuner.html). Alimentar desde los ejes reales.
- **`showMap()` (app.js:1006) SÍ es dinámico en dimensiones** (lee `_mapsData.axes` y la
  tabla del servidor). PERO labels y botones fijos a 4 mapas: `{fuel_front, fuel_rear,
  spark_front, spark_rear}` (1016-1017, 1035) y `index.html:549-552` (4 botones). Un 2nd
  fuel map (DDFI-3) necesitaría label + botón nuevos.

### 2.6 Pestañas/ejes del Tuner — `web/templates/tuner.html:105,164`
4 pestañas fijas (FUEL/SPARK × FRONT/REAR) y `AX` con 4 mapas. Las DIMENSIONES son
dinámicas, pero el CONJUNTO de mapas no: un **2nd fuel map (12×8, DDFI-3)** necesitaría
pestaña + entrada en `AX` nuevas.

---

## 3. Código muerto — borrar 💀
`ecu/eeprom.py`: `BUEIB_PARAMS` (línea 15) + `decode_eeprom_params()` (línea 79).
**Nadie los importa** (grep en todo el repo). Reemplazados por `eeprom_params.decode_params`.

---

## 4. Independiente / fuera de alcance
- **`web/launch.py:291-292`** — `RPM_BINS` (16) + `TPS_BINS` (16) para análisis de
  conducción (comparar sesiones), **no** para decodificar EEPROM. No migrar.
- **Frame RT (RT_VARIABLES, poll_len)** — ⛔ BLOQUEADO. `poll_len` varía 99/100/103/107/135.
  Los XML no definen RT (eso vive en `.adx` de TunerPro, ausentes). El **logging en vivo
  se queda DDFI-2-only** hasta conseguir los `.adx`. Esta es la mitad que el refactor NO
  resuelve.

---

## 5. Datos reales (`.bin` de la Pi)
13 `eeprom.bin`; tamaños únicos **1206** (válidos) y **0** (lecturas fallidas → tolerar
`len==0`, ya se hace). Firmware **BUEIB310** siempre. Golden master abundante para
regresión BUEIB.

---

## 6. Plan reducido (6 fases → ~3 reales)

**Fase A — Decoder de mapas/ejes desde XML.** Extender `eeprom_params.py` o crear
`ecu/ecm_defs.py`: `decode_maps()`/`encode_map()` con **stride dinámico** (`stride = size//rows`;
`cols+1`=separador, `cols`=denso), `fuel_rpm_bins()`/`fuel_load_bins()` desde ejes,
tamaño EEPROM dinámico, `derive_pages()`, `safe_zone()`. Tolerar `len==0`.

**Fase B — Migrar lectura.** `decode_eeprom_maps(blob, defs)` con fallback BUEIB;
`protocol` bins → `get_rpm_bins(defs)`; `CellTracker(rpm_bins, load_bins)` por constructor;
`connection.read_full_eeprom` con tamaño/páginas dinámicas; `app.js` recibe ejes reales.
Validar regresión byte a byte contra los .bin BUEIB.

**Fase C — Migrar escritura/burn (al final, con guard).** `encode_eeprom_maps` +
`write_full_eeprom` con offsets/safe_zone del XML; **hard-refuse si el firmware no
matchea** (fallback-a-BUEIB solo para leer, nunca escribir). Borrar código muerto.

**Transversal:** documentar RT "DDFI-2 only" + guard `poll_len≠107` (rechazar/avisar).
2nd fuel map en tuner.html cuando se necesite DDFI-3.

### Reglas de seguridad (no negociables)
1. Leer primero (reversible); **burn al final** detrás del guard.
2. Burn solo con offsets del XML matcheado y dentro de `safe_zone`. Hard-refuse si no.
3. Validación: `decode_*(snapshot, BUEIB) == salida actual` byte a byte tras cada fase.
4. Snapshot golden de la EEPROM de la Pi ANTES de codear.

---

## 7. Decisiones pendientes (usuario)
1. Alcance: EEPROM-only (recomendado) vs perseguir `.adx` para RT.
2. ¿Capturar snapshot golden ya? (read-only)
3. Código graf2 del commit 25075e5: ¿revertir o dejar?

> Nota: el usuario pidió el nombre `backlog_eeprom_read_logic.md`; se usó
> `BACKLOG_EEPROM_READ_LOGIC.md` para respetar la convención de los otros BACKLOG_*.md.
