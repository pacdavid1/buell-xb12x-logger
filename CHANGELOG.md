# CHANGELOG — Buell XB12X DDFI2 Logger
> Raspberry Pi Zero 2W · CH343P · Python 3 · 9600,8N1
> Repository: https://github.com/pacdavid1/buell-xb12x-logger
---
## [v2.5.46] — 2026-04-18
### Added
- Tab "Mapa" en dashboard con Leaflet.js (OpenStreetMap, sin API key)
- Endpoint `/gps_track?session=X&ride=N` — lee CSV y devuelve puntos GPS válidos
- Mapa de ruta con polyline coloreada por velocidad (verde=lento, rojo=rápido)
- Marcadores de inicio (verde) y fin (rojo) en la ruta
- Selector de rides en el tab Mapa
- Info bar: cantidad de puntos, velocidad máxima, distancia aproximada
### Changed
- `showTab()` extendido para incluir 'map'

## [v2.5.45] — 2026-04-18
### Added
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

### Added
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

### Added
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
### Added
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
### Added
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
### Added
- `eeprom_decoded.json`: generado desde eeprom.bin (35 params, 4 mapas VE/spark)
- `SessionManager._update_tuning_report()`: incluye eeprom_decoded en tuning_report
### Notes
- tuning_report ahora contiene mapa VE actual + sugerencias en un solo JSON
- Co-diagnosed: Claude (Anthropic)

## [v2.5.38] — 2026-04-06
### Added
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
### Added
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
### Added
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
### Added
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
