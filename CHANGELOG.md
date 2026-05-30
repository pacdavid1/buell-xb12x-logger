# Changelog

<!-- PROMPT_START — read ALL instructions until PROMPT_END before doing anything.
  If you only see part of this block (e.g. via head -5), scroll or read further —
  there are more instructions below.

  INSTRUCTIONS FOR AI ASSISTANTS:
  1. All changelog entries MUST be written in English.
  2. Each new entry follows this format:
       ## [vX.Y.Z] — YYYY-MM-DD
       ### Changed / Added / Fixed / Removed
       - file: description of change
       ### AI
       - <AI name and provider> (e.g. "Claude Sonnet 4.6, Anthropic")
  3. The ### AI section is MANDATORY for every new entry.
     If multiple AIs contributed, list each one.
     If no AI was involved, write: "- No AI assistance"
  4. Do not modify existing entries.
  5. Add new entries at the top, below this header block.
  6. After every change to this repo, run:
       git add <changed files> && git commit -m "vX.Y.Z: description" && git push
     This keeps history clean and allows rollback to any previous state.
  7. Before every commit, check for leftover fix_*.py scripts and delete them:
       ls /home/pi/buell/fix_*.py && rm /home/pi/buell/fix_*.py
     Never commit fix_*.py files to the repo — they are temporary patch scripts.
PROMPT_END -->

## [v2.6.49] — 2026-05-30

### Changed

- web/templates/index.html: .hs cells now bottom-aligned (justify-content:flex-end) — all header values share the same visual baseline regardless of content size

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.48] — 2026-05-30

### Changed

- web/templates/index.html: .hs-label now absolutely positioned (5px, top-left overlay) — value takes full cell height, font-size 28px -> 36px with same row height
- web/static/app.js: VE grid Load column (10-255) moved from left side to right side of the grid

### Fixed

- web/static/app.js: buildCobertGrid had incorrect closing brace placement during grid restructure — corrected

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.47] — 2026-05-30

### Changed

- web/templates/index.html: big cards — removed CHT/KPH/TPS/RPM title labels and bottom unit text; units now shown inline to the right of the value (°C, km/h, %, rpm) saving vertical space
- web/templates/index.html: big-card padding reduced 8px -> 5px to further reduce header height
- web/templates/index.html: TPS degrees sub-display simplified, removed "grados" text label

### Fixed

- web/static/app.js: bigRPM element was never updated — RPM card always showed "--". Added missing update: Math.round(lv.RPM)
- web/static/app.js: TPS value no longer includes "%" suffix (moved to inline HTML unit span)

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.46] — 2026-05-30

### Changed

- web/templates/index.html: big-display changed from flex row to 2x2 CSS grid — each card now ~190px wide on iPhone 12 instead of ~90px, allowing 72px numbers to render correctly

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.45] — 2026-05-30

### Changed

- web/templates/index.html: big-num font size increased 56px -> 72px for better readability on iPhone 12
- web/templates/index.html: flavor mode buttons (Segundos/EGO/SWEET/TIPOUT/Confianza/O2 ADC/WOT) moved from above the VE grid to below it — they are not changed during a ride so they don't need to be prominent
- web/templates/index.html: removed "Celdas" section label — no informational value

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.44] — 2026-05-30

### Fixed

- main.py: GPS watchdog now calls gps.stop() before replacing the dead thread — prevents two GPSReader threads running simultaneously
- main.py: _ecu_thread.join(timeout=5s) added before shutdown() — eliminates race condition where both _ecu_loop and shutdown() tried to close the active ride simultaneously
- web/server.py: _get_live() called cell_tracker.snapshot() twice per request — now called once and stored in _snap, halves lock acquisitions on the cell tracker

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.43] — 2026-05-30

### Removed

- web/templates/index.html: ERR indicator removed from live tab header — not useful in daily use
- web/static/app.js: hErr JS block removed (ride_errors display logic)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.42] — 2026-05-30

### Fixed

- ecu/connection.py: usb_power_cycle() and usb_reset() now use with open() — eliminates leaked file handles on USB recovery paths (Bug P2 from BACKLOG)
- web/server.py: CSV multi-part download skipped only 1 line per part instead of 2 (comment + header), causing duplicate headers in concatenated output — now skips both lines for parts 2+
- web/static/app.js: downloadEeprom() and downloadMsq() now use URL.createObjectURL(blob) + revokeObjectURL — fixes download on mobile browsers
- web/templates/sessions_vs.html: download() rewritten with fetch + blob instead of bare anchor click — consistent with app.js approach

### Removed

- web/server.py: TIPIN removed from COVERAGE_TARGETS_DEFAULT, _set_coverage_targets validation set, and _get_coverage() flavor loop — TIPIN is not actionable for VE tuning (AE active during tip-in, map does not govern fuel)
- web/templates/index.html: TIPIN button removed from coverage grid

### AI
- Claude Sonnet 4.6, Anthropic




## [v2.6.41] — 2026-05-27

### Fixed

- **web/server.py: Path traversal vulnerability in _handle_static** (#12): `lstrip("/")` + `os.path.join` allowed `../` traversal to read arbitrary files outside the web root. Replaced `fpath.startswith(base)` with `os.path.commonpath([base, fpath]) == base` — the robust Python approach that correctly resolves both `../` traversal and prefix-matching attacks.

- **Bug #9: `_get_version()` reads CHANGELOG.md every call** — `LOGGER_VERSION = _get_version()` was moved to module level so the file is read only once at import time. Also fixed parsing to skip HTML comment blocks (PROMPT_START/PROMPT_END).

## [v2.6.40] — 2026-05-27

### Fixed

- main.py: _check_threads string literals missing quotes (ecu-rt, sysmon) causing NameError in thread watchdog - dead threads would never be restarted
- ecu/session.py: _update_tuning_report used leaked outer-loop variable v instead of agg dict a for o2_adc_avg calculation - caused KeyError and corrupted tuning reports
- ecu/session.py: _rebuild_summary cell default dict missing o2_adc_sum key - caused KeyError when recovering orphan rides

### AI

- Codebuff (DeepSeek V4 Flash) - bug analysis and fixes

## [v2.6.39] — 2026-05-26
### Fixed
- web/server.py: add JSON type validation to _handle_coverage_targets — reject non-dict payloads with clear error message
- network/manager.py: add threading.Lock to NetworkManager for _save_state and load_state (prevents network_state.json corruption on concurrent WiFi/hotspot switches)
- web/server.py: _handle_static FD leak incidentally fixed in v2.6.38 (with open)
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.38] — 2026-05-26
### Fixed
- web/server.py: fix path traversal in _handle_static — sanitize with os.path.realpath() + startswith(base) guard (also fixes FD leak with `with open`)
- main.py: add _check_threads() watchdog — restart dead ecu-rt/sysmon daemon threads from heartbeat loop
- web/server.py + main.py: add threading.RLock (_data_lock) for serial_stats read-modify-write and ecu_live writes
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.37] — 2026-05-26
### Fixed
- ecu/session.py: fix variable scope bug in _rebuild_summary — a["o2_adc_sum"] → v["o2_adc_sum"] (NameError when recovering orphaned rides)
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.36] - 2026-05-26

### Fixed
- Bug #7: Added _validate_eeprom() sanity checks (KMFG_Year, KMFG_Day, Ride_Counter, KEngineRun, spark_load axis ranges) — corrupted EEPROM dumps now return empty dicts with warning log instead of silently decoding garbage

## [v2.6.35] - 2026-05-26

### Fixed
- Bug #6: Added 5-second cooldown to FIFO flush with getattr/monotonic — prevents rapid repeated buffer flushes when serial port is erratic
- Optimized: Inlined time.monotonic() calls and replaced hasattr with getattr for cleaner cooldown check

## [v2.6.34] - 2026-05-26

### Fixed
- Bug #8: Added (total_valid_s or 0) guard in quality_ratio calculation — prevents TypeError when total_valid_s is None due to data corruption

## [v2.6.33] - 2026-05-26

### Fixed
- Bug #5: Added self.logger.debug() to 4 silent except blocks in session.py (tuning report, eeprom_decoded, MSQ gen, cell aggregation) — no behavior change, just visibility

## [v2.6.32] - 2026-05-26

### Fixed
- Bug #4: Replaced time.time() with time.monotonic() in connection.py and ecu/connection.py (12 occurrences) — prevents infinite timeout loops when system clock jumps due to NTP/DST
- Left main.py time.time() calls unchanged (data timestamps and logging interval need wall-clock time)

## [v2.6.31] - 2026-05-26

