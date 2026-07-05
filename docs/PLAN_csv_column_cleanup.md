# PLAN: CSV Column Cleanup — Remove Captured Unused Signals

**Date:** 2026-07-03  
**Status:** ANALYSIS COMPLETE  
**Based on:** `data_pipelines_by_sector.html` Sector 7 — Captured Unused  

---

## Current Cost

| Metric | Value |
|--------|-------|
| Total CSV columns | 98 |
| Never consumed by tuning | 18 columns (18.4%) |
| Rows per second | ~8 Hz |
| Wasted bytes per ride (1h) | ~500 KB |
| Storage wasted (1000 rides) | ~500 MB |

---

## Triage by Signal

### 🟢 REMOVE (zero impact, no consumer exists)

| Columns | Reason | GAP Ref |
|---------|--------|---------|
| `dirty_byte_hex`, `dirty_byte_name`, `forensic_event` | Only consumed manually via errorlog_viz. Serial corruption is extremely rare (<0.01% of rows). **Automated detection via checksum is sufficient.** | — |
| `CDiag0`-`CDiag4`, `HDiag0`-`HDiag4` (10 cols) | IDEA-005 proposed fault-mining, never implemented. **No consumer exists.** 40KB/hour saved. | IDEA-005 |
| `O2_ADC` | Disconnected narrowband → always noise. Piped to tuning_report (INACTIVE_NOISE). **Meaningless data.** | INACTIVE_NOISE |
| `EGO_Corr` | Locked at 100.0. Entire tuning_report pipeline is INACTIVE_NOISE. **Remove from CSV AND disable _update_tuning_report().** | INACTIVE_NOISE |
| `AFV` | Locked at 100.0. Same as EGO_Corr. **Keep only if wideband installed.** | INACTIVE_NOISE |

### 🟡 REDUCE FREQUENCY (keep but log less often)

| Columns | Plan | Reason |
|---------|------|--------|
| `humidity_pct` | Log every 60s instead of every row (8 Hz → 0.017 Hz) | Descriptive metadata only, never used in deltas. Good for climatology but doesn't need per-row resolution. |
| `baro_temp_c` | Already logged at sysmon rate (~1 Hz). Verify no higher-rate path exists. | Descriptive, used in env_stats. Fine at 1 Hz. |
| `gps_*` (10+ columns) | GPS already runs at 1-10 Hz independent of ECU. No change needed — but verify we don't store redundant GPS data faster than the receiver provides it. | — |

### 🔵 ADD VALIDATION (Batt_V — keep but USE it)

| Columns | Plan | Reason |
|---------|------|--------|
| `Batt_V` | **KEEP** — but add voltage dead-time correction (see PLAN_confounders.md) | BL-DI-01: 2.3% PW shift proven. This is a **confounder, not noise**. |

### 🟢 REMOVE — Dead Code Fields

| Field | File | Reason |
|-------|------|--------|
| `session_metadata["rider_notes"]` | `ecu/session.py` | Initialized as `[]`. No write endpoint. No UI. Fully dead. |

---

## Implementation Plan

### Phase 1: Safe Removals (1h, zero risk)

1. **Remove `dirty_byte_*` from `CSV_COLUMNS`** in `ecu/protocol.py`
2. **Remove `CDiag*`, `HDiag*` from `CSV_COLUMNS`**
3. **Remove `rider_notes` initialization** from `session.py:_load_or_create()`
4. **Remove `AFV`, `EGO_Corr` from all VS engine code** (already unused since locked at 100)

### Phase 2: Disable INACTIVE_NOISE Pipeline (2h)

1. **Gate `_update_tuning_report()`** behind a config flag `tuning_report_enabled: false`
2. When flag is false, skip the entire tuning_report generation + suggested_msq
3. **Remove `O2_ADC` accumulation** from `CellTracker` (saves 8 bytes/frame → 230KB/hour)

### Phase 3: Logging Rate Optimization (1h)

1. Add `ride_csv` metadata header: `# humidity_interval=60`
2. Write humidity only when `sample_count % (60*8) == 0`

### Phase 4: Validation (1h)

