# CHANGELOG — Buell XB12X DDFI2 Logger
> Raspberry Pi Zero 2W · FT232RL · Python 3 · 9600,8N1  
> Repository: https://github.com/pacdavid1/buell-xb12x-logger
---

## [2.5.23] - 2026-03-22
### Fixed
- `web/server.py`: rides without summary.json now extract `opened_utc` from CSV `timestamp_iso` column — sorts correctly by date
---

## [2.5.22] - 2026-03-22
### Fixed
- `web/templates/index.html`: long press on RIDE pane no longer selects text (`user-select:none`)
- `web/templates/index.html`: `preventDefault` on pointerdown prevents context menu interference
- `web/templates/index.html`: 30px movement tolerance — vibration while riding no longer cancels countdown
---

## [2.5.21] - 2026-03-22
### Changed
- `web/templates/index.html`: sessions tab now sorted by most recent ride date descending
- `web/templates/index.html`: session header shows readable date next to checksum
---

## [2.5.20] - 2026-03-22
### Added
- `web/templates/index.html`: Restart Logger + Reboot Pi buttons now side-by-side 2-column grid in CONFIG
- `web/templates/index.html`: long press 3s on RIDE pane → saves active ride + reboots Pi (countdown overlay)
- `web/server.py`: `/close_ride` endpoint — calls `session.close_current_ride(reason="dashboard_request")`
- `main.py`: `self.web.session = self.session` — SessionManager now accessible from WebServer
### Fixed
- Button labels changed to English: "Restart Logger", "Reboot Pi"
---

## [2.5.19] - 2026-03-22
### Fixed
- `web/server.py`: added `/restart_logger` endpoint — restarts buell-logger service via systemd
- `web/server.py`: added `/reboot_pi` endpoint — reboots Pi using `sudo /usr/sbin/reboot`
- `/etc/sudoers.d/buell-reboot`: added NOPASSWD rule for `/usr/sbin/reboot`
### Closed
- TASK-3: Restart Logger and Reboot Pi buttons now functional

---

## [2.5.18] - 2026-03-22
### Changed
- `ecu/session.py`: ride filenames now include session checksum — `ride_{checksum}_{NNN}.csv`
- `ecu/session.py`: summary and errorlog filenames follow same pattern
- `web/server.py`: `_get_rides()` uses `sf.name` directly instead of hardcoded filename
- `web/server.py`: fallback CSV parse uses `split('_')[-1]` — backward compat old + new format
- `web/server.py`: CSV handler derives path from `filename` stem — no longer hardcodes `ride_num`
- `web/templates/index.html`: ride list shows filename-based label; download uses correct filename
### Notes
- Existing rides with old format (`ride_NNN.csv`) continue to load correctly

---

## [2.5.17] - 2026-03-22
### Fixed
- `ecu/eeprom.py`: map reading rewritten — zero bytes are row separators, not structural markers
- Previous logic read fixed 13-byte rows and treated zeros as empty cells — incorrect
- Actual structure: 156 bytes = 11 zero separators + 12 segments of 13 values each
- Each segment contains one complete row in descending RPM order (RPM=8k→RPM=0)
- After reversal each row is in ascending RPM order matching the axis
- Load=255 has only 2 valid values (RPM=7k, RPM=8k) — remaining 11 cols padded as None
- `web/templates/index.html`: map cell renderer now handles null (empty region) correctly
### Validated
- Fuel Front verified cell-by-cell against EcmSpy with unique-value test matrix (values 10-165)
- All 156 values match EcmSpy exactly after fix- `ecu/eeprom.py`: map reading now correctly splits by zero-byte separators
- Each segment between zeros contains exactly 13 values in descending RPM order
- Removed incorrect row trimming — all 13 values per row are now valid
- Load=255 row padded to 13 cols (only 2 values stored, rest None)
- `web/templates/index.html`: map renderer now handles null cells correctly
- All 156 values match EcmSpy exactly
### Closed
- BACKLOG-LOG2 final — map display now fully correct

---

## [2.5.16] - 2026-03-22
### Fixed
- `ecu/eeprom.py`: map rows now reversed to match ascending RPM axis
- `ecu/eeprom.py`: structural zero cells marked as None (diagonal triangular region)
- `ecu/session.py`: checksum now covers full EEPROM blob (1206 bytes) instead of first 64
- `web/server.py`: /maps endpoint falls back to most recent eeprom.bin on disk
- `web/templates/index.html`: removed legacy RPM period-to-RPM conversion in showMap()
### Root Cause
- Map rows stored in descending RPM order in EEPROM — reversal was missing
- Checksum based on first 64 bytes missed fuel/spark map modifications
- Full EEPROM checksum now detects any parameter or map change
### Validated
- Fuel Front map confirmed against EcmSpy using unique-value test matrix
- Load=10 row: [10,11,12..22] matches EcmSpy exactly after fix

