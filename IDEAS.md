<!-- INST
purpose: exploratory ideas — threads, not tasks
action:  read-only reference; never auto-convert to BACKLOG
         user decides which idea to pull; when they do, move entry to BACKLOG
add:     one entry per session max, only from creative mode or end-of-session finds
delete:  never (entries move to BACKLOG or Descartadas, file persists)
INST_END -->
# IDEAS.md — Vertientes sin explorar

> Generado por Claude en modo creativo o al cerrar sesiones.
> No son tareas. Son hilos. El usuario decide cuál jalar.
> Cuando una idea se convierte en tarea → mover a BACKLOG.md

## Pendientes de evaluar

### IDEA-001 — Kalman Filter fusión VSS + GPS
**Señal:** VS_KPH + gps_speed_kmh (ambas en CSV, nunca fusionadas)
**Técnica:** Filtro de Kalman — combina señales ruidosas con
pesos dinámicos según confianza de cada fuente
**Aplica a:** dv/dt para VDYNO — el talón de Aquiles actual
**Por qué importa:** mejor aceleración estimada = mejor dyno virtual

### IDEA-002 — Causal inference para veredicto de quemada
**Señal:** todas las variables ambientales + mapa + resultado
**Técnica:** inferencia causal (DoWhy, DAGs) — distingue
"mapa B produce más potencia" de "mapa B causa más potencia"
**Aplica a:** VDYNO veredicto — actualmente es correlación pura
**Por qué importa:** con ruido ambiental alto, la causalidad
es lo único que da veredicto confiable

### IDEA-003 — Estilo de manejo como señal, no como ruido
**Señal:** secuencias de TPS, RPM, gear a lo largo del tiempo
**Técnica:** Hidden Markov Models — detectar estados latentes
(agresivo, suave, ciudad, carretera) sin reglas hardcodeadas
**Aplica a:** normalización de comparaciones cross-session
**Por qué importa:** dos rides del mismo mapa con estilos
distintos no son comparables — HMM los clasifica automáticamente

### IDEA-004 — Fan + Voltage durante WOT: el estabilizador olvidado
**Señal:** Fan_Stat + Voltage + pw1 + spark1 (todas en CSV, nunca correlacionadas)
**Técnica:** Ventana deslizante — medir delta_V durante eventos WOT vs fan ON/OFF
**Aplica a:** VDYNO consistencia — pulls con fan ON tienen alternador bajo carga
**Por qué importa:** El fan consume ~3-4A. Si el voltaje cae durante un WOT pull porque el fan estaba encendido, la bobina recibe menos energía → chispa más débil → menos potencia. El VDYNO podría estar comparando pulls con fan ON vs OFF sin saberlo. Fan_Stat se loggea pero no se usa en ningún análisis.

### IDEA-005 — CDiag como minería de fallos incipientes
**Señal:** CDiag bytes (5 bytes, 40 bits de diagnóstico — loggeados pero nunca minados)
**Técnica:** Análisis de frecuencia — ¿qué bits de CDiag se activan en rides previas a un DTC?
**Aplica a:** Mantenimiento predictivo — detectar fallos eléctricos/actuadores antes de que fallen
**Por qué importa:** La ECU pone bits de diagnóstico mucho antes de encender la CEL. Podrían predecir: inyector degradándose, bobina perdiendo aislamiento, fallo de bujía incipiente. Todos los CDiag y HDiag bytes se descartan hoy.

### IDEA-006 — Micro-ciclos térmicos: CLT + fl_hot + do_fan como modelo de sistema
**Señal:** CLT + fl_hot + do_fan (todas loggeadas, nunca modeladas juntas)
**Técnica:** Modelo de primer orden — CLT(t) = CLT_inf + (CLT_0 - CLT_inf) * exp(-t/τ)
**Aplica a:** Normalización de comparaciones — etiquetar cada evento F7 con estado térmico real
**Por qué importa:** do_fan se cicla (CLT sube-baja ~6°C de histéresis). Un evento F7 en subida térmica (fan OFF) vs bajada (fan ON) son condiciones distintas. Hoy se clasifican igual si CLT > 80°C.

### IDEA-007 — gps_heading como etiquetador de tramo
**Señal:** gps_heading (rumbo cardinal absoluto, 0-360)
**Técnica:** Agrupar eventos F7 por heading → mismo tramo de ruta, diferentes sesiones
**Aplica a:** Normalización cross-session — comparar el mismo tramo elimina ruido geográfico
**Por qué importa:** gps_heading se loggea pero nadie lo analiza. En una ruta conocida, heading identifica exactamente qué segmento se estaba manejando, permitiendo comparar PW en ese tramo exacto entre sesiones con distintos mapas.

### IDEA-008 — fl_cam_active como filtro de calidad de ignición
**Señal:** fl_cam_active (flag de sensor de leva sincronizado)
**Técnica:** Si fl_cam_active se desactiva durante WOT, marcar ese evento F7 como baja confianza
**Aplica a:** F7 event quality — descartar eventos donde la sincronía de leva se perdió
**Por qué importa:** Si el sensor de leva pierde sincronía, el timing de chispa/inyección puede estar desfasado. La curva PW de ese evento no es confiable. Nadie lo verifica hoy.

