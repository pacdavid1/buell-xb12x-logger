# BACKLOG PROPOSAL V2 — Implementation Plan

**Date:** 2026-07-03
**Source:** freebuff research tasks 006-013 (global prior art sweep, 48 searches)
**Validated:** Against actual code in `web/vs_engine.py`, `web/f7.py`, `web/launch.py`, `web/handlers/eeprom.py`, `web/burn_ledger.py`

**Correction (2026-07-03):** freebuff's codebase validation pass treated `web/burn_ledger.py:convergence_report()` as a working GAP5 implementation. It is dead code — grep confirms it is never called anywhere outside its own file. The real, wired GAP5 implementation is `web/vs_engine.py:compute_convergence()`, called from the `/convergence` endpoint (`web/handlers/eeprom.py:346-354`). Not relevant to this plan's phases, but don't cite `burn_ledger.py:convergence_report()` as evidence GAP5 works — cite `vs_engine.compute_convergence()` instead.

---

## Overview

Four initiatives ordered by dependency + impact. Each builds on the previous:

```
Phase 1: DDTW in F7          (swap, no deps)       ← impact: HIGH, effort: LOW
Phase 2: F7 + VS zone fusion (depends on F7)        ← impact: HIGH, effort: MEDIUM
Phase 3: GP Regression        (replaces _merge_maps)← impact: HIGH, effort: MEDIUM
Phase 4: New proposal.py      (consumes all above)  ← impact: HIGH, effort: MEDIUM
```

---

## Phase 1 — DDTW in F7 — ✅ DONE (v2.7.271, 2026-07-03)

**Why:** Research (task_010, global academic) confirmed Derivative DTW is the standard for vehicle-telemetry cross-session alignment because it's robust to sensor drift/offset. F7's `_f7_dtw()` currently uses plain amplitude DTW (`abs(a[i-1] - b[j-1])`). Since cross-session F7 matching is the explicit use case (different maps → different absolute PW levels), DDTW directly improves match quality.

**File:** `web/f7.py` → function `_f7_dtw()` (lines 65-79)

**Verified 2026-07-03 against actual code:** cost function is `abs(a[i - 1] - b[j - 1])`,
plain amplitude DTW — confirmed, not speculative.

### What exists now

```python
def _f7_dtw(a, b, window=_F7_WINDOW):
    cost = abs(a[i - 1] - b[j - 1])   # plain amplitude cost
```

DDTW replaces the cost with the absolute difference of the *derivatives*:

```python
def _derivative(x):
    return [(x[i] - x[i-1]) / 2 + (x[i+1] - x[i-1]) / 2  # central diff
            for i in range(1, len(x) - 1)]
```

### Tasks

| # | Task | File | Lines | Est. |
|---|------|------|-------|------|
| 1.1 | Add `_f7_ddtw()` — derivative-based DTW | `web/f7.py` | +15 | 15min |
| 1.2 | Add `derivative=True` param to existing `_f7_dtw()` or add separate `_f7_ddtw()` wrapper that computes derivative then calls `_f7_dtw` | `web/f7.py` | +5 | 5min |
| 1.3 | Wire DDTW into `_f7_match_cross_session()` (line ~532: `tps_sim = _f7_dtw(...)` → `tps_sim = _f7_dtw_derivative(...)`) | `web/f7.py` | +1 | 5min |
| 1.4 | Bump `_F7_EVENTS_V` from 7 to 8 (invalidates all cached clusters) | `web/f7.py` | +1 | 1min |
| 1.5 | Validate against existing test pair (91B225 vs 248AE2): compare DDTW matches vs plain DTW matches | Manual | — | 30min |

### Validation

```bash
# After implementation, compare match quality on known pair
python -c "
from web.f7 import _f7_load_session_clusters, _f7_match_cross_session
from pathlib import Path
buell = Path('/home/pi/buell')
a = _f7_load_session_clusters(buell, '91B225')
b = _f7_load_session_clusters(buell, '248AE2')
m = _f7_match_cross_session(a['clusters'], b['clusters'])
print(f'DDTW matches: {len(m)} vs former {N} (check before/after)')
"
```

