# BACKLOG — Rescue from buell_fable5 fork

> Source fork: `buell_fable5` (commit `b16d932`, 2026-07-05)
> Audited: 2026-07-06
> Purpose: catalog everything worth rescuing from the fable5 experiment back into
> the main buell repo, prioritized by impact and effort.

The fable5 fork was a clean rewrite of the analysis pipeline (`measure/` package)
with validated PW research, golden tests, and a formal calculation audit. The base
infrastructure (ecu/, sensors/, network/) is **identical** — only analysis and
documentation changed. These entries document what to rescue, in what order, and
why each item matters.

---

## Priority legend

| Icon | Meaning |
|------|---------|
| 🔴 HIGH | Bugs or design flaws blocking trust in current output |
| 🟡 MEDIUM | New capability with validated math |
| 🟢 LOW | Documentation, UI polish, or nice-to-have |

---

### BL-FABLE5-C1 — ECO sign inversion in vs_engine.py (CRITICAL BUG)

**Source:** `docs/CALC_AUDIT.md` finding C1 (buell_fable5)
**Applies to:** `web/vs_engine.py:193-197` in original buell — same codebase
**Priority:** 🔴 HIGH

**Finding:** `_build_ci()` sets `eco = 'A' if delta < 0` (vs_engine.py:196).
Since `dpw_eff = pw_eff_B - pw_eff_A`, when **B injects LESS fuel** (delta < 0),
A wins "eco" — meaning the winner is always the session INJECTING MORE fuel.
ECO mode selects the richer map, which is the opposite of what a user selecting
"ECO" expects. Either the sign is inverted or the mode is misnamed.

**Impact:** Any ECO/BALANCE proposal generated today may systematically enrich
where it claims to economize. Affects `proposal.py` via inherited winner.

**Fix:**
```
In _build_ci(), line ~196:
  eco = 'A' if delta < 0   →   eco = 'A' if delta > 0
```
Then add a golden test with synthetic data of known direction (two sessions with
known PW difference, verify ECO picks the leaner one).

**Validation:** Create a golden test: session A has PW higher by X% than B in
matched cells. ECO should pick B (the leaner map). Run before and after fix.

**Dependencies:** None. This is a one-line fix + one test.

**Files touched:** `web/vs_engine.py`, `tests/` (new test file)

---

### BL-FABLE5-VDYNOV2 — Replace vdyno.py physics with measure/physics.py

**Source:** `measure/physics.py` (buell_fable5) + `docs/CALC_AUDIT.md` V1-V5
**Applies to:** `web/vdyno.py` in original buell
**Priority:** 🔴 HIGH

**Problems in current vdyno.py (per CALC_AUDIT):**
- V1: **No road-slope term.** `m·g·sin(θ)` absent. At 100 km/h a 1% grade adds
  ~0.8 kW phantom power. `slope_reference.json` (631 KB) exists but is never used.
- V2: **Inconsistent density handling.** Fixed `rho=1.10` for aero drag while SAE
  J1349 correction rescales total power using measured baro+IAT. Two atmospheres.
- V3: `drivetrain_eff` (0.91) defined but never used.
- V4: Fixed mass 295 kg (fuel varies ~10 kg full-to-reserve → ~3% error in
  inertial term during WOT).
- V5: CdA=0.60 and Crr=0.015 are uncalibrated guesses. Coast-down segments
  (`fl_decel` rows) already exist in session CSVs to calibrate both.

**Solution:** Replace the physics engine in `web/vdyno.py` with `measure/physics.py`:
- `compute_behavior()` returns per-row kinematics with honest metadata
- Air density from baro+IAT when available, config default fallback otherwise
- Slope term as additive `m·g·sin(θ)·v` when slope is known (M2 in MASTER_PLAN)
- Dynamic mass from fuel_tracker when available
- Central differences (np.gradient) — no synthetic zero appended
- `slope_corrected=False` and `cda_crr_calibrated=False` declared in meta

**Integration plan:**
1. Copy `measure/physics.py` → `web/physics.py` (or import from measure/)
2. Refactor `web/vdyno.py` to use `compute_behavior()` instead of inline math
3. Add slope term: lookup from `slope_reference.json` via GPS position
4. Wire dynamic mass from fuel tracker
5. Add coast-down calibration endpoint: extract `fl_decel` segments, fit CdA+Crr
6. Keep backward compat: old vdyno endpoint still works for existing data