---

## [2.5.15] - 2026-03-22
### Fixed
- `ecu/eeprom.py`: RPM axis was read as big-endian — corrected to little-endian
- `ecu/eeprom.py`: RPM axis stored in descending order in EEPROM — now reversed to ascending
- Fuel map and spark map columns reversed to match corrected RPM axis
- VE/FUEL/SPARK tabs now show correct RPM bins (0→8000 instead of mirrored)
### Root Cause
- Confirmed by comparing B2RIB.xml offsets against live eeprom.bin dump
- XML offset 644: fuel RPM axis (13x uint16 LE) stored as [8000..0]
- Hardcoded bins [0..8000] were correct — reading order was wrong
### Closed
- BACKLOG-LOG2

---

## [2.5.14] - 2026-03-22
### Fixed
- `main.py`: reconnect path now applies same EEPROM fallback logic as startup path
- If EEPROM fetch fails on reconnect: falls back to most recent cached blob on disk
- If no blob on disk: uses version string as checksum seed (last resort)
- Session now always opens on reconnect — ride start no longer silently skipped
### Root Cause
- Rides not recorded when Pi boots with engine already running above RPM_START threshold
- EEPROM fetch failure on reconnect left `current_checksum=None`
- `write_sample()` was never called despite full telemetry visible in dashboard

## [2.5.13] - 2026-03-21
### Fixed
- `main.py`: EEPROM fallback to most recent cached blob on disk if live fetch fails
- `main.py`: version string used as last-resort checksum if no blob available anywhere
- Session now always opens regardless of EEPROM read success
### Known Issue
- `get_rt_data()` returns None consistently after multiple killswitch/reconnect cycles
- ECU responds to `get_version()` but not to RT data requests in this state
- Root cause under investigation — see BACKLOG-LOG6
### Added
- BACKLOG-LOG6: RT data failure after killswitch cycles — documented for next session

---

## [2.5.12] - 2026-03-21
### Fixed
- `main.py`: EEPROM fetch blocked RT loop on reconnect — removed from reconnect path
- `main.py`: 3s stabilization delay before EEPROM fetch on startup
- `main.py`: session guard on ride start — no crash when session not yet open
- `main.py`: ride start guard indentation — `error_log.start()` and log inside `else` block
- `main.py`: tracker initialized before being passed to web server
- `web/server.py`: `snapshot()` returns tuple — fixed index from `["cells"]` to `[0]`
### Added
- `web/server.py`: live VE cell tracker passed to dashboard via `cell_tracker` attribute
- VE heatmap now shows live cell coverage in real time during ride

---

## [2.5.11] - 2026-03-21
### Changed
- `ecu/session.py`: session checksum now derived from first 64 bytes of EEPROM blob instead of version string
- `main.py`: EEPROM fetched before `open_session()` on both startup and reconnect
- New session created automatically whenever ECU parameters change
### Result
- Session EF4995 (version-based) → Session 9ECD1E (EEPROM-based)
- Each parameter change in ECU produces a new session folder
- Rides before/after tuning changes are now correctly separated
### Closed
- BACKLOG-ECU4 (partial) — session isolation by EEPROM content implemented

---

## [2.5.10] - 2026-03-21
### Added
- `index.html`: IP address in Network tab is now tappable — opens `http://IP:8080` directly in new browser tab
- Works for both WiFi and Hotspot modes, IP always reflects current Pi assignment
### Closed
- BACKLOG-UX1

---

## [2.5.9] - 2026-03-21
### Added
- `main.py`: reads bike Serial Number from EEPROM blob offset 12 (little-endian uint16)
- `web/server.py`: `bike_serial` field added to `live.json` and `WebServer.__init__`
- `index.html`: Serial cell in dashboard header row 1 — shows `#651` when ECU connected

---

## [2.5.8] - 2026-03-21
### Fixed
- `main.py`: sysmon thread was not visible until service restart — confirmed working after `systemctl restart buell-logger`
- CPU% and TEMP now display correctly in dashboard header at all times


---


## [2.5.7] - 2026-03-21
### Added
- `main.py`: `_sysmon_loop` — independent thread, updates CPU% and TEMP every 2s
- CPU% and TEMP visible in dashboard at all times, regardless of ECU connection
### Changed
- `main.py`: sysmon thread starts alongside ECU thread in `run()`
- Code style: all new comments and docstrings written in English going forward

