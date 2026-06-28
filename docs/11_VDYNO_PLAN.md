# 11 — VDYNO Implementation Plan (step-by-step, model-agnostic)

> Companion to `BACKLOG_VDYNO.md` (vision + physics). This file is the
> EXECUTION plan: exact files, schemas, validation commands. Written so any
> AI model (or human) can pick up any phase cold. Read `CLAUDE.md` first —
> all its rules apply (English only, changelog prepend, commit order,
> data-reuse principle, OL-mode constraints).

## Project north star (user-confirmed 2026-06-11)

Measure engine power. The system collects data every ride, compares across
rides/maps, and ultimately proposes map improvements. HARD RULES:

1. **The system NEVER writes the EEPROM on its own.** The automated pipeline
   ends at a proposal staged in the VE tab. The user always loads/burns
   manually. Before burning anything, the user is always asked.
2. **Every proposal gets a new map identity** (tune checksum) so lineage is
   unambiguous.
3. **Verdicts respect the noise floor.** Measure intra-map ride-to-ride
   variance first; if |ΔP| between maps is below it, verdict is
   INCONCLUSIVE — never forced.

## Map identity (use everywhere, do not invent a new one)

```python
# ecu/session.py — SessionManager._checksum
hashlib.md5(blob[327:]).hexdigest()[:6].upper()   # tune region only
```

Session IDs (e.g. 248AE2) ARE map identities. After a verified burn,
`ecu/logger_process.py` immediately opens a new session from the proposed
blob — so a ledger child checksum equals the future session ID. Lineage
joins against existing session data with no extra mapping.

---

## PHASE V0 — Burn ledger (BL-VD-04) — STATUS: implemented v2.7.123

Append-only record of every EEPROM burn. Records only; never writes ECU.

**Files:**
- `web/burn_ledger.py` (new): `tune_checksum(blob)`, `diff_maps(old, new)`,
  `record_burn(buell_dir, entry)`, `load_burns(buell_dir)`.
  Storage: `/home/pi/buell/burns.json`, atomic write (tmp + os.replace).
- `web/handlers/eeprom.py` → `_handle_eeprom_burn`: after the IPC result
  arrives, decode parent (`current_bin`) and child (`proposed`) maps, diff,
  `record_burn(...)`. Wrapped in try/except — a ledger failure must NEVER
  block the burn response. Also `_handle_burns_list` for GET `/burns`.
- `web/server.py`: route `'/burns'` in the GET table.
- UI: VE tab (`index.html` `#pane-ve`, below `#mapContainer`) — "BURN
  HISTORY" section; `app.js` `loadBurnLedger()` called from `loadMaps()`
  and after a successful `burnStaged()`.

**Entry schema (burns.json is a JSON array):**
```json
{
  "ts_utc": "2026-06-11T20:15:00+00:00",
  "parent": "248AE2",          // tune_checksum(current_bin)
  "child": "9F12AB",           // tune_checksum(proposed) == next session id
  "source_session": "248AE2",  // session whose eeprom.bin was used as base
  "verified": true,             // from ECU write result
  "n_cells": 7,
  "cells": [{"map":"fuel_front","ri":3,"ci":5,"old":88.0,"new":91.0}],
  "maps_touched": ["fuel_front"],
  "backup": "eeprom_backup_20260611_201500.bin"
}
```

**Validation (run on the Pi):**
```bash
cd /home/pi/buell
python3 -c "from web.burn_ledger import tune_checksum, diff_maps; print('OK')"
python3 -c "from web.server import WebServer; print('OK')"
# restart server (see CLAUDE.md), then:
curl -s http://localhost:8080/burns | python3 -m json.tool
# UI: VE tab shows BURN HISTORY section (empty state until first burn)
```

---

## PHASE V1 — Virtual dyno engine (BL-VD-01/02)

**Physics** (constants configurable in `vdyno_config.json` at buell root):

```
P_wheel = (m*a + 0.5*rho*CdA*v^2 + Crr*m*g + m*g*sin(theta)) * v
rho = p/(R_d*T_k) adjusted for humidity   # baro_hPa, baro_temp_c, humidity_pct
theta = d(gps_alt_m)/d(distance), heavily smoothed
a = dv/dt from VS_KPH, Savitzky-Golay (window ~1.5 s); compare GPS spd as
    a second source, prefer the lower-variance one per segment
T_engine = P_wheel / omega_engine / drivetrain_eff (default 0.91)
```