### Rollback
- Revert `_F7_EVENTS_V` to 7 and DDTW change in `_f7_dtw`
- Old cached clusters remain valid

---

## Phase 2 — F7 + VS Zone Fusion — ✅ DONE (v2.7.272, 2026-07-03)

**Deviations from the original task list, with rationale:**
- Binning key uses `bucket_a.rpm_center` + `max(tps_peak)` (not bucket_a's tps_center) so the
  zone classification and the cell key are driven by the same throttle value — binning by the
  pre-event stable TPS while classifying zone by peak TPS would file a WOT pull under a cruise
  cell while treating it with WOT zone rules, which is incoherent.
- `w_vs` is fixed at 1.0 (not a separate confidence formula) since vs_delta already passed the
  GAP1 significance gate before fusion is considered — that gate IS its confidence signal.
- CACHE_VERSION was NOT bumped — the raw cached data shape (`delta`, `f7_matches`) didn't
  change, only how `_merge_maps` (uncached) interprets it. `_F7_EVENTS_V` was bumped instead
  (8→9) because `f7.py`'s cluster `bucket_a` summary gained a new `tps_peak` field.
- Validated with synthetic injected F7 matches (monkeypatched `_compare_sessions_cached`)
  rather than only real data — locally available sessions have exactly one real F7
  cross-session match total, and it lands in the WOT zone (correctly excluded by design), so
  it couldn't exercise the MID-zone fusion path. Confirmed both branches (agreeing signs →
  weighted average; conflicting signs → rich-bias max) fire correctly against a real target
  cell from 47BF04 vs 248AE2. Also confirmed zero regression on 91B225 vs 248AE2 (still
  25 cells / 3 skipped, `fused_with_f7=0` since 91B225 has no F7 clusters at all).



**Why:** `_merge_maps()` currently uses only `vs_delta` from Sessions VS. But F7 already produces cross-session event matches (`delta_pw`, `delta_vss`) that measure acceleration performance per cluster. The research (FASE 6.1 in BACKLOG.md) says to fuse F7 and VS by zone: WOT (tps_peak >= 85%) → VS only, Mid (40-85%) → weighted fusion, Light (< 40%) → F7 only. This is the single biggest missed opportunity in the current pipeline.

### What exists now

- `_f7_match_cross_session()` returns matches with `delta_pw`, `delta_vss`, `efficiency_delta`, `sort_score` — but these are **never consumed** by `_merge_maps()`
- `_compare_sessions()` in `launch.py` stores results in `result['f7_matches']` — available but unused
- `tps_peak` is CONFIRMED as a field in F7 events (value: 98.9)

### Tasks

| # | Task | File | Lines | Est. |
|---|------|------|-------|------|
| 2.1 | Add `_f7_delta_to_cells()` — maps F7 cross-session matches to EEPROM cells (same RPM/TPS binning as vs_delta) | `web/vs_engine.py` | +40 | 1h |
| 2.2 | Add zone classification helper: `_zone_by_tps_peak(tps_peak)` → `'WOT'` / `'MID'` / `'LIGHT'` | `web/vs_engine.py` | +10 | 15min |
| 2.3 | Add fusion formula in `_merge_maps()`: `delta = (f7_delta * w_f7 + vs_delta * w_vs) / (w_f7 + w_vs)` with rich bias on conflict | `web/vs_engine.py` | +15 | 30min |
| 2.4 | Add F7 confidence formula: `w_f7 = min(1, n_sessions/2) * avg_dtw_sim * (1.0 if cross-session else 0.7)` | `web/vs_engine.py` | +10 | 15min |
| 2.5 | Add dual delta output: track `f7_delta` and `vs_delta` separately in `ci` dict, fuse at merge time | `web/vs_engine.py` | +10 | 15min |
| 2.6 | Bump `CACHE_VERSION` from 9 to 10 (delta schema changed) | `web/vs_engine.py` | +1 | 1min |
| 2.7 | Validate: compare merged outputs with and without F7 fusion on 91B225 vs 248AE2 | Manual | — | 30min |

