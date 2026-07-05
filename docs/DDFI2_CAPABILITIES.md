# DDFI2 ECU — Capabilities Reference (ground truth)

> **Purpose:** stop hallucinating capabilities this ECU does not have. Every claim here is
> derived from the actual artifacts, not from generic EFI knowledge:
> - `ecu_defs/BUEIB.xml` — 238 EEPROM parameters (the tunable/config surface)
> - `ecu_defs/rtdata.xml` — the real-time serial protocol fields
> - a real ride CSV header — what is actually logged (98 columns)
> - the decoded `eeprom.bin` of session 248AE2 — actual values on this bike
>
> **If a technique needs a capability NOT listed under "What the ECU HAS", it does not apply
> to this bike. Say so in the first line of any finding.**

Bike: **Buell XB12** — air/oil/fan-cooled **45° V-twin**, ~1203cc, Harley Sportster-derived.
ECU: **Delphi DDFI2**, firmware family **BUEIB** (e.g. "BUEIB310"). Serial data logger on a
Raspberry Pi. Runs **Open Loop** on this bike (see "This bike's config").

---

## 1. Core architecture (verified)

- **Fueling is Alpha-N as the PRIMARY lookup:** `Fuel Map Front` / `Fuel Map Rear`, each a 2D
  table indexed by **Load (TPS-derived, 8-bit) × RPM**. There is **no MAP sensor** driving a
  speed-density fuel calc. Load comes from throttle position, not manifold pressure.
- **Per-cylinder EVERYTHING:** separate `Fuel Map Front`/`Fuel Map Rear`, separate
  `Timing Table Front`/`Timing Table Rear`, plus `Front Cylinder Correction`, `AFV Front`/
  `AFV Rear`, `EGO Correction Front`, per-injector `pw1`/`pw2`, per-coil `spark1`/`spark2`,
  per-cylinder VE (`veCurr1_RAW`/`veCurr2_RAW`). **The hardware fully supports independent
  front/rear tuning** — and the factory front/rear fuel maps ARE already different (measured
  248AE2: mean 3.8, max 19 units apart). This is why per-cylinder work (BL-VS-PERCYL,
  IDEA-035) is real, not speculative.
- **Uneven firing:** 45° V-twin, single crankpin → the two power strokes are at distinct,
  known crank angles. Relevant to per-cylinder crank-speed / vibration inference.
- **Map→PW is affine:** measured `pw1_base ≈ 0.055 × fuel_map_value − 1.38 ms` (R²=0.95).
  Linear but NOT purely proportional — "% of map" ≠ "% of PW".

## 2. What the ECU HAS (real subsystems, from the 238 EEPROM params)

**Fuel:**
- Front/Rear fuel maps (Alpha-N), `Startup Fuel Pulsewidth`, `Startup Enrichment` (temp map),
  `Warmup Enrichment`, `Hot Start Condition`, `Open Loop Default Correction`,
  `Open Loop Enrichment Delay`.
- `Acceleration Enrichment` (+ Region, Temp Adjustment, Duration) — the "AE" (`Accel_Corr`).
- `Deceleration Correction` + **Deceleration LEARN** (the ECU has a decel-learn feature:
  Learn Min/Max RPM, Min Duration, Min Readings).
- `WOT Enrichment` / `WOT Region`, `Idle Correction`.
- `Front Cylinder Correction`, `Air Temperature Correction` (IAT), `Battery Voltage
  Correction` (**injector dead-time**, voltage→ms), `Baro Correction`, `Airbox Pressure
  Correction`, `Altitude Adjustment`.
- `Fuel PI Controller` (P/I values for high/low/idle) — closed-loop fuel controller **in
  firmware**.
- Injector dead-time table decoded live at `ecu/ecm_defs.py:decode_batt_correction()`.

**Spark:**
- Front/Rear timing maps (Load × RPM), `Dwell Duration`, `Idle Spark Advance Temperature
  Adjustment`, `WOT Spark Advance Reduction`, and a full **Spark Advance Reduction** system
  keyed on VSS/RPM ratio with RPM boundaries and ramp in/hold/out (gear/speed-based retard).
- **Spark is COMPUTED from the maps + reductions. It is NOT closed-loop and NOT knock-adjusted.**

**Closed-loop / O2 (IN FIRMWARE — but see "This bike's config"):**
- Full narrowband closed-loop machinery exists: `O2 Sensor Target/Rich/Lean Voltage`,
  `Closed Loop Feature Minimum RPM/Throttle`, `Closed Loop Region Upper/Lower Boundary`,
  `EGO Correction Max/Min`, `AFV` (Adaptive Fuel Value) with Increase/Decrease factors and
  storage, `Calibration Mode`. The protocol even streams `AFR Front`/`AFR Rear`/`Catalyst
  O2 Sensor`. **This is a NARROWBAND (switching) system, not wideband** — it can only find
  stoich (λ=1), it cannot measure how rich/lean at WOT.

**Sensors the ECU reads (inputs):**
- TPS (10-bit), Engine Temp (CLT), Air Temp (MAT/IAT), Battery Voltage, **Baro Pressure
  Sensor**, **Airbox Pressure (ABP)**, Bank Angle Sensor (`BAS`, tip-over Hall), narrowband
  O2 (front/rear + catalyst positions), cam & crank position, VSS, tacho, clutch/neutral
  digital inputs, injector/coil/fuel-pump/fan **feedback** (health monitoring).