**Validation:** Golden test from `tests/test_measure.py`: constant 100 km/h on
flat → analytic power within 5%. Run vdyno before/after on same session data.

**Dependencies:** Requires `measure/` integration (BL-FABLE5-MEASURE) first, or
at minimum copying `physics.py` and `schema.py`.

**Files touched:** `web/vdyno.py`, `web/physics.py` (new), `web/handlers/vdyno.py`

---

### BL-FABLE5-MEASURE — Integrate measure/ package (new analysis pipeline)

**Source:** `measure/` directory (buell_fable5)
**Priority:** 🟡 MEDIUM

**What it is:** A clean-slate rewrite of the behavior measurement pipeline with
7 golden tests, quality-flagged events, and honest-instrument design. Four modules:

| Module | Lines | Purpose |
|--------|-------|---------|
| `measure/schema.py` | ~100 | CSV loading with capability detection (`has_baro`, `has_gear`, etc.) |
| `measure/physics.py` | ~120 | Per-row kinematics, forces, wheel power with metadata |
| `measure/events.py` | ~200 | Steady-state buckets + TPS step-response events with quality flags |
| `measure/compare.py` | ~150 | Cross-session event matching by TPS trace RMSE (not PW) |
| `measure/__main__.py` | ~80 | CLI: `python -m measure events/steady/compare` |

**Why integrate (vs keep F7):**

| Aspect | F7 (current) | measure/ (fable5) |
|--------|-------------|-------------------|
| Tests | None | 7 golden tests with analytic answers |
| Code quality | Tangled in server.py, dead code after return | Clean single-responsibility modules |
| Event matching | DTW on PW curves | RMSE on TPS traces (matches by rider input) |
| Quality flags | Hard TPS threshold (dtps>8) | Per-event plausibility checks (accel, gear) |
| Physics | Inline in vdyno.py | `compute_behavior()` with metadata |
| State | Cached F7 JSONs exist for 4/33 sessions | Fresh compute from CSV, no cache deps |

**Two integration options:**

**Option A — Coexist (recommended):** Add `measure/` alongside F7. The CLI
(`python -m measure events 248AE2`) works immediately without touching server.py.
Users can cross-validate F7 results against measure results. Gradual migration.

**Option B — Replace F7:** Remove `web/f7.py`, `web/launch.py`, `web/vs_engine.py`,
`web/proposal.py` and their handlers/templates. Wire `measure/` into the web layer.
This is what fable5 did. Only do this after Option A has been validated on real data.

**Steps (Option A — recommended):**
- [ ] Copy `measure/` directory to buell root
- [ ] Add import in `__init__.py` (optional)
- [ ] Verify CLI works: `python -m measure events 248AE2`
- [ ] Add CLI documentation to README
- [ ] Cross-validate: run F7 and measure on same 2-3 sessions, compare event counts
- [ ] Optionally wire measure results into a new tab/page, leaving F7 untouched

**Validation:** Run `python -m pytest tests/test_measure.py` after copy.
Run `python -m measure events 248AE2` and verify event count > 0.

**Dependencies:** None — purely additive. Zero risk to existing code.

**Files added:** `measure/` (5 files), `tests/test_measure.py`

---

### BL-FABLE5-PWMODEL — Integrate validated PW reverse-engineering formula

**Source:** `research/pw_model/` (buell_fable5)
**Priority:** 🟡 MEDIUM

**What it is:** A fully validated formula for the DDFI2 injector pulse width,
reverse-engineered from ~100,000+ rows across 19 sessions and 9 ECUs:

```
M5: PW = -2.664 + 0.001278·veCurr + (-0.00336)·veCurr/RPM
          + 0.0318·WUE + (-0.208)·(Batt-14) + 0.0439·(Batt-14)²
          + 1.248·fl_wot + (-0.103)·fl_o2 + 0.016·fl_cl
```

| Metric | Value |
|--------|-------|
| R² | 0.957 |
| MAPE | 2.96% |
| Condition number | 3.7 (healthy) |
| Cross-validation (3/6 ECUs) | R² > 0.95 |