---

## [2.5.6] - 2026-03-21
### Added
- `main.py`: CPU% (via `/proc/stat`, delta 1s) y CPU temp (via `/sys/class/thermal/thermal_zone0/temp`) en `serial_stats`
- `index.html`: celdas CPU% y TEMP en header fila 2 con semáforo (verde/amarillo/rojo)
- TEMP: amarillo >60°C, rojo >75°C
- CPU%: amarillo >60%, rojo >80%

---

## [2.5.5] - 2026-03-21
### Added
- `main.py`: auto-flush FIFO RX del FT232RL cuando `buf_in > 192b` (>50% de 384b)
- Warning en log: `AUTO-FLUSH FIFO buf_in=Xb >50% — flushed`
- El CSV registra el valor `buf_in` previo al flush — dato forense intacto

---

## [2.5.4] - 2026-03-21

### Fixed
- `ecu/eeprom_params.py`: revertido fix EGO Min — parser correcto, era diferencia entre fetches distintos
- Validado EGO Max=105% y EGO Min=95% contra EcmSpy post-burning ✅

### Changed
- `.gitignore`: agrega `*.save`, `*.save.*`, 
`network_state.json` - `objectives.json`: versionado en el repo

---

## [2.5.3] - 2026-03-21

### Added
- `web/templates/index.html`: sección "Parámetros EEPROM" en tab cfg — 173 params con valor actual
- `web/templates/index.html`: función `loadEepromParams()` — agrupa por categoría, muestra nombre/valor/unidades
- Tab cfg llama `loadEepromParams()` al abrirse

### Fixed
- `ecu/eeprom_params.py`: validado contra EcmSpy — valores correctos para Fan, RPM limits, Serial, Year

### Backlog
- ECM MODEL DETECTION: investigar cómo EcmSpy mapea version_string→model code (BUEIB310→B2RIB). Actualmente usamos BUEIB.xml pero la ECU es B2RIB. Diferencia crítica en offset 574 (Bank Angle Sensor scale 0.01 vs 10.0)
- ECM MODEL SELECTOR: permitir al usuario seleccionar manualmente el XML correcto en cfg si la detección automática falla
- EGO MIN NEGATIVO: EGO Correction Minimum Value muestra 950% pero EcmSpy dice 50% — investigar signed encoding o translate especial para este parámetro
- EDITOR EEPROM: tabla con valor actual + campo editable por parámetro, aviso de cambio de checksum al guardar
- HISTORIAL FETCHES EEPROM: guardar cada fetch con timestamp, poder revertir desde dashboard
- VIN/ID MOTO: usar ECM Serial Number (offset 12, valor 651) para identificar moto — advertir si EEPROM cargada es de otra moto
- AUTO-FLUSH FIFO: reset_input_buffer() cuando buf_pct > umbral para prevenir saturación en FT232 de baja calidad

---

## [2.5.2] - 2026-03-21

### Fixed
- `ecu/eeprom_params.py`: HEADER_OFFSET corregido de 4 a 0 — offsets XML son directos al blob de la Pi
- `ecu/eeprom_params.py`: encoding corregido a little-endian para parámetros size=2
- Validado 7/7 contra EcmSpy: Serial=651, Year=2006, FanOn=220°C, FanOff=180°C, KO_On=170°C, KO_Off=150°C, AFV=100%

### Backlog
- EDITOR EEPROM: tabla agrupada por categoría, valor actual + campo editable, aviso cambio checksum
- HISTORIAL FETCHES: poder revertir a versión anterior de EEPROM desde dashboard
- VIN/ID MOTO: usar ECM Serial Number para identificar moto y advertir si EEPROM es de otra moto
- AUTO-FLUSH FIFO: reset_input_buffer() cuando buf_pct > umbral

---

## [2.5.1] - 2026-03-21

### Added
- `ecu/protocol.py`: columna `buf_in` al CSV — bytes acumulados en FIFO RX del FT232RL por sample
- `main.py`: inyecta `ser.in_waiting` en cada sample antes de `write_sample()`
- Diagnóstico forense: correlación temporal buffer↔errores en el CSV

### Backlog
- AUTO-FLUSH: limpiar FIFO RX automáticamente cuando `buf_pct > umbral` via `ser.reset_input_buffer()` para prevenir saturación en FT232 de baja calidad

---

## [2.5.0] - 2026-03-21