### IDEA-009 — VSS_Count raw tiene más resolución que VS_KPH
**Señal:** VSS_Count (contador crudo de pulsos VSS, 0-255)
**Técnica:** Usar raw count en vez de VS_KPH para mediciones de corta distancia (lanzamientos)
**Aplica a:** Launch analysis — distancias <50m tienen error grande con KPH redondeado
**Por qué importa:** VS_KPH se deriva de VSS_Count pero redondea y filtra. El raw count tiene cuantización de ~1.2 km/h por pulso. Para aceleración en ventanas de 1-2s, el raw es mejor señal. VSS_Count se loggea pero nunca se usa directamente.

### IDEA-010 — ETS_ADC como ventana a la combustión real
**Señal:** ETS_ADC (sensor de temperatura de escape, ADC crudo)
**Técnica:** Correlacionar ETS + spark1 + pw1 — si ETS sube sin cambio de PW, hay combustión anómala
**Aplica a:** Detección de knocking sin sensor de knock — escape más caliente indica detonación
**Por qué importa:** ETS es el único sensor que mide calor real de salida del cilindro. Sin knock sensor, es la mejor señal indirecta de detonación. Nunca se usa en análisis.

### IDEA-011 — cpu_temp como indicador de calidad serial
**Señal:** cpu_temp + dirty_byte_count + tasa de error
**Técnica:** Correlación temporal — cuando cpu_temp > 75°C, ¿aumenta la tasa de dirty_bytes?
**Aplica a:** Diagnóstico de desconexiones — explicar patrones de pérdida de datos
**Por qué importa:** El FTDI puede tener errores cuando la Pi se calienta. Ambas señales están en el CSV. Si hay correlación, explica ciertos patrones de desconexión sin causa identificada hoy.

### IDEA-012 — do_coil + spark como detector de fallo de ignición
**Señal:** do_coil1/do_coil2 (comando ECU) + spark1/spark2 (avance real)
**Técnica:** Si do_coil1=1 pero spark1 no sube → ECU ordena pero no ejecuta
**Aplica a:** Mantenimiento predictivo — detectar bobina o bujía degradada antes de que falle
**Por qué importa:** La ECU ordena chispa (do_coil) pero el avance real (spark) es independiente. Una divergencia persistente es un DTC incipiente que nadie está minando.

### IDEA-013 — Perfil RPM como huella de estilo de manejo
**Señal:** Tiempo acumulado por celda (RPM × Load) del CellTracker
**Técnica:** Vector de distribución — % de tiempo en cada bin como feature de 12 dimensiones
**Aplica a:** Normalización cross-session — clasificar rides por perfil antes de comparar
**Por qué importa:** El CellTracker ya acumula tiempo por celda. Ese vector es una huella del estilo. Dos sesiones con mapas diferentes pero estilos diferentes no son directamente comparables. Similar a IDEA-003 (HMM) pero más simple — usa datos ya calculados.

### IDEA-014 — gps_turning como filtro de calidad en eventos F7
**Señal:** gps_heading_rate (Fase 2 GPS) — tasa de cambio de rumbo en deg/s durante el evento
**Técnica:** Filtrar eventos F7 donde el pre-event window incluye gps_turning=True
**Aplica a:** f7.py event detection — el detector actual asume que la moto va recto
**Por qué importa:** Un evento WOT en curva mezcla carga lateral con carga longitudinal.
La curva PW en curva no es comparable con PW en recta aunque RPM/TPS sean iguales.
Hoy se clasifican igual. Si gps_heading_rate > 15 deg/s durante el pre-event, el
evento debería marcarse como `quality: TURNING` y excluirse del promedio cross-session.
**Dato clave:** Require Fase 2 GPS (gps_heading_rate). Sin GPS, no se puede implementar.
**Impacto esperado:** Reduce ruido en comparaciones cross-session de eventos con motos
que toman curvas rápido antes del WOT (típico en calles de ciudad).

### IDEA-015 — GPS quality score compuesto como gate único para todo análisis
**Señal:** gps_mode + gps_epx + gps_snr_avg + gps_stale (Fase 1 + Fase 2 GPS)
**Técnica:** Score 0–1: `(mode==3)*0.4 + (epx<8)*0.3 + (snr_avg>30)*0.2 + (!stale)*0.1`
**Aplica a:** Cualquier análisis que consuma GPS: Sessions VS alt classification,
F7 event quality, VDYNO track mapping, BL-BUG-02 VSS calibration
**Por qué importa:** Hoy cada consumidor de GPS tiene su propio criterio ad-hoc:
launch.py usa `gps_valid`, BL-BUG-02 propone `hdop < 2.0`, Sessions VS usa `gps_valid`.
Un score único evita que se implemente n veces con distintos umbrales.
Threshold sugerido: `gps_quality >= 0.6` para análisis de precisión, `>= 0.4` para logging.
**Requiere:** Fase 1 (epx) + Fase 2 (snr_avg) ambas en CSV — ver BL-GPS-01 en BACKLOG.