**What exists in research/pw_model/:**
- `validate_model_confidence.py` — standalone validation tool
- `pw_simulator_v5.html` — browser-based PW calculator (audited, bugs fixed)
- `RESULTADO_FINAL.md` — full documentation of all models (M1-M6)
- `REPORTE_DE_HALLAZGOS.md` — 4-round formal audit with 5 charges, all resolved
- Scripts `01_exploracion.py` through `10_audit_response.py`

**Integration options:**

**Option A — Backend endpoint (recommended):** Create a small module
`web/pw_model.py` that loads the formula coefficients and exposes:
- `predict_pw(veCurr, rpm, wue, batt_v, flags)` — returns predicted PW
- `estimate_ve_from_pw(pw, rpm, wue, batt_v, flags)` — inverse: what VE produces
  a given PW (useful for tuning: target PW → needed VE)
- GET `/pw_model/predict?veCurr=...&rpm=...` endpoint for dashboard use

**Option B — Research documentation only:** Keep `research/pw_model/` as-is
in the repo root. Document the formula in ARCHITECTURE.md. No code integration.
Valid but leaves value on the table.

**Why it matters (from MASTER_PLAN.md):**
> "This is the single most valuable unused asset in the project."
The PW model gives **injector observability in open loop without a wideband**.
With it you can infer fuel flow from any ride CSV, compare actual vs expected PW,
and detect data-quality issues (R² drop = alarm).

**Steps (Option A):**
- [ ] Copy `research/pw_model/` to buell root
- [ ] Create `web/pw_model.py` with predict/estimate functions + coefficients
- [ ] Add GET `/pw_model/predict` endpoint
- [ ] Wire into dashboard as a "PW Model" tab or tooltip
- [ ] Add `validate_model_confidence.py` to tools/

**Validation:** `python research/pw_model/validate_model_confidence.py ride_002.csv --model M5`
should print R²=0.957 and CONFIRMED verdict.

**Dependencies:** None — research/ is purely additive. `web/pw_model.py` is a new file.

**Files added:** `research/pw_model/` (20+ files), `web/pw_model.py`, endpoint in server.py

---

### BL-FABLE5-TESTS — Port golden tests from fable5

**Source:** `tests/test_measure.py` (buell_fable5)
**Priority:** 🟡 MEDIUM

**What it is:** 7 golden tests with analytically known answers:

| Test | What it validates |
|------|-------------------|
| `test_air_density_standard_conditions` | Physics constants: ρ(1013.25, 15°C) = 1.225 |
| `test_steady_cruise_power_matches_analytic` | Power = (½ρCdAv² + Crr·m·g)·v within 5% |
| `test_acceleration_power_has_inertial_term` | Inertial power = m·a·v within 10% |
| `test_step_event_detected_with_correct_baseline` | Step event detection works |
| `test_steady_states_found_before_step` | Steady-state detection works |
| `test_compare_direction_b_faster_wins` | Sign convention: B-A deltas |
| `test_identical_sessions_give_zero_delta` | Zero delta when identical |

**Why it matters:** The original buell has **zero unit tests**. Every number in the
pipeline is unverified. These golden tests provide a repeatable baseline: if they
pass, the physics engine is trustworthy. If they fail, something is broken.

**Steps:**
- [ ] Copy `tests/test_measure.py` to buell root
- [ ] Run: `python tests/test_measure.py`
- [ ] If any test fails, fix the physics bug (likely in current vdyno.py math)
- [ ] Add pytest config to `mypy.ini` or `pyproject.toml`

**Validation:** All 7 tests must PASS. If `test_compare_direction_b_faster_wins`
fails, the F7 code has a sign convention bug.

**Dependencies:** Requires `measure/` package or at minimum `measure/schema.py`
and `measure/physics.py` for the imports.

**Files added:** `tests/test_measure.py`

---

### BL-FABLE5-CALCAUDIT — Apply CALC_AUDIT findings to existing code

**Source:** `docs/CALC_AUDIT.md` (buell_fable5)
**Priority:** 🔴 HIGH (C1, V1) / 🟡 MEDIUM (V2-V5)

**What it is:** A formal audit of every calculation in the buell tuning pipeline.
Already done — just needs to be applied. Key findings affecting original buell:

| ID | Finding | Severity | File:Line | Fix |
|----|---------|----------|-----------|-----|
| C1 | ECO picks richer map (sign inverted) | CRITICAL | vs_engine.py:196 | `a if delta < 0` → `a if delta > 0` |
| V1 | No road-slope term in vdyno | HIGH | vdyno.py:124 | Add `m·g·sin(θ)·v` from slope_reference |
| V2 | Inconsistent density handling | MEDIUM | vdyno.py:30,124,136 | Single rho source |
| C2 | SPORT winner no significance gate | HIGH | vs_engine.py:198-202 | Add Welch CI for ddvss |
| P2 | Proposal inherits C1 | CRITICAL | proposal.py | Depends on C1 fix |
| V4 | Fixed mass 295 kg | MEDIUM | vdyno.py:28 | Dynamic mass from fuel_tracker |
| V5 | CdA/Crr uncalibrated | MEDIUM | vdyno.py:29-30 | Coast-down calibration |

**Unused data inventory (from CALC_AUDIT §5):**

| Asset | Size | Would improve | Effort |
|-------|------|---------------|--------|
| `slope_reference.json` | 631 KB | V1: slope term in vdyno | Medium |
| `route_reference.json` | 1.1 MB | Same-road matching for A/B | Medium |
| PW model (research/) | validated | Fuel flow observability in OL | Medium |
| Fuel tracker fuel estimate | live | V4: dynamic mass | Low |
| Coast-down / fl_decel | every CSV | V5: CdA & Crr calibration | Medium |
| AHT20 humidity + temp | sensor logs | True air density (fixes V2) | Low |
| `burn_ledger.py` | ledger | Iteration outcome tracking | Low |

**Priority order to fix (from CALC_AUDIT §6):**
1. **C1** — ECO sign semantics + golden test. Nothing map-related should be burned
   before this.
2. **V1** — Slope term from slope_reference.json + GPS.
3. **C2** — Welch significance gate for SPORT/ddvss winner.
4. **V2/V4/V5** — Measured ρ, dynamic mass, coast-down calibration.
5. PW model integration — per MASTER_PLAN Phase 1.

**Steps:**
- [ ] Fix C1 in vs_engine.py + add golden test
- [ ] Fix V1 in vdyno.py: wire slope from slope_reference.json
- [ ] Fix C2 in vs_engine.py: add Welch CI for ddvss winner
- [ ] Fix V2: single rho source (use measured baro+IAT when available)
- [ ] Fix V4: dynamic mass from fuel_tracker
- [ ] Fix V5: coast-down calibration function
- [ ] Copy `docs/CALC_AUDIT.md` to buell/docs/ for reference

**Dependencies:** C1 has no deps (one-liner). V1 depends on `gps/slope_reference.py`
(already exists in buell). V5 depends on extracting fl_decel segments from CSV.

**Files touched:** `web/vs_engine.py`, `web/vdyno.py`, `web/proposal.py`,
`web/handlers/vdyno.py`, `docs/CALC_AUDIT.md` (new)

---

### BL-FABLE5-MASTERPLAN — Adopt MASTER_PLAN strategic direction

**Source:** `MASTER_PLAN.md` (buell_fable5)
**Priority:** 🟢 LOW (documentation)

**What it is:** A strategic plan document that defines the measurement-first
philosophy. Core principles:
1. Honest instrument: every result declares uncorrected assumptions
2. Rider input vs ECU response vs Outcome: TPS is input, PW is response,
   acceleration is outcome
3. Differential first: absolute power is uncertain; matched-event deltas are
   the trustworthy signal

**Three-phase plan:**
- **M1 — Trust the instrument:** repeatability baseline, coast-down calibration,
  VSS glitch cleaning, air density per ride
- **M2 — Terrain:** slope correction per event from GPS
- **M3 — Relate full ECU state:** PW model per session, steady-state atlas,
  event atlas

**Why it matters:** The original buell lacks any equivalent document. The existing
BACKLOG.md is a task list organized by FASE, not a strategic plan with priorities.
MASTER_PLAN.md provides the missing strategic layer.

**Steps:**
- [ ] Copy `MASTER_PLAN.md` to buell root
- [ ] Link to it from the top of BACKLOG.md as the strategic reference

**Validation:** Just a document copy — no runtime validation needed.

**Dependencies:** None.

**Files added:** `MASTER_PLAN.md` (new, ~100 lines)

---

### BL-FABLE5-CLI — measure CLI for offline analysis

