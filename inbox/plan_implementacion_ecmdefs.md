# Plan de Implementación: EcmDefs Refactor — Multi-ECU Support

## Fecha
2026-06-14

## Resumen

Eliminar todos los hardcodeos específicos de BUEIB y reemplazarlos con
carga dinámica desde los XMLs de EcmSpy (14 firmwares en ecu_defs/).

6 fases, ordenadas para que cada una sea independientemente testeable
y nunca rompa la funcionalidad con BUEIB (la ECU actual).

---

## Fase 1: `ecu/ecm_defs.py` — Parser XML + Factory

**Archivo nuevo** — 0 cambios a código existente.

Clases:
```
EcmDefs           → Carga un XML y expone definiciones
EepromParamDef    → (name, offset, size, scale, translate, units)
EepromMapDef      → (name, offset, rows, cols, scale, stride, has_separator)
EepromAxisDef     → (name, offset, count, byte_width)
```

Métodos principales:
- load(version_str) / load_default() — factory
- params() → dict[str, EepromParamDef]
- maps() / get_map(name) / get_axis(name)
- fuel_rpm_bins() / fuel_load_bins() — valores decodificados
- map_stride(name) / has_separator(name) — detección de formato
- derive_pages() → [(page_nr, offset, length)]
- safe_zone() → (safe_start, safe_end)
- decode_params(blob) / decode_maps(blob) / encode_map(blob, name, table)

Prueba: Cargar los 14 XMLs, verificar maps() no vacío y eeprom_size > 0.

---

## Fase 2: `ecu/eeprom.py` — Migrar a EcmDefs

| Cambio | Antes | Después |
|:-------|:------|:--------|
| BUEIB_PARAMS | 34 entradas fijas | ecm_defs.params() |
| decode_eeprom_params() | Itera BUEIB_PARAMS | Itera ecm_defs.params() |
| decode_eeprom_maps() | Offsets fijos (602,612,632,644,670,770,870,1038) | Itera ecm_defs.maps()+get_axis() |
| encode_eeprom_maps() | Offsets fijos (670,770,870,1038) | Itera ecm_defs.maps(), stride dinámico |
| read_map() | stride = cols + 1 fijo | stride = ecm_defs.map_stride(name) |
| read_map_spark() | stride = cols fijo | Unificado con read_map() genérico |
| _validate_eeprom() | len<600, offset 632 fijo | ecm_defs.eeprom_size*0.5, offsets dinámicos |

Firma: `decode_eeprom_maps(blob, ecm_defs=None)` con fallback a load_default().

---

## Fase 3: `ecu/connection.py` — Páginas dinámicas

| Cambio | Línea | Antes | Después |
|:-------|:-----|:------|:--------|
| BUEIB_PAGES | 43-50 | 6 tuplas fijas | ecm_defs.derive_pages() |
| read_full_eeprom() | 258 | bytearray(1206) | bytearray(ecm_defs.eeprom_size) |
| write_full_eeprom() | 303 | safe_start=670, safe_end=1205 | ecm_defs.safe_zone() |
| write_full_eeprom() | 313 | len(proposed) != 1206 | len(proposed) != ecm_defs.eeprom_size |

safe_zone() = (min(maps_offset), max_offset - 1)

---

## Fase 4: `protocol.py` + `session.py` — Bins dinámicos

protocol.py:
- ELIMINAR RPM_BINS, LOAD_BINS como constantes de módulo
- get_rpm_bins(version=None) / get_load_bins(version=None)
- set_default_defs(defs) para propagar desde main.py

session.py:
- CellTracker.__init__(self, rpm_bins=None, load_bins=None)
- CellTracker.* usa self.rpm_bins / self.load_bins (no globales)
- cell_key() función módulo con parámetros opcionales
- _rebuild_summary() compatible con rides viejos

---

## Fase 5: Integración main.py + logger_process.py + web/

main.py (líneas 118, 173):
1. Al detectar versión de ECU → EcmDefs.load(version_str)
2. set_default_defs(ecm_defs)
3. CellTracker(rpm_bins, load_bins)
4. decode_eeprom_maps(blob, ecm_defs)

logger_process.py (línea 138):
- Recibe ecm_defs vía IPC desde el proceso padre
- CellTracker(ecm_defs.fuel_rpm_bins(), ecm_defs.fuel_load_bins())

web/handlers/eeprom.py (múltiples):
- Pasar ecm_defs por contexto de request o cargar desde session_metadata

web/handlers/tuner.py (línea 63):
- Heatmap dinámico: enviar dimensiones y bins reales al frontend

---

## Fase 6: Validación contra EEPROM real

1. Snapshot EEPROM desde la Pi antes de cambios
2. decode_eeprom_maps(snapshot, EcmDefs.load("BUEIB")) == resultado actual
3. decode_eeprom_params(snapshot, EcmDefs.load("BUEIB")) == valores actuales
4. read_full_eeprom() con páginas derivadas = 1206 bytes idénticos
5. Prueba unitaria: 14 XMLs → todos con maps() no vacío
6. Prueba unitaria: detección de formato (separador vs denso) correcta

---

## Dependencias entre fases

```
Fase 1 (ecm_defs.py)
  ├── Fase 2 (eeprom.py)  →  depende de EcmDefs.params/maps
  ├── Fase 3 (connection.py) → depende de EcmDefs.derive_pages/safe_zone
  └── Fase 4 (protocol.py + session.py) → depende de EcmDefs.bins
        └── Fase 5 (main.py + web/) → integra todo
Fase 6 (validación) → después de cada fase
```

## Riesgos conocidos

1. **RT_VARIABLES** — Los XMLs de EcmSpy definen la EEPROM pero NO el frame RT
   de 107 bytes. Si el layout RT cambia entre firmwares, necesitamos otra fuente.
   Por ahora: asumir layout RT constante (solo validar empíricamente).

2. **Compatibilidad rides viejos** — _rebuild_summary() usa los bins para
   reconstruir rides. Si cambian, rides viejos podrían no coincidir.
   Solución: guardar bins en el summary JSON al cerrar ride.

3. **web/launch.py** — Tiene su propio RPM_BINS = [800,1200,...] para análisis
   de lanzadas. Es independiente del mapa VE, no necesita cambiar.

4. **web/eeprom_params.py** (archivo separado) — decode_eeprom_params se importa
   desde web/server.py y web/handlers/eeprom.py como `from ecu.eeprom_params`.
   Verificar si tiene su propio BUEIB_PARAMS.

---

## Orden de implementación sugerido

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
(crear)  (eeprom) (pages)  (bins)   (integration) (validation)
```

Cada fase: implementar → probar con BUEIB → validar contra EEPROM real → commit.

