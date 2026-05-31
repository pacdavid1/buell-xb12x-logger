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



## UX — Grid Simplification (Cobertura)
- [ ] Simplificar grid: eliminar modos EGO, O2 ADC, Confianza (no útiles con narrowband bloqueado a 100%)
- [ ] Mantener solo: Segundos (cantidad de data) + SWEET + TIPIN + TIPOUT + WOT (calidad por condición)
- [ ] Navegación: swipe left/right entre modos en lugar de botones
- [ ] Dots indicadores de posición (carrusel) debajo del grid
- [ ] Animación de transición suave entre modos

## HARDWARE — Wideband Piggyback (AFR Target Controller)
- [ ] Hardware: wideband O2 sensor (ej: Spartan 2, 14Point7) → Arduino/RPi ADC → leer AFR real
- [ ] Lógica: comparar AFR real vs AFR objetivo (mapa por RPM/TPS)
- [ ] Emular señal narrowband a la DDFI2: si AFR real == objetivo → mandar 14.7 (0.45V). Si real < objetivo (rica) → mandar voltaje que la DDFI2 interprete como rico. Si real > objetivo (pobre) → mandar voltaje que la DDFI2 interprete como pobre.
- [ ] La DDFI2 corrige combustible vía EGO para llegar a 14.7 — pero el piggyback la engaña para que inyecte lo correcto
- [ ] Target AFR map editable desde la web (VE-like, tabla RPM x TPS con AFR objetivo)
- [ ] Modo "passthrough" para desactivar el piggyback y dejar la DDFI2 operar normal
- [ ] El logger ya captura Accel_Corr, WUE, EGO_Corr — se puede loggear la señal del wideband como columna extra en CSV
- [ ] Seguridad: limits de corrección máximos para evitar daño al motor si el WB falla

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

### 🟡 Priority Medium — Fragile Patterns
- [ ] **#5 — Silent except: pass** (`ecu/session.py`): Multiple `except Exception` blocks log warnings but don't repair corrupted data. Swallows structural validation errors.
- [ ] **#8 — No type guard on quality_ratio** (`ecu/session.py:208`): `total_valid_s / total_s` — protected against div by zero but not against `None` values from data corruption.

### 🟢 Priority Low — Improvements
- [ ] **#10 — Floating point drift in long sessions** (`ecu/session.py`): Cumulative sums of `seconds` and `ego_sum` use `round()` but drift over very long rides (>1h).
- [ ] **#11 — Reconnect race condition** (`main.py:ecu_loop`): `ECU_RETRY_INTERVAL=5s` but serial port takes 1-2s to release. Retry fails because port is still busy. Add jitter or port availability check.

### 📋 Planned Features
- [ ] **Version tracking per ride** — Store `logger_version` in ride_summary.json at ride close, show in UI, correlate error rates with code versions.
- [ ] **GLM-5.1 API integration** — "AI Analyze" button in errorlog visualizer that sends ride data to Zhipu AI's GLM-5.1 for pattern analysis.

### Priority High (Confirmed Bugs)
- **#13 — Daemon threads without watchdog** (`main.py:446-449`): `_ecu_thread` and `_sysmon_thread` are `daemon=True`. If they die, the process continues but without ECU data or system monitoring. No recovery mechanism.

### Priority Medium (Fragile Patterns)
### Priority Low (Improvements)

## REFACTOR — JS Robustness

- [ ] **app.js setInterval without clearInterval** (lines ~641, 642, 2319): timers keep running in history-viewing mode — should pause polling when not in live ride view
- [ ] **app.js getElementById without null checks** (~30+ instances): if HTML changes, silent crashes — add guards or use a safe `el()` wrapper
- [ ] **app.js global namespace pollution**: `lastData`, `_fetchingLive`, `_lastLiveOk`, `SESSIONS`, `DATA` are unnamespaced globals — risk of collision if scripts grow — consider wrapping in an `App` object

---

## FASE 4 — Data-driven tune recommendation pipeline

**Goal:** after collecting enough rides across sessions, automatically recommend
VE/spark map updates based on observed engine response vs expected ECU output.

### Context
- Sessions VS and Launch Analysis already match conditions (gear, RPM, TPS, speed)
  and compare outcomes (spd_gain, rpm_gain, peak_pw, AE%).
- The MSQ download gives the baseline map for any session (via /eeprom/msq).
- The missing link: connecting observed differences in outcome → specific map cells
  that should change.

### Backlog items

#### 4.1 — Minimum data threshold per cell
- [ ] Define minimum sample count per (RPM bin, TPS bin) cell before it can be
  used as a recommendation source (suggested: ≥30 valid samples across ≥3 rides)
- [ ] Surface coverage per cell in Sessions VS view (already partially in VE grid)

#### 4.2 — Cell-level outcome correlation
- [ ] For cells with enough data: correlate mean(AE%) with injector correction demand
  (AE > 0 sustained = lean condition in that cell → VE should go up)
- [ ] Flag cells where EGO correction consistently trends one direction
  (persistent lean/rich bias across multiple sessions = map needs adjustment)

#### 4.3 — Launch outcome → map cell attribution
- [ ] When a Launch Analysis pair shows B faster than A with lower PW (efficiency win):
  identify which (RPM, TPS) cells were active during the launch window
- [ ] Weight the evidence: cells visited more during the pull get stronger signal

#### 4.4 — Recommendation report
- [ ] Generate a recommendation JSON per session: { cell_key: { current_ve, suggested_ve,
  confidence, evidence_count, direction } }