**Source:** `measure/__main__.py` (buell_fable5)
**Priority:** 🟢 LOW

**What it is:** A CLI interface to the measure package:

```bash
python -m measure events 248AE2        # extract events from session
python -m measure steady 248AE2        # extract steady states
python -m measure compare A295AD 248AE2  # cross-session comparison
```

**Why it matters:** Currently all analysis goes through the web server. The CLI
allows:
- Debugging analysis logic without starting the web server
- Batch processing sessions with shell scripts
- Running on the Pi via SSH without opening a browser
- CI/CD: compare two sessions in a script and check if delta exceeds threshold

**Steps:**
- [ ] After integrating `measure/` (BL-FABLE5-MEASURE), the CLI works automatically
      (`python -m measure` via `__main__.py`)

**Dependencies:** BL-FABLE5-MEASURE.

---

### BL-FABLE5-UICARDS — Dashboard big-card label/unit split

**Source:** `web/static/app.js` + `web/templates/index.html` (buell_fable5)
**Priority:** 🟢 LOW (UI polish)

**Changes in fable5:**
- `app.js`: `_combineLabel(label, unit)` removed. Label and unit set separately:
  ```js
  $id('waLabel').textContent=m.label;
  $id('waUnit').textContent=m.unit;
  ```
- `index.html`: Units in separate `<span class="big-unit-inline">` elements.
  Big numbers 80px vs 56px original. `fitLabels()` removed.

**Why integrate:** Cleaner separation of label and unit. Bigger numbers are more
readable on the Pi's small screen when the dashboard is viewed from a phone.
Removing `fitLabels()` simplifies JS.

**Steps:**
- [ ] Update `web/static/app.js`: split label/unit in `_paintA()`
- [ ] Update `web/templates/index.html`: add `<span class="big-unit-inline">` elements
- [ ] Remove `fitLabels()` references (DOMContentLoaded listener)
- [ ] Verify dashboard renders correctly: `python serve_local.py --serve`

**Validation:** Open `http://127.0.0.1:8080` and check big-card display —
units should appear as separate inline text next to values, numbers should be larger.

**Dependencies:** None.

**Files touched:** `web/static/app.js`, `web/templates/index.html`

---

### BL-FABLE5-EEPROMTOMSQ — Move _eeprom_to_msq to utils.py

**Source:** `web/utils.py` (buell_fable5)
**Priority:** 🟢 LOW (code cleanup)

**Change in fable5:** `_eeprom_to_msq()` was moved from `web/vs_engine.py` to
`web/utils.py` when the legacy analysis engine was removed. Comment in fable5
says: "Moved from web/vs_engine.py when the legacy analysis engine was removed —
this is an EEPROM export utility, not analysis."

**Why integrate:** It's in the right place (`utils.py`) — it's a serialization
utility, not analysis. The original buell still has it in `vs_engine.py`.

**Steps:**
- [ ] Move `_eeprom_to_msq()` from `web/vs_engine.py` to `web/utils.py`
- [ ] Update import in `web/handlers/eeprom.py` (already imports from utils)
- [ ] Remove old definition from vs_engine.py (or leave import alias)

**Dependencies:** None.

**Files touched:** `web/utils.py`, `web/vs_engine.py`, `web/handlers/eeprom.py`
(import may already be correct)

---

### BL-FABLE5-FUELFIX — Fuel handler POST body parsing

**Source:** `web/handlers/fuel.py` (buell_fable5)
**Priority:** 🟢 LOW (minor robustness)

**Change in fable5:** `_handle_fuel_reserve` and `_handle_fuel_refuel` now read
the POST body directly from `self.rfile` instead of accepting a `payload` parameter.
Added `try-except` that defaults `active=True` on parse failure.

**Why integrate:** Slightly more robust — if the payload is malformed, the
handler doesn't crash. The `active=True` default means reserve mode activates
by default even if the request body is broken, which is fail-safe.

**Steps:**
- [ ] Update both methods in `web/handlers/fuel.py` to match fable5 version
- [ ] Verify with `curl -X POST http://127.0.0.1:8080/fuel/reserve -d '{}'`

**Dependencies:** None.

**Files touched:** `web/handlers/fuel.py`

---

### BL-FABLE5-FUELTRACKER — Remove stale mtime optimization in _calc_since

