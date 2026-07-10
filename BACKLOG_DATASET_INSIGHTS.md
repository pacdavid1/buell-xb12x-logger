# BACKLOG_DATASET_INSIGHTS — Hidden signals in the 70+ ride dataset

> Generated 2026-06-12 from cross-AI dataset audit. These are analytical
> opportunities latent in the existing data — no new rides needed.
> Each item is a standalone research/implementation task.

Status prefix: [PLAN] = design needed | [CODE] = implementable now

---

## BL-DI-01 — Batt_V confounder in map comparison (HIGH)
**Tags:** bug, correction, sessions-vs
**Status:** [DONE v2.7.277] (dead-time part); magnitude corrected below

### Finding (as originally stated — partially wrong, see correction)
Injector dead time varies inversely with battery voltage. The plan (and this
entry) claimed a 2-4% pw shift of the same magnitude as real map deltas.

### Correction (v2.7.277, validated against real data)
The dead-time part is REAL but SMALLER than claimed. Measuring pw-vs-Batt_V:
- At IDLE the slope is ~-0.60 ms/V, but that is mostly idle-control confound,
  NOT injector dead-time.
- At clean steady-cruise cells (the SWEET cells that matter) the empirical
  slope is -0.19 to -0.20 ms/V, matching the ECU's own Battery Voltage
  Correction table (~-0.16 ms/V near 14V). So the real dead-time artifact at
  the cells that drive tuning is ~0.6-1%, not 2-4%.
The "+2.31% fan-on shift" headline was inflated by idle-control confound.

### Done (v2.7.277)
Instead of the planned empirical linear guess (k=0.015), used the ECU's REAL
voltage→ms table: `ecu/ecm_defs.py:decode_batt_correction()` + `deadtime_ms()`
(XML-by-name, firmware-agnostic). `web/launch.py:build_index()` now computes
fueling as `pw − deadtime(Batt_V)` per row before pw_eff/dpw_eff. Raw pw1/pw2
kept for display. CACHE_VERSION 10→11. Cancels correctly where two sessions
share voltage profile; only shifts where they differ (fan-on fraction).