- [ ] Confidence tiers: LOW (<30 samples), MEDIUM (30-100), HIGH (>100)
- [ ] Only recommend changes within ±15% of current value per iteration (safety limit)

#### 4.5 — MSQ export with recommendations applied
- [ ] _generate_suggested_msq() currently only fires when tuning report has suggestions
  Fix: always generate from eeprom_decoded.json, apply suggestions if present,
  write even if 0 cells changed (baseline export)
- [ ] Version the MSQ with session + ride count in bibliography field

#### 4.6 — UI: recommendation overlay on VE heatmap
- [ ] In VE tab: overlay arrows (↑↓) on cells with pending recommendations
  colored by confidence tier
- [ ] Click cell → show evidence: how many rides, mean AE correction, EGO trend

### Dependencies
- Requires sufficient data variety: same bike, multiple rides, stable CLT (>80°C)
- Launch Analysis pairs are the highest-quality signal (controlled conditions)
- Sessions VS SWEET/ECO cells are the bulk signal (cruising fuel efficiency)

### Notes
- Do NOT mix data from different bikes (serial #235 vs #651) — already enforced
  in Sessions VS via bike_serial check
- CLT must be comparable between sessions for valid efficiency comparisons
  (see Eff score caveat in v2.6.64)

---

## FASE 5 — VE Subtab as Full EEPROM Editor (EcmSpy replacement)

**Goal:** replace EcmSpy entirely for day-to-day tuning. Edit any named EEPROM
parameter directly from the dashboard (phone or browser), burn to ECU via Pi.

### Context

The VE subtab already reads and displays the decoded EEPROM (fuel maps, spark maps,
named parameters). The BUEIB.xml covers 99% of the EEPROM (1204/1206 bytes,
238 named parameters). `write_full_eeprom()` is implemented and tested.
The missing piece is the UI layer and parameter-level burn controls.

### Phase 5.1 — Fuel + Spark map editor (safe zone only)

The 4 maps (Fuel Front, Fuel Rear, Spark Front, Spark Rear) are the primary
tuning targets. These live in the safe write zone (offsets 670–1205).

- [ ] Make each VE heatmap cell editable (click → input field → enter new value)
- [ ] "Stage" changes locally (highlight modified cells in yellow/orange)
- [ ] Show a diff summary: N cells changed, max delta ±X%
- [ ] Safety gate: reject changes > ±15% of current value per cell
- [ ] "Burn to ECU" button → calls write_full_eeprom() → shows progress + result
- [ ] "Discard changes" button → revert staged cells to current ECU values
- [ ] Auto-backup: save current EEPROM as XPR before any burn

Endpoint needed:
- POST /eeprom/burn { session: X, maps: { fuel_front: [[...]], ... } }
  → decodes proposed maps → builds full 1206-byte blob → calls write_full_eeprom()

### Phase 5.2 — Configuration parameters editor

Beyond fuel/spark maps, the BUEIB.xml defines 238 named parameters including:
EGO correction thresholds, AFV limits, closed-loop RPM window, startup enrichment,
idle spark, WOT spark reduction, fuel cut region, and more.

- [ ] Expose all named eeoffsets from BUEIB.xml in a new "Config" section of VE tab
- [ ] Group by category (Fuel, Spark, Idle, Closed Loop, Temperature, etc.)
- [ ] Each parameter: current value, units, editable input
- [ ] Burn config parameters with same safety gate + backup workflow as Phase 5.1
- [ ] Note: config params live in offsets 0–669 — expand safe_start dynamically
      based on which params the user edits (never touch DTC/serial/factory bytes)

### Phase 5.3 — AI-assisted parameter suggestions

Generating tuning suggestions for the 200+ configuration parameters is too complex
for deterministic algorithms. The right approach: export a structured JSON snapshot
that a language model can interpret and suggest changes for.

- [ ] Export endpoint: GET /eeprom/ai_context?session=X
  Returns JSON with:
  - Current EEPROM values for all 238 named parameters (with units + description)
  - Recent session statistics (avg CLT, RPM histogram, load distribution, EGO history)
  - Current VE/spark maps vs sessions-derived suggestions
  - Known constraints (safe ranges from XML, bike serial, ECU version)

- [ ] The JSON is designed to be pasted into a Claude/GPT prompt for parameter review
- [ ] Suggestions come back as human-readable text, user applies them manually
  (not auto-applied — the human stays in the loop for configuration changes)

### Why this replaces EcmSpy

| Workflow today         | Workflow after Phase 5.1        |
|------------------------|---------------------------------|
| Pi logs session        | Pi logs session                 |
| Analyze in dashboard   | Analyze in dashboard            |
| Open EcmSpy on laptop  | Stay in dashboard (phone OK)    |
| Load EEPROM via USB    | Already loaded from Pi          |
| Edit maps manually     | Edit cells directly in VE tab   |
| Save MSQ               | Stage changes                   |
| Burn to ECU via USB    | Burn to ECU via Pi (WiFi)       |
| Reconnect Pi           | Already connected                |

### Dependencies

- write_full_eeprom() ✅ implemented (ecu/connection.py v2.6.71)
- BUEIB.xml parameter map ✅ 99% coverage confirmed
- GET /eeprom/msq ✅ already generates MSQ from current EEPROM
- Safe write zone documented ✅ (docs/10_DDFI2_PROTOCOL.md section 11)
