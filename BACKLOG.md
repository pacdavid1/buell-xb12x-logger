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

### AI Agent Header Note (incremental cleanup)
When modifying any source file, if the file header does not already contain a DEV NOTE,
add one immediately after the first line:
- Python: 
- JS: 
- HTML: see the 5-line HTML comment block used in web/templates/*.html as reference
This is incremental — only add to files you touch, never as a bulk pass on untouched files.

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

### 🟡 Priority Medium — Fragile Patterns
<!-- #5 silent except and #8 quality_ratio already resolved in current code -->

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



## FASE 7 — Detección y clustering de eventos de aceleración (Bucket A/B)

### Concepto
Detectar eventos de aceleración como pares (condición estable A → transición B).
Agrupar por similitud de TPS trajectory dentro y entre sesiones.
Comparar PW (pulsos de inyección) para medir el efecto del mapa.
Sin categorías predefinidas — los grupos emergen de los datos.

```
EVENTO = Bucket_A (condiciones estables ≥3s) + Curve_B (trayectoria TPS)

Within session (mismo mapa):
  Agrupar por Bucket_A → medir consistencia de PW
  PW_std alto = ruido de ruta (pendiente, viento) → advertencia, no filtro

Cross session (mapas diferentes):
  Asociar por: mismo Bucket_A + Pearson(TPS_curve) > 0.85
  Comparar: ΔPW(t) = PW_b(t) - PW_a(t)   ← efecto del mapa
            Δkph(t) = kph_b(t) - kph_a(t) ← efecto en aceleración
  Confianza variable por slice temporal t según n_eventos(t) cubriendo ese punto
```

### 7.4 — Cross-session matching
<!-- 7.4.1 _f7_match_cross_session(), 7.4.2 _compare_sessions integration,
     7.4.3 event struct improvements — all implemented in v2.6.92 -->

#### 7.4.4 — Environmental context in matches
- [ ] Per match: add context_a/context_b with baro/temp_amb/humidity/clt averages
- [ ] env_warning list: flag Δbaro>5hPa, Δtemp>10°C, Δhumidity>20%
- [ ] These are warnings only — never filters



### 7.5 — Live "READY FOR EVENT" notification
- [ ] ECU loop: monitor gear + RPM_bucket + TPS_bucket; emit event_ready in live.json if stable ≥3s
- [ ] Dashboard: green pulsing chip "GO: 3a · 3000rpm · 5%tps"
- [ ] Auto-record event when stable_s ≥ 3 and transition detected

### 7.6 — Session Events UI
- [ ] Confidence band visualization (shaded area on chart — partially implemented)
- [ ] ΔPW(t) and ΔVSS(t) cross-session comparison chart (needs 7.4)
- [ ] Warning badges: CLT range, GPS slope, PW imbalance (partial — imbalance badge done)


#### 7.7 — Events-compete-directly comparison (all sessions)
- [ ] Batch-generate session_f7clusters JSON for all sessions that have ride CSVs
- [ ] Compare events directly (not sessions) — any two accel events with matching
  Bucket_A (gear, RPM_bin, TPS_bin, KPH_bin) and Pearson(TPS_curve) > 0.85 compete
  regardless of which session they came from
- [ ] Score: Δkph winner per event pair → rank sessions by win rate
- [ ] Filter: require >= 5 matched events per session before including in ranking
- [ ] Output: ranked list of sessions/eeproms by acceleration win rate

#### 7.8 — Migrate Launch Analysis to use f7 events JSON
- [ ] Launch currently runs detect_launches() independently — migrate to consume
  session_f7clusters JSON as its event source (accel events only)
- [ ] Removes duplicate detection logic; f7 events are richer (Bucket_A struct, env context)
- [ ] detect_launches() stays alive in parallel until migration is complete and validated

### Notas de diseño
- Pendiente y aero = advertencias, NUNCA filtros de agrupación (demasiado restrictivo)
- Velocidad = incluida en Bucket_A como referencia, no como filtro estricto
- PW es la variable de medición, TPS es la variable de asociación
- Pearson sobre N=20 puntos es suficiente — DTW es overkill para este caso
- El algoritmo actual detect_launches sigue corriendo en paralelo hasta migración

## FASE 6 — Propuesta de mapa desde Sessions VS

### Contexto
Sessions VS ya genera 62+ filas de delta (dpw_eff, dspk por bin RPM/TPS) comparando dos sesiones.
El gap es proyectar ese delta a las celdas reales del EEPROM y generar una sesión PROP_* que
aparece en VE para revisar y quemar. Sin WB — el tuning es relativo entre sesiones, no absoluto.

### 6.1 — Mapeador bin compare → celda EEPROM
- [ ] Función que toma dpw_eff por bin (RPM 400wide × TPS 5wide) y lo proyecta a celdas EEPROM
  usando los ejes reales (fuel_rpm, fuel_load, spark_rpm, spark_load)
  Método: nearest-neighbor o bilinear inverse — asignar cada bin a la celda EEPROM más cercana
- [ ] Solo proyectar celdas con na >= min_samples (configurable, default 30)
- [ ] Resultado: dict {(ri, ci): dpw_eff} por mapa (fuel_front, fuel_rear, spark_front, spark_rear)

### 6.2 — Cálculo de propuesta VE
- [ ] Convertir dpw_eff a delta VE: factor = pw_eff_a / pw_eff_b (sesión elegida como referencia)
  new_VE[ri][ci] = current_VE[ri][ci] * factor  (limitado a ±15% por iteración)
- [ ] Sin WB: la propuesta es relativa (no corrige a AFR objetivo, blendea entre sesiones)
- [ ] Opción: tomar valores directamente de sesión A o B, o blend configurable (alpha A + (1-alpha) B)
- [ ] Celdas sin cobertura: sin cambio (mantener valor actual)

### 6.3 — Suavizado del delta (no del valor)
- [ ] Suavizar el DELTA, no el valor total — evita mover celdas que no se tocaron
  delta[ri][ci] = staged_change  (0 para celdas no modificadas)
  delta_smooth = laplacian(delta, lambda=0.25, iterations=2, radius=1)
  new_VE = current_VE + delta_smooth
- [ ] Celdas ancla: marcadas como NO mover aunque sean vecinas de celdas modificadas
- [ ] Radio configurable: 1 celda (solo vecinas directas) o 2 celdas
- [ ] Versión sin suavizar disponible siempre — logear con escalones, suavizar después
- [ ] Protección: ignorar deltas < 0.5 unidades para evitar ruido

### 6.4 — Generación de sesión PROP_*
- [ ] POST /eeprom/propose — recibe {session_a, session_b, params}
  Genera EEPROM propuesto, lo guarda como sessions/PROP_YYYYMMDD_HHMMSS/eeprom.bin
  Aparece automáticamente en lista Revert de VE (más reciente = arriba)
- [ ] La sesión PROP_* es editable normalmente en VE antes de quemar
- [ ] Botón "Generar propuesta" en Sessions VS (después del compare)
- [ ] Botón "Auto-tune" = generate + smoothing en un solo click

### 6.5 — Piggy WB (cuando tengamos sensor)
- [ ] Hardware: interceptar señal NB del O2, inyectar voltaje simulado desde WB
  14.7 AFR = 0.5V, lean = 0.3V, rich = 0.7V, rango 0-1V
- [ ] Tabla AFR objetivo por RPM/TPS (configurable en dashboard)
- [ ] Pi lee WB real, compara con target, calcula voltaje NB a inyectar a la DDFI2
- [ ] Con piggy activo: EGO correction real → propuesta VE basada en AFR absoluto
- [ ] Sin piggy: open loop, propuesta relativa entre sesiones (FASE 6.1-6.4)

## Mantenimiento / Limpieza de código

### Código muerto Python (confirmado — 0 referencias en todo el codebase)
- [ ] Eliminar  — ecu/eeprom_params.py (función de compat nunca llamada)
- [ ] Eliminar  — ecu/session.py (nunca referenciada)
- [ ] Eliminar  — ecu/session.py (nunca llamada)
- [ ] Eliminar  — network/manager.py (nunca llamada)
- [ ] Eliminar  — ecu/connection.py (nunca llamada)
- [ ] Quitar imports muertos en main.py: , 

### Archivos huérfanos (existen pero nadie los importa)
- [ ] Eliminar  — script de actualización obsoleto
- [ ] Eliminar  — patch para ddfi2_logger.py que ya no existe
- [ ] Eliminar o documentar , , 

### Sesiones huérfanas (sin rides)
- [ ] Endpoint o script de limpieza: borrar sesiones sin rides y sin eeprom_backup_*.bin
  Solo conservar sesiones que tienen al menos 1 ride o son la sesión activa


## FASE 7 — Sensores y Telemetria
- [ ] Comparacion AHT20_temp vs BMP280_temp: AHT20 tiene su propio sensor de temperatura
  ademas del BMP280. Evaluar que tan consistentes son entre si y si vale la pena
  incluir ambas temperaturas en el dashboard y CSV. Posible uso: deteccion de
  deriva termica entre sensores o redundancia.


# Backlog: UPS-Lite v1.3 — Power Management Features

## 2. Limitar carga al 80%% para cuidar vida util de la bateria

### Problema
El CW2015 (0x62) es solo un fuel gauge (monitoreo). NO controla la carga.
El cargador del UPS-Lite es un chip separado (TP4056 o similar) que:
- No tiene interfaz I2C
- No se puede programar por SW
- Solo tiene pin CE (enable) para habilitar/deshabilitar carga

### Solucion posible (requiere HW)
1. Agregar MOSFET controlado por GPIO entre cargador y bateria
2. Script: leer CW2015, cuando SOC >= 80%%, togglear GPIO para desconectar cargador
3. Cuando SOC < 70%%, reconectar

### Esfuerzo: HW bajo (1 MOSFET + 1 resistor), SW bajo (20 lineas Python)
### Prioridad: MEDIA

---

## 3. Corte de energia a sensores al apagar la Pi

### Problema
Al hacer sudo shutdown -h now, el UPS-Lite v1.3 sigue alimentando los pines GPIO
porque es pasivo (pass-through). Los sensores (BMP280, AHT20, GPS) siguen
consumiendo bateria.

### Solucion (requiere HW)
Poner MOSFET de canal P entre salida 5V del UPS y los sensores:
- Gate controlado por GPIO de la Pi
- Script pre-shutdown: GPIO LOW -> corta alimentacion a sensores
- Script de arranque (rc.local): GPIO HIGH -> enciende sensores

### Diagrama
  UPS-Lite 5V -> [MOSFET P-Ch] -> Sensores (5V)
                     |
                  GPIO (control)

### Esfuerzo: HW bajo, SW bajo (systemd + rc.local)
### Prioridad: ALTA (ahorro de bateria)

---

## 4. Auto Power-On al conectar fuente externa

### Problema
El UPS-Lite v1.3 tiene pads para detectar alimentacion externa en GPIO4,
pero solo detecta, no enciende automaticamente la Pi.

### Solucion posible
1. Puentear pads del UPS-Lite para habilitar deteccion en GPIO4
2. Configurar Wake-on-GPIO en la Pi (dtoverlay)
3. Conectar GPIO4 al pin RUN de la Pi para despertarla desde shutdown

### Alternativa: cambiar a UPS-Lite v3 o Mausberry que tienen esto nativo

### Esfuerzo: HW medio (puentear + cable a RUN), SW bajo
### Prioridad: BAJA (la bateria dura horas apagada)

---

## 5. Voltajes de referencia (LiPo 1S)

SOC  | Descanso | Cargando
100%% | 4.20V    | 4.20V
90%%  | 4.10V    | 4.15V
80%%  | 4.00V    | 4.08V
70%%  | 3.90V    | 3.98V
60%%  | 3.80V    | 3.88V
50%%  | 3.75V    | 3.80V
40%%  | 3.70V    | 3.75V
30%%  | 3.65V    | 3.70V
20%%  | 3.58V    | 3.63V
10%%  | 3.45V    | 3.50V
0%%   | 3.00V    | --
Corte HW | 2.70V | --

Nota: El CW2015 ya tiene modelo interno para SOC. Usar SOC en vez de voltaje
para el indicador de bateria (la curva voltaje-SOC no es lineal).

---

## 6. Monitoreo de corriente (futuro)
CW2015 puede reportar corriente (reg 0x06) pero el UPS-Lite no tiene shunt.
Para medir consumo real, agregar INA219 por I2C.
### Prioridad: BAJA

---

## Nota: CW2015 se autocalibra solo
Tras 2-3 ciclos completos de carga/descarga, el chip ajusta su modelo interno.
No necesita learning cycle manual.


# Backlog: UPS-Lite v1.3 SW-only Ideas (planned)

## Prioridad: MEDIA
- [ ] Runtime remaining estimation: track discharge rate, show "~Xh" in dashboard
- [ ] Daily battery health log: write bat_voltage + SOC to JSON file every hour
- [ ] Charge cycle counter: track cumulative SOC changes, store in cycles.json
- [ ] Adaptive shutdown threshold: higher during rides (30%%), lower when idle (15%%)
- [ ] Charging completion notification: flash/alert when SOC reaches 100%%

## Prioridad: BAJA
- [ ] Historical battery graph: plot voltage over last 24h in dashboard
- [ ] Battery degradation trend: compare voltage at same SOC over weeks
- [ ] System health journal: JSON log of all detected issues

---

# Backlog: UPS-Lite v1.3 HW Modifications (requires soldering)

## Prioridad: ALTA
- [ ] MOSFET power switch for sensors: cut 5V to BMP/AHT/GPS when Pi shuts down
  Components: 1x IRLML6402 (P-Ch MOSFET), 1x 10K resistor, 1x breadboard
  GPIO control: HIGH = sensors ON, LOW = sensors OFF
  Script: systemd pre-shutdown -> GPIO LOW, rc.local -> GPIO HIGH

## Prioridad: MEDIA
- [ ] Charge limiter at 80%%: MOSFET + GPIO to disconnect charger when SOC >= 80%%
  Concept: CW2015 reads SOC -> GPIO toggles charger enable -> stops charging
  Reconnect when SOC < 70%% for hysteresis

## Prioridad: BAJA
- [ ] Wake-on-GPIO: connect UPS-Lite power detect pad to Pi RUN pin
  Requires: solder pads on UPS-Lite, wire to Pi header
  Effect: Pi turns on when USB power connected
- [ ] INA219 current sensor for precise power consumption monitoring

---