Defaults: `mass_kg` = 295 (bike wet + rider; refine with fuel_tracker
liters), `CdA` = 0.60, `Crr` = 0.015. Absolute error does not matter —
the instrument is DIFFERENTIAL (same bike, same rider, A-vs-B maps).

**Steps:**
1. `web/vdyno.py` (new, lazy-imported like proposal.py was — Pi Zero RAM):
   - Input: one ride CSV + its `ride_*_f7events.json` (F7 WOT events are
     the clean segments: stable gear, high TPS). Reuse `f7._load_csv_rows`
     column parsing — do NOT write a new CSV parser.
   - Filter: fl_decel off, gear_detected stable, TPS_pct above threshold
     (start 80%), at least 2 s long.
   - Output cache: `sessions/<cs>/ride_NNN_vdyno.json`:
     `{rpm_bins:[{rpm:4250, p_kw_med, p_kw_sigma, n}], conditions:{rho,
     temp_c, baro_hPa, mass_kg, gear}}` — bins of 250 RPM, median + sigma.
2. Endpoint `GET /vdyno?session=X&ride=N` → compute-on-miss, cache like f7.
3. Endpoint `GET /vdyno/compare?a=CS_A&b=CS_B` → merged bins, ΔP per bin,
   pooled sigma. Reuse the sessions_vs session-pair selector pattern.
4. UI: new subtab "Dyno" inside Sessions VS page (data-reuse rule: no new
   page). Chart.js line: P vs RPM, one line per session, shaded sigma band.

**Validation:** pick session 248AE2 (40 rides, richest), compute one ride,
sanity-check peak power 60–90 hp at the wheel for an XB12X — order of
magnitude only; the differential use is what matters.

## PHASE V2 — Environmental normalization (BL-VD-03)

- SAE J1349-style correction of P to standard rho_0; show density altitude
  per ride (stat card in ride summary + Sessions VS header).
- Noise floor tool: `GET /vdyno/noise?session=X` → pairwise ΔP between
  rides of the SAME map = the floor that V3 verdicts must beat.

## PHASE V3 — Burn verdict + evidence instructor (BL-VD-05/06)

1. After a ride closes (hook where ride_summary is written), if the active
   map has a parent in burns.json: compare vdyno bins + sessions_vs cells
   (only cells touched by that burn), conditions matched by density
   altitude (±150 m) and CLT warm.
2. Verdict per RPM bin and per touched cell: BETTER / WORSE / INCONCLUSIVE
   (must beat the V2 noise floor). Store `sessions/<cs>/burn_verdict.json`.
3. Dashboard card after ride close: verdict summary + EVIDENCE INSTRUCTOR:
   which gear/RPM/TPS ranges still lack samples, phrased as a concrete
   instruction ("need one WOT pull, 3rd gear, 4000-6000 RPM").
4. The same coverage logic shown BEFORE a ride as "mission of the day".

## PHASE V4 — Proposal to VE tab (BL-VD-07) — the pipeline's end

- FASE 6 proposal engine (recoverable from git: v2.7.115, commit 0539360,
  reverted in v2.7.116) consumes vdyno + VS cells + burn history, emits a
  proposed map with its NEW tune checksum.
- The proposal appears in the VE tab as staged cells (orange, like manual
  edits today) for the user to review, load and burn MANUALLY.
- HARD RULE 1 applies: no auto-burn, ever. The system asks; the user acts.

---

## Conventions for whoever implements any phase

- One phase step = one commit = one CHANGELOG entry (prepend script — see
  CLAUDE.md, never `cat >>`).
- Validate each step on the Pi before the next (import check → restart →
  curl → UI). Add a freebuff validation task to
  `C:/Users/pacda/freebuff/TASKS.md` after each commit.
- Pi Zero 2W has ~400 MB free RAM: lazy imports, per-ride computation,
  JSON caches, never load whole sessions into memory at once.
- OL mode: nothing may depend on EGO_Corr/AFV (constant 100).
- New UI goes inside existing tabs/pages (data-reuse rule).