**Source:** `web/fuel_tracker.py` (buell_fable5)
**Priority:** 🟢 LOW (bug fix for stale data)

**Change in fable5:** Removed the `os.path.getmtime(csv_path) < from_unix` check
that skipped files modified before a timestamp. The optimization was causing
stale consumption data (fixes `/fuel/status` hang on old rides).

**Why integrate:** This was already fixed in original buell at v2.7.282 (see
CHANGELOG: "fix /fuel/status hang (69s) by skipping old ride CSVs in _calc_since").
Check if the same fix was applied — if not, apply it.

**Steps:**
- [ ] Compare `web/fuel_tracker.py` in both repos — the fable5 version removed
      the mtime filter entirely. Current buell v2.7.282 already has this fix.
      May be no-op.

**Dependencies:** None. Check before applying.

---

## Implementation order (recommended)

### Sprint 1 — Bugs (HIGH priority)
1. **BL-FABLE5-C1** — ECO sign inversion (1 line + 1 test, critical)
2. **BL-FABLE5-TESTS** — Port golden tests (catches physics bugs immediately)
3. **BL-FABLE5-CALCAUDIT** — Fix V1 (slope), C2 (SPORT gate), V2 (density)

### Sprint 2 — New capabilities (MEDIUM priority)
4. **BL-FABLE5-MEASURE** — Integrate measure/ package (coexists with F7)
5. **BL-FABLE5-PWMODEL** — Integrate PW formula (expose as endpoint)
6. **BL-FABLE5-VDYNOV2** — Replace vdyno physics with measure/physics

### Sprint 3 — Polish (LOW priority)
7. **BL-FABLE5-MASTERPLAN** — Copy strategic plan document
8. **BL-FABLE5-UICARDS** — Big-card label/unit split
9. **BL-FABLE5-CLI** — CLI works automatically after measure/ integration
10. **BL-FABLE5-EEPROMTOMSQ** — Code cleanup (move function)
11. **BL-FABLE5-FUELFIX** — Minor robustness fix

---

## Quick reference: files to add vs modify

### New files to add (from fable5)
```
measure/__init__.py        # Package + public API
measure/__main__.py        # CLI entry point
measure/schema.py          # CSV loading with capability detection
measure/physics.py         # Per-row kinematics and wheel power
measure/events.py          # Steady states + step event detection
measure/compare.py         # Cross-session matching by TPS RMSE
tests/test_measure.py      # 7 golden tests
docs/CALC_AUDIT.md         # Calculation audit (reference doc)
docs/BACKLOG_FABLE5_RESCUE.md  # This file
MASTER_PLAN.md             # Strategic plan
research/pw_model/         # PW reverse-engineering (20+ files)
web/pw_model.py            # PW model integration (new)
```

### Existing files to modify
```
web/vs_engine.py           # Fix C1: ECO sign
web/vdyno.py               # Replace physics with measure/physics.py
web/proposal.py            # Inherited C1 fix
web/utils.py               # Move _eeprom_to_msq here
web/handlers/fuel.py       # Body parsing robustness
web/static/app.js          # Label/unit split in big-cards
web/templates/index.html   # Unit spans, bigger numbers
web/server.py              # Add pw_model endpoint
```

---

## Appendix: file manifest comparison

### Only in buell_fable5 (to add to buell)
```
measure/                 → 5 Python files (2.5 KB schema, 3.5 KB physics, 6.5 KB events, 5 KB compare)
tests/test_measure.py    → 1 Python file (~4 KB)
docs/CALC_AUDIT.md       → 1 Markdown file (~12 KB)
MASTER_PLAN.md           → 1 Markdown file (~4 KB)
research/pw_model/       → 20+ files including simulators, reports, scripts
sessions/_cache/         → 3 JSON files (measure results for 248AE2)
```

### Only in buell (NOT in fable5 — do NOT remove)
```
web/f7.py                → FASE 7 event detection (still primary)
web/launch.py            → Launch detection
web/vdyno.py             → Virtual dyno (to be replaced, not removed yet)
web/vs_engine.py         → Session comparison (to be fixed, not removed)
web/proposal.py          → Map proposal (to be fixed, not removed)
web/handlers/sessions.py → Session handler
web/handlers/tuner.py    → Tuner handler
web/handlers/vdyno.py    → Vdyno handler
6 session/tuner templates → HTML files
```