**Actuators & features the ECU controls (outputs):**
- Injectors (front/rear), coils (front/rear), fuel pump (duty-cycle controlled), cooling fan
  (key-on AND key-off run logic, duty cycle, min battery voltage), CEL, tacho, **Active
  Muffler** (exhaust valve, RPM switching points), **Active Intake** (variable intake,
  ramp/hold duty).
- **Rev/temp protection ladder:** RPM Soft / Hard / Kill limits (fixed + speed-timed + gear-
  aware), Temperature Soft / Hard / Kill limits (the thermal protection we already mapped:
  soft ~280°C gated on RPM+TPS, hard ~295°C spark cut, kill ~305°C).
- Full DTC / error system (`Current Errors` bytes, `Error Mask`, per-sensor error counters,
  `Rides Required to Clear DTC`).

## 3. What the ECU does NOT have (anti-hallucination list)

- ❌ **No knock/detonation sensor** — none. No piezo, no knock flag, no knock retard. `spark1`/
  `spark2` are map-computed advance, never adjusted for detonation. Any knock-based method
  requires ADDED hardware. (Detonation can only be caught by rider ear, plug reads, or EGT.)
- ❌ **No wideband O2** — the O2 system is narrowband (switching) only. It cannot quantify AFR;
  at WOT (rich) it saturates and reports nothing useful. This is the core project constraint.
- ❌ **No MAP-sensor speed-density fuel calc** — Alpha-N. (It DOES have baro + airbox pressure
  *corrections*, see the gotcha below — but the primary fuel table is TPS×RPM, not MAP.)
- ❌ **No EGT / exhaust temp sensor** from the factory. (`ETS_ADC` is logged but its meaning is
  unconfirmed — treat as spare/unused, not a working exhaust thermocouple.)
- ❌ **No individual-cylinder O2 on this bike** (the protocol has front/rear AFR fields, but the
  hardware isn't there — see next section).
- ❌ **No CAN bus** for tuning — serial (TTL-level) protocol only.

## 4. THIS bike's configuration (what's disconnected/locked)

- **O2 sensor is physically DISCONNECTED → the bike runs Open Loop.** Consequently, in the
  logs: `EGO_Corr` = 100 (locked), `AFV` = 100 (locked), `O2_ADC` ≈ noise, `fl_closed_loop`
  never true. All the closed-loop/AFV/EGO firmware machinery is dormant. **The `AFR Front`/
  `AFR Rear` protocol fields are meaningless on this bike.**
- Fan thresholds on this tune: `KTemp_Fan_On` = 220°C, `KTemp_Fan_Off` = 180°C.
- Baro/Airbox/Front-Cylinder correction tables are present and non-zero in the tune (see gotcha).

## 5. What is actually LOGGED (the 98 CSV columns we can analyze)

Real signals we have per row: `RPM`, `Load`, `TPD`/`TPS_pct`/`TPS_10Bit`/`TPS_V`, `CLT`, `MAT`,
`Batt_V`, `spark1`/`spark2`, `veCurr1_RAW`/`veCurr2_RAW`, `pw1`/`pw2`, `WUE`, `IAT_Corr`,
`Accel_Corr`, `Decel_Corr`, `WOT_Corr`, `Idle_Corr`, `OL_Corr`, `VSS_Count`/`VS_KPH`/`Gear`/
`VSS_RPM_Ratio`, `Fan_Duty_Pct`, `BAS_ADC`, `ETS_ADC`, `IAT_ADC`, baro (external BMP280), GPS,
sysmon (`cpu_temp` etc.), and the flag/DO/DI bits (`fl_*`, `do_*`, `di_*`).

**Locked/noise (do not use as signal):** `EGO_Corr`, `AFV`, `O2_ADC` (O2 disconnected).

## 6. Gotchas / nuances (get these right)

- **"DDFI2 is pressure-blind Alpha-N" is an oversimplification.** The PRIMARY fuel lookup is
  Alpha-N (Load×RPM), BUT the EEPROM has ACTIVE, non-zero `Baro Correction` and `Airbox
  Pressure Correction` tables, and the ECU reads both a baro sensor and airbox pressure (ABP).
  So the ECU DOES apply pressure-based fuel corrections. **Implication:** logged `pw1`/`pw2`
  are the FINAL commanded pulse *after* whatever corrections the ECU applied (baro, IAT,
  battery dead-time, etc.). This is why analysis-side baro-normalization was removed
  (v2.7.276) — but the correct reason is "the ECU already applied its own baro correction and
  the logged PW reflects it; re-normalizing double-corrects," NOT "the ECU ignores baro."
  ⚠️ CLAUDE.md's "barometric pressure does NOT enter the fuel equation" and the v2.7.276
  commit comment are imprecise on this point and should be reworded (conclusion still holds).
- **Logged PW is post-correction.** When comparing sessions, `pw1`/`pw2` already bake in
  IAT/baro/dead-time/warmup corrections. dpw_eff is a comparison of final commanded pulses,
  which is what we want — but don't re-apply corrections the ECU already did.
- **Per-cylinder correction table state:** `Front Cylinder Correction` exists and is populated;
  on this tune the front/rear split appears to live mainly in the separate Fuel Maps rather
  than that trim table. Decode carefully before assuming its exact effect.
- **Narrowband ≠ nothing at WOT.** Even if the O2 were connected, a narrowband can't tune WOT
  (it saturates rich). The WOT blind spot is universal, not unique to our disconnected setup.

---

*Generated 2026-07-04 from BUEIB.xml (238 params), rtdata.xml, ride CSV (98 cols), and the
decoded 248AE2 eeprom.bin. Re-verify against `ecu_defs/<firmware>.xml` if the firmware differs.*
