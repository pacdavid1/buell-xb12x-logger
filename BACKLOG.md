# BACKLOG — Buell Logger / Tuner

## UX — Mejoras urgentes (2026-06-07)

### BL-UX-01 — Burn de propuesta completa (no celda por celda)
**Priority:** HIGH
**Pages:** Tuner (PROPOSAL tab)

El flujo correcto es: ver propuesta → editar si hace falta → quemar el mapa completo.
NO se quema celda por celda ni con límite de 20 celdas.
El PROPOSAL tab debe generar el mapa propuesto completo y quemarlo igual que el VE subtab:
generate MSQ → burn full EEPROM (usando la lógica existente de write_full_eeprom).
- Eliminar límite de 20 celdas del endpoint /eeprom/burn
- Eliminar límite de 20 celdas del JS en tuner.html (commitStage/burnStaged)
- PROPOSAL tab: botón BURN PROPOSAL quema el mapa suavizado completo (smoothed_pct),
  no las celdas staged manualmente

### BL-UX-02 — Tabs faltantes en navegación
**Priority:** HIGH
**Pages:** TBD (user reportó tabs que no aparecen)

Auditar el menú de navegación de todas las páginas y verificar que todos los tabs
estén presentes y visibles. Confirmar con el usuario cuáles faltan específicamente.

### BL-UX-03 — Baro como estadística del ride, no como factor de normalización PW
**Priority:** HIGH
**Pages:** Dashboard, Session Events, Sessions VS

El usuario cuestiona la normalización PW × (1013/baro):
- El baro SÍ afecta la densidad del aire y por lo tanto el PW correcto — la normalización
  es matemáticamente válida para comparar sesiones a distinta altitud.
- PERO: el baro debe ser VISIBLE como gráfica de estadísticas del ride, no un ajuste silencioso.
- Agregar en Session Events y Sessions VS: stats de baro promedio, altitud, temperatura ambiente
  y humedad para cada sesión comparada.
- El usuario debe poder ver: "sesión A a 870 hPa / 2200m, sesión B a 1010 hPa / 200m"
  y entender por qué los PW normalizados difieren de los raw.

### BL-UX-04 — Session Events: curva de muestra única se ve como línea delgada
**Priority:** MEDIUM
**Pages:** Session Events (session_events.html)

Cuando un cluster tiene n=1 evento, la curva se renderiza como línea muy delgada
(no tiene área de desviación std). Debe verse igual que clusters multi-muestra:
misma curva promedio, sin área sombreada si n=1 pero con el mismo grosor de línea.

### BL-UX-05 — Session Events: agregar stats ambientales por evento
**Priority:** MEDIUM
**Pages:** Session Events (session_events.html)

Incluir en cada evento/cluster: baro_hPa, gps_alt_m, gps_slope, temp_amb_c, humedad.
Mostrar como fila de stats debajo del gráfico o como tooltip al hover.
Permite ver: "este evento WOT fue cuesta arriba a 2100m y 28°C" —
contexto crítico para entender por qué el PW fue mayor o menor.

### BL-UX-06 — Dashboard: labels a la izquierda, rotados 90°, números más grandes
**Priority:** MEDIUM
**Pages:** Dashboard (index.html)

Actualmente: label del parámetro en la parte superior del contenedor, número abajo.
Cambio: label a la izquierda del contenedor, rotado 90° (texto vertical), número ocupa
todo el ancho restante → números visiblemente más grandes desde la moto.
Afecta el layout CSS de los contenedores de cada variable en index.html.

### BL-DDFI2-01 — Investigar y exponer parámetro de compensación barométrica de la DDFI2
**Priority:** CLOSED — freebuff research 2026-06-07: DDFI2 NO tiene KBaro/baro_comp nativo.
Stock DDFI-2 compensates via closed-loop AFV + narrow-band O2 (not a lookup table).
In OL mode (our setup), there is NO barometric compensation at all.
Use BMP280 (already reading) to display baro as ride stat only (BL-UX-03).
**Files:** ecu/eeprom.py, ecu/BUEIB.xml, web/server.py

La DDFI2 tiene un parámetro interno en EEPROM que ajusta la inyección por cambios
barométricos (altitud). EcmSpy puede leerlo y escribirlo. La Pi debería poder hacer lo mismo.

### Qué investigar (freebuff task pendiente)
1. Identificar el parámetro en BUEIB.xml — buscar: baro, altitude, KBaro, baro_comp, KAlt
   `grep -i 'baro\|altitude\|kalt\|kbaro' /home/pi/buell/ecu/BUEIB.xml | head -20`
2. Leer el valor actual del parámetro desde el EEPROM de una sesión
3. Entender el rango válido y la unidad (hPa? factor? offset?)
4. Diseñar el endpoint GET/POST /eeprom/baro_comp para leer y escribir el valor
5. Agregar al VE tab o Tuner: mostrar el valor actual y permitir ajustarlo

### Contexto importante
- La moto es Alpha-N: TPS+RPM determinan la inyección base
- Este parámetro es una corrección SOBRE esa base, no el cálculo principal
- No confundir con la normalización post-ride (PW × 1013/baro) que implementamos
  en f7.py/launch.py — esa es nuestra normalización de análisis, independiente del ECU
- El parámetro del ECU actúa en tiempo real durante la ride

---

---

## FASE 6 — Algoritmo: hallazgos de freebuff (tareas 001-006)

### Combinación F7 + Sessions VS (task 001 + 005)
- [ ] Usar PEAK TPS del evento (no Bucket_A TPS) para clasificar zona
  Zonas: WOT (peak>60%) → F7 priority | Mid (20-60%) → F7 blend | Light (<20%) → VS
- [ ] Mantener dos delta maps separados: f7_delta y vs_delta, fusionar por zona
  No promediar — son señales de objetivos distintos (aceleración vs eficiencia)
- [ ] Bias hacia rico cuando hay conflicto (seguridad en OL sin WB)
- [ ] Fórmula de confianza F7 (3 componentes):
  w_f7 = w_multi_session * w_dtw_quality * w_cross_match
  donde: w_multi_session=min(1, n_sessions/2), w_dtw_quality=avg_DTW_sim,
         w_cross_match=1.0 si hay par cross-session, 0.7 si orphan
- [ ] Cross-session matched pairs: bonus de confianza (1.0x vs 0.7x orphan)
- [ ] Probar: 2s stable bucket (vs 3s actual) y DTW 0.80 intra-sesión (vs 0.85)
  para reducir tasa de huérfanos del 97% actual
- [ ] Coverage mask por celda: marcar si dato es real, interpolado, o sin dato
- [ ] Front y rear maps fusionados INDEPENDIENTEMENTE (no mezclar cilindros)

### Suavizado del mapa (task 003)
- [ ] Dos pasos: 1) Interpolar celdas vacías (bilinear sin deps, bicubic con scipy)
               2) Laplacian sobre el delta COMPLETO (incluyendo interpoladas)