### Zone thresholds (from BACKLOG.md FASE 6.1)

```
WOT:    tps_peak >= 85%  → trust VS only (few F7 WOT events)
Mid:    40% <= tps_peak < 85% → F7 + VS weighted fusion
Light:  tps_peak < 40%   → F7 only (VS poor at low TPS)
```

### Rich bias on conflict (signals disagree)

```python
if f7_sign != vs_sign:
    # Bias toward richer (safety in open-loop without WB)
    delta = max(f7_delta, vs_delta)  # richer = more fuel = safer
```

### Rollback
- Revert `CACHE_VERSION` to 9 and zone fusion changes

---

## Phase 3 — GP Regression in `_merge_maps` — ✅ DONE (v2.7.274, 2026-07-03)

**Scope deviation from the original task list, with rationale:** the plan described GP
Regression as replacing `_merge_maps()`'s discrete winner-take-all entirely. Implemented
scope is narrower and safer: GP is used ONLY to fill cells that have NO real vs_delta vote
at all (never visited in either session) -- it never overrides a cell that already has a
discrete/fused verdict from Phases 1-2. This directly targets the "no interpolation into
empty cells" gap from the research without touching or re-validating the already-tested
significant-cell logic. Training data intentionally includes ALL valid SWEET cells
(significant or not) with `dpw_eff_se^2` as heteroscedastic noise -- GAP1's hard
significance gate is bypassed for GP training on purpose, since noise-weighting is the
GP's whole advantage over a binary gate. A GP-filled cell must itself pass a 95%-CI test
on the POSTERIOR (mean +/- 1.96*std doesn't cross zero) before being used, so it's not
introducing an unvetted proposal path -- same statistical bar as GAP1, applied to the
smoothed surface instead of the raw two-sample data.

**Bug found and fixed during validation:** this sklearn version (1.9.0) requires `alpha`
(and the fit/predict arrays) to be `numpy.ndarray`, not plain Python lists --
`GaussianProcessRegressor(alpha=[...])` raises `InvalidParameterError`. Wrapped all
GP inputs in `np.array()`.

**Validated:** real local data (91B225/248AE2, 21 SWEET training points) produced 204
candidate empty cells, all correctly REJECTED (GP posterior std ~1.1-1.4, essentially the
prior -- not enough spatial coverage to extrapolate confidently) -- `filled_by_gp=0`, exactly
the safe outcome wanted on sparse data. Confirmed the fill path itself works with a
synthetic tight cluster of consistent points around a real gap (monkeypatched
`_compare_sessions_cached`): `filled_by_gp=4`. No regression on either real pair (same
`cells_with_data`/`skipped_insignificant` as Phases 1-2).



**Why:** The current `_merge_maps()` does discrete winner-take-all per cell (pick A or B). No interpolation, no uncertainty, no spatial coherence. Research (Tietze 2015, TU Darmstadt) confirms GP Regression is the state of the art for engine map modeling — it gives a principled continuous surface with per-cell posterior variance. It directly replaces the separate interpolation + smoothing steps that don't exist yet as standalone modules.

**Documentation:** `freebuff/responses/gp_regression_proposal_generator.md` (full design)

### What exists now

```python
# vs_engine.py:_merge_maps() — discrete winner per cell
ci[key] = {'eco': 'A' if dpw_eff < 0 else 'B', 
           'sport': 'A' if ddvss < 0 else 'B'}
winner() → picks A/B/AVG per cell independently
```

### Tasks

| # | Task | File | Lines | Est. |
|---|------|------|-------|------|
| 3.1 | Add `_gpr_smooth_delta(delta_rows, fuel_rpm, fuel_load)` — builds GP from Sessions VS delta rows with heteroscedastic noise (dpw_eff_se² as alpha), predicts on full 12x13 grid | `web/vs_engine.py` or new `web/smoothing.py` | +60 | 2h |
| 3.2 | Add `_gpr_make_training_data(delta_rows, flavor)` — extracts (rpm_center, tps_center, dpw_eff, dpw_eff_se²) as training set | `web/vs_engine.py` | +20 | 30min |
| 3.3 | Wire GPR into `_merge_maps()` — after building `ci` dict, optionally run GPR to produce smoothed proposal instead of discrete winner | `web/vs_engine.py` | +10 | 15min |
| 3.4 | Add `confidence` field from `mean_std` → `'HIGH'` (std < 0.005), `'MEDIUM'` (0.005-0.02), `'LOW'` (> 0.02) | `web/vs_engine.py` | +5 | 10min |
| 3.5 | Fallback: if scikit-learn not available or < 5 training points, use current discrete logic | `web/vs_engine.py` | +5 | 5min |
| 3.6 | Validate: compare GP output vs discrete output on 91B225 vs 248AE2 | Manual | — | 30min |
| 3.0 | **CORRECTION (verified 2026-07-03): scikit-learn is NOT installed.** `requirements.txt` lists only pyserial, smbus2, numpy, bmp280 — no sklearn anywhere in the codebase or requirements file. freebuff's claim of "confirmed available on Pi (v1.15.3)" was not actually verified. Add `scikit-learn` to `requirements.txt`, pin a version, and `pip install` it on the Pi BEFORE 3.1-3.6. Pi is resource-constrained — check install size/RAM footprint first. | `requirements.txt` | +1 | 30min (install + verify) |

### Kernel configuration

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel

kernel = ConstantKernel(1.0) * Matern(
    length_scale=[2000, 20],  # RPM, TPS
    length_scale_bounds=[(500, 5000), (5, 50)],
    nu=2.5  # Matern 5/2
) + WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-5, 1.0))

