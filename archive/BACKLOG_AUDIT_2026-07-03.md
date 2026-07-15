<!-- ARCHIVED 2026-07-15: audit executed. Whole-file archivals done
(BACKLOG_PROPOSAL_V2, BACKLOG_ECM_DEFS, BACKLOG_EEPROM_READ_LOGIC moved to
archive/). The two "reopen" items were later FIXED in v2.7.285 (ANL14 disk
watchdog, BL-MAP-03 speed legend). Remaining inline dedup/removals inside
BACKLOG.md are tracked in docs/HARDENING_PLAN.md as a mechanical sweep task.
Kept as developer-diary reference. -->

## 🔍 AUDIT REPORT — 2026-07-03 (stale-DONE + duplicate sweep, verified against code)

**Why this exists:** the backlog had grown to ~137 actionable items across 10 files,
too large to safely prioritize by feel. A two-pass audit was run: (1) an inventory
pass flagged every item marked DONE/✅ that was still physically present in a backlog
file (this project's own rule says completed items must be removed immediately —
any leftover DONE item is itself a bug); (2) a verification pass did NOT trust that
flag — it re-read the actual code for every flagged item (function names, call sites,
CHANGELOG cross-check) before accepting or rejecting the DONE claim, per the same
"verify before trusting an audit" rule this project already applies to freebuff.

**Per-item detail (evidence, file:line, function names) lives in the full agent
transcripts from this session — not reproduced in full here to avoid bloating this
file further. What follows is the actionable summary: verdict + recommended action
per item. Inline `🔍 AUDITED 2026-07-03` markers at each item's original location
point back to this section.**

### ✅ Confirmed DONE — safe to delete once actioned
- **BL-GEAR-01** (line ~285) — gear detection via ECU Gear ground truth. Confirmed:
  `ecu/gear_calibration.py`, `web/gear_detect.py`, `web/gear_learner.py` all exist and
  are wired into `f7.py`/`launch.py`/live `GearFilter`.
- **BL-GPS-03** (line ~334) — GPS fix quality filters. Confirmed: `_gps_quality()` in
  `web/f7.py` (epv≤5.0, mode≥3, sats≥6) plus an independent equivalent gate in
  `gps/route_reference.py`. Two separate implementations, not a bug — worth
  consolidating someday, not urgent.
- **BL-ECM-01** (line ~398) — multi-ECU XML-driven EEPROM decode/encode. Confirmed:
  `ecu/ecm_defs.py`, `ecu/version_resolver.py`, `ecu/rt_defs.py` all wired into
  `ecu/eeprom.py`/`ecu/connection.py`. Its own "BL-ECM-01-RESIDUAL" callout
  (hardcoded RPM_BINS/LOAD_BINS in protocol.py) is still accurate — keep that one open.
- **BL-GRAF-03** (line ~493, BACKLOG.md's copy) — floating GRAF2 cursor readout
  removed. Confirmed: no `#cur-readout` anywhere, replaced by inline `.chip .cval`
  spans. **Naming collision warning:** `BACKLOG_3D_VIZ.md` has an UNRELATED, still-open
  item also called BL-GRAF-03 (per-preset signal persistence) — do not confuse the two,
  see that file's note.
- **FASE6 baro-norm removal / task006** (lines ~617-631) — confirmed: no baro
  multiplication of PW anywhere in `f7.py`/`launch.py`, matches CHANGELOG v2.7.276.
- **FASE6 PROP_* output / task015** (line ~722) — confirmed: `web/proposal.py`
  (`generate_proposal()`, `save_proposal()`) wired to `POST /eeprom/propose`.
- **FASE6.1 zone fusion design / task037** (line ~1826) — confirmed done, but it's a
  **duplicate of the F7+VS combo item below**, not independently useful — delete as
  redundant once that one is resolved.
- **BL-ECM-03** (line ~1984) — revert EEPROM version guard. Confirmed:
  `_handle_eeprom_revert()` in `web/handlers/eeprom.py` does the donor/live DDFI-tier
  check. Note: CHANGELOG v2.7.251 claims a duplicate entry was removed, but the
  *remaining single entry* was never actually deleted — exactly the bug this audit
  is checking for.
- **`BACKLOG_PROPOSAL_V2.md`** (whole file, 402 lines) — all 4 phases (DDTW, F7+VS
  zone fusion, GP Regression, proposal.py) independently confirmed shipped and wired
  (v2.7.271/272/274/275). Candidate for archival once actioned.

### ⚠️ Confirmed shipped, but backlog TEXT is stale/wrong — needs rewrite, not deletion
- **FASE6 F7+VS zone fusion / task001+005** (lines ~569-583) — the functionality
  shipped in `web/vs_engine.py` (`_zone_by_tps_peak`, `_f7_delta_to_cells`,
  `_build_ci`), but with different thresholds than the original spec (85/40 not
  60/20) and the spec'd `w_cross_match` (orphan vs matched bonus) component was
  never built — confirmed absent from `vs_engine.py`. This is a documented,
  deliberate deviation (see `BACKLOG_PROPOSAL_V2.md` Phase 2) — the old spec text
  should be replaced with a pointer to what actually shipped, not just deleted.
- **FASE5.1 map click-edit+burn** (line ~1011) — **real contradiction found**:
  `tuner.html` implementation works end-to-end (`/eeprom/burn`, ±15% gate, auto-backup,
  all confirmed live). BUT `map-editor.html` is a **separate, still-broken** duplicate
  page — its burn button POSTs to `/tuner/burn`, which has no route (404), confirmed
  in `web/server.py`'s routing table. This is the SAME bug as **BL-BUG-04** (line
  ~476), which stays open — correctly. Action: delete the stale line-1011 spec (its
  intent is satisfied by tuner.html), keep BL-BUG-04 open, and separately decide
  whether to fix or remove `map-editor.html`'s dead burn button.