- [ ] Verificar si scipy está disponible en el Pi: python3 -c "import scipy; print('ok')"
- [ ] Orden correcto: computar delta → ponderar por confianza → CLAMP ±15% → interpolar → smooth → second clamp
- [ ] Terminación por convergencia (no por número fijo de iteraciones):
  Fuel: threshold=0.5 units, max 5 iter | Spark: threshold=0.1-0.2°, max 6 iter
- [ ] Bias asimétrico SOLO en la iteración final (no acumular):
  Fuel: rico x1.1 | Spark: retard x1.1
- [ ] Parámetros separados por tipo de mapa:
  Fuel: lambda=0.25 | Spark: lambda=0.10 (más conservador)
- [ ] NO suavizar a través de fronteras de zona (idle <1500 RPM, WOT >60% TPS)
  Suavizar cada zona independientemente
- [ ] Celdas con dato medido: aplicar smooth a lambda*0.5 (preservar señal real)
- [ ] Rear cylinder: lambda más conservador que front (corre 30-50°C más caliente)

### Spark map sin knock sensing (task 004)
- [ ] Limit ±2° por iteración, ±1° por celda (más estricto que fuel)
- [ ] Gate: solo advance si delta_vss > +3% | retard si delta_vss < -3%
  delta_vss > +5% → +1.0° | 3-5% → +0.5° | -3% a -5% → -0.5° | < -5% → -1.0°
- [ ] Default cuando no hay datos: -0.5° de retard de seguridad (NUNCA advance sin datos)
- [ ] Regla del 2-session: requerir 2+ pares independientes antes de cualquier advance
- [ ] NUNCA exceder el advance máximo de fábrica del ECU (es el límite de seguridad)
- [ ] Rear cylinder SIEMPRE 1-2° más retardado que front
- [ ] Fuel-before-spark ordering: aplicar cambios de fuel primero (2-3 iteraciones),
  luego spark. Fuel incorrecto contamina el delta_vss del spark.
- [ ] IAT retard: spark_retard = max(0, (iat - 40) * 0.07) grados (≈0.7°/10°C sobre 40°C)
- [ ] El DDFI2 SÍ tiene spark_front y spark_rear separados (confirmado en EEPROM)
- [ ] Agregar campo rider_notes a session_metadata.json: opciones (normal, knock_heard,
  hesitation, unknown) — el rider como sensor zero-cost
- [ ] Futuro: EGT sensor en cilindro trasero (~$40, Type-K + MAX6675) = mejor upgrade

### Normalización barométrica (task 006 — valida nuestra implementación)
- [ ] Nuestra implementación (row level, 1013.25 hPa, baro=0 skip) es CORRECTA ✅
- [ ] NO agregar corrección de temperatura — ECU ya maneja IAT en sus tablas
- [ ] Mejora pendiente: GPS altitude como fallback si baro=0:
  baro_est = 1013.25 * (1 - 0.0065 * gps_alt / 288.15) ** 5.255
  (válido para <3000m, precisión ±5 hPa)
- [ ] Validar rango baro: solo aplicar si 900 < baro < 1100 hPa
- [ ] Si >10% de rows sin baro válido en una sesión: skip normalization para esa sesión + flag
- [ ] Considerar: preservar pw1/pw2 raw y agregar pw1_norm/pw2_norm
  (actualmente modificamos pw1/pw2 in-place — design decision pendiente)
- [ ] Dashboard: mostrar avg_baro, baro_valid_pct, Δbaro por comparación

### Items pendientes para proposal.py v2 (freebuff tasks 010, 013)
- [ ] ddvss cross-check in proposal.py: dpw_eff alone doesn't say if B is better
  Cross-reference with ddvss: if dpw_eff<0 AND ddvss>0 → B more efficient (high conf)
  if dpw_eff<0 AND ddvss<0 → B leaner but less power (low conf). Add for v2.
- [ ] Handle pw1/pw2 data mismatch: if pw1 has signal for a cell but pw2 doesn't
  (or vice versa), the current code may apply 0.0 delta to the missing cylinder.
  Add explicit check: if pw2_a == 0, use pw1 delta as fallback for rear, flag as low-conf.

### Preguntas de freebuff que necesitan respuesta nuestra
- ¿scipy disponible en Pi? → verificar antes de implementar interpolación bicubic
- ¿Valores máximos de spark en los EEPROM.bin existentes? → extraer para definir ceiling
- ¿El tps_peak field existe en los f7events JSON? → SÍ, confirmado en f7.py
- ¿Existe infraestructura para acumular deltas cross-session? → NO, pendiente FASE 6

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



## CLEANUP — proposal.py cosmetic fixes (freebuff task 013)
- [ ] Move `_clamp` helper outside the VS row loop in generate_fuel_proposal()
      (currently defined inside loop — cosmetic, Python dogma, no perf impact)
- [ ] Track confidence separately for front and rear cylinders
      (currently shared confidence for both — fine for v1, needed for v2)
- [ ] Add side-by-side fuel_front / fuel_rear display in dashboard
      when proposal is viewed

## CLEANUP — Dead Code




## BUG — pw1/pw2 in load_csv() should be raw + add pw1_norm/pw2_norm
(Source: freebuff tasks 007, 008, 012)

**Priority: HIGH — current code modifies pw1/pw2 in-place, breaking detect_launches()**

### Problem
Current load_csv() in web/launch.py normalizes pw1/pw2 in-place:
  pw1 = sf(r['pw1']) * _baro_factor   <- raw value lost
detect_launches() reads pw1 expecting raw physical PW (milliseconds).
If thresholds are absolute (e.g. peak_pw > 15ms), baro normalization shifts them ~2-3%.

### Fix (freebuff task 012 — VERIFY CODE BEFORE APPLYING, snippets may not match actual code)
In load_csv() baro block:
  1. Change guard: _baro_valid = 900 < _baro < 1100  (not just > 0)
  2. Keep pw1/pw2 raw: 'pw1': sf(r['pw1']),  'pw2': sf(r.get('pw2', 0))
  3. Add normalized: 'pw1_norm': sf(r['pw1']) * _baro_factor,
                     'pw2_norm': sf(r.get('pw2', 0)) * _baro_factor
  4. Add: 'baro_valid': _baro_valid

Also update Sessions VS cell accumulation (web/launch.py build_index()):
  Change c['pw1'] += r['pw1']  ->  c['pw1'] += r['pw1_norm']
  Change c['pw2'] += r['pw2']  ->  c['pw2'] += r['pw2_norm']
  (and same for pw_eff computation)

Also bump CACHE_VERSION from 6 to 7 in web/vs_engine.py.

- [ ] Apply pw1_norm fix to load_csv() in web/launch.py
- [ ] Update build_index() to use pw1_norm/pw2_norm for cell accumulation
- [ ] Bump CACHE_VERSION to 7
- [ ] Verify detect_launches() peak_pw thresholds — are they absolute or relative?
- [ ] Verify CACHE_VERSION is included in vs_engine cache key (freebuff task 007)
  If not, old normalized caches will be served silently. Check _compare_sessions_cached.