### Fixed
- Bug #3: Heartbeat loop now wrapped in try/except — thread won't die silently
- Fixed indentation in _sysmon_loop and _ecu_loop caused by collateral from sed (removed duplicate/empty `try:` lines)

## [v2.6.30] - 2026-05-26

### Fixed
- **Bug #1 — `o2_adc_avg` variable scope:** Fixed NameError in `_update_tuning_report` (`ecu/session.py:341`). Changed `v["o2_adc_sum"]` to `a["o2_adc_sum"]` — `v` was from an outer loop scope while all other fields correctly used the aggregated dict `a`.

## [v2.6.28] - 2026-05-26
### Added
- web/templates/index.html + web/static/app.js: error log viewer modal — el badge ⚠️ ahora es clickeable y abre un modal con resumen de errores (tabla de conteos por tipo) y lista cronológica de eventos con contexto del motor (RPM, CLT, TPS, VSS, BATT) para cada error
### AI
- Implemented error log viewer feature: clickable errBadge in ride list opens modal fetching /errorlog/{ride_num} and renders summary table + event timeline with ctx

### Fixed
- Bug: session-mismatch en /errorlog/ — endpoint buscaba solo por ride_num, devolviendo datos de sesión incorrecta cuando existían rides con el mismo número en distintas sesiones. Se agregó session al path (/errorlog/<session>/<ride_num>).
- Bug: _get_rides() no poblaba has_errorlog/errorlog_events — backend no enviaba los campos que el frontend ya esperaba para mostrar el badge ⚠️.
- Bug: modal mostraba "No se encontraron eventos" — frontend checkeaba !d.has_errorlog pero el endpoint devuelve el JSON crudo sin ese campo. Se eliminó la condición redundante.
- Bug: errBadge no era clickeable (backfill) — se agregó onclick con openErrorLog(sk, ride_num).
## [v2.6.29] - 2026-05-26

### Added
- Pagina dedicada /errorlog/viz con visor grafico de error logs.
  - Selectores de sesion y ride con filtro por tipo de evento.
  - Stats en vivo: total eventos, timeouts, reconnects, tiempo perdido, % afectado.
  - Timeline canvas: linea RPM + barras de timeout con altura proporcional a lost_s.
  - Scatter plots (Canvas nativo): RPM x CLT coloreado por lost_s y BATT x lost_s.
  - Barras de distribucion por tipo de evento.
  - Lista de eventos filtrable con contexto completo del motor.
- Nav-tab "Errores" en index.html apuntando a /errorlog/viz.
- Ruta /errorlog/viz en server.py con handler _handle_errorlog_viz.

### Fixed
- La ruta /errorlog/viz se antepone al prefix /errorlog/ para evitar conflicto.

## [v2.6.27] - 2026-05-26
### Added
- ANL6: added valid_for_tuning flag to ride summary JSON
- ANL7: added health_score (0-100) to ride summary JSON
- ANL12: added /tuning_report HTTP endpoint
- ANL13: added format=csv option to /tuning_report
- ANL3: added format=csv option to /coverage.json
- ANL2: added O2_ADC real-time overlay to the cobertura heatmap (frontend + backend - o2_adc_avg per cell)
- ANL1: added confidence overlay mode (Confianza) to the cobertura heatmap (frontend) — exports per-cell VE coverage data with flavor progress
### Removed
- archive/: deleted unused legacy code
- BACKLOG.md: removed completed REFACTOR items and empty ARCHIVO section
- BACKLOG_ANL.md: removed completed BACKLOG-ANL4
### Changed
- main.py: replaced magic sleep values with named constants
### Fixed
- web/server.py: replaced bare except: blocks with specific handlers + logging
### AI
- DeepSeek V4 Flash

## [v2.6.27] - 2026-05-26
### Fixed
- web/static/app.js: added missing `confColor()` function — was nested inside `pctColor()`, breaking JS execution before `fetchLive()` could display version
- web/static/app.js: cleaned corrupted `renderCobertLegend()` — had grid code (variables `c`, `populated`, `bg`) mistakenly inserted between legend blocks
- web/static/app.js: added missing `confidence` and `o2_adc` mode cases to `renderCobertGrid()` — were accidentally omitted when confidence/o2_adc overlays were added
- web/server.py: moved `_handle_tuning_report()` out of `_compare_sessions()` — was defined inside `_compare_sessions()` after `return`, making it unreachable dead code; caused `AttributeError: DashboardHandler object has no attribute _handle_tuning_report` on every request
- web/server.py: fixed indentation of `/tuning_report` route entry in routes dict (was missing leading whitespace)
- web/server.py: split inline dict entry — `"confidence"` and `"o2_adc_avg"` on separate lines (cosmetic)
- ecu/session.py: added missing `n=v["count"]; vn=v["valid_count"]` in `_rebuild_summary()` — variables were deleted but dict still referenced them; caused `NameError` in `power_loss_recovered` recovery path
- web/templates/index.html: added `--LOGGER_VERSION--` placeholder inside `hdrVersion` span so version renders statically from server (no longer depends solely on JS fetchLive)
### AI
- DeepSeek V4 Flash
## [v2.6.26] — 2026-05-24
### Changed
- web/templates/index.html: moved version display from config subtab to header, next to BUELL LOGGER.
- web/static/app.js: updated to target hdrVersion element in header.
### AI
- DeepSeek V4 Flash

## [v2.6.25] — 2026-05-24
### Fixed
- ecu/protocol.py: ZeroDivisionError in VSS_RPM_Ratio calculation when RPM=0. Added guard clause to avoid division by zero when engine is off.
### AI
- DeepSeek V4 Flash


> All entries must be written in English.
> Each entry must include an ### AI section crediting the AI(s) that contributed.

## [v2.6.24] — 2026-05-24
### Fixed
- web/server.py: _handle_post_network() was missing `net = self.server_instance.network`
  causing a NameError when the hotspot button was pressed — hotspot/wifi switch now works.
- gps/reader.py: satellite count now reads gpsd `uSat` field directly; falls back to
  counting satellites[] array — fixes SAT=0 in dashboard header.
- web/server.py: GPS fix data merged into live.json `live{}` at all times regardless
  of ECU connection state.
- web/server.py: _get_version() now skips HTML comment block in CHANGELOG.md before
  searching for version string — fixes dashboard showing "vX.Y.Z".
### Changed
- CHANGELOG.md: added PROMPT_START/PROMPT_END markers and instructions #6 and #7
  requiring git commit+push after every change and cleanup of fix_*.py before commit.
- Removed stale fix_*.py scripts from working directory.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.23] — 2026-05-24
### Changed
- CHANGELOG.md: added PROMPT_START/PROMPT_END markers to instruction block so AI
  assistants know to read all instructions before acting, even when only a partial
  view of the file is available (e.g. head -5).
- CHANGELOG.md: added instruction #6 requiring git add + commit + push after every
  change to keep history clean and enable rollback to any previous state.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.22] — 2026-05-24
### Fixed
- web/server.py: _get_version() now skips the HTML comment block in CHANGELOG.md
  before searching for the version — previously the regex matched the example
  entry inside the instructions comment, returning "vX.Y.Z" instead of the
  actual version.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.21] — 2026-05-24
### Fixed
- gps/reader.py: satellite count now reads gpsd `uSat` field directly instead of
  counting `satellites[]` array entries — fixes persistent SAT=0 in dashboard header
  when gpsd sends SKY messages without the full satellite list.
- web/server.py: GPS fix data (lat, lon, alt, speed, heading, satellites, valid)
  now merged into live.json `live{}` payload at all times, regardless of ECU
  connection state — previously GPS fields were absent when ECU was disconnected.
- web/static/app.js: dashboard SAT field now correctly reflects live satellite count.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.20] — 2026-05-24
### Changed
- web/server.py: refactored monolithic do_GET (~26 routes) and do_POST (~12 routes)
  into named _handle_* methods with clean dict-based dispatchers.
  Each route block keeps its exact original logic — zero behavioral changes.
- do_GET: dict dispatcher for exact matches + if/elif chain for prefix routes
  (static, csv, ride, errorlog, wifi/redirect_url).
- do_POST: dict dispatcher dispatching to _handle_post_* methods.

## [v2.6.20] — 2026-05-24
### Changed
- web/server.py: refactored monolithic do_GET (~26 routes) and do_POST (~12 routes)
  into named _handle_* methods with clean dict-based dispatchers.
  Each handler preserves exact original logic — zero behavioral changes.
- do_GET: dict dispatcher for exact matches + if/elif chain for prefix routes
  (static, csv, ride, errorlog, wifi/redirect_url).