### Added
- Dashboard header rediseñado en 2 filas
- Fila 1: parámetros moto — EGO, MAT, Batt, Marcha, Ride
- Fila 2: telemetría sistema — TTL%, BPS, BUF% (FIFO FT232RL), MEM%, ERR
- TTL% con semáforo: verde 85-97% normal, amarillo <85%, rojo >97% o <50%
- BUF% detecta acumulación en FIFO RX del FT232RL (384 bytes)
- MEM% del sistema desde /proc/meminfo sin dependencias externas
- serial_stats en live.json: bps, pct, buf_in, buf_pct, mem_pct

---

## [2.4.2] - 2026-03-21

### Added
- `ecu/session.py`: `save_eeprom()` y `load_eeprom()` — EEPROM persistida en `sessions/CHECKSUM/eeprom.bin`
- `ecu/session.py`: `open_session()` retorna `needs_fetch` — True si no existe eeprom.bin
- `main.py`: fetch automático de EEPROM al detectar sesión nueva, carga desde archivo en sesiones existentes
- `main.py`: `decode_params()` reemplaza `decode_eeprom_params()` — 173 parámetros vs 35

---

## [2.4.1] - 2026-03-21

### Added
- `ecu/eeprom_params.py`: parser de parámetros EEPROM — decode_params() y decode_params_dict()
- Mapeo automático version_string → ecu_defs/XXXX.xml
- 173 parámetros Value decodificados para BUEIB, extensible a todas las variantes

---

## [2.4.0] - 2026-03-21

### Added
- `ecu_defs/`: 14 XMLs de definición EEPROM para variantes ECU Buell (fuente: EcmSpy)
- Cubre DDFI-1 y DDFI-2: BUEIB, B2RIB, BUEGB, BUECB, BUE1D-3D, BUEOD, BUEWD, BUEYD, BUEZD, BUEIA, BUEKA, BUEGC
- `ecu_defs/README.md`: documentación de estructura y mapeo ECU→XML

---

## [2.3.6] - 2026-03-21

### Fixed
- `main.py`: botón "Apagar Pi" ahora funciona — usa `sudo poweroff` desde el proceso systemd
- `/etc/sudoers.d/buell-poweroff`: regla NOPASSWD para usuario `pi`

---

## [2.3.5] - 2026-03-21

### Added
- `web/server.py`: endpoint GET `/errorlog/ride_NNN` — retorna errorlog JSON del ride o `{has_errorlog: false}` si fue limpio

---
## [2.3.4] - 2026-03-21

### Added
- `main.py`: reconexión escalada en `_ecu_loop` — MAX_CONSEC=30, hard reconnect a 30s, USB reset FT232RL a 60s
- `main.py`: `RideErrorLog` integrado — registra serial_exception, ecu_timeout, reconnect_attempt por ride

### Fixed
- Loop ya no se queda mandando RTX indefinidamente con ECU desconectada

---
## [2.3.3] - 2026-03-21

### Added
- `ecu/session.py`: `RideErrorLog` extraído de `ddfi2_logger.py` — registro estructurado de errores por ride (serial_exception, dirty_bytes, bad_checksum, ecu_timeout, ecu_reset, reconnect_attempt)

---
## [2.3.2] - 2026-03-21

### Fixed
- `ecu/session.py`: agregados `cell_key` y `CellTracker` (movidos de `ddfi2_logger.py`)
- `main.py`: instancia `CellTracker`, carga `objectives.json`, llama `tracker.update()` en cada sample y pasa `tracker.snapshot()` a `close_current_ride()` — corrige bug donde el summary JSON nunca se generaba por `tracker_snapshot=None`

---
## [v2.3.1] — 2026-03-21
**DASHBOARD COMPLETO — SESIONES, CSV Y GRÁFICAS**

### Added

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

### Added

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

### Added

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

### Added

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

### Added

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

### Added

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

## How to read this file

Each version has three possible sections:
- **Added** — new functionality
- **Fixed** — bug fix, with `Before / After` block for critical bugs
- **Changed** — behavior change that is not a bug

To inspect the exact diff of any version:
```bash
git diff v1.14.0 v1.16.1                              # all changes between versions
git diff v1.14.0 v1.16.1 -- ddfi2_logger.py           # main file only
git show v1.14.0:ddfi2_logger.py | grep -A 20 "def _sync_to_soh"  # function at a past version
git checkout v1.14.0 -- ddfi2_logger.py               # restore a full past version
```

---

## [v1.16.2] — 2026-03-14
**README — PROJECT DOCUMENTATION**

### Added
- Full `README.md`: project description, captured parameters table, hardware diagram,
  installation instructions, generated file structure, protocol notes and license.

---

## [v1.16.1] — 2026-03-13
**REAL-TIME DIAGNOSTICS · AUTO NOTES ON CLOSE · VERSION IN CSV**