- [ ] Add baro normalization to f7.py load_csv_rows() — HIGH priority (freebuff task 007)
  Same REF_BARO logic, same range gate (900-1100 hPa). May reduce 97% orphan rate.
  f7.py has its own CSV loader that does NOT share code with launch.py.

## BUG — Barometric normalization missing in Sessions VS

**Priority: CRITICAL — contaminates all cross-session PW comparisons**

### Problem
dpw_eff = mean_pw_B - mean_pw_A is computed WITHOUT baro correction.
A Δbaro of 10 hPa between sessions creates ~1% false PW signal.
Combined baro+temp can produce 5-7% false signal — our real deltas are 5-15%.
This can mask or INVERT real map quality signals.

### Fix
In `web/launch.py` -> `_compare_sessions` -> `load_csv()`:
```python
# After loading each row, normalize PW to reference baro
REF_BARO = 1013.25  # standard atmosphere hPa
if row['baro'] > 0:
    baro_factor = REF_BARO / row['baro']
    row['pw1'] = row['pw1'] * baro_factor
    row['pw2'] = row['pw2'] * baro_factor
```
- [ ] Apply normalization in load_csv() at row level
- [ ] Add `baro_norm_ref` field to comparison result so UI can show it
- [ ] Invalidate sessions_vs cache (bump CACHE_VERSION to 6)
- [ ] Handle rows where baro=0: skip normalization, flag cell as 'no baro'
- [ ] Add environmental similarity score per comparison (Δbaro, Δtemp, Δalt)

### Confirmed by
Freebuff task 002 analysis: 0.1% false signal per 1 hPa. Validated against
DDFI2 speed-density behavior. This is the #1 confounder for dpw_eff.

## FASE 6 — PROP_* session output (freebuff task 015)

**Goal:** Save proposal as a burnable session that appears in Tuner automatically.

### Key findings
- Tuner scans `sessions/*/session_metadata.json` — PROP_* needs this file too
- `encode_eeprom_maps()` is in `ecu/eeprom.py` (also imported in server.py line 757)
- Save BOTH eeprom_decoded.json (display) and eeprom.bin (burn)

### Files to create in sessions/PROP_YYYYMMDD_HHMMSS/
- `session_metadata.json` — minimal: checksum=PROP_*, version_string='proposal', total_rides=0
- `eeprom_decoded.json` — proposed fuel maps + current spark maps unchanged
- `eeprom.bin` — binary from encode_eeprom_maps()
- `proposal_metadata.json` — source sessions, stats, smoothing params, safety stats
- `current_eeprom_decoded.json` — copy of session_a's EEPROM for reference

### Apply delta formula (integer EEPROM values 0-250)
```python
proposed = np.round(current * (1 + smoothed_delta)).astype(int)
proposed = np.clip(proposed, 0, 250)
max_change = np.round(current * 0.15).astype(int)
change = np.clip(proposed - current, -max_change, max_change)
proposed = current + change
```

### New endpoint needed
POST /eeprom/propose?a=SA&b=SB&save=1
  save=0 (default) = dry run, return JSON only
  save=1 = save PROP_* session to disk, return path + JSON

- [ ] Implement save_proposal() function in proposal.py
- [ ] Add save=0/1 param to _handle_eeprom_propose in server.py
- [ ] Include diff_map (proposed - current) in response for heatmap display

## SISTEMA ACTUAL — OL sin WB (contexto crítico)

**El sistema opera en Open Loop (OL) sin sensor wideband.**
El sensor EGO narrowband está desconectado intencionalmente.

### Estado confirmado en datos
- `EGO_Corr` = 100 siempre (locked)
- `AFV`      = 100 siempre (locked)
- `WUE`, `AE` = funcionan normal (no dependen del O2)

### Pipeline válida en OL
```
F7 events (curvas PW físicas)  →  comparación cross-session  →  ¿cuál mapa acelera mejor?
Sessions VS (dpw, ddvss)       →  comparación por celda      →  ¿cuál mapa es más eficiente?
```
**No usar EGO_Corr ni AFV para nada hasta tener WB instalado y validado.**

### JSONs activos vs inactivos en OL

| JSON | Estado | Nota |
|------|--------|------|
| `ride_*_f7events.json` | ✅ ACTIVO | PW + TPS físicos |
| `session_f7clusters` | ✅ ACTIVO | DTW sobre PW |
| `sessions_vs delta` (dpw, ddvss) | ✅ ACTIVO | Físico |
| `eeprom_decoded.json` | ✅ ACTIVO | Mapa puro |
| `tuning_report_*.json` | ⛔ INACTIVO | ego_avg=100 → 0 sugerencias |
| `ego_avg` en ride_summary | ⛔ RUIDO | Siempre 100 |

### Propuesta de mapa unificada (OL — sin EGO)
- [ ] Combinar F7 cross-session (¿cuál mapa acelera más?) con Sessions VS delta
      (¿cuál mapa consume menos en crucero?) para generar una propuesta por celda
- [ ] Cada celda del EEPROM recibe: señal F7 (WOT) + señal VS (SWEET) + confianza
- [ ] Celdas sin cobertura de ninguno de los dos: sin cambio
- [ ] Output: eeprom propuesto que el Tuner puede revisar y quemar (FASE 6)

### Futuro — integración WB
- [ ] Cuando WB esté instalado: leer AFR real → comparar vs target map
- [ ] Con WB: `tuning_report` se vuelve útil (EGO trend = corrección real por celda)
- [ ] Integrar WB como tercer input a la propuesta unificada (suma a F7 + VS, no reemplaza)
- [ ] Validar primero con WB en paralelo (passthrough) antes de integrarlo al loop

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

## UX — PROPOSAL tab in Tuner page (freebuff task 020)

**Goal:** Add a PROPOSAL tab to tuner.html showing the fuel delta heatmap.

### Design decisions (freebuff task 020)
- Trigger: "Generate Proposal" button (NOT on page load — takes 2-3s)
- Color scale: RdBu diverging — blue=lean(-15%), white=0%, red=rich(+15%)
- Interpolated cells: white dot overlay (signal_mask=false)
- UX: async/await + spinner + disabled button + error fallback
- Cache: sessionStorage keyed by `${sa}_${sb}` for instant re-visit
- Data: `data.smoothed.delta_fuel_front`, `data.smoothed.signal_mask`

### Changes needed in tuner.html

**A) Tab button (1 line):**
```html
<button class="tab-btn" data-tab="proposal">PROPOSAL</button>
```

**B) Tab content div (~20 lines):**
- Canvas `proposal-canvas` 520x480
- Dropdowns: Smoothed/Raw/Signal/Confidence + Front/Rear cylinder
- Status span + error div

**C) JS functions (~70 lines total):**
```js
function deltaColor(pct, maxAbs=15) {  // RdBu diverging
  const t = Math.max(-1, Math.min(1, pct/maxAbs));
  return t < 0
    ? `rgb(${Math.round(255*(1+t))},${Math.round(255*(1+t))},255)`
    : `rgb(255,${Math.round(255*(1-t))},${Math.round(255*(1-t))})`;
}

function renderDeltaHeatmap(canvasId, data, signalMask, maxAbsPct=15) {
  // 20-line canvas renderer with color + dots + value labels
  // see freebuff task 020 full snippet
}

async function generateProposal() {
  // async/await, spinner, fetch /eeprom/propose?a=SA&b=SB
  // cache in sessionStorage[`${sa}_${sb}`]
}
```