- do_POST: dict dispatcher dispatching to _handle_post_* methods.
- Each GET handler receives `path` as argument and resolves `net` internally
  to fix NameError scope issues when extracting from the enclosing do_GET scope.

## [v2.6.19] — 2026-05-24
### Removed
- web/static/app.js: removed orphaned TPS/VSS calibration functions
  (startTpsCapture, _tpsCaptureActive, init calls loadTpsCal/loadVssCal).
  These were dead code — no backend endpoints existed.
- web/templates/index.html: removed Calibracion TPS and Calibracion Velocidad
  UI sections (orphaned, no backend).
### Changed
- CHANGELOG.md: added "All entries must be written in English" header.

## [v2.6.18] — 2026-05-24
### Fixed
- web/static/app.js: bug del menú hamburguesa — el archivo contenía etiquetas
  `<script>` y `</script>` del HTML original (error de extracción con sed).
  Al cargarse como JS externo, `<script>` causaba SyntaxError y ninguna
  función (incluyendo showTab) se definía. Solución: remover las etiquetas
  del principio y final del archivo.

## [v2.6.17] — 2026-05-24
### Changed
- web/: JS separado de templates/index.html a static/app.js (~2100 líneas inline
  a archivo externo). Agregado ruteo /static/ en server.py con soporte MIME.
- web/templates/index.html: reducido de 2846 a 685 líneas. El JS se carga vía
  <script src=/static/app.js> con window.LOGGER_VERSION inline.

## [v2.6.16] — 2026-05-24
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG.md: Launch Event como prerequisito de FASE 1 (Merge RAW de mapas).
  Detecta crucero estable ≥3s → WOT para etiquetar pulls válidos.

## [v2.6.15] — 2026-05-24
### Changed
- ARCHITECTURE.md: limpieza de datos de runtime en file tree — eliminados
  network_state.json, objectives.json, backups (.bak/.save). Agregada nota
  de exclusión en el header del árbol y advertencia ⚠️ en la sección "Archivos
  de datos (runtime)".

## [v2.6.14] — 2026-05-24
### Fixed
- ecu/protocol.py: crash al iniciar el servicio — `NameError: name "CENTERS" is
  not defined` en GearFilter. Causa: list comprehension dentro de la clase no
  podía acceder a otra variable de clase (Python 3 scoping). Solución: mover
  CENTERS y THRESHOLDS a nivel módulo.

## [v2.6.13] — 2026-05-24
### Changed
- ecu/protocol.py: gear detection migrada a ventana deslizante estadística.
  - Nuevo GearFilter con ratio RPM/KPH (invertido vs VSS_RPM_Ratio)
    para mayor separación entre marchas.
  - Cliff detector: detecta cambios bruscos en ~0.5s (vs ~1s antes).
  - Outlier filter + stability check via desviación estándar.
  - Centros calibrados empíricamente: [75.5, 53.8, 40.1, 33.3, 28.7].
  - VSS_RPM_Ratio en CSV se mantiene sin cambios.
- Eliminadas constantes viejas: GEAR_KPH_PER_KRPM, GEAR_THRESHOLDS,
  _gear_buffer, _rpm_buffer, _kph_buffer.

# Buell XB12X Logger — Changelog

> **Language policy:** All code, comments, variable names, and documentation
> must be written in English. Spanish is only acceptable for UI strings
> displayed to the end-user in the web dashboard.

## [v2.6.12] — 2026-05-24
### Changed
- ecu/protocol.py: agregados type hints (GearFilter, decode_rt_packet, constantes).
- ecu/connection.py: agregados type hints (DDFI2Connection, build_pdu, helpers).

## [v2.6.11] — 2026-05-24
### Fixed
- main.py: eliminada llamada duplicada a `recover_orphan_rides()`.

## [v2.6.10] — 2026-05-23
### Changed
- tools/make_index.py y tools/recover_summaries.py → archive/ (scripts one-shot,
  mantenidos como referencia).
- ARCHITECTURE.md: header actualizado con nota de archivado, file tree refleja
  nuevas rutas.
- BACKLOG.md: eliminado item P3 completado + agregado item P2 para revisar
  lógica de ARCHITECTURE.md (ignorar datos de runtime).

## [v2.6.9] — 2026-05-23
### Changed
- ecu/connection.py: todos los open() ahora usan with open() (7 bloques).
  Elimina file handles colgados en usb_power_cycle, usb_reset y usb_reset reads sysfs.
- BACKLOG.md: marcado P2 completado.

## [v2.6.8] — 2026-05-23
### Changed
- ecu/protocol.py: gear detection — ring buffers envueltos en clase GearFilter.
  Elimina estado mutable a nivel modulo, permite testeo independiente
  y uso de instancias aisladas.
- BACKLOG.md: marcado P2 completado.

## [v2.6.7] — 2026-05-23
### Changed
- ddfi2_logger.py movido a archive/ (código muerto, modularizado hace tiempo)
- connection.py importa constantes de protocol.py (SOH, EOH, ACK, etc.) en vez de redefinirlas
- protocol.py: nueva fuente única de verdad para constantes de protocolo DDFI2

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG.md: nueva sección REFACTOR / DEUDA TÉCNICA con 10 mejoras identificadas

### Removed
- Temp scripts basura (_update_changelog*.py, _add_speed_axis.py, nul) del raíz

## [v2.6.6] — 2026-05-23
### Changed
- ecu/protocol.py: recalibración VSS_CPKM25 1368 → 1518 (~11% ajuste).
  Alinea velocidad del dash (VS_KPH) con GPS. Derivado de 3,029 períodos
  estables en rides 4-5 de sesión 47BF04.

## [v2.6.5] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- web/templates/index.html (loadMapTrack): perfil de altitud ahora incluye
  linea de velocidad (km/h) como segundo eje Y (derecha) en el chart.
  Coloreada con el mismo gradiente continuo azul-verde-amarillo-rojo-magenta
  del mapa para correlacion visual inmediata.

## [v2.6.4] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- ecu/protocol.py: filtro mediano (20 samples, ~1s) en gear detection.
  Cuando RPM/KPH estan estables (rango RPM < 200, KPH < 8) valida la
  marcha usando la mediana de los ultimos ~1s, corrigiendo outliers.

## [v2.6.3] — 2026-05-23
### Fixed
- main.py _sysmon_loop: merge en vez de overwrite de serial_stats — TTL%/BPS ya no parpadean en el dash
- ecu/protocol.py gear detection: removida histeresis con _gear_prev — la marcha ya no se queda pegada en 5ta.
  Vuelve a detección absoluta (cada sample se evalúa independientemente, como en v2.5.x).

## [v2.6.2] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
-  en : merge de celdas ahora incluye  de los summary JSON
  - Los modos SWEET, TIPIN, TIPOUT, WOT del grid VE ahora funcionan con rides históricos
  - Usa  desde  para calcular porcentaje de cobertura
  - Solo muestra flavors con segundos > 0 (consistente con el live /coverage.json)

## [v2.6.1] — 2026-05-23
### Fixed
-  en : merge de celdas ahora usa fallback a  cuando  (rides de motor frío)
  - El grid VE en Ride tab mostraba vacío para rides con datos grabados durante calentamiento (WUE > 102)
  - Afectaba rides de las sesiones ,  y cualquier ride donde CellTracker marcara datos como inválidos

# CHANGELOG — Buell XB12X DDFI2 Logger
> Raspberry Pi Zero 2W · CH343P · Python 3 · 9600,8N1
> Repository: https://github.com/pacdavid1/buell-xb12x-logger
---
## [v2.6.0] — 2026-05-21
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `GPSReader.is_alive()` — método público que encapsula acceso a `_thread` (reemplaza `self.gps._thread.is_alive()` en `main.py`)
- `pollCobertGrid()` en frontend — polling en tiempo real desde `/coverage.json` para el grid de cobertura VE

### Changed
- Grid de pane Ride reemplazado por grid de cobertura VE con 6 modos visuales: Segundos, EGO, SWEET, TIPIN, TIPOUT, WOT — con leyenda dinámica, coloreado por porcentaje y chips de resumen por flavor
- Leyenda del mapa GPS actualizada a 5 stops consistentes con `getGradientColor()` (azul→verde→amarillo→naranja→magenta)
- `getSpeedColor()` eliminada — mapa y perfil de altitud ahora usan `getGradientColor()` unificado

