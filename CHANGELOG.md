# CHANGELOG — Buell XB12X DDFI2 Logger
> Raspberry Pi Zero 2W · FT232RL · Python · 9600,8N1  
> Repositorio: https://github.com/pcdavid1/buell-xb12x-logger

---

## Cómo leer este archivo

Cada versión tiene tres secciones posibles:
- **Added** — funcionalidad nueva
- **Fixed** — corrección de bug, con bloque `Antes / Después` para bugs críticos
- **Changed** — cambio de comportamiento sin ser bug

Para ver el diff exacto de cualquier versión:
```bash
git diff v1.14.0 v1.16.1                          # todos los cambios entre versiones
git diff v1.14.0 v1.16.1 -- ddfi2_logger.py       # solo el archivo principal
git show v1.15.0:ddfi2_logger.py | grep -A 20 "def _sync_to_soh"  # función en versión anterior
```

---

## [v1.16.1] — 2026-03-13
**DIAGNÓSTICO EN TIEMPO REAL · RETRY SOH · NOTAS AUTOMÁTICAS**

### Added
- **Header ERR** — celda nueva en el header de la dashboard junto a Batt.  
  Muestra el total de errores del ride activo (dirty + timeout) con color dinámico:
  - 🟢 Verde: 0–2 errores/min
  - 🟡 Naranja: 2–5 errores/min
  - 🔴 Rojo: >5 errores/min  
  Tooltip detalla: `Dirty: N  Timeout: N  Serial: N (X.X/min)`

- **`RideErrorLog.counts()`** — método nuevo en Python.  
  Retorna `{dirty, timeout, serial, total}` leyendo en memoria (sin I/O de disco),  
  expuesto en cada actualización de `live.json` como campo `ride_errors`.

- **Comentario de versión en CSV** — primera línea del CSV es ahora `# logger=v1.16.1`.  
  Permite identificar la versión que capturó el archivo sin abrir el CSV completo.  
  El parser JS filtra estas líneas con `#` para compatibilidad total.

### Fixed
- **Retry SOH tras buffer sucio** (`_sync_to_soh` / `_flush_and_retry_soh`)

  *Antes:* si no encontraba SOH en 0.5s después de un byte sucio, retornaba `None` directamente — el ciclo se perdía y se registraba como `dirty_bytes`.
  ```python
  # ANTES
  recovered = self._sync_to_soh()
  if not recovered: return None   # ← fin, se pierde el sample
  ```
  *Después:* segundo intento automático: vacía el buffer (`reset_input_buffer`), reenvía `PDU_RT_DATA` completo y reintenta la búsqueda de SOH con 0.4s. Reduce directamente el contador de dirty_bytes no recuperados.
  ```python
  # DESPUÉS
  recovered = self._sync_to_soh()
  if not recovered:
      recovered = self._flush_and_retry_soh()   # vacía + reenvía + reintenta
      if not recovered: return None
  ```

- **Dashboard activo en modo espera** (`_waiting_loop`) — **BUG-2**

  *Antes:* mientras el logger esperaba ECU, `update_state()` nunca se llamaba. El browser mostraba `--` en todos los indicadores (CLT, TPS, KPH, etc.) aunque la ECU ya estuviera respondiendo con RPM=0.

  *Después:* `update_state(ride_active=False, live_data={})` se llama en cada iteración del waiting loop — el dashboard refleja el estado de espera correctamente desde el inicio.

- **Modal de notas cuando ride fue auto-cerrado** (`closeRide` JS)

  *Antes:* si el ride había sido cerrado automáticamente por reconexión, `d.ok=false` y el modal de notas nunca aparecía.

  *Después:* cuando `d.ok=false`, se consulta `/rides` y se abre el modal con el último ride disponible. El usuario nunca pierde la oportunidad de documentar la vuelta.

---

## [v1.16.0] — 2026-03-13
**HTTP IMPROVEMENTS · GRÁFICAS v1.15.1 FUSIONADAS**

### Changed
- **`ThreadingHTTPServer`** en lugar de `HTTPServer`  
  Requests paralelas sin bloqueo mutuo. Antes: descargar un CSV grande congelaba el `live.json` porque el servidor era single-thread. Ahora los requests son simultáneos.

- **Gzip automático en descarga CSV**  
  Si el browser envía `Accept-Encoding: gzip`, el servidor comprime con `zlib` nivel 6.  
  Reducción de transferencia 5–10x en WiFi. Transparente para el cliente.