gpr = GaussianProcessRegressor(
    kernel=kernel,
    alpha=cell_noise_variances,  # heteroscedastic from GAP1
    n_restarts_optimizer=10,
    random_state=42
)
```

### Where to put it

Option A (recommended): New `web/smoothing.py` module with `_gpr_smooth_cells()` — this is where smoothing/interpolation logic belongs, cleanly separated from `vs_engine.py`'s comparison logic.

Option B: Inline in `vs_engine.py` — less refactoring but the file is already 250+ lines.

### Rollback
- Revert to discrete winner logic (set flag `use_gpr=False`)
- GP smoothing is additive, not destructive — old caches remain valid

---

## Phase 4 — New `proposal.py` — ✅ DONE (v2.7.275, 2026-07-04)

**Scope deviations, with rationale (see full reasoning in `web/proposal.py`'s module
docstring):**
- Dropped the percentage-delta synthesis (`proposed = current * (1 + delta)`) from
  task 4.2/4.3. Applying `eco_delta` as a signed percentage requires certainty about
  which direction (more/less PW) is the "winning" one for a given flavor/zone --
  guessing that sign convention wrong would silently propose a WRONG-directioned change
  into something that can eventually be burned. Instead, every proposed cell value is
  either session A's or session B's OWN already-driven map value -- never a synthesized
  number. The percentage-delta path remains a legitimate future upgrade, gated on a human
  confirming the winner-direction semantics first.
- Cells with no real decision (no vs_delta vote, no F7 fusion, no GP fill) stay at the
  REFERENCE session's own value, unchanged -- NOT averaged with the other session, unlike
  `_merge_maps()`'s own AVG-for-untested-cells behavior (reasonable for its interactive
  comparison UI, wrong for an automated/unsupervised proposal per BACKLOG_VDYNO.md rule 1).
  Same for BALANCE-mode eco/sport conflicts: stay at reference rather than blend.
- Spark maps are never touched -- this whole pipeline (dpw_eff, F7 delta_pw) is a fuel/PW
  signal only; there is no spark-timing correction computed anywhere upstream.

**Bug found during first validation pass (before the above scope correction):** naively
reusing `_merge_maps()`'s `merged` grid produced `cells_changed=304` (~97% of all fuel
cells) with `max_delta_pct` pinned at the 15% clamp ceiling almost everywhere -- because
untested cells were defaulting to `AVG(A,B)`, which differs substantially from the
reference whenever the two maps are broadly different (the normal case for two different
tunes). After the fix (untested cells stay at reference), the same real pair produces
`cells_changed=10`, `max_delta_pct=5.88%` -- a plausible, targeted result.

**Validated end-to-end against a live local server** (`serve_local.py`, not just direct
function calls): started the server, POSTed to `/eeprom/propose` with `save=false` (dry
run, correct proposed values returned) and `save=true` (PROP_20260704_081441 written to
disk, confirmed discoverable via the existing `/eeprom/sessions-list` endpoint --
i.e. the Tuner will list it). Verified the encoded `eeprom.bin` round-trips through
`decode_eeprom_maps` cleanly and that exactly the expected 10 fuel cells differ from the
reference, with spark maps byte-identical. Test session deleted after validation, server
process killed (found and cleaned up two stale server processes left over from earlier in
this session, both squatting on port 8080).



**Why:** The current proposal path (`vs_engine.py:_merge_maps()`) combines merge logic, comparison, and proposal into one function. The `/eeprom/propose` endpoint is **deprecated** (returns 410). There's no clean way to generate a burnable proposal from the pipeline. A dedicated `proposal.py` module would:

1. Consume vs_delta + f7_delta + GP surface
2. Convert smoothed dpw_eff → EEPROM cell deltas
3. Generate a PROP_* session on disk
4. Reactivate the proposal endpoint

### What exists now

- `vs_engine.py:_merge_maps()` — returns merged maps with cell provenance (A/B/AVG/ORIG)
- `eeprom.py:_handle_eeprom_burn()` — can burn any full map
- No dedicated proposal generation flow → user must manually pick cells

### Tasks

| # | Task | File | Lines | Est. |
|---|------|------|-------|------|
| 4.1 | Create `web/proposal.py` — `generate_proposal(buell_dir, sa, sb, params)` | `web/proposal.py` | +80 | 2h |
| 4.2 | `proposal.py:generate_proposal()` — 1) Get vs_delta from Sessions VS  2) Get f7_delta from F7 cross-session  3) Zone fusion  4) GP smoothing 5) Convert to EEPROM deltas 6) Clamp ±15%  7) Return proposed maps | `web/proposal.py` | — | — |
| 4.3 | Add `_delta_to_eeprom(delta, current_maps, rpm_bins, load_bins)` — converts bin-level dpw_eff to per-cell EEPROM values with ±15% clamp | `web/proposal.py` | +30 | 30min |
| 4.4 | Add `_save_proposal(buell_dir, proposed_maps, current_maps, sa, sb, params)` — saves as PROP_* session (session_metadata.json, eeprom_decoded.json, eeprom.bin, proposal_metadata.json) | `web/proposal.py` | +40 | 1h |
| 4.5 | Reactivate `/eeprom/propose` as POST with `save=True/False` → calls `generate_proposal()` + optionally `_save_proposal()` | `web/handlers/eeprom.py` | +15 | 15min |
| 4.6 | Register new route in `server.py` if needed | `web/server.py` | +1 | 1min |
| 4.7 | Validate: generate proposal for 91B225 vs 248AE2, verify PROP_* session appears in Tuner | Manual | — | 15min |

### Proposal metadata JSON

```json
{
  "source_sessions": ["91B225", "248AE2"],
  "generated_utc": "2026-07-03T12:00:00Z",
  "params": {
    "mode": "BALANCE",
    "use_gpr": true,
    "alpha": 1.0,
    "max_change_pct": 15
  },
  "stats": {
    "cells_with_data": 47,
    "cells_skipped_insig": 3,
    "cells_changed_f7": 12,
    "cells_changed_vs": 25,
    "max_delta_pct": 11.2,
    "convergence_status": "converging"
  }
}
```

### Endpoint design

```
POST /eeprom/propose
Body: {
  "session_a": "91B225",
  "session_b": "248AE2",
  "mode": "BALANCE",        # ECO / SPORT / BALANCE
  "use_gpr": true,
  "alpha": 1.0,
  "save": true              # false = dry run (return JSON only)
}
Returns: {
  "proposed": { fuel_front: [[...]], fuel_rear: [[...]] },
  "delta_pct": { fuel_front: [[...]], fuel_rear: [[...]] },
  "uncertainty": { fuel_front: [[...]], fuel_rear: [[...]] },
  "stats": { cells_changed, max_delta_pct, ... },
  "prop_session": "PROP_20260703_120000"  // only if save=True
}
```

---

## Dependency Graph

```
DDTW in F7 ──────────────────────────┐
                                     ├──> F7+VS fusion ──> GP Regression ──> proposal.py