### Fixed
- `web/server.py`: imports perezosos (`csv`, `zlib`, `logging`, `json`, `urllib.parse`) movidos al inicio del archivo — elimina 8 imports redundantes dentro de métodos
- `web/server.py`: bare `except:` cambiado a `except Exception:` (2 instancias)
- `web/server.py`: path hardcodeado `/home/pi/buell/sessions` en `/gps_track` reemplazado por `Path(self.server_instance.buell_dir) / 'sessions'`
- `web/server.py`: fetch duplicado de GPS en `_get_live_data()` eliminado — los datos GPS ya se inyectan en el ECU loop (`main.py:356`)
- `gps/reader.py`: bare `except: continue` cambiado a `except Exception as e: logger.debug(...); continue`
- `main.py`: acceso a `self.gps._thread.is_alive()` reemplazado por `self.gps.is_alive()`

### Removed
- `web/templates/cobertura.html` — eliminado, funcionalidad integrada en pane Ride de `index.html`
- Ruta `/cobertura` en `web/server.py`
---

## [v2.5.50] — 2026-04-27
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- GPS via gpsd — reemplaza pyserial directo, manejo profesional del M8N
- Endpoint /gps_fix para monitorear GPS sin ECU conectada
- GPS satellites visible en header del dash (SAT)
- SBAS habilitado para mejor accuracy
- gpsd como dependencia systemd de buell-logger
### Fixed
- GPS CFG-PRT antes de CFG-RATE — habilita protocolo UBX, ACK confirmado
- GPS 5Hz guardado en flash del M8N — persiste entre reinicios
- GPS parse no guarda speed/pos cuando gps_valid=False
- GPS satellites no se resetea a 0 con SKY vacío de gpsd
- GPS siempre presente en live.json via _get_live_data aunque no haya ECU
- GPS inject removido de sysmon — lo maneja _get_live_data en server.py
---
## [v2.5.49] — 2026-04-19
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Altitude profile chart (Chart.js) below Leaflet map, colored by speed
- GPS confirmed at 5Hz (UBX CFG-RATE 200ms persisted in module flash)
### Fixed
- GPS ttyS0 permission via sudoers + ExecStartPre in systemd service
- Map dark mode (CARTO night tiles)
- Speed gradient colors fixed scale on map polyline

## [v2.5.48] — 2026-04-18
### Fixed
- session_metadata.json corruption caused JSONDecodeError on boot — manual fix applied to 3311B1
- start_ride() RuntimeError no longer kills ECU thread — now caught and logged as warning
- Race condition: start_ride() attempted before open_session() completed after motor voltage drop
- GPS reader: keeps last known position when fix is lost (gps_valid=False but lat/lon retained)
- /gps_track endpoint: includes all points with non-null lat/lon regardless of gps_valid flag
- except Exception in run() now logs full traceback for easier debugging
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG-INF1: session_metadata.json corruption guard (queued)

## [v2.5.47] — 2026-04-18
### Fixed
- shutdown() ahora cierra el ride activo limpiamente antes de detener servicios
- Rides huérfanos (sin summary JSON) ya no se pierden en apagados abruptos
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- tools/recover_summaries.py — recupera summaries JSON de rides huérfanos leyendo CSV
- 31 summaries recuperados de sesiones anteriores
### Changed
- Tab Mapa: selector de rides ordenado por fecha descendente (Date object sort)

## [v2.5.46] — 2026-04-18
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Tab "Mapa" en dashboard con Leaflet.js (OpenStreetMap, sin API key)
- Endpoint `/gps_track?session=X&ride=N` — lee CSV y devuelve puntos GPS válidos
- Mapa de ruta con polyline coloreada por velocidad (verde=lento, rojo=rápido)
- Marcadores de inicio (verde) y fin (rojo) en la ruta
- Selector de rides en el tab Mapa
- Info bar: cantidad de puntos, velocidad máxima, distancia aproximada
### Changed
- `showTab()` extendido para incluir 'map'

## [v2.5.45] — 2026-04-18
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- GPS integration: NEO-M8N connected via UART (ttyS0, pins 8/10, 9600 baud)
- `gps/reader.py`: GPSReader thread — parses $GNRMC and $GNGGA, thread-safe get_fix()
- `gps/__init__.py`: module init
- CSV columns: gps_lat, gps_lon, gps_alt_m, gps_speed_kmh, gps_heading, gps_satellites, gps_valid
- GPS data injected per sample in main.py RT loop alongside ECU data
### Changed
- `ecu/protocol.py`: CSV_COLUMNS extended with 7 GPS fields
- `main.py`: GPSReader instantiated, started with other threads, fix injected before write_sample
- Disabled serial-getty@ttyS0 (was blocking UART port)
- Added udev rule 99-ttyS0-gps.rules (MODE=0666)


## [v2.5.44] — 2026-04-11
### Fixed
- Tooltip "aplastado": eliminado fondo transparente, ajustado padding y tamaños de fuente
- Gráficas borrosas/distorsionadas: corregido aspect ratio eliminando `!important` en CSS canvas
- Líneas de gráfica más nítidas: `borderWidth` 2.5, `tension` 0 (líneas rectas)

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Panel lateral de datos ("DATOS CURSOR"): visualización fija de RPM, KPH, CLT al mover cursor
- Plugin crosshair Chart.js: línea vertical punteada que sigue el cursor en tiempo real
- Tooltip external: sistema personalizado que alimenta el panel lateral sin interferir visualmente
- Offset configurable: tooltip separado 15px del punto de datos para no estorbar

### Changed
- Alineación de tooltip: ahora aparece a la izquierda del cursor (`xAlign: left`)
- Fondo de tooltip: completamente transparente para ver solo los números

### Technical
- Registro global de plugin Chart.js para crosshair sincronizado
- Implementación de callback `external` en tooltip para desacoplar visualización de datos

> Co-authored-by: Kimi (Moonshot AI) <kimi@moonshot.cn>

---

## [v2.5.44] — 2026-04-11
### Fixed
- Tooltip "aplastado": eliminado fondo transparente, ajustado padding y tamaños de fuente
- Gráficas borrosas/distorsionadas: corregido aspect ratio eliminando `!important` en CSS canvas
- Líneas de gráfica más nítidas: `borderWidth` 2.5, `tension` 0 (líneas rectas)

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Panel lateral de datos ("DATOS CURSOR"): visualización fija de RPM, KPH, CLT al mover cursor
- Plugin crosshair Chart.js: línea vertical punteada que sigue el cursor en tiempo real
- Tooltip external: sistema personalizado que alimenta el panel lateral sin interferir visualmente
- Offset configurable: tooltip separado 15px del punto de datos para no estorbar

### Changed
- Alineación de tooltip: ahora aparece a la izquierda del cursor (`xAlign: left`)
- Fondo de tooltip: completamente transparente para ver solo los números

### Technical
- Registro global de plugin Chart.js para crosshair sincronizado
- Implementación de callback `external` en tooltip para desacoplar visualización de datos

---
## [v2.5.43] — 2026-04-11
### Fixed
- Live grid now updates in real-time even when viewing a historical ride
- `fetchLive()`: if `_viewingHistory=true` but a ride is active, grid and header still refresh at 500ms
- Previously the grid froze as soon as a saved ride was selected for viewing

### Notes
- Co-authored-by: Claude (Anthropic)

## [v2.5.42] — 2026-04-11
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `WebServer.ecu_identity`: new field exposing resolved ECU metadata (name, dbfile, ddfi, remark)
- `main.py`: populates `ecu_identity` via `resolve_ecu()` at all 3 EEPROM load sites (startup, reconnect, cached fallback)
- `live.json`: includes `ecu_identity` alongside `bike_serial`
- Startup log now shows ECU name and DDFI variant on EEPROM ready
### Changed
- `fix_charts_sync.py`: removed (changes already applied to index.html in prior session)
- `.gitignore`: exclude `*.bak*` template backups
### Notes
- Co-diagnosed: Claude (Anthropic)

## [v2.5.41] — 2026-04-09
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `SessionManager._generate_suggested_msq()`: genera MSQ con sugerencias aplicadas automáticamente al cerrar cada ride
- MSQ toma EEPROM actual como base y aplica factor de corrección solo a celdas con suggestion
- Safety limits: VE entre 10-250, máximo 5% de cambio por iteración
- Endpoint `GET /suggested_msq`: descarga el MSQ sugerido de la sesión activa
- MSQ guardado en `sessions/CHECKSUM/suggested_CHECKSUM.msq`
### Notes
- Solo modifica fuel_front por ahora — fuel_rear y spark se copian sin cambios
- MSQ compatible con EcmSpy — misma estructura que Custom_DDFI2_Map.msq
- Co-diagnosed: Claude (Anthropic)