- **`Cache-Control: no-store`** en todas las respuestas JSON  
  Doble seguro anti-cache: el header `_json()` base + header explícito en `/live.json`.  
  Elimina el problema de datos desactualizados en safari/iOS.

### Fixed
- **Resource leaks en lectura de archivos**  
  8 instancias de `json.load(open(...))` y `csv.DictReader(open(...))` reemplazadas por `with open(...) as f`. Si hay excepción durante la lectura, el archivo queda cerrado correctamente.

- **JSON parse errors silenciosos en POST**  
  *Antes:* si el body del POST no era JSON válido, el error se silenciaba y `payload={}`.  
  *Después:* `logging.warning(f"JSON inválido: {err} — body={body[:80]!r}")` para debug.

- **Spam keepalive desde múltiples tabs**  
  Rate limiting: se acepta máximo 1 keepalive cada 10 segundos. Antes, múltiples tabs abiertas multiplicaban los keepalives innecesariamente.

---

## [v1.15.1] — 2026-03-13
**GRÁFICAS REDISEÑADAS — 5 CHARTS CON EJES FUSIONADOS**

### Changed — Arquitectura de gráficas (redesign completo)

Se eliminaron `chartCLT` y `chartAFV` como charts independientes.  
Resultado: 5 gráficas en lugar de 7, con más información por gráfica y menos scroll.

| # | Canvas | Contenido | Ejes |
|---|--------|-----------|------|
| G1 | `chartRPM` h=120 | RPM · KPH · CLT°F | Triple: RPM izq, KPH der, CLT°F 2do der |
| G2 | `chartFuel` h=100 | EGO Corr · AFV · WUE · **Promedio** | Único % con rango dinámico |
| G3 | `chartTPS` h=85 | TPS% | Izquierdo 0–100% |
| G4 | `chartSPK` h=95 | Spark1/2 °BTDC · PW1/2 ms | °BTDC izq, ms der |
| G5 | `chartBatt` h=70 | Batt V | Auto ±0.3V con línea ref 12.5V |

### Added
- **G2: Línea promedio** — `(EGO + AFV + WUE) / 3` por muestra, línea blanca punteada gruesa. Permite ver la corrección neta real sin que las 3 curvas se cancelen visualmente entre sí.
- **G1: Línea umbral 250°F** — referencia visual de temperatura crítica en la curva CLT.
- **G4: Pulse Width** — `pw1` y `pw2` en eje derecho (ms). Permite correlacionar visualmente avance de encendido con duración de inyección ciclo a ciclo.
- **G4: Marcador Spark=0°** — puntos rojos cuando `spark1=0` y `fl_decel=0`. Identifica retardo forzado por ECU bajo `fl_hot=1` (confirmado, no es artefacto del parser).
- **G1: Marcadores fl_hot y fl_kill** — movidos aquí desde el antiguo chart CLT independiente.
- **G2: Marcadores Rico/Pobre** — sobre la curva EGO cuando cruza umbrales.

---

## [v1.15.0] — 2026-03-12
**DETECTOR DE MARCHA · TPS CAPTURA AUTO · LATENCY TIMER FT232RL · VSS_RPM_RATIO**

### Added
- **Detector de marcha** — campo `Gear` (0=neutro/desconocido, 1–5) calculado en `parse_rt_data()` a partir del ratio `VS_KPH / (RPM/1000)` comparado contra umbrales `GEAR_THRESHOLDS` para la transmisión stock XB12X. Requiere RPM>500 y VS_KPH>3. Visible en header como `1ª`–`5ª` o `N`.

- **VSS_RPM_Ratio** — campo nuevo en el CSV (offset 100, 1 byte).  
  Ratio interno calculado por la ECU para reducción de chispa a alta velocidad. Confirmado en BUEIB.xml offset=405.

- **Latency timer FT232RL** — al conectar, intenta configurar el latency timer a 2ms via sysfs (`/sys/bus/usb-serial/devices/ttyUSB*/latency_timer`). Reduce latencia de respuesta serial de 16ms a 2ms. Silencioso si no encuentra el path.

- **Captura automática TPS** — botón "⏺ Captura Auto (10s)" en Config.  
  Hace polling del `live.json` cada 500ms durante 10s, registra min/max de `TPS_10Bit` y rellena automáticamente los campos de calibración. Requiere rango >20 para considerar válida.

---

## [v1.14.0] — 2026-03-12
**FECHA EN GRÁFICAS · VE HEATMAP ORDENADO · USB RESET · FIX SESIONES→GRAF**