- **`BACKLOG_ECM_DEFS.md`** (whole file, 229 lines) — mostly superseded by BL-ECM-01,
  but NOT fully: 2 sub-items are still genuinely open (2nd fuel map not in
  `MAP_KEYS`, dynamic RPM/LOAD bins in protocol.py). Good news: both are already
  independently tracked elsewhere (BL-ECM-02's "2nd Fuel Map" note, and
  BL-ECM-01-RESIDUAL) — nothing is lost if this file is archived, but confirm those
  two items are properly captured before deleting this file.
- **`BACKLOG_EEPROM_READ_LOGIC.md`** (whole file, 195 lines) — same situation: Fases
  A and C fully confirmed shipped; Fase B (read path) is "mostly done" but its own
  flagged gap ("app.js grid dinámico") is confirmed STILL broken —
  `web/static/app.js` still hardcodes 13×12 BUEIB-only RPM_BINS/LOAD_BINS. This is
  the exact same residual as BL-ECM-01-RESIDUAL — already tracked, safe to archive
  this file once confirmed.

### 🔴 NOT actually done — false DONE claims, reopen with corrected scope
- **BACKLOG_ANL.md → BACKLOG-ANL14** "disk-space watchdog" — **false claim**. Only a
  `/health` endpoint exposing `disk_free_gb` via `shutil.disk_usage` exists
  (`web/server.py:_handle_health`). Zero polling, zero threshold, zero dashboard
  badge, zero auto-stop-recording logic — a watchdog was never built, only a metric.
  The cited version (v2.7.186) is also wrong (that version is about ecm_defs.py size
  guards, unrelated). The real metric-only work shipped at v2.7.192. **Action: reopen
  as a real, still-small task** (periodic check + threshold + dashboard badge +
  optional auto-stop) — this is a good XS/S candidate for the "smallest first" queue.
- **BACKLOG_MAPA_3D.md → BL-MAP-03** "speed-color legend bar" — **genuine regression**,
  not a false original claim. The 5-swatch legend (`spd2color()` buckets: 0-20/
  20-60/60-120/120-160/160+ km/h) really did ship in the old "Mapa" tab of
  `index.html` at the cited version, but was silently deleted 41 commits later in
  commit `89fefe0` (v2.7.233) when that tab was replaced by `gps_analysis.html` — the
  new page never got the legend ported over, and dead `.map-legend-bar` CSS was left
  behind in `index.html`. **Action: reopen as a small task** — port the legend markup
  into `gps_analysis.html`, delete the dead CSS from `index.html`. Also a good
  "smallest first" candidate.

### Duplicates confirmed (safe to merge) — 7 of 9 checked
- **"PROPOSAL tab in Tuner UI"**: BACKLOG.md lines ~828 (task020), ~1602 (task025),
  ~1705 (FASE5.2) — same task 3x. Backend ready (`/eeprom/propose`), zero UI consumes
  it. Merge into one entry.
- **"Batch compare / rank maps by win-rate"**: lines ~1122 (FASE7 7.7), ~1753
  (task031) — same task 2x, neither built (`web/batch_compare.py` doesn't exist).
  Merge.
- **"Migrate Launch to F7"**: lines ~1131 (FASE7 7.8), ~1801 (task032) — same task
  2x. Keep the ~1801 version (more implementation detail), delete the other.
- **"AI context export"**: lines ~1041, ~1779 (task035) — same task 2x
  (`GET /eeprom/ai_context`), neither built. Merge.
- **"Daemon watchdog heartbeat"**: lines ~919 (#13), ~1645 (task033) — likely
  duplicate (task033 already has a worked-out concrete plan) — not independently
  re-verified in this pass, do a quick manual check before merging.
- **"GPS/VSS tire-wear ratio"**: `BACKLOG_DATASET_INSIGHTS.md` BL-DI-07 and BL-DI-11
  — same idea 2x, neither built. Keep BL-DI-11 (more method detail: heading-stable,
  CLT>70 filter), delete BL-DI-07.
- **"UPS-Lite MOSFET features"** (power-cut, charge-limiter, INA219): described twice
  in BACKLOG.md — once in the numbered "Power Management Features" section
  (~1419-1500), once in "HW Modifications" (~1528-1577). The HW Modifications version
  has more detail (IRLML6402 part number, wake-on-ignition circuit, tiered shutdown)
  — merge into that one, delete the earlier duplicate content.

### NOT a duplicate — do not merge
- **BL-FUEL-13 vs BL-FUEL-17** (odometer from EEPROM): sequential, not parallel.
  BL-FUEL-17 is the research task ("does the odometer exist in EEPROM"), BL-FUEL-13
  is the downstream integration that depends on it. Neither is built
  (`grep -rn odometer ecu/ web/` is empty). The "found at BUEYD/BUEWD/BUEZD offset
  -36" research note is currently misfiled under BL-FUEL-13 — move it to BL-FUEL-17,
  it's that item's actual output.

### Rename, don't merge
- **BL-GRAF-03 collision**: BACKLOG.md's BL-GRAF-03 (done, cursor-readout removal)
  and `BACKLOG_3D_VIZ.md`'s BL-GRAF-03 (open, per-preset signal persistence in
  localStorage) are unrelated features that share an ID by accident. Renumber the
  `BACKLOG_3D_VIZ.md` one before it causes confusion — see that file's note.

---