## [v2.5.40] — 2026-04-06
### Changed
- `CellTracker.update()`: distribución bilineal entre 4 celdas vecinas (antes 100% a una celda)
- `CellTracker._bilinear_weights()`: pesos bilineales consistentes con interpolación del ECU
- `CellTracker._empty_cell()`: inicialización centralizada incluyendo `ego_iir`
- `CellTracker.HARDNESS = 0.3`: parámetro configurable de velocidad de aprendizaje IIR
- `snapshot()`: incluye `ego_iir` (estimado IIR adaptivo) por celda
### Notes
- count/valid_count ahora son sumas de pesos flotantes — consistente con distribución bilineal
- Co-diagnosed: Claude (Anthropic)

## [v2.5.39] — 2026-04-06
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `eeprom_decoded.json`: generado desde eeprom.bin (35 params, 4 mapas VE/spark)
- `SessionManager._update_tuning_report()`: incluye eeprom_decoded en tuning_report
### Notes
- tuning_report ahora contiene mapa VE actual + sugerencias en un solo JSON
- Co-diagnosed: Claude (Anthropic)

## [v2.5.38] — 2026-04-06
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `CellTracker`: filtros de validez por sample (WUE, CLT, RPM, AFV, decel, fuel_cut, TPS_delta)
- `CellTracker`: acumuladores de calidad por celda (valid_seconds, valid_ego_avg, confidence, clt_avg, wue_avg, afv_avg, inv_reasons)
- `CellTracker._is_valid()`: retorna (bool, reason) para clasificar cada sample
- `SessionManager._update_tuning_report()`: genera/actualiza tuning_report_CHECKSUM.json al cerrar cada ride
- `analyze_session.py`: script standalone para agregar todos los CSVs de una sesión con filtros de validez
- `BACKLOG_ANL.md`: backlog dedicado al pipeline de análisis y tuning
- `tempColor(c)`: función JS de interpolación azul→blanco→rojo por temperatura °C
### Changed
- Big CHT en dashboard: color dinámico via tempColor() en lugar de clases CSS fijas
- Chart CLT: borderColor y eje Y3 usan tempColor(cltMax) del ride
- Labels CLT°F → CLT°C en chart y eje
- Límite de referencia en chart: 250°F → 235°C (umbral crítico XB)
### Notes
- tuning_report solo procesa rides con formato nuevo (valid_seconds en cells) — rides anteriores ignorados
- Co-diagnosed: Claude (Anthropic)