- [ ] Add PROPOSAL tab button to tuner.html tab-header
- [ ] Add tab content div with canvas + dropdowns + status
- [ ] Implement deltaColor() + renderDeltaHeatmap() in JS
- [ ] Implement generateProposal() with async/await + spinner + sessionStorage cache
- [ ] Wire dropdown switches (front/rear, raw/smooth) to re-render

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


## BUG-DISC-01 — ECU disconnection gaps during rides (~11s periodic blackouts)

**Priority:** HIGH
**Sessions affected:** 47BF04 (all rides), likely all sessions
**Symptoms:** CSV shows gaps of exactly 11.2-11.4s at random times during rides, with engine still running (RPM > 0 after gap). Some rides also have longer gaps (20-165s).

### Data pattern (47BF04 ride_001 sample)
- GAP 80s->92s=11.2s RPM=1083
- GAP 135s->147s=11.2s RPM=2591
- GAP 284s->296s=11.7s RPM=3491
All gaps: 11.2-11.4s. No dirty bytes. Engine running throughout.

### Hypothesis
The ~11.2s gap =  blocking: 5 attempts x (2.0s timeout + 0.3s sleep) = 11.5s.
This is called by the hard reconnect path in  when .
But if get_version() ALSO blocks during the accumulation phase, or is triggered by
a different path, the total observed gap could be shorter than 10+11.5s.

### What to investigate (freebuff task)
1. SSH and read the buell log during a ride:  while riding
2. Find any Hard reconnect or get_version log lines and correlate timestamps
3. Check if  is called from any path outside the hard reconnect block
4. Check if  triggers a disconnect during a ride
   (currently guarded by  at line ~458 of main.py — verify this is correct)
5. Measure actual duration of  failing: 5 x 2.3s = 11.5s matches the gaps

### Proposed fix options
A. Skip  during active rides — use  directly as the liveness check
B. Reduce get_version to 1-2 attempts (not 5) during a ride
C. Add a fast ping: send PDU_VERSION, read 1 byte with 0.5s timeout — if SOH received, ECU is alive
D. Log every get_version() call with timestamp to buell.log

### Related files
- main.py: _ecu_loop(), hard reconnect block (~line 465), MAX_CONSEC_ERRORS=30
- ecu/connection.py: _get_version_impl() (5 attempts x 2.3s), get_rt_data()

### Freebuff research findings (2026-06-07)
| ECUID | Gaps >5s | Total lost | Severity |
|-------|----------|-----------|----------|
| 47BF04 | 111+ | ~2438s (40min) | CRITICAL |
| 91B225 | 25 | 857s | HIGH |
| 653DC0 | 10 | 2723s | MODERATE |
| 27F1A2 | 1 | 46s | EXCELLENT |

Worst ride: 47BF04 ride_007 (29 gaps, 841s = 14 min lost).
Gaps do NOT correlate with RPM load. Possible causes: USB adapter overheating after ~15min,
alternator electrical noise, vibration loosening connector.
Rides ending "power_loss_recovered" = disconnection longer than ECU_RETRY threshold.


## FASE 8 — Fuel Economy & Reserve Tracking

**Priority:** MEDIUM (next major feature after FASE 6)
**Pivot point:** when fuel reserve light activates

### Overview
Track real fuel consumption using injector pulse data, validated against actual fill-ups.
Iterative: each fill-up cycle improves the PW→liters calibration.

### Sub-features (in order)

#### 8.1 — Find fuel reserve signal in ECU data
- Search ecu_defs XML (all *.xml) for: reserve, FuelWarning, FuelLevel, fuel lamp, DIn bits
- Check DIn bitmask in protocol.py — does any bit correspond to fuel reserve light?
- Check DOut / CDiag / HDiag fields in live data
- Alternative: Pi GPIO pin connected to fuel reserve wire (reed switch at tank float)
- Freebuff task: audit all XML defs + DIn/DOut bit mappings for reserve indicator
- If not in ECU data: add external GPIO sensor support to main.py

#### 8.2 — Reserve activation event
When fuel reserve activates (signal goes high):
- Log timestamp + odometer (km) + session/ride
- Start km counter from that point (using VS_KPH integrated over time)
- Start injector counter: accumulate pw1 + pw2 ms per sample
- Store in session_metadata.json: {reserve_triggered_at: t, reserve_km_start: km}

#### 8.3 — Fill-up event (user input from dashboard)
New button/modal in Dashboard or Config tab:
- Input: liters added (float, e.g. 12.5)
- Input: octane rating selector (87 / 91 / 93 / 95)
- Auto-fill: session, ride_num, timestamp, odometer at fill-up
- Store in: sessions/fill_ups.json (global log) + session_metadata
- Format: {ts, liters, octane, session, ride_num, km_at_fill, reserve_km_since_trigger}

#### 8.4 — Consumption validation
After next reserve trigger (cycle complete):
- Compare: injector_pw_accumulated (ms) vs liters consumed (from fill-up log)
- Derive: liters_per_pw_ms calibration constant
- Display: km/L, L/100km, range estimate to next reserve
- Validate: does the PW-derived consumption match the pump reading? Confidence score.
- This becomes iterative — each cycle refines the constant

#### 8.5 — Maintenance tab
New dashboard tab "Mant" (maintenance):
- Oil change tracker: km counter + hours counter since last oil change
  User inputs date + km when oil was changed
- Chain lube: km counter
- Tire check: km counter  
- Spark plugs: km counter
- All counters reset on user input, persist in maintenance_log.json
- Alert when any counter exceeds threshold (configurable)

### Technical notes — XB12X confirmed specs (from service manual + parts catalog)

#### Injectors
- Front: P0026.1AA / Rear: P0027.1AA (NOT interchangeable — different spray patterns)
- Resistance: 12.25 ohms per injector
- Flow rate: ~320cc/min (forum reference — manual only specifies 49-51 PSI rail pressure)
- cc_per_ms = 320 / 60000 = 0.00533 cc/ms per injector
- Both cylinders per sample: (pw1_ms + pw2_ms) * 0.00533 cc

#### Tank — XB12X Ulysses
- Total capacity: 16.7 liters (4.40 gal) — includes reserve
- Usable before reserve light: 16.7 - 3.1 = 13.6 liters
- Reserve light activates at: 3.1 liters remaining (0.83 gal)
- NOTE: XB12S/Scg/R have smaller 14.5L tank — XB12X is the larger one

#### Fuel calculation formula
injected_cc_per_sample = (pw1_ms + pw2_ms) * 0.00533
total_liters = SUM(injected_cc_per_sample) / 1000
(sum from reserve trigger to next fill-up, then compare vs actual liters pumped)

#### km counter formula
km_per_sample = VS_KPH * sample_interval_s / 3600
total_km = SUM(km_per_sample) from reserve trigger