### IDEA-016 — Intervalo de confianza bootstrap para VDYNO
**Señal:** Múltiples pulls WOT en una misma sesión (datos existentes, no se agrupan estadísticamente)
**Técnica:** Bootstrap no paramétrico — remuestrear los pulls WOT, calcular potencia media por bin RPM con IC 95%
**Aplica a:** vdyno.py::compare_sessions() — el veredicto actual es "mapa A da más potencia que B" sin decir qué tan seguro es
**Por qué importa:** Sin intervalo de confianza, no sabes si una diferencia de 2 HP es real o es ruido.
**Dato concreto:** Si una sesión tiene 8 pulls WOT y otra tiene 6, bootstrap con 1000 remuestreos da distribución de la diferencia. Hoy no se hace.

### IDEA-017 — Corrección por densidad de aire (SAE J1349)
**Señal:** IAT + baro_hPa — ambas en el CSV, nunca usadas en VDYNO
**Técnica:** Factor SAE J1349 — potencia corregida = potencia medida * (29.23 / baro_inHg) * sqrt((IAT_F + 460) / 537)
**Aplica a:** vdyno.py::_seg_physics() — normalizar potencia a condiciones estándar
**Por qué importa:** Un día frío vs uno caliente cambia la densidad del aire ~10%. Corregir elimina ese ruido.
**Dato concreto:** IAT y baro_hPa ya están en el CSV por fila. Solo hay que aplicarlos.

### IDEA-018 — Umbral adaptativo de detección de launch
**Señal:** dtps histórico por sesión vs umbral fijo de 8.0
**Técnica:** Media móvil + 2-sigma del dtps en ventana de 1s antes del evento
**Aplica a:** launch.py::detect_launches() — reemplazar min_dtps=8.0 fijo por uno dinámico
**Por qué importa:** En ciudad con tráfico el umbral de 8.0 da falsos positivos. En carretera da falsos negativos. Adaptativo resuelve ambos.
**Dato concreto:** dtps = 8.0 significa apertura de 8% en ~50ms. Funciona para un estilo de manejo específico solamente.

### IDEA-019 — Climb rate: vertical power loss silently corrupting VDYNO
**Señal:** `climb` field in gpsd TPV messages — vertical speed in m/s (currently ignored by reader.py)
**Técnica:** Add gravitational component to _seg_physics():
`F_gravity = mass_kg * 9.81 * sin(arctan(climb_ms / vss_ms))`
Add to F before computing P_w. On downhill pulls, subtract it.
**Aplica a:** vdyno.py::_seg_physics() — the flat-road assumption is baked in and never questioned
**Por qué importa:** At 80 km/h climbing at 3 m/s, slope ≈ 7.6°. For 250 kg bike+rider,
F_gravity ≈ 320 N. That's ~7% phantom power inflation on uphill WOT pulls.
Downhill pulls are deflated by the same amount. Cross-session comparison where
one pull was uphill and the other downhill can produce a fake ~14% power difference.
**Dato concreto:** `climb` is already sent by gpsd in the TPV message — it's a 1-line
addition to reader.py to capture it. Then 1 line in protocol.py for CSV, and the
correction formula in vdyno.py. J1349 + climb together = truly normalized VDYNO.
**Requiere:** Add `climb` to GPSFix, CSV_COLUMNS, and _seg_physics().

### IDEA-020 — HDOP from SKY messages: the quality metric gpsd already computes for us
**Señal:** `hdop`, `vdop`, `pdop` fields in gpsd SKY messages — currently we ignore all of them
**Técnica:** Log hdop to CSV. Use as primary quality gate: HDOP < 1.5 = excellent,
< 2.5 = good, > 4 = unreliable. Replace or anchor the ad-hoc epx check in IDEA-015.
**Aplica a:** GPS quality score (IDEA-015), VDYNO track mapping, Sessions VS alt classification
**Por qué importa:** HDOP is a single, universally understood number that encodes satellite
geometry (not just count). epx is device-specific and hardware-calibrated. HDOP < 2
is the SAE standard threshold for "usable" GPS. Using HDOP means the quality gate
speaks a language that any GPS reference book validates.
**Dato concreto:** SKY message already arrives — we parse it for satellite count and SNR
but skip hdop entirely. It's a 2-line addition to reader.py and 1 column in protocol.py.
Combining hdop + snr_avg gives the most informative quality pair possible from a passive receiver.
**Requiere:** Add `hdop` to GPSFix and CSV_COLUMNS. Update IDEA-015 score formula.