## [v2.5.37] — 2026-04-04
### Changed
- reading_loop reconnect simplificado: va directo a `usb_power_cycle()` a los 10s sin escalación.
- `usb_power_cycle()` timing reducido: 1s suspend + 2s resume (antes 2s+3s).
### Notes
- Elimina la lógica de escalación DTR→usb_reset→power_cycle que tenía bugs de timing.
- Pendiente confirmar recuperación tras killswitch cycles con moto real.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.36] — 2026-04-04
### Changed
- `usb_reset()` in `ecu/connection.py` now detects both FT232RL (`0403:6001`) and CH343P (`1a86:55d3`).
- reading_loop reconnect escalation synced with waiting_loop: 10s hard reconnect, 20s usb_reset, 30s power_cycle.
- `usb_power_cycle()` added to reading_loop escalation — previously only ran in waiting_loop.
### Notes
- LOG6 partially addressed — escalation now aggressive enough to recover hung adapter without reboot.
- Requires moto test to confirm full recovery after multiple killswitch cycles.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.35] — 2026-04-04
### Changed
- `decode_eeprom_params()` hardcode replaced by `decode_params_compat()` from `ecu/eeprom_params.py`.
- Both startup and reconnect flows now pass `version` string to `resolve_ecu()` via `version_resolver.py`.
- Correct XML selected automatically from `ecu_defs/files.xml` (exact match + alpha prefix fallback).
### Notes
- `BUEIB_PARAMS` dict remains in `ecu/eeprom.py` but is no longer used for parameter decoding.
- Closes BACKLOG-ECU1. Both motos (red #651, blue #235) now resolve their own XML at connect time.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.34] — 2026-04-02
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `usb_power_cycle()` method in `ecu/connection.py` — recovers dwc2 IRQ crash via sysfs autosuspend without reboot.
- Watchdog now triggers USB power cycle at 15s without ECU, USB reset at 30s.
### Changed
- Previous USB reset threshold was 60s — too slow for real-world reconnection.
### Notes
- Root cause: FT232RL + dwc2 (Pi Zero 2W) incompatibility causes `error -71` and `Disabling IRQ #51`.
- Power cycle via `/sys/bus/usb/devices/usb1/power/level` suspend/on recovers the controller without reboot.
- CH343P (isolated) confirmed as more stable alternative for permanent moto installation.
- Co-authored: Claude (Anthropic) — 2026-04-02

---

## [v2.5.33] — 2026-04-02
### Changed
- EEPROM is now always read on ECU connect, regardless of whether a session is already active.
- Enables automatic bike identity detection via checksum — switching logger between bikes (e.g. red #651 → blue #235) now creates correct session without restarting.
### Notes
- Previously EEPROM was only read when `current_checksum is None` — bike swap was invisible to the logger.
- `open_session()` already handled checksum change detection — fix was removing the guard condition.
- Co-authored: Claude (Anthropic) — 2026-04-02

---

## [v2.5.32] — 2026-04-01
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- udev rule `/etc/udev/rules.d/99-ecu-serial.rules` — auto-detects FT232RL (0403:6001) and CH343P (1a86:55d3), both symlinked to `/dev/ttyECU`.
- `ftdi_sio` driver added to `/etc/modules-load.d/ftdi.conf` for automatic load on boot.
- Service and install.sh updated to use `/dev/ttyECU` — adapter-agnostic, no code changes needed when switching TTL adapters.
- `@reboot dmesg -C` added to root crontab — clears kernel buffer on boot to prevent dwc2 USB controller IRQ crash after hot-swap.
### Notes
- CH343P (isolated) validated as drop-in replacement for FT232RL.
- Co-diagnosed: Claude (Anthropic) — 2026-04-01


---

## [v2.5.31] — 2026-04-01
### Fixed
- USB host mode not working on Pi Zero 2W after OS update.
- `dtoverlay=dwc2,dr_mode=host` was scoped under `[cm5]` in `/boot/firmware/config.txt` instead of `[all]`, causing FT232RL to never be detected by the kernel.
- Moved overlay to `[all]` section — FT232RL now enumerates correctly as `ttyUSB0` on boot.
### Notes
- Fix applied to `/boot/firmware/config.txt` (outside repo — system-level config).
- Diagnosed via `dmesg` and `lsusb`: kernel was attempting USB enumeration but failing with `error -71`.
- Co-diagnosed: Claude (Anthropic) — 2026-04-01


---

## [v2.5.30] — 2026-03-28
### Fixed
- Corrected Spark (Ignition Advance) EEPROM map decoding.
- Spark maps are now decoded as dense 10×10 rectangular grids instead of triangular VE-style layouts.
- Zero values in Spark maps are treated as valid data, not structural separators.
- Spark RPM axis handling corrected independently of VE axis logic.

### Verified
- Spark Front / Rear heatmaps now display correct rectangular geometry.
- Values are coherent across RPM/TPS with no diagonal padding artifacts.
- Runtime validated against EEPROM: Spark Advance visible and consistent.

---

## [v2.5.29] — 2026-03-28
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Deterministic ECU variant resolution using `ecu_defs/files.xml`.
- New ECU version resolver maps `get_version()` strings (e.g. `BUEIB310`) to the correct EEPROM XML definition via `dbfile`.

### Changed
- EEPROM parameter decoding no longer relies on heuristic prefix matching.
- XML selection for EEPROM decoding is now aligned with EcmSpy behavior.

### Verified
- BUEIB310 / B2RIB / BUEIC variants correctly resolve to `BUEIB.xml`.
- Runtime confirmed: `Decoded 173 params from BUEIB.xml`.

---

## [v2.3.1] — 2026-03-21
**DASHBOARD COMPLETO — SESIONES, CSV Y GRÁFICAS**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **Endpoint `/rides`** (`web/server.py`) — lista rides desde summaries JSON.
  Fallback para rides sin summary (ride activo o sin cerrar).

* **Endpoint `/csv/`** (`web/server.py`) — sirve CSV del ride con soporte
  gzip automático. Concatena partes si el ride tiene múltiples archivos.

* **Endpoint `/ride/`** (`web/server.py`) — retorna summary JSON del ride
  con cells y objectives para el tab Ver.

* **`_get_rides()`** en `WebServer` — método que lista rides desde el
  filesystem sin leer CSVs completos.

### Result

Dashboard 100% funcional en modo modular: datos live ECU, mapas EEPROM,
sesiones grabadas, gráficas de rides visibles.

---

## [v2.3.0] — 2026-03-20
**EEPROM MODULAR — MAPAS VE Y SPARK EN DASHBOARD**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`ecu/eeprom.py`** — `BUEIB_PARAMS` (35 parámetros), `decode_eeprom_params()`
  y `decode_eeprom_maps()` extraídos del monolito. Módulo independiente y testeable.

* **Lectura EEPROM al arrancar** (`main.py`) — después de `get_version()` exitoso,
  se leen las 6 páginas BUEIB (1206 bytes) y se decodifican los 4 mapas:
  Fuel Front/Rear (12×13) y Spark Front/Rear (10×10). Tiempo de lectura ~3s.

* **Endpoints `/maps` y `/eeprom`** (`web/server.py`) — exponen los mapas
  decodificados y los parámetros de calibración como JSON. El dashboard
  ya muestra el heatmap con datos reales del EEPROM de la ECU.

* **`eeprom_maps` y `eeprom_params`** en `WebServer` — atributos inicializados
  en `{}` y poblados desde `main.py` después de leer el EEPROM.


---

## [v2.2.2] — 2026-03-20
**FIX SHUTDOWN — ExecStop eliminado del unit file**

### Fixed

* **`ExecStop=/usr/sbin/poweroff` en systemd unit** — línea agregada manualmente
  en una sesión anterior causaba que `systemctl restart` apagara la Pi en lugar
  de reiniciar el servicio. Eliminada del unit file en vivo.
  El `install.sh` ya generaba el unit sin `ExecStop` — no requirió cambios.

* **`WORKING_METHOD.md`** — agregadas secciones `AI ASSISTANT PROTOCOL` y
  `COMMIT DISCIPLINE` para que cualquier asistente siga las reglas de edición
  correctas desde el inicio de sesión.

---

## [v2.2.1] — 2026-03-20
**FIXES DE ESTABILIDAD — SHUTDOWN + ECU LOOP**

### Fixed

* **Poweroff en `systemctl restart`** (`main.py`, `web/server.py`) — al recibir
  SIGTERM, el logger ejecutaba `poweroff` apagando la Pi. Separado en dos flags:
  `_poweroff_requested` (solo desde dashboard web) vs SIGTERM que solo detiene
  el loop. El botón shutdown del dashboard ya no llama `poweroff` directo desde
  `server.py` — lo delega a `main.py`.

* **ECU loop sin reconexión** (`main.py`) — si el FT232 no estaba conectado al
  arrancar el servicio, `_ecu_loop` corría en silencio retornando `None` para
  siempre y `live.json` quedaba con `"live": {}`. Ahora el loop detecta
  `ser is None` y reintenta `connect()` + `get_version()` cada 5 segundos
  hasta que el adaptador esté disponible.

* **`import subprocess` faltante** (`main.py`) — el módulo se usaba en
  `shutdown()` pero no estaba importado al inicio del archivo.

---

## [v2.2.0] — 2026-03-20
**MODULARIZACIÓN ECU — ecu/connection.py + ecu/protocol.py**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`ecu/connection.py`** — `DDFI2Connection` extraída del monolito.
  Maneja apertura de puerto serial, toggle DTR, envío de PDUs,
  `get_version()`, `get_rt_data()`, `read_full_eeprom()` y USB reset via sysfs.
  Validada vs ECU real: `BUEIB310 12-11-03`.

* **`ecu/protocol.py`** — constantes y decodificación del protocolo DDFI2.
  `RT_VARIABLES` (56 parámetros), `decode_rt_packet()`, calibración TPS,
  cálculo VS_KPH, detección de marcha. Validada: RPM, CLT, Gear correctos.

* **`tools/test_ecu.py`** — script de diagnóstico independiente.
  Abre puerto, toggle DTR, envía PDU_VERSION y reporta respuesta.
  No depende del servicio ni del proyecto.

### Fixed

* **Poweroff en SIGTERM** (`main.py`) — `systemctl restart` apagaba la Pi
  porque `_handle_signal` ponía `_shutting_down=True` y `shutdown()` ejecutaba
  `poweroff`. Separado en `_poweroff_requested` — poweroff solo ocurre cuando
  el shutdown viene desde el dashboard web.

### Changed

* **`main.py`** — conecta a la ECU en arranque y loguea versión.
  Puerto serial ya no es argumento sin usar.

---

## [v2.1.6] — 2026-03-19

**INSTALL — IMAGEN LIMPIA COMPLETA**

### Fixed

* **`NetworkManager.conf managed=false`** — en imagen limpia de Raspberry Pi OS,
  NM no gestiona interfaces por defecto. El installer ahora cambia `managed=false`
  a `managed=true` antes de configurar el hotspot. Sin este fix el hotspot nunca
  arranca en una Pi recién flasheada.

---

## [v2.1.5] — 2026-03-19

**VERSION DINÁMICA DESDE CHANGELOG**

### Changed

* **`LOGGER_VERSION` en `main.py`** y **`logger_version` en `server.py`** —
  ambos leen la versión dinámicamente del `CHANGELOG.md` en lugar de tenerla
  hardcodeada. La pestaña Config siempre muestra la versión real del sistema.

---

## [v2.1.4] — 2026-03-19

**GIT PULL DESDE BROWSER — ACTUALIZACIÓN SIN TERMINAL**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **Endpoint `POST /git_pull`** en `server.py` — corre `git pull` en el repo
  y reinicia el servicio automáticamente. Sin necesidad de SSH ni terminal.

* **Botón "🔄 Git Pull"** ya existía en el HTML tab Config — ahora funciona
  correctamente al tener el endpoint implementado.

### Changed

* **Botón rojo "Descargar ddfi2_logger.py"** eliminado del tab Config.
  Reemplazado por el flujo de actualización via git pull.
  El texto de la sección ahora dice: "Jala la última versión desde GitHub
  y reinicia el servicio automáticamente."

### Fixed

* **Regla sudoers** — agregado permiso `NOPASSWD` para
  `systemctl restart buell-logger` al usuario `pi`.


---

## [v2.1.3] — 2026-03-19

**SHUTDOWN FIX — APAGADO DESDE BROWSER OPERATIVO**

### Fixed

* **Botón "Apagar Pi" no apagaba el sistema** — el proceso Python corría sin
  permisos para llamar `poweroff`. Solución en tres partes:
  - Regla polkit `99-buell-poweroff.rules` que autoriza al usuario `pi` a
    apagar sin contraseña via `org.freedesktop.login1.power-off`.
  - `web/server.py` — reemplaza `os.system("sudo poweroff")` por
    `subprocess.run(["/usr/sbin/poweroff"])` en el endpoint `/shutdown`.
  - `main.py` — mismo reemplazo en `shutdown()` para el apagado por señal.

* **`--no-poweroff` eliminado del servicio systemd** — el flag bloqueaba
  el apagado intencional desde el browser. El servicio ahora arranca sin él.

* **`Restart=always` → `Restart=on-failure`** — evita que systemd reinicie
  el logger después de un apagado limpio.

* **Regla polkit agregada al `install.sh`** — futuras instalaciones desde
  imagen limpia incluyen el permiso automáticamente.

---

## [v2.1.2] — 2026-03-19

**ARCHITECTURE INDEX — AUTO-GENERADO EN CADA COMMIT**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`tools/make_index.py`** — script que escanea el repo completo y genera
  `ARCHITECTURE.md` automáticamente. Detecta: árbol de archivos, clases,
  métodos, constantes, endpoints HTTP, tabs y funciones JS, pasos del installer.
  Compatible con cualquier archivo nuevo que se agregue al repo sin configuración.

* **`ARCHITECTURE.md`** — índice auto-generado en la raíz del repo.
  Documenta el estado real del código en cada commit.

* **Git hook `pre-commit`** — corre `make_index.py` y agrega `ARCHITECTURE.md`
  automáticamente antes de cada commit. Cero fricción, índice siempre actualizado.

---

## [v2.1.1] — 2026-03-19

**INSTALL FIX — APPLIANCE MODE OPERATIVO**

### Fixed

* **`ExecStart` apuntaba a `ddfi2_logger.py`** — corregido a `main.py --no-poweroff`.
  El servicio systemd ahora levanta el stack modular correcto al arrancar.

* **`avahi-daemon` y `python3-flask` no se instalaban** — agregados al `apt install`.
  Sin avahi no hay mDNS (`buell.local`). Sin flask el `WebServer` no arranca.

* **`network_state.json` no se creaba** — el installer ahora escribe el estado
  inicial `{"mode":"hotspot","ip":"10.42.0.1"}` si el archivo no existe.
  Evita comportamiento indefinido en `load_state()` y `get_wifi_ip()` en el primer boot.

* **Usuario hardcodeado a `pi`** — reemplazado por detección dinámica via
  `$SUDO_USER` / `logname` / `whoami`. Compatible con cualquier imagen de Raspberry Pi OS.

---

## [v2.1.0] — 2026-03-18

**MÓDULO DE RED — SWITCH A PRUEBA DE BALAS**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`network/manager.py`** — módulo independiente de gestión de red.
  Extraído del monolito `ddfi2_logger.py` y reescrito con lógica completa:
  - `get_redirect_url(action)` — calcula la URL destino **antes** de ejecutar
    el switch, permite abrir nueva pestaña en el browser con la IP correcta
  - `_set_switch_status()` / `get_switch_status()` — estado del switch en memoria,
    expuesto via `/wifi/status` para polling desde el browser
  - `_save_state()` / `load_state()` — persiste `{mode, ip, last_wifi_ip}` en
    `network_state.json`; permite recuperar la última IP WiFi conocida aunque
    la Pi haya cambiado de modo
  - `start_monitor()` — thread que vigila la conexión cada 30s y activa hotspot
    si no hay ninguna red activa
  - Fallback automático a hotspot si cualquier switch falla

* **`web/server.py`** — servidor HTTP modular con endpoints completos:
  - `GET /wifi/scan` — escaneo de redes disponibles
  - `GET /wifi/saved` — perfiles guardados en NetworkManager
  - `GET /wifi/status` — modo actual, IP y estado del switch en curso
  - `GET /wifi/redirect_url?action=X` — URL destino antes del switch
  - `POST /wifi/connect` — conectar a perfil guardado
  - `POST /wifi/add` — agregar red nueva y conectar
  - `POST /wifi/forget` — eliminar perfil
  - `POST /network` — switch hotspot↔wifi

* **Switch con redirect URL** — flujo completo a prueba de pérdida de conexión:
  1. Browser pide redirect URL al servidor
  2. Servidor responde con IP destino (conocida del `network_state.json`)
  3. Browser abre nueva pestaña con la URL correcta
  4. Se ejecuta el switch
  5. Modal de transición con cuenta regresiva
  6. Polling cada 2s hasta confirmar `connected`, `fallback` o `failed`
  7. Si falla, alerta al usuario y vuelve a hotspot automáticamente

* **`switchModal`** — div de transición en la pestaña Redes que muestra
  el estado del switch y la URL destino mientras cambia la red

### Fixed

* **`saved_wifi()` no encontraba perfiles** — nmcli devuelve tipo `802-11-wireless`,
  no `wifi`; el filtro anterior nunca matcheaba ningún perfil

* **`web.network = None`** — el `NetworkManager` nunca se conectaba al `WebServer`;
  `/live.json` crasheaba con `AttributeError: 'NoneType'` en cada request

* **`/wifi/scan` era POST en el JS** — el server lo manejaba como GET;
  el escaneo nunca retornaba resultados

* **`updateNetStatus` sin IP** — `fetchLive` pasaba solo el modo, no la IP;
  el label mostraba `WiFi conectado` sin indicar la dirección

* **RED ACTIVA mostraba `--`** — `loadNetPane` no se llamaba al cargar
  el status inicial de red en la pestaña

---

## [v1.16.2] — 2026-03-14
**README — PROJECT DOCUMENTATION**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Full `README.md`: project description, captured parameters table, hardware diagram,
  installation instructions, generated file structure, protocol notes and license.

---

## [v1.16.1] — 2026-03-13
**REAL-TIME DIAGNOSTICS · AUTO NOTES ON CLOSE · VERSION IN CSV**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **ERR cell in header** — new cell in the dashboard header next to Batt.  
  Shows total errors of the active ride (dirty + timeout) with dynamic color:
  - 🟢 Green: 0–2 errors/min
  - 🟡 Orange: 2–5 errors/min
  - 🔴 Red: >5 errors/min  
  Tooltip details: `Dirty: N  Timeout: N  Serial: N (X.X/min)`

- **`RideErrorLog.counts()`** — new Python method.  
  Returns `{dirty, timeout, serial, total}` from in-memory counters (no disk I/O),
  exposed in every `live.json` update as the `ride_errors` field.

- **Version comment in CSV** — first line of every CSV is now `# logger=v1.16.1`.  
  Allows identifying the capture version without parsing the full file.  
  The JS parser filters `#` lines for full backwards compatibility.

### Fixed
- **SOH retry after dirty buffer** (`_sync_to_soh` / `_flush_and_retry_soh`)

  *Before:* if SOH was not found within 0.5s after a dirty byte, returned `None`
  immediately — the cycle was lost and logged as `dirty_bytes`.
  ```python
  # BEFORE
  recovered = self._sync_to_soh()
  if not recovered: return None   # give up, sample lost
  ```
  *After:* automatic second attempt: flushes the buffer (`reset_input_buffer`),
  re-sends the full `PDU_RT_DATA` and retries SOH search with 0.4s timeout.
  Directly reduces the unrecovered dirty_bytes counter.
  ```python
  # AFTER
  recovered = self._sync_to_soh()
  if not recovered:
      recovered = self._flush_and_retry_soh()   # flush + resend + retry
      if not recovered: return None
  ```

- **Dashboard active in waiting mode** (`_waiting_loop`) — **BUG-2**

  *Before:* while the logger was waiting for the ECU, `update_state()` was never
  called. The browser showed `--` on all indicators (CLT, TPS, KPH, etc.) even
  when the ECU was already responding with RPM=0.

  *After:* `update_state(ride_active=False, live_data={})` is called on every
  iteration of the waiting loop — the dashboard correctly reflects the standby
  state from startup.

- **Notes modal when ride was auto-closed** (`closeRide` JS)

  *Before:* if the ride had been automatically closed by a reconnection event,
  `d.ok=false` and the notes modal never appeared.

  *After:* when `d.ok=false`, the client queries `/rides` and opens the modal
  with the last available ride. The user never loses the chance to document the session.

---

## [v1.16.0] — 2026-03-13
**HTTP IMPROVEMENTS · CHARTS v1.15.1 MERGED**

### Changed
- **`ThreadingHTTPServer`** replaces `HTTPServer`  
  Parallel requests without mutual blocking. Before: downloading a large CSV
  froze `live.json` updates because the server was single-threaded.

- **Automatic gzip on CSV download**  
  If the browser sends `Accept-Encoding: gzip`, the server compresses with
  `zlib` level 6. Transfer reduction 5–10x over WiFi. Transparent to the client.

- **`Cache-Control: no-store`** on all JSON responses  
  Double anti-cache guard: base `_json()` header + explicit header on `/live.json`.
  Fixes stale data on Safari/iOS.

### Fixed
- **Resource leaks in file reads**  
  8 instances of `json.load(open(...))` and `csv.DictReader(open(...))` replaced
  by `with open(...) as f`. Files are properly closed even if an exception occurs
  during reading.

- **Silent JSON parse errors on POST**  
  *Before:* invalid POST body silently set `payload={}`.  
  *After:* `logging.warning(f"Invalid JSON: {err} — body={body[:80]!r}")` for debugging.

- **Keepalive spam from multiple tabs**  
  Rate limiting: maximum 1 keepalive accepted every 10 seconds.

---

## [v1.15.1] — 2026-03-13
**REDESIGNED CHARTS — 5 CHARTS WITH MERGED AXES**

### Changed — Chart architecture (full redesign)

Removed `chartCLT` and `chartAFV` as independent charts.  
Result: 5 charts instead of 7, more information per chart, less scrolling.

| # | Canvas | Content | Axes |
|---|--------|---------|------|
| G1 | `chartRPM` h=120 | RPM · KPH · CLT°F | Triple: RPM left, KPH right, CLT°F 2nd right |
| G2 | `chartFuel` h=100 | EGO Corr · AFV · WUE · **Average** | Single % with dynamic range |
| G3 | `chartTPS` h=85 | TPS% | Left 0–100% |
| G4 | `chartSPK` h=95 | Spark1/2 °BTDC · PW1/2 ms | °BTDC left, ms right |
| G5 | `chartBatt` h=70 | Batt V | Auto ±0.3V with 12.5V reference line |

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **G2: Average line** — `(EGO + AFV + WUE) / 3` per sample, thick white dashed line.
  Shows the actual net fuel correction without the 3 curves visually canceling each other.
- **G1: 250°F threshold line** — visual reference for critical temperature on the CLT curve.
- **G4: Pulse Width** — `pw1` and `pw2` on right axis (ms). Allows visual correlation
  of ignition advance with injector pulse duration cycle by cycle.
- **G4: Spark=0° marker** — red dots when `spark1=0` and `fl_decel=0`. Identifies
  ECU-forced retard under `fl_hot=1` (confirmed behavior, not a parser artifact).
- **G1: fl_hot and fl_kill markers** — moved here from the former standalone CLT chart.
- **G2: Rich/Lean markers** — on the EGO curve when it crosses thresholds.

---

## [v1.15.0] — 2026-03-12
**GEAR DETECTION · AUTO TPS CAPTURE · FT232RL LATENCY TIMER · VSS_RPM_RATIO**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Gear detection** — `Gear` field (0=neutral/unknown, 1–5) calculated in
  `parse_rt_data()` from the `VS_KPH / (RPM/1000)` ratio compared against
  `GEAR_THRESHOLDS` for the stock XB12X transmission. Requires RPM>500 and
  VS_KPH>3. Displayed in header as `1st`–`5th` or `N`.

- **VSS_RPM_Ratio** — new field in CSV (offset 100, 1 byte).  
  Internal ratio calculated by the ECU for spark reduction at high speed.
  Confirmed in BUEIB.xml offset=405.

- **FT232RL latency timer** — on connect, attempts to set the latency timer to
  2ms via sysfs (`/sys/bus/usb-serial/devices/ttyUSB*/latency_timer`).
  Reduces serial response latency from 16ms to 2ms. Silent if path not found.

- **Automatic TPS capture** — "⏺ Auto Capture (10s)" button in Config tab.  
  Polls `live.json` every 500ms for 10s, records min/max of `TPS_10Bit` and
  auto-fills the calibration fields. Requires range >20 to be considered valid.

---

## [v1.14.0] — 2026-03-12
**DATE IN CHARTS · VE HEATMAP SORTED · USB RESET · FIX SESSIONS→CHART**

### Fixed
- **VE heatmap RPM unsorted** (`showMap` JS)

  *Before:* the heatmap X axis showed RPM periods in EEPROM order (random),
  making the table unreadable.

  *After:* `period → real RPM (60,000,000 / period)`. Columns with period=0
  are discarded. Sorted ascending left→right. Empty cells shown as `·` on dark background.

- **Race condition Sessions→Chart** (`openRideGraph` / `openLiveRideGraph` JS)

  *Before:* the [Chart] button depended on the dropdown select, which might not
  be synced yet → showed the wrong ride.

  *After:* `r.filename` is passed directly to `loadGraphRide()` bypassing the select.

- **`close_reason` missing in summary JSON**  
  The real field in the JSON is `"reason"`, not `"close_reason"`. Fixed with fallback:  
  `summary.get("reason", summary.get("close_reason", ""))`.

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Date and duration in chart selector** — each ride in the dropdown shows
  `YYMMDDHHMM · Xmin · N samples`.

- **FT232RL USB Reset** (`usb_reset` / `_reading_loop`)  
  Automatic escalation at 60s of ECU loss: finds the FT232RL in sysfs
  (vendor=0403 product=6001) and does `authorized=0 → sleep(0.8) → authorized=1 → sleep(2.0)`.
  Equivalent to physically unplugging and replugging the USB adapter.

- **`opened_utc` in summary JSON** — records the UTC timestamp of ride start
  for correct date calculations in the frontend.

---

## [v1.13.1] — 2026-03-11
**ERRORLOG CONTEXT · AUTOMATIC HARD RECONNECT**

### Fixed / Changed
- **Automatic hard reconnect at 30s** (`_reading_loop`)

  *Before:* reconnection after ECU loss only attempted a soft `get_version()`.
  If the FT232RL was in a hung state, it never recovered.

  *After:* at 30s of loss, performs a full `disconnect()` + `connect()` (DTR toggle)
  even with an active ride. Logged in the errorlog with `trigger="auto_30s"`.
  Soft VERSION logic remains as fallback when no ride is active.

- **Enriched context in errorlog** (`RideErrorLog.update_last_sample`)  
  Each event now includes a snapshot of `{vss, seconds, fl_learn}` in addition
  to existing fields. Makes it easier to correlate errors with bike state.

---

## [v1.13.0] — 2026-03-10
**RIDE ERROR LOG — STRUCTURED ERROR RECORDING**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **`RideErrorLog`** — new class that records communication error events per ride.  
  File `ride_NNN_errorlog.json` is created only if errors occurred.
  Clean ride = no file = immediate diagnosis.

  Recorded event types:
  | Type | Trigger |
  |------|---------|
  | `serial_exception` | exception on serial port |
  | `dirty_bytes` | dirty byte before SOH |
  | `bad_checksum` | incorrect RT checksum |
  | `ecu_timeout` | no response every 10s |
  | `ecu_reset` | ECU `Seconds` field goes backwards |
  | `reconnect_attempt` | reconnection attempt |

- **Error badge** in ride list: `🔴N` next to the ride if it has an errorlog.  
  Tooltip shows summary: `3 serial  2 dirty  1 timeout`.

- **`_flush_ride()` helper** — single point for ride close + errorlog flush.  
  Replaces all scattered direct `session.close_current_ride()` calls.

---

## [v1.12.1] — 2026-03-10
**MINOR VISUAL FIXES**

### Fixed
- `graphRideTitle` invisible when hidden under the chart scroll area → moved before `graphStatus`.
- `replace('_',' ')` → `replace(/_/g,' ')` — replaces **all** underscores, not just the first one.

---

## [v1.12.0] — 2026-03-10
**VE HEATMAP · ACTIVE RIDE BANNER · STATUS INDICATOR**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **VE Heatmap** in VE tab — 4 real EEPROM maps: Fuel Front/Rear, Spark Front/Rear.
  RPM and TPS axes, blue→red color scale by value. Active cell highlighted in real time.
- **Active ride banner** in Sessions tab with timer and "View Chart" button.
- **Pill indicator** — blinking green/yellow dot in header (no "IN RIDE" text).
- **`graphRideTitle`** — shows the name of the ride currently loaded in the chart.

---

## [v1.11.2] — 2026-03-10

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Battery chart** — `chartBatt`, height 70px. Auto Y axis from ride min/max ±0.3V.
  12.5V reference line.
- **WUE in AFV chart** — `WUE` added to the corrections chart as a dashed orange series.

---

## [v1.11.1] — 2026-03-10

### Fixed
- **Silent crash on serial exception** (`_reading_loop`)

  *Before:* an exception in `get_rt_data()` could terminate the loop without
  reaching the `waiting` state or activating the "Force reconnect" button —
  the logger died silently.

  *After:* `try/except` around `get_rt_data()` with correct fallthrough to the
  consecutive error counter.

- **`_force_reconnect` flag ignored during timeout**  
  *Before:* the flag was checked after `get_rt_data()`, which could block on
  timeout for up to 0.3s.  
  *After:* the flag is checked at the start of each iteration, before any I/O.

- **EGO 100% dashed reference line** — horizontal dataset on the TPS%/EGO chart
  as a visual closed-loop reference.

---

## [v1.11.0] — 2026-03-09
**SESSIONS REDESIGN · RIDE NOTES · USAGE TRACKER**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **"Sessions" tab** (formerly "Rides") — rides grouped by session/checksum,
  collapsible, sorted most recent first. `[View]` `[Chart]` `[📝]` buttons per ride.
- **Notes modal** — textarea per ride (`ride_NNN_notes.txt`). Auto-opens when
  closing a ride (800ms delay).
- **Usage Tracker** — usage counter per function (buttons, tabs). Visible in
  Config tab with count bars and download/reset option.

---

## [v1.10.3] — 2026-03-09

### Fixed
- `BUEIB_PARAMS`: `Fan_On/Off translate 200→50` (was showing 370°/330°C instead of 220°/180°C).
- `Fan_KO_On/Off translate 200→0` — same fix.
- `LOGGER_VERSION` moved to a single constant (previously duplicated in multiple places).

---

## [v1.10.1] — 2026-03-08
**WiFi NETWORK MANAGEMENT · FIX DURATION_S**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Networks tab** — WiFi scan, connect/forget networks, hotspot/WiFi switch from the dashboard.

### Fixed
- **Incorrect `duration_s`** in summary JSON  
  *Before:* used `time.monotonic()` at close — if the ride had pauses or
  reconnections, the time was wrong.  
  *After:* uses `last_elapsed_s` (actual accumulated time of data written to CSV).


---

- **Bug #14: No threading locks on shared state** — Added `threading.RLock()` in `web/server.py` (`_data_lock`) protecting `serial_stats`, `ecu_live`, `gps`, and `eeprom_maps` from concurrent access by HTTP threads, ECU loop, and sysmon loop. Used via `self.web._data_lock` in main.py.