### Added
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

### Added
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

### Added
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

### Added
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

### Added
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

### Added
- **VE Heatmap** in VE tab — 4 real EEPROM maps: Fuel Front/Rear, Spark Front/Rear.
  RPM and TPS axes, blue→red color scale by value. Active cell highlighted in real time.
- **Active ride banner** in Sessions tab with timer and "View Chart" button.
- **Pill indicator** — blinking green/yellow dot in header (no "IN RIDE" text).
- **`graphRideTitle`** — shows the name of the ride currently loaded in the chart.

---

## [v1.11.2] — 2026-03-10

### Added
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

### Added
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

### Added
- **Networks tab** — WiFi scan, connect/forget networks, hotspot/WiFi switch from the dashboard.

### Fixed
- **Incorrect `duration_s`** in summary JSON  
  *Before:* used `time.monotonic()` at close — if the ride had pauses or
  reconnections, the time was wrong.  
  *After:* uses `last_elapsed_s` (actual accumulated time of data written to CSV).

---

## [v1.9.x] — PROJECT BASE

Base version from which active development started.

- `CellTracker` — RPM×Load cell tracking for map coverage
- `LiveDashboard` HTTP on port 8080
- `SessionManager` — CSV + JSON summary per ride, grouped by session (ECU version checksum)
- EEPROM BUEIB 1206-byte decode on startup (offsets verified against `ecmdroid.db`)
- Real-time DTC detector
- SOH sync, `reset_input_buffer`, `PDU_VERSION` recovery

---

## Known issues / Backlog

| ID | Description | Priority | Status |
|----|-------------|----------|--------|
| BUG-3 | VE heatmap RPM unsorted (regression in v1.15) | High | Open |
| PENDING-R1 | Validate USB reset clean reconnection in real ride | High | Open |
| PENDING-F7 | Verify latency timer sysfs path with FT232RL connected on Pi | High | ✅ Closed — sysfs path unavailable on this kernel (-32), handled silently |
| PENDING-R3 | Calibrate `GEAR_KPH_PER_KRPM` with real ride data | Medium | Open |
| PENDING-H2 | Lower `KTemp_Fan_On` offset=498 from 220→200°C in EEPROM | Medium | Open |
| PENDING-H3 | Fix Warmup Corr 260°C→100% in EEPROM | Medium | Open |
| PENDING-V1 | Select ride in Sessions → load in both tabs simultaneously | Low | Open |
| PENDING-U1 | Botón "Descargar ddfi2_logger.py" → reemplazar por acción "Actualizar desde GitHub" que ejecute el installer | Medium | Open |
| PENDING-W1 | Migrar a Flask — reemplazar servidor HTTP manual en server.py | Medium | Open |
| LOAD-G3 | Add Load as 2nd series in G3 chart (right axis 0–255) | Low | Open |
| GPS | Ride-end detection when ECU drops while bike is moving | Future | Open |
| MODULAR-4 | SessionManager — grabar CSVs y summaries por ride | High | ✅ Closed — ride_001.csv grabado, RPM 976 confirmado |
| OBJ-1 | Rediseño Objetivos del ride — generación automática basada en cobertura de celdas del mapa VE, sin entrada manual de JSON | Medium | Open |
| DTC-1 | Cruzar zonas de falla (EGO bajo, DTC activos) con celdas vacías del mapa VE — ride_060 zona 2400/15 RPM mezcla pobre documentada | High | Open |
| MODULAR-1 | Crear `ecu/connection.py` — módulo de conexión serial ECU | High | ✅ Closed — validado vs ECU real (BUEIB310 12-11-03) |
| MODULAR-2 | Integrar `ecu/connection.py` en `main.py` | High | ✅ Closed — ECU conectada en arranque, fix poweroff en SIGTERM |
| MODULAR-3 | Thread RT 8Hz — dashboard live con datos ECU reales | High | ✅ Closed — CHT, Batt, EGO, TPS visibles en HTML |
| v2.0 | Code modularization into independent modules | Future | ✅ Closed — ecu/connection.py, ecu/protocol.py, thread RT integrados |
| BACKLOG-LOG6 | `get_rt_data()` returns None after multiple killswitch/reconnect cycles — 13 failed reconnects in ride_003 session 917900 | High | Open |
| BACKLOG-UX4 | Dashboard freeze indicator when TTL disconnects | Medium | Open |
| BACKLOG-ECU1 | Hardcoded offsets for BUEIB — real ECU is B2RIB | Medium | Open |
| BACKLOG-ECU3 | EEPROM editor — write to ECU with checksum recalculation | Low | Open |