1. Run regression: load all existing CSVs → verify no downstream code crashes without removed columns
2. Verify `csv.DictReader` with `extrasaction="ignore"` in all consumers handles missing columns gracefully

---

## Column Removal Detail

### protocol.py — CSV_COLUMNS before/after

```python
# BEFORE: 98 columns
CSV_COLUMNS = [
    "ride_num", "timestamp_iso", "time_elapsed_s",
    "RPM", "Load", "TPD", "TPS_10Bit", "CLT", "MAT", "Batt_V",
    "spark1", "spark2", "veCurr1_RAW", "veCurr2_RAW", "pw1", "pw2",
    "EGO_Corr", "WUE", "AFV", "IAT_Corr", "Accel_Corr", "Decel_Corr",
    "WOT_Corr", "Idle_Corr", "OL_Corr", "O2_ADC",
    "Flags0", "Flags1", "Flags2", "Flags3", "Flags4", "Flags5", "Flags6", "Unk63",
    "Unk63_b0", "Unk63_b1", "Unk63_b2", "Unk63_b3", "Unk63_b4", "Unk63_b5", "Unk63_b6", "Unk63_b7",
    "CDiag0", "CDiag1", "CDiag2", "CDiag3", "CDiag4",
    "HDiag0", "HDiag1", "HDiag2", "HDiag3", "HDiag4",
    "Rides", "DIn", "DOut", "ETS_ADC", "IAT_ADC", "BAS_ADC", "SysConfig",
    "TPS_V", "TPS_pct",
    "VSS_Count", "VS_KPH", "Fan_Duty_Pct", "VSS_RPM_Ratio", "Gear",
    "dirty_byte_hex", "dirty_byte_name", "forensic_event",
    # flags...
    "fl_engine_run", "fl_o2_active", "fl_accel", "fl_decel", "fl_engine_stop", "fl_wot", "fl_ignition",
    "fl_closed_loop", "fl_rich", "fl_learn",
    "fl_cam_active", "fl_kill", "fl_immob",
    "fl_fuel_cut",
    "fl_hot",
    "do_coil1", "do_coil2", "do_inj1", "do_inj2", "do_fuel_pump", "do_tacho", "do_cel", "do_fan",
    "di_cam", "di_tacho_fb", "di_vss", "di_clutch", "di_neutral", "di_crank",
    "buf_in",
    "ttl_pct", "cpu_pct", "cpu_temp", "mem_pct",
    "gps_lat", "gps_lon", "gps_alt_m", "gps_speed_kmh", "gps_heading", "gps_satellites", "gps_valid",
    "gps_mode", "gps_epx", "gps_epy", "gps_epv", "gps_snr_avg",
    "gps_heading_rate", "gps_turning", "gps_stale",
    "baro_hPa", "baro_temp_c",
    "humidity_pct",
]

# AFTER: 77 columns (remove 21)
CSV_COLUMNS = [
    # ... keep all tuning-relevant columns ...
    # REMOVE: EGO_Corr, AFV, O2_ADC  (INACTIVE_NOISE — locked at 100.0)
    # REMOVE: CDiag0-4, HDiag0-4  (no consumer)
    # REMOVE: dirty_byte_hex, dirty_byte_name, forensic_event  (manual only)
    # REMOVE: Unk63_b0-7 (already present as Unk63 byte; bits decomposed only for manual debug)
    # KEEP: Batt_V (confounder — needs correction, not removal)
    # KEEP: humidity_pct (but log at 1/480 Hz)
]
```

---

## Backward Compatibility

All CSV consumers use `csv.DictReader` which ignores extra columns and uses `None` for missing columns. The removed columns are:

- **CDiag, HDiag**: No code path reads these from CSV. Green to remove.
- **dirty_byte_***: Only `RideErrorLog.dirty_bytes()` writes to errorlog, not from CSV. Green to remove.
- **EGO_Corr, AFV**: `build_index()` reads these but they're always 100.0 → change to constant 100.0 in code. Green to remove.
- **O2_ADC**: `CellTracker.update()` accumulates it. Remove accumulation. Green to remove.
- **Unk63_bits**: Individual bits of `Unk63` byte. The byte itself stays. Green to remove individual bit columns.