- All math is approximation until validated against real fill-up data
- The iterative calibration (8.4) will refine the 0.00533 cc/ms constant


## FASE 8 — Fuel Tracker: pending features (step by step)

### BL-FUEL-10 — Reset / Tanque lleno button [NEXT]
**Priority:** HIGH
When user fills up to full (or wants to reset the estimate):
- Add toggle in fill-up form: "Tanque lleno"
- If checked: level resets to 16.7L regardless of calculation
- Still log entered liters + the discrepancy (calculated_remaining vs actual_fill)
- Example: calc says 5L remaining, user puts 14L → discrepancy = 14+5-16.7 = 2.3L unaccounted
  Could be: undocumented short ride, disconnections, calculation error
- discrepancy is stored in the refuel entry for future calibration analysis

### BL-FUEL-11 — Consumption per ride (L/100km, km/L)
**Priority:** MEDIUM
Calculate fuel consumption for each ride:
- Read pw1+pw2 from each ride CSV, apply injector constant
- Read VS_KPH, integrate to get km per ride
- Output: L consumed, km, L/100km, km/L
- Show in the fill-up history and optionally in Sessions tab
- Can compare across sessions to see effect of tuning on fuel economy

### BL-FUEL-12 — Discrepancy log and calibration analysis
**Priority:** MEDIUM
Every fill-up where calc_remaining + actual_liters != 16.7L (within margin):
- Flag the discrepancy and reason (undocumented ride, disconnections, sensor drift)
- Track cumulative calibration error over multiple cycles
- Show confidence score for the injector constant (0.00533 cc/ms)
- After N fill-ups, suggest refined constant

### BL-FUEL-13 — Odometer integration (km total from EEPROM)
**Priority:** LOW
- freebuff found odometer in BUEYD/BUEWD/BUEZD.xml at offset -36
- Read actual odometer from eeprom.bin to cross-validate km counter
- Show total odometer alongside trip km

### BL-FUEL-14 — Short ride detection / undocumented km
**Priority:** LOW
- If discrepancy > 1.5L, prompt: "Did you ride without the logger?"
- User can input km ridden without logger — added to trip counter
- Improves calibration accuracy

## Mantenimiento / Limpieza de código
### BL-BUG-01 — Low priority bugs from freebuff audit (2026-06-07)
**Priority:** LOW

- AHT20 sensor (sensors/aht20.py): no retry on init failure — if sensor is in transient state post power-up, it fails permanently until process restart. Fix: add 3 retry attempts with 100ms delay in begin().
- CW2015 (sensors/cw2015.py): does not write MODE register (0x0A) to ensure active mode on init. Fix: write 0x00 to register 0x0A at startup.
- Gear detect (web/gear_detect.py): returns gear 1 when rpm > 1500 and vss > 5 but bike is in neutral. Fix: return 0 (unknown) when rpm/vss ratio doesn't match any gear range.
- network/manager.py: multiple threads can launch nmcli simultaneously (no lock on _switch_status). Fix: add threading.Lock around nmcli calls.
- web/static/app.js: 37 fetch() calls without AbortSignal — requests hang forever if server stops responding. Fix: use AbortController with 10s timeout on all fetch() calls.
- web/vs_engine.py: _compare_sessions_cached uses total_samples as cache key — stale if data changes without sample count change. Fix: include file mtime or content hash in key.
- install.sh: hotspot password hardcoded as "buell2024" — consider reading from env or config file.
- web/static/app.js: renderCobertGrid() calls getElementById in nested loops (line ~2450) — cache the element reference outside the loop to avoid repeated DOM lookups.
- web/static/app.js: showTab() uses setTimeout(loadFn, 0) for defer — potential race if user switches tabs faster than 0ms render cycle.



### BL-DOCS-01 — README.md full rewrite (freebuff audit 2026-06-07)
**Priority:** LOW
**Source:** freebuff readme_gap_analysis.md

README.md is severely outdated — documents ~30% of actual project capabilities.
Missing: 15+ Python modules, 20+ features, 50+ API endpoints, 6 HTML pages,
full session data structure (10+ file types), hardware details.
Key gaps: WiFi/Hotspot management, error log viz, gear detection, GPS, system health,
battery shutdown, baro normalization, VE heatmap editing, MSQ export, F7 pipeline.
Use readme_annotated.md (freebuff output) as draft template when implementing.



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
## Prioridad: ALTA — Battery tiered shutdown (startup-aware)
- [ ] Tiered shutdown logic based on startup battery level:
  - startup_pct >= 30%: shutdown if drops below 30% (normal)
  - startup_pct 20-29%: shutdown if drops below 20% (grace tier 1)
  - startup_pct 10-19%: shutdown if drops below 10% (grace tier 2)
  - startup_pct < 10%:  safe shutdown immediately on boot
  - Always: if is_charging == True, NEVER shutdown regardless of %
  Implementation: read pct at startup, store as BOOT_PCT, use tiered threshold
  File: likely main.py or the CW2015 monitor loop
  Dashboard: show which tier is active (normal / grace-1 / grace-2 / critical)
- [ ] Wake-on-GPIO: connect UPS-Lite power detect pad to Pi RUN pin
  Requires: solder pads on UPS-Lite, wire to Pi header
  Effect: Pi turns on when USB power connected
- [ ] INA219 current sensor for precise power consumption monitoring

---

---

# Backlog: Knowledge Graph de Mapas (FASE 7)

## Prioridad: ALTA
- [ ] Build maps_knowledge.db — SQLite knowledge graph for tuning history
  Schema: maps (checksum, fuel_front, fuel_rear), sessions (conditions: baro/temp/alt),
          performance (sweet_pct, spicy_pct, bitter_pct, dpw_eff, orphan_rate),
          map_vectors (312-float embedding = fuel_front[12x13] + fuel_rear[12x13])
  Queries: best map for given conditions, cosine similarity between maps, convergence trend
  Library: sqlite-vec (pip) for KNN search, numpy already available
  File: web/knowledge.py (~200 lines)
  Powers: FASE 6 condition-aware proposal (weight deltas by historical sweet_pct at same baro)
  Prerequisite: freebuff task 028 research first (condition buckets, ranking weights)


---

# Backlog: Auditoría freebuff — TASK 025 (v2.7.25)

## Prioridad: ALTA
- [ ] PROPOSAL tab en Tuner page (no implementado — freebuff task 025 top-1)
  Context: tuner.html tiene tabs BASE/DELTA/MOD con renderizado heatmap, pero NO existe
  un tab PROPOSAL. Solo falta anadir: boton en tab-bar, <div id="proposal"> con canvas,
  y JS fetch a /eeprom/propose?a=SA&b=SB.
  Referencia: responses/task_020_delta_heatmap_tuner.md (diseno completo)
  Estimado: 2-3h

