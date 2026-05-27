# BACKLOG — Buell Logger / Tuner

## FASE 1 — Merge RAW de mapas
- [ ] Detector de eventos LAUNCH: crucero estable ≥3s (TPS/RPM/KPH con delta mínimo) → WOT (delta TPS grande o 100%) → fin cuando TPS sale de WOT. Necesario para etiquetar pulls válidos en el merge.
- [ ] Auto-detección de qué mapa cambió entre sesiones (comparar eeprom.bin byte a byte)
- [ ] Si cambió más de 1 mapa → marcar como "no atribuible", no generar merge
- [ ] Merge RAW por celda:
  - SWEET → tomar mapa que gana en dpw_eff (ECO/fuel)
  - SPICY_WOT → tomar mapa que gana en ddvss (SPORT/accel)
  - SPICY_TIPIN/TIPOUT → ignorar (AE activo, mapa no manda)
  - Sin datos → promedio de ambos mapas (neutro)
- [ ] Etiquetar cada celda: `A` / `B` / `AVG` (origen del dato)
- [ ] Visualización en Tuner Studio: 4ta pestaña "MERGED" al lado de BASE/DELTA/MOD
- [ ] Exportar merge como JSON descargable

## FASE 2 — Suavizado asimétrico del merge
- [ ] Detectar transiciones A↔B o A/B↔AVG (fronteras entre orígenes)
- [ ] Suavizado DIRECCIONAL: siempre hacia el pico sugerido, nunca en contra
  - Pico más alto que vecinos → vecinos se bajan hacia el pico
  - Pico más bajo que vecinos → vecinos se suben hacia el pico
  - Pico entre dos valores → interpolar hacia el lado correcto
- [ ] Respetar celdas del mismo origen (ya vienen suaves de fábrica)
- [ ] Parámetro de intensidad del suavizado (lambda)
- [ ] Comparación visual antes/después del suavizado

## FASE 3 — MPU6050 (vibración FR/RR)
- [ ] Hardware: MPU6050 + cables al Pi (I2C: VCC 3.3V, GND, SDA, SCL)
- [ ] Montaje: chasis aluminio (triángulo delantero o subchasis), con aislamiento goma
- [ ] Driver: lectura I2C a ~100-200Hz, integrar al loop del logger
- [ ] CSV: agregar columnas accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
- [ ] Sessions VS: nueva métrica de vibración por bin RPM/TPS
- [ ] Merge de spark: usar vibración como métrica "quién gana" para balance FR/RR
- [ ] Flujo: cambiar spark_front → ride → comparar vibración → decidir si mejoró

## FASE 4 — Exportar mapa mergeado
- [ ] Generar .msq compatible con ECMSpy desde el merge suavizado
- [ ] Opción de exportar solo 1 mapa (ej: solo fuel_front)
- [ ] Validación: no exceder rangos válidos del ECU (0-250 fuel, 0-45 spark)



## CLEANUP — Dead Code

### app.js — funciones definidas pero nunca llamadas
- [ ] `handleMsqDrop` (line 583): manejador drag/drop de MSQ — nunca enlazado
- [ ] `markerSet` (line 1224): helper para marker en maps — nunca usado
- [ ] `extractTransitions` (line 1249): parsing de transiciones — nunca llamado
- [ ] `detectGearChanges` (line 1262): detección de cambios de marcha — nunca llamado
- [ ] `detectWOT` (line 1274): detección de WOT — nunca llamado
- [ ] `detectDTC` (line 1284): detección de DTCs — nunca llamado
- [ ] `doKeepalive` (line 1919): mantener sesión activa — nunca llamado
- [ ] `toggleEcu` (line 1957): conectar/desconectar ECU — nunca llamado (nota: hay un botón "ECU" en el panel de red, verificar si debería estar enlazado)


## NOTAS / REGLAS
- Solo mover UN mapa a la vez entre sesiones (fuel_front, fuel_rear, spark_front, spark_rear)
- Si se mueven 2+ mapas → datos no atribuibles → no merge
- Knock sensor: NO por ahora (ruido mecánico alto en Buell air-cooled, falsos positivos)
- Spark sin knock: tunear por dACC (si avanzás spark y aceleración sube sin subir vibración, no hay knock)

## CODE STANDARDS

### Workflow
- **Backlog → Changelog**: When a task is completed, remove it from BACKLOG.md
  and add an entry to CHANGELOG.md with the version number. Do NOT leave
  completed items marked as [x] in the backlog.