### Still open
- `web/f7.py` delta_pw not yet corrected (secondary; short WOT events).
- The larger idle voltage-correlation (~0.44 ms/V beyond dead-time) is real
  fueling response to fan-on conditions (hot idle + electrical load), NOT an
  artifact to subtract — if anything it argues for fan-state stratification of
  idle cells, not PW correction. Not pursued (idle cells aren't SWEET targets).

---

## BL-DI-02 — Stator death-watch via fan load step (HIGH)
**Tags:** reliability, monitoring, dashboard
**Status:** [PLAN]

### Finding
do_fan flips 0->1 hundreds to thousands of times per session. Each
fan-on event applies a known ~10 A load step. The instantaneous Batt_V
droop at that step is a direct measurement of charging-system source
impedance at that RPM. Tracked across 70+ rides, this is longitudinal
impedance spectroscopy of stator and regulator — free, no new hardware.
Rising droop trend at fixed RPM = replace stator in garage vs roadside.

### Action
1. Detect do_fan 0->1 edges per ride
2. Measure Batt_V droop magnitude at each edge (steady-state before vs
   nadir after, matched RPM)
3. Track trend across rides: avg droop vs ride date
4. Dashboard widget: Stator health: OK / WATCH / REPLACE

---

## BL-DI-03 — Virtual dyno drag calibration from coastdowns (HIGH)
**Tags:** vdyno, prerequisite
**Status:** [PLAN]

### Finding
The virtual dyno needs CdA and Crr. These are already latent in the
data: clutch-in (di_clutch=1) or neutral decel segments at TPS≈0 are
coastdown tests. gps_alt_m corrects for road slope. Fitting dV/dt across
these segments yields CdA + rolling resistance for this bike + rider.
NOTE: fl_fuel_cut never fires, so segment selection must use TPS +
clutch + gear, not the flag.

### Action
1. Extract coastdown segments: TPS<2, di_clutch=1, gear neutral or
   stable, gps_alt slope known
2. Fit dV/dt = -(1/2m)*rho*CdA*v^2 - Crr*g (least squares)
3. Store per-ride CdA/Crr, use as baseline for VDYNO power calc
4. Update docs/11_VDYNO_PLAN.md with calibration method

---

## BL-DI-04 — Intake leak detection via idle RPM trend (MEDIUM)
**Tags:** reliability, monitoring, engine-safety
**Status:** [PLAN]

### Finding
On Alpha-N with EGO disconnected, an intake leak changes nothing in fuel
channels — the ECU fuels off TPS and stays oblivious while engine runs
lean at small throttle openings (piston-burn regime). The one place a
leak must appear: idle. At fixed TPS, fixed pw, matched CLT and matched
air density (baro_hPa + baro_temp_c), idle RPM is determined by airflow.
A density-normalized idle-RPM-at-matched-CLT trend across 70+ rides is a
self-updating intake-leak detector.

### Action
1. Extract idle samples: TPS<2, RPM between idle_target and +200, CLT>70
2. Normalize RPM by air density (baro_hPa, baro_temp_c)
3. Track trend: avg idle RPM vs ride date
4. Alert if >3% drop from baseline

---

## BL-DI-05 — Weather as natural lambda sweep (MEDIUM)
**Tags:** analysis, fueling, no-wideband
**Status:** [PLAN]

### Finding
No KBaro, no EGO: fueling never adjusts for air density. Every change in
density altitude shifts effective lambda at every cell — +3% density ≈ 3%
leaner. Cross with F7 WOT events: if acceleration on dense days improves
more than density gain predicts, that map region was rich of best power;
if less, it's already lean. Answers which side of best power per cell
from data already on disk.

### Action
1. Compute density altitude per ride from baro_hPa + baro_temp_c
2. Group F7 WOT events by density quartile
3. For each RPM/TPS cell: compare ddvss vs density delta
4. Flag regions as RICH / LEAN / AT_BEST_POWER

---

## BL-DI-06 — Thermal protection stratum contamination (REFUTED BY DATA)
**Tags:** bug, correction, sessions-vs, f7
**Status:** [CLOSED 2026-07-02 — premise empirically false; kept documented per BACKLOG_VDYNO.md rules 6/7]

### Original claim
The rear cylinder runs hotter and triggers ECU protection (enrichment,
timing retard) not modeled anywhere in pipeline; fl_hot/do_fan samples
measure ECU self-defense, not the map, and should be excluded.

### What the data actually showed (89 rides, 14 sessions, 391,508 samples)
- **fl_hot is NOT a protection flag — it's a "warmed-up" indicator.**
  Flags6 bit 3 (protocol.py:305); flips ON at CLT median ~65°C, matching
  the EEPROM "Hot Start Condition" param (45°C, offset 156). fl_hot=1
  covers **95.1% of ALL samples** (fl_hot=0 = cold start, CLT mean 35°C).
  The proposed exclusion filter would have discarded 95% of the dataset.
- **No thermal-protection fueling/spark step exists in the warm regime:**
  matched RPM×TPS buckets, CLT band 200-240°C vs 140-180°C (163 buckets,
  ΔCLT +51°C): pw1 median +0.58% IQR [-3.12,+2.84]; spark +0.01°
  IQR [-0.17,+0.15]. No enrichment, no retard.
- **Real protection never engages in the entire dataset:** soft limit is
  280°C (gated RPM≥3500 + TPS≥80), hard limit 295°C (spark cut). Max CLT
  ever recorded = 280°C (one single sample). BUEIB.xml contains NO
  hot-enrichment fuel table — only Warmup Enrichment (exhausted ~140°C).
- **do_fan has a real but electrical effect:** fan-on at matched buckets
  drops Batt_V by −0.19V → pw1 +2.31% IQR [-0.39,+4.71] (injector
  dead-time path). fl_hot and do_fan are independent signals (only 33.7%
  overlap). User's fan thresholds: On=220°C, Off=180°C.

### Resulting actions
1. No thermal exclusion, no thermal stratification — CLT-band matching
   adds ≤±3% noise reduction at best; a warm-up inclusion gate (CLT≥80°C
   or fl_hot=1) is sufficient and the pipeline effectively has it already.
2. The REAL confounder confirmed here is Batt_V (fan-induced −0.19V ≈ +2%
   PW) → folded into BL-DI-01, which is now the single highest-value
   hygiene item, with empirical priors attached.
3. This item stands as the first applied case of BACKLOG_VDYNO.md rule 7
   (measure before filtering): the "one-line filter" would have quietly
   destroyed the dataset.

---

## BL-DI-07 — GPS/VSS ratio as tire wear gauge (HIGH)
🔍 **AUDITED 2026-07-03: duplicate** of BL-DI-11 below (~line 222), which has more method detail (heading-stable, CLT>70 filter). Merge into that one, delete this. Neither is built. Full detail in the AUDIT REPORT section at the top of `BACKLOG.md`.
**Tags:** calibration, monitoring
**Status:** [PLAN]

### Finding
VSS calibrator exists (protocol.py) but static. Rolling circumference
shrinks 1-2% new to worn. Steady-cruise gps_speed / VS_KPH ratio, one
number per ride, is a tire odometer and poor man's TPMS. Also time-stamps
tire changes retroactively. Tire radius drift feeds back into VDYNO
force calculations and gear detection (VSS_RPM_Ratio).

### Action
1. Compute gps_speed / VS_KPH per ride (steady cruise, >50 km/h)
2. Track trend across rides
3. Add calibration update suggestion when drift >1%
4. Feed radius correction into VDYNO and gear detector

---

## BL-DI-08 — Battery health from cranking data (LOW)
**Tags:** monitoring, battery
**Status:** [PLAN]

### Finding
Some rides open mid-crank (verified: 532 rpm at 10.05 V). Min cranking
voltage, time-to-stable-idle, and WUE-vs-CLT trajectory form battery
state-of-health curve and cold-start quality score per map.

### Action
1. Detect crank segments: RPM < idle, Batt_V dip
2. Record: min cranking V, cranking time, time to stable idle
3. Track trend

---

## BL-DI-09 — Lean angle from GPS heading rate (LOW)
**Tags:** rider analytics
**Status:** [PLAN]

### Finding
GPS heading rate × speed gives lateral acceleration and estimated lean
angle per corner. Riding insight, not tuning.

### Action
1. Compute lean_angle = atan(lat_accel / g) from GPS heading + speed
2. Store per-corner stats per ride
3. Dashboard: max lean, avg lean per ride

---

---

## BL-DI-11 — GPS/VSS ratio as tire wear and pressure gauge (HIGH)
🔍 **AUDITED 2026-07-03: duplicate** of BL-DI-07 above (~line 170). Keep this version (more method detail), delete the other. Full detail in the AUDIT REPORT section at the top of `BACKLOG.md`.
**Tags:** monitoring, tire, calibration
**Status:** [PLAN]

### Finding
VSS (transmission) vs GPS speed ratio measures rolling circumference.
Low pressure reduces radius ~1% per 4-6 PSI loss; tread wear drifts
1-2% over tire life. Effect is small per-ride but detectable as a
trend across multiple rides.

### Method
- Extract cruise samples: TPS stable, GPS heading stable (straight),
  speed > 50 km/h, CLT > 70 C
- Compute gps_speed / VS_KPH per ride (single ratio)
- Compare to rolling average of last N rides

### Action
1. One post-ride job (like f7) that computes per-ride ratio
2. Store in longitudinal JSON
3. Alert if ratio drops >1.5% from baseline (leak/tire change)
4. Feed radius correction into VDYNO force calc and gear detector

---

## BL-DI-12 — Pre-wideband execution plan: 4 phases (HIGH)
**Tags:** roadmap, hygiene, vdyno
**Status:** [PLAN]

### Finding
Deep analysis of what to extract from the dataset BEFORE installing a
wideband O2 sensor. The WB is powerful but installing it early causes
abandonment of the rest of the dataset. Four ordered phases proposed.

### Phase A — Hygiene (fixes systematic errors in existing pipeline)
1. **Voltage confounder test**: Regress pw residuals against Batt_V at
   matched RPM/TPS/CLT cells. If slope != 0, add Batt_V to cell-matching
   criteria in Sessions VS. One-afternoon script.
2. **Thermal filter**: Exclude fl_hot=1 or do_fan=1 samples from
   Sessions VS and F7 comparisons. One-line filter that sharpens all
   verdicts.
3. **Density normalization**: Calculate air density per sample from
   baro_hPa + baro_temp_c. Annotate in comparison caches.

### Phase B — Motorcycle health ledger (new post-ride job)
Compute 6 scalars per ride, append to longitudinal JSON:
- Voltage droop at do_fan 0->1 edge (stator health, THE classic XB failure)
- Batt_V vs RPM curve (same, slow view)
- Idle RPM normalized by density + CLT (intake leak detection — invisible
  to Alpha-N fueling)
- GPS/VSS ratio in cruise (tire wear/pressure)
- pw2/pw1 and spark1-spark2 at fixed cells (cylinder asymmetry)
- Min cranking voltage and time to stable idle (battery health)

### Phase C — Coastdown calibration (prerequisite for VDYNO)
Extract clutch-in/neutral segments at TPS≈0, correct slope with gps_alt,
fit CdA + rolling resistance. Data already exists in 70+ rides.

### Phase D — Weather as mixture sweep (ambitious, do last)
1. Histogram of air density across all rides (cheap check)
2. If spread > +/-3%, cross F7 WOT events with density to infer
   which side of best power each map region is on
3. When WB is eventually installed, this inference can be validated

---

## BL-DI-13 — Rust rewrite: not recommended (LOW)
**Tags:** decision, architecture
**Status:** [PLAN] — analysis complete, no action needed

### Finding
Rust was evaluated as a potential rewrite language. Verdict: not worth
it for this project. Reasons:
- Speed: bottleneck is ECU serial at 4.6 Hz, not Python. CPU idle at 19%.
- Safety: real past bugs (WiFi drops, OOM, serial race) are system-level,
  not language-level. Rust prevents none of them.
- Cost: rewriting 8000 lines, losing iteration speed (fix_*.py in minutes)

### Recommendation
Get 60% of Rust's benefit at 5% cost: add Python type hints to all
function signatures + run ruff/mypy as CI check. Catches wrong types,
dict key typos, unexpected None — without rewriting anything.

### When Rust WOULD make sense
- Sampling at kHz (crank-domain misfire detection)
- Microcontroller battery budget
- Real-time signal processing
None of these are on the roadmap. A future sensor module could be written
in Rust as a separate component, not a project rewrite.