## Prioridad: MEDIA
- [ ] proposal.py _clamp() sigue siendo nested function (cosmetic cleanup — freebuff task 025 top-3)
  Problema: _clamp(v) esta definida DENTRO de otra funcion, redefiniendose en cada llamada.
  Fix: extraer a nivel modulo como def _clamp(v, max_delta), aceptando max_delta como parametro.
  Archivo: web/proposal.py linea ~192
  Estimado: 10min

## Prioridad: HECHA (v2.7.25) - Verificada por freebuff
- [x] pw1/pw2 raw preserved in load_csv() - BUG FIXED
  Commit 2b87e4f. pw1 ahora es RAW, pw1_norm agregado, CACHE_VERSION bump a 7.
  detect_launches() usa pw1 raw correctamente.
  Archivos: launch.py, vs_engine.py, CHANGELOG.md
---

# Backlog: Knowledge Graph de Mapas — Diseño (freebuff task 028)

## Schema (Pure SQLite — no sqlite-vec, PEP 668 blocks pip on Pi)

- maps(checksum PK, fuel_front JSON 12x13, fuel_rear JSON 12x13, axes_rpm, axes_load, n_sessions)
- sessions(session_id PK, checksum FK, avg_baro, avg_temp, avg_alt, date_utc, is_proposal)
- performance(session_id PK FK, sweet_pct, spicy_pct, bitter_pct, dpw_eff_avg, orphan_rate, sample_count)
- Similarity: 312-float vector (fuel_front flat + fuel_rear flat), numpy cosine, no DB extension needed

## Condition buckets
- baro: 20 hPa bands | temp: 5C bands | alt: 500m bands
- Fallback: nearest-neighbor Euclidean when < 3 sessions in bucket

## Performance ranking formula
  map_score = sweet_pct*0.35 + |dpw_eff_avg|*10*0.25 + (100-orphan_rate)*0.25 + spicy_pct*0.15

## File: web/knowledge.py (~200 lines)
## Effort: 5-6h total (schema + 3 core functions + 2 endpoints + ingestion + dashboard card)

## Prioridad: ALTA — implementar despues de PROPOSAL tab

## Prioridad: ALTA
- [ ] Step 1: web/knowledge.py — DB schema + ingest_session() + best_maps_for_conditions() + map_similarity()
- [ ] Step 2: ingest_all_sessions() to bootstrap from existing 22 sessions
- [ ] Step 3: GET /knowledge/best?baro=&temp=&alt= + GET /knowledge/similar/<checksum>
- [ ] Step 4: Dashboard card showing best historical map for current conditions



---

# Backlog: Validacion freebuff - TASK 036 (pw1_norm fix v2.7.25)

## Prioridad: VALIDADA - Todo correcto

Commit: 2b87e4f - fix: pw1/pw2 raw preserved in rows, pw1_norm for cross-session

### Check de validacion

| # | Que se valido | Resultado |
|---|---------------|-----------|
| 1 | pw1 RAW en rows.append() | PASA - sf(r["pw1"]) sin factor |
| 2 | pw1_norm con baro factor | PASA - sf(r["pw1"]) * _baro_factor (line 351) |
| 3 | detect_launches() usa pw1 raw | PASA - peak_pw calculado con r["pw1"] raw |
| 4 | CACHE_VERSION bump a 7 | PASA - vs_engine.py line 106 (v2.7.25) |
| 5 | pw1_norm en cross-session | PASA - lines 437,446: c["pw1"] += r["pw1_norm"] |
| 6 | Import check sin errores | PASA - python OK |
| 7 | pw2_norm tambien existe (front + rear) | PASA - linea 446 usa ambos |
| 8 | Commit 2b87e4f existe | PASA |

### Veredicto
El fix de pw1_norm esta correctamente implementado:
- pw1 preserva el valor RAW (no contaminado por baro)
- pw1_norm se usa para acumulacion cross-session (normalizado)
- detect_launches() usa pw1 raw (no afectado por el fix)
- CACHE_VERSION bump a 7 invalida cache viejos
- No hay regresiones en imports

- [x] Claude: confirmar que la validacion es correcta y cerrar este item.


---

# Backlog: Investigacion freebuff - TASK 033 (Bug #13 daemon thread watchdog)

## Prioridad: HECHA (Research) - Watchdog existe pero con gaps

### Estado actual en main.py
El watchdog YA existe (lineas 658-675) pero tiene limitaciones:

| Aspecto | Estado actual |
|---------|--------------|
| _check_threads() | EXISTE - llamado cada ~1s desde el main loop |
| Deteccion de threads muertos | es alive() check - detecta si el thread termino |
| Restart con cooldown | 30s - evita restart loops |
| Heartbeat timestamp por thread | NO existe - no detecta threads colgados |
| Health metric (ej: last_read) | NO existe - no sabe si el thread progresa |
| Restart de ecu-rt | SI - crea nuevo Thread y lo arranca |
| Restart de sysmon | SI - misma logica |

### Gaps identificados

1. **Thread colgado vs thread muerto**
   is_alive() solo detecta si el thread termino (return o exception no capturada).
   Un thread trabado en read()/write() (blocking I/O) aparece vivo pero no progresa.
   Solucion: agregar timestamp heartbeat que cada thread actualice en cada iteracion.

2. **Sin health check**
   No hay metricas como "ultimo sample de ECU recibido" o "ultima lectura de sysmon".
   Solucion: agregar stats["ecu_last_read"] y stats["sysmon_last_read"] para monitoreo.

3. **Sin heartbeat en ecu_loop**
   El _ecu_loop no reporta si esta vivo. Si serial.read() cuelga, no hay recovery.
   Solucion: ecu_loop agrega self._ecu_heartbeat = time.monotonic() en cada iteracion.

### Propuesta de implementacion

Agregar a main.py:


### Efecto secundario: zombie threads en restart
Riesgo real: si el thread viejo esta trabado en read() (kernel nivel), el .start()
del nuevo thread no mata al viejo. El recurso (serial port) podria quedar lockeado.

Mitigacion:
- Antes de restart: self.ecu.disconnect() libera el puerto serial
- Para sysmon: no hay recurso compartido, bajo riesgo

### Archivos a modificar
| Archivo | Cambio | Lineas |
|---------|--------|--------|
| main.py | Agregar self._ecu_heartbeat y _sysmon_heartbeat | +4 en init |
| main.py | Actualizar heartbeats en _ecu_loop y _sysmon_loop | +2 lineas |
| main.py | _check_threads: agregar chequeo de stale heartbeat | +5 lineas |

### Estado: RESEARCH HECHA
- [ ] Claude: revisar el analisis e implementar heartbeat check + stale detection
- [ ] Claude: decidir si vale la pena o el is_alive() actual es suficiente


---

# Backlog: Investigacion freebuff - TASK 033 (Bug #13 daemon thread watchdog)

## Prioridad: HECHA (Research) - Watchdog existe pero con gaps

### Estado actual en main.py
El watchdog YA existe (lineas 658-675) pero tiene limitaciones:

| Aspecto | Estado actual |
|---------|--------------|
| _check_threads() | EXISTE - llamado cada ~1s desde el main loop |
| Deteccion de threads muertos | is_alive() check - detecta si el thread termino |
| Restart con cooldown | 30s - evita restart loops |
| Heartbeat timestamp por thread | NO existe - no detecta threads colgados |
| Health metric (ej: last_read) | NO existe - no sabe si el thread progresa |
| Restart de ecu-rt | SI - crea nuevo Thread y lo arranca |
| Restart de sysmon | SI - misma logica |

### Gaps identificados

1. Thread colgado vs thread muerto - is_alive() no detecta I/O blocking
2. Sin health check - no metricas de progreso
3. Sin heartbeat en ecu_loop

### Propuesta de implementacion
- self._ecu_heartbeat = time.monotonic() en cada iteracion del loop
- self._sysmon_heartbeat idem
- _check_threads: si heartbeat stale > 10s, restart
- Antes de restart ecu: cerrar serial primero

### Archivos a modificar
main.py: +11 lineas total (init + 2 heartbeats + stale check)

### Estado: RESEARCH HECHA
- [ ] Claude: revisar analisis e implementar heartbeat + stale detection
---

## FASE 5.1 — Click-to-edit VE heatmap (freebuff task 029)

### Infrastructure already in place
- /eeprom/burn endpoint EXISTS (server.py line 725): safety gate, auto-backup, encode/decode
- tuner.html has canvases for Base/Delta/Mod — no click handler yet

### Architecture
- STAGE.dirty = { fuel_front: { "3,5": new_value } } — JS dict tracking edits
- Click cell → overlay input → store in STAGE.dirty → redraw yellow overlay
- BURN button: POST /eeprom/burn { changes: { fuel_front: {"3,5": 45.2} } }
- Backend: per-cell ±15% gate + max 20 cells per burn

### Files to modify
- tuner.html: STAGE object + click handler + overlay input + BURN/RESET buttons (~+80 lines)
- server.py: changes validation in _handle_eeprom_burn (~+15 lines)

## Prioridad: ALTA
- [ ] tuner.html: add STAGE.dirty tracking + canvas click handler + cell input overlay
- [ ] tuner.html: BURN button (POST /eeprom/burn with changes dict) + RESET button
- [ ] server.py: validate changes in _handle_eeprom_burn (±15% per cell, max 20 cells)
---

## FASE 6 — Readiness matrix (freebuff task 030, 2026-06-06)

### Status: 5/11 spec items done

| # | Item | Status |
|---|------|--------|
| 1 | F7 + VS zone fusion (peak TPS → WOT/Mid/Light) | ❌ MISSING — v2 work |
| 2 | Two delta maps: f7_delta + vs_delta separate | ❌ MISSING — only VS delta exists |
| 3 | Rich bias on conflict | ⚠️ PARTIAL — in smoothing, no F7 vs VS conflict logic |
| 4 | F7 confidence formula (w_multi * w_dtw * w_cross) | ❌ MISSING — sample-based only |
| 5 | Coverage mask per cell (multi-session) | ⚠️ PARTIAL — signal_mask exists, not multi-session |
| 6 | Front/rear merged independently | ✅ DONE |
| 7 | Smoothing pipeline: clamp→interp→smooth→clamp | ✅ DONE |
| 8 | Convergence termination | ✅ DONE |
| 9 | Asymmetric bias only on last iteration | ✅ DONE |
| 10 | No smoothing across zone boundaries | ❌ MISSING |
| 11 | Rear cylinder lambda*0.5 for measured cells | ❌ MISSING |

### Next implementation order (FASE 6 v2)
1. F7 delta integration in proposal.py (items 1, 2, 4) — HIGH
2. Zone boundary protection in smoothing.py (item 10) — MEDIUM
3. Multi-session coverage mask (item 5) — MEDIUM
4. Rear cylinder lambda*0.5 (item 11) — LOW
---

## Backlog 7.7 — Batch compare all-sessions (freebuff task 031)

### Infrastructure already exists
-  in f7.py — reuse directly, no reimplementation
-  in f7.py — auto-generates clusters if missing
- 4 of 33 sessions already have f7clusters JSON (248AE2, 47BF04, 91B225, 9ECD1E)

### New file: web/batch_compare.py (~145 lines)
-  — calls _f7_load_session_clusters() for all sessions
-  — loops all pairs via _f7_match_cross_session(), aggregates wins
-  — sort by win_rate, filter min 5 matches, opponent breakdown
- Output: sessions/_batch_compare_ranking.json (cached)
- GET /batch_compare endpoint in server.py (+15 lines)
- Button in dashboard (+10 lines)

### Win determination
vss_curve is 20-point resampled. idx_3s = min(int(3.0 / duration * 20), 19).
win = delta_vss_A[idx] > delta_vss_B[idx]. Ties = 0.5 each.

## Prioridad: ALTA
- [ ] Create web/batch_compare.py with 3 core functions
- [ ] GET /batch_compare endpoint in server.py
- [ ] Dashboard button Rank maps by acceleration

---

## FASE 5.3 — AI context export (freebuff task 035)

### Key finding
BUEIB.xml has 477 eeoffsets but only 35 are user-facing tuning params.
EGO/AFV always 100.0 in OL — exclude from AI context (misleading to LLM).

### Safe vs dangerous params
- WHITELIST: fuel maps, spark maps, fan temps, soft temp limits
- BLACKLIST: KTemp_Kill_Hi/Lo, KTemp_Hard_Hi/Lo, CEL params, EEPROM version fields

### Implementation: server.py (~85 lines)
-  — builds JSON with 35 safe params + 4 maps
- GET /eeprom/ai_context?session=X
- Dashboard button Copy AI context
- Token estimate: ~1,125 tokens total — fits any LLM context

## Prioridad: BAJA
- [ ] _build_ai_context() helper in server.py with whitelist/blacklist
- [ ] GET /eeprom/ai_context?session=X endpoint
- [ ] Dashboard Copy AI context button
---

## Backlog 7.8 — Migrate Launch to consume F7 events (freebuff task 032)

### Recommendation: Dual mode
Keep detect_launches() for sessions WITHOUT f7clusters (29/33).
Add _launch_from_f7clusters() for sessions that have F7 clusters.

### F7 field mapping
- gear, pre_rpm/spd/tps, clt, baro, pw1/pw2 curves: YES
- peak_rpm, peak_spd, peak_pw, rpm_gain, spd_gain: YES
- pre_alt_m: NO (F7 has slope, not absolute alt)
- ae accel enrichment: NO
- raw timestamps dt: NO

### Implementation plan (+60 lines)
1. f7.py: add ae + gps_alt to event struct (+5 lines)
2. launch.py: _launch_from_f7clusters() converter (+40 lines)
3. launch.py: _load_launch_data() dual-mode router (+15 lines)
4. Bump events_v cache version (+1 line)

## Prioridad: MEDIA
- [ ] f7.py: add ae, gps_alt to event struct
- [ ] launch.py: _launch_from_f7clusters() converter
- [ ] launch.py: _load_launch_data() dual-mode router
---

## FASE 6.1 — F7 + VS zone fusion design (freebuff task 037)

