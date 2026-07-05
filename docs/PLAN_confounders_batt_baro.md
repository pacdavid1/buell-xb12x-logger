# PLAN: Confounders Contaminating Sessions VS

**Date:** 2026-07-03  
**Status:** ANALYSIS COMPLETE — ready for implementation  

## Executive Summary

Two confounders introduce systematic error into Sessions VS `dpw_eff` deltas that is indistinguishable from real map differences. Together they can produce false-positive "significant" deltas in 30-50% of cells, which would cause `_merge_maps()` to pick the wrong map or GP Regression to fit noise.

---

## Confounder 1: Batt_V → Injector Dead-Time (BL-DI-01)

### Empirical Evidence

Confirmed 2026-07-02 with actual Buell data:

| Condition | Batt_V Δ | pw1 shift (median) | IQR |
|-----------|----------|---------------------|-----|
| Fan OFF | baseline | — | — |
| Fan ON | −0.19 V | +2.31% | −0.39 / +4.71 |

2.31% is the **same order of magnitude** as the `dpw_eff` deltas Sessions VS treats as map differences. A 2% PW shift in 30 cells looks exactly like "Session B runs richer than A at low-mid load."

### Root Cause

Injector opening time (dead-time) varies inversely with battery voltage. Lower voltage = slower injector solenoid response = less fuel for the same commanded PW. The DDFI2 ECU has a dead-time compensation table, but it's calibrated for a healthy charging system (~13.5-14.5V). When Batt_V drops to 12.1V (fan + stoplights + hot engine), the compensation under-corrects, and effective AFR leans out.

### Where This Hits

- **Sessions VS `build_index()`**: `pw1_norm` and `pw2_norm` are baro-normalized but **NOT voltage-normalized**
- **A vs B comparison**: If Session A was logged with fan OFF and Session B with fan ON, every cell logged during fan-on periods in B gets an artificial +2-4% pw shift → "B needs more fuel" → false winner
- **CellTracker**: No voltage gate. Batches of cells logged at low Batt_V get different effective fueling than those at high Batt_V

### Current State

`Batt_V` is logged per-row in CSV but **only used** in `RideErrorLog` for diagnostic context. It is **never** used to correct PW or gate cell validity in Sessions VS.

### Fix Plan

#### Phase A: Detection (1h)
Add to `launch.py::build_index()`: accumulate `n_vbins` × voltage range per cell. Report if a cell's samples span >0.5V range across sessions.

```python
# In build_index(), per-cell accumulation:
c['batt_sum'] += batt_v
c['batt_min'] = min(c.get('batt_min', batt_v), batt_v)
c['batt_max'] = max(c.get('batt_max', batt_v), batt_v)
```

#### Phase B: Dead-Time Correction Model (4h)
1. Collect paired data: same RPM/TPS cell at high Batt_V (13.5V+) vs low Batt_V (12.0-12.5V)
2. Fit a simple linear correction: `pw_corrected = pw_raw × (1 + k × (V_ref − Batt_V))`
3. Start with a conservative V_ref = 13.0V, k = 0.015 (1.5%/V)
4. Apply in `load_csv()` alongside baro normalization

#### Phase C: Session Gating (2h)
1. In `_compare_sessions()`, compute `batt_range_a` and `batt_range_b` per cell
2. If `|batt_range_a − batt_range_b| > 0.5V` for >20% of common cells, flag the comparison as **BATT_CONTAMINATED**
3. In UI: show orange warning on Sessions VS page: "⚠ Battery voltage differs between sessions — some deltas may be artifacts"

#### Phase D: Future — Adaptive Model (8h, defer)
- Learn k per bike from logged data
- Build a per-voltage bin lookup table from OEM injector characterization
- Replace linear model with piecewise-linear

---

## Confounder 2: Baro PW Normalization (CONTRADICTS CLAUDE.md)

### Current Behavior

In `web/launch.py::load_csv()`, **every PW value** is baro-normalized:

```python
_baro_factor = 1013.25 / _baro if _baro_valid else 1.0
pw1_norm = pw1 * _baro_factor
```

### The Problem