### Fixed
- **VE heatmap RPM desordenado** (`showMap` JS)

  *Antes:* el eje X del heatmap mostraba los períodos de RPM en orden de la EEPROM (aleatorio), haciendo ilegible la tabla.

  *Después:* `período → RPM real (60,000,000 / período)`. Columnas con período=0 se descartan. Ordenadas ascendente izquierda→derecha. Celdas sin datos muestran `·` sobre fondo oscuro.

- **Race condition Sesiones→Graf** (`openRideGraph` / `openLiveRideGraph` JS)

  *Antes:* el botón [Graf] dependía del dropdown select, que podía no estar sincronizado todavía → mostraba el ride equivocado.

  *Después:* `r.filename` se pasa directo a `loadGraphRide()` sin pasar por el select.

- **`close_reason` ausente en summary JSON**  
  El campo real en el JSON es `"reason"`, no `"close_reason"`. Fix con fallback:  
  `summary.get("reason", summary.get("close_reason", ""))`.

### Added
- **Fecha y duración en selector de gráficas** — cada ride en el dropdown muestra `YYMMDDHHMM · Xmin · N muestras`.

- **USB Reset FT232RL** (`usb_reset` / `_reading_loop`)  
  Escalación automática a los 60s de pérdida de ECU: busca el FT232RL en sysfs (vendor=0403 product=6001) y hace `authorized=0 → sleep(0.8) → authorized=1 → sleep(2.0)`. Equivalente a desconectar y reconectar el USB físicamente.

- **`opened_utc` en summary JSON** — registra timestamp UTC de inicio del ride para cálculos de fecha correctos en el frontend.

---

## [v1.13.1] — 2026-03-11
**ERRORLOG CONTEXT · HARD RECONNECT AUTOMÁTICO**

### Fixed / Changed
- **Hard reconnect automático a los 30s** (`_reading_loop`)

  *Antes:* la reconexión tras pérdida de ECU solo intentaba `get_version()` suavemente. Si el FT232RL quedaba en estado hung, nunca recuperaba.

  *Después:* a los 30s de pérdida hace `disconnect()` + `connect()` completo (DTR toggle) aunque haya ride activo. Registrado en el errorlog con `trigger="auto_30s"`. La lógica VERSION simple queda como fallback cuando no hay ride.

- **Contexto enriquecido en errorlog** (`RideErrorLog.update_last_sample`)  
  Cada evento ahora incluye snapshot `{vss, seconds, fl_learn}` además de los campos existentes. Facilita correlacionar errores con estado de la moto.

---

## [v1.13.0] — 2026-03-10
**RIDE ERROR LOG — REGISTRO ESTRUCTURADO DE ERRORES**

### Added
- **`RideErrorLog`** — clase nueva que registra eventos de error durante cada ride.  
  Archivo `ride_NNN_errorlog.json` creado solo si hubo errores. Ride limpio = sin archivo = diagnóstico inmediato.

  Tipos de evento registrados:
  | Tipo | Trigger |
  |------|---------|
  | `serial_exception` | excepción en puerto serial |
  | `dirty_bytes` | byte sucio antes de SOH |
  | `bad_checksum` | checksum RT incorrecto |
  | `ecu_timeout` | sin respuesta cada 10s |
  | `ecu_reset` | campo `Seconds` de la ECU retrocede |
  | `reconnect_attempt` | intento de reconexión |

- **Badge de errores** en lista de rides: `🔴N` junto al ride si tiene errorlog.  
  Tooltip muestra resumen: `3 serial  2 dirty  1 timeout`.

- **`_flush_ride()` helper** — punto único de cierre de ride + flush de errorlog.  
  Reemplaza todos los `session.close_current_ride()` directos dispersos en el código.

---

## [v1.12.1] — 2026-03-10
**FIXES VISUALES MENORES**

### Fixed
- `graphRideTitle` invisible al quedar bajo el scroll de gráficas → movido antes de `graphStatus`.
- `replace('_',' ')` → `replace(/_/g,' ')` — reemplaza **todos** los underscores, no solo el primero.

---

## [v1.12.0] — 2026-03-10
**HEATMAP VE · BANNER RIDE ACTIVO · INDICADOR DE ESTADO**

### Added
- **Heatmap VE** en pestaña VE — 4 mapas reales del EEPROM: Fuel Front/Rear, Spark Front/Rear. Ejes RPM y TPS, colores azul→rojo por valor. Celdas activas marcadas en tiempo real.
- **Banner ride activo** en pestaña Sesiones con timer y botón "Ver Graf".
- **Indicador pill** — puntito verde/amarillo parpadeante en header (sin texto "EN RIDE").
- **`graphRideTitle`** — muestra nombre del ride cargado en la gráfica.