F7 events + cross-session matches ───┘         │                  │
                                               │                  │
                                     vs_delta from Sessions VS ──┘
                                                       │
                                               GAP1 Welch CI (already exists)
```

- **Phase 1** (DDTW) has no dependencies — can be done first
- **Phase 2** (zone fusion) depends on Phase 1 (DDTW improves F7 match quality before fusion)
- **Phase 3** (GP Regression) depends on having both vs_delta (already exists) and optionally f7_delta (Phase 2 builds it)
- **Phase 4** (proposal.py) consumes all previous phases — must be last

---

## Effort Summary

| Phase | Description | Files Touched | Lines | Est. Time |
|-------|-------------|---------------|-------|-----------|
| **1** | DDTW in F7 | 1 (f7.py) | ~25 | 1h |
| **2** | F7 + VS zone fusion | 1 (vs_engine.py) | ~85 | 3h |
| **3** | GP Regression | 1-2 (vs_engine.py, smoothing.py) | ~100 | 3.5h |
| **4** | New proposal.py | 3-4 (proposal.py, eeprom.py, server.py) | ~165 | 4h |
| **Total** | | | ~375 | ~11.5h |

---

## Risk Register

| Risk | Phase | Mitigation |
|------|-------|------------|
| DDTW reduces match count vs plain DTW | 1 | Keep plain DTW as fallback configurable via `_ddtw=False` |
| GP overfits with < 10 data points | 3 | Require minimum N samples; fallback to discrete logic |
| scikit-learn not available on Pi | 3 | `try: import sklearn` guard with discrete fallback |
| F7 matches have no GAP1-equivalent CI | 2 | F7 confidence uses `avg_conf * tps_sim * min(n_a, n_b)` — heuristic, not statistical |
| proposal.py corrupts EEPROM | 4 | Follow existing burn guard: `encode_eeprom_maps()` validates, ±15% clamp, backup before burn |
| Old session caches invalidated by CACHE_VERSION bump | 1-4 | Cache invalidation is by design — stale caches are deleted on access |

---

## How to Start

For each phase in order:

1. Read the relevant section of this backlog
2. Read the source files listed
3. Read the research docs in `freebuff/responses/`:
   - `gp_regression_proposal_generator.md`
   - `consolidated_summary_006-013.md`
   - `validation_vs_codebase.md`
4. Implement changes
5. Validate against known session pair (91B225 vs 248AE2)
6. Bump version in CHANGELOG.md
7. Commit with message format: `v2.7.XXX: Phase N — description`

> **Note:** After each phase, burn a test ride to validate the proposal doesn't make things worse before proceeding to the next phase.
>
> **Per CLAUDE.md:** Any change touching `/eeprom/burn` or `/eeprom/revert` paths requires a git branch, not a direct commit to main, and explicit user approval.