### Zone classification by peak TPS
- WOT: tps_peak >= 85% -> trust VS only (few F7 WOT events)
- Mid: 40% <= tps_peak < 85% -> F7 + VS weighted fusion
- Light: tps_peak < 40% -> F7 only (VS poor at low TPS)
- tps_peak field CONFIRMED in f7events JSON (value: 98.9)

### Dual delta fusion formula
  f7_weight = f7_confidence (n_clusters * dtw_score)
  vs_weight = vs_confidence (n_samples, capped 1.0)
  delta = (f7_delta * f7_weight + vs_delta * vs_weight) / (f7_weight + vs_weight)
  Rich bias on conflict: if signs differ, delta = max(f7_delta, vs_delta)

### Implementation
1. web/proposal.py: _compute_f7_delta() — calls _f7_match_cross_session(), maps to EEPROM cells
2. web/proposal.py: zone classification by tps_peak (85%/40% thresholds)
3. web/proposal.py: generate_fuel_proposal() fuses f7_delta + vs_delta
4. Prerequisite: F7 cross-session clusters must exist for both proposal sessions

## Prioridad: ALTA — prerequisite for full FASE 6
- [ ] _compute_f7_delta() in proposal.py
- [ ] Zone classification by tps_peak
- [ ] Weighted fusion + rich bias in generate_fuel_proposal()

---

## FASE 6.3 — Map smoothing upgrades (freebuff task 038)

### Key finding: scipy 1.15.3 IS available on Pi
smoothing.py has fallback comment — scipy is confirmed available, use it.

### Improvements
1. Bicubic upgrade: scipy.interpolate.griddata(method='cubic') vs current IDW
2. Rear cylinder lambda: LAPLACIAN_LAMBDA_FUEL_REAR = 0.20 (vs front 0.25)
3. Zone-aware boundaries: skip neighbors with different zone_id in laplacian_smooth()

### Implementation
1. web/smoothing.py: add LAPLACIAN_LAMBDA_FUEL_REAR = 0.20
2. web/smoothing.py: upgrade interpolate_fill() to use scipy griddata cubic (fallback IDW)
3. web/smoothing.py: optional zone_mask param to laplacian_smooth() — skip cross-zone neighbors
Note: zone-aware boundaries depend on FASE 6.1 zone fusion being implemented first

## Prioridad: MEDIA (after FASE 6.1)
- [ ] LAPLACIAN_LAMBDA_FUEL_REAR = 0.20 in smoothing.py
- [ ] scipy griddata cubic in interpolate_fill()
- [ ] zone_mask param in laplacian_smooth()
---

## FASE 6.4 — Spark map without knock sensing (freebuff task 039)

### Factory spark limits (from session 248AE2 EEPROM)
- spark_front max: 36 deg BTDC (high RPM/load)
- spark_rear max: 35 deg BTDC (1 deg more retarded than front)
- Rear already 1-2 deg retarded vs front at high loads

### Design
- Per-iteration limit: +/-2 deg | Per-cell limit: +/-1 deg
- Advance gate: only if delta_vss > +3% (harder acceleration = spark advance working)
- Retard gate: only if delta_vss < -3%
- 2-session rule: require 2+ independent session pairs before any advance
- Fuel-before-spark: apply fuel deltas first, then spark in next iteration
- Never exceed factory max: 36 front, 35 rear
- Rear always 1-2 deg more retarded than front

### Implementation (web/proposal.py)
1. _compute_spark_delta() with +/-2 deg limit + delta_vss gates
2. 2-session rule check before any advance
3. fuel-before-spark ordering in generate_fuel_proposal()
4. Ceiling: never exceed factory max

## Prioridad: MEDIA (after FASE 6.1 F7+VS fusion)
- [ ] _compute_spark_delta() in proposal.py
- [ ] 2-session rule for advance
- [ ] fuel-before-spark ordering
---

## FASE 6.6 — Baro normalization remaining items (freebuff task 040)

### Already done
- baro_valid range gate (900-1100 hPa): launch.py + f7.py ✅
- pw1_norm/pw2_norm split: v2.7.25 ✅
- Note: gps_alt_m IS in CSV (launch.py line 362 reads it) — GPS fallback possible if needed

### Missing
1. Skip-flag: if session has < 90% baro_valid rows → skip baro normalization, flag session
2. Dashboard: show avg_baro, baro_valid_pct, delta_baro per session comparison

### Implementation
1. web/launch.py: _compute_baro_stats(session_id) → {avg_baro, baro_valid_pct, skip_normalization}
2. web/launch.py: if skip_normalization → use baro_factor=1.0 for all rows
3. Dashboard template: add baro stats columns to session list

## Prioridad: BAJA
- [ ] _compute_baro_stats() in launch.py + skip flag
- [ ] Dashboard baro columns (avg_baro, baro_valid_pct)

### BL-LOGGER-01 — Grabar humidity_pct y gps_alt_m en el CSV
**Status: DONE** — already in CSV_COLUMNS (protocol.py) and injected in main.py before write_sample. Old rides (Apr 2026) have 98 cols but new rides have 108.
**Priority:** MEDIUM
**File:** main.py o el logger de CSV

humidity_pct del sensor AHT20 no está siendo grabada en el CSV.
gps_alt_m del GPS sí está en el CSV pero gps_valid=True casi nunca coincide con eventos F7.
Verificar que ambas columnas se graben correctamente y con la frecuencia adecuada.

### BL-LOGGER-01 — Grabar humidity_pct y gps_alt_m en el CSV
**Priority:** MEDIUM
**File:** main.py o el logger de CSV

humidity_pct del sensor AHT20 no está siendo grabada en el CSV.
gps_alt_m del GPS sí está en el CSV pero gps_valid=True casi nunca coincide con eventos F7.
Verificar que ambas columnas se graben correctamente y con la frecuencia adecuada.

## Fixes aplicados por freebuff (2026-06-07)
- [x] connection.py (root) eliminado - duplicado de ecu/connection.py (freebuff)
- [x] protocol.py (root) eliminado - duplicado de ecu/protocol.py (freebuff)
- [x] tools/test_ecu.py.save eliminado - backup leftover (freebuff)
- [x] tools/health_journal.py: atomic write fix (tmp+os.replace) (freebuff)

### BL-BUG-02 — VSS auto-calibration via GPS comparison
**Priority:** MEDIUM
**Source:** user request 2026-06-07

The VSS_CPKM25 constant (1518.0) is hardcoded. When GPS has a valid fix, compare
GPS-derived kph vs VSS-derived kph and auto-adjust the calibration constant over time.

Goal:
- When GPS signal is valid (hdop < 2.0, speed > 10 kph), log ratio: gps_kph / vss_kph
- Apply exponential moving average to refine VSS_CPKM25 in real time
- Persist the calibrated value so it survives restarts
- Benefit: handles tire size changes, sprocket swaps, any mechanical variation
- When GPS unavailable, use the learned constant — independent and accurate

**Freebuff task:** Investigate if this mechanism already exists (grep VSS_CPKM25,
gps_kph comparison in protocol.py / main.py). If not, design the calibration loop.