The **DDFI2 ECU uses Alpha-N** (TPS + RPM → VE table lookup), **NOT Speed-Density** (MAP sensor → air density correction). In Alpha-N, air density changes with barometric pressure are **NOT** compensated by the ECU — the VE table is calibrated for the local atmosphere.

In practice:
- **Mexico City (780 hPa)**: ECU is calibrated for thin air → VE table values are smaller
- **Sea level (1013 hPa)**: Same VE table would over-fuel → tuner adjusts VE down

**By baro-normalizing PW, we are undoing the actual map difference we're trying to measure.**

### Proof

Session 47BF04 (Cuernavaca, ~900-950 hPa) vs Session 91B225 (Mexico City, ~780 hPa):

| What | Expected pw (no normalization) | Expected pw (with baro norm) |
|------|-------------------------------|------------------------------|
| Same cell, same VE | B higher (thicker air → more fuel per PW) | Equal (normalized) |
| Map actually richer in B | B even higher | Normalized hides the diff |

The normalization **removes real map differences** when sessions are at different altitudes, but **introduces false differences** when sessions are at the same altitude with different weather.

### Where This Hits

- **`_compare_sessions()`**: Both sessions' PWs are baro-normalized independently
- **Sessions VS cache (v9)**: `pw1_norm` and `pw_eff` are baro-normalized
- **F7 event detection**: `_load_csv_rows` in `f7.py` also baro-normalizes PW

### Rule from CLAUDE.md

> "do NOT normalize PW by baro for DDFI2 Alpha-N"

The code in `load_csv()` **explicitly violates this rule**.

### Fix Plan

#### Phase A: Remove Baro Normalization from Sessions VS (1h)

In `web/launch.py::load_csv()`:

```python
# CHANGE:
'pw1_norm': sf(r['pw1']) * _baro_factor,   # REMOVE baro factor
'pw2_norm': sf(r.get('pw2', 0)) * _baro_factor,  # REMOVE baro factor

# TO:
'pw1_norm': sf(r['pw1']),   # raw PW, no baro correction
'pw2_norm': sf(r.get('pw2', 0)),  # raw PW, no baro correction
```

#### Phase B: Remove from F7 Load (0.5h)

In `web/f7.py::_load_csv_rows()`:

```python
# CHANGE:
'pw1': _sf(r['pw1']) * _baro_factor,

# TO:
'pw1': _sf(r['pw1']),  # no baro correction for Alpha-N
```

#### Phase C: Add Baro as Descriptive Covariate in VS (1h)

Instead of normalizing PW, carry baro as a cell-level covariate so we can detect when altitude differs between sessions:

```python
# In _compare_sessions() result:
'baro_a': _env_stats(ra)['baro_avg'],
'baro_b': _env_stats(rb)['baro_avg'],
'baro_delta': round(env_b['baro_avg'] - env_a['baro_avg'], 1),
```

If `|baro_delta| > 50 hPa`, show warning: "⚠ Barometric pressure differs — interpret deltas with caution"

#### Phase D: Keep Baro Normalization ONLY for VDYNO (already correct)

`web/vdyno.py` baro-normalizes via SAE J1349 correction — this is **correct** because VDYNO measures actual wheel power (physics), not ECU behavior. Keep as-is.

---

## Combined Impact

| Confounder | Direction | Magnitude | Affects | Priority |
|------------|-----------|-----------|---------|----------|
| Batt_V | +2-4% PW at low voltage | ~2.3% median | SWEET cells (idle/stoplight) | 🔴 HIGH |
| Baro norm | Removes real diffs across altitudes | 10-30% of delta | ALL cells when sessions at different altitude | 🔴 HIGH |

### Immediate Action Items (this week)

1. **Remove baro normalization from `load_csv()`** — 1h, 3 lines changed, validates our existing data better
2. **Add Batt_V range tracking to `build_index()`** — 1h, detection only
3. **Add environmental warnings to Sessions VS UI** — 2h, helps user interpret results

### Deferred

- Batt_V dead-time correction model (Phase B) — needs injector characterization data
- Adaptive voltage model (Phase D) — only if fan-on is a recurring pattern