### IDEA-021 — GPS idle disconnect: stop burning CPU when the bike is parked
**Señal:** GPSReader holds `?WATCH={"enable":true}` 24/7, even when no ride is recording
**Técnica:** Integrate with session lifecycle — on ride_stop, send `?WATCH={"enable":false}`;
on ride_start, send `?WATCH={"enable":true, "json":true}`. gpsd drops polling rate
and stops forwarding JSON to unregistered clients, reducing CPU wake-ups.
**Aplica a:** main.py or ecu/session.py — wherever ride start/stop events fire
**Por qué importa:** Pi Zero 2W has 1 ARM core at 1 GHz. The GPS thread runs a readline()
loop that wakes the CPU on every gpsd message (~1 Hz). When parked with the logger on but
not recording, this is pure waste. The GPS still keeps its fix (gpsd stays running),
so reconnecting on ride start recovers a fix in <1s (warm start — the "faster satellite
detection" the user observed is this same mechanism). This is likely what freebuff
described as "low consumption when inactive."
**Requiere:** Add pause()/resume() methods to GPSReader. Wire to session start/stop.
No hardware changes — pure software. Risk: if ride detection fires before GPS resumes,
first 1-2 seconds of GPS data could be missing. Mitigate with resume() in ride_arm().

### IDEA-022 — Stator failure early warning via fan load impulse
**Señal:** do_fan (0→1 edges, hundreds per session) + Batt_V (logged every sample at 4.6 Hz)
**Técnica:** Detect each do_fan 0→1 transition. Measure Batt_V droop: steady-state before
vs nadir in the first 2-3 seconds after. Match by RPM bucket (charging output varies by RPM).
Track droop magnitude across rides chronologically. Rising droop at fixed RPM = stator/regulator
source impedance increasing = approaching failure.
**Aplica a:** Predictive maintenance — XB12X stator is the #1 known failure mode.
Kills alternator, kills battery, strands rider. This data is already being logged.
**Por qué importa:** The fan creates a free impedance test at a known current step (~10A)
hundreds of times per session. Across 70+ rides that's longitudinal impedance spectroscopy
with zero new hardware. A dying stator shows rising droop weeks before voltage warnings appear.
**Dato clave:** IDEA-004 also uses Batt_V + do_fan but for VDYNO consistency (WOT window).
This uses the fan STARTUP transient — different extraction window, different signal. Complement.
**Requiere:** Post-ride job similar to f7.py. No new hardware. numpy already on Pi.

### IDEA-023 — Map evolution as trajectory in 312-dimensional fuel space
**Señal:** fuel_front (12×13=156 values) + fuel_rear (12×13=156 values) = 312-float vector per map
**Técnica:** Each EEPROM map = point in R^312. Sequence of burns = trajectory through that space.
Key question: is the trajectory CONVERGING (contracting toward a point = found it) or OSCILLATING
(cycling = chasing noise)? Cosine similarity between consecutive maps quantifies direction.
PCA to 2D makes the trajectory visual.
**Aplica a:** Meta-level tuning insight — beyond per-burn verdicts, tells whether the tuning
PROCESS is working. Also powers maps_knowledge.db nearest-neighbor search (BACKLOG.md).
**Por qué importa:** Each burn gives BETTER/WORSE/GRAY. But you never see the arc.
"Your last 6 burns are converging toward this region" is actionable.
"They're cycling" is a signal to change strategy, not keep burning.
**Requiere:** maps_knowledge.db (BACKLOG.md) as foundation. numpy cosine similarity is enough
— no PCA needed for distance. Visualization optional.

### IDEA-024 — cc_per_ms calibration drift as injector wear indicator
**Señal:** cc_per_ms per fill-up cycle (auto-calibrated by FASE 8 BL-FUEL-12) + pw2/pw1 ratio
**Técnica:** The calibration constant converges toward a stable value across cycles.
Systematic drift upward over 10+ cycles = injector flow decreasing (clog/wear),
corrected for pressure (stable at 49-51 PSI) and ethanol changes (octane field).
The residual trend is injector health. pw2/pw1 at matched conditions diagnoses which cylinder.
**Aplica a:** Predictive maintenance — clogged injector = lean cell, invisible in OL without WB.
Heat-cycled air-cooled Buell = aggressive environment for injector tips.
**Por qué importa:** The calibration loop runs anyway for fuel level accuracy.
The injector wear signal is FREE — it's the byproduct of a loop already planned.
Today BL-FUEL-12 flags individual discrepancies but doesn't track the TREND.
Trend > 1.03/cycle for 5+ cycles = schedule injector cleaning. One insight, ~10 lines.
**Dato clave:** If cc_per_ms drifts but pw2/pw1 stays stable → fuel pump pressure drop.
If pw2/pw1 shifts → one injector specifically. Same data, different diagnosis.
**Requiere:** FASE 8 running + ≥5 fill-up cycles for trend to exceed noise floor.

### IDEA-025 — Weather as natural lambda sweep without a wideband
**Señal:** baro_hPa + baro_temp_c (air density per sample) + F7 WOT events (acceleration curves)
**Técnica:** DDFI2 Alpha-N has no KBaro — fuel doesn't compensate for density.
Dense day (cold, low alt) → engine gets more oxygen at same TPS → mixture goes LEAN.
If acceleration is better than the density gain predicts, the cell is rich of best power.
If worse, it's already lean. Cross F7 events by density quartile to classify per cell.
**Aplica a:** F7 analysis — enrich per-cell verdicts with a lean/rich tag from physics,
no wideband required. Feeds into FASE 6 proposals as a third signal.
**Por qué importa:** 70+ rides of varying density already on disk = natural experiment.
Weather was doing lambda sweeps every time the rider climbed or descended elevation.
Even a rough "this cell is probably rich" removes ambiguity in the proposal.
**Dato clave:** Check density histogram first. If 95% of rides are within ±1% density,
spread is too small. gps_alt_m is the best proxy — a 1000m altitude difference = ~12% density drop.
**Requiere:** ρ = baro_hPa / (287.058 × (baro_temp_c + 273.15)) per sample.
Group F7 events by density quartile. No new data collection.

### IDEA-026 — Engine wear isolated via repeated GPS segments
**Señal:** GPS coordinates + VDYNO power per segment + map checksum (same map = control variable)
**Técnica:** Find rides where: same GPS corridor (within ~50m), same density conditions (±2%),
same map checksum. Across rides meeting all three conditions, any downward VDYNO power trend
= engine wear, not tuning. Map is the control variable; time is the independent variable.
**Aplica a:** VDYNO long-term — beyond single-burn comparisons, tracks mechanical health
over the life of the project. Separates "map effect" from "ring/valve wear."
**Por qué importa:** Every comparison controls for conditions but not engine health.
After 10,000+ km the engine is different. Isolating wear requires the same experiment
repeated under the same conditions — GPS segments + density matching makes this possible
with data already being collected.
**Dato clave:** BL-VD-06 (instructor de evidencia) could include "ride this segment again
to update engine health baseline" in its mission list — same infrastructure, dual use.
**Requiere:** GPS Fase 1 in CSV (BL-GPS-01, not yet persisted). VDYNO (BL-VD-01).
Meaningful after ≥5 qualifying rides on the same segment.

### IDEA-027 — Ghost lap: two rides synchronized by distance, not time
**Señal:** gps_lat/gps_lon per CSV row + user-marked start point + full telemetry (RPM, PW, VS_KPH, etc.)
**Técnica:** Ghost lap / telemetry overlay — standard in motorsport (MoTeC, AiM, Racelogic).
The critical insight is synchronization by cumulative GPS distance from a user-defined start
point, NOT by timestamp. At meter 250, both rides are at the same physical location regardless
of when they arrived. A shared distance-axis cursor advances both rides simultaneously, showing:
- Two ghost markers on the Leaflet map (one per ride, same-position-in-route at any cursor position)
- Dual telemetry overlay on the chart: RPM, PW, VS_KPH vs distance for both rides
- Time delta at each distance point (how many seconds one ride leads the other)
The user marks the start point on the GPS Analysis map (click → "Set lap start here").
Distance = cumulative haversine sum from that point forward.
**Aplica a:** Three use cases, same implementation:
1. **Lap comparison** — same route, different sessions/maps: which lap was faster and why?
2. **Drag strip** — same 400m segment, two runs: winner + telemetry diff (did I shift earlier? more PW?)
3. **Pull comparison** — 300m segment where you always WOT: IDEA-026's engine wear baseline
**Por qué importa:** Sessions VS already tells you which map has better average dpw per cell.
Ghost lap tells you the WHY at a specific moment in a specific place. You see exactly where
one ride pulls ahead and what RPM/TPS/PW was different at that meter. The story goes from
"Map A produced better pulls overall" to "Map A was 0.4s faster through the uphill and
the RPM at meter 180 was 400 higher — that's where it diverged." Unmissable for tuning.
**Dato clave:** The time-sync temptation is wrong. If you sync by wall-clock offset, within
30 seconds the two ghost markers are physically far apart (different speeds, traffic stops).
Distance-sync keeps them at the same road location always. This is the non-obvious part that
separates working implementations from broken ones.
**Requiere:** GPS Fase 1 in CSV (BL-GPS-01, not yet persisted — gps_lat/gps_lon/gps_speed_kmh).
Start-point picker UI in GPS Analysis map (Leaflet click handler, stores lat/lon + row index).
Haversine distance accumulation (already used elsewhere in the codebase). Dual-trace renderer
on the existing uPlot or canvas chart in GPS Analysis. No new data collection needed beyond GPS Fase 1.

### IDEA-028 — Prior art check: where this project sits vs. published MBC / system-ID work
**Señal:** N/A — literature/prior-art research, not a data signal from the CSV.
**Técnica:** Web search across three tiers of related work: (1) hobbyist ECU auto-tune
(MegaSquirt VE Analyze Live, Speeduino, HP Tuners self-learn) — all require a wideband O2
as the closed-loop error signal, none work without one; (2) OEM/academic on-road calibration
via Bayesian optimization + Gaussian Process, 2025-2026 papers — closest in spirit (learn
directly on the vehicle, no dyno) but still anchor to a measured ground-truth output
(AFR/NOx/torque) and carry formal uncertainty quantification (posterior variance) plus
algorithmic safety constraints; (3) MathWorks Model-Based Calibration Toolbox — classic
dyno + DoE with designed excitation signals (RPM/load sweeps), the opposite of street logging.
No published tool or paper was found doing DTW-based curve matching (TPS shape) to pair
equivalent events across sessions/maps for tuning validation — this looks like a genuinely
uncommon technique in this domain, worth treating as a potential differentiator, not just
an internal implementation detail.
**Aplica a:** Project framing / positioning. Also names three concrete gaps against the
state of the art: no uncertainty quantification beyond GAP 5's convergence variance, no
designed/persistent excitation (F7's DTW event pairing is a partial mitigation, not a
formal substitute), no algorithmic safety-constrained optimization (burn decision is
human-reviewed instead).
**Por qué importa — the reframe that matters:** the user's own framing on the "designed
excitation" gap: a dyno + DoE protocol is faster per iteration only because the sampled
space is deliberately bounded — it tests a controlled grid, not the real operating envelope.
This project's approach is slower per iteration because real-street data is dispersed across
whatever the rider and the road actually produced, but that dispersion is not noise to be
eliminated — it IS the joint distribution of real-world use (weather, elevation, thermal
cycles, traffic patterns, throttle behavior) that a lab protocol never samples and therefore
can never document, even in principle. What's traded for speed in the lab is coverage; this
project buys coverage of conditions that no dynamometer test plan will ever contain a record
of. The lab produces a faster answer to a narrower question. This project is the only place
where evidence of those specific real-world operating conditions — and how the ECU actually
behaved in them — exists at all.
**Dato clave:** the closest published parallel (fleet-based Bayesian optimization / GP
calibration directly on vehicles, no dyno) validates that "learn continuously from real
operating data instead of a lab grid" is a principled approach elsewhere too — not just a
budget workaround for lacking a dyno. The gap vs. that literature is formal uncertainty
quantification and safety-constrained search, not the on-road premise itself.
**Requiere:** nothing new to build. This is a positioning note — useful context if any of
this ever gets written up (forum post, short paper) or when deciding priority between
GAP 5-style convergence stats vs. new signal sources.
**Actualización 2026-07-03 — the strongest confirmation yet (freebuff task_008, Germany):**
Germany is the one industry with a name and decades of practice for exactly our approach —
**Straßenapplikation** (road-based calibration, pre-2010) — and the industry's own history
is a direct answer to the tension the user named this session: *"todos se van al banco de
prueba porque se puede medir, es medible y confiable, pero si dejamos fuera las pruebas de
calle estamos dejando el crecimiento iterativo de mejora continua — el banco es estático,
la calle es dinámica."* Germany faced that exact tradeoff and chose the opposite side:
low reproducibility on real roads was judged not worth the dynamic realism, so the industry
moved to **Road-to-Rig (R2R)** — capture real driving data, then replay it as a *fixed*
boundary condition back on a dyno. That is the static side winning by design: real-world
richness gets sampled once, then frozen and reproduced, not lived with and re-measured ride
after ride. Their own engineering literature calls the newest step **Virtuelle Applikation**
— full digital-twin calibration where road data is explicitly demoted to *validation only*,
never the source of a proposed change. Every region searched so far (English academic +
hobbyist, China, now Germany) shows the identical pattern: the industry-grade path always
resolves the static/dynamic tension by making the street data static (freeze it into a rig
replay or a validation snapshot). This project resolves it the other way: it keeps logging
open-ended and dynamic, and instead builds the statistics to survive that (GAP1 Welch CI,
F7 DTW event matching, GAP5 convergence) rather than freezing the input. Neither resolution
is free — Germany buys reproducibility, this project buys the continuously-growing dataset
of real operating conditions no rig replay set was ever built to contain. That trade, stated
explicitly, is the cleanest one-paragraph pitch for why this project's method exists at all.
**German Differenzkennfeld** (map-A minus map-B) is literally our dpw_eff × ddvss matrix —
their own comparison method, minus the automated proposal step we already do on top of it.

### IDEA-029 — Virtual combustion sensors: no-wideband paths from global ICE literature (freebuff tasks 006+007)
**Señal:** RPM, PW, TPS, CLT, baro/IAT already logged; ion current/ignition-waveform would need new hardware.
**Técnica:** China sweep (task_006, re-run after broadening scope from motorcycle-only to general ICE)
plus the Russian gray-literature sweep (task_007) surfaced four veins:
1. **Neural-network virtual lambda** (Elman/RNN/LSTM/BP estimating AFR from MAP/RPM/IAT/PW) —
   SAE 2005-24-058, SAE 2006-01-1348, Turkson 2016 (survey). **The catch freebuff did not
   flag:** training needs measured lambda as ground truth — chicken-and-egg without a
   wideband. Only viable on borrowed dyno data (transfer quality unknown) or after a
   temporary wideband session, at which point it becomes a way to KEEP the wideband's
   knowledge after removing the sensor. That reframing is the actually useful version.
2. **Transient AFR / fuel-film (wall-wetting) modeling during throttle transients** —
   task_006 flagged LSTM models specifically for the transient window where a physical O2
   sensor has 0.5-2s transport lag; separately flagged EKF fuel-puddle models for
   port-injected engines. **Update (task_006 re-run, intensive mode):** freebuff found the
   citation is even more specific than "port-injected engines in general" — Zhang Fujun,
   Beijing Institute of Technology (2005), *"Transient AFR Control Method for Motorcycle
   Engine Based on Fuel Film Model"* (北京理工大学学报), using throttle-position derivative +
   coolant temp as inputs to a fuel-film transfer-function compensator. That is our exact
   vehicle class. **This is the connection freebuff didn't make but is verifiable in our own
   code:** DDFI2 is port-injected, F7 events ARE throttle transients, and our ECU already
   logs an `AE` (accel enrichment) signal — which is the factory's own crude, uncalibrated
   compensation for wall-wetting, using the same two inputs (TPS derivative, CLT) as the
   cited model. AE during F7 events is a directly available, zero-new-hardware signal for
   exactly the phenomenon the literature says matters most, on the exact vehicle class studied.
3. **Crankshaft speed fluctuation (CSF) analysis**, now with CNN/LSTM per task_006 (misfire/
   combustion-quality/cylinder balance from RPM micro-variation). Published method needs
   crank-tooth resolution; our serial stream is ~10 Hz, out of reach as published. Cheap
   degraded proxy worth one experiment: per-cell RPM stability/jitter within stable buckets
   as a combustion-roughness signal — zero new hardware, data already on disk.
4. **Ignition-signal combustion diagnostics** — two independent hardware paths converge here:
   Chinese ion-current sensing (CN112160842B, spark plug as probe, ~$50-100 module) and the
   Russian Январь/chiptuner.ru practice of oscilloscope spark-duration analysis (>1ms healthy,
   <0.6-0.7ms = poor combustion/lean misfire) via a simple voltage divider on the ignition
   coil primary — much cheaper than ion-current, GPIO-feasible on the Pi. Both are per-cycle
   combustion feedback without touching the exhaust; the Russian version is the more buildable
   first step.
**Aplica a:** the absolute rich/lean direction gap — the whole current pipeline is relative
comparison (map A vs map B); these are candidate paths to an absolute mixture signal,
alongside the density-as-lambda-sweep idea (IDEA-025). Item 2 (AE during F7) is the only
one requiring zero new hardware or research — worth a standalone quick analysis.
**Dato clave — novelty confirmed a second and third time:** neither the Chinese nor the
Russian sweep found any prior art doing automated cross-session log comparison to propose
map changes — the Январь/Itelma scene (decades of open-loop tuning on ECUs structurally
similar to DDFI2: old, narrowband-only, serial-logged) does it manually in Excel. Their
"scale open-loop cells by the closed-loop-learned correction at stoich cells" method is
also an independent validation of our SWEET/SPICY/BITTER concept. This stacks with
IDEA-028 (English sweep) — three literature pools now say the same thing.
**Riesgo de las citas:** freebuff cites specific papers/patents (SAE numbers, CNKI patent
IDs, named researchers) that were NOT independently verified to exist as cited — same
caveat CLAUDE.md already gives for any freebuff claim. Treat citations as leads to check
before quoting externally, not as confirmed bibliography.
**Requiere:** (1) AE-during-F7 analysis: nothing, one script, data already on disk — do this
first; (2) RPM-stability proxy: nothing, one analysis script; (3) NN-VLS: a lambda
ground-truth source first; (4) ignition-waveform sensing: hardware R&D (Russian voltage-
divider approach is the cheaper starting point vs. ion current). Full source lists preserved
in freebuff task_006/task_007 responses (processed 2026-07-03, CHANGELOG v2.7.264/v2.7.265).

### IDEA-030 — RPM-only torque/manifold-pressure observer as a second, independent VDYNO estimator
**Señal:** RPM alone (no GPS, no accel) — genuinely different sensor input from VDYNO's current
GPS-acceleration-based power estimate.
**Técnica:** freebuff task_006 (China, re-run) surfaced CN110987452A/B (Northeast University,
2020/2021): a mean-value engine model plus a Lyapunov-stability observer that estimates intake
manifold pressure and torque **from the RPM signal alone**, with no pressure sensor. Also cited:
academic EKF/SMO observer literature for air-path/AFR estimation (Jilin, Tsinghua) that runs on
the same "infer an unmeasured internal state from an available signal" logic.
**Aplica a:** design rule 6 in BACKLOG_VDYNO.md — parallel processing paths are cheap, compute
both, document convergence. VDYNO (BL-VD-10, ΔHP→cell) currently has exactly one estimator of
engine output (GPS-measured acceleration × mass → power/torque). An RPM-only observer would be
a second, physically independent estimate of the same quantity from a different sensor path —
if the two agree, that's real cross-validation of VDYNO's core assumption; if they disagree in
a structured way (e.g. only at certain RPM×TPS cells), that disagreement is itself diagnostic
information about where the vehicle-as-dynamometer assumption breaks down (wind, grade, road
surface aren't observed by RPM but do show up in GPS-accel).
**Por qué importa:** this is not another "maybe someday" virtual sensor — it's a free second
opinion on a number the pipeline already computes and already trusts (VDYNO). Two independent
measurements of the same physical quantity, from unrelated data paths, converging or diverging,
is a stronger validation signal than either path's own confidence interval.
**Riesgo de las citas:** same caveat as IDEA-029 — patent numbers not independently verified to
exist as cited.
**Requiere:** implementing a mean-value-engine-model observer (the actual math from the cited
patent was not reproduced by freebuff, only the concept) — this is a real modeling task, not a
one-script analysis. Worth a scoping pass before committing effort: is RPM-only torque
estimation accurate enough on a V-twin with our sampling rate to be worth building.

### IDEA-031 — Gaussian Process Regression as the map-proposal surface (replaces/extends GAP1's discrete binning)
**Señal:** whatever cells already feed `_merge_maps`/GAP1 today (dpw_eff per RPM×TPS bin) — GPR
would consume the same data, not new data.
**Técnica:** freebuff task_008 (Germany) found this is the actual state of the art in the one
industry with a formal discipline for it: Tietze, N. (2015), *Model-based Calibration of Engine
Control Units Using Gaussian Process Regression*, TU Darmstadt — GP surrogate models of engine
maps that give a continuous surface AND a native uncertainty estimate at every point, instead of
per-cell independent statistics. A named extension, **Local GPR (LGPR)**, specifically handles
non-stationary dynamics and **ECU mode-switching** — i.e. exactly the warm-up/OL fl_hot
stratification question from [[project-pipeline-dataflow]]'s rule 7 debate, but solved as part
of the model instead of as a manual stratification step.
**Aplica a:** FASE 6 revival (proposal.py + smoothing.py recovery, planned but not started). The
old FASE 6 used IDW (inverse distance weighting) + Laplacian smoothing to interpolate between
cells with data. GPR is a principled replacement for that exact step: it would give the eco/
SWEET winner a real posterior variance instead of (or alongside) GAP1's per-cell Welch CI, and
would naturally interpolate into cells with sparse data instead of needing a separate smoothing
pass. This is the single most direct "upgrade our existing math" finding across all sweeps so far.
**Dato clave:** Germany's own comparison method, Differenzkennfeld (map A minus map B), is
literally our dpw_eff × ddvss matrix — meaning the German literature validates both ends of our
pipeline: the comparison step (Differenzkennfeld ≈ our matrix) and the proposal step (GPR as the
principled way to turn that matrix into a smoothed, uncertainty-aware map change).
**Riesgo de las citas:** dissertation link was given and looks real (tuprints.ulb.tu-darmstadt.de)
but has not been fetched/verified independently.
**Requiere:** a real evaluation task, not a quick script — read the Tietze dissertation (or a
GPR tutorial) enough to judge whether `scikit-learn`'s GaussianProcessRegressor is sufficient or
whether this needs a proper GP library; prototype on one map pair (91B225 vs 248AE2, the same
pair already used to validate GAP1) before deciding whether it replaces or augments GAP1.

### IDEA-032 — Brazilian flex-fuel virtual sensor: the reusable pattern, corrected for our actual constraint (freebuff task_009)
**Señal:** structurally, whatever we already use as a "correction magnitude" — dpw_eff between
two known maps — not a new signal.
**Técnica:** freebuff task_009 (Japan+India+Brazil, intensive) called Brazil's mass-production
virtual ethanol-content sensor (2003-present) "the single most important finding of the entire
research batch." The mechanism: on refuel, the ECU watches how much long-term fuel trim (LTFT)
correction the narrowband O2 feedback loop demands to hold stoichiometric, and maps that
correction magnitude to an ethanol percentage (small correction = mostly gasoline, large =
mostly ethanol), cross-checked against knock behavior (ethanol's higher octane resists knock at
advanced timing).
**Freebuff's overclaim, corrected:** its own comparison table admits the mechanism's input is
"O2 feedback + LTFT" — i.e. it requires a *working closed-loop narrowband sensor* as the error
signal. This project has no O2 feedback of any kind (EGO_Corr/AFV locked at 100.0, sensor
physically disconnected). So the specific algorithm does not transfer; our problem is strictly
harder than Brazil's (they infer one unknown FROM a working sensor, we have no sensor at all).
**What actually transfers is the pattern, not the algorithm:** "turn a correction/deviation
magnitude into a classification of an unmeasured property" is exactly what SWEET/SPICY/BITTER
already does — except our correction signal is dpw_eff (the fueling difference between two
*known* map states) instead of LTFT (the fueling difference between one map and a *live O2
target*). Brazil substitutes a live sensor for the reference point; we substitute a second
already-driven map. Production-proof that the general pattern works at scale is worth having,
but it does not hand us a shortcut — it validates a design choice we already made independently.
**Secondary items from the same task, same caveat pattern as IDEA-029/030/031 (assume O2 present):**
Japanese MPC for transient AFR (Takiyama 2015/2017, JSAE) — same F7-relevant transient-window
framing as the Chinese/German transient-AFR findings, but again modeled around a working O2
loop; Indian multi-gas exhaust analysis (CO%/HC%/CO2% from a portable analyzer instead of a
wideband) — the one finding here that's a genuinely different *hardware* alternative rather
than a pure-software inference, worth a line in a future hardware-options list alongside ion
current and voltage-divider spark sensing (IDEA-029 item 4).
**Dato clave:** fifth region searched (after English/US, China, Russia, Germany), fifth time no
automated cross-session log-comparison tool was found anywhere. The novelty claim in IDEA-028
keeps getting more load-bearing evidence, not less.
**Riesgo de las citas:** same standing caveat — SAE numbers (2017-36-0241, 2011-36-0057,
2008-36-0262) and JSAE DOIs not independently verified to exist as cited.
**Requiere:** nothing to build — this is a corrected positioning note, not a new technique.

## Descartadas

## Convertidas a BACKLOG