---

## [v1.11.2] — 2026-03-10

### Added
- **Chart Batería** — `chartBatt`, altura 70px. Eje Y automático desde min/max del ride ±0.3V. Línea de referencia 12.5V.
- **WUE en Chart AFV** — `WUE` agregado al chart de correcciones como serie punteada naranja.

---

## [v1.11.1] — 2026-03-10

### Fixed
- **Crash silencioso en excepción serial** (`_reading_loop`)

  *Antes:* una excepción en `get_rt_data()` podía terminar el loop sin llegar al estado `waiting` ni activar el botón "Forzar reconexión" — el logger quedaba muerto sin indicarlo.

  *Después:* `try/except` alrededor de `get_rt_data()` con fallthrough correcto al contador de errores consecutivos.

- **`_force_reconnect` ignorado durante timeout**  
  *Antes:* el flag se chequeaba después del `get_rt_data()`, que podía bloquearse en timeout hasta 0.3s.  
  *Después:* el flag se chequea al inicio de cada iteración, antes de cualquier I/O.

- **Línea punteada EGO 100%** — dataset horizontal en la gráfica TPS%/EGO como referencia visual de bucle cerrado.

---

## [v1.11.0] — 2026-03-09
**REDISEÑO SESIONES · NOTAS · USAGE TRACKER**

### Added
- **Pestaña "Sesiones"** (antes "Rides") — rides agrupados por sesión/checksum, colapsables, ordenados por más reciente arriba. Botones `[Ver]` `[Graf]` `[📝]` por ride.
- **Modal de notas** — textarea por ride (`ride_NNN_notes.txt`). Se auto-abre al cerrar un ride (800ms delay).
- **Usage Tracker** — contador de uso por función (botones, tabs). Visible en Config con barras de conteo y opción de descarga/reset.

---

## [v1.10.3] — 2026-03-09

### Fixed
- `BUEIB_PARAMS`: `Fan_On/Off translate 200→50` (mostraba 370°/330°C en lugar de 220°/180°C).
- `Fan_KO_On/Off translate 200→0` — fix similar.
- `LOGGER_VERSION` movido a constante única (antes repetida en múltiples lugares).

---

## [v1.10.1] — 2026-03-08
**GESTIÓN DE REDES WiFi · FIX DURATION_S**

### Added
- **Pestaña Redes** — escaneo WiFi, conexión/olvido de redes, switch hotspot/WiFi desde el dashboard.

### Fixed
- **`duration_s` incorrecto** en summary JSON  
  *Antes:* usaba `time.monotonic()` al cierre — si el ride había tenido pausas o reconexiones, el tiempo era incorrecto.  
  *Después:* usa `last_elapsed_s` (tiempo acumulado real de datos escritos al CSV).

---

## [v1.9.x] — BASE DEL PROYECTO

Versión base desde la que comenzó el desarrollo activo.

- `CellTracker` — tracking de celdas RPM×Load para cobertura de mapa
- `LiveDashboard` HTTP en puerto 8080
- `SessionManager` — CSV + JSON summary por ride, agrupados por sesión (checksum de versión ECU)
- Decode EEPROM BUEIB 1206 bytes al arrancar (offsets verificados contra `ecmdroid.db`)
- Detector DTC en tiempo real
- Sync SOH, `reset_input_buffer`, recuperación por `PDU_VERSION`

---

## Pendientes conocidos (backlog)

| ID | Descripción | Prioridad |
|----|-------------|-----------|
| BUG-3 | VE heatmap RPM desordenado (regresión en v1.15) | Alta |
| PENDING-R1 | Validar reconexión limpia USB reset en ride real | Alta |
| PENDING-F7 | Verificar path latency timer con FT232RL conectado en Pi | Alta |
| PENDING-R3 | Calibrar `GEAR_KPH_PER_KRPM` con datos reales de ride | Media |
| PENDING-H2 | Bajar `KTemp_Fan_On` offset=498 de 220→200°C en EEPROM | Media |
| PENDING-H3 | Corregir Warmup Corr 260°C→100% en EEPROM | Media |
| PENDING-V1 | Seleccionar ride en Sesiones → cargar en ambas pestañas simultáneamente | Baja |
| LOAD-G3 | Agregar Load como 2ª serie en G3 (eje derecho 0–255) | Baja |
| GPS | Detección ride-end cuando ECU cae con moto en movimiento | Futura |
| v2.0 | Modularización del código en módulos independientes | Futura |