### Language
- **All code, comments, and documentation must be written in English.**
  This includes: variable names, function names, class names, docstrings,
  inline comments, commit messages, and markdown documentation.
  Spanish is only acceptable for direct user-facing strings in the web UI
  (dashboard labels, tooltips) where the end-user speaks Spanish.

## UX — Export / Download

- [ ] **Session consolidated CSV download button**: add a download button per session in the rides list that fetches and downloads a single merged CSV of all rides in that session. Currently only individual ride CSVs are downloadable. Endpoint suggestion: `GET /session_csv?session=<checksum>` → streams all `ride_*.csv` files concatenated with a single header row.


## CODE CLEANUP — Found during code review (2026-05-26)

### 🔴 Priority High — Confirmed Bugs
- [x] **#1 — `o2_adc_avg` wrong variable scope** (`ecu/session.py:341`): Uses `v["o2_adc_sum"]` but `v` is from outer scope — should be `a["o2_adc_sum"]`. Causes NameError at runtime when generating tuning report.
- [ ] **#2 — Infinite loop on serial port wait** (`ecu/connection.py:69`): `while not os.path.exists(self.port):` has no timeout. Process hangs forever if USB serial never appears.
- [ ] **#3 — Heartbeat loop unprotected** (`main.py:460-471`): `while self._running:` body has no try/except wrapper. Thread dies silently if anything raises.

### 🟡 Priority Medium — Fragile Patterns
- [ ] **#4 — `time.time()` vulnerable to clock jumps** (`ecu/connection.py:197`): `while time.time() < deadline:` — if system clock jumps backward (NTP, DST), loop blocks indefinitely. Use `time.monotonic()`.
- [ ] **#5 — Silent except: pass** (`ecu/session.py`): Multiple `except Exception` blocks log warnings but don't repair corrupted data. Swallows structural validation errors.
- [ ] **#6 — Aggressive FIFO flush** (`main.py:355-357`): When serial buffer > 50%, flushes input. In erratic serial state, keeps flushing good data. Add cooldown or rate-limit.
- [ ] **#7 — No CRC/magic byte validation** (`ecu/eeprom.py`): Decodes assuming valid dump. If EEPROM is corrupted, silently extracts garbage values.
- [ ] **#8 — No type guard on quality_ratio** (`ecu/session.py:208`): `total_valid_s / total_s` — protected against div by zero but not against `None` values from data corruption.

### 🟢 Priority Low — Improvements
- [ ] **#9 — `_get_version()` reads CHANGELOG.md at every call** (`main.py:57-65`): Cache `LOGGER_VERSION` instead of re-reading file.
- [ ] **#10 — Floating point drift in long sessions** (`ecu/session.py`): Cumulative sums of `seconds` and `ego_sum` use `round()` but drift over very long rides (>1h).
- [ ] **#11 — Reconnect race condition** (`main.py:ecu_loop`): `ECU_RETRY_INTERVAL=5s` but serial port takes 1-2s to release. Retry fails because port is still busy. Add jitter or port availability check.

### 📋 Planned Features
- [ ] **Version tracking per ride** — Store `logger_version` in ride_summary.json at ride close, show in UI, correlate error rates with code versions.
- [ ] **GLM-5.1 API integration** — "AI Analyze" button in errorlog visualizer that sends ride data to Zhipu AI's GLM-5.1 for pattern analysis.

### Priority High (Confirmed Bugs)
- **#12 — Path traversal in _handle_static** (`web/server.py:162-163`): `lstrip("/")` + `os.path.join` allows `..` traversal to read files outside the web root.
- **#13 — Daemon threads without watchdog** (`main.py:446-449`): `_ecu_thread` and `_sysmon_thread` are `daemon=True`. If they die, the process continues but without ECU data or system monitoring. No recovery mechanism.

### Priority Medium (Fragile Patterns)
- **#14 — No threading locks on shared state** (`main.py`, `server.py`): `serial_stats`, `ecu_live`, `gps`, `eeprom_maps` accessed from HTTP threads + ECU loop + sysmon loop without `threading.Lock` protection.
- **#15 — File descriptor leak in _handle_static** (`web/server.py:166`): `open(fpath, "rb").read()` without `with` statement — file handle remains open until garbage collection.
- **#16 — Missing JSON schema validation** (`web/server.py:298`): `_handle_coverage_targets` parses JSON without validation — `KeyError` on malformed input.
- **#17 — network_state.json race condition** (`network/manager.py:92-108`): `_save_state` reads/writes without lock — file corruption on concurrent WiFi/hotspot state switches.

### Priority Low (Improvements)
