# Changelog

<!-- PROMPT_START — read ALL instructions until PROMPT_END before doing anything.
  If you only see part of this block (e.g. via head -5), scroll or read further —
  there are more instructions below.

  INSTRUCTIONS FOR AI ASSISTANTS:
  1. All changelog entries MUST be written in English.
  2. Each new entry follows this format:
       
## [vX.Y.Z] — YYYY-MM-DD
  3. The ### AI section is MANDATORY for every new entry.
     If multiple AIs contributed, list each one.
     If no AI was involved, write: "- No AI assistance"
  4. Do not modify existing entries.
  5. Add new entries at the top, below this header block.
  6. After every change to this repo, run:
       git add <changed files> && git commit -m "vX.Y.Z: description" && git push
     This keeps history clean and allows rollback to any previous state.
  7. Before every commit, check for leftover fix_*.py scripts and delete them:
       ls /home/pi/buell/fix_*.py && rm /home/pi/buell/fix_*.py
     Never commit fix_*.py files to the repo — they are temporary patch scripts.
PROMPT_END -->






## [v2.7.298] — 2026-07-19
### Added
- **Import XPR as session**: `ecu/xpr_import.py` (shared by CLI and web) trims
  an ECMSpy `.xpr` export to the expected EEPROM size and saves it as a
  normal session via `SessionManager` — no ECU connection needed. Reused by
  `tools/import_xpr.py` (CLI) and the new `POST /eeprom/import_xpr` endpoint.
  Map Editor gets an "Import XPR" button (native file picker, reads the file
  client-side, posts base64 — same pattern `/eeprom/burn` already uses).
  Format note: an `.xpr` is a raw EEPROM image plus a few ECMSpy trailer
  bytes; `decode_eeprom_maps` already reads it once trimmed, no XPR-specific
  parsing needed.
- **Save staged edits as a new session, without burning** (`POST
  /eeprom/save_session`): applies staged cell changes through the same
  `apply_map_changes()` path as burn (same ±15% guard), but only writes to
  `sessions/<new_checksum>/` — never touches the ECU. Map Editor's new SAVE
  button opens a modal listing the base session, a read-only table of every
  staged change (map, RPM, Load, before → after), and a free-text note field
  before confirming.
### Fixed
- **BL-BUG-04 — Map Editor BURN button (404)**: `map-editor.html` posted to
  `/tuner/burn`, which was never registered in `web/server.py` (only
  `/eeprom/burn` exists) — the button silently 404'd. Also fixed a second,
  previously-masked bug in the same function: the success check was
  `if (d.ok)`, but `/eeprom/burn`'s response never sets an `ok` field, so
  even a fixed URL would have kept reporting "Burn failed: ?" on success.
  Pointed the fetch at `/eeprom/burn` and fixed the check to `if (!d.error)`,
  matching the working pattern already used by `tuner.html`.
### Changed
- Extracted `apply_map_changes()` into `ecu/eeprom.py` (validate + apply a
  `changes` list with the ±15% guard, then encode) so `/eeprom/burn` and the
  new `/eeprom/save_session` share one implementation instead of two copies.
### AI
- Claude Sonnet 5

## [v2.7.297] — 2026-07-19
### Fixed
- **Windows IPC write bug — live dashboard data froze after first frame**:
  `main.py:_ipc_write` and `ecu/logger_process.py:_write` used
  `tmp.rename(path)` for the atomic write-then-swap. On POSIX this replaces
  the destination silently (why it always worked on the Pi); on Windows
  `Path.rename()` raises `FileExistsError` once the destination already
  exists, and the bare `except Exception: pass` swallowed it — so `live.json`,
  `cells.json`, `ecu_init.json`, `gps.json`, `sysmon.json` all froze at their
  first frame while their `.tmp` siblings kept updating underneath. Found
  running the logger locally on Windows against the real ECU over CH343/COM4:
  dashboard connected (`ecu_connected: true`) but TPS/RPM/clock never moved.
  Fix: `tmp.replace(path)` in both places — atomic on POSIX and Windows,
  no behavior change on the Pi (Linux `rename` and `replace` are equivalent).
### AI
- Claude Sonnet 5

## [v2.7.296] — 2026-07-18
### Added
- **IDEA-036 items 1+2 — NB O2 as per-cell rich/lean comparator** (bench-tested
  in buell_fable5 v2.7.286 first, then ported here per the test-fork workflow):
  - `web/o2.py`: V = O2_ADC×5/1023; >0.60 V rich / <0.30 V lean / mixed
    switching; label only when ≥70% of fl_o2_active-gated samples sit on one
    side (min 4). Comparator, never an AFR meter. EGO_Corr/AFV rule intact.
  - `web/launch.py`: rows carry o2_v + fl_o2; build_index accumulates per-cell
    O2 counters (BITTER exclusion already keeps decel-fuel-cut lean spikes out);
    delta rows carry o2_a/o2_b labels + mean volts (CACHE_VERSION 11→12).
  - `web/vs_engine.py _build_ci`: **lean-cell safety veto** — an eco winner
    whose own cell reads LEAN is never crowned (new stat `skipped_lean_o2`).
  - `web/templates/sessions_vs.html`: O2 RR column (A/B label + volts).
  - `tests/test_o2.py`: 11 golden tests (thresholds, dominance, veto).
### Context
- Field evidence behind the thresholds: 47BF04 R2 t=375–379 s — NB pegged
  0.00 V for 3 s at 23% TPS / 3250–3500 RPM sustained with fl_o2_active=1,
  instant 0.6 V recovery on throttle close (real lean, not a dropout; decel
  fuel cut produces the same 0 V signature as positive control). End-to-end
  653DC0 vs 47BF04: 150/153 delta cells labeled, veto fired on 3 cells,
  and 4400–4800 RPM / TPS 25–30 reads LEAN in BOTH sessions (persistent
  lean region across map epochs — matches the glassbox cube rear-lean zone).
- Doc bug registered: docs/08_ANALYSIS_TUNING.md still describes O2_ADC as
  8-bit 0–255 with 128=stoich; the validated scale is 10-bit 0–1023,
  V = ADC×0.004887585 (IDEA-036). Not corrected in this commit.
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.295] — 2026-07-15
### Fixed
- **~30% idle CPU burn in main.py (sysmon thread)**: BMP280 (0x77) and AHT20
  (0x38) are physically off the I2C bus (instant NAK), but sysmon kept polling
  every 2 s and each doomed BMP280 transaction costs ~0.83 s of kernel CPU
  (measured via strace: single ioctl ENXIO in 830 ms). Sensor reads now back
  off for 300 s after 5 consecutive failures, with a WARN log. CPU also cost
  heat (64.5 °C idle) and UPS runtime. HARDWARE follow-up: check wiring/power
  of the BMP280+AHT20 board — CW2015 on the same bus answers fine.
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.294] — 2026-07-15
### Changed
- **Backlog hygiene — 2026-07-03 audit finally actioned**: moved finished
  planning files to archive/ (BACKLOG_PROPOSAL_V2.md, BACKLOG_ECM_DEFS.md,
  BACKLOG_EEPROM_READ_LOGIC.md — all confirmed shipped, residuals tracked in
  BACKLOG.md) and extracted the audit section itself to
  archive/BACKLOG_AUDIT_2026-07-03.md (its two reopens were fixed in v2.7.285).
  Nothing deleted — archive/ is the developer diary.
### Added
- docs/HARDENING_PLAN.md — measured Pi baseline (RAM 48% is mostly OS daemons;
  buell code is ~17%; the real finding is main.py at ~30% CPU idle), runtime
  robustness queue, RAM/CPU service-separation design (analysis-as-mortal-worker,
  ride-time 503 guard, lazy sklearn imports), and the backlog keep/archive
  triage (what stays open vs what is explicitly closed).
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.293] — 2026-07-15
### Changed
- CLAUDE.md OL section corrected: the narrowband sensor is NOT disconnected —
  `O2_ADC` (rear cylinder) shows real switching (validated on 91B225 R9:
  0–0.76 V, mean 0.62 V, fl_o2_active toggling). Closed loop remains off;
  EGO_Corr/AFV remain locked at 100 and useless.
- IDEAS.md: new IDEA-036 — O2_ADC as a free ternary rich/lean gate per cell
  (proposal safety veto, Sessions VS cell labeling, switching-frequency map
  as future WB anchor cells).
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.292] — 2026-07-15
### Added
- CSV columns `bat_voltage`, `bat_soc`, `bat_charging` — UPS state per ride
  row. Until now battery data lived only in live sysmon/system_health.json,
  so a mid-ride UPS drain (or a lying charge bit) left no forensic trail in
  the ride CSV.
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.291] — 2026-07-15
### Fixed
- **UPS low-battery shutdown never fired**: the CW2015 "charging" bit
  (register 0x08 bit4) is not a charge indicator — per datasheet 0x08 is
  RRT_ALERT, so the bit can sit high indefinitely. On 2026-07-14 it claimed
  "charging" while the pack drained 30%→14% (journal + system_health.json
  evidence) and vetoed the shutdown; the Pi never powered off. New
  `sensors/battery_guard.py` discharge detector (SOC −2% or −0.03 V over a
  10-min window) now overrides the charge claim; shutdown warning logs
  `chg_claim`/`discharging`, and a vetoed shutdown below threshold is logged
  every 5 min so a lying CHG_IND is diagnosable from the journal.
### Added
- `tests/test_battery_guard.py` — 6 golden tests including a reproduction of
  the 2026-07-14 drain profile.
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.290] — 2026-07-14
### Fixed
- **BL-FABLE5-C1 (CRITICAL)**: ECO winner sign was inverted in vs_engine.py —
  every ECO/BALANCE decision crowned the RICHER map (more fuel) instead of the
  leaner one. Extracted `_eco_winner()` (dpw_eff = B−A, positive → A leaner)
  and fixed all 3 decision sites: VS-only, F7 fusion, GP gap-fill. On VS↔F7
  sign conflict the cell now abstains (new `skipped_conflicting_f7` stat)
  instead of the old "richer wins" bias — conflicting evidence is not evidence
  (same policy as proposal.py eco-vs-sport conflicts).
- **vdyno J1349 correction read `IAT_Corr` as Celsius** — IAT_Corr is the
  ECU's correction factor in percent (92–118), not a temperature; the real
  intake temp column is `MAT`. The bug inflated vdyno power ~10–12%
  systematically. Now uses MAT with plausibility guards (−20..60 °C,
  800..1100 hPa); correction is skipped when data is implausible.
- **logger_process.py write path hardened**: `session.write_sample` and
  `tracker.update` had no exception handling — one exception killed the logger
  subprocess and silently truncated the ride (glassbox finding, candidate #1
  for unexplained ride gaps). Both are now wrapped; failures are logged to the
  ride errorlog as `write_failure` events (streak-throttled to avoid spam).
### Added
- `tests/test_eco_and_j1349.py` — 8 golden tests with analytically known
  answers (eco semantics, F7 fusion/abstention, sport unchanged, J1349 MAT).
- `RideErrorLog.write_failure()` event type in ecu/session.py.
- BACKLOG_FABLE5_RESCUE.md: delta re-audit 2026-07-14 (DELTA-3..7: bench/ port,
  graf2 overlay, glassbox logger findings, portable UI features).
### AI
- Claude Fable 5 (Claude Code)

## [v2.7.289] — 2026-07-13
### Changed
- BACKLOG.md: registered pending items found during today's /fuel and repo-
  hygiene work -- BL-FUEL-01 (add_refuel's discrepancy_L/calc_remaining
  logic looks unsound, not fixed, needs its own look), BL-FUEL-02 (stray
  25MB backup tarball on the Pi), and a note flagging pre-existing
  uncommitted local work (web/server.py GPS routes + web/handlers/gps.py)
  that was deliberately left untouched across all of today's commits and
  needs its author to review/commit or discard it.
### AI
- Claude Fable 5

## [v2.7.288] — 2026-07-13
### Fixed
- system_health.json was tracked in git despite being a pure runtime log
  (the Pi appends to it continuously, causing a perpetual uncommitted diff
  on every status check -- 654 lines of drift found this session). Added
  to .gitignore alongside the other per-installation runtime state files
  (fuel_tracking.json, gear_profile.json, etc.) and untracked with
  `git rm --cached` (file stays on disk, both locally and on the Pi).
### AI
- Claude Fable 5

## [v2.7.287] — 2026-07-12
### Added
- Calibration history + undo. Every injector_cc_per_ms change (reserve-
  activation calibration, refuel calibration) now appends
  {ts, trigger, old_cc, new_cc, ratio, context} to
  `calibration_history` (capped at 20). New `undo_last_calibration()` /
  `POST /fuel/calibration/undo` reverts to the pre-calibration cc. /fuel
  page: new "Injector calibration" section showing current cc, the last 8
  events, and an UNDO LAST CALIBRATION button (single-tap -- undo is the
  corrective direction, same precedent as DEACTIVATE RESERVE).
- Live dashboard: tank % now always visible next to the fixed ~KM widget
  (gridWidgetB second line), independent of what "Widget A" is set to.
  Root cause of "km updates live but % doesn't": both come from the same
  `/fuel/status` payload refreshed every 30s (`fetchFuelStatus`) -- % was
  simply never rendered anywhere unless the user manually picked fuel_% as
  Widget A's mode. No backend cadence change was needed or made (30s
  already sits inside the "once a minute is fine" bar).
### Fixed
- `add_refuel()` calibration (liters pumped vs. logger-computed consumption
  since reserve) now runs on ANY refuel type, not just non-full-tank --
  full-tank resets, the recommended/default flow, were silently discarded
  as calibration signal before. Guarded by a new staleness check: a
  `reserve_ts` already attributed to an earlier refuel is treated as spent
  and ignored for both the km/L estimate and calibration, so a routine
  top-up long after the last real reserve event can no longer reuse (and
  corrupt) that old window.
### AI
- Claude Fable 5

## [v2.7.286] — 2026-07-12
### Fixed
- web/fuel_tracker.py: two stacked bugs found live on /fuel after today's
  fill-up showed 5.92L consumed vs 1.74+1.77=3.51L summed from the per-ride
  table. Root-caused and numerically reproduced to the cent (5.924L):
  1. Per-ride consumption (`_calc_ride_from_csv`) explicitly skipped file-
     rotation continuations (`_p2`/`_p3`...), silently dropping the tail of
     any ride that crossed the 10000-row rotation -- today's ride lost its
     last 0.6L/7.6km. Replaced with `_ride_file_group()` +
     `_calc_ride_group()`, which sum the main file and its continuations as
     one ride, used by both `save_ride_consumption_cache` (ride-close) and
     `calc_ride_consumption` (listing/recompute path).
  2. `toggle_reserve(active=True)` auto-calibrates `injector_cc_per_ms`
     against the hard-coded 13.6L full-to-reserve window on ANY reserve
     activation with >1L logged since the last fill -- an accidental tap
     with only ~3.5L logged (this session) inflated the constant from
     0.00533 to 0.007688 (+44%), retroactively skewing every future
     consumption read. Added `RESERVE_CALIBRATION_MIN_L` (half a tank):
     below that, reaching reserve is physically implausible, so the
     calibration opportunity is skipped instead of trusted.
- web/templates/fuel.html: ACTIVATE RESERVE now requires a second tap
  within 3s ("TAP AGAIN TO CONFIRM") before firing -- the accidental single
  tap that triggered bug #2 above. DEACTIVATE (correcting a mistake) stays
  single-tap.
### Data
- Pi fuel_tracking.json: injector_cc_per_ms reset 0.007688 -> 0.00533
  (matches what both existing ride caches were computed with -- no
  legitimate calibration had occurred before today's accidental one).
  ride_91B225_009_consumption.json regenerated with the fixed code
  (1.769L -> 2.366L, now includes its _p2 tail).
### AI
- Claude Fable 5

## [v2.7.285] — 2026-07-10
### Added
- BACKLOG-ANL14 disk-space watchdog (was a false DONE claim -- only a /health
  metric existed, no polling/threshold/badge/auto-stop). `main.py` sysmon loop
  now computes disk_used_pct every cycle, stops the ECU logger subprocess above
  DISK_STOP_PCT (95%) to avoid writing to a full disk, and surfaces a DSK badge
  on the dashboard (green/yellow/red at 85%/95%) via `hDisk` in app.js/index.html.
### Fixed
- BL-MAP-03 regression: the 5-swatch speed-color legend (spd2color buckets
  0-20/20-60/60-120/120-160/160+ km/h) that shipped in the old Mapa tab was
  silently deleted in v2.7.233 when that tab was replaced by gps_analysis.html,
  and never ported over. Re-added as a `#speedLegend` overlay on the 2D map in
  `gps_analysis.html`. Deleted the dead `.map-legend-bar` CSS left behind in
  `index.html`.
### AI
- Claude Sonnet 5

## [v2.7.284] — 2026-07-03
### Added
- Backlog audit: two-pass sweep across all 10 BACKLOG*.md files (~137 items inventoried, 15 stale-DONE claims + 9 duplicate pairs verified against actual code, not just backlog text). Findings written directly into the audited files: full consolidated report in BACKLOG.md ("AUDIT REPORT" section at top), inline audit markers at every item's original location. 8 items confirmed genuinely done (safe to delete), 4 items confirmed shipped but with stale spec text (needs rewrite), 2 items were FALSE DONE claims and reopened with corrected scope -- one is a genuine regression (BL-MAP-03 speed-color legend existed and was silently deleted in commit 89fefe0/v2.7.233, never ported to its replacement page). 7 of 9 duplicate pairs confirmed and flagged for merge; 1 pair (BL-FUEL-13/17) found to be a dependency chain, not a duplicate; 1 ID collision (BL-GRAF-03 used for two unrelated features across BACKLOG.md and BACKLOG_3D_VIZ.md) flagged for rename.
### Audited
- BACKLOG.md, BACKLOG_PROPOSAL_V2.md, BACKLOG_ANL.md, BACKLOG_MAPA_3D.md, BACKLOG_ECM_DEFS.md, BACKLOG_EEPROM_READ_LOGIC.md, BACKLOG_DATASET_INSIGHTS.md, BACKLOG_3D_VIZ.md -- all findings verified against actual code (function names, call sites, CHANGELOG cross-check) before being written, not trusted from the inventory pass alone.
### AI
- Claude Sonnet 5

## [v2.7.283] — 2026-07-05
### Changed
- Dashboard 2x2 big-display grid (CHT/KPH/TPS/widget-A): merged each tile's
  unit into its rotated 90° label instead of showing it twice (`CHT` + `°C`
  -> `CHT °C`; `TPS` + `%` -> `TPS %`; dropped the redundant `km/h` next to
  `KPH` since the label already is the unit). Configurable widget A
  (`_paintA` in `app.js`) now builds the same combined label via
  `_combineLabel()`, collapsing label+unit into one when they're the same
  word (e.g. `RPM`+`rpm` -> `RPM`) instead of showing both.
- Reduced `.big-num` font-size ~30% (80px->56px desktop, 64px->45px mobile)
  -- the previous size overflowed the tile at a glance.
### Fixed
- `fitLabels()` (auto-sizes the rotated big-card labels to fit the tile
  height) was only ever wired to the `resize` event, never called on
  initial page load or after `_paintA()` changed the label text -- so
  labels rendered at the browser-default size until the window was
  resized, overlapping/clipping inside the tile. Now also runs on
  `DOMContentLoaded` and after every `_paintA()` update.
### AI
- Claude Sonnet 5

## [v2.7.282] — 2026-07-05
### Fixed
- `/fuel/status` took 69s and hung the (single-threaded) dev server once any
  refuel existed, because `_calc_since()` re-parsed every row of every ride
  CSV in `sessions_dir` (82 files, 409k rows) on every call -- triggered by
  the 10s poll in `fuel.html`, so the Fill-up History panel stayed stuck on
  "Loading...". Fixed by skipping ride files whose mtime (== ride end time)
  predates the `from_ts` window being summed, instead of opening and parsing
  every historical ride on every status check.
### AI
- Claude Sonnet 5

## [v2.7.281] — 2026-07-05
### Fixed
- Fuel tracker "Save Fill-up" always failed with `404 {"error": "unknown
  endpoint"}`. Root cause: `/fuel/refuel` and `/fuel/reserve` were registered
  in the `do_GET` routing table in `web/server.py`, but their handlers
  (`_handle_fuel_refuel`, `_handle_fuel_reserve`) read the raw POST body and
  are only ever called via `fetch(..., {method:'POST'})` from `fuel.html` --
  so every request was dispatched to `do_POST`, whose routing table had no
  `/fuel/*` entries at all. Moved both routes to the `do_POST` table and
  updated both handlers to accept the already-parsed `payload` dict (which
  `do_POST` builds from the body) instead of re-reading `self.rfile` a second
  time, which would have returned empty bytes since the stream was already
  consumed upstream.
### AI
- Claude Sonnet 5

## [v2.7.280] — 2026-07-05
### Added
- Inferred Active Muffler Control (AMC / exhaust valve) status column,
  `fl_amc_active_inferred`, in the ride CSV. DDFI-2's live telemetry frame does
  not report AMC drive/feedback state (confirmed against `ecu_defs/rtdata.xml`:
  the "Active Muffler Output" bit only exists for DDFI-3) -- this is computed
  from RPM + WOT flag against the EEPROM-decoded AMC config (feature enable,
  WOT-only condition, and the 3 RPM activation regions), not measured. `None`
  when the inference can't be made (feature disabled/RPM unknown); `False`
  means "known closed". New `ecu/ecm_defs.py: decode_amc_config()` /
  `is_amc_active()`, wired into `ecu/session.py` (`open_session`/`write_sample`),
  both wrapped defensively so a decode/inference failure can never crash the
  recording loop -- worst case the column is `None` for that sample.
### AI
- Claude Opus 4.8

## [v2.7.279] — 2026-07-04
### Fixed
- Bike-identity bug when the Pi is moved between motorcycles. A ride could be
  misfiled under the PREVIOUS bike's session because `_load_eeprom` /
  `_try_cached_session` (ecu/logger_process.py) fall back to the most-recent
  `eeprom.bin` on disk (the last bike) when the live EEPROM read has not yet
  succeeded. The session checksum derives from the EEPROM, so the wrong blob →
  wrong bike → wrong session. Root-caused from today's data: after the 13:15
  restart, the Buell's first ride landed in the 1125's session (`A295AD`).
  Fix: `_load_eeprom` now returns `(blob, source)`; a session is `session_verified`
  only when its checksum came from a LIVE ECU read. Ride start is gated on
  `session_verified`, an unverified session keeps retrying a live EEPROM read
  before any ride opens, and hard-reconnect forces re-verification (hot-swap).
### Added
- Per-CSV bike-identity stamp: ride CSV header now carries
  `# logger=… session=<checksum> ecu=<firmware>` so a ride's true bike is
  auditable from the file itself, not just its folder.
- Idle-only ride tagging (ecu/session.py). A ride whose peak RPM never clears a
  per-model threshold (XB12/DDFI-2 = 2000, 1125/DDFI-3 = 2800; model resolved via
  `resolve_ecu(...).ddfi`) is tagged `idle_only=true` in `session_metadata.json`
  (`rides` map) — never deleted. New `list_ride_csvs(sdir, include_idle=False)`
  helper filters these out by default; wired into F7 (web/f7.py) and launch
  (web/launch.py) ride enumeration so bench/idle tests stop polluting analysis.
### AI
- Claude Opus 4.8, Anthropic

## [v2.7.278] — 2026-07-04
### Added
- IDEAS.md IDEA-035: reframe the sensorless "missing error signal" (IDEA-034) around this
  engine's actual geometry — a 45° uneven-firing V-twin whose two combustion events happen at
  distinct known crank angles, opening per-cylinder crank-speed-fluctuation and vibration
  channels that inline-engine research under-weighted. Queued freebuff research batch 2
  (tasks 014-017: cylinder-asymmetry physics, per-cylinder CSF, vibration sensing, how other
  twins do per-cylinder trim) in freebuff/TASKS.md.
### AI
- Claude Opus 4.8, Anthropic

## [v2.7.277] — 2026-07-04
### Added
- `ecu/ecm_defs.py`: `decode_batt_correction()` + `deadtime_ms()` — decode the ECU's own
  "Battery Voltage Correction" table (injector dead-time, voltage→ms) from the session's
  EEPROM via XML-by-name (works across firmwares, returns None when absent), and linearly
  interpolate the dead-time at a given battery voltage.
### Changed
- BL-DI-01 (injector dead-time confounder): Sessions VS now strips the battery-voltage
  artifact from PW before computing `pw_eff`/`dpw_eff`. In `web/launch.py` `build_index()`,
  each row's fueling uses `pw − deadtime(Batt_V)` (per-cylinder, same dead-time both since
  they share the battery). Raw `pw1`/`pw2` in the row are left untouched, so launch displays
  still show the actual commanded pulse; only the cross-session fueling comparison is
  corrected. This uses the ECU's REAL voltage→ms table instead of the plan's invented linear
  guess (k=0.015). CACHE_VERSION 10→11.
- Validated the model against real data before trusting it (this is why it's the table, not
  a guess): the plan claimed the +2.31% fan-on PW shift was dead-time under-compensation, but
  measuring the pw-vs-Batt_V slope showed the ~-0.60 ms/V seen at IDLE is mostly idle-control
  confound, not dead-time. At clean steady-cruise cells (the SWEET cells that matter) the
  empirical slope is -0.19 to -0.20 ms/V, matching the table's dead-time gradient (-0.16 ms/V
  near 14V) within noise — confirming both the table AND the inferred 0.125 V/count axis
  scale. So the real dead-time artifact at cruise is ~0.6-1% (not the 2.31% headline, which
  was inflated by idle-control). The correction is correct but modest for this dataset.
- Revalidation (Phases 1-4): 91B225/248AE2 unchanged (both sessions have similar voltage
  profiles at matched cells, so the dead-time subtraction cancels in dpw_eff — correct: an
  uncontaminated comparison isn't perturbed); 47BF04/248AE2 shifted in the de-confounding
  direction (one cell went insignificant, 3→4 skipped; proposal cells changed 20→18) because
  47BF04 has 45% fan-on vs the others' lower fractions. Fallback verified: no Batt_V or no
  table → deadtime 0, raw behavior preserved, no crash.
### Deferred
- `web/f7.py` delta_pw not yet dead-time-corrected (secondary fusion input; F7 events are
  short WOT pulls with momentarily-stable voltage, so the artifact is smaller there). Follow-up.
- Tuning the Battery Voltage Correction table itself (user's ECU-side idea) is mechanically
  ready but blocked on not being able to verify the correction direction without a fuel/AFR
  measurement — a wideband-gated future item, not done here.
### AI
- Claude Opus 4.8, Anthropic (analysis input: freebuff docs/PLAN_confounders_batt_baro.md)

## [v2.7.276] — 2026-07-04
### Fixed
- Removed barometric normalization of injector PW from `web/launch.py` (`load_csv` +
  `build_index`) and `web/f7.py` (`_load_csv_rows`). This was a real bug: the DDFI2 runs
  Alpha-N (TPS+RPM, no MAP sensor), so the ECU does NOT compensate commanded PW for
  barometric pressure — raw PW already carries the true map-calibration difference between
  sessions. Multiplying PW by `1013.25/baro` injected a false delta (or hid a real one
  across altitudes). This exactly violated the existing CLAUDE.md "Alpha-N fueling" rule
  ("do NOT normalize PW by (1013/baro) for DDFI2"). `dpw_eff` — which drives every cell
  decision in GAP1, F7 fusion, the GP gap-fill, and proposal.py — is now computed from raw
  PW. Collapsed the now-redundant `pw1_norm`/`pw2_norm` fields into the raw `pw1`/`pw2`
  already stored; `baro`/`baro_valid` are kept as descriptive covariates only. VDYNO's own
  baro normalization (SAE J1349, physics-based power correction) is correct and untouched.
- Cache invalidation: bumped `CACHE_VERSION` 9→10 (`vs_engine.py`) and `_F7_EVENTS_V` 9→10
  (`f7.py`) so stale results computed with the old normalization don't survive the fix.
- Sub-fix required for the above to actually take effect: `f7.py`'s per-ride
  `ride_*_f7events.json` cache was invalidated by CSV mtime ONLY, so a code change to
  event-building (like this baro fix) could not force its regeneration — the version bump
  alone would have left contaminated per-ride pw curves in place on any machine with
  existing caches (including the Pi after pull). Wrapped that cache in a versioned envelope
  (`{'v': N, 'events': [...]}`) that regenerates on `_F7_EVENTS_V` mismatch; old bare-list
  caches are treated as stale and rebuilt.
### Changed
- Corrected a factual error in `docs/PLAN_confounders_batt_baro.md` (freebuff): the plan
  assumed 47BF04 was Cuernavaca ~900-950 hPa and 91B225 was Mexico City ~780 hPa, projecting
  a 10-30% baro contamination. Actual data: both sessions log valid baro near 1000 hPa
  (997-1011 and 992-1005 hPa → factors ~0.8-1.1%), and 248AE2 has baro=0 in 100% of rows
  (broken/absent sensor → never normalized). So the confounder's real magnitude in the
  current dataset is ~1%, not the projected altitude scenario — the fix is still correct on
  principle (removes a logically-wrong operation matching CLAUDE.md), but its practical
  impact on THIS data is small. Revalidation confirms this: 91B225/248AE2 proposal unchanged
  (25 cells, 10 changed, 5.88% — the ~0.8% shift flipped no significant-cell winners),
  47BF04/248AE2 proposal shifted from its prior values (now 20 cells changed) — real but
  cell-specific, not a wholesale change. No explosion, counts stable.
- Corrects a wrong belief recorded in a prior session (memory + implied by BACKLOG.md's
  "task 006 validates our baro implementation" note): baro normalization was NOT a validated
  deliberate technique, it contradicted CLAUDE.md all along.
### AI
- Claude Opus 4.8, Anthropic (analysis input: freebuff docs/PLAN_confounders_batt_baro.md)

## [v2.7.275] — 2026-07-04
### Added
- `web/proposal.py` (FASE 6 Phase 4, final phase): `generate_proposal()` builds a
  burnable EEPROM map proposal from two compared sessions (dry run, no disk writes) and
  `save_proposal()` persists it as a `sessions/PROP_YYYYMMDD_HHMMSS/` session per
  BACKLOG.md's existing FASE 6 spec (session_metadata.json, eeprom_decoded.json,
  eeprom.bin, proposal_metadata.json, current_eeprom_decoded.json).
- `POST /eeprom/propose` reactivated (`web/handlers/eeprom.py:_handle_eeprom_propose_post`,
  registered in `web/server.py`): body `{session_a, session_b, mode?, reference?, save?}`.
  `save=false` (default) returns the proposal JSON only; `save=true` also writes the
  PROP_* session and returns its checksum. The GET variant is unchanged (still returns
  410 — deprecated on purpose, POST is the reactivated path).
### Changed
- `web/vs_engine.py`: extracted `_build_ci()` out of `_merge_maps()` (same fusion logic —
  VS + F7 zone fusion + GP gap-fill — now shared with `proposal.py` instead of duplicated).
  `_merge_maps()`'s own behavior and return shape are unchanged (re-validated: identical
  cell counts on both real test pairs after the refactor).
- Scope corrections applied during implementation (see BACKLOG_PROPOSAL_V2.md Phase 4 for
  full rationale): proposal values are always an existing session's own already-driven
  map value, never a synthesized percentage-delta number (avoids guessing an unverified
  sign convention on something that can reach a real burn); cells with no real decision
  stay at the reference session's value unchanged, not averaged (a first validation pass
  before this fix produced `cells_changed=304`, ~97% of all fuel cells, before the
  untested-cells-stay-at-reference fix brought it down to a plausible `cells_changed=10`);
  spark maps are never touched (no spark-timing signal exists anywhere upstream).
- Validated against a live local server end-to-end (not just direct function calls):
  `POST /eeprom/propose` with `save=false` and `save=true`, confirmed the saved PROP_*
  session is discoverable via the existing `/eeprom/sessions-list` endpoint (Tuner will
  list it), confirmed the encoded `eeprom.bin` round-trips cleanly through
  `decode_eeprom_maps` with exactly the expected cells changed and spark maps untouched.
### AI
- Claude Sonnet 5, Anthropic (plan: freebuff BACKLOG_PROPOSAL_V2.md Phase 4 — final phase
  of the FASE 6 revival)

## [v2.7.274] — 2026-07-04
### Added
- `requirements.txt`: added `scikit-learn==1.9.0` for FASE 6 Phase 3 (GP Regression).
  Not required for the logger's live path, only the proposal engine's gap-filling — flagged
  to check install time/RAM footprint on the Pi's first install.
### Changed
- BACKLOG_PROPOSAL_V2.md Phase 3 implemented, narrower in scope than originally planned:
  `web/vs_engine.py` gained `_gpr_make_training_data()` and `_gpr_predict_grid()` (Matern
  5/2 kernel, heteroscedastic noise from GAP1's `dpw_eff_se`), used in `_merge_maps()` to
  fill ONLY cells with zero real vs_delta votes — it never overrides an already-decided
  cell from Phases 1-2. A GP-filled cell must still pass a 95% CI test on its own posterior
  before being used (same statistical bar as GAP1, applied to the smoothed surface).
  Training intentionally includes non-significant cells too (GAP1's hard gate is bypassed
  for GP training only) since the heteroscedastic noise term is what lets the GP trust
  noisy cells appropriately instead of a binary include/exclude.
  Fixed a real bug found during validation: this sklearn version requires `alpha` and the
  fit/predict arrays as `numpy.ndarray`, not plain Python lists (raises
  `InvalidParameterError` otherwise).
- Validated on real local data (91B225/248AE2): 204 candidate empty cells, all correctly
  rejected by the GP's own uncertainty (not enough spatial coverage in this small dataset
  to extrapolate confidently) — `filled_by_gp=0`, the safe outcome. Confirmed the actual
  fill path works via a synthetic tight cluster of consistent points injected around a real
  gap — `filled_by_gp=4` in that case. No regression on cell counts from Phases 1-2.
### AI
- Claude Sonnet 5, Anthropic (plan: freebuff BACKLOG_PROPOSAL_V2.md Phase 3)

## [v2.7.273] — 2026-07-03
### Changed
- docs/pipeline_layout.json updated with the user's latest manual node arrangement
  (exported via the graph viewer's "export layout" button).
- scripts/build_pipeline_graph.py / docs/pipeline_graph.html: clicking empty canvas space
  (or a line, since edges aren't independently clickable) now clears node/edge selection,
  restoring full visibility and resetting the side panel — previously nothing happened on
  background click, so a selected node's dimming of unrelated nodes/edges stayed stuck until
  another node was clicked. Click-vs-pan is distinguished by movement threshold (>3px),
  same pattern already used for node-drag-vs-click.
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.272] — 2026-07-03
### Changed
- BACKLOG_PROPOSAL_V2.md Phase 2 implemented: F7 + VS zone fusion in `web/vs_engine.py`.
  Added `RPM_BINS`/`TPS_BINS` module-level constants and `_bin_index()` (hoisted out of
  `_merge_maps`, which now references them instead of duplicating the bin edges),
  `_zone_by_tps_peak()` (WOT >=85 / MID 40-85 / LIGHT <40), and `_f7_delta_to_cells()`
  which maps F7 cross-session matches (`web/launch.py`'s `result['f7_matches']`) to the
  same RPM/TPS cells `_merge_maps` already uses, keyed by bucket_a's rpm_center + the
  peak TPS actually reached during the pull (not the pre-event stable TPS, so the zone
  classification and the cell key agree on which throttle value they mean).
  `_merge_maps`'s SWEET/eco winner now fuses `dpw_eff` (Sessions VS) with `f7_delta` when
  a MID or LIGHT zone F7 match exists for that cell and passes GAP1 significance: weighted
  average when both signals agree on sign, rich-bias (max of the two, favoring more fuel)
  when they conflict — matching the project's "err rich, not lean" open-loop safety stance.
  WOT-zone F7 matches are excluded from this fusion by design (VS is the trusted signal
  there; SPICY_WOT/sport winner logic is unchanged). Added `f7_delta_to_cells`'s `bucket_a`
  dependency: `web/f7.py` cluster summaries now carry `tps_peak` (max across cluster
  members); bumped `_F7_EVENTS_V` 8→9 to invalidate caches missing that field.
- `web/f7.py`: cluster `bucket_a` summary gained a `tps_peak` field (max of member events'
  own `tps_peak`), needed for Phase 2's zone classification.
- Validated: real data only had one F7 cross-session match locally (47BF04 vs 248AE2,
  correctly landing in the WOT zone and therefore correctly excluded from eco fusion).
  Exercised the actual MID-zone fusion code path with a synthetic match injected at a real
  significant SWEET cell (monkeypatched `_compare_sessions_cached`) — confirmed both the
  agreeing-sign weighted-average branch and the conflicting-sign rich-bias branch fire
  correctly. Confirmed zero regression on the 91B225 vs 248AE2 pair (still 25 cells with
  data / 3 skipped insignificant, `fused_with_f7=0` since that session has no F7 clusters).
### AI
- Claude Sonnet 5, Anthropic (plan: freebuff BACKLOG_PROPOSAL_V2.md Phase 2)

## [v2.7.271] — 2026-07-03
### Changed
- BACKLOG_PROPOSAL_V2.md Phase 1 implemented: `web/f7.py` cross-session TPS matching
  (`_f7_match_cross_session`, previously line 532) now uses derivative-based DTW (DDTW)
  instead of plain amplitude DTW, per freebuff task_010's citation that DDTW is the
  vehicle-telemetry standard for cross-session alignment robust to sensor/calibration
  drift. Added `_f7_derivative()` (central-difference) and `_f7_ddtw()` wrapper; within-
  session PW clustering (`_f7_cluster`) intentionally kept on plain `_f7_dtw` — same map,
  so absolute PW amplitude is meaningful there, only the cross-session TPS shape match
  benefits from ignoring amplitude/offset. Bumped `_F7_EVENTS_V` 7 → 8 to invalidate
  cached clusters built with the old matcher.
- Validated against real session data (91B225/248AE2, the pair used for GAP1 validation,
  turned out to have zero non-orphan accel clusters in 91B225 — not a usable test case for
  F7 cross-session matching specifically). Found a better pair with actual accel clusters
  on both sides (47BF04: 6, 248AE2: 2) and confirmed: DDTW finds the same match as plain
  DTW on this data (gear 5, ~3453 RPM, ~10% TPS) — no regression, code runs cleanly against
  the real cluster/cache structure.
### AI
- Claude Sonnet 5, Anthropic (plan: freebuff BACKLOG_PROPOSAL_V2.md Phase 1)

## [v2.7.270] — 2026-07-03
### Added
- BACKLOG_PROPOSAL_V2.md committed: freebuff's 4-phase FASE 6 revival plan (DDTW in F7 →
  F7+VS zone fusion → GP Regression → new proposal.py module), built from the tasks 006-013
  prior-art sweep and cross-referenced against actual code (file:line references, task
  breakdown, effort estimates ~11.5h total, dependency graph, risk register). Linked from
  BACKLOG.md's existing FASE 6 section as the updated path to the PROP_* session output
  already planned there.
### Changed
- Verified key claims in BACKLOG_PROPOSAL_V2.md against the live codebase before accepting
  them: confirmed `/eeprom/propose` returns HTTP 410 (`eeprom.py:492`), `CACHE_VERSION=9`
  (`vs_engine.py:121`), `tps_peak` is a real F7 field, and `_f7_dtw` is plain amplitude DTW
  (all accurate). Found and corrected two errors: (1) the plan assumed scikit-learn is
  "confirmed available on Pi" — false, it's absent from requirements.txt and unimported
  anywhere; added an explicit install step before the GP Regression phase. (2) freebuff's
  separate codebase-validation pass cited `web/burn_ledger.py:convergence_report()` as a
  working GAP5 implementation — it's dead code, never called; the real one is
  `web/vs_engine.py:compute_convergence()`. Corrected in BACKLOG_PROPOSAL_V2.md and fed back
  to freebuff's standing instructions so it doesn't repeat either mistake.
- Processed freebuff's task_012 (Atomic Tune deep dive) and task_013 (universal WOT problem)
  plus 3 unrequested-but-useful follow-ups it produced on its own initiative: a consolidated
  summary of the whole 006-013 batch, a full GP Regression design doc, and the codebase
  validation pass discussed above.
### AI
- Claude Sonnet 5, Anthropic (freebuff research/planning input: task_012, task_013,
  BACKLOG_PROPOSAL_V2.md, gp_regression_proposal_generator.md, validation_vs_codebase.md,
  consolidated_summary_006-013.md)

## [v2.7.269] — 2026-07-03
### Changed
- Processed freebuff's self-initiated re-evaluation of tasks 006-009 against the ZERO-O2
  constraint (unprompted — it re-scored its own earlier findings after reading the standing
  feedback added to TASKS.md). Confirms the feedback loop is working: its downgrades of the
  Brazilian flex-fuel sensor and Russian STFT/LTFT scaling to LOW independently match the
  corrections already recorded in IDEA-032/029.
- IDEAS.md IDEA-029 item 1: added a second reframe from that re-evaluation — retrain the
  Elman-RNN architecture on our own SWEET/SPICY/BITTER labels instead of AFR, sidestepping
  the ground-truth problem. Noted precisely what this becomes (a dpw_eff smoother/generalizer,
  redundant with IDEA-031's GPR unless a real comparison shows the NN adds something GPR can't).
- IDEA-030: corrected a category error in freebuff's re-evaluation — it listed "VDYNO relative
  comparison" as newly undervalued work to prioritize; VDYNO-as-relative-comparator is BL-VD-10,
  already built, not a pending implementation item.
- IDEA-031: corrected freebuff's "software-only, zero cost" framing of GPR — zero hardware
  cost, but the modeling/prototyping/validation work is real effort, not free.
### AI
- Claude Sonnet 5, Anthropic (freebuff research input: unprompted 006-009 re-evaluation)

## [v2.7.268] — 2026-07-03
### Added
- IDEAS.md IDEA-033: swap F7's DTW for derivative-based DTW (DDTW) — freebuff task_010
  (global academic sweep) flagged DDTW as the vehicle-telemetry standard for cross-session
  alignment robust to sensor drift. Verified against actual code: `web/f7.py:_f7_dtw`
  (lines 65-79) uses plain amplitude DTW (`abs(a[i-1] - b[j-1])`), confirming this is a real
  gap, not something already covered. Concrete, same-day, low-effort item — the single most
  actionable finding of the whole 6-task research batch.
- IDEAS.md IDEA-034: cross-task synthesis — every region surveyed (Russia's Atomic Tune,
  Honda/Nissan/Subaru STFT/LTFT scaling, MegaLogViewer/VE Analyze Live) converged on the
  same bin-by-RPM×Load + compute-error + scale-cell algorithm our dpw_eff/SWEET-SPICY-BITTER
  already implements independently. Named the actual R&D frontier precisely: not the
  map-correction math (solved, five times over) but a substitute for the AFR-error signal
  itself, which every other recent IDEA (029-033) is an attempt at.
### Changed
- IDEA-030 (RPM-only torque observer) got a direct caution from freebuff task_010: inferring
  mixture quality/combustion efficiency from acceleration alone is explicitly underdetermined
  in the literature — confirms VDYNO must stay a relative comparator (as BL-VD-10 already
  uses it), never a path to absolute AFR.
- IDEA-029 item 4 (ion current sensing) reinforced with its strongest citation yet: Lee et
  al. (2001) reports <2% AFR error for non-rich conditions; freebuff calls it the single
  most promising hardware upgrade for this project across all tasks surveyed.
- Novelty claim (IDEA-028) now confirmed by task_011 across rusEFI/Speeduino, MoTeC/AiM,
  PGMFI/Nistune/ROMRaider, HP Academy, and — most pointedly — our own Buell DDFI tuning
  community (ECMSpy/TunerPro users): nobody tuning this exact ECU has attempted mixture
  inference without a wideband.
- freebuff's new standing-feedback mechanism (added this session to TASKS.md) appears to be
  working: task_010's response proactively flagged "no paper claims unsupervised long-term
  operation without any O2 feedback" and marked EKF/SMO/UIO methods with explicit ❌ where
  they require a sensor we don't have, instead of overclaiming relevance as in tasks 006/009.
### AI
- Claude Sonnet 5, Anthropic (freebuff research input: task_010, task_011 — final tasks of
  the 006-011 research batch)

## [v2.7.267] — 2026-07-03
### Added
- IDEAS.md IDEA-032: Brazilian flex-fuel virtual ethanol sensor (freebuff task_009, Japan+
  India+Brazil) recorded with a correction to freebuff's own overclaim — the algorithm needs
  a working closed-loop O2 sensor as its error signal, which this project does not have, so
  it does not transfer directly. What transfers is the pattern (turn a correction magnitude
  into a classification of an unmeasured property), which SWEET/SPICY/BITTER already
  implements using dpw_eff (map-vs-map) instead of LTFT (map-vs-live-O2-target) as the
  reference. Also logged: Japanese transient-AFR MPC (same O2-present caveat) and Indian
  multi-gas exhaust analysis as a genuinely different hardware alternative to wideband.
  Fifth literature pool (after English, China, Russia, Germany) with no automated
  cross-session log-comparison prior art found.
### AI
- Claude Sonnet 5, Anthropic (freebuff research input: task_009)

## [v2.7.266] — 2026-07-03
### Added
- IDEAS.md IDEA-030: RPM-only torque/manifold-pressure observer (freebuff task_006,
  China CN110987452A/B, mean-value engine model + Lyapunov observer) proposed as a second,
  physically independent estimator to cross-validate VDYNO's GPS-acceleration-based power
  estimate — per BACKLOG_VDYNO.md design rule 6 (cheap parallel paths, document convergence).
- IDEAS.md IDEA-031: Gaussian Process Regression as the map-proposal surface, from
  freebuff task_008 (Germany) — Tietze 2015 TU Darmstadt dissertation on GPR-based engine
  map calibration, with Local GPR explicitly handling ECU mode-switching (relevant to the
  fl_hot stratification question from BL-DI-06). Identified as a principled replacement for
  FASE 6's old IDW+Laplacian smoothing step, giving proposals a real posterior variance
  instead of per-cell independent statistics. Direct input to the (not yet started) FASE 6
  revival plan.
### Changed
- IDEA-028 (prior art positioning) strengthened with the sharpest confirmation found so far:
  freebuff task_008 shows the German industry actually built and then abandoned road-based
  calibration (Straßenapplikation, pre-2010) in favor of Road-to-Rig — capturing road data
  once and replaying it as a frozen boundary condition on a dyno, i.e. resolving the
  static-bench-vs-dynamic-street tension by freezing the street data. This project resolves
  the same tension the opposite way (keep logging open-ended, build statistics to survive
  the lack of control) — recorded as the clearest one-paragraph statement yet of why this
  project's method exists, prompted by the user's own framing this session ("el banco es
  estático, la calle es dinámica").
- IDEA-029 item 2 (transient AFR / wall-wetting) reinforced: freebuff's task_006 re-run
  (intensive mode, ICE scope broadened per user request) found the fuel-film paper is
  motorcycle-specific (Zhang Fujun, BIT 2005) using the same two inputs (TPS derivative,
  coolant temp) as our existing `AE` signal — strengthens the zero-new-hardware AE-during-F7
  analysis proposed there.
- Confirmed via freebuff task_006 re-run: no Chinese prior art for automated cross-session
  fuel-map proposal from road data (6 parallel searches, high confidence) — third
  literature pool reaching the same novelty conclusion as English (IDEA-028) and Russian
  (IDEA-029) sweeps; Germany (task_008) makes a fourth.
- freebuff task_007 (Russia) re-checked for updates: none found, already fully processed.
### AI
- Claude Sonnet 5, Anthropic (freebuff research input: task_006 intensive re-run, task_008)

## [v2.7.265] — 2026-07-03
### Changed
- IDEAS.md IDEA-029 broadened and re-verified: user redirected freebuff's task_006 scope
  from motorcycle-only to general ICE literature, freebuff re-ran it, and task_007
  (Russia/CIS) landed in the same batch. Added: transient-AFR/fuel-film (wall-wetting)
  modeling during throttle transients, with the connection freebuff itself missed — DDFI2
  is port-injected, F7 events are throttle transients, and the ECU's own `AE` (accel
  enrichment) signal is a zero-new-hardware proxy for exactly this phenomenon, already on
  disk. Also added ignition-waveform combustion diagnostics (Russian oscilloscope
  spark-duration method, cheaper GPIO-feasible alternative to Chinese ion-current sensing).
  Novelty claim (no cross-session log-comparison tool found anywhere) now confirmed by a
  third literature pool (Russian Январь/Itelma tuning scene) doing decades of manual
  open-loop tuning on ECUs structurally similar to DDFI2. Flagged a standing risk: freebuff
  cites specific papers/patents not independently verified to exist.
### AI
- Claude Sonnet 5, Anthropic (freebuff research input: task_006 revised, task_007)

## [v2.7.264] — 2026-07-03
### Added
- IDEAS.md: IDEA-029 — three no-wideband virtual-combustion-sensor paths from freebuff's
  China prior-art sweep (task_006): NN virtual lambda (viable only with a lambda ground
  truth to train on — freebuff missed the chicken-and-egg), crankshaft-fluctuation analysis
  (out of reach at our ~10 Hz serial rate; cheap per-cell RPM-jitter proxy proposed instead),
  ion current sensing (spark plug as combustion probe, hardware project). Second literature
  pool (Chinese) also found nothing resembling F7's DTW event pairing — reinforces IDEA-028.
### Changed
- Processed and cleared the freebuff response backlog: task_001-005 (gear detection
  research, 2026-06-28) verified as already fully consumed by v2.7.246/v2.7.248
  (ecu/gear_calibration.py single source of truth + web/gear_learner.py) — files deleted;
  task_006 consumed as IDEA-029 above.
- freebuff instruction files (TASKS.md header, _prompt.txt, _format.txt) updated to the
  post-v2.7.233 workflow: read the LOCAL repo on the Windows host (GitHub canonical),
  Pi is pull-only deploy target, audits go to response files — never edit CHANGELOG/any
  file on the Pi; fixed stale graphify path/invocation and added Tailscale IP.
### AI
- Claude Fable 5, Anthropic (freebuff research inputs: task_001-006)

## [v2.7.263] — 2026-07-03
### Added
- IDEAS.md: IDEA-028 — prior art comparison against published MBC/system-ID work
  (hobbyist wideband-dependent auto-tuners, on-road Bayesian/GP fleet calibration
  research, MathWorks MBC Toolbox dyno+DoE). No published tool/paper found doing
  DTW-based TPS curve matching for cross-session event pairing. Documents the framing
  that designed-excitation (dyno) trades real-world coverage for iteration speed,
  while this project's street-data approach trades speed for coverage of operating
  conditions no lab protocol samples or documents.
### AI
- Claude Sonnet 5, Anthropic (authored in remote web session; applied locally by Claude Fable 5)

## [v2.7.262] — 2026-07-03
### Changed
- CLAUDE.md: clarified git branch policy for remote/cloud sessions (Claude Code on
  the web) — when the harness assigns a default feature branch, switch to `main`
  before the first commit unless the user explicitly requests a separate branch/PR review.
### AI
- Claude Sonnet 5, Anthropic (authored in remote web session; applied locally by Claude Fable 5)

## [v2.7.261] — 2026-07-02
### Changed
- BL-DI-06 (thermal protection contamination) CLOSED AS REFUTED by empirical analysis of all 89 rides / 391,508 samples: fl_hot is a warmed-up indicator (Flags6 bit 3, flips at CLT ~65°C, matches EEPROM "Hot Start Condition" 45°C), not a protection flag — it covers 95.1% of all samples, so the proposed exclusion filter would have silently discarded 95% of the dataset. No thermal fueling/spark step exists anywhere in the warm regime (pw1 +0.58% median across a +51°C CLT band; spark +0.01°); real protection (soft 280°C / hard 295°C) never engaged in the entire dataset (max CLT ever = 280°C, one sample). Tombstone kept in BACKLOG_DATASET_INSIGHTS.md per design rules 6/7.
- BL-DI-01 (Batt_V confounder) upgraded with empirical priors from the same analysis: fan-on drops Batt_V −0.19V and shifts pw1 +2.31% (IQR −0.39/+4.71) at matched warm cells — same order as the dpw deltas the pipeline treats as map signal. Now the single confirmed highest-value hygiene item.
- docs/PIPELINE_DATA_FLOW.md updated accordingly (vs_classify and raw_ecu_batt notes, gap-to-north-star section); pipeline graph regenerated.
### AI
- Claude Fable 5, Anthropic

## [v2.7.260] — 2026-07-02
### Changed
- BACKLOG_VDYNO.md design rule 7 added: STRATIFY, DON'T EXCLUDE. Never discard data for being "outside the ideal" — split into strata and compare within-stratum. Triggered by the thermal-filter debate: fl_hot/do_fan exclusion (BL-DI-06) would throw away potentially large amounts of valid air-cooled-Buell operating data (normal head temp 160-220°C, fan threshold is an editable EEPROM byte) and would hide a map that wins specifically in the hot regime. Only physically information-free signals get fully dropped (e.g. EGO_Corr/AFV locked at 100.0 with the sensor disconnected). Cheap dual computations (gear via RPM/VSS and VSS/RPM) get done both ways and documented.
- BACKLOG_DATASET_INSIGHTS.md BL-DI-06 updated: exclusion option rejected, stratification chosen; empirical measurement of the flag's actual PW/spark effect (matched-bucket, within-session) launched before wiring anything.
### AI
- Claude Fable 5, Anthropic

## [v2.7.259] — 2026-07-02
### Added
- BACKLOG.md BL-BUG-04 — confirmed /tuner/burn 404 (Map Editor burn button) filed as a proper backlog bug, HIGH priority, flagged as needing a branch (touches an EEPROM burn path) per CLAUDE.md's git branch policy.
### Changed
- BACKLOG_VDYNO.md design rule 1 clarified: human-in-the-loop means review + approve/reject, not manual per-cell value authoring. The user does not want to decide cell deltas by hand — that has no basis beyond the data the system already processes. Human's active role is choosing what to analyze/compute (with AI) and approving or rejecting the system's proposal before burn.
- BACKLOG.md FASE 5.1 (manual VE cell editor) scoped explicitly as an exception/override tool, not the primary tuning workflow — the primary workflow is FASE 6 / VDYNO computing and proposing values, human reviews and approves.
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.258] — 2026-07-02
### Fixed
- docs/PIPELINE_DATA_FLOW.md — systematic validation pass against actual code (all json_artifact/ui_page/analysis_stage nodes fully traced, raw signals spot-checked). Added 12 missing edges and corrected 3 wrong ones, including flipping `objectives_json <-> ride_summary_json` (config feeds the ride-close computation, not the reverse) and replacing two edges that pointed at functions never actually called (`f7_cross_session_match -> ui_session_events`, `vdyno_compare -> ui_launch_power`).
- Updated the stale "GAP1 not consumed as a gate" claim in the gap-to-north-star section — v2.7.256 already fixed this for the eco/SWEET side.
### Found (not fixed — needs a live check / human call)
- `web/templates/map-editor.html` POSTs to `/tuner/burn`, which has no matching route in `web/server.py` — the Map Editor burn button likely 404s silently. Needs live verification before filing as a confirmed bug.
- `/live` in `web/server.py` hardcodes `"objectives": []`; the dashboard's real objectives display appears to be driven by a separate `raw_objectives` field instead — looks like dead code from an earlier attempt, not a broken feature.
- Two duplicate/unused implementations: `web/route_reference.py:build_slope_grid` (duplicates `gps/route_reference.py`) and `web/burn_ledger.py:convergence_report` (a second, unwired GAP5 — the real one is `vs_engine.compute_convergence`).
- `ui_session_events` does not do cross-session comparison despite CLAUDE.md's tuning-cycle table implying it does.
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.257] — 2026-07-02
### Added
- docs/pipeline_layout.json — manual node arrangement for the pipeline graph viewer, exported from the browser and committed so it's not only living in localStorage. scripts/build_pipeline_graph.py now loads it automatically (LAYOUT_OVERRIDE) and prefers it over the computed layout.
- pipeline_graph.html: export/import layout buttons (download/upload the arrangement as JSON), a save-status indicator on every drag, a confirm() dialog before "reset positions", a toggle to show all connection lines at full brightness regardless of selection, and a collapsible info panel.
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.256] — 2026-07-02
### Fixed
- web/vs_engine.py `_merge_maps` — GAP 1 significance now actually gates the only working PROPONER path. Previously a cell's eco (SWEET) winner was picked from the raw sign of `dpw_eff` alone; now cells where `dpw_eff_sig=False` (Welch 95% CI crosses zero) are skipped entirely instead of picking a side from noise. New `skipped_insignificant` count in the response. Validated against real data (91B225 vs 248AE2): 3 of 25 cells with data were previously assigned a winner from a non-significant delta. The `sport` (SPICY_WOT/ddvss) side is NOT gated — no GAP1-equivalent CI exists for ddvss yet, noted inline as a follow-up (BACKLOG.md GAP 1 remaining item).
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.255] — 2026-07-02
### Added
- docs/PIPELINE_DATA_FLOW.md — structured data-flow inventory (68 nodes, 102 edges) of the full tuning pipeline: raw signals -> JSON artifacts -> analysis stages -> UI pages, tagged by reliability (ACTIVE_VALID/ACTIVE_UNVALIDATED/INACTIVE_NOISE/CAPTURED_UNUSED/DESIGN_ONLY). Documents that `_merge_maps` (the only working PROPONER path today) never checks `dpw_eff_sig` (GAP1 significance), that `rider_notes` and most GRAF2 annotation types are captured but never read downstream, and that `f7.py`/`launch.py` baro-normalize PW unconditionally (reconciled against CLAUDE.md's Alpha-N doctrine via BACKLOG.md task 006 -- not a bug, but the reconciliation isn't written down in CLAUDE.md itself).
- scripts/build_pipeline_graph.py + docs/pipeline_graph.html — standalone left-to-right layered DAG viewer generated from PIPELINE_DATA_FLOW.md, no charting library. Longest-path layering with DFS cycle-breaking (loop-back edges arced separately), barycenter row ordering to reduce line crossings, draggable nodes with localStorage-persisted positions, click-to-select with full transitive upstream/downstream highlight (BFS both directions), reliability filters.
- .graphifyignore — excludes CHANGELOG.md (noise) and sessions/ (ride data, not code — was inflating the graphify code graph from ~2.9k to ~29k nodes) from `graphify update .`
### Changed
- BACKLOG_VDYNO.md — added design decision #6: multiple processing paths over the same raw data are valid to explore in parallel (cheap to compute on the Pi), but validation (burning + riding) stays serial and human-gated; abandoned paths must be documented with the reason, not just left silent.
### AI
- Claude Sonnet 5, Anthropic

## [v2.7.253] — 2026-06-30
### Added
- GAP 5: compute_convergence() in vs_engine.py — residual variance of dpw_eff across consecutive session pairs. GET /convergence?sessions=A,B,C,D returns per-pair variance and global convergence status. Threshold 0.002 (~0.2% PW diff); converged=True when last 3 consecutive pairs are below threshold.
### AI
- Claude Sonnet 4.6

## [v2.7.252] — 2026-06-30
### Fix
- BL-GRAF-03: removed floating #cur-readout panel from GRAF2 (was rendering full-width due to CSS conflict); cursor values now shown inline in block header chips only.
### AI
- Claude Sonnet 4.6

## [v2.7.251] — 2026-06-30
### Changed
- BACKLOG.md: BL-ECM-01 marked DONE — validated that ecm_defs.py, version_resolver.py, rt_defs.py are all implemented and in production. XML-driven decode/encode/pages/RT vars confirmed. Residual low-priority item extracted as BL-ECM-01-RESIDUAL (RPM_BINS/LOAD_BINS hardcoded in protocol.py — no corruption risk, affects only CSV cell headers for non-BUEIB).
- BACKLOG.md: BL-ECM-03 (revert EEPROM version guard) marked DONE — already implemented per CHANGELOG.
- BACKLOG.md: removed duplicate BL-ECM-03 entry. Updated BL-ECM-02 and BL-XPR-01 dependency notes to reflect BL-ECM-01 completion.
### AI
- Claude Sonnet 4.6

## [v2.7.250] — 2026-06-29
### Fix
- `main.py _sleep_gps()`: only stop gpsd and send M8N backup-mode command when `_poweroff_requested` is True. On a plain service restart (`systemctl restart buell-logger`) gpsd.socket was being killed, leaving GPS dead on the next start. GPS reader thread is still stopped on both paths.
### AI
- Claude Sonnet 4.6

## [v2.7.249] — 2026-06-29
### Cleanup
- Remove dead `CENTERS` constant from `ecu/protocol.py` (was "reference only" after v2.7.248 refactor). Update `gear_detect.py` docstring to correctly describe threshold fallback chain. Add `gear_profile.json` to `.gitignore` and untrack it — it is per-installation learned data, not code.
### AI
- Claude Sonnet 4.6

## [v2.7.248] — 2026-06-28
### Refactor
- Extract gear thresholds to `ecu/gear_calibration.py` as single source of truth. Both `ecu/protocol.py` (live GearFilter) and `web/gear_detect.py` (post-ride) now import `GEAR_THRESHOLDS_LIVE`/`GEAR_THRESHOLDS_DETECT` and `COAST_RATIO_MIN` from this shared module. Eliminates threshold duplication that caused live vs post-ride disagreement when values were updated in only one place.
### AI
- Claude Sonnet 4.6 + FreeBuffs

## [v2.7.247] — 2026-06-28
### Fix
- GearFilter live gear display: recalibrate CENTERS and THRESHOLDS in `ecu/protocol.py` from 313k samples across all sessions. Previous values [0,75.5,53.8,40.1,33.3,28.7] were off by ~30-40% — gear-5 riding (ratio ~33) was being classified as gear 4 every time the window committed. New CENTERS [0,142.8,76.0,60.1,53.7,33.4] with brute-force THRESHOLDS [106,73,58,47] match actual distributions. Fixes "nunca le atina a la marcha" on live dashboard.
### AI
- Claude Sonnet 4.6

## [v2.7.246] — 2026-06-28
### Features
- BL-GEAR-01: data-driven gear detection — `web/gear_learner.py` rewritten to use ECU-reported `Gear` column as ground truth; finds optimal RPM/VSS ratio threshold between each adjacent gear pair by brute-force minimisation; 92.71% accurate vs 91.41% hardcoded; largest improvement at 2/1 boundary (errors 1101→28, threshold 90→106); works for any bike that reports a Gear column (XB12X, 1125CR, etc.)
- `GearLearner.learn()` now populates `gear_profile.json` using per-boundary optimisation instead of k-means on raw histogram (k-means was failing due to ECU quantisation artifacts creating multi-modal within-gear distributions)
- `/gear_profile?learn=1` endpoint triggers re-learning from all sessions
### AI
- Claude Sonnet 4.6

## [v2.7.245] — 2026-06-28
### Docs
- BACKLOG: close BL-GPS-03 (done in slope_reference.py), discard BL-GPS-04 (GPS M8N absolute altitude not suitable — systematic errors from bridges/underpasses do not average out, per-session bias ±10m), document BL-GPS-05 limits (differential slope ±3-5% precision, only reliable for grades ≥4%), update GAP 4 scope accordingly
- Analysis conclusion: GPS altitude is useful for geographic orientation and coarse slope detection (>4%) only. Absolute altitude reference and sub-3% slope detection are physically impossible with M8N — do not revisit
### AI
- Claude Sonnet 4.6

## [v2.7.244] — 2026-06-28
### Fixed
- GPS Analysis 3D: dblclick pivot hit-test uses rect.width/height (CSS px) instead of canvas.width/height (physical px) — restores accurate pivot selection after HiDPI fix
### AI
- Claude Sonnet 4.6

## [v2.7.243] — 2026-06-28
### Fixed
- GPS Analysis 3D canvas: render at devicePixelRatio resolution — eliminates blur on HiDPI displays; geometry and pointer events stay in CSS pixels
### AI
- Claude Sonnet 4.6

## [v2.7.242] — 2026-06-28
### Fixed
- GPS Analysis: load Leaflet from /static/ instead of unpkg CDN — fixes "L is not defined" when offline
### AI
- Claude Sonnet 4.6

## [v2.7.241] — 2026-06-28
### Added
- GPS Analysis: coordinate display — overlay on 2D map updates lat/lon on chart cursor hover; chart title shows lat/lon at cursor position; click anywhere on 2D map shows popup with exact coordinates
### AI
- Claude Sonnet 4.6

## [v2.7.240] — 2026-06-28
### Added
- BL-GPS-05: gps/slope_reference.py — differential slope accumulator using within-ride altitude deltas between consecutive GPS bucket transitions (5–40 m segments); per-session GPS offset cancels in the delta so slope converges even when absolute altitude drifts ±10 m; MAD outlier rejection across sessions; canonical segment key with direction sign for bidirectional lookup; GET /slope_reference endpoint (stats, update, coordinate query)
### AI
- Claude Sonnet 4.6

## [v2.7.239] — 2026-06-28
### Fixed
- GPS Analysis 3D: reverted to raw GPS altitude for rendering — ref_alts bucket quantization creates visual staircase; ref_alts stays reserved for ALT chart comparison and F7 slope calculation
### AI
- Claude Sonnet 4.6

## [v2.7.238] — 2026-06-28
### Fixed
- GPS Analysis 3D: apply Gaussian moving average (halfWin=10) to merged ref+raw altitude before 3D render — eliminates bucket-boundary staircase artifact from 11m spatial bucketing
### AI
- Claude Sonnet 4.6

## [v2.7.237] — 2026-06-28
### Changed
- GPS Analysis 3D map: uses trusted reference altitude (ref_alts) per point when available, falls back to raw GPS; shows `[trusted alt]` / `[raw GPS alt]` label in top-right corner of 3D canvas
### AI
- Claude Sonnet 4.6

## [v2.7.236] — 2026-06-28
### Added
- GPS Analysis: trusted reference altitude overlay — `/gps_analysis_data` now returns `ref_alts` array (RouteReference lookup per lat/lon); chart gains ALT mode button showing raw GPS alt (blue) vs trusted reference alt (green) + noise delta (red); statsBar shows ref coverage %; RAW/REF/Δm series toggles in alt mode
### AI
- Claude Sonnet 4.6

## [v2.7.235] — 2026-06-28
### Added
- BL-GPS-03: GPS quality filter (_gps_quality) in F7 — gates altitude use on satellites>=6, epv<5m, mode==3 (newer CSVs); gps_lat/lon/sats/epv/mode added to F7 row dict
- BL-GPS-04: gps/route_reference.py — multi-pass averaged GPS altitude profile with MAD outlier rejection; RouteReference.update_all_sessions() ingested 14 sessions / 171k points / 6182 buckets (95% confident with 3+ passes); GET /route_reference endpoint (stats, update, coordinate query)
### AI
- Claude Sonnet 4.6

## [v2.7.233] — 2026-06-28

### Changed
- **Workflow migration**: local-first development with GitHub as source of truth
- CLAUDE.md: updated workflow from Pi-SSH to Local -> GitHub -> Pi (git pull)
- FREEBUFF.md: rewritten for local-first audit (no SSH needed)
- buell-sessions/CLAUDE.md: rewritten as session data reference
- All hardcoded /home/pi/buell/ paths replaced with relative paths (__file__ + buell_dir params)
- web/utils.py: _get_version() uses relative path + utf-8 encoding
- web/server.py: sys.path.insert + buell_dir fallback use relative paths
- web/vs_engine.py: sys.path.insert uses relative path
- network/manager.py: STATE_FILE now configurable via buell_dir
- web/fuel_tracker.py: FUEL_FILE accepts buell_dir parameter
- tools/health_journal.py: HEALTH_FILE accepts buell_dir parameter
- web/handlers/system.py: git_pull cwd uses buell_dir
- web/handlers/fuel.py: passes buell_dir to fuel_tracker
- main.py: _get_version() uses relative path + utf-8 encoding
- Git remote added: origin https://github.com/pacdavid1/buell-xb12x-logger.git

### AI
- DeepSeek V4 Flash, Codebuff (Buffy)

## [v2.7.232] -- 2026-06-28
> **Pi rollback point — commit `b731e67`**
> If deploy of v2.7.233–v2.7.249 fails: `git reset --hard b731e67 && sudo systemctl restart buell-logger`

### fix: crisp HiDPI canvas charts in Sessions VS (no more blurry graphs)

All 5 chart canvases used a fixed backing-store size (e.g. 620x200) rendered on
HiDPI/retina/4K screens with 2-3x more physical pixels -> blurry lines and text.
Added a hidpi() helper that scales the backing store by window.devicePixelRatio,
keeps CSS size in logical px, and scales the 2D context so draw code stays in
logical coords. Idempotent across re-renders.

- web/templates/sessions_vs.html: hidpi(canvas) helper + applied to
  drawClusterPowerChart, drawClusterChart, drawDualClusterChart,
  drawLaunchChart, and the launch dyno canvas
- Charts now render sharp on any pixel density

## [v2.7.231] -- 2026-06-28

### feat: GAP 1 UI -- flag non-significant fuel deltas in Sessions VS

Backend (v2.7.230) computed dpw_eff_sig per cell; now the Sessions VS table
surfaces it. When a cell's dpw_eff 95% CI crosses zero (the fuel delta could be
noise), its dPW1/dPW2 cells are dimmed (opacity .35), prefixed with "~", and
carry a tooltip showing dpw_eff and its CI. Significant cells render as before.

- web/templates/sessions_vs.html renderBody(): sigDim/dimStyle/sigMark/sigTitle
  derived from r.dpw_eff_sig; applied to the two fuel-delta cells
- Backward compatible: only dims when dpw_eff_sig is explicitly false (old
  cached rows without the field render normally)

Now a decision to burn a cell is visually gated by whether its difference is
statistically real, not just by its magnitude.

## [v2.7.230] -- 2026-06-28

### feat: GAP 1 -- per-cell statistical significance for dpw_eff (Welch CI)

Sessions VS reported dpw_eff per cell with no measure of whether the difference
was real or noise (wind, temp, traffic, rider variation). You could be burning a
map that is "better" by pure statistical fluctuation. Now each common cell gets a
95% Welch confidence interval and a significance flag.

- web/launch.py build_index(): Welford online std for pw_eff per cell (std_pweff),
  same pattern already used for std_rpm/std_tps
- web/launch.py delta loop: Welch two-sample CI on dpw_eff
    se = sqrt(std_a^2/na + std_b^2/nb);  CI = dpw_eff +/- 1.96*se
    dpw_eff_sig = True only when CI does not cross 0
  New delta fields: dpw_eff_se, dpw_eff_ci_lo, dpw_eff_ci_hi, dpw_eff_sig
- web/vs_engine.py: CACHE_VERSION 8 -> 9 (delta schema changed)

Validated on 917900 vs 3311B1: 13/17 cells significant. Cells with more samples
get a tighter CI (na=38 -> se=0.126) vs sparse cells (na=6 -> se=1.049), exactly
as expected. The 4 non-significant cells are ones the old code treated as real.

CAVEAT (honest): samples within a cell are autocorrelated (consecutive 10Hz
rows), so N is optimistic and the CI is narrower than the true independent CI.
Welch over samples is a real improvement over nothing, but a cell flagged
significant with few independent visits should still be treated with caution.
Tracked as a follow-up (effective N from independent visits).

Not yet done: UI does not yet surface dpw_eff_sig (next step -- mark
non-significant cells as "insufficient data" instead of a proposal).

## [v2.7.229] -- 2026-06-28

### fix: three backlog quick wins -- GPS CSV fields, AHT20 init retry, gear neutral detection

BL-GPS-01: three GPS fields the reader already produces were being silently
dropped by the CSV DictWriter (extrasaction="ignore"). Now persisted so
post-session analysis (Kalman VSS+GPS, GPS quality score, VSS auto-cal) can
use them.

- ecu/protocol.py: add gps_heading_rate, gps_turning, gps_stale to CSV_COLUMNS

BL-BUG-01 (AHT20): the sensor could fail permanently until process restart if
it was in a transient state right after power-up (single init attempt). Added
3 retries x 100ms in begin(). File rewritten in English (was Spanish).

- sensors/aht20.py: begin() retries via _try_begin_once(), read() handles the
  RuntimeError path gracefully, full English rewrite + DEV NOTE

BL-BUG-01 (gear detect): detect_gear() reported false 1st gear in neutral.
Data analysis (session 248AE2, 67k samples) confirmed the RPM/VSS ratio cannot
separate low-speed 1st gear (clutch slipping, ratio up to 735) from neutral
revving -- the distribution is a continuous tail with no clean cut. Fixed using
the physical neutral switch (di_neutral) already present in the CSV instead of a
magic ratio ceiling.

- web/gear_detect.py: detect_gear() accepts di_neutral; returns 0 when set
- web/f7.py, web/launch.py: pass di_neutral from the CSV row (backward
  compatible -- old sessions without the column degrade to ratio-only)

Backlog audit: BL-ECM-04 (SERIAL_RX_BYTES) was already resolved -- _rx_bytes
updates dynamically from ecu._rt_frame_size on connect/reconnect. proposal.py
_clamp() item is obsolete -- proposal.py no longer exists, /eeprom/propose
deprecated.

## [v2.7.228] -- 2026-06-27

### feat: GPS M8N backup mode on shutdown -- reduces idle draw from 25mA to ~15uA

Before poweroff, shutdown() now sends UBX-RXM-PMREQ (indefinite backup) to
the u-blox M8N via /dev/ttyS0. The chip enters backup mode (~15uA) with the
timepulse LED off. M8N wakes automatically when gpsd restarts at next boot
(first UART byte triggers wake).

- main.py: _sleep_gps() method -- stops GPS reader, stops gpsd/gpsd.socket,
  sends UBX-RXM-PMREQ (class=0x02 id=0x41 duration=0 flags=0x02), fenced
  try/except so failure never blocks poweroff
- main.py: gps-sleep added as first step in shutdown() steps tuple
- gps/m8n_config_backup.json: UBX config backup (CFG-PRT, CFG-RATE, CFG-NAV5,
  CFG-GNSS, MON-VER, CFG-TP5) -- baud=9600, 1Hz, portable nav model

Test confirmed: timepulse LED stops immediately on PMREQ, resumes on gpsd start.
Power LED stays on (3.3V rail, hardware -- cannot cut in software).

## [v2.7.227] -- 2026-06-27

### fix: sysmon thread crash loop -- TypeError in battery shutdown f-string

**Root cause of battery drain to 0%:**

Chain of failures:
1. CW2015 in SLEEP mode (fixed in v2.7.226) => voltage=0 filtered to None, SOC=0.0 passes filter
2. boot_soc captured as 0.0 => _get_shutdown_threshold() returns (-1, 3.20) => v_crit=True
3. Shutdown warning f-string {_v:.2f} with _v=None raises TypeError
4. sysmon thread dies; thread watchdog restarts it every 30s
5. Thread immediately crashes again => loop forever, no monitoring, no poweroff
6. Battery drains to 0% undetected

Fixes:
- main.py: guard f-string for None voltage/soc in shutdown warning
- main.py: boot_soc captured only when > 0 (guard against fake-zero readings)

Both bugs are now moot (cw2015 wake fixes the root cause) but kept as
defense-in-depth in case of future I2C errors or sensor unavailability.

## [v2.7.226] -- 2026-06-27

### fix: CW2015 in SLEEP mode -- wake on init, readings now correct

Root cause: CONFIG register 0x0A bit7 (SLEEP) was set, causing VCELL and SOC
to read 0 while STATUS still responded. Battery IS present (Pi runs on battery
when AC disconnected). Profile registers 0x10-0x4F were also all zeros.

- cw2015.py: _wake() called in __init__ clears SLEEP bit if set
- cw2015.py: read_all() re-checks and clears SLEEP bit on each read (power glitch guard)
- cw2015.py: removed battery_present() VER-based gate (wrong assumption)
- cw2015.py: read_all() returns bat_charging from CHG_IND bit (STATUS bit4)
- main.py: removed bat_present field, uses _hw_charging from read_all()
- main.py: hardware CHG_IND remains primary charging source with voltage-trend fallback

Result: bat_voltage=3.666V, bat_soc=5.1%, bat_charging=True, bat_trend=up

## [v2.7.225] -- 2026-06-27

### fix: CW2015 UPS battery reports 0% when no battery present

**Root cause:** CW2015 VER register reads 0x0000 (should be 0x00A5) and
VCELL/SOC registers both read 0 when battery is absent or dead. The old
SOC filter (0 <= s <= 100) passed the 0 value as valid, showing 0%.

- cw2015.py: Added battery_present() via VER register check; read_all()
  now returns None for voltage/SOC and bat_present=False when no battery
- cw2015.py: SOC filter changed from 0<=s<=100 to 0<s<=100 (0 is invalid)
- cw2015.py: read_all() now returns bat_charging from STATUS bit4 (CHG_IND),
  which works independent of battery presence (driven by charger IC pin)
- main.py: Hardware CHG_IND is now primary charging source; voltage-trend
  heuristic kept as fallback when CW2015 not present
- main.py: bat_present propagated through serial_stats to UI
- server.py: bat_present added to serial_stats default dict

**Result:** UI now shows -- for SOC/voltage with charging indicator visible
when UPS is connected to power but battery is absent/dead.

**Hardware note:** battery is physically absent or completely dead (VER=0x0000).
CHG_IND=1 confirms charger circuit is active and receiving power.

## [v2.7.224] -- 2026-06-27

### docs: FASE V4 iterative map optimizer documented in BACKLOG_VDYNO

- Documented two-mode optimization algorithm: Hybrid mode (best-of-N cells
  from competing maps by measured vdyno HP) and Proposal mode (conservative
  +/-% experiments when no competing maps exist)
- Physical-based tuning philosophy: acceleration/vdyno as fitness function,
  no wideband required, CLT as safety guardrail
- Cell-to-HP attribution: mapping vdyno bins to active EEPROM map cells
  during WOT segments (session_cell_scores.json per session)
- Environmental noise filters: SAE J1349 air density correction, GPS slope
  compensation, mass correction via fuel_tracker; slope flagged as biggest
  contaminant (~2 HP per 2% grade at 100 km/h)
- Noise floor rule: only declare VERDE/ROJO if delta_HP > 2*sigma of
  same-map ride-to-ride variance; otherwise GRIS/inconclusive
- Manual override digest: tuner aggressive changes enter the pool and get
  processed by next hybrid cycle without losing baseline history
- New backlog items BL-VD-10 through BL-VD-14

## [v2.7.223] -- 2026-06-27

### map-editor: UI polish and chart improvements

- Remove "3D drag to rotate" hint text (intuitive, no label needed)
- Axis labels in 3D chart now rotate to follow their axis direction on screen
- 3D tick values sorted ascending on both axes (fixes scrambled ECU axis data)
- 3D face color uses max of 4 corner values instead of average — spikes now show correct heatmap color vs table
- Table column headers (X axis) colored red, row headers (Y axis) colored green — matching 3D axis colors
- Cell heatmap color scale computed from actual data range per map (fixes all-red display on maps like idle air control setpoint 1150-1700 range)
- Axis unit labels moved out of corner cell into map title header as inline subtitle (cleaner table)
- Toast font preview: changing font size now triggers a live toast so the effect is visible immediately
- Floating font panel: toast input now labeled "Toast / notifications"

## [v2.7.222] -- 2026-06-25
### Changed
- Added Map Editor link to nav menu in all page templates (index, tuner, session_events, sessions_vs, sessions_launch, graf2, fuel, errorlog_viz)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.221] -- 2026-06-25
### Added
- New /map-editor page (BL-TUNER-02): all maps stacked vertically, editable table left + 3D surface right
- 3D surface renderer ported from tuner.html — Lambert shading, depth sort, drag-rotate, scroll-zoom per map
- Bar chart renderer for 1D maps (rows=1) with value labels and color gradient
- Session dropdown with URL sync (?session=ID) and localStorage font-scale persistence
- Inline cell edit: click to stage, Enter/Escape to confirm/cancel, max 50 cells
- Staged cells reflected live in both table (amber) and 3D surface (gold outline on faces)
- Hover tooltip: shows X axis value, Y axis value, current cell value
- Per-map staged badge in block header
- Front maps accented orange, rear maps accented blue
- Dynamic font scale: CSS variable --fs-base drives all text sizes; slider in header adjusts in real time
- Timing maps now correctly colored (units: Degree matched to timing range 0-50)
- /map-editor route added to server.py and TunerHandlerMixin
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.220] — 2026-06-25
### Fixed
- tuner.html: tab buttons had mismatched HTML quotes in the class attribute template — class="tab was never closed before data-m=", causing the HTML parser to treat data-m as part of the class value and fuel_map_front/etc. as a standalone attribute without a name; b.dataset.m was always undefined, setting cur=undefined on every tab click which broke render() and triggered the mouseleave TypeError
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.219] — 2026-06-25
### Fixed
- tuner.html: added missing closing brace for render() after its try-catch block
- tuner.html: added missing closing brace for drawAll() after its try-catch block
- tuner.html: added missing semicolon after tabLabel function expression
- All three fixes resolve the JS SyntaxError (Unexpected end of input / Unexpected token var) that prevented the tuner page from loading
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.218] -- 2026-06-24
### Changed
- BACKLOG.md: added BL-TUNER-02 — new tuner page, all maps vertical with table+3D side by side per map

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.217] -- 2026-06-24
### Fixed
- tuner.html: tab order and labels restored to original UX — fuel maps first (FUEL FRONT/REAR), then spark/timing (SPARK FRONT/REAR); removed debug line

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.216] -- 2026-06-24
### Changed
- tuner.html: removed XPR FILE section (HTML block + loadFile function) — XPR loading moves to dedicated page BL-XPR-01; code preserved in git history

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.215] -- 2026-06-24
### Changed
- BACKLOG.md: added BL-XPR-01 — dedicated XPR/Session map editor page (removed XPR section from tuner pending this page)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.214] -- 2026-06-24
### Fixed
- tuner.html: tab bar showed all XML maps including 1D maps (startup_enrichment etc.); now filters to 2D maps only (rows>1 && yaxis), defaulting to first fuel map

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.213] -- 2026-06-24
### Fixed
- tuner.html: default map selection skipped 1D maps (startup_enrichment, no yaxis) — now picks first 2D map (fuel_map_front) as default; fixes heatmap showing only RPM axis row with no data rows

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.212] -- 2026-06-24
### Fixed
- tuner.html: SyntaxError in load() — escaped quotes (\") inside single-quoted JS string produced literal backslashes, breaking script parse and preventing session dropdowns from populating on page load

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.211] -- 2026-06-21

### Changed
- fuel.html: header restructured to single-line layout with .hdr-logo wrapper
- fuel.html: body now uses flexbox layout (display:flex;flex-direction:column;height:100dvh)
- fuel.html: scrollbar hidden on .content while preserving scroll functionality
- fuel.html: "HOW TO ACTIVATE FUEL TRACKING" instructions now collapsible (starts collapsed)
- fuel.html: fixed duplicate "v" in version display (v--LOGGER_VERSION-- → --LOGGER_VERSION--)

### AI
- Claude Sonnet 4.6 (DeepSeek-v4-flash)


## [v2.7.210] -- 2026-06-20

### Changed
- Ride dashboard: restructured from 3 rows x 6 to 5 rows x 4 auto-sizing stat grid
  .hdr-row converted from display:flex to display:grid;grid-template-columns:repeat(4,1fr)
- Header logo row separated into .hdr-logo CSS class to prevent grid interference with flex
- Tailscale toggle button in Redes panel with systemctl start/stop/status via NOPASSWD sudoers

### Added
- Dashboard: 20 data-slot containers (5 rows x 4) numbered 1-20
- Tailscale VPN control: toggle + status indicator + IP display in Redes pane
- /tailscale POST endpoint with _handle_post_tailscale handler
- Passwordless sudo rule for pi user to control tailscaled service
- tailscale JS toggle/status functions in app.js

### Removed
- Old .hdr-stats/.hdr-comms wrapper divs (direct children .hdr-row)
- Fixed 60px width constraint on stat chips (now auto grid 1fr 1fr 1fr 1fr)
- Vertical label rotation on stat chips (horizontal 10px labels)

### AI
- DeepSeek V4 Flash

## [v2.7.209] - 2026-06-20
### Feature
- Dashboard (/): EEPROM map viewer now XML-driven. /maps endpoint returns full
  decode_maps_full() format ({maps: {norm_key: {label,data,rows,cols,xaxis,yaxis,units}},
  axes: {norm_key: {label,data,units}}}). Map tabs generated dynamically for all 21
  DDFI-3 maps (vs 4 hardcoded). Legend and header updated dynamically per selected map.
- tuner.html: Fixed loadFile() (was checking d.fuel_front — broken); now checks d.maps
  and generates tabs dynamically. Matches load() behavior.
- app.js: showMap() reads from new nested format; supports any map/axis combination.
  Legend shows actual axis labels from XML. All Spanish strings converted to English.
- handlers/eeprom.py: _handle_maps() uses decode_eeprom_maps_full() (not old 4-map
  decode_eeprom_maps()). Falls back to latest session bin if no session param given.
- index.html/app.js: Remaining Spanish status/error strings converted to English.

### AI
- Claude Sonnet 4.6 (claude-sonnet-4-6) via Claude Code
## [v2.7.208] - 2026-06-20
### Feature
- Tuner page now XML-driven: all maps and axes read from ECU XML definition,
  no hardcoded keys. DDFI-2 shows 6 maps, DDFI-3 shows 21 maps automatically.
- ecu/ecm_defs.py: added _norm(), decode_maps_full() returning all Map/Axis entries
  with normalized keys, explicit xaxis/yaxis references from XML <xaxis>/<yaxis> tags.
- ecu/eeprom.py: added decode_eeprom_maps_full(); encode_eeprom_maps() now accepts
  both legacy keys (fuel_front) and new XML-driven keys (fuel_map_front).
- web/handlers/tuner.py: /tuner/maps now returns full XML-driven format.
- web/handlers/eeprom.py: burn handler uses decode_eeprom_maps_full() for
  cell validation; supports burning any map by normalized key.
- web/templates/tuner.html: tabs generated dynamically from API response;
  removed hardcoded AX dict and 4 tab buttons; fixed Spanish UI strings.

### AI
- Claude Sonnet 4.6


## [v2.7.207] - 2026-06-20
### Fix
- Sessions VS: block comparison when DDFI families differ (DDFI-2 vs DDFI-3).
  Previously showed empty table with common:0 and no explanation.
  Now returns error with map_mismatch flag; UI shows explicit ⚠️ message.
  Comparison of different bikes with the same firmware is still allowed.
  Changes: web/vs_engine.py (import + guard), web/templates/sessions_vs.html (UI).

### AI
- Claude Sonnet 4.6


## [v2.7.206] - 2026-06-20
### Fix
- `CellTracker.snapshot()` in `ecu/session.py`: KeyError 'count' when cells were
  populated via IPC `set_snapshot()` (subprocess architecture). The subprocess writes
  cells.json in output format (ego_avg, confidence...) but snapshot() expected raw
  internal format (count, ego_sum...). Fix: passthrough cells already in output format.
  Result: live.json no longer crashes while engine is running on DDFI-3.
- `web/templates/tuner.html`: XPR FILE firmware selector now defaults to
  auto-detect instead of hardcoded BUEIB.
### Validated
- First DDFI-3 (1125CR, BUE2D242) live session: A295AD, 2 rides recorded,
  summary + tuning_report generated. RPM/ride_active/ecu_connected all correct.

### AI
- Claude Sonnet 4.6


## [v2.7.205] - 2026-06-20
### Fix
- Dashboard black screen on hotspot (no internet): Chart.js, PapaParse, Leaflet JS+CSS
  were loaded from external CDNs. Synchronous `<script>` tags block JS execution while
  waiting for a TCP connection that never completes on an offline AP.
  Fix: downloaded all 4 files to `/web/static/` and changed `index.html` to serve them
  locally via `/static/`. Google Fonts remains CDN-only (CSS link, non-blocking, optional).

### AI
- Claude Sonnet 4.6


## [v2.7.204] - 2026-06-20
### Fix
- `_handle_coverage_json` in `web/handlers/rides.py`: bare `session` NameError crashed
  every `/coverage.json` request, causing dashboard black screen on hotspot and home WiFi.
  Fix: read `self.server_instance.session.current_checksum` before building `_csv_url`.

### AI
- Claude Sonnet 4.6


## [v2.7.203] - 2026-06-21
### Feature
- F7 Phase 2.2 (Option B): pilot-marked launch events from GRAF2 annotations
- New `_f7_events_from_annotations()` in `web/f7.py`: reads `ride_*_annotations.json`,
  filters `type == "launch"`, extracts rows in [t0_s, t1_s], builds event dicts with the
  same shape as `_f7_detect_events` output (bucket_a, pw_curve, tps_curve_norm, etc.)
- Bucket A from [t0_s - 3s, t0_s) pre-window rows; extra fields: `annotation_id`, `annotation_note`
- Pilot events pass through same `_f7_cluster()` + `_f7_temporal_stats()` pipeline
- Result has separate `pilot_clusters` list (cluster_id `P{i:03d}`, cluster_type `pilot-marked`)
  — NOT mixed with auto `clusters`. "Las vemos juntas pero no revueltas."
- `_f7_load_session_clusters()` staleness check now includes annotation file mtimes
- Added `_F7_PRE_N = 10` module-level constant; bumped `_F7_EVENTS_V` 6 -> 7 (invalidates caches)

### AI
- Claude Sonnet 4.6


## [v2.7.202] - 2026-06-21
### Fix
- BL-ECM-04: `SERIAL_RX_BYTES = 107` was hardcoded — serial stats bps/rx display was wrong for DDFI-3
- Introduced local `_rx_bytes = SERIAL_RX_BYTES` in `run()` (default 107, DDFI-2)
- Updated to `ecu._rt_frame_size` after each `set_ecu_version()` call: initial connect and hard reconnect
- Stats `bps`, `rx` fields now reflect actual 135-byte frames when connected to DDFI-3 ECU

### AI
- Claude Sonnet 4.6


## [v2.7.201] - 2026-06-21
### Fix
- BL-ECM-03: `_handle_eeprom_revert` now validates EEPROM layout before burn
- Version guard reads donor session `version_string` from `session_metadata.json`,
  resolves DDFI tier via `resolve_ecu()`, and compares against live `ecu_identity['ddfi']`
- Blocks revert with clear error if donor DDFI != live ECU DDFI (e.g. DDFI-2 donor vs DDFI-3 ECU)
- Guard skipped only when version info is unavailable on either side (fails open, not closed)
- Added `from ecu.version_resolver import resolve_ecu as _resolve_ecu` to `web/handlers/eeprom.py`

### AI
- Claude Sonnet 4.6



## [v2.7.200] - 2026-06-20
### Infrastructure
- Tailscale installed (v1.98.4) — Pi accessible from any network at 100.78.186.123
- Web dashboard: http://100.78.186.123:8080 from any device on the Tailscale network
- tailscaled enabled as systemd service (auto-starts on boot)
- dpkg database /var/lib/dpkg/ initialized (was missing — all apt installs were failing silently)
- Tailscale account: pacdavid1@gmail.com
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.199] - 2026-06-20
### Changed
- ecu/protocol.py: decode_rt_packet() now accepts optional rt_vars dict and frame_size int; defaults to module-level DDFI-2 constants for backward compat
- ecu/connection.py: DDFI2Connection stores self._rt_vars + self._rt_frame_size; set_ecu_version() resolves ddfi family via resolve_ecu() and calls load_rt_vars() to update both; get_rt() reads self._rt_frame_size bytes and passes self._rt_vars to decode_rt_packet()
### Result
- BL-ECM-02: native DDFI-3 RT frame support (135 bytes / 121 vars) — connecting Pi to 1125CR (BUE2D242) now reads full DDFI-3 frame automatically; no XPR workaround needed
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.198] - 2026-06-20
### Added
- web/handlers/tuner.py: _handle_tuner_maps_file() - GET /tuner/maps/file?path=<file>&version=<ver> decodes any .xpr or .bin from /tmp/ or the buell data dir. Auto-detects firmware version from filename stem if not specified. Returns same JSON as /tuner/maps
- web/server.py: registered /tuner/maps/file route
- web/templates/tuner.html: XPR FILE panel with path input, firmware dropdown, Load as Base/Mod buttons. Clicking Load sets mB or mM and renders immediately (auto-fills both slots if only one loaded so render works)
### Added (pending)
- BACKLOG.md: BL-ECM-03 revert EEPROM version guard - revert writes raw bytes bypassing encode; needs version match check before burn
### Context
- Multi-firmware insight: DDFI-2 XMLs all share 12x13 fuel dims but different offsets (BUEIB=870 BUEGB=862 BUECB=802). DDFI-3 all share 16x20. encode_eeprom_maps already supports cross-version burn by value (decode with source XML encode with dest XML). Only revert path uses raw bytes
### AI
- Claude Sonnet 4.6, Anthropic


## [v2.7.197] - 2026-06-20
### Fixed
- ecu/version_resolver.py: resolve_ecu() now uses longest-prefix match before alpha-only fallback. Real ECU version strings like 'BUE2D242' now resolve to 'BUE2D' (was returning None because alpha-strip turned '2' in 'BUE2D242' into 'BUED' which had no match)
### Validated
- decode_eeprom_maps(xpr_bytes, 'BUE2D242') produces fuel_front 16x20, spark_front 10x14 from real BUE2D (1125CR) hardware XPR dump. Axes match EcmSpy MSQ byte-exact (20 RPM bins [400..10700], 16 TPS bins [7..255])
### AI
- Claude Sonnet 4.6, Anthropic


## [v2.7.196] - 2026-06-20
### Changed
- ecu/eeprom.py: encode_eeprom_maps() now XML-driven — offsets, dimensions, and scale come from ecm_defs._entries() for the given firmware version (was hardcoded to BUEIB 870/1038/670/770). Burn guard: unknown firmware returns eeprom_bytes unchanged, nothing written. encode(decode(blob)) validated byte-identical in safe zone across 12 BUEIB sessions
- web/handlers/eeprom.py: pass _session_version(eeprom_path) to encode_eeprom_maps() so the correct firmware XML is used during burn
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.195] - 2026-06-20
### Changed
- ecu/ecm_defs.py: added get_eeprom_pages(version_string) — EEPROM page table moved here from connection.py. BUEIB confirmed on live hardware; unknown firmware falls back to sequential 256-byte pages
- ecu/connection.py: removed hardcoded BUEIB_PAGES and duplicate RT_RESPONSE_SIZE=107. DDFI2Connection now stores _ecu_version (default "BUEIB") and exposes set_ecu_version(). read_full_eeprom() and write_full_eeprom() derive page layout and total size dynamically
- ecu/logger_process.py: call ecu.set_ecu_version() after get_version() on initial connect and hard reconnect
- ecu/session.py: _rebuild_summary() now uses self._rpm_bins/self._load_bins instead of module globals. cell_key() renamed to _cell_key(rpm, load, rpm_bins, load_bins) with explicit bins params; call site uses self._rpm_bins/self._load_bins
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.194] - 2026-06-20
### Fixed
- CLAUDE.md: restored "How to edit files on the Pi" rule body (code examples were stripped by shell backtick expansion in previous session)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.193] - 2026-06-20
### Changed
- CLAUDE.md: added "Where to work" rule — Pi is source of truth, all changes via SSH; Windows clone is read-only
- CLAUDE.md: commit workflow now includes mandatory git push after every commit
- CLAUDE.md: Alpha-N section clarified as DDFI2-only; added note that DDFI3 (1125CR) is Speed Density — baro normalization belongs in DDFI3-specific code only
- CLAUDE.md: WB sensor section expanded with strategic rationale — building F7+VS pipeline first, WB arrives as validation layer on proven system
- CLAUDE.md: removed baro normalization from priority backlog (not a working rule; DDFI3-specific concern)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.191] - 2026-06-20
### Added
- ecu/rt_defs.py: parse ecu_defs/rtdata.xml at import time to build RT_VARIABLES per DDFI family. load_rt_vars('DDFI-2') returns (dict, 107); load_rt_vars('DDFI-3') returns (dict, 135). lru_cache — parsed once per family. Mirrors ecm_defs.py pattern for EEPROM maps
### Changed
- ecu/protocol.py: removed 57-line hardcoded RT_VARIABLES dict; RT_VARIABLES and RT_RESPONSE_SIZE now loaded from rt_defs.load_rt_vars('DDFI-2') at module level — single source of truth in rtdata.xml
### Fixed
- CDiag4 was decoded from offset 71 (wrong — that byte is RDiag0/Recent Errors, secret). Correct offset per XML is 101
- HDiag4 was decoded from offset 79 (wrong — that byte is unknown-79). Correct offset per XML is 103
- Unk63 (offset 63, 1B) is the barometric pressure sensor ADC (EcmSpy name: "Baro ADC") — legacy key name preserved for caller compatibility
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.190] - 2026-06-20
### Added
- mypy.ini: permissive mypy config (Python 3.11, ignore_missing_imports, no strict)
- CLAUDE.md: type hints rule — add return types to every Python function touched
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.189] - 2026-06-20
### Added
- ecu_defs/rtdata.xml: EcmSpy RT parameter definitions for DDFI2 (90 params) and DDFI3 (126 params, 135-byte frame). Unblocks live logging for 1125CR — same PDU framing, only RT_VARIABLES dict + frame size differ
### Changed
- BACKLOG.md: BL-ECM-02 blocker resolved — rtdata.xml found, DDFI3 live logging path documented
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.188] - 2026-06-20
### Changed
- ecu/session.py: CellTracker now stores rpm_bins/load_bins as instance vars (default = BUEIB310 protocol globals). New set_bins(rpm_bins, load_bins) method updates the grid at runtime. _bilinear_weights uses self._rpm_bins/self._load_bins instead of module globals
- main.py: _update_web_ecu_state calls tracker.set_bins() with axes from decoded EEPROM after every EEPROM read — CellTracker grid now matches the actual ECU fuel map axes
- ecu/logger_process.py: same set_bins() call at ECU connect and post-burn; imported decode_eeprom_maps
- Backward-compatible: if set_bins() is never called, BUEIB310 defaults apply
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.187] - 2026-06-20
### Added
- BACKLOG.md: BL-ECM-02 — multi-bike DDFI3 support (1125CR). Architecture decision: one integrated software, firmware-aware layers. Documents what BL-ECM-01 already covers, what needs new work, and the live logging blocker (no ADX for DDFI3)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.186] - 2026-06-20
### Changed
- ecu/ecm_defs.py: replace hardcoded 1206 size guard with dynamic min_size derived from max(offset+size) across all XML entries — BUE1D (1125CR) requires 2904 bytes and now passes cleanly
- ecu/eeprom.py: remove BUEIB-specific fuel load axis check (blob[632:644] all non-zero) from _validate_eeprom — offset 632 is unrelated in other firmwares; _validate_eeprom now uses only firmware-independent fields (serial/year/config at offsets 8-13)
- Golden bin validation: 12/12 BUEIB sessions still pass byte-identical
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.192] - 2026-06-20

### Added
- T1: Disk space watchdog -- /health endpoint now returns disk_free_gb, disk_total_gb, disk_used_pct (shutil.disk_usage)
- T2: Auto-gzip old CSVs -- scripts/gzip_old_csvs.py compresses CSVs >30 days old, weekly cron (Sunday 03:00)
- T4: BL-MAP-03 3D speed legend -- Color-coded speed bar (0-20/20-60/60-120/120-160/160+ km/h) overlaid on track3d canvas
- T5: Camera preset labels -- 3D view buttons renamed S1-S4 to T(top)/R(rear)/F(front)/S(side) with tooltip titles
- T6: CSV export link -- _handle_tuning_report now includes _csv_url in JSON response pointing to format=csv

### Changed
- T2: gzip script excludes files modified in last 5 minutes (active write protection)
- T2: /home/pi/buell/logs/ directory auto-created for cron output
- T4: 3D legend labels match 2D legend format for consistency

### Removed
- T3: O2_ADC overlay in sessions_vs comparison table -- reverted, requires backend data pipeline (non-trivial)

### AI
- Buffy (deepseek-v4-flash)

**Audited:** N/A - trivial tasks, no cross-cutting concerns

## [v2.7.185] -- 2026-06-20
### Changed
- BL-ECM-01 Phase B2: thread real ECU version through all decode_eeprom_maps() callers.
  Added web/utils._session_version(bin_path) helper (reads session_metadata.json).
  Updated: main.py (live path uses ecu_version from serial), handlers/tuner.py,
  handlers/eeprom.py (5 call sites), vs_engine.py (2 call sites).
  Removed dead import in server.py. All 12/12 golden bins pass regression harness.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (BL-ECM-01 Phase B2: _session_version verified in utils.py, tuner.py, main.py)
## [v2.7.184] -- 2026-06-20
### Changed
- ecu/eeprom.py (BL-ECM-01 Phase B1): decode_eeprom_maps() now delegates to
  ecm_defs.decode_maps() (XML-driven, multi-firmware). Backward-compatible:
  all callers omitting version get BUEIB310 default; output byte-identical
  (validated 12/12 golden BUEIB bins). Removed dead code: BUEIB_PARAMS dict
  and decode_eeprom_params() (replaced by ecu.eeprom_params since v2.x).
  encode_eeprom_maps() unchanged (Phase C).
- IDEAS.md: added IDEA-027 (ghost lap — two rides synchronized by GPS distance,
  not time; telemetry overlay on shared distance axis for map-vs-map comparison)
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (BL-ECM-01 Phase B1: ecm_defs.decode_maps imported, BUEIB_PARAMS removed, encode unchanged, IDEA-027 in IDEAS.md)
## [v2.7.183] -- 2026-06-20
### Changed
- IDEAS.md: added IDEA-022 through IDEA-026 from creative backlog review
  IDEA-022: stator failure early warning via fan load impulse (Batt_V droop trend)
  IDEA-023: map evolution as trajectory in 312-dim fuel space (converging vs oscillating)
  IDEA-024: cc_per_ms calibration drift as injector wear indicator
  IDEA-025: weather as natural lambda sweep without wideband (density × acceleration)
  IDEA-026: engine wear isolated via repeated GPS segments (map as control variable)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.182] -- 2026-06-20
### Changed
- ARCHITECTURE.md: replaced static 923-line manual doc with auto-generated version (scripts/gen_architecture.py)
- FREEBUFF.md: updated freebuff workflow document
- scripts/gen_architecture.py: new utility -- generates ARCHITECTURE.md from actual file tree + module docstrings
- archive/ARCHITECTURE_v2.6.10.md: archived old manual ARCHITECTURE.md for reference
- .gitignore: exclude inbox/ (operational freebuff comms, Pi-local only)
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (gen_architecture.py exists, .gitignore inbox/, ARCHITECTURE_v2.6.10.md archived)
## [v2.7.181] --- 2026-06-19
### Changed
- GPS Analysis replay: pre-render quality strip to offscreen canvas (_stripCache); drawStripCursor is now O(1) per frame instead of O(n)
- GPS Analysis replay: cache uPlot overlay BoundingClientRect at replay start instead of per-frame layout reflow
- GPS Analysis replay: 2D map follows cursor when it leaves visible bounds (animate: false to avoid competing rAF loop)
- GPS Analysis 3D: batch track segments by color before stroking — reduces ctx.stroke() calls from ~1200 to ~20-40 per frame
- GPS Analysis replay: fix absolute clock timing (was broken for data gaps — cursor would freeze indefinitely)
- GPS Analysis replay: skip data gaps larger than 1s instead of waiting through them at real-time speed
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.180] --- 2026-06-19
### Changed
- GPS Analysis 3D: dblclick now also sets the clicked point as the rotation pivot
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.179] --- 2026-06-19
### Added
- GPS Analysis 3D: dblclick on 3D canvas finds the nearest track point to the click
  position and marks it — updates 2D marker, quality strip cursor, legend text, and
  moves the chart cursor to that time position
- GPS Analysis 3D: dataIdxMap stored in _t3 to map decimated 3D pts back to DATA indices
### Changed
- GPS Analysis 3D: dblclick no longer resets view (was reset, now is mark-point);
  canvas hint updated accordingly
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.178] --- 2026-06-19
### Fixed
- GPS Analysis 3D: vertical exaggeration capped at 4x (was uncapped — a 5km ride with 50m
  elevation gain produced 15x exaggeration making gentle hills look like mountains)
- GPS Analysis 3D: zoom extended to 50x (was 10x)
- GPS Analysis 3D: zoom level and alt exaggeration factor shown in top-right corner of canvas
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.177] --- 2026-06-19
### Added
- GPS Analysis: 3D pause button (3D pause) stops auto-rotation
- GPS Analysis: pivot rotation — pause 3D, click chart to set pivot point (purple crosshair),
  3D then rotates around that geographic point instead of the track center
- GPS Analysis: dblclick on 3D canvas also clears pivot; unpause clears pivot
- GPS Analysis: contextual hint in 3D canvas changes based on pause/pivot state
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.176] --- 2026-06-19
### Fixed
- GPS Analysis: added GPS ANALYSIS header label in toolbar
- GPS Analysis: 3D pan changed from Shift+drag to Ctrl+drag; controls hint shown at canvas bottom
- GPS Analysis: replay now drives uPlot chart cursor (synthetic mousemove on over element)
- GPS Analysis: chart setCursor hook skips update during replay (prevents hover interference)
- GPS Analysis: 3D camera follows cursor point during replay without modifying manual pan state
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.175] --- 2026-06-19
### Changed
- GPS Analysis: 3D pan via Shift+drag to translate view; double-click 3D canvas resets position, angle, and zoom
- GPS Analysis: replay button (1x/4x/10x speed) advances marker through 2D+3D+strip in real time
- GPS Analysis chart: 2-finger touch pan slides X axis when zoomed; removed redundant Y-fit button
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.174] — 2026-06-19
### Changed
- GPS Analysis: 3D rotation 18s→30s per revolution, zoom range extended to 0.1–10×
- GPS Analysis chart: drag-zoom on X axis (select range), double-click or ⟳ button to reset,
  Y⇕ toggle for auto-fit visible range, GPS fix mode shown in cursor readout
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.173] — 2026-06-19
### Added
- GPS Analysis page (/gps_analysis): side-by-side 2D Leaflet + 3D canvas, uPlot speed chart
  comparing GPS speed vs VS_KPH, GPS fix quality strip, spin event markers, cursor sync,
  and stats (GPS dist, VSS dist, max spin delta, artifact count)
- Spin detection: marks on 2D map where VS_KPH - GPS_speed > 8 km/h (rear wheel spin during WOT)
- GPS artifact detection: flags events where GPS > VSS by >12 km/h while fix is active
- Nav link GPS Analysis added to all page hamburger menus
### Changed
- Map tab: 2D 35dvh / chart 15dvh / 3D 50dvh (Option C — less vertical scroll, bigger 3D)
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (gps_analysis page, nav link, 3D split CSS 35/15/50dvh)
## [v2.7.172] — 2026-06-19
### Fixed
- BL-MAP-01: GPS map track never loaded — loadMapTrack checked d.ok but /gps_track never sets that field; removed the check
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (BL-MAP-01: d.ok check removed from loadMapTrack)
## [v2.7.171] — 2026-06-19
### Fixed
- web/static/graf2.js: GRAF2 floating cursor readout stretches full width when cursor
  moves to left half. Cause: CSS stylesheet has `right:8px` as a rule; JS was setting
  `el.style.right=''` which only clears inline style, leaving the stylesheet rule active —
  so left:8px + right:8px (from CSS) = full width stretch. Fixed: use 'auto' instead of
  '' so the inactive side is explicitly overridden in both directions.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (GRAF2 cursor: el.style.left/right set to 'auto' at line 59)
## [v2.7.170] — 2026-06-19
### Docs
- BACKLOG.md: added BL-GRAF-03 — remove GRAF2 floating cursor readout (#cur-readout
  stretches full width, bug confirmed). Replace with inline cursor values in each lane
  header so each chart shows its own current value without a centralized panel.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.169] — 2026-06-19
### Fixed
- web/templates/session_events.html: BL-UX-04 — n=1 cluster curves rendered as thin
  line instead of full-width average line. Two root causes: (1) cached events have
  pw_curve stripped to save space — added fallback to pw1_curve when pw_curve is
  missing; (2) showEvt individual renders (lineWidth=0.8) were firing for n=1 and
  painting over the avg — skip individual renders when mb.length===1.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (BL-UX-04: n=1 fallback pw1_curve, solo detection, lineWidth)
## [v2.7.168] — 2026-06-19
### Changed
- CLAUDE.md: objectives section refined — "session" → "conversation" to avoid
  collision with ride-session concept; cycle steps removed from objectives
  (already documented in tuning cycle section); replaced with philosophy statement
  ("every ride is an experiment, every burn is a hypothesis test").
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.167] — 2026-06-19
### Docs
- CLAUDE.md: added "Objectives" section at the top (before all other content).
  System objective: continuous autonomous DDFI2 map optimization via LOG→ACOTAR→
  COMPARAR→PROPONER→QUEMAR cycle. Claude objective: active co-exploration, not just
  task execution — surface math, techniques, and patterns the user can't yet request.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.166] — 2026-06-19
### Changed
- CREATIVE_MODE.md: removed 3-ideas-per-session limit. Replaced
  "if already in IDEAS.md → skip" with "enrich the existing entry instead
  of creating a duplicate."
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.165] — 2026-06-19
### Docs
- IDEAS.md: 3 new GPS creative-mode ideas (IDEA-019/020/021).
  IDEA-019: climb rate from GPSFix to correct VDYNO vertical power error (~7% per
  8° slope, currently silently inflates/deflates uphill vs downhill WOT pulls).
  IDEA-020: HDOP from SKY messages as primary GPS quality gate (universally standard,
  already computed by gpsd, ignored today — 2-line addition to reader.py).
  IDEA-021: GPS idle WATCH disconnect — send ?WATCH=false when no ride is active to
  stop CPU wake-ups on Pi Zero 2W; warm start recovers fix in <1s (explains faster
  satellite detection observed post-Fase 2).
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.164] — 2026-06-19
### Added
- ecu/protocol.py: 5 new GPS fields added to CSV_COLUMNS — gps_mode, gps_epx,
  gps_epy, gps_epv, gps_snr_avg. These are now persisted to CSV for post-analysis
  (resolves BL-GPS-01). Freebuff/Buffy authored; version corrected from stale v2.7.158.
- web/handlers/gps.py: _handle_gps_config() GET endpoint — returns current GPSConfig
  as JSON (stale_timeout, turn_rate_threshold, min_snr).
- web/handlers/gps.py: _handle_gps_config_update() POST endpoint — applies runtime
  GPSConfig changes via query params.
- web/handlers/gps.py: /gps_track enriched — track points now include gps_heading,
  gps_mode, gps_snr_avg when available. Freebuff/Buffy authored.
- web/server.py: registered /gps_config and /gps_config_update routes (were missing —
  freebuff added handlers but did not wire routes).
### Fixed
- web/vdyno.py: SAE J1349 correction in _seg_physics() silently never applied because
  r.get('IAT') always returns None (CSV field is IAT_Corr). Fixed to r.get('IAT_Corr').
  Freebuff/Buffy authored J1349 block (version corrected from stale v2.7.157);
  field name bug found and fixed by Claude Sonnet 4.6 during inbox validation.
### AI
- DeepSeek V4 Flash, Codebuff (Buffy) — GPS Fase 3 handlers + J1349 block
- Claude Sonnet 4.6, Anthropic — route registration fix + IAT field name fix + validation

**Audited:** PASS - Buffy 2026-06-20 (GPS fields in CSV_COLUMNS, IAT_Corr in vdyno.py, gps_config routes)
## [v2.7.163] — 2026-06-19
### Docs
- IDEAS.md: merged IDEA-016/017/018 from freebuff (Buffy). IDEA-016: bootstrap
  confidence interval for VDYNO compare_sessions(). IDEA-017: SAE J1349 air
  density correction for VDYNO (IAT + baro already in CSV). IDEA-018: adaptive
  launch detection threshold (rolling 2-sigma vs hardcoded dtps=8.0).
  GPS Fase 1+2 BACKLOG items from freebuff stash discarded — already covered by
  BL-GPS-01/02 (v2.7.161) and implemented in v2.7.160/162.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.162] — 2026-06-19
### Added
- gps/reader.py GPS Fase 2 (freebuff/Buffy — version corrected from v2.7.156):
- GPSConfig class (stale_timeout=5.0s, turn_rate_threshold=30 deg/s, min_snr=0)
  with as_dict() and runtime set_config(**kwargs).
- SNR tracking: average signal strength of used satellites from SKY messages,
  exposed as gps_snr_avg. Optional validity gate: if min_snr>0 and snr<min_snr,
  fix marked invalid (default disabled — min_snr=0).
- Heading rate of change (deg/s) with 0-360 wrap handling. Rate >= threshold
  sets gps_turning=True. Exposed as gps_heading_rate and gps_turning in as_dict().
- stale detection now uses config.stale_timeout instead of hardcoded 5.0s.
### Fixed
- gps/reader.py: SKY handler had duplicated SNR logic in both uSat and fallback
  branches. Extracted to _snr_from_sat_list() helper — single path, same result.
### AI
- DeepSeek V4 Flash, Codebuff (Buffy) — GPS Fase 2 implementation
- Claude Sonnet 4.6, Anthropic — validation, DRY fix, version correction

**Audited:** PASS - Buffy 2026-06-20 (GPSConfig class, heading_rate, turning, snr_avg in reader.py)
## [v2.7.161] — 2026-06-19
### Docs
- IDEAS.md: added IDEA-014 (gps_turning as F7 event quality filter — turning events
  contaminate cross-session PW comparisons) and IDEA-015 (GPS quality composite
  score 0-1 from mode+epx+snr+stale as single gate for all GPS consumers).
- BACKLOG.md: added GPS section with BL-GPS-01 (persist Fase 1 fields to CSV —
  epx/epy/mode/stale are in-memory only, never written to ride_*.csv) and
  BL-GPS-02 (validate and integrate GPS Fase 2 from freebuff inbox, including
  version conflict fix).
### AI
- Claude Sonnet 4.6, Anthropic (creative mode)

## [v2.7.160] — 2026-06-19
### Added
- gps/reader.py: GPSFix now captures fix precision (epx, epy, epv) and gpsd mode
  (0=no fix, 2=2D, 3=3D). New fields exposed via as_dict() as gps_epx, gps_epy,
  gps_epv, gps_mode. mode is stored inside the lock so stale_ts and valid update
  atomically with the fix. Precision fields cleared to None when fix is lost.
- gps/reader.py: stale fix detection — gps_stale=True when no valid fix has been
  received (stale_ts==0) or last fix is older than 5s.
  Written by freebuff (DeepSeek V4 Flash / Codebuff). Version corrected: freebuff
  proposed v2.7.155 (already taken by BL-UX-04); recorded here as v2.7.160.
  Claimed bug fix (epx←msg['epy']) was a false positive — old code had no epx/epy
  at all; freebuff added new code and mislabeled it as a fix.
### AI
- DeepSeek V4 Flash, Codebuff (Buffy) — GPS changes
- Claude Sonnet 4.6, Anthropic — version correction, changelog audit

**Audited:** PASS - Buffy 2026-06-20 (gps_epx/epy/epv/mode/stale fields in reader.py)
## [v2.7.159] — 2026-06-19
### Added
- BL-UX-03 (Sessions VS): environmental stats row per session. `load_csv` now
  captures `baro_temp` and `humidity` per row. New helper `_env_stats(rows)`
  computes avg baro_hPa, baro_temp_c, humidity_pct, and gps_alt_m from rows
  with valid readings. Stats added to `sa.env` / `sb.env` in compare result.
  Frontend `renderFlavors` shows a dimmed env row (baro · °C · humidity · alt)
  below the flavor legend when any env data is present. CACHE_VERSION bumped
  7→8 to force cache rebuild with new env fields.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (_env_stats helper, CACHE_VERSION=8, env stats in sessions_vs.html)
## [v2.7.158] — 2026-06-18
### Added
- BL-3DV-03: staged cells now highlighted in MOD 3D view. Faces adjacent to any
  staged cell get an orange stroke (rgba 245,166,35) at 1.5px instead of the default
  white 0.5px ghost stroke. Each face stores its grid (i,j) coords; at draw time the
  STAGE[cur] lookup checks all 4 corners of the quad. BASE 3D and DELTA 3D unaffected.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (BL-3DV-03: orange stroke rgba(245,166,35) for staged cells in MOD 3D)
## [v2.7.157] — 2026-06-18
### Fixed
- MSQ download buttons in tuner.html were `<button>` elements with class `.vb`,
  which received a white browser-default background because `.vb` had no `background`
  property. Fixed by: (1) adding `background:transparent` to `.vb` CSS rule,
  (2) converting both MSQ buttons from `<button>` to `<span>` elements, and
  (3) moving them inline beside the Base/Modificada labels instead of below the
  select dropdown, so they no longer clutter the session selector area.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (MSQ buttons as span with background:transparent)
## [v2.7.156] — 2026-06-18
### Fixed
- BL-GRAF-05: GRAF2 ⚙ gear button moved to left side of block header so it is
  always visible regardless of how many signal chips are present. Removed from
  block-btns, placed before block-title with flex-shrink:0 (graf2.js).
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (GRAF2 gear button left of block-title with flex-shrink:0)
## [v2.7.155] — 2026-06-18
### Fixed
- BL-UX-04: Session Events n=1 cluster curves rendered at lineWidth 0.8 instead
  of full weight. Root cause: _compute_cluster_stats returns early for len<2, so
  pw_avg/rpm_avg/etc are absent. Frontend now falls back to mb[0] curves when
  solo=true, giving n=1 clusters the same visual weight as multi-sample ones.
  Pre-event zone (drawPre) and main curve (drawAvg) both get the fallback.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.154] — 2026-06-18
### Fixed
- app.js: all four polling interval handles (_liveInterval, _freezeInterval,
  _cobertInterval, _fuelInterval) changed from `let` to `var` for consistent
  global scope. Freebuff audit had changed only _fuelInterval; this completes
  the fix across all four.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** FAIL - Buffy 2026-06-20 (CHANGELOG claims let->var but app.js lines 58-61 still use let)
## [v2.7.153] — 2026-06-18
### Changed
- BL-M3D-01: increased 3D GPS track canvas height in Mapa tab from 38dvh to
  70dvh. The pane already scrolls (overflow-y:auto on .content); this makes the
  canvas big enough to actually see and interact with the track. Canvas
  auto-resizes via getBoundingClientRect() on every draw frame — no JS changes
  needed.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.152] — 2026-06-18
### Added
- BL-GRAF-04: floating cursor data readout in GRAF2. A `#cur-readout` panel
  (fixed-position, dark, monospace) shows timestamp + all signal values at
  the cursor position across all blocks. Dodges left ↔ right based on mouse X
  with 80 px hysteresis so it never overlaps the cursor. Hides automatically
  when the cursor leaves the chart area. `transition: .12s` on left/right for
  smooth hop (`graf2.html`, `graf2.js`).
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (#cur-readout floating panel with _rdLeft positioning)
## [v2.7.151] — 2026-06-18
### Added
- BL-3DV-10: persist 3D camera state in `localStorage` (`buell_cam_3d`). YAW/PIT/ROL
  angles, ALT scale, and ZOOM survive page reload. Saved on every `applyAngles()` call
  and on mouse-wheel zoom; loaded automatically in `init3D()` startup.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (buell_cam_3d localStorage, saveCameraState/loadCameraState in tuner.html)
## [v2.7.150] — 2026-06-18
### Added
- BL-3DV-07: PNG snapshot button in 3D control bar (`tuner.html`). Clicking PNG
  stitches all three canvases (BASE / DELTA / MOD) into one wide image with labels,
  triggers a `canvas.toBlob()` download named
  `3D_{MAP}_{SESSION}_{DATE}.png`. No server round-trip.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (PNG snapshot button with snapshotAll3D + toBlob)
## [v2.7.149] — 2026-06-18
### Removed
- `decode_params_dict()` from `ecu/eeprom_params.py` — compat wrapper (returns
  `decode_params` result keyed by name) with zero callers anywhere in the codebase.
  Freebuff dead-code audit flagged it; exhaustive grep confirmed 0 references.
- Dead-code and orphan-file sections from BACKLOG.md — function names were blank
  (backtick rendering bug). After full investigation: only `decode_params_dict`
  was genuinely dead; all other flagged functions have internal callers; orphan
  scripts were already removed in v2.7.62.
### Changed
- `ecu/eeprom_params.py`: added DEV NOTE header, translated Spanish docstrings
  to English.
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (decode_params_dict removed, DEV NOTE added)
## [v2.7.148] — 2026-06-14
### Note
- Carries the actual GRAF2 type-required code + backlog docs that were missing from the
  `v2.7.147` commit (a `git add` with a stale pathspec staged nothing but the file rename,
  so `v2.7.147` landed empty). This commit completes it.
### Changed
- GRAF2 annotation `type` is now REQUIRED instead of defaulting to `launch`. The mark
  modal opens with no type selected ("— choose type —") and saving is blocked with an
  inline "pick a type first" warning until the user picks launch/diagnostic/note
  (web/static/graf2.js). Backend rejects writes without a valid type with HTTP 400
  (web/handlers/rides.py). Rationale: a `launch` default makes users pass everything as
  launch, polluting the F7 PILOT-MARKED pipeline.
- GRAF2 annotations with no/unknown type now render in an amber "unclassified" color so
  legacy/untyped marks are visually flagged for reclassification (web/static/graf2.js).
### Added
- BACKLOG_ECM_DEFS.md (BL-ECM-01): multi-ECU support via EcmSpy XML — promoted from the
  freebuff inbox. Plan to remove hardcoded BUEIB EEPROM/RT offsets (14 firmwares, 217
  differing offsets). Marked TOP priority / core of the project in BACKLOG.md (without it
  the logger only works for the author's BUEIB); flags the burn-corruption risk in
  encode_eeprom_maps() and the open RT_VARIABLES / backward-compat questions.
- BACKLOG BL-DX-01: auto-bump README/architecture version on commit (low priority).
### AI
- Claude Opus 4.8, Anthropic

**Audited:** PASS - Buffy 2026-06-20 (GRAF2 type required + BACKLOG_ECM_DEFS.md exists)
## [v2.7.146] — 2026-06-14
### Fixed
- ecu/session.py: **CRITICAL** — `_update_tuning_report` usaba `v["o2_adc_sum"]`
  (variable del loop anterior de cells) en vez de `a["o2_adc_sum"]` (loop actual
  de agg). Cada celda del tuning report tenía el o2_adc_avg de otra celda.
- ecu/session.py: `_load_or_create` asignaba `meta = None` cuando el JSON
  estaba corrupto, causando AttributeError en posteriores `.get()`. Ahora
  inicializa con dict completo para evitar pérdida silenciosa del ride.
- ecu/session.py: `_rebuild_summary` escribía session_metadata.json
  directamente sin atomic write (tmp+rename). Riesgo de corrupción.
- web/server.py: `_get_live_data()` y `_get_live()` leían `ecu_live`,
  `ecu_connected` y `serial_stats` sin adquirir `_data_lock`, creando una
  race condition reader-writer con el IPC reader thread.
- web/server.py: docstring del módulo movido al inicio del archivo
  (estaba después de `import os`, por lo que `__doc__` era None).
- web/server.py: `_get_rides` abría cada CSV huérfano dos veces — la segunda
  sin `with`, dejando file descriptors abiertos temporalmente.
- ecu/logger_process.py: `consecutive_errors` se incrementaba dos veces por
  frame en excepción (una en except, otra en `if data is None`).
- ecu/logger_process.py: hard reconnect no asignaba `ecu.get_version()`
  a `ecu_version`. Burns posteriores usaban versión stale.
- main.py: heartbeats de threads inicializados a `float('inf')` y seteados
  al inicio de cada thread loop para evitar falsos positivos del watchdog.
- main.py: timeout de `_stop_logger_subprocess` aumentado de 5s a 10s
  antes de `os.execv` por memoria crítica.
- ecu/connection.py: `_read_exact` no adquiría `self._lock`, permitiendo
  acceso serial concurrente entre `_send` y `_read`.
- ecu/connection.py: docstring de `_sync_to_soh` movido a posición correcta.
- ecu/protocol.py: type hint de `decode_rt_packet` corregido a `| None`.
### AI
- DeepSeek V4 Flash (codebuff)

**Audited:** PASS - Buffy 2026-06-20 (o2_adc_sum scope fixed, _read_exact under lock, consecutive_errors fix, _data_lock in server.py)
## [v2.7.145] — 2026-06-14
### Added
- GRAF2 annotation `type` field (Phase 2.1): mark modal now has a launch/diagnostic/note selector (default launch); type is persisted and validated server-side against an allow-list, falling back to launch on unknown values (web/handlers/rides.py). Bands are colored by type in the viewer (launch=blue, diagnostic=gray, note=green); legacy annotations without a type render as launch. This is the prerequisite for Phase 2.2, where F7 will consume only `type=launch` marks as a separate PILOT-MARKED category (web/static/graf2.js).
### AI
- Claude Opus 4.8, Anthropic





**Audited:** PASS - Buffy 2026-06-20 (GRAF2 type field launch/diagnostic/note + backend 400 validation)
## [v2.7.144] — 2026-06-14
### Added
- BACKLOG_GRAF2.md: GRAF2 work plan for any AI/session — current state (v2.7.140-143), Phase 2 (annotation `type` field + F7 consuming launch marks as a separate PILOT-MARKED category, option B), Phase 3 (A/B overlay), and validated findings (CLT in °C, WOT +10%, segregate comparisons by fl_wot, signal-gap bug task_052).
### AI
- Claude Fable 5, Anthropic

## [v2.7.143] — 2026-06-14
### Added
- GRAF2 annotation edit/delete: click an existing band (outside mark mode) opens the note for editing or deletion. Backend POST /annotations now updates by id instead of always appending (web/handlers/rides.py).
### AI
- Claude Fable 5, Anthropic

## [v2.7.142] — 2026-06-14
### Added
- GRAF2 region annotations (Phase 1): mark a time span [t0,t1] with a note, persisted on the Pi at sessions/<session>/ride_*_annotations.json for F7 to consume in Phase 2. 🔖 Mark button (2-click start/end), note modal, blue shaded bands drawn across all synced blocks, marks list/delete. Backend: GET/POST /annotations (web/server.py, web/handlers/rides.py).
- GRAF2 Y-axis toggle (Y: full / Y: fit): default fixed to the full-ride range so absolute magnitude is kept on zoom; fit re-scales to the visible window. Lanes and flags were already fixed.
### AI
- Claude Fable 5, Anthropic

## [v2.7.141] — 2026-06-14
### Added
- web/static/graf2.js, web/templates/graf2.html: GRAF2 manual lane stacking. Any analog signal can be sent to its own stacked lane via the ≡ chip toggle (binary flags are always laned). Lanes stack from the bottom, ~20% panel height each (LANE_FRAC, capped at 95% total), auto-scale within their own lane, never overlap, and are labeled left. Persists in localStorage (block.lanes). Replaces the flag-only lane logic with a unified lane model.
### AI
- Claude Fable 5, Anthropic

## [v2.7.140] — 2026-06-14
### Added
- web/templates/graf2.html, web/static/graf2.js, web/static/uPlot.* : new GRAF2 telemetry page (/graf2)
  - uPlot-based; zoom and cursor synced across all blocks
  - flag-state background shading (fl_hot, do_fan, ...) to reveal effects on analog traces
  - logic-analyzer flag lanes: each binary flag in its own stacked lane; analog signals confined above the lane band
  - unified legend chips in the block header: color, name, live value at cursor, click-to-toggle, x-to-remove
  - laptop trackpad gestures: pinch = zoom X, 2-finger horizontal = pan time, 2-finger vertical = page scroll
  - per-block height resize, drag-to-reorder blocks, searchable signal picker, ride list newest-first
- web/handlers/rides.py, web/server.py: /graf2 route + handler
- web/templates/index.html: GRAF2 link in hamburger nav
### Note
- Checkpoint also captures in-progress VDYNO launch (web/vdyno.py, web/handlers/vdyno.py, web/templates/launch_power.html) and sessions_vs work, entangled via shared routes in web/server.py.
### AI
- Claude Fable 5, Anthropic

## [v2.7.139] — 2026-06-13
### Changed
- web/static/app.js: Graf panel gear button (⚙) moved to left of title
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.138] — 2026-06-13
### Added
- web/static/app.js: configurable Graf panels — each panel has ⚙ (signal picker) and × (delete); + Panel button adds new panel; layout persists in localStorage buell_chart_layout_v2
- web/templates/index.html: chartsInner is now empty (panels built by _rebuildDOM); tunePanel moved before chartsOuter
- web/templates/index.html: CSS for .chart-ctrl-btn, .signal-picker, .sig-chip, .picker-item, .picker-swatch, .chart-add-btn
- web/static/app.js: DEFAULT_LAYOUT replaces FIXED_CHARTS (6 panels: DYNAMICS, FUEL, IGNITION, ENVIRONMENT, VDYNO, ALL FLAGS)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.137] — 2026-06-13
### Fixed
- web/static/app.js: add fl_hot band to FUEL fixed panel (see PW vs thermal flag)
- web/static/app.js: add do_fan band to ENVIRONMENT fixed panel (see CLT vs fan activation)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.136] — 2026-06-13
### Added
- web/static/app.js: THERMAL ENRICHMENT preset — CLT+do_fan panel, pw1+pw2+fl_hot panel for thermal enrichment correlation
### Fixed
- web/server.py: /health endpoint version was hardcoded v2.7.132, now uses _get_version()
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.135] — 2026-06-13
### Fixed
- ecu/session.py: translate Spanish log strings to English (watchdog, ride recovery)
- ecu/protocol.py: translate Spanish comment on VSS_CPKM25 constant
- web/vs_engine.py: translate Spanish API error string
- web/launch.py: translate Spanish comment
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.134] — 2026-06-13

### Changed
- sessions_vs: add VDYNO stat cards to fsum (max HP, peak torque N·m, RPM at peak)
  for session A and B, populated after dyno compare loads

## [v2.7.133] — 2026-06-13

### Changed
- Dashboard: 6 fixed permanent chart groups replace preset-based layout
  - DYNAMICS (200px): RPM, KPH, TPS%, Gear + WOT/Decel/Accel flags
  - FUEL (160px): PW1/PW2, WUE, Accel/Decel corrections + fuel flags
  - IGNITION (120px): Spark1/2, VE Curr1/2 RAW
  - ENVIRONMENT (140px): CLT, MAT, Batt V + hot flag
  - VDYNO (140px): HP, Torque N·m, RPM dim + WOT flag
  - ALL FLAGS (140px): full logic-analyzer with 16 flag lanes
- Per-signal fixed y-ranges (no more auto-scale compression)
- Removed preset selector UI (hidden, not deleted)

## [v2.7.132] — 2026-06-13
### Fixed
- /health endpoint added to server.py (was returning 404)
- Spanish strings translated to English (session.py, eeprom_params.py, version_resolver.py)
### AI
- freebuff (audit + implementation)

## [v2.7.131] — 2026-06-13
### Fixed
- install.sh was not reproducible and would build a broken Pi on replication:
  - apt installed python3-serial + python3-flask, but Flask is never imported
    (server uses stdlib http.server) and the real runtime deps (numpy, smbus2,
    bmp280) were missing — a freshly provisioned Pi crashed on import.
  - Malformed POLKIT here-document (escaped-quote delimiters) swallowed the rest
    of the installer as text, so the systemd service, sudoers and enable/restart
    steps never executed on a clean install.
  - Missing udev rule for the stable /dev/ttyECU symlink — a fresh Pi could not
    find the ECU port.
### Added
- requirements.txt with runtime Python deps pinned to the versions validated on
  the production Pi: pyserial==3.5, smbus2==0.4.3, numpy==2.4.4, bmp280==1.0.0.
  install.sh now pip-installs them and deploys 99-ecu-serial.rules.
### AI
- Claude Fable 5, Anthropic

## [v2.7.130] — 2026-06-13
### Fixed
- app.js: the `fetchFuelStatus` 30s poller was never tracked or cleared, so it
  kept hitting /fuel/status while viewing ride history. It now uses a
  `_fuelInterval` handle that is cleared in viewSelectedRides() and restarted in
  exitHistory(), matching the live/freeze/coverage pollers (BACKLOG: JS Robustness).
### AI
- Claude Fable 5, Anthropic

## [v2.7.129] — 2026-06-13
### Removed
- Dead JS function `saveObj()` in web/static/app.js (BL-DI-10): it was defined
  but never referenced from any template or script. Confirmed via the cross-AI
  dead-code audit. `loadObj()`/`objJson` left intact (audit scoped to saveObj only).
### AI
- Claude Fable 5, Anthropic

## [v2.7.128] — 2026-06-13
### Fixed
- Logger version detection was broken: both `_get_version()` in main.py and the
  CSV/metadata version in ecu/session.py matched the `## [vX.Y.Z]` template inside
  the CHANGELOG instruction block, so the startup banner, CLI description, and every
  ride CSV header recorded a placeholder/stale version instead of the real one.
  Both now skip past `PROMPT_END -->` and resolve the live version (v2.7.127).
- ecu/session.py no longer hardcodes `LOGGER_VERSION = "v2.3.0-MODULAR"`; it
  derives the version from CHANGELOG.md the same way main.py does.
### Added
- Per-ride version tracking (BACKLOG: "Version tracking per ride"):
  `logger_version` is stored in session_metadata.json at session creation and
  stamped on every ride start, so logged rides can be correlated with the code
  version that produced them.
### Changed
- ecu/session.py module docstring translated to English + DEV NOTE added;
  Spanish log strings in start_ride translated.
### AI
- Claude Fable 5, Anthropic

## [v2.7.127] — 2026-06-11
### Fixed
- Power-off button: any exception in the pre-poweroff cleanup steps
  (_stop_logger_subprocess / web.stop / network.stop_monitor) aborted
  shutdown() before reaching the poweroff call; the process exited
  non-zero and systemd (Restart=on-failure) resurrected the logger, so
  the Pi never powered off. Every cleanup step is now fenced with its own
  try/except + error log, the poweroff is always attempted (sudo -n) and
  its return code is logged.
### AI
- Claude Fable 5, Anthropic

## [v2.7.126] — 2026-06-11
### Fixed
- 3D GPS track was mirrored vs the real map: the north axis entered the
  projection with inverted sign. Z is now (lat0 - lat) so a top-down 3D
  view matches Leaflet orientation (north up, east right). Validated by
  screenshot comparison against the 2D map (start/end markers and shape).
### AI
- Claude Fable 5, Anthropic

## [v2.7.125] — 2026-06-11
### Added
- BL-M3D-01/02/03 rotating 3D GPS track view in the Mapa subtab, below the
  altitude profile: canvas-only engine (no libraries), GPS converted to
  local meters (cos(lat) equirectangular), speed-colored track line, floor
  shadow, start/end markers, auto vertical exaggeration (~15% of span).
  Auto-rotates 360 deg every 30 s; pointer drag rotates freely (any angle),
  wheel zooms; rotation pauses on interaction, resumes after 4 s idle.
  Renders only while the Mapa pane is active and the tab visible (rAF).
  Bounding-sphere framing keeps the track stable while rotating.
### AI
- Claude Fable 5, Anthropic

## [v2.7.124] — 2026-06-11
### Added
- BACKLOG_MAPA_3D.md, BACKLOG_3D_VIZ.md and BACKLOG_VDYNO.md committed to
  version control — they only existed on the Pi SD card until now. VDYNO
  backlog carries the project north star and the hard design rules
  (no autonomous EEPROM writes, new tune checksum per proposal, noise
  floor before verdicts).
### Notes
- Pi rebooted on its own ~23:26 local; main.py autostarts on boot. Reflog
  has invalid entries from the abrupt reboot (HEAD and objects verified
  fine; GitHub holds full history). Cleanup pending user decision.
### AI
- Claude Fable 5, Anthropic

## [v2.7.123] — 2026-06-11
### Added
- BL-VD-04 Burn ledger (VDYNO phase V0): web/burn_ledger.py records every
  EEPROM burn to burns.json (atomic append) — parent/child tune checksums
  (same md5[327:] identity as session IDs, so child == next session ID),
  exact cell diff, maps touched, verified flag, backup name. Hooked into
  _handle_eeprom_burn after the ECU result; a ledger failure never blocks
  the burn response. The ledger only records — it never writes the ECU.
- GET /burns endpoint (newest first) + "Burn History" section in the VE
  tab (lineage table), refreshed on loadMaps and after each burn.
### Changed
- Chart title tooltip translated to English (repo rule: English only).
### Notes
- Unit-checked locally (tune_checksum, diff_maps, record_burn round-trip).
  On-Pi endpoint/UI validation pending — Pi was offline during this commit;
  validation steps are in docs/11_VDYNO_PLAN.md phase V0.
### AI
- Claude Fable 5, Anthropic

## [v2.7.122] — 2026-06-11
### Added
- docs/11_VDYNO_PLAN.md: step-by-step, model-agnostic implementation plan
  for the VDYNO program (virtual dyno, burn ledger, burn verdict, evidence
  instructor, proposal-to-VE). Phases V0-V4 with file lists, JSON schemas,
  physics constants and per-step validation commands. Hard rules
  documented: no autonomous EEPROM writes ever, new tune checksum per
  proposal, verdicts must beat the measured noise floor.
### AI
- Claude Fable 5, Anthropic

## [v2.7.121] — 2026-06-11
### Added
- TRANSIENTS/ACCEL preset: VSS_RPM_Ratio added next to VS_KPH+Gear so the
  speed/RPM bands make the actual gear readable per ride.
- Chart titles are now clickable and open the signal selector (the gear
  button sits at the right end of the ~6000px scroll-wide title row, i.e.
  off-screen — title click is the reachable trigger).
### Fixed
- Stale closure in the chart gear button: onclick was bound only on the
  first buildCharts pass, so after a ride/preset change the selector kept
  editing the first-load chartCfgs. Handlers now rebind with fresh
  closures on every build.
### AI
- Claude Fable 5, Anthropic

## [v2.7.120] — 2026-06-11
### Fixed
- BL-MAP-01: GPS track segments and start/end markers were added straight to
  the Leaflet map and never removed (_mapPolyline was cleared but never
  assigned), so every ride change stacked the previous tracks. All track
  layers now live in one L.layerGroup (_trackLayer) cleared on each load.
  Verified: layer count resets per ride (858 -> 317 -> 858 on reload).
- BL-MAP-02: track distance ignored cos(lat) on the longitude delta,
  overestimating ~8% at lat 32. New gpsKm() helper (equirectangular with
  cos(lat)) used in the info line and the altitude profile distance axis.
### AI
- Claude Fable 5, Anthropic

## [v2.7.119] — 2026-06-11
### Added
- BL-GRAF-01 Graf chart presets: PRESET selector in the Graf pane with 5
  tuning-oriented signal groups (MIXTURE/PW (OL), TRANSIENTS/ACCEL,
  THERMAL/WARMUP, SPARK, ELECTRICAL/HEALTH) plus DEFAULT and CUSTOM.
  Presets override chart configs in memory only; manual edits via the gear
  button always switch to CUSTOM and persist to buell_chart_cfg_v2.
  Active preset persists in localStorage buell_chart_preset.
  OL compliance: mixture preset uses physical PW + VE raw, not EGO/AFV.
### Fixed
- Chart panel titles were hardcoded in index.html and lied once a preset or
  the gear editor changed the signals — titles now render from the
  configured signal labels on every buildCharts pass.
### AI
- Claude Fable 5, Anthropic

## [v2.7.118] — 2026-06-11
### Added
- BL-3DV-01 Lambert shading on tuner 3D surfaces (BASE/MOD): per-face normal
  vs fixed light direction, double-sided (abs of dot) so faces never flip
  dark while rotating. New shadeRGBA() helper darkens face fill 0.55-1.0.
- Real camera zoom for the 3D row: CAM.zoom scales the whole projection
  (sX/sY/sZ) in drawSurf and drawDelta. New amber ZOOM slider (0.3-2.5) +
  mouse wheel on any 3D canvas.
### Changed
- Former "ZOOM" slider renamed to ALT — it only scales value height (sZ),
  i.e. vertical exaggeration, not camera distance.
### AI
- Claude Fable 5, Anthropic

## [v2.7.117] — 2026-06-11
### Changed
- Tuner 3D zoom control: text input replaced with a range slider (0.1–3.0,
  step 0.05) plus live numeric readout; canvas constrained with
  max-width/max-height to stop overflow of the g3 row.
### Fixed
- Restored fixArrow() — it was removed together with fixArrowZoom() while
  applying the zoom slider patch, but inTps/inRpm/inVal still reference it
  via onkeydown, so arrow keys on the angle inputs threw ReferenceError.
### AI
- Claude Fable 5, Anthropic

## [v2.7.116] — 2026-06-11
### Removed
- Reverted v2.7.115 (commit 0539360) by user decision: PROPOSAL tab, restored
  proposal.py/smoothing.py and the /eeprom/propose endpoint are out again.
  The engine remains recoverable from git history if FASE 6 picks it back up.
  PROPOSAL tab task (020) restored to BACKLOG.md.
### Added
- BACKLOG BL-BUG-03: VS compare OOM on uncached large session pairs
  (found while testing — affects sessions_vs page too, kept despite revert).
### AI
- Claude Fable 5, Anthropic

## [v2.7.115] — 2026-06-11
### Added
- PROPOSAL tab in Tuner page (freebuff task 020): RdBu delta heatmap on canvas
  with Smoothed/Raw/Confidence/Source views, Front/Rear cylinder selector,
  white-dot overlay for interpolated cells, async generate with sessionStorage
  cache keyed by session pair.
### Fixed
- Restored web/proposal.py (378 lines, FASE 6 F7+VS zone-fusion engine) and
  web/smoothing.py (163 lines, IDW + Laplacian) — both were deleted
  undocumented by commit 6270cec (v2.7.64, titled "cleanup stale .bak files",
  changelog only mentions .bak removals). Re-enabled GET /eeprom/propose in
  web/handlers/eeprom.py replacing the 410 deprecated stub. Validated against
  current code: f7.py, vs_engine.py and ecu/eeprom.py signatures unchanged.
  Endpoint tested with 91B225 vs 248AE2: 14/156 cells with signal.
### Known issue
- First-time proposal on a large uncached session pair can OOM the Pi Zero
  (watchdog restarts the logger) — logged as BL-BUG-03.
### AI
- Claude Fable 5, Anthropic

## [v2.7.114] — 2026-06-11
### Fixed
- BL-UX-02 nav audit: hamburger menu on the 5 secondary pages
  (session_events, sessions_vs, sessions_launch, tuner, errorlog_viz) was
  missing the Fuel link — added after Errors. Dashboard and Fuel pages
  already had the complete menu. Cross-page navigation matrix now complete.
### AI
- Claude Fable 5, Anthropic

## [v2.7.113] — 2026-06-11
### Fixed
- Sesiones tab "Ver" button did nothing: viewSelectedRides() read the
  undeclared global _freezeInterval, throwing a silent ReferenceError inside
  the async function before showTab('ride') ran. The tab never switched and
  live polling was left dead (cleared one line earlier). Root cause: commit
  953ee94 moved the freeze-check interval into exitHistory() and dropped the
  top-level declaration. Fix: declare _liveInterval, _freezeInterval and
  _cobertInterval as proper globals in app.js.
### AI
- Claude Fable 5, Anthropic

## [v2.7.112] — 2026-06-10

### Changed
- `main.py`: ECU serial + CSV logging moved to independent subprocess (`ecu/logger_process.py`). Main process now owns sensors, web server, GPS; subprocess owns ECU protocol and ride recording. A crash in web/dash calculations no longer stops CSV logging.
- `ecu/logger_process.py`: new — standalone ECU logger subprocess. Reads sysmon/GPS from IPC files, writes live.json (every 4 frames), cells.json (every 30 frames), ecu_init.json (on ECU connect/post-burn). Handles burn_req.json and control.json commands. Clean SIGTERM shutdown with ride close.
- `ecu/session.py`: `CellTracker.set_snapshot(snap, active)` — replace internal cell state from IPC reader (subprocess architecture). No behavioral change for callers of `snapshot()`.
- `web/handlers/eeprom.py`: `_handle_eeprom_burn` and `_handle_eeprom_revert` now use file IPC (`burn_req.json` / `burn_res.json` with req_id) instead of `threading.Queue`. Eliminates cross-process dependency.
- `web/handlers/system.py`: `_handle_post_close_ride` now writes `control.json` IPC command instead of calling `session.close_current_ride()` directly.
- IPC directory `/tmp/buell` (tmpfs). All writes are atomic (write to `.tmp` then rename).
- BUG-DISC-01 architectural fix: process isolation means a GPS/dash crash can no longer interrupt CSV recording.

### Removed
- `main.py`: `_ecu_loop` method, `DDFI2Connection` import, `pending_burn` queue — all moved to subprocess.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.111] — 2026-06-10

### Changed
- `ecu/protocol.py`: expand `Unk63` into 8 individual bit columns `Unk63_b0`–`Unk63_b7` in `decode_rt_packet` and `CSV_COLUMNS`
- `ecu/protocol.py`: remove `Unk80`, `Unk81`, `Unk82` from `CSV_COLUMNS` — always constant (255/255/62), dead bytes in the RT packet

### Notes
- Detective analysis (389K samples, 132 activation events): Unk63 activates exclusively at WOT + high RPM (avg 5273 RPM, avg TPS 57%, avg 133 km/h). Strongest binary correlator: `di_crank` (61% vs 0.1%). Hypothesis: DDFI2 hard-acceleration / high-RPM injection event flag. All 8 bits nearly always 1 (0xFF) when active; lower bits (b0/b1) are least stable, possibly per-cylinder.

## [v2.7.110] — 2026-06-09

### Changed
- `web/f7.py`: default DTW threshold `_F7_THRESH` 0.75 → 0.85, consistent with UI default
- `web/vs_engine.py`: `_compare_sessions_cached` now deletes stale versions of the same session pair after writing a new cache file
- `ecu/session.py`: removed `_generate_consolidated` method and all 3 call sites — `consolidated.csv` was never read by any code path (all consumers iterate `ride_*.csv` directly)

### Removed
- Deleted 14 stale `sessions_vs_v{4,5,6}` cache files (~8.5 MB)
- Deleted 2 `session_f7clusters_0_75.json` files (~450 KB)
- Deleted 12 `consolidated.csv` + 1 `consolidated.tmp` (~172 MB)
- **Total freed: 181 MB**

## [v2.7.109] — 2026-06-09
### Changed
- Extracted remaining handlers from DashboardHandler into 5 new mixins:
  web/handlers/wifi.py (WifiHandlerMixin) — 8 handlers: wifi GET/POST + network
  web/handlers/gps.py (GpsHandlerMixin) — 2 handlers: gps_fix, gps_track
  web/handlers/tuner.py (TunerHandlerMixin) — 4 handlers: tuner, tuner_sessions, tuner_maps, tuner_merge
  web/handlers/system.py (SystemHandlerMixin) — 6 handlers: shutdown, keepalive, git_pull, close_ride, restart_logger, reboot_pi
  web/handlers/rides.py (RidesHandlerMixin) — 13 handlers: index, live, rides, coverage, csv, ride, errorlog, ride_note, tuning_report, post_ride_note, ride_launch_event
- Fixed silent NameError bug in wifi GET handlers (net was unbound)
- Translated Spanish strings to English in all extracted handlers
- DashboardHandler now owns only: server_instance, _json, _html, do_GET, do_POST, _load_html, _get_live, _handle_static
- server.py: -498 lines
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.108] — 2026-06-09
### Changed
- Extracted 10 EEPROM handlers from DashboardHandler into web/handlers/eeprom.py (EepromHandlerMixin)
- Handlers moved: _handle_suggested_msq, _handle_eeprom_download, _handle_eeprom_msq,
  _handle_eeprom_sessions_list, _handle_eeprom_revert, _handle_eeprom_burn,
  _handle_msq_download, _handle_eeprom_propose, _handle_maps, _handle_eeprom
- Translated Spanish strings to English in extracted handlers
- server.py: -375 lines
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.107] — 2026-06-09
### Changed
- Extracted 8 session handlers from DashboardHandler into web/handlers/sessions.py (SessionsHandlerMixin)
- Handlers moved: _handle_session_events, _handle_session_events_data, _handle_session_events_download,
  _handle_sessions_launch, _handle_sessions_launch_data, _handle_sessions_vs,
  _handle_sessions_vs_compare, _handle_sessions_vs_download
- Translated Spanish error strings to English in extracted handlers
- server.py: -143 lines, DashboardHandler continues toward <20 edges target
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.106] — 2026-06-09
### Changed
- Extracted fuel handlers from DashboardHandler into web/handlers/fuel.py (FuelHandlerMixin)
- Extracted _get_version() to web/utils.py shared module
- Created web/handlers/__init__.py package
- DashboardHandler edges reduced: -5 fuel methods removed from server.py
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.105] — 2026-06-09
### docs
- BACKLOG.md: added REFACTOR — DashboardHandler (betweenness 0.166, extract handlers to web/handlers/)
- BACKLOG.md: added REFACTOR — ecu/ split EEPROM decode from RT decode (Community 1 cohesion 0.09)
- Source: Graphify code-only graph analysis
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.104] — 2026-06-09
### docs
- CLAUDE.md: added Dev tools section — Graphify knowledge graph workflow (runs on Windows, not Pi)
- FREEBUFF.md: added Dev tools section — same context for freebuff agent
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.103] — 2026-06-08

### Added
- `app.js` + `index.html`: added `Accel_Corr` (AE%) to CORRECCIONES COMBUSTIBLE chart
  default series — chart title updated to include `AE`; bumped `LS_KEY` to `v2` so
  browser resets to new defaults on next load

### AI
- Claude Sonnet 4.6

---

## [v2.7.102] — 2026-06-08

### Added
- `fuel.html`: onboarding banner shown when no fill-ups registered — explains the
  4-step activation flow (reserve light → ACTIVATE RESERVE → fill up → FULL TANK RESET);
  auto-hides once the first fill-up is saved
- `app.js` (BL-FUEL-18): reserve-aware color for ~KM widget — when `level_L <= 3.1`
  (XB12X reserve threshold from service manual), both the grid widget B and widget A
  ~KM mode show amber `#e67e22` instead of the normal green/yellow/red km scale;
  reserve amber is visually distinct from the low-km red (<30km)

### Changed
- `BACKLOG.md`: marked BL-FUEL-10 (full tank reset), BL-FUEL-11 (ride consumption),
  BL-FUEL-15 (header fuel bar) as DONE — all implemented in v2.7.83–v2.7.85

### AI
- Claude Sonnet 4.6

---

## [v2.7.101] — 2026-06-08

### Added
- `fuel_tracker.py`: calibration at reserve activation — when reserve light is triggered
  after a full-tank fill-up, the system now compares actual consumed (16.7 - 3.1 = 13.6L,
  both hard facts from service manual) against logger-calculated consumption and adjusts
  `injector_cc_per_ms` with 30% learning rate; ratio clamped to [0.6, 1.67] to prevent
  runaway correction; calibration fields logged to response for audit
- `server.py`: pass `sessions_dir` to `toggle_reserve()` to enable calibration

### AI
- Claude Sonnet 4.6

---

## [v2.7.100] — 2026-06-08

### Fixed
- `fuel_tracker.py`: added 5-min TTL module-level cache for `avg_l100` computation —
  previously `calc_ride_consumption()` read up to 50 JSON files on every `/fuel/status`
  request (~3 req/s across 6 pages); cache invalidated automatically on new ride save

### AI
- Claude Sonnet 4.6

---

## [v2.7.99] — 2026-06-08

### Fixed
- `server.py`: set `daemon_threads = True` on `ThreadingHTTPServer` — request handler
  threads now exit when the request completes instead of accumulating; thread count
  dropped from 42+ to 8 at steady state

### AI
- Claude Sonnet 4.6

---

## [v2.7.98] — 2026-06-07

### Fixed
- `app.js`: broken JS string literal in `buildCobertGrid()` — unclosed quote left by
  previous patch caused entire coverage grid to disappear; merged split style string

---

## [v2.7.97] — 2026-06-07

### Changed
- `app.js`: widget B (grid dead zone) simplified to fixed `~KM` display — removed
  `_WB`, `_wbIdx`, `cycleWidgetB`, `_paintB`; value and color updated directly in
  `fetchFuelStatus()`; cell no longer has onclick

---

## [v2.7.96] — 2026-06-07

### Changed
- `app.js`: `FUEL` label → `GAS` in widget A and B metric arrays
- `app.js`: grid widget B cell HTML — removed `gw-unit` (suffix) and `gw-dots`
  (4 indicator dots); cell now shows only vertical label + big value
- `server.py`: static file `Cache-Control` changed from `max-age=3600` to
  `no-cache, must-revalidate` — browser always loads latest `app.js` after updates

---

## [v2.7.95] — 2026-06-07

### Changed
- `app.js` + `index.html`: widget A long-press replaced with simple tap → shows
  option list overlay; list is locked (shows "LOCK" flash) when `VS_KPH > 0`
- `app.js`: `TANK` label → `TNK` (3-char limit) in both widget A and B arrays
- `app.js`: grid widget B cell reformatted — vertical label (`writing-mode:vertical-rl`)
  on left edge, value centered on right; matches column-header style of coverage grid

---

## [v2.7.94] — 2026-06-07

### Added
- `fuel_tracker.py`: `get_status()` now computes `avg_l100` (weighted avg from rides ≥5km)
  and `km_remaining` (if fuel level is known) — appended to `/fuel/status` JSON response
- `app.js` + `index.html`: RPM big-card replaced with **widget A** — tap to cycle through
  RPM / ~km remaining / fuel L / tank %; selection persisted to localStorage
- `app.js`: TPS=255/175 × RPM=0/800/1000 dead zone in coverage grid replaced with
  **widget B** — tap to cycle through ~km / fuel L / tank % / avg L/100; independent selection
- Both widgets update from `/fuel/status` polled every 30 seconds

## [v2.7.93] — 2026-06-07

### Changed
- `fuel.html`: mobile responsive CSS via `@media (max-width:420px)` — scales fonts,
  padding, and column widths for narrow screens; desktop layout unchanged
- `fuel.html`: removed `white-space:nowrap` from `.sg-stat-val` to allow stat values
  to wrap naturally when cards are narrow

## [v2.7.92] — 2026-06-07
### Changed
- fuel.html: +3px to all font-size values <=14px (CSS + inline)
- index.html: fix nav menu Combustible -> Fuel
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.91] — 2026-06-07
### Changed
- Remove label rows from session stat cards — suffix already carries the unit
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.90] — 2026-06-07
### Changed
- Consumption session header: 4 stat cards (KM / LITERS / KM/L / L/100)
  - 4-column grid replaces 3-column
  - Suffix inline next to value: '1234.5 km', '98.7 L', '12.6 km/L', '7.9 L/100'
  - KM/L card added (calculated as total_km/total_liters per session)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.89] — 2026-06-07
### Changed
- fuel.html design fixes:
  - Replace back-link with hamburger nav menu (consistent with all other pages)
  - Section title: 'Consumption per ride' → 'Consumption by session'
  - Add subtitle 'rides ≥5km · weighted avg' under section title
- BACKLOG BL-FUEL-16: expand with full XB12X maintenance schedule from service manual
  (15 items, intervals, part numbers, notes on short-trip/brake/seal intervals)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.88] — 2026-06-07
### Changed
- BL-FUEL-15: fuel level bar (4px) added to all 6 page headers (index, session_events,
  sessions_launch, sessions_vs, tuner, errorlog_viz) — single fetch on load, green/yellow/red
- BL-FUEL-11 (accordion layout): redesign session header as 2-row layout
  - Row 1: session ID + date + ride count
  - Row 2: 3 stat cards (KM / LITERS / L/100) with label+value — scales to any km/liter values
  - Ride rows: drop inline units (km, L) — column header carries the label
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.87] — 2026-06-07
### Changed
- BL-FUEL-11 (session accordion): replace flat ride list with grouped session accordion
  - Sessions expand/collapse; newest session open by default
  - Session header shows: ID, date, ride count, total km, total liters, L/100 (weighted)
  - Individual ride rows show: ride number, time, km, liters, L/100
  - Color coding per row: green <7, yellow <10, orange <14, red >=14 L/100
- fuel_tracker.calc_ride_consumption: add limit param (default 200) — scales to 1000 rides
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.86] — 2026-06-07
### Changed
- BL-FUEL-11 (cache): add ride_*_consumption.json cache generated at ride close
  - New fuel_tracker._calc_ride_from_csv() extracts CSV parsing; adds duration_s field
  - New fuel_tracker.save_ride_consumption_cache() persists cache atomically
  - calc_ride_consumption() reads from cache first — no CSV scan on fuel page load
  - session.close_current_ride() calls save_ride_consumption_cache() after summary write
  - Backfilled 64 existing rides on deploy
- BL-FUEL-11 (stats): fix weighted average — totals/km ratio instead of mean of ratios
  - Exclude rides <5km from summary stats to avoid warm-up ride skew
- BACKLOG: add BL-FUEL-15 (header fuel bar), BL-FUEL-16 (maintenance indicator), BL-FUEL-17 (EEPROM odometer research)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.84] — 2026-06-07
### Fixed
- web/server.py: _handle_fuel_status, _handle_fuel_refuel, _handle_fuel_consumption — replaced undefined self._sessions_dir with self.server_instance.buell_dir / 'sessions' (bug since v2.7.78)
### Added
- web/templates/fuel.html: Consumption per ride section — summary stats (avg L/100, avg km/L, total km) + per-ride table with date/km/liters/L/100 color-coded by efficiency
- BACKLOG.md: BL-BUG-02 VSS auto-calibration via GPS comparison
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.83] — 2026-06-07
### Added
- web/fuel_tracker.py: full_tank flag in add_refuel() — when set, level resets to 16.7L; discrepancy_L logged (calc_remaining vs actual fill gap); level_override_L stored in refuel entry
- web/server.py: pass full_tank from request body to add_refuel()
- web/templates/fuel.html: FULL TANK RESET toggle in fill-up form; discrepancy shown in history; all UI text in English
- BACKLOG.md: BL-FUEL-10 through BL-FUEL-14 (consumption per ride, discrepancy analysis, odometer, undocumented km)
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-07 (corrected_audit + validation_v2: ZeroDivision x5 FALSE POSITIVE guards confirmed, json.loads 13/13 with try/except, RLock by-design — Claude was correct on all counts)

## [v2.7.82] — 2026-06-07
### Changed
- web/fuel_tracker.py: km pivot is reserve activation — trip_km counts from reserve_ts, survives fill-up, resets only on next reserve activation; add_refuel clears reserve_active but keeps reserve_ts
- web/templates/fuel.html: trip km is now top-level big counter; reserve button pulses when active; gauge shows estimated level from last fill-up; fill-up clears indicator but km keeps counting
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.81] — 2026-06-07
### Added
- web/fuel_tracker.py: level_L, level_pct, km_since_fill, consumed_since_fill computed from last refuel timestamp
- web/templates/fuel.html: fuel gauge bar (green/yellow/orange/red with reserve marker at 18.6%), km counter, better date formatting
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.80] — 2026-06-07
### Changed
- CLAUDE.md: reinforced English-only rule — explicit no-exceptions policy, covers all code/comments/UI/logs, Spanish code encountered must be translated on touch
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.79] — 2026-06-07
### Added
- web/templates/index.html: Combustible link added to hamburger menu (opens /fuel)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.78] — 2026-06-07
### Added
- web/fuel_tracker.py: fuel tracking module (reserve toggle, refuel logging, PW-based consumption estimate, iterative calibration)
- web/server.py: /fuel, /fuel/status, /fuel/reserve, /fuel/refuel endpoints
- web/templates/fuel.html: fuel tracker page (reserve button, fill-up form, history list)
- SPECS: XB12X tank 16.7L, reserve at 3.1L, injector 0.00533 cc/ms
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.77] — 2026-06-07
### Fixed
- ecu/session.py: json.load(session_metadata.json) now has try/except — corrupted metadata no longer crashes open_session()
- web/server.py: json.loads(tuning_report) now has try/except — corrupted report returns 500 instead of crashing handler
### Notes
- freebuff bug_audit_report: Items 1,6 were false positives (already fixed in v2.7.63/65, guards already existed)
- Items 2,4,5 low priority / by design / partially fixed already
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.76] — 2026-06-07
### Changed
- CLAUDE.md: added critical evaluation protocol for freebuff proposals — Claude must verify claims, assess risk, and ask user if anything seems wrong before executing
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.75] — 2026-06-07
### Added
- BACKLOG.md: FASE 8 technical specs confirmed from XB12X service manual
  Injectors: P0026.1AA (front) / P0027.1AA (rear), 12.25 ohm, ~320cc/min, 49-51 PSI
  Tank: 16.7L total, reserve light at 3.1L remaining (13.6L usable)
  Fuel formula: (pw1+pw2) * 0.00533 cc/ms per sample
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.74] — 2026-06-07
### Fixed
- CHANGELOG.md: fixed ordering v2.7.47/48/49 (was 47,49,48 — now 49,48,47 descending)
- CHANGELOG.md: renamed duplicate v2.7.47 (label shortening) to v2.7.47.1
### Added
- freebuff/TASKS.md: task 053 — bike mapping research (which session = which bike, injector specs, odometer)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.73] — 2026-06-07
### Fixed
- main.py: hard reconnect trigger lowered 10s -> 3s (gaps now ~7s worst case vs ~21s before)
- main.py: lost_interval logging interval 10 -> 3 to match new threshold
- ecu/connection.py: get_version() attempts 5 -> 2 (max 4.6s vs 11.5s blocking)
### Research
- BUG-DISC-01 confirmed hardware-specific: 27F1A2 (same Pi/cable) = 3.6% loss, 47BF04 = 60.5%
  Root cause is ECU K-line connector (corrosion/vibration), not software
  Pattern A (auto-reconnect 11s gaps) = 69% of 47BF04 gaps -> now reduced to ~5s
  Pattern B (severe >30s) = hardware failure, needs physical inspection
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.72] — 2026-06-07
### Added
- BACKLOG.md: FASE 8 — Fuel Economy & Reserve Tracking (5 sub-features: reserve signal, km/injector counters, fill-up modal, consumption validation, maintenance tab)
- BACKLOG.md: BUG-DISC-01 updated with freebuff research findings (47BF04=111 gaps/40min lost, 27F1A2=almost clean, USB adapter heat hypothesis)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.71] — 2026-06-07
### Added
- BACKLOG.md: BUG-DISC-01 — ECU disconnection investigation (11.2s gaps during rides)
  Pattern: consistent 11.2-11.4s blackouts across all 47BF04 rides, RPM non-zero, no dirty bytes
  Hypothesis: get_version() 5 attempts x 2.3s = 11.5s blocking the ECU loop
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.70] — 2026-06-07
### Fixed
- web/static/app.js: loadGraphRide title — escapeHtml was applied to datePart (HTML string), causing literal <span style...> visible in UI
- web/static/app.js: flags chart now uses logic-analyzer style (renderFlagsChart) — each flag gets its own vertical band with label, stepped fill
- web/templates/index.html: chartFlags height 130px -> 220px to accommodate 11 flag bands
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.69] — 2026-06-07
### Fixed
- CLAUDE.md: CHANGELOG prepend script now searches after PROMPT_END block — prevents entries from being inserted inside the instruction comment
- freebuff/TASKS.md: added CRITICAL warning — freebuff must never create new version entries, only add audit lines inside existing ones
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.68] — 2026-06-07
### Changed
- web/templates/index.html: app.js cache-buster now uses --LOGGER_VERSION-- (auto-injected, never needs manual update)
- web/templates/index.html: RPM grid headers rotated 90deg, font-size 16px
- web/static/app.js: RPM label format changed from N.N (1.4k) to NN (14, no decimal, no K)
- web/templates/index.html: removed launch-bar (dead code, never activated)
- web/templates/index.html: removed cobert-legend and cobert-status elements
- web/static/app.js: restored hPill blinking dot logic
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.67] — 2026-06-07
### Changed
- web/templates/index.html: mobile optimization via @media (max-width:600px) — header cells flex:1 instead of fixed 60px, hdr padding 10px->4px, big-num 80px->64px
- web/templates/index.html: left padding and gap on .hs/.hs-sm reduced to 2px
- web/templates/index.html: removed cobert-legend and cobert-status elements from ride pane
- web/templates/index.html: moved blinking pill-dot (#hPill) next to freezeIndicator in main header
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.66] — 2026-06-07
### Changed
- BACKLOG.md: closed BL-LOGGER-01 (humidity_pct + gps_alt_m already in CSV_COLUMNS + injected in main.py — confirmed working for new rides)
### Notes
- BUG-B (ZeroDivisionError VSS): false positive — protocol.py:389 already has guard (if vss > 0 and cpkm25 > 0)
- BUG-C (AbortSignal 37 fetch calls): deferred to BL-BUG-01 in BACKLOG
- .bak files (reader.py.bak, index.html.bak.grid, sessions_launch.html.bak): already removed in prior session
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.65] — 2026-06-07
### Fixed
- ecu/connection.py: disconnect() and get_version() now locked with self._lock (prevents serial close/send race during concurrent ECU operations)
### Notes
- BUG-B (ZeroDivisionError VSS): false positive — guard already exists at protocol.py:389 (if vss > 0 and cpkm25 > 0)
- .bak files (gps/reader.py.bak, index.html.bak.grid, sessions_launch.html.bak): already deleted in prior session
### AI
- Claude Sonnet 4.6, Anthropic


## [v2.7.64] — 2026-06-07
### Changed
- BACKLOG.md: closed BL-DDFI2-01 (freebuff research confirms DDFI2 has no KBaro/baro_comp)
- BACKLOG.md: added BL-BUG-01 with 6 low-priority bugs from freebuff audit
### Removed
- web/server.py.bak: stale backup file
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.63] — 2026-06-07
### Fixed
- ecu/connection.py: added threading.RLock — get_rt_data and write_full_eeprom are now mutually exclusive (prevents serial stream corruption during concurrent EEPROM burn)
- tools/health_journal.py: atomic write via tmp+os.replace() — prevents JSON corruption on crash during write
- main.py: OOM restart now closes active ride session before serial disconnect (prevents ride data loss)
### Removed
- connection.py, protocol.py (root): legacy pre-refactor duplicates, never imported, deleted
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.62] — 2026-06-07
### Fixed
- ecu/eeprom_params.py: added 2s complement conversion for size==4 params (was missing, size==2 already had it)
- main.py: call self.ecu.disconnect() before os.execv() in OOM restart — prevents inherited open serial FD
- web/static/app.js: exitHistory() now restarts _cobertInterval (was cleared in viewSelectedRides but never restarted)
### Removed
- add_map_diff.py, _update_cl_v268.py, tools/ecm_bridge.py, tools/test_csv_humidity.py, tools/test_ecu.py, tools/test_write.py
  Orphaned standalone scripts — no imports from anywhere. Logic already covered by ecu/eeprom.py and ecu/connection.py.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.61] — 2026-06-07
### Fixed
- tools/health_journal.py: bare except -> except Exception in check() and get_summary()
### Changed
- CHANGELOG.md: renamed 4 duplicate version entries to .1 suffix (v2.7.16, v2.6.27, v2.6.20, v2.5.44)
### Added
- BACKLOG.md: BL-DOCS-01 README full rewrite task (freebuff readme_gap_analysis 2026-06-07)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.60] — 2026-06-07
### Changed
- web/templates/index.html: values inside 60x33 containers left-aligned (text-align:left)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.59] — 2026-06-07
### Changed
- web/templates/index.html: .hs-val and .hs-sm .hs-val centered (flex:1 + text-align:center)
  Font sizes: hs-val 22→24px, hs-sm .hs-val 18→20px
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.58] — 2026-06-07
### Fixed
- web/server.py: proposal.py import moved from module level to lazy (inside handler)
  numpy + scipy_openblas64 were loading at startup consuming ~180MB RAM
  Now only loads when /eeprom/propose endpoint is called (which has no UI)
  MEM% at startup: 51% (219MB) -> 7.5% (32MB)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.57] — 2026-06-07
### Added
- main.py: memory watchdog in _sysmon_loop — auto-restarts process via os.execv if MEM% > 90%
  Prevents OOM kernel crash (which reboots the Pi) with a clean process restart instead
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.56] — 2026-06-07
### Reverted
- web/templates/index.html: BUELL LOGGER header back to original (14px, no fixed row height)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.55] — 2026-06-07
### Changed
- web/templates/index.html: #hdrLogoRow fixed height 40px, BUELL LOGGER font-size 36px
  Removed JS auto-scaling for logo (was miscalculating)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.54] — 2026-06-07
### Fixed
- web/templates: replaced 'Barlow Condensed' with 'JetBrains Mono' as body font
  index.html, session_events.html, sessions_launch.html — Barlow was declared but never loaded
  JetBrains Mono already loaded via Google Fonts link, now consistent everywhere
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.53] — 2026-06-07
### Changed
- web/templates/index.html: #hdrMain logo text auto-scales to 90% of row height via fitLabels()
  Added id="hdrLogoRow" and id="hdrLogo" for targeting
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.52] — 2026-06-07
### Fixed
- web/templates/index.html: restored hBatChg ⚡ span in BAT cell (removed by mistake in v2.7.50)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.51] — 2026-06-07
### Changed
- web/static/app.js: removed trend arrow (↑↓→) from VLT battery voltage display
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.50] — 2026-06-07
### Changed
- web/templates/index.html: removed charging arrow (hBatChg ⚡) from BAT cell
- .hs .hs-label now shares same 90° rotation CSS as .hs-sm .hs-label
  All three header rows now have uniform vertical labels
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.49] — 2026-06-07
### Changed
- web/templates/index.html: #hdrRowBike cells now have 3-letter labels (EGO/MAT/BAT/GER/RID/SER)
  .hs switched to flex-row matching .hs-sm, labels rotate 90° via fitLabels()
  Font sizes increased: hs-sm .hs-val 13→18px, .hs-val 20→22px
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.48] — 2026-06-07
### Changed
- web/templates/index.html: .hs-sm containers set to 60x33px matching .hs
  All cells in #hdrRowBike, #hdrRowSerial, #hdrRowSensor now uniform size
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.47] — 2026-06-07
### Changed
- web/f7.py: _F7_THRESH lowered 0.85 → 0.75 to reduce orphan rate (estimated 30-40% reduction)
- web/f7.py: _f7_ba_consistent RPM threshold 250 → 400, TPS threshold 3.0 → 5.0 (doubles compatible pairs)
- web/f7.py: _F7_EVENTS_V bumped 5 → 6 to invalidate stale f7events/f7clusters caches
### Fixed
- web/server.py: added logging to 2 silent except Exception blocks (eeprom serial parse + session list loop)
### AI
- freebuff (analysis agent)

## [v2.7.47.1] — 2026-06-07
### Changed
- web/templates/index.html: all dashboard labels shortened to 3 letters
  TTL%→TTL, BUF%→BUF, MEM%→MEM, CPU%→CPU, BARO hPa→BAR,
  AMB°C→AMB, BAT%→BAT, BATV→VLT, TEMP→TMP
- freezeIndicator (正常/OK) moved from hdrRowSensor to #hdrMain next to version
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.46] — 2026-06-07
### Changed
- web/templates/index.html: #hdrRowSerial and #hdrRowSensor labels rotated 90°
  .hs-sm: flex-direction column→row, label on left vertical
  .hs-sm .hs-label: writing-mode vertical-rl + rotate(180deg), no fixed font-size
  fitLabels() extended to auto-scale .hs-label height same as big-card labels
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.45] — 2026-06-07
### Changed
- web/templates/index.html: moved #hdrRowBike, #hdrRowSerial, #hdrRowSensor
  from #hdrMain into #pane-ride (above #bigDisplay)
  Header now shows only logo + nav menu
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.44] — 2026-06-07
### Changed
- web/templates/index.html: dashboard big-card labels auto-scale to card height
  fitLabels() computes font-size = card_height / n_chars × 0.82
  Runs on load (setTimeout 150ms) and on window resize
  CSS: removed fixed font-size:7px from .big-label
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.43] — 2026-06-07
### Changed
- web/templates/index.html: dashboard big-card labels rotated 90° on left side
  Label (CHT/KPH/TPS/RPM) now vertical-left, number font-size 72→80px
  big-card layout: column→row, writing-mode:vertical-rl + rotate(180deg)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.42] — 2026-06-07
### Fixed
- web/f7.py: gps_valid comparison was case-sensitive ('TRUE') but CSV writes 'True'
  gps_alt_avg was always None even when GPS data existed — now fixed
- web/launch.py: same gps_valid case bug fixed
  gps_slope now correctly computed from GPS altitude during Bucket A window
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.41] — 2026-06-07
### Added
- web/f7.py: f7events now include 6 new fields per event
  mat_avg (MAT air temp from ECU), spark_avg (avg spark advance),
  iat_corr_avg (IAT correction), humidity_avg (AHT20, if available),
  gps_alt_avg (GPS altitude, if available), gear_detected (post-ride)
  _F7_EVENTS_V bumped 4→5 — all f7events auto-regenerate on next access
  Cache check updated: missing mat_avg also triggers regeneration
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.40] — 2026-06-07
### Removed
- web/templates/tuner.html: PROPOSAL tab eliminated
  Tab button, propPanel div, generateProposal/renderPropCanvas/renderPropData/propColor JS
  Tab switch logic simplified (no more isProp branch)
  Backend proposal.py and smoothing.py kept for future use
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.39] — 2026-06-07
### Fixed
- web/proposal.py: use eeprom.bin directly instead of requiring eeprom_decoded.json
  eeprom_decoded.json may not exist in older sessions — eeprom.bin is always present
  Falls back to session_b eeprom.bin if session_a is also missing
- CLAUDE.md: data reuse principle + no-new-tab principle documented
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.38] — 2026-06-07
### Fixed
- web/templates/tuner.html: PROPOSAL tab — error responses no longer cached in sessionStorage
  renderPropData now checks d.error before accessing d.smoothed_pct/d.raw
  Prevents Cannot read properties of undefined crash on stale cached error
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.37] — 2026-06-06
### Fixed
- web/proposal.py: zone classification in generate_fuel_proposal() now uses
  f7_tpk (tps_peak of the F7 cluster) instead of the VS cell center TPS
  _compute_f7_delta() now returns 5-tuple including f7_tpk grid
  Edge case: Mid F7 event (tps_peak 40-85%) mapped to low TPS cell no longer
  misclassified as Light — zone uses the real event peak, not cell midpoint
### AI
- Claude Sonnet 4.6, Anthropic
* **Audited:** PASS — freebuff 2026-06-06 (TASK 047: F7 tps_peak zone fusion fix, 2/2 FIXED)

## [v2.7.36] — 2026-06-06
### Added
- web/gear_detect.py: post-ride gear detection from RPM/VSS ratio
  Thresholds from session 248AE2 (96.9% accuracy, confusion only between adjacent gears)
  detect_gear(rpm, vss_kph) returns gear 1-5 or 0 if neutral/uncertain
### Changed
- web/f7.py: _load_csv_rows() adds gear_detected field per row
  Event detection gate, bucket_a gear avg, phase_b consistency check
  all use gear_detected with fallback to ECU Gear field
- web/launch.py: load_csv() adds gear_detected field per row
  _mode_gear() and gear_vals stability check use gear_detected with fallback
- Cache: deleted 89 stale f7events + f7clusters files (regenerate on next access)
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.35] — 2026-06-06
### Fixed
- web/proposal.py: _compute_f7_delta() now uses tps_peak (max from cluster members)
  instead of bucket_a.tps_center for zone classification
  bucket_a.tps_center is pre-WOT stable TPS (~10-15%); tps_peak is actual WOT peak (60-99%)
  Previous: all F7 cells incorrectly landed in Light zone, contributing 0 signal
  Now: F7 cells classified correctly (WOT/Mid/Light) based on real event peak TPS
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (TASK 045: tps_peak zone fix — cells land in correct zone, generate_fuel_proposal OK)

## [v2.7.34] — 2026-06-06
### Added
- web/templates/tuner.html: FASE 5.1 — click-to-edit VE heatmap cells
  - Click any fuel/spark cell → inline input overlay appears
  - Staged cells turn amber; BURN/RESET buttons shown in header bar
  - BURN: POST /eeprom/burn with all staged changes
  - RESET: clears all staged changes
  - Client-side ±15% gate with range feedback
  - Max 20 cells per burn enforced client-side and server-side
- web/server.py: _handle_eeprom_burn — server-side ±15% per-cell gate + max 20 cells limit
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (TASK 044: FASE 5.1 click-to-edit VE — 8/8 checks, STAGE+burn+reset OK)

## [v2.7.33] — 2026-06-06
### Changed
- web/f7.py: _f7_match_cross_session() now returns delta_pw1 and delta_pw2 (front/rear independently)
- web/proposal.py: FASE 6 v2 — added _classify_zone(), _compute_f7_delta(), zone-based F7+VS fusion
  - Zone thresholds: WOT>=85% (VS only), Mid 40-85% (weighted fusion), Light<40% (F7 priority)
  - Rich bias: when F7/VS signals conflict, prefer richer (max) value
  - Summary now includes f7_available flag
### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (FASE 6 v2: zone fusion, 7/7)
**Audited:** PASS — freebuff 2026-06-06 (TASK 042: FASE 6 v2 zone fusion — tps_peak classification correct, OL clean)

## [v2.7.32] — 2026-06-06

### Fixed
- main.py: heartbeat updates now in correct threads (freebuff audit v2.7.30 WARN)
  _ecu_heartbeat updated only in _ecu_loop (not sysmon)
  _sysmon_heartbeat updated only in _sysmon_loop (not ecu)
  Previously both updated in ecu_loop — hung sysmon would never be detected

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (heartbeat thread isolation: _ecu_heartbeat in _ecu_loop, _sysmon_heartbeat in _sysmon_loop)

## [v2.7.31] — 2026-06-06

### Fixed
- web/templates/tuner.html: PROPOSAL tab color scale was using fractional deltas (0.15)
  instead of percentage deltas (15%). Now uses smoothed_pct which has correct units.
  renderPropData(): smoothed mode now reads d.smoothed_pct instead of d.smoothed
  (freebuff audit v2.7.29 WARN caught this)

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (smoothed_pct color scale fix: renderPropData uses d.smoothed_pct with fallback)

## [v2.7.30] — 2026-06-06

### Fixed
- main.py: thread watchdog now detects hung threads via heartbeat timestamps (freebuff task 033)
  _ecu_heartbeat + _sysmon_heartbeat updated each loop iteration
  _check_threads(): stale >10s (ECU) or >15s (sysmon) triggers restart even if thread is alive
  Before ECU restart: self.ecu.ser.close() to avoid zombie file descriptors

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (watchdog heartbeat: _check_threads(), stale limits 10s/15s, serial close)

## [v2.7.29] — 2026-06-06

### Added
- web/templates/tuner.html: PROPOSAL tab — shows fuel delta heatmap from /eeprom/propose
  RdBu diverging color scale (blue=lean, red=rich), dot overlay for interpolated cells
  Dropdown: Fuel Front/Rear, Smoothed/Raw | sessionStorage cache per session pair
  Uses existing Base+Mod session selectors — no new selectors needed

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (PROPOSAL tab UI: tab, panel, canvas, RdBu scale, session cache)

## [v2.7.28] — 2026-06-06

### Fixed
- main.py: voltage shutdown threshold now tiered to match SOC tier (freebuff task 027 audit WARN)
  boot>=30%: v<3.50V | boot 20-29%: v<3.40V | boot 10-19%: v<3.30V | boot<10%: v<3.20V
  _get_shutdown_threshold() now returns (soc_threshold, voltage_threshold) tuple

### Changed
- BACKLOG.md: removed freebuff audit sections (audits belong in responses/, not BACKLOG)

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (tiered voltage threshold)

## [v2.7.27] — 2026-06-06

### Changed
- web/proposal.py: extract _clamp() from nested function to module-level helper
  Signature: _clamp(v, max_delta=MAX_DELTA) — accepts explicit max_delta param
  No behavior change — pure cosmetic cleanup (freebuff task 025 top-3)
- BACKLOG.md: freebuff task 025 audit entries added (PROPOSAL tab, cleanup items)

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (_clamp module-level)

## [v2.7.26] — 2026-06-06

### Added
- main.py: tiered battery shutdown based on boot SOC (freebuff task 027)
  _boot_soc captured once after 3+ stable CW2015 readings
  _get_shutdown_threshold(): boot>=30->30%, boot 20-29->20%, boot 10-19->10%, boot<10->shutdown now
  Watchdog: skips shutdown entirely when bat_charging=True (charger connected)
  Log message includes boot SOC and active threshold for diagnostics

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (tiered shutdown + charging)

## [v2.7.25] — 2026-06-06

### Fixed
- web/launch.py: pw1/pw2 now preserved raw in rows dict; pw1_norm/pw2_norm added as baro-normalized fields
  build_index() cell accumulation uses pw1_norm/pw2_norm for accurate cross-session PW comparison
  detect_launches() series keeps raw pw1 (shows actual ECU pulse width to user)
- web/vs_engine.py: CACHE_VERSION bumped 6→7 to invalidate stale sessions_vs caches

### AI
- Claude Sonnet 4.6, Anthropic

**Audited:** PASS — freebuff 2026-06-06 (pw1_norm 8/8 checks)

## [v2.7.24] — 2026-06-06

### Fixed
- web/launch.py: baro normalization range gate and diagnostic field (freebuff audit task 024)
  Range gate:  →  (matches f7.py spec, rejects sensor faults)
  Added  field to row dict for diagnostics downstream
  Note: pw1 in-place normalization confirmed correct for DTW — detect_launches() uses TPS/RPM
  thresholds, not absolute pw1, so raw pw1 is not needed separately here.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.23] — 2026-06-06

### Changed
- web/templates/*.html (6 files): Replace Share Tech Mono with JetBrains Mono font.
  Added Google Fonts <link> for JetBrains Mono 400/700 weights to every template.
  Share Tech Mono had no bold weight and poor readability at small sizes (freebuff task 023).

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.7.22] — 2026-06-06

### Added
- web/proposal.py: save_proposal() function (freebuff task 022)
  Creates PROP_YYYYMMDD_HHMMSS/ session with session_metadata.json,
  eeprom_decoded.json (proposed fuel maps), eeprom.bin, proposal_metadata.json.
  encode_eeprom_maps() confirmed safe (no checksum, only touches offsets 670-1205).
  Units fix: smoothed deltas passed as percentages (not fractions) to the function.

## [v2.7.21] — 2026-06-06

### Research
- F7 orphan rate post-baro-fix: 97%% -> 96.4%% (no significant change).
  Confirmed: baro fix helps cross-session matching, not within-session clustering.
  Orphan rate is a within-session DTW threshold issue, not baro-related.
- freebuff task 023 queued: frontend typography + font size research.

## [v2.7.20] — 2026-06-06

### Docs
- BACKLOG.md: PROPOSAL tab design from freebuff task 020. RdBu diverging
  color scale, async button trigger, sessionStorage cache, 70-line JS plan.
- freebuff TASKS.md: cleaned — 19 DONE tasks removed, 3 PENDING remain.

## [v2.7.19] — 2026-06-06

### Docs
- freebuff TASKS.md: queued tasks 020-022
  020: proposal heatmap in Tuner page (research + JS snippet)
  021: F7 orphan rate validation script (will baro fix help?)
  022: save_proposal() full implementation + encode_eeprom_maps safety

## [v2.7.18] — 2026-06-06

### Added
- ecu/session.py: rider_notes field in session_metadata (freebuff task 018)
  New sessions initialize with rider_notes: []
  Format: {ride: N, note: normal|knock_heard|hesitation|unknown, ts: ISO}
  Existing sessions: backward compatible via .get('rider_notes', [])

## [v2.7.17] — 2026-06-06

### Fixed
- web/f7.py: baro normalization in _load_csv_rows() (freebuff task 017)
  pw1/pw2 now normalized to 1013.25 hPa. Range gate: 900-1100 hPa.
  baro_valid field added to row dict for downstream diagnostics.
  May reduce 97%% orphan rate in cross-session F7 matching.
  scipy 1.15.3 confirmed available on Pi (task 016).

## [v2.7.16] — 2026-06-06

### Added
- web/proposal.py: smoothing integration (task 014) — IDW + Laplacian applied
  to delta_fuel_front and delta_fuel_rear. Returns both raw and smoothed deltas.
  signal_mask built from source grid (not delta values).

### Docs
- BACKLOG.md: added PROP_* session output spec from freebuff task 015.
  encode_eeprom_maps() in ecu/eeprom.py. Tuner needs session_metadata.json
  (scans sessions/*/session_metadata.json, not eeprom_decoded.json).

## [v2.7.16.1] — 2026-06-06

### Added
- web/proposal.py: smoothing integration — IDW+Laplacian applied to fuel deltas.
  Returns raw + smoothed deltas. scale fix: fractions*100 -> smooth -> /100.
  Result: 17 signal cells, 139 interpolated, propagation working.

### Docs
- BACKLOG.md: PROP_* session output spec (task 015).
  encode_eeprom_maps in ecu/eeprom.py, Tuner needs session_metadata.json.

## [v2.7.15] — 2026-06-06

### Docs
- freebuff TASKS.md: added tasks 016-019 from backlog
  016: scipy check on Pi, 017: F7 baro normalization (HIGH),
  018: rider_notes field in session_metadata, 019: smoothing integration.
  All include exact current code so freebuff can produce matching replacements.

## [v2.7.14] — 2026-06-06

### Docs
- CLAUDE.md: rewrote freebuff consume protocol — DO NOT DELETE response file
  until ALL findings are processed (applied, backlogged, or tasked).
  5-step protocol with explicit VERIFY step before deletion.

## [v2.7.13] — 2026-06-06

### Docs
- BACKLOG.md: added 4 items that were missing from freebuff tasks 007-013:
  F7 baro normalization (HIGH — f7.py has own CSV loader, same fix needed),
  CACHE_VERSION cache key verification (MEDIUM),
  ddvss cross-check for proposal v2 (LOW),
  pw1/pw2 data mismatch edge case in proposal.py (MINOR).

## [v2.7.12] — 2026-06-06

### Docs
- BACKLOG.md: added cleanup items from freebuff task 013 (_clamp outside loop,
  per-cylinder confidence, side-by-side map display).
- freebuff TASKS.md: added task 014 (smoothing integration) and
  task 015 (apply delta to EEPROM + PROP_* session output).

## [v2.7.11] — 2026-06-06

### Added
- web/smoothing.py: IDW interpolation + Laplacian smoother for FASE 6 delta maps.
  Written by freebuff (task 011). numpy only, no scipy required. <2ms on 12x13 grid.

### Docs
- CLAUDE.md: added rule — freebuff findings we can't apply now go to BACKLOG.md
  immediately, with file/change/source reference. Verify code before applying.
- BACKLOG.md: added pw1_norm fix (freebuff tasks 007/008/012) — keep pw1/pw2 raw,
  add pw1_norm/pw2_norm, update Sessions VS to read normalized values.

## [v2.7.10] — 2026-06-06

### Fixed
- web/proposal.py: _find_cell() rewritten with bisect.bisect_right for clarity
- web/proposal.py: front/rear fuel deltas now computed independently
  using pw1/dpw1 for fuel_front and pw2/dpw2 for fuel_rear.
  Session 248AE2 vs 47BF04: rear cylinder shows distinct deltas
  (e.g. rear -3.6% vs front -0.8% at 5000rpm/WOT — expected for V-twin).
  +15% clamp at low TPS confirmed as real map difference, not baro artifact
  (248AE2 has no baro sensor data; delta is only ~0.5% from baro).

## [v2.7.09] — 2026-06-06

### Docs
- BACKLOG.md: consumed freebuff tasks 007-009. Key findings:
  F7 pipeline needs baro normalization (explains 97% orphan rate),
  pw1/pw2 should stay raw + add pw1_norm/pw2_norm for Sessions VS,
  smoothing.py ready to implement (numpy IDW + Laplacian, 50 lines).
- freebuff TASKS.md: added task 011 (write smoothing.py code) and
  task 012 (add pw1_norm to load_csv). First code tasks for freebuff.

## [v2.7.08] — 2026-06-06

### Added
- web/proposal.py: FASE 6 proposal engine v1 — generates per-EEPROM-cell
  fuel delta from Sessions VS dpw_eff. Nearest-neighbor VS bin -> EEPROM cell
  mapping. SWEET/SPICY_WOT flavors only, min 5 samples, +-15% clamp.
  Fuel front and rear proposed independently.
- web/server.py: GET /eeprom/propose?a=SA&b=SB endpoint.

## [v2.7.07] — 2026-06-06

### Docs
- BACKLOG.md: added FASE 6 algorithm section with all freebuff findings
  (tasks 001-006): zone arbitration, confidence formula, smoothing params,
  spark safety rules, baro validation, rider_notes field, EGT suggestion.
- freebuff TASKS.md: added tasks 008 (baro design decision) and 009 (scipy/interpolation).

## [v2.7.06] — 2026-06-06

### Fixed
- web/launch.py: barometric normalization in load_csv() — pw1/pw2 now normalized
  to REF_BARO=1013.25 hPa before computing dpw_eff. Removes ~0.1%/hPa false signal.
  Rows with baro=0 (sensor unavailable) keep raw PW unchanged.
- web/vs_engine.py: bumped CACHE_VERSION 5->6 to invalidate pre-normalization caches.

## [v2.7.05] — 2026-06-06

### Docs
- CLAUDE.md: freebuff loop now mandatory — check responses/ at session start,
  after every commit, and at natural pauses. Proactive reminder protocol.
- BACKLOG.md: added BUG — barometric normalization missing in Sessions VS.
  Critical: 5-7% false signal possible, confirmed by freebuff task 002.

## [v2.7.04] — 2026-06-06

### Docs
- CLAUDE.md: added Freebuff parallel agent workflow — task queue protocol,
  response consumption flow, reminder protocol, code validation task format.
  Updated priority backlog (baro normalization now #1).
- C:/Users/pacda/freebuff/TASKS.md: added code validator role for freebuff,
  task 005 (zone boundaries/orphan confidence), task 006 (baro normalization).

## [v2.7.03] — 2026-06-06

### Docs
- CLAUDE.md: documented OL mode — EGO=100 locked, AFV=100 locked, no WB sensor.
  Valid pipeline: F7 (PW/TPS physical) + Sessions VS (dpw/ddvss physical).
  tuning_report flagged as inactive in OL — generates 0 suggestions by design.
- BACKLOG.md: added OL mode section, WB integration future item,
  tuning_report deprecation note, unified proposal pipeline spec.

## [v2.7.02] — 2026-06-06

### Changed
- Nav menu: normalized names and ordered by pipeline step on all pages
  Order: Session Events → Sessions VS → Launch → Tuner → Errors
  Renamed: 'Tuner Studio' → 'Tuner', 'Errores' → 'Errors' (English),
           'VS'/'Events' → 'Sessions VS'/'Session Events' (full names)

## [v2.7.01] — 2026-06-06

### Refactor
- web/vs_engine.py: extracted Sessions VS engine from server.py (~194 lines)
  _maps_differ, _merge_maps, _fmtk, CACHE_VERSION, _cache_lock,
  _eeprom_to_msq, _compare_sessions_cached
  server.py: 1545 -> ~1355 lines

## [v2.7.00] — 2026-06-06

### Fixed
- web/launch.py: dead code after  in  — same-map detection
  and FASE7 cross-session matching block were unreachable. Converted  to
  , moved both blocks before the final .
  Sessions VS and Sessions Launch now include  and  in response.

### Docs
- CLAUDE.md: added commit workflow rule — CHANGELOG must be updated before /,
  not after. All changed files (including CHANGELOG.md) go in the same commit.

## [v2.6.99] — 2026-06-06

### Refactor
- web/launch.py: extracted launch analysis from server.py (~570 lines)
  detect_launches, _s_std, cluster_launches, match_clusters, _compare_sessions
  server.py: 2109 → 1545 lines
  Validated: /sessions_launch/data returns 49+20 clusters, 5 matches
             /sessions_vs/compare returns 109 delta rows

## [v2.6.98] — 2026-06-06

### Refactor
- web/f7.py: extracted FASE7 block from server.py (~669 lines)
  server.py: 2770 → 2109 lines. Validated: /session_events/data returns 66 clusters.

## [v2.6.97] — 2026-06-06

### Changed
- web/templates: added DEV NOTE English-only header to sessions_vs, sessions_launch,
  session_events, tuner, errorlog_viz — incremental AI agent coding standard rollout
- BACKLOG.md: added AI Agent Header Note rule (incremental, touch-triggered)
- BACKLOG.md: added 7.7 events-compete-directly comparison and 7.8 launch→f7 migration

## [v2.6.96] — 2026-06-06

### Changed
- web/templates: replaced flat hdr-nav links with hamburger dropdown (☰) on all
  pages (sessions_vs, sessions_launch, session_events, tuner, errorlog_viz) — 
  navigation is now identical across every page (UX backlog item)

## [v2.6.95] — 2026-06-06

### Fixed
- web/server.py: CACHE_VERSION bumped 4→5 — invalidates Sessions VS caches
  predating FASE7 integration; f7_matches now included in cached result (7.4.5)

### Removed
- web/static/app.js: deleted 10 dead functions with no callers or HTML bindings:
  handleMsqDrop, handleMsqFile, parseMsq (MSQ drag-drop, never wired),
  markerSet (scatter helper), extractTransitions, detectGearChanges,
  detectWOT, detectDTC, doKeepalive, toggleEcu + ecuPanelOpen variable

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.94] — 2026-06-06

### Docs
- BACKLOG.md: removed completed items — 7.4.1/_f7_match_cross_session,
  7.4.2/_compare_sessions integration, 7.4.3 event struct improvements,
  7.2 GPS slope, UPS-Lite battery gradient (all documented in v2.6.92/v2.6.93)
- Remaining 7.4 pending: 7.4.4 env_warning in matches, 7.4.5 cross-session cache

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.93] — 2026-06-06

### Fixed
- web/server.py: _compare_sessions() was returning None — FASE7 integration
  appended code after result dict but omitted the return statement; Sessions VS
  and Launch Analysis were silently broken (returned null to frontend)
- web/server.py: /session_events/download route not registered in _routes dict
  — handler existed but button returned 404 on every click

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.92] — 2026-06-06

### Added
- web/server.py: _f7_match_cross_session() — cross-session cluster matching
  using TPS-curve DTW (not PW DTW; rider gesture is common input, PW difference
  is the signal). Bucket A compatibility: gear exact, RPM±300, TPS±5%, VSS±15kph.
  Computes delta_pw[t], delta_vss[t], conf_match[t], efficiency_delta, balance_shift.
  Sorts by confidence-weighted score (avg_conf × tps_dtw × min(n_a, n_b)).
- web/server.py: FASE7 integrated into _compare_sessions() — result now includes
  f7_session_a, f7_session_b, f7_matches, f7_n_matches. Failure is non-fatal.
- web/server.py: same_map detection in _compare_sessions() — compares eeprom.bin
  bytes; sets result['same_map']=True when sessions share identical map

### Changed
- web/server.py: _F7_EVENTS_V bumped to 4 — event struct extended with:
  tps_curve_norm [0,1] including 3 Phase A tail samples + Phase B (captures
  gesture start for cross-session DTW; edge case max(tps)==0 returns [0]*N);
  gps_slope computed from stable window GPS altitude;
  baro_hpa, temp_amb_c (baro_temp_c), clt_avg, gps_slope added to each event
- web/server.py: _load_csv_rows in _f7_load_session_clusters now reads
  gps_alt_m, gps_valid, baro_temp_c from CSV

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.91] — 2026-06-05

### Added
- DESIGN.md: project design system added to repo root — complete token set
  (CSS variables --bg/--p/--bd/--ac/--a2/--bl/--gn/--dm/--tx/--rd/--mn),
  typography scale (7/8/9/10/11/13/14px only), component rules for header,
  controls bar, chip strip, badge, cond-box, canvas chart, metric toggles,
  members table; anti-patterns and QA checklist per page. Based on mono
  design skill (typeui.sh) extended with project-specific tokens.
- ECC web-design rules: mono SKILL.md installed at ~/.claude/skills/mono.md
  for automatic design consistency in future frontend work

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.90] — 2026-06-04

### Docs
- BACKLOG.md: FASE7 section updated — marked 7.1/7.2/7.3/7.6 as complete,
  documented all implemented items, added pending 7.4 (cross-session) and 7.5 (live)
- ECC coding-style.md: added Language — English Only rule: all touched code,
  comments, UI text, and frontend strings must be written in English; Spanish
  code is rewritten to English when modified (incremental cleanup, not mass refactor)
- ECC git-workflow.md: added Commit Order section — CHANGELOG must be updated
  before committing; changelog entry and code change go in the same commit

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.89] — 2026-06-04

### Fixed
- web/server.py: implement _f7_ba_consistent() and _f7_sub_divide_by_bucket_a()
  — after complete-linkage DTW clustering, each cluster is sub-divided by Bucket A
  consistency: gear exact, RPM ±250, TPS ±3%, VSS ±10 km/h. Three levels:
  (1) gear + 200-RPM bucket, (2) 10 km/h VSS bucket, (3) 3%-TPS bucket.
  Root cause: cluster with apparent gear=4a (vss=54/98/98 kph) was an averaging
  artefact — (2+5+5)/3 = 4.0. Sub-division reveals true gears and separates the
  misdetected 2a@54kph orphan from the valid 5a@97-98kph pair (ba_ok=True for both).
  Physical rationale: Alpha-N means PW=f(TPS,RPM); same RPM at 54 vs 98 kph in the
  same gear is physically impossible — VSS must be included as a grouping criterion.
- web/server.py: restored threshold-specific cluster cache filename
  (session_f7clusters_0_85.json) that was lost in a previous fix script

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.88] — 2026-06-04

### Added
- web/server.py + session_events.html: accel/decel event type segregation
  — _f7_detect_events detects TPS break direction (rising=accel, falling=decel);
  PW-rise filter only applied to accel events; accel and decel clustered
  independently (A001/D001 cluster IDs); result JSON includes n_accel/n_decel counts
- session_events.html: type filter bar (ALL / ACCEL / DECEL) above cluster strip;
  status bar shows per-type counts (e.g. 50↑ 34↓); filtering is frontend-only
  so no recomputation needed
- web/server.py: threshold-specific cluster cache files (session_f7clusters_0_85.json);
  switching thresholds uses separate cached JSON without recomputation
- web/server.py + session_events.html: /session_events/download endpoint returns
  full cluster JSON as attachment; download button appears after load
- web/server.py: _F7_EVENTS_V version guard — stale event caches (missing
  pre_pw_curve or newer struct fields) are automatically invalidated and recomputed

### Fixed
- session_events.html: filter change now hides chart when selected cluster is
  not in new filter (previously showed stale chart data after type switch)
- session_events.html: active chip highlight now uses cluster_id instead of
  positional index — no more wrong chip lighting up after strip rebuild on filter change
- web/server.py: _safe_pre in _f7_temporal_stats removed redundant numpy re-import
  (used _np2 when _np was already in scope)
- _F7_EVENTS_V bumped to 3 to invalidate event caches missing pre_*_curve fields

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.87] — 2026-06-04

### Added
- web/server.py + session_events.html: pre-break time series in Session Events chart
  — _f7_detect_events now stores pre_pw/rpm/vss/tps_curve (10-point resample of the
  3s stable window before the break); _f7_temporal_stats computes pre_*_avg across
  cluster members; chart left zone (BUCKET A) now shows actual time series curves
  instead of flat reference lines, matching Launch Analysis visual style
- session_events.html: full layout rewrite — horizontal chip strip replaces vertical
  sidebar, chart fills full width, two cond-boxes at bottom (BUCKET A initial
  conditions + BUCKET B event outcomes)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.86] — 2026-06-04

### Fixed
- web/server.py: _f7_detect_events — truncate event when any sample has PW < 2.0ms
  (fuel injector off / fuel cut not caught by fl_fc flag); truncate when PW drops
  >35% below event peak for 2+ consecutive samples (captures clean acceleration
  phase only, prevents post-peak deceleration from contaminating the curve)
- web/server.py: _f7_detect_events — removed vss_d < 0 acceleration filter (unreliable
  after truncation since VSS may not have time to build)
- web/server.py: _f7_cluster — replaced Union-Find (single-linkage, allows transitive
  chaining) with agglomerative complete-linkage: a cluster only forms/grows when ALL
  cross-pair DTW scores >= threshold. Prevents super-clusters where DTW min was 0.282
  but events were grouped by transitivity. Result: DTW min 0.282→0.849, max cluster
  size 38→10, detected events 60→84 (shorter clean events now survive)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.85] — 2026-06-04

### Fixed
- main.py: battery charging indicator (⚡) was always shown regardless of charger
  state because the CW2015 CHG_IND bit (STATUS register bit 4) is stuck high on
  this UPS-Lite hardware — reverted to voltage trend + hysteresis approach from
  v2.6.82. Detection: rising >0.005V over 2-read window → charging, falling
  <-0.005V → not charging, stable → keep previous state (hysteresis). Fallback
  for <3 readings: voltage > 3.85V assumes charging. Removed duplicate bat_trend
  block that was overwriting the trend arrow computed in the charging logic.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.84] — 2026-06-04

### Fixed
- main.py: battery charging indicator (⚡) was always False because the voltage
  trend approach fails in CV phase (battery near full, voltage barely changes).
  Replaced with direct CW2015 CHG_IND bit (STATUS register bit 4) with a
  3-read majority debounce. Previous CHANGELOG note about CHG_IND "always being 1"
  was incorrect — the bit correctly reflects USB power connection state.
  Voltage trend is now used only for the ↑↓→ arrow in the BATV display.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.83] — 2026-06-04

### Fixed
- web/server.py: _f7_load_session_clusters cluster cache was not invalidated when
  DTW threshold changed — any threshold different from the cached one now triggers
  full recomputation instead of returning stale results
- main.py: battery charging detection threshold raised to 0.015V and window
  extended to 10 readings (~5s) to reduce false positives on stable voltage

### Added
- web/templates/session_events.html: session dropdown now uses /tuner/sessions
  endpoint (same as Sessions VS), showing id #serial date rides/samples
- web/templates/session_events.html: per-event dashed lines in Bucket A zone of
  the chart showing each cluster member's individual starting conditions
  (pw_start, rpm_avg, vss_avg, tps_avg) — makes pre-event context visible
  when comparing event curves
- web/templates/sessions_vs.html: added Events nav link
- web/templates/sessions_launch.html: added Events nav link
- web/templates/index.html: added Session Events link to hamburger menu

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.82] — 2026-06-02

### Fixed
- web/templates/index.html + web/static/app.js: lightning bolt indicator (⚡) was
  invisible because JavaScript textContent replaced the entire element tree, destroying
  the ⚡ span. Fixed by isolating BAT%% value in its own <span id="hBatPctVal">.
- sensors/cw2015.py: added STATUS register (0x08) CHG_IND bit 4 read, but the bit
  always returns 1 on UPS-Lite v1.3 hardware — not usable for charging detection.

### Changed
- main.py: charging detection reverted from CW2015 CHG_IND to voltage trend with
  hysteresis. Threshold lowered from 0.008V to 0.005V over ~1s window.
  Stable voltage keeps previous state (up↑ = charging, down↓ = not charging).

### AI
- Codebuff (DeepSeek V4 Flash)

## [v2.6.81] — 2026-06-02

### Added
- main.py: low battery watchdog — graceful shutdown when SOC < 30%% or V < 3.50V
  to prevent sudden power loss and protect LiPo battery
- web/templates/index.html: BAT%% and BATV indicators with color gradient
- sensors/cw2015.py: CW2015 driver for UPS-Lite v1.3 battery fuel gauge

### Changed
- main.py: battery watchdog thresholds raised from 5%%/3.15V to 30%%/3.50V
- web/static/app.js: battery color uses HSL interpolation (red 0%% -> green 100%%)
- web/static/app.js: hs-val class preserved for layout consistency

### Fixed
- main.py: SMBus creation condition now includes _CW2015_OK
- main.py: CW2015 uses its own SMBus(1) bus (was sharing i2c-2 with BMP/AHT)
- web/static/app.js: restored missing hs-val className on battery elements

### AI
- Codebuff (DeepSeek V4 Flash)


## [v2.6.80] — 2026-06-02

### Added
- sensors/cw2015.py: new CW2015 driver for UPS-Lite v1.3 battery fuel gauge
  at I2C address 0x62 (VCELL voltage + SOC percentage)
- main.py: CW2015 integration — import, shared SMBus init, bat_voltage/bat_soc
  reading in _sysmon_loop, data injection into ecu_loop
- web/server.py: bat_voltage and bat_soc added to serial_stats
- web/templates/index.html: BAT%% and BATV indicators in header row
- web/static/app.js: live battery display with voltage and percentage

### Changed
- Identified mystery I2C device at 0x62 as UPS-Lite v1.3 (CW2015 fuel gauge)
  for Raspberry Pi battery backup monitoring

### AI
- Codebuff (DeepSeek V4 Flash)

## [v2.6.79] — 2026-06-02

### Added
- web/templates/index.html: HUM% indicator added to header row, to the right of AMB°C
- web/static/app.js: live humidity display with 1 decimal, updated via serial_stats.humidity_pct
- web/server.py: humidity_pct added to default serial_stats dict
- BACKLOG.md: FASE 7 task for AHT20 vs BMP280 temperature comparison

### Changed
- web/static/app.js: humidity display precision from 0 to 1 decimal

### AI
- Codebuff (DeepSeek V4 Flash)

## [v2.6.78] — 2026-06-02

### Added
- sensors/aht20.py: new AHT20 humidity + temperature sensor driver using smbus2
  with i2c_rdwr for raw I2C reads (fixes corrupt humidity data from command byte)
- main.py: AHT20 integration — import, shared SMBus initialization, humidity_pct
  reading in _sysmon_loop, data injection into ecu_loop
- ecu/protocol.py, protocol.py: humidity_pct added to CSV_COLUMNS for CSV logging

### Fixed
- Humidity reading was stuck at 0.0%% — root cause: driver used smbus2
  read_i2c_block_data which sends a command byte before reading, corrupting
  the humidity bytes. Fixed by switching to i2c_rdwr (raw I2C read).

The AHT20 sensor had no code at all — humidity data was completely missing from
both the live dashboard and CSV logs. Now fully functional.

### AI
- Codebuff (DeepSeek V4 Flash)


## [v2.6.77] — 2026-06-01

### Fixed
- web/static/app.js: ride date displayed as unreadable "2605231741" — added
  separators to format as "YY/MM/DD HH:mm" (e.g. "26/05/23 17:41")

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.76] — 2026-06-01

### Fixed
- web/static/app.js: restored missing file — static/ directory had been deleted,
  causing header to show no live sensor values (baro, temp, CPU, GPS)
- web/templates/sessions_vs.html: restored missing file — sessions_vs returned 500
- CHANGELOG.md, connection.py: restored files deleted from working tree
- web/server.py: add 5s cache for _get_rides() to reduce CSV reads on every request;
  invalidate cache on ride close

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.75] — 2026-05-31

### Fixed
- web/templates/sessions_vs.html: Session A dropdown was empty due to escapeHtml()
  applied to innerHTML — HTML option tags were being escaped to literal text instead
  of rendered as options. Session B was unaffected. One-line fix.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.74] — 2026-05-31

### Added

- web/server.py: GET /eeprom/sessions-list — returns sessions with eeprom.bin sorted by date,
  with ride count and current session indicator
- web/server.py: POST /eeprom/revert — burns a previous session's eeprom.bin to ECU,
  saves backup before write, returns {written, verified, reverted_to}
- web/static/app.js: loadEepromSessions() + revertToSession() — UI in VE tab to list
  all sessions and revert to any previous EEPROM with one click
- web/templates/index.html: Revert EEPROM section in VE tab with session list and refresh button

### Fixed

- main.py: post-burn session reload now uses verified `proposed` bytes instead of re-reading
  EEPROM from ECU — eliminates a 3rd serial read that was delaying the ECU loop by 26s
- main.py: result_q.put() moved before post-burn reload so HTTP handler responds immediately
  instead of timing out while waiting for session consolidation
- web/server.py: revert timeout increased from 30s to 90s for sessions with many differing bytes
- web/server.py: accept {changes:[{map,ri,ci,val}]} AND {maps:{...}} in burn endpoint

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.73] — 2026-05-31

### Fixed

- web/static/app.js: stale data bug — burn now sends only staged cell changes
  instead of full map tables; server applies changes to current EEPROM from disk,
  eliminating collateral writes from stale _mapsData
- web/static/app.js: removed 50%/15% hard block and confirm gates in stageChange;
  any value accepted without blocking (enables small absolute changes like 1°→2°)
- web/static/app.js: post-burn auto-reload of VE map — 1.5s delay after verified burn
  then loadMaps() is called automatically, shows 'Actualizando mapa...' status
- web/server.py: POST /eeprom/burn now accepts {changes:[{map,ri,ci,val}]} format
  in addition to {maps:{...}} for cell-level burns without full table
- web/server.py: removed BURN_RECV debug logging (was temporary diagnostic)
- main.py: post-burn EEPROM reload — after successful write_full_eeprom, ECU loop
  re-reads EEPROM, updates session and web state immediately without service restart
- ecu/session.py / main.py: eeprom.bin always saved on session open (not only on
  first create), so /maps always serves current ECU state after reconnect

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.72] -- 2026-05-31

### Added

- ecu/eeprom.py: encode_eeprom_maps(eeprom_bytes, maps) -- inverse of decode_eeprom_maps
  writes fuel (scale 1.0, stride cols+1) and spark (scale 0.25, dense) back to EEPROM bytes
  round-trip lossless confirmed for full safe zone (670-1205)
- main.py: pending_burn hook in ECU loop -- executes write_full_eeprom() between RT reads
  only fires when no ride is active, queues result back to server via queue.Queue
- web/server.py: POST /eeprom/burn endpoint
  accepts {maps: {fuel_front, fuel_rear, spark_front, spark_rear}}
  saves eeprom_backup_TIMESTAMP.bin before burn, returns {written, verified, backup}
- web/templates/index.html: Edit mode toggle button + staged changes toolbar in VE tab
- web/static/app.js: full staging system for map cell edits
  editCell() floating input, stageChange() with +-15%% safety gate,
  burnStaged() POST to /eeprom/burn, discardChanges(), updateEditToolbar()
  staged cells shown in yellow with original value as subscript

### Fixed

- ecu/eeprom.py: _validate_eeprom() had wrong offset assumptions (offset 4 as
  Manufacturing Day when it is Rides-since-Error). Now checks serial (12-13),
  year (9), system config (8), fuel axis (632). Maps now load from session files.

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.71] -- 2026-05-31

### Added

- ecu/connection.py: CMD_SET = 0x57 constant (confirmed write command)
- ecu/connection.py: write_eeprom_page(page_nr, offset, data) -> bool
  payload format [CMD_SET, offset, page, data...] no length field
- ecu/connection.py: write_full_eeprom(proposed, safe_start=670, safe_end=1205)
  BurnDiffs approach: read current -> diff in safe zone -> write chunks -> verify
  groups consecutive diffs into chunks (max 16 bytes, gap <= 4 bytes merged)
  never touches offsets 0-669 (DTC/factory/config area)
- BACKLOG.md: FASE 5 -- VE subtab as full EcmSpy replacement
  5.1 fuel/spark map editor with staged changes + burn button
  5.2 full configuration parameters editor (238 named params from BUEIB.xml)
  5.3 AI-assisted parameter suggestions via structured JSON export

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.70] -- 2026-05-31

### Added

- docs/10_DDFI2_PROTOCOL.md: section 11 -- EEPROM safe write zones
  offsets 0-669 are DTC/factory/config (never write), 670-1205 are maps (safe)
  documents how accidental DTC write was discovered and corrected
  explains why EcmSpy BurnDiffs avoids the problem and how Pi must replicate it

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.69] -- 2026-05-31

### Added

- docs/10_DDFI2_PROTOCOL.md: complete protocol reference for DDFI2 serial + EEPROM burn
  covers PDU frame structure, CMD_GET (0x52) read, CMD_SET (0x57) write (confirmed today),
  EEPROM page layout, XPR file format, MSQ format, EcmSpy BurnDiffs strategy,
  planned Pi burn workflow, and test history with dates and outcomes
- tools/ecm_bridge.py: TCP-serial bridge for protocol monitoring (EcmSpy MITM)
- tools/test_write.py: DDFI2 write protocol validation script

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.68] -- 2026-05-30

### Fixed

- web/server.py _handle_eeprom_msq(): fallback to eeprom.bin when eeprom_decoded.json
  is absent -- only 1 of 22 sessions had eeprom_decoded.json, all others failed with 500
  now decodes eeprom.bin on-the-fly via decode_eeprom_maps() for any session

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.67] -- 2026-05-30

### Fixed

- web/static/app.js: downloadMsq() now reads filename from Content-Disposition header
  so downloaded file is named eeprom_CHECKSUM.msq instead of eeprom_current.msq

### Added

- web/templates/tuner.html: MSQ download buttons next to Base and Modificada selectors
  dlMsq('sB') / dlMsq('sM') call /eeprom/msq?session=X for the selected session
- BACKLOG.md: FASE 4 -- data-driven tune recommendation pipeline documented
  covers cell coverage thresholds, AE/EGO correlation, launch attribution,
  recommendation report, MSQ export and VE heatmap overlay

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.66] -- 2026-05-30

### Added

- web/server.py: _eeprom_to_msq() module-level helper -- serializes eeprom_decoded.json
  to MSQ XML (EcmSpy format) without applying any tuning modifications
- web/server.py: GET /eeprom/msq?session=X endpoint -- generates and serves MSQ from
  eeprom_decoded.json; defaults to active session or most recent if no session param

### Fixed

- web/static/app.js: downloadMsq() now calls /eeprom/msq instead of /msq/download
  previous endpoint required suggested_SESSION.msq which almost never existed
- web/static/app.js: _mapsSession tracks which session is loaded in VE tab
  so MSQ download uses the correct session without needing an explicit param
- web/templates/index.html: MSQ button tooltip corrected

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.65] -- 2026-05-30

### Fixed

- web/server.py: _cache_lock = threading.Lock() was missing at module level
  caused NameError on every /sessions_launch/data request -> 500 error

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.64] -- 2026-05-30

### Changed

- web/server.py match_clusters(): distance formula unified to Euclidean (was Manhattan dr+ds+dt)
  matching now uses (dr**2+ds**2+dt**2)**0.5 < 1.5, same geometry as cluster_launches
- web/server.py cluster_launches(): added comment documenting intentional no-leakage design
  outcome metrics excluded from clustering to avoid grouping bias
- web/templates/sessions_launch.html: similarity score labeled 'sim X.XX' in pair chips
  to distinguish condition similarity from performance score
- web/templates/sessions_launch.html: efficiency score added to delta row
  Eff(spd/PW) = spd_gain / peak_pw in km/h per ms, with % delta B vs A
  note: valid when CLT is comparable between sessions
- web/templates/sessions_launch.html: +RPM and +Spd in conditions box now show sigma
  showing repeatability of the launch outcome across events in the cluster

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.63] -- 2026-05-30

### Changed

- web/templates/sessions_launch.html: session selectors now use <optgroup> grouped by bike serial
  - sessions sorted by date within each group, label shows id + date + ride count
  - groups sorted numerically by serial (#235, #651); unknown serials last

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.62] -- 2026-05-30

### Changed

- web/templates/sessions_launch.html: layout redesign — chart is now the protagonist
  - body fills viewport (height:100dvh, overflow:hidden); chart-area flex:1 takes all remaining space
  - pairs list replaced by horizontal scrollable chip strip above the chart
  - metric toggles moved to compact toolbar above the canvas
  - canvas sizing bug fixed: chart-area shown before drawChart() so canvas.offsetWidth is not 0
  - std deviation bands removed; A series solid 2.5px, B series dashed 1.8px at 72% alpha
  - Y-axis reduced to label + min/max only (no tick clutter)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.61] -- 2026-05-30

### Added

- web/server.py detect_launches(): GPS altitude (alt) added to event time series
- web/server.py cluster_launches(): alt added to mean_series and std_series fields
- web/templates/sessions_launch.html: Alt m metric added to chart (color #84cc16) for GPS altitude profile -- allows comparing slope/gradient between sessions
- web/templates/sessions_launch.html: chart height now responsive -- 240px mobile, up to 52% viewport height on desktop (max 520px), redraws on window resize

### Changed

- web/server.py: CACHE_VERSION bumped 3->4 (alt field added to schema)

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.60] -- 2026-05-30

### Changed

- web/templates/sessions_launch.html: chart redesigned with distributed multi-axis system. All 5 metrics (RPM, km/h, PW ms, TPS%, AE%) shown simultaneously in one chart. Each active metric gets its own Y axis positioned at equal intervals horizontally within the plot area -- axis line is subtle (18% opacity), ticks and labels in the metric color. Toggle buttons to enable/disable each metric independently (minimum 1 active). Session A = solid line, Session B = dashed line, same color per metric. Std band shown as fill.

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.59] -- 2026-05-30

### Changed

- web/templates/sessions_launch.html: complete rewrite (861->448 lines). New UX: auto-matched pairs shown as a list (no manual cluster selection), single click to compare, chart shows mean curves A and B with std shading, metric selector (RPM/Speed/PW), conditions table A vs B with deltas. Removed: cluster tables, mean/std tables, redundant chart toggles.
- web/server.py: _compare_sessions_cached() versioned (CACHE_VERSION=3) -- cache invalidated when detect_launches or cluster_launches schema changes. Cache key now includes version prefix.
- web/server.py: result stamped with _cache_version before saving, validated on load.

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.58] -- 2026-05-30

### Changed

- web/server.py detect_launches(): min_dtps lowered 15.0->8.0 to capture smoother throttle openings; gear now taken from pre-window mode (not launch sample) and event discarded if gear=0 or changed during pre-window; adds environmental metadata: pre_clt, pre_alt_m, pre_baro_hpa; adds gear_stable flag
- web/server.py cluster_launches(): speed removed as clustering dimension (follows from gear+RPM by physics); rpm_tol tightened 400->250; distance metric changed from sum to Euclidean; 2-pass k-means style (assign, recompute centroids, reassign); adds clt/alt/baro metadata aggregation to clusters
- web/static/app.js checkBaseConditions(): added Gear > 0 requirement (gear must be confirmed before accumulating)
- web/static/app.js ACCUMULATING state: added bufferGearStable() check -- resets to INACTIVE if gear changes during pre-window

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.57] — 2026-05-30

### Added

- ecu/protocol.py: VSSCalibrator class — IIR auto-calibration of VSS_CPKM25 against GPS speed during stable cruise (no WOT, no decel, both > 10 km/h, GPS/VSS ratio within 20%). Alpha=0.02 (~50 samples per 1% correction). Saves learned value to /home/pi/buell/vss_cal.json when drift > 0.5%. Loads on startup.
- ecu/protocol.py: module-level functions update_vss_calibration(), load_vss_calibration(), save_vss_calibration(), vss_changed_significantly() for use from main.py
- main.py: loads vss_cal.json at startup before threads start
- main.py: calls update_vss_calibration() in _ecu_loop after each GPS+VSS merge

### Changed

- ecu/protocol.py: GearFilter.detect() now accepts di_clutch and fl_decel parameters
- ecu/protocol.py: GearFilter coasting detection — two guards: (1) ratio below CENTERS[5]*0.80 = physically impossible in any gear; (2) fl_decel=1 AND rpm < 1400 AND kph > 15 = near-idle decel with wheel spinning
- ecu/protocol.py: GearFilter STD_THR tightened 1.5 -> 1.0, MIN_SAMPLES increased 8 -> 12 for higher accuracy
- ecu/protocol.py: cliff detector now verifies new segment stability before accepting gear change
- ecu/protocol.py: decode_rt_packet passes di_clutch and fl_decel to GearFilter.detect()
- ecu/protocol.py: decode_rt_packet uses _vss_calibrator.get() instead of hardcoded VSS_CPKM25

### Fixed

- ecu/protocol.py: removed unused `final` import from typing

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.56] — 2026-05-30

### Changed

- web/templates/index.html: scrollbar styled to match dark theme — 3px wide, dark border color thumb, transparent track. Scrolling preserved. Works on Safari/Chrome (webkit) and Firefox (scrollbar-width/color).

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.55] — 2026-05-30

### Fixed

- web/server.py: missing `import zlib` — caused NameError when serving CSV downloads with gzip encoding

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.54] — 2026-05-30

### Fixed

- web/server.py: _handle_csv returned empty HTTP 200 when no CSV chunks were found (legacy rides with mismatched filenames) — now returns 404 with descriptive error message
- web/static/app.js: loadGraphRide now reads error body from non-200 responses to show actual message instead of generic "HTTP 500". Guards against empty CSV text (shows "Sin datos" instead of crashing parseCSVtoRows)

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.53] — 2026-05-30

### Added

- web/static/app.js: sessions list auto-refreshes 1.5s after a ride ends — detected via ride_active transition true->false in fetchLive(). No full page reload needed.

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.52] — 2026-05-30

### Removed

- web/static/app.js: close_reason removed from sessions ride list display — was showing internal strings like "RPM=0 por 5s" which are not useful to the user

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.51] — 2026-05-30

### Removed

- web/templates/index.html: 騎行終 close-ride button removed from header row 3
- web/static/app.js: btnCloseRide control block removed (disabled/opacity logic). closeRide() function retained.

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.50] — 2026-05-30

### Changed

- web/templates/index.html: .hs containers now fixed 50x33px, flex centered — eliminates all vertical alignment inconsistencies between cells
- web/templates/index.html: removed all .hs-label divs from header row 1 (EGO/MAT/Batt/Marcha/Ride/Serial) — no more label text taking space or causing misalignment
- web/templates/index.html: .hs-val font-size set to 30px (fits 4-char values within 50px width)
- web/static/app.js: removed hRideLabel references — ride display simplified to single hRide element (shows elapsed time when active, ride number when inactive)

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.49] — 2026-05-30

### Changed

- web/templates/index.html: .hs cells now bottom-aligned (justify-content:flex-end) — all header values share the same visual baseline regardless of content size

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.48] — 2026-05-30

### Changed

- web/templates/index.html: .hs-label now absolutely positioned (5px, top-left overlay) — value takes full cell height, font-size 28px -> 36px with same row height
- web/static/app.js: VE grid Load column (10-255) moved from left side to right side of the grid

### Fixed

- web/static/app.js: buildCobertGrid had incorrect closing brace placement during grid restructure — corrected

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.47] — 2026-05-30

### Changed

- web/templates/index.html: big cards — removed CHT/KPH/TPS/RPM title labels and bottom unit text; units now shown inline to the right of the value (°C, km/h, %, rpm) saving vertical space
- web/templates/index.html: big-card padding reduced 8px -> 5px to further reduce header height
- web/templates/index.html: TPS degrees sub-display simplified, removed "grados" text label

### Fixed

- web/static/app.js: bigRPM element was never updated — RPM card always showed "--". Added missing update: Math.round(lv.RPM)
- web/static/app.js: TPS value no longer includes "%" suffix (moved to inline HTML unit span)

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.46] — 2026-05-30

### Changed

- web/templates/index.html: big-display changed from flex row to 2x2 CSS grid — each card now ~190px wide on iPhone 12 instead of ~90px, allowing 72px numbers to render correctly

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.45] — 2026-05-30

### Changed

- web/templates/index.html: big-num font size increased 56px -> 72px for better readability on iPhone 12
- web/templates/index.html: flavor mode buttons (Segundos/EGO/SWEET/TIPOUT/Confianza/O2 ADC/WOT) moved from above the VE grid to below it — they are not changed during a ride so they don't need to be prominent
- web/templates/index.html: removed "Celdas" section label — no informational value

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.44] — 2026-05-30

### Fixed

- main.py: GPS watchdog now calls gps.stop() before replacing the dead thread — prevents two GPSReader threads running simultaneously
- main.py: _ecu_thread.join(timeout=5s) added before shutdown() — eliminates race condition where both _ecu_loop and shutdown() tried to close the active ride simultaneously
- web/server.py: _get_live() called cell_tracker.snapshot() twice per request — now called once and stored in _snap, halves lock acquisitions on the cell tracker

### AI
- Claude Sonnet 4.6, Anthropic



## [v2.6.43] — 2026-05-30

### Removed

- web/templates/index.html: ERR indicator removed from live tab header — not useful in daily use
- web/static/app.js: hErr JS block removed (ride_errors display logic)

### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.42] — 2026-05-30

### Fixed

- ecu/connection.py: usb_power_cycle() and usb_reset() now use with open() — eliminates leaked file handles on USB recovery paths (Bug P2 from BACKLOG)
- web/server.py: CSV multi-part download skipped only 1 line per part instead of 2 (comment + header), causing duplicate headers in concatenated output — now skips both lines for parts 2+
- web/static/app.js: downloadEeprom() and downloadMsq() now use URL.createObjectURL(blob) + revokeObjectURL — fixes download on mobile browsers
- web/templates/sessions_vs.html: download() rewritten with fetch + blob instead of bare anchor click — consistent with app.js approach

### Removed

- web/server.py: TIPIN removed from COVERAGE_TARGETS_DEFAULT, _set_coverage_targets validation set, and _get_coverage() flavor loop — TIPIN is not actionable for VE tuning (AE active during tip-in, map does not govern fuel)
- web/templates/index.html: TIPIN button removed from coverage grid

### AI
- Claude Sonnet 4.6, Anthropic




## [v2.6.41] — 2026-05-27

### Fixed

- **web/server.py: Path traversal vulnerability in _handle_static** (#12): `lstrip("/")` + `os.path.join` allowed `../` traversal to read arbitrary files outside the web root. Replaced `fpath.startswith(base)` with `os.path.commonpath([base, fpath]) == base` — the robust Python approach that correctly resolves both `../` traversal and prefix-matching attacks.

- **Bug #9: `_get_version()` reads CHANGELOG.md every call** — `LOGGER_VERSION = _get_version()` was moved to module level so the file is read only once at import time. Also fixed parsing to skip HTML comment blocks (PROMPT_START/PROMPT_END).

## [v2.6.40] — 2026-05-27

### Fixed

- main.py: _check_threads string literals missing quotes (ecu-rt, sysmon) causing NameError in thread watchdog - dead threads would never be restarted
- ecu/session.py: _update_tuning_report used leaked outer-loop variable v instead of agg dict a for o2_adc_avg calculation - caused KeyError and corrupted tuning reports
- ecu/session.py: _rebuild_summary cell default dict missing o2_adc_sum key - caused KeyError when recovering orphan rides

### AI

- Codebuff (DeepSeek V4 Flash) - bug analysis and fixes

## [v2.6.39] — 2026-05-26
### Fixed
- web/server.py: add JSON type validation to _handle_coverage_targets — reject non-dict payloads with clear error message
- network/manager.py: add threading.Lock to NetworkManager for _save_state and load_state (prevents network_state.json corruption on concurrent WiFi/hotspot switches)
- web/server.py: _handle_static FD leak incidentally fixed in v2.6.38 (with open)
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.38] — 2026-05-26
### Fixed
- web/server.py: fix path traversal in _handle_static — sanitize with os.path.realpath() + startswith(base) guard (also fixes FD leak with `with open`)
- main.py: add _check_threads() watchdog — restart dead ecu-rt/sysmon daemon threads from heartbeat loop
- web/server.py + main.py: add threading.RLock (_data_lock) for serial_stats read-modify-write and ecu_live writes
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.37] — 2026-05-26
### Fixed
- ecu/session.py: fix variable scope bug in _rebuild_summary — a["o2_adc_sum"] → v["o2_adc_sum"] (NameError when recovering orphaned rides)
### AI
- DeepSeek V4 Flash, DeepSeek
## [v2.6.36] - 2026-05-26

### Fixed
- Bug #7: Added _validate_eeprom() sanity checks (KMFG_Year, KMFG_Day, Ride_Counter, KEngineRun, spark_load axis ranges) — corrupted EEPROM dumps now return empty dicts with warning log instead of silently decoding garbage

## [v2.6.35] - 2026-05-26

### Fixed
- Bug #6: Added 5-second cooldown to FIFO flush with getattr/monotonic — prevents rapid repeated buffer flushes when serial port is erratic
- Optimized: Inlined time.monotonic() calls and replaced hasattr with getattr for cleaner cooldown check

## [v2.6.34] - 2026-05-26

### Fixed
- Bug #8: Added (total_valid_s or 0) guard in quality_ratio calculation — prevents TypeError when total_valid_s is None due to data corruption

## [v2.6.33] - 2026-05-26

### Fixed
- Bug #5: Added self.logger.debug() to 4 silent except blocks in session.py (tuning report, eeprom_decoded, MSQ gen, cell aggregation) — no behavior change, just visibility

## [v2.6.32] - 2026-05-26

### Fixed
- Bug #4: Replaced time.time() with time.monotonic() in connection.py and ecu/connection.py (12 occurrences) — prevents infinite timeout loops when system clock jumps due to NTP/DST
- Left main.py time.time() calls unchanged (data timestamps and logging interval need wall-clock time)

## [v2.6.31] - 2026-05-26

### Fixed
- Bug #3: Heartbeat loop now wrapped in try/except — thread won't die silently
- Fixed indentation in _sysmon_loop and _ecu_loop caused by collateral from sed (removed duplicate/empty `try:` lines)

## [v2.6.30] - 2026-05-26

### Fixed
- **Bug #1 — `o2_adc_avg` variable scope:** Fixed NameError in `_update_tuning_report` (`ecu/session.py:341`). Changed `v["o2_adc_sum"]` to `a["o2_adc_sum"]` — `v` was from an outer loop scope while all other fields correctly used the aggregated dict `a`.

## [v2.6.29] - 2026-05-26

### Added
- Pagina dedicada /errorlog/viz con visor grafico de error logs.
  - Selectores de sesion y ride con filtro por tipo de evento.
  - Stats en vivo: total eventos, timeouts, reconnects, tiempo perdido, % afectado.
  - Timeline canvas: linea RPM + barras de timeout con altura proporcional a lost_s.
  - Scatter plots (Canvas nativo): RPM x CLT coloreado por lost_s y BATT x lost_s.
  - Barras de distribucion por tipo de evento.
  - Lista de eventos filtrable con contexto completo del motor.
- Nav-tab "Errores" en index.html apuntando a /errorlog/viz.
- Ruta /errorlog/viz en server.py con handler _handle_errorlog_viz.

### Fixed
- La ruta /errorlog/viz se antepone al prefix /errorlog/ para evitar conflicto.

## [v2.6.28] - 2026-05-26
### Added
- web/templates/index.html + web/static/app.js: error log viewer modal — el badge ⚠️ ahora es clickeable y abre un modal con resumen de errores (tabla de conteos por tipo) y lista cronológica de eventos con contexto del motor (RPM, CLT, TPS, VSS, BATT) para cada error
### AI
- Implemented error log viewer feature: clickable errBadge in ride list opens modal fetching /errorlog/{ride_num} and renders summary table + event timeline with ctx

### Fixed
- Bug: session-mismatch en /errorlog/ — endpoint buscaba solo por ride_num, devolviendo datos de sesión incorrecta cuando existían rides con el mismo número en distintas sesiones. Se agregó session al path (/errorlog/<session>/<ride_num>).
- Bug: _get_rides() no poblaba has_errorlog/errorlog_events — backend no enviaba los campos que el frontend ya esperaba para mostrar el badge ⚠️.
- Bug: modal mostraba "No se encontraron eventos" — frontend checkeaba !d.has_errorlog pero el endpoint devuelve el JSON crudo sin ese campo. Se eliminó la condición redundante.
- Bug: errBadge no era clickeable (backfill) — se agregó onclick con openErrorLog(sk, ride_num).
## [v2.6.27] - 2026-05-26
### Added
- ANL6: added valid_for_tuning flag to ride summary JSON
- ANL7: added health_score (0-100) to ride summary JSON
- ANL12: added /tuning_report HTTP endpoint
- ANL13: added format=csv option to /tuning_report
- ANL3: added format=csv option to /coverage.json
- ANL2: added O2_ADC real-time overlay to the cobertura heatmap (frontend + backend - o2_adc_avg per cell)
- ANL1: added confidence overlay mode (Confianza) to the cobertura heatmap (frontend) — exports per-cell VE coverage data with flavor progress
### Removed
- archive/: deleted unused legacy code
- BACKLOG.md: removed completed REFACTOR items and empty ARCHIVO section
- BACKLOG_ANL.md: removed completed BACKLOG-ANL4
### Changed
- main.py: replaced magic sleep values with named constants
### Fixed
- web/server.py: replaced bare except: blocks with specific handlers + logging
### AI
- DeepSeek V4 Flash

## [v2.6.27.1] - 2026-05-26
### Fixed
- web/static/app.js: added missing `confColor()` function — was nested inside `pctColor()`, breaking JS execution before `fetchLive()` could display version
- web/static/app.js: cleaned corrupted `renderCobertLegend()` — had grid code (variables `c`, `populated`, `bg`) mistakenly inserted between legend blocks
- web/static/app.js: added missing `confidence` and `o2_adc` mode cases to `renderCobertGrid()` — were accidentally omitted when confidence/o2_adc overlays were added
- web/server.py: moved `_handle_tuning_report()` out of `_compare_sessions()` — was defined inside `_compare_sessions()` after `return`, making it unreachable dead code; caused `AttributeError: DashboardHandler object has no attribute _handle_tuning_report` on every request
- web/server.py: fixed indentation of `/tuning_report` route entry in routes dict (was missing leading whitespace)
- web/server.py: split inline dict entry — `"confidence"` and `"o2_adc_avg"` on separate lines (cosmetic)
- ecu/session.py: added missing `n=v["count"]; vn=v["valid_count"]` in `_rebuild_summary()` — variables were deleted but dict still referenced them; caused `NameError` in `power_loss_recovered` recovery path
- web/templates/index.html: added `--LOGGER_VERSION--` placeholder inside `hdrVersion` span so version renders statically from server (no longer depends solely on JS fetchLive)
### AI
- DeepSeek V4 Flash
## [v2.6.26] — 2026-05-24
### Changed
- web/templates/index.html: moved version display from config subtab to header, next to BUELL LOGGER.
- web/static/app.js: updated to target hdrVersion element in header.
### AI
- DeepSeek V4 Flash

## [v2.6.25] — 2026-05-24
### Fixed
- ecu/protocol.py: ZeroDivisionError in VSS_RPM_Ratio calculation when RPM=0. Added guard clause to avoid division by zero when engine is off.
### AI
- DeepSeek V4 Flash


> All entries must be written in English.
> Each entry must include an ### AI section crediting the AI(s) that contributed.

## [v2.6.24] — 2026-05-24
### Fixed
- web/server.py: _handle_post_network() was missing `net = self.server_instance.network`
  causing a NameError when the hotspot button was pressed — hotspot/wifi switch now works.
- gps/reader.py: satellite count now reads gpsd `uSat` field directly; falls back to
  counting satellites[] array — fixes SAT=0 in dashboard header.
- web/server.py: GPS fix data merged into live.json `live{}` at all times regardless
  of ECU connection state.
- web/server.py: _get_version() now skips HTML comment block in CHANGELOG.md before
  searching for version string — fixes dashboard showing "vX.Y.Z".
### Changed
- CHANGELOG.md: added PROMPT_START/PROMPT_END markers and instructions #6 and #7
  requiring git commit+push after every change and cleanup of fix_*.py before commit.
- Removed stale fix_*.py scripts from working directory.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.23] — 2026-05-24
### Changed
- CHANGELOG.md: added PROMPT_START/PROMPT_END markers to instruction block so AI
  assistants know to read all instructions before acting, even when only a partial
  view of the file is available (e.g. head -5).
- CHANGELOG.md: added instruction #6 requiring git add + commit + push after every
  change to keep history clean and enable rollback to any previous state.
### AI
- Claude Sonnet 4.6, Anthropic

## [v2.6.22] — 2026-05-24
### Fixed
- web/server.py: _get_version() now skips the HTML comment block in CHANGELOG.md
  before searching for the version — previously the regex matched the example
  entry inside the instructions comment, returning "vX.Y.Z" instead of the
  actual version.
### AI
- Claude Sonnet 4.6, Anthropic
* **Audited:** PASS — freebuff 2026-06-06 (TASK 048: post-ride gear detection v2.7.36, 96.9% accuracy)

## [v2.6.21] — 2026-05-24
### Fixed
- gps/reader.py: satellite count now reads gpsd `uSat` field directly instead of
  counting `satellites[]` array entries — fixes persistent SAT=0 in dashboard header
  when gpsd sends SKY messages without the full satellite list.
- web/server.py: GPS fix data (lat, lon, alt, speed, heading, satellites, valid)
  now merged into live.json `live{}` payload at all times, regardless of ECU
  connection state — previously GPS fields were absent when ECU was disconnected.
- web/static/app.js: dashboard SAT field now correctly reflects live satellite count.
### AI


## [v2.6.20] — 2026-05-24
### Changed
- web/server.py: refactored monolithic do_GET (~26 routes) and do_POST (~12 routes)
  into named _handle_* methods with clean dict-based dispatchers.
  Each route block keeps its exact original logic — zero behavioral changes.
- do_GET: dict dispatcher for exact matches + if/elif chain for prefix routes
  (static, csv, ride, errorlog, wifi/redirect_url).
- do_POST: dict dispatcher dispatching to _handle_post_* methods.

## [v2.6.20.1] — 2026-05-24
### Changed
- web/server.py: refactored monolithic do_GET (~26 routes) and do_POST (~12 routes)
  into named _handle_* methods with clean dict-based dispatchers.
  Each handler preserves exact original logic — zero behavioral changes.
- do_GET: dict dispatcher for exact matches + if/elif chain for prefix routes
  (static, csv, ride, errorlog, wifi/redirect_url).
- do_POST: dict dispatcher dispatching to _handle_post_* methods.
- Each GET handler receives `path` as argument and resolves `net` internally
  to fix NameError scope issues when extracting from the enclosing do_GET scope.

## [v2.6.19] — 2026-05-24
### Removed
- web/static/app.js: removed orphaned TPS/VSS calibration functions
  (startTpsCapture, _tpsCaptureActive, init calls loadTpsCal/loadVssCal).
  These were dead code — no backend endpoints existed.
- web/templates/index.html: removed Calibracion TPS and Calibracion Velocidad
  UI sections (orphaned, no backend).
### Changed
- CHANGELOG.md: added "All entries must be written in English" header.

## [v2.6.18] — 2026-05-24
### Fixed
- web/static/app.js: bug del menú hamburguesa — el archivo contenía etiquetas
  `<script>` y `</script>` del HTML original (error de extracción con sed).
  Al cargarse como JS externo, `<script>` causaba SyntaxError y ninguna
  función (incluyendo showTab) se definía. Solución: remover las etiquetas
  del principio y final del archivo.

## [v2.6.17] — 2026-05-24
### Changed
- web/: JS separado de templates/index.html a static/app.js (~2100 líneas inline
  a archivo externo). Agregado ruteo /static/ en server.py con soporte MIME.
- web/templates/index.html: reducido de 2846 a 685 líneas. El JS se carga vía
  <script src=/static/app.js> con window.LOGGER_VERSION inline.

## [v2.6.16] — 2026-05-24
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG.md: Launch Event como prerequisito de FASE 1 (Merge RAW de mapas).
  Detecta crucero estable ≥3s → WOT para etiquetar pulls válidos.

## [v2.6.15] — 2026-05-24
### Changed
- ARCHITECTURE.md: limpieza de datos de runtime en file tree — eliminados
  network_state.json, objectives.json, backups (.bak/.save). Agregada nota
  de exclusión en el header del árbol y advertencia ⚠️ en la sección "Archivos
  de datos (runtime)".

## [v2.6.14] — 2026-05-24
### Fixed
- ecu/protocol.py: crash al iniciar el servicio — `NameError: name "CENTERS" is
  not defined` en GearFilter. Causa: list comprehension dentro de la clase no
  podía acceder a otra variable de clase (Python 3 scoping). Solución: mover
  CENTERS y THRESHOLDS a nivel módulo.

## [v2.6.13] — 2026-05-24
### Changed
- ecu/protocol.py: gear detection migrada a ventana deslizante estadística.
  - Nuevo GearFilter con ratio RPM/KPH (invertido vs VSS_RPM_Ratio)
    para mayor separación entre marchas.
  - Cliff detector: detecta cambios bruscos en ~0.5s (vs ~1s antes).
  - Outlier filter + stability check via desviación estándar.
  - Centros calibrados empíricamente: [75.5, 53.8, 40.1, 33.3, 28.7].
  - VSS_RPM_Ratio en CSV se mantiene sin cambios.
- Eliminadas constantes viejas: GEAR_KPH_PER_KRPM, GEAR_THRESHOLDS,
  _gear_buffer, _rpm_buffer, _kph_buffer.

# Buell XB12X Logger — Changelog

> **Language policy:** All code, comments, variable names, and documentation
> must be written in English. Spanish is only acceptable for UI strings
> displayed to the end-user in the web dashboard.

## [v2.6.12] — 2026-05-24
### Changed
- ecu/protocol.py: agregados type hints (GearFilter, decode_rt_packet, constantes).
- ecu/connection.py: agregados type hints (DDFI2Connection, build_pdu, helpers).

## [v2.6.11] — 2026-05-24
### Fixed
- main.py: eliminada llamada duplicada a `recover_orphan_rides()`.

## [v2.6.10] — 2026-05-23
### Changed
- tools/make_index.py y tools/recover_summaries.py → archive/ (scripts one-shot,
  mantenidos como referencia).
- ARCHITECTURE.md: header actualizado con nota de archivado, file tree refleja
  nuevas rutas.
- BACKLOG.md: eliminado item P3 completado + agregado item P2 para revisar
  lógica de ARCHITECTURE.md (ignorar datos de runtime).

## [v2.6.9] — 2026-05-23
### Changed
- ecu/connection.py: todos los open() ahora usan with open() (7 bloques).
  Elimina file handles colgados en usb_power_cycle, usb_reset y usb_reset reads sysfs.
- BACKLOG.md: marcado P2 completado.

## [v2.6.8] — 2026-05-23
### Changed
- ecu/protocol.py: gear detection — ring buffers envueltos en clase GearFilter.
  Elimina estado mutable a nivel modulo, permite testeo independiente
  y uso de instancias aisladas.
- BACKLOG.md: marcado P2 completado.

## [v2.6.7] — 2026-05-23
### Changed
- ddfi2_logger.py movido a archive/ (código muerto, modularizado hace tiempo)
- connection.py importa constantes de protocol.py (SOH, EOH, ACK, etc.) en vez de redefinirlas
- protocol.py: nueva fuente única de verdad para constantes de protocolo DDFI2

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG.md: nueva sección REFACTOR / DEUDA TÉCNICA con 10 mejoras identificadas

### Removed
- Temp scripts basura (_update_changelog*.py, _add_speed_axis.py, nul) del raíz

## [v2.6.6] — 2026-05-23
### Changed
- ecu/protocol.py: recalibración VSS_CPKM25 1368 → 1518 (~11% ajuste).
  Alinea velocidad del dash (VS_KPH) con GPS. Derivado de 3,029 períodos
  estables en rides 4-5 de sesión 47BF04.

## [v2.6.5] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- web/templates/index.html (loadMapTrack): perfil de altitud ahora incluye
  linea de velocidad (km/h) como segundo eje Y (derecha) en el chart.
  Coloreada con el mismo gradiente continuo azul-verde-amarillo-rojo-magenta
  del mapa para correlacion visual inmediata.

## [v2.6.4] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- ecu/protocol.py: filtro mediano (20 samples, ~1s) en gear detection.
  Cuando RPM/KPH estan estables (rango RPM < 200, KPH < 8) valida la
  marcha usando la mediana de los ultimos ~1s, corrigiendo outliers.

## [v2.6.3] — 2026-05-23
### Fixed
- main.py _sysmon_loop: merge en vez de overwrite de serial_stats — TTL%/BPS ya no parpadean en el dash
- ecu/protocol.py gear detection: removida histeresis con _gear_prev — la marcha ya no se queda pegada en 5ta.
  Vuelve a detección absoluta (cada sample se evalúa independientemente, como en v2.5.x).

## [v2.6.2] — 2026-05-23
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
-  en : merge de celdas ahora incluye  de los summary JSON
  - Los modos SWEET, TIPIN, TIPOUT, WOT del grid VE ahora funcionan con rides históricos
  - Usa  desde  para calcular porcentaje de cobertura
  - Solo muestra flavors con segundos > 0 (consistente con el live /coverage.json)

## [v2.6.1] — 2026-05-23
### Fixed
-  en : merge de celdas ahora usa fallback a  cuando  (rides de motor frío)
  - El grid VE en Ride tab mostraba vacío para rides con datos grabados durante calentamiento (WUE > 102)
  - Afectaba rides de las sesiones ,  y cualquier ride donde CellTracker marcara datos como inválidos

# CHANGELOG — Buell XB12X DDFI2 Logger
> Raspberry Pi Zero 2W · CH343P · Python 3 · 9600,8N1
> Repository: https://github.com/pacdavid1/buell-xb12x-logger
---
## [v2.6.0] — 2026-05-21
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `GPSReader.is_alive()` — método público que encapsula acceso a `_thread` (reemplaza `self.gps._thread.is_alive()` en `main.py`)
- `pollCobertGrid()` en frontend — polling en tiempo real desde `/coverage.json` para el grid de cobertura VE

### Changed
- Grid de pane Ride reemplazado por grid de cobertura VE con 6 modos visuales: Segundos, EGO, SWEET, TIPIN, TIPOUT, WOT — con leyenda dinámica, coloreado por porcentaje y chips de resumen por flavor
- Leyenda del mapa GPS actualizada a 5 stops consistentes con `getGradientColor()` (azul→verde→amarillo→naranja→magenta)
- `getSpeedColor()` eliminada — mapa y perfil de altitud ahora usan `getGradientColor()` unificado

### Fixed
- `web/server.py`: imports perezosos (`csv`, `zlib`, `logging`, `json`, `urllib.parse`) movidos al inicio del archivo — elimina 8 imports redundantes dentro de métodos
- `web/server.py`: bare `except:` cambiado a `except Exception:` (2 instancias)
- `web/server.py`: path hardcodeado `/home/pi/buell/sessions` en `/gps_track` reemplazado por `Path(self.server_instance.buell_dir) / 'sessions'`
- `web/server.py`: fetch duplicado de GPS en `_get_live_data()` eliminado — los datos GPS ya se inyectan en el ECU loop (`main.py:356`)
- `gps/reader.py`: bare `except: continue` cambiado a `except Exception as e: logger.debug(...); continue`
- `main.py`: acceso a `self.gps._thread.is_alive()` reemplazado por `self.gps.is_alive()`

### Removed
- `web/templates/cobertura.html` — eliminado, funcionalidad integrada en pane Ride de `index.html`
- Ruta `/cobertura` en `web/server.py`
---

## [v2.5.50] — 2026-04-27
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- GPS via gpsd — reemplaza pyserial directo, manejo profesional del M8N
- Endpoint /gps_fix para monitorear GPS sin ECU conectada
- GPS satellites visible en header del dash (SAT)
- SBAS habilitado para mejor accuracy
- gpsd como dependencia systemd de buell-logger
### Fixed
- GPS CFG-PRT antes de CFG-RATE — habilita protocolo UBX, ACK confirmado
- GPS 5Hz guardado en flash del M8N — persiste entre reinicios
- GPS parse no guarda speed/pos cuando gps_valid=False
- GPS satellites no se resetea a 0 con SKY vacío de gpsd
- GPS siempre presente en live.json via _get_live_data aunque no haya ECU
- GPS inject removido de sysmon — lo maneja _get_live_data en server.py
---
## [v2.5.49] — 2026-04-19
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Altitude profile chart (Chart.js) below Leaflet map, colored by speed
- GPS confirmed at 5Hz (UBX CFG-RATE 200ms persisted in module flash)
### Fixed
- GPS ttyS0 permission via sudoers + ExecStartPre in systemd service
- Map dark mode (CARTO night tiles)
- Speed gradient colors fixed scale on map polyline

## [v2.5.48] — 2026-04-18
### Fixed
- session_metadata.json corruption caused JSONDecodeError on boot — manual fix applied to 3311B1
- start_ride() RuntimeError no longer kills ECU thread — now caught and logged as warning
- Race condition: start_ride() attempted before open_session() completed after motor voltage drop
- GPS reader: keeps last known position when fix is lost (gps_valid=False but lat/lon retained)
- /gps_track endpoint: includes all points with non-null lat/lon regardless of gps_valid flag
- except Exception in run() now logs full traceback for easier debugging
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- BACKLOG-INF1: session_metadata.json corruption guard (queued)

## [v2.5.47] — 2026-04-18
### Fixed
- shutdown() ahora cierra el ride activo limpiamente antes de detener servicios
- Rides huérfanos (sin summary JSON) ya no se pierden en apagados abruptos
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- tools/recover_summaries.py — recupera summaries JSON de rides huérfanos leyendo CSV
- 31 summaries recuperados de sesiones anteriores
### Changed
- Tab Mapa: selector de rides ordenado por fecha descendente (Date object sort)

## [v2.5.46] — 2026-04-18
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Tab "Mapa" en dashboard con Leaflet.js (OpenStreetMap, sin API key)
- Endpoint `/gps_track?session=X&ride=N` — lee CSV y devuelve puntos GPS válidos
- Mapa de ruta con polyline coloreada por velocidad (verde=lento, rojo=rápido)
- Marcadores de inicio (verde) y fin (rojo) en la ruta
- Selector de rides en el tab Mapa
- Info bar: cantidad de puntos, velocidad máxima, distancia aproximada
### Changed
- `showTab()` extendido para incluir 'map'

## [v2.5.45] — 2026-04-18
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- GPS integration: NEO-M8N connected via UART (ttyS0, pins 8/10, 9600 baud)
- `gps/reader.py`: GPSReader thread — parses $GNRMC and $GNGGA, thread-safe get_fix()
- `gps/__init__.py`: module init
- CSV columns: gps_lat, gps_lon, gps_alt_m, gps_speed_kmh, gps_heading, gps_satellites, gps_valid
- GPS data injected per sample in main.py RT loop alongside ECU data
### Changed
- `ecu/protocol.py`: CSV_COLUMNS extended with 7 GPS fields
- `main.py`: GPSReader instantiated, started with other threads, fix injected before write_sample
- Disabled serial-getty@ttyS0 (was blocking UART port)
- Added udev rule 99-ttyS0-gps.rules (MODE=0666)


## [v2.5.44] — 2026-04-11
### Fixed
- Tooltip "aplastado": eliminado fondo transparente, ajustado padding y tamaños de fuente
- Gráficas borrosas/distorsionadas: corregido aspect ratio eliminando `!important` en CSS canvas
- Líneas de gráfica más nítidas: `borderWidth` 2.5, `tension` 0 (líneas rectas)

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Panel lateral de datos ("DATOS CURSOR"): visualización fija de RPM, KPH, CLT al mover cursor
- Plugin crosshair Chart.js: línea vertical punteada que sigue el cursor en tiempo real
- Tooltip external: sistema personalizado que alimenta el panel lateral sin interferir visualmente
- Offset configurable: tooltip separado 15px del punto de datos para no estorbar

### Changed
- Alineación de tooltip: ahora aparece a la izquierda del cursor (`xAlign: left`)
- Fondo de tooltip: completamente transparente para ver solo los números

### Technical
- Registro global de plugin Chart.js para crosshair sincronizado
- Implementación de callback `external` en tooltip para desacoplar visualización de datos

> Co-authored-by: Kimi (Moonshot AI) <kimi@moonshot.cn>

---

## [v2.5.44.1] — 2026-04-11
### Fixed
- Tooltip "aplastado": eliminado fondo transparente, ajustado padding y tamaños de fuente
- Gráficas borrosas/distorsionadas: corregido aspect ratio eliminando `!important` en CSS canvas
- Líneas de gráfica más nítidas: `borderWidth` 2.5, `tension` 0 (líneas rectas)

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Panel lateral de datos ("DATOS CURSOR"): visualización fija de RPM, KPH, CLT al mover cursor
- Plugin crosshair Chart.js: línea vertical punteada que sigue el cursor en tiempo real
- Tooltip external: sistema personalizado que alimenta el panel lateral sin interferir visualmente
- Offset configurable: tooltip separado 15px del punto de datos para no estorbar

### Changed
- Alineación de tooltip: ahora aparece a la izquierda del cursor (`xAlign: left`)
- Fondo de tooltip: completamente transparente para ver solo los números

### Technical
- Registro global de plugin Chart.js para crosshair sincronizado
- Implementación de callback `external` en tooltip para desacoplar visualización de datos

---
## [v2.5.43] — 2026-04-11
### Fixed
- Live grid now updates in real-time even when viewing a historical ride
- `fetchLive()`: if `_viewingHistory=true` but a ride is active, grid and header still refresh at 500ms
- Previously the grid froze as soon as a saved ride was selected for viewing

### Notes
- Co-authored-by: Claude (Anthropic)

## [v2.5.42] — 2026-04-11
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `WebServer.ecu_identity`: new field exposing resolved ECU metadata (name, dbfile, ddfi, remark)
- `main.py`: populates `ecu_identity` via `resolve_ecu()` at all 3 EEPROM load sites (startup, reconnect, cached fallback)
- `live.json`: includes `ecu_identity` alongside `bike_serial`
- Startup log now shows ECU name and DDFI variant on EEPROM ready
### Changed
- `fix_charts_sync.py`: removed (changes already applied to index.html in prior session)
- `.gitignore`: exclude `*.bak*` template backups
### Notes
- Co-diagnosed: Claude (Anthropic)

## [v2.5.41] — 2026-04-09
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `SessionManager._generate_suggested_msq()`: genera MSQ con sugerencias aplicadas automáticamente al cerrar cada ride
- MSQ toma EEPROM actual como base y aplica factor de corrección solo a celdas con suggestion
- Safety limits: VE entre 10-250, máximo 5% de cambio por iteración
- Endpoint `GET /suggested_msq`: descarga el MSQ sugerido de la sesión activa
- MSQ guardado en `sessions/CHECKSUM/suggested_CHECKSUM.msq`
### Notes
- Solo modifica fuel_front por ahora — fuel_rear y spark se copian sin cambios
- MSQ compatible con EcmSpy — misma estructura que Custom_DDFI2_Map.msq
- Co-diagnosed: Claude (Anthropic)

## [v2.5.40] — 2026-04-06
### Changed
- `CellTracker.update()`: distribución bilineal entre 4 celdas vecinas (antes 100% a una celda)
- `CellTracker._bilinear_weights()`: pesos bilineales consistentes con interpolación del ECU
- `CellTracker._empty_cell()`: inicialización centralizada incluyendo `ego_iir`
- `CellTracker.HARDNESS = 0.3`: parámetro configurable de velocidad de aprendizaje IIR
- `snapshot()`: incluye `ego_iir` (estimado IIR adaptivo) por celda
### Notes
- count/valid_count ahora son sumas de pesos flotantes — consistente con distribución bilineal
- Co-diagnosed: Claude (Anthropic)

## [v2.5.39] — 2026-04-06
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `eeprom_decoded.json`: generado desde eeprom.bin (35 params, 4 mapas VE/spark)
- `SessionManager._update_tuning_report()`: incluye eeprom_decoded en tuning_report
### Notes
- tuning_report ahora contiene mapa VE actual + sugerencias en un solo JSON
- Co-diagnosed: Claude (Anthropic)

## [v2.5.38] — 2026-04-06
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `CellTracker`: filtros de validez por sample (WUE, CLT, RPM, AFV, decel, fuel_cut, TPS_delta)
- `CellTracker`: acumuladores de calidad por celda (valid_seconds, valid_ego_avg, confidence, clt_avg, wue_avg, afv_avg, inv_reasons)
- `CellTracker._is_valid()`: retorna (bool, reason) para clasificar cada sample
- `SessionManager._update_tuning_report()`: genera/actualiza tuning_report_CHECKSUM.json al cerrar cada ride
- `analyze_session.py`: script standalone para agregar todos los CSVs de una sesión con filtros de validez
- `BACKLOG_ANL.md`: backlog dedicado al pipeline de análisis y tuning
- `tempColor(c)`: función JS de interpolación azul→blanco→rojo por temperatura °C
### Changed
- Big CHT en dashboard: color dinámico via tempColor() en lugar de clases CSS fijas
- Chart CLT: borderColor y eje Y3 usan tempColor(cltMax) del ride
- Labels CLT°F → CLT°C en chart y eje
- Límite de referencia en chart: 250°F → 235°C (umbral crítico XB)
### Notes
- tuning_report solo procesa rides con formato nuevo (valid_seconds en cells) — rides anteriores ignorados
- Co-diagnosed: Claude (Anthropic)

## [v2.5.37] — 2026-04-04
### Changed
- reading_loop reconnect simplificado: va directo a `usb_power_cycle()` a los 10s sin escalación.
- `usb_power_cycle()` timing reducido: 1s suspend + 2s resume (antes 2s+3s).
### Notes
- Elimina la lógica de escalación DTR→usb_reset→power_cycle que tenía bugs de timing.
- Pendiente confirmar recuperación tras killswitch cycles con moto real.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.36] — 2026-04-04
### Changed
- `usb_reset()` in `ecu/connection.py` now detects both FT232RL (`0403:6001`) and CH343P (`1a86:55d3`).
- reading_loop reconnect escalation synced with waiting_loop: 10s hard reconnect, 20s usb_reset, 30s power_cycle.
- `usb_power_cycle()` added to reading_loop escalation — previously only ran in waiting_loop.
### Notes
- LOG6 partially addressed — escalation now aggressive enough to recover hung adapter without reboot.
- Requires moto test to confirm full recovery after multiple killswitch cycles.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.35] — 2026-04-04
### Changed
- `decode_eeprom_params()` hardcode replaced by `decode_params_compat()` from `ecu/eeprom_params.py`.
- Both startup and reconnect flows now pass `version` string to `resolve_ecu()` via `version_resolver.py`.
- Correct XML selected automatically from `ecu_defs/files.xml` (exact match + alpha prefix fallback).
### Notes
- `BUEIB_PARAMS` dict remains in `ecu/eeprom.py` but is no longer used for parameter decoding.
- Closes BACKLOG-ECU1. Both motos (red #651, blue #235) now resolve their own XML at connect time.
- Co-diagnosed: Claude (Anthropic) — 2026-04-04

---
## [v2.5.34] — 2026-04-02
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- `usb_power_cycle()` method in `ecu/connection.py` — recovers dwc2 IRQ crash via sysfs autosuspend without reboot.
- Watchdog now triggers USB power cycle at 15s without ECU, USB reset at 30s.
### Changed
- Previous USB reset threshold was 60s — too slow for real-world reconnection.
### Notes
- Root cause: FT232RL + dwc2 (Pi Zero 2W) incompatibility causes `error -71` and `Disabling IRQ #51`.
- Power cycle via `/sys/bus/usb/devices/usb1/power/level` suspend/on recovers the controller without reboot.
- CH343P (isolated) confirmed as more stable alternative for permanent moto installation.
- Co-authored: Claude (Anthropic) — 2026-04-02

---

## [v2.5.33] — 2026-04-02
### Changed
- EEPROM is now always read on ECU connect, regardless of whether a session is already active.
- Enables automatic bike identity detection via checksum — switching logger between bikes (e.g. red #651 → blue #235) now creates correct session without restarting.
### Notes
- Previously EEPROM was only read when `current_checksum is None` — bike swap was invisible to the logger.
- `open_session()` already handled checksum change detection — fix was removing the guard condition.
- Co-authored: Claude (Anthropic) — 2026-04-02

---

## [v2.5.32] — 2026-04-01
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- udev rule `/etc/udev/rules.d/99-ecu-serial.rules` — auto-detects FT232RL (0403:6001) and CH343P (1a86:55d3), both symlinked to `/dev/ttyECU`.
- `ftdi_sio` driver added to `/etc/modules-load.d/ftdi.conf` for automatic load on boot.
- Service and install.sh updated to use `/dev/ttyECU` — adapter-agnostic, no code changes needed when switching TTL adapters.
- `@reboot dmesg -C` added to root crontab — clears kernel buffer on boot to prevent dwc2 USB controller IRQ crash after hot-swap.
### Notes
- CH343P (isolated) validated as drop-in replacement for FT232RL.
- Co-diagnosed: Claude (Anthropic) — 2026-04-01


---

## [v2.5.31] — 2026-04-01
### Fixed
- USB host mode not working on Pi Zero 2W after OS update.
- `dtoverlay=dwc2,dr_mode=host` was scoped under `[cm5]` in `/boot/firmware/config.txt` instead of `[all]`, causing FT232RL to never be detected by the kernel.
- Moved overlay to `[all]` section — FT232RL now enumerates correctly as `ttyUSB0` on boot.
### Notes
- Fix applied to `/boot/firmware/config.txt` (outside repo — system-level config).
- Diagnosed via `dmesg` and `lsusb`: kernel was attempting USB enumeration but failing with `error -71`.
- Co-diagnosed: Claude (Anthropic) — 2026-04-01


---

## [v2.5.30] — 2026-03-28
### Fixed
- Corrected Spark (Ignition Advance) EEPROM map decoding.
- Spark maps are now decoded as dense 10×10 rectangular grids instead of triangular VE-style layouts.
- Zero values in Spark maps are treated as valid data, not structural separators.
- Spark RPM axis handling corrected independently of VE axis logic.

### Verified
- Spark Front / Rear heatmaps now display correct rectangular geometry.
- Values are coherent across RPM/TPS with no diagonal padding artifacts.
- Runtime validated against EEPROM: Spark Advance visible and consistent.

---

## [v2.5.29] — 2026-03-28
### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Deterministic ECU variant resolution using `ecu_defs/files.xml`.
- New ECU version resolver maps `get_version()` strings (e.g. `BUEIB310`) to the correct EEPROM XML definition via `dbfile`.

### Changed
- EEPROM parameter decoding no longer relies on heuristic prefix matching.
- XML selection for EEPROM decoding is now aligned with EcmSpy behavior.

### Verified
- BUEIB310 / B2RIB / BUEIC variants correctly resolve to `BUEIB.xml`.
- Runtime confirmed: `Decoded 173 params from BUEIB.xml`.

---

## [v2.3.1] — 2026-03-21
**DASHBOARD COMPLETO — SESIONES, CSV Y GRÁFICAS**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **Endpoint `/rides`** (`web/server.py`) — lista rides desde summaries JSON.
  Fallback para rides sin summary (ride activo o sin cerrar).

* **Endpoint `/csv/`** (`web/server.py`) — sirve CSV del ride con soporte
  gzip automático. Concatena partes si el ride tiene múltiples archivos.

* **Endpoint `/ride/`** (`web/server.py`) — retorna summary JSON del ride
  con cells y objectives para el tab Ver.

* **`_get_rides()`** en `WebServer` — método que lista rides desde el
  filesystem sin leer CSVs completos.

### Result

Dashboard 100% funcional en modo modular: datos live ECU, mapas EEPROM,
sesiones grabadas, gráficas de rides visibles.

---

## [v2.3.0] — 2026-03-20
**EEPROM MODULAR — MAPAS VE Y SPARK EN DASHBOARD**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`ecu/eeprom.py`** — `BUEIB_PARAMS` (35 parámetros), `decode_eeprom_params()`
  y `decode_eeprom_maps()` extraídos del monolito. Módulo independiente y testeable.

* **Lectura EEPROM al arrancar** (`main.py`) — después de `get_version()` exitoso,
  se leen las 6 páginas BUEIB (1206 bytes) y se decodifican los 4 mapas:
  Fuel Front/Rear (12×13) y Spark Front/Rear (10×10). Tiempo de lectura ~3s.

* **Endpoints `/maps` y `/eeprom`** (`web/server.py`) — exponen los mapas
  decodificados y los parámetros de calibración como JSON. El dashboard
  ya muestra el heatmap con datos reales del EEPROM de la ECU.

* **`eeprom_maps` y `eeprom_params`** en `WebServer` — atributos inicializados
  en `{}` y poblados desde `main.py` después de leer el EEPROM.


---

## [v2.2.2] — 2026-03-20
**FIX SHUTDOWN — ExecStop eliminado del unit file**

### Fixed

* **`ExecStop=/usr/sbin/poweroff` en systemd unit** — línea agregada manualmente
  en una sesión anterior causaba que `systemctl restart` apagara la Pi en lugar
  de reiniciar el servicio. Eliminada del unit file en vivo.
  El `install.sh` ya generaba el unit sin `ExecStop` — no requirió cambios.

* **`WORKING_METHOD.md`** — agregadas secciones `AI ASSISTANT PROTOCOL` y
  `COMMIT DISCIPLINE` para que cualquier asistente siga las reglas de edición
  correctas desde el inicio de sesión.

---

## [v2.2.1] — 2026-03-20
**FIXES DE ESTABILIDAD — SHUTDOWN + ECU LOOP**

### Fixed

* **Poweroff en `systemctl restart`** (`main.py`, `web/server.py`) — al recibir
  SIGTERM, el logger ejecutaba `poweroff` apagando la Pi. Separado en dos flags:
  `_poweroff_requested` (solo desde dashboard web) vs SIGTERM que solo detiene
  el loop. El botón shutdown del dashboard ya no llama `poweroff` directo desde
  `server.py` — lo delega a `main.py`.

* **ECU loop sin reconexión** (`main.py`) — si el FT232 no estaba conectado al
  arrancar el servicio, `_ecu_loop` corría en silencio retornando `None` para
  siempre y `live.json` quedaba con `"live": {}`. Ahora el loop detecta
  `ser is None` y reintenta `connect()` + `get_version()` cada 5 segundos
  hasta que el adaptador esté disponible.

* **`import subprocess` faltante** (`main.py`) — el módulo se usaba en
  `shutdown()` pero no estaba importado al inicio del archivo.

---

## [v2.2.0] — 2026-03-20
**MODULARIZACIÓN ECU — ecu/connection.py + ecu/protocol.py**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`ecu/connection.py`** — `DDFI2Connection` extraída del monolito.
  Maneja apertura de puerto serial, toggle DTR, envío de PDUs,
  `get_version()`, `get_rt_data()`, `read_full_eeprom()` y USB reset via sysfs.
  Validada vs ECU real: `BUEIB310 12-11-03`.

* **`ecu/protocol.py`** — constantes y decodificación del protocolo DDFI2.
  `RT_VARIABLES` (56 parámetros), `decode_rt_packet()`, calibración TPS,
  cálculo VS_KPH, detección de marcha. Validada: RPM, CLT, Gear correctos.

* **`tools/test_ecu.py`** — script de diagnóstico independiente.
  Abre puerto, toggle DTR, envía PDU_VERSION y reporta respuesta.
  No depende del servicio ni del proyecto.

### Fixed

* **Poweroff en SIGTERM** (`main.py`) — `systemctl restart` apagaba la Pi
  porque `_handle_signal` ponía `_shutting_down=True` y `shutdown()` ejecutaba
  `poweroff`. Separado en `_poweroff_requested` — poweroff solo ocurre cuando
  el shutdown viene desde el dashboard web.

### Changed

* **`main.py`** — conecta a la ECU en arranque y loguea versión.
  Puerto serial ya no es argumento sin usar.

---

## [v2.1.6] — 2026-03-19

**INSTALL — IMAGEN LIMPIA COMPLETA**

### Fixed

* **`NetworkManager.conf managed=false`** — en imagen limpia de Raspberry Pi OS,
  NM no gestiona interfaces por defecto. El installer ahora cambia `managed=false`
  a `managed=true` antes de configurar el hotspot. Sin este fix el hotspot nunca
  arranca en una Pi recién flasheada.

---

## [v2.1.5] — 2026-03-19

**VERSION DINÁMICA DESDE CHANGELOG**

### Changed

* **`LOGGER_VERSION` en `main.py`** y **`logger_version` en `server.py`** —
  ambos leen la versión dinámicamente del `CHANGELOG.md` en lugar de tenerla
  hardcodeada. La pestaña Config siempre muestra la versión real del sistema.

---

## [v2.1.4] — 2026-03-19

**GIT PULL DESDE BROWSER — ACTUALIZACIÓN SIN TERMINAL**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **Endpoint `POST /git_pull`** en `server.py` — corre `git pull` en el repo
  y reinicia el servicio automáticamente. Sin necesidad de SSH ni terminal.

* **Botón "🔄 Git Pull"** ya existía en el HTML tab Config — ahora funciona
  correctamente al tener el endpoint implementado.

### Changed

* **Botón rojo "Descargar ddfi2_logger.py"** eliminado del tab Config.
  Reemplazado por el flujo de actualización via git pull.
  El texto de la sección ahora dice: "Jala la última versión desde GitHub
  y reinicia el servicio automáticamente."

### Fixed

* **Regla sudoers** — agregado permiso `NOPASSWD` para
  `systemctl restart buell-logger` al usuario `pi`.


---

## [v2.1.3] — 2026-03-19

**SHUTDOWN FIX — APAGADO DESDE BROWSER OPERATIVO**

### Fixed

* **Botón "Apagar Pi" no apagaba el sistema** — el proceso Python corría sin
  permisos para llamar `poweroff`. Solución en tres partes:
  - Regla polkit `99-buell-poweroff.rules` que autoriza al usuario `pi` a
    apagar sin contraseña via `org.freedesktop.login1.power-off`.
  - `web/server.py` — reemplaza `os.system("sudo poweroff")` por
    `subprocess.run(["/usr/sbin/poweroff"])` en el endpoint `/shutdown`.
  - `main.py` — mismo reemplazo en `shutdown()` para el apagado por señal.

* **`--no-poweroff` eliminado del servicio systemd** — el flag bloqueaba
  el apagado intencional desde el browser. El servicio ahora arranca sin él.

* **`Restart=always` → `Restart=on-failure`** — evita que systemd reinicie
  el logger después de un apagado limpio.

* **Regla polkit agregada al `install.sh`** — futuras instalaciones desde
  imagen limpia incluyen el permiso automáticamente.

---

## [v2.1.2] — 2026-03-19

**ARCHITECTURE INDEX — AUTO-GENERADO EN CADA COMMIT**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`tools/make_index.py`** — script que escanea el repo completo y genera
  `ARCHITECTURE.md` automáticamente. Detecta: árbol de archivos, clases,
  métodos, constantes, endpoints HTTP, tabs y funciones JS, pasos del installer.
  Compatible con cualquier archivo nuevo que se agregue al repo sin configuración.

* **`ARCHITECTURE.md`** — índice auto-generado en la raíz del repo.
  Documenta el estado real del código en cada commit.

* **Git hook `pre-commit`** — corre `make_index.py` y agrega `ARCHITECTURE.md`
  automáticamente antes de cada commit. Cero fricción, índice siempre actualizado.

---

## [v2.1.1] — 2026-03-19

**INSTALL FIX — APPLIANCE MODE OPERATIVO**

### Fixed

* **`ExecStart` apuntaba a `ddfi2_logger.py`** — corregido a `main.py --no-poweroff`.
  El servicio systemd ahora levanta el stack modular correcto al arrancar.

* **`avahi-daemon` y `python3-flask` no se instalaban** — agregados al `apt install`.
  Sin avahi no hay mDNS (`buell.local`). Sin flask el `WebServer` no arranca.

* **`network_state.json` no se creaba** — el installer ahora escribe el estado
  inicial `{"mode":"hotspot","ip":"10.42.0.1"}` si el archivo no existe.
  Evita comportamiento indefinido en `load_state()` y `get_wifi_ip()` en el primer boot.

* **Usuario hardcodeado a `pi`** — reemplazado por detección dinámica via
  `$SUDO_USER` / `logname` / `whoami`. Compatible con cualquier imagen de Raspberry Pi OS.

---

## [v2.1.0] — 2026-03-18

**MÓDULO DE RED — SWITCH A PRUEBA DE BALAS**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)

* **`network/manager.py`** — módulo independiente de gestión de red.
  Extraído del monolito `ddfi2_logger.py` y reescrito con lógica completa:
  - `get_redirect_url(action)` — calcula la URL destino **antes** de ejecutar
    el switch, permite abrir nueva pestaña en el browser con la IP correcta
  - `_set_switch_status()` / `get_switch_status()` — estado del switch en memoria,
    expuesto via `/wifi/status` para polling desde el browser
  - `_save_state()` / `load_state()` — persiste `{mode, ip, last_wifi_ip}` en
    `network_state.json`; permite recuperar la última IP WiFi conocida aunque
    la Pi haya cambiado de modo
  - `start_monitor()` — thread que vigila la conexión cada 30s y activa hotspot
    si no hay ninguna red activa
  - Fallback automático a hotspot si cualquier switch falla

* **`web/server.py`** — servidor HTTP modular con endpoints completos:
  - `GET /wifi/scan` — escaneo de redes disponibles
  - `GET /wifi/saved` — perfiles guardados en NetworkManager
  - `GET /wifi/status` — modo actual, IP y estado del switch en curso
  - `GET /wifi/redirect_url?action=X` — URL destino antes del switch
  - `POST /wifi/connect` — conectar a perfil guardado
  - `POST /wifi/add` — agregar red nueva y conectar
  - `POST /wifi/forget` — eliminar perfil
  - `POST /network` — switch hotspot↔wifi

* **Switch con redirect URL** — flujo completo a prueba de pérdida de conexión:
  1. Browser pide redirect URL al servidor
  2. Servidor responde con IP destino (conocida del `network_state.json`)
  3. Browser abre nueva pestaña con la URL correcta
  4. Se ejecuta el switch
  5. Modal de transición con cuenta regresiva
  6. Polling cada 2s hasta confirmar `connected`, `fallback` o `failed`
  7. Si falla, alerta al usuario y vuelve a hotspot automáticamente

* **`switchModal`** — div de transición en la pestaña Redes que muestra
  el estado del switch y la URL destino mientras cambia la red

### Fixed

* **`saved_wifi()` no encontraba perfiles** — nmcli devuelve tipo `802-11-wireless`,
  no `wifi`; el filtro anterior nunca matcheaba ningún perfil

* **`web.network = None`** — el `NetworkManager` nunca se conectaba al `WebServer`;
  `/live.json` crasheaba con `AttributeError: 'NoneType'` en cada request

* **`/wifi/scan` era POST en el JS** — el server lo manejaba como GET;
  el escaneo nunca retornaba resultados

* **`updateNetStatus` sin IP** — `fetchLive` pasaba solo el modo, no la IP;
  el label mostraba `WiFi conectado` sin indicar la dirección

* **RED ACTIVA mostraba `--`** — `loadNetPane` no se llamaba al cargar
  el status inicial de red en la pestaña

---

## [v1.16.2] — 2026-03-14
**README — PROJECT DOCUMENTATION**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- Full `README.md`: project description, captured parameters table, hardware diagram,
  installation instructions, generated file structure, protocol notes and license.

---

## [v1.16.1] — 2026-03-13
**REAL-TIME DIAGNOSTICS · AUTO NOTES ON CLOSE · VERSION IN CSV**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **ERR cell in header** — new cell in the dashboard header next to Batt.  
  Shows total errors of the active ride (dirty + timeout) with dynamic color:
  - 🟢 Green: 0–2 errors/min
  - 🟡 Orange: 2–5 errors/min
  - 🔴 Red: >5 errors/min  
  Tooltip details: `Dirty: N  Timeout: N  Serial: N (X.X/min)`

- **`RideErrorLog.counts()`** — new Python method.  
  Returns `{dirty, timeout, serial, total}` from in-memory counters (no disk I/O),
  exposed in every `live.json` update as the `ride_errors` field.

- **Version comment in CSV** — first line of every CSV is now `# logger=v1.16.1`.  
  Allows identifying the capture version without parsing the full file.  
  The JS parser filters `#` lines for full backwards compatibility.

### Fixed
- **SOH retry after dirty buffer** (`_sync_to_soh` / `_flush_and_retry_soh`)

  *Before:* if SOH was not found within 0.5s after a dirty byte, returned `None`
  immediately — the cycle was lost and logged as `dirty_bytes`.
  ```python
  # BEFORE
  recovered = self._sync_to_soh()
  if not recovered: return None   # give up, sample lost
  ```
  *After:* automatic second attempt: flushes the buffer (`reset_input_buffer`),
  re-sends the full `PDU_RT_DATA` and retries SOH search with 0.4s timeout.
  Directly reduces the unrecovered dirty_bytes counter.
  ```python
  # AFTER
  recovered = self._sync_to_soh()
  if not recovered:
      recovered = self._flush_and_retry_soh()   # flush + resend + retry
      if not recovered: return None
  ```

- **Dashboard active in waiting mode** (`_waiting_loop`) — **BUG-2**

  *Before:* while the logger was waiting for the ECU, `update_state()` was never
  called. The browser showed `--` on all indicators (CLT, TPS, KPH, etc.) even
  when the ECU was already responding with RPM=0.

  *After:* `update_state(ride_active=False, live_data={})` is called on every
  iteration of the waiting loop — the dashboard correctly reflects the standby
  state from startup.

- **Notes modal when ride was auto-closed** (`closeRide` JS)

  *Before:* if the ride had been automatically closed by a reconnection event,
  `d.ok=false` and the notes modal never appeared.

  *After:* when `d.ok=false`, the client queries `/rides` and opens the modal
  with the last available ride. The user never loses the chance to document the session.

---

## [v1.16.0] — 2026-03-13
**HTTP IMPROVEMENTS · CHARTS v1.15.1 MERGED**

### Changed
- **`ThreadingHTTPServer`** replaces `HTTPServer`  
  Parallel requests without mutual blocking. Before: downloading a large CSV
  froze `live.json` updates because the server was single-threaded.

- **Automatic gzip on CSV download**  
  If the browser sends `Accept-Encoding: gzip`, the server compresses with
  `zlib` level 6. Transfer reduction 5–10x over WiFi. Transparent to the client.

- **`Cache-Control: no-store`** on all JSON responses  
  Double anti-cache guard: base `_json()` header + explicit header on `/live.json`.
  Fixes stale data on Safari/iOS.

### Fixed
- **Resource leaks in file reads**  
  8 instances of `json.load(open(...))` and `csv.DictReader(open(...))` replaced
  by `with open(...) as f`. Files are properly closed even if an exception occurs
  during reading.

- **Silent JSON parse errors on POST**  
  *Before:* invalid POST body silently set `payload={}`.  
  *After:* `logging.warning(f"Invalid JSON: {err} — body={body[:80]!r}")` for debugging.

- **Keepalive spam from multiple tabs**  
  Rate limiting: maximum 1 keepalive accepted every 10 seconds.

---

## [v1.15.1] — 2026-03-13
**REDESIGNED CHARTS — 5 CHARTS WITH MERGED AXES**

### Changed — Chart architecture (full redesign)

Removed `chartCLT` and `chartAFV` as independent charts.  
Result: 5 charts instead of 7, more information per chart, less scrolling.

| # | Canvas | Content | Axes |
|---|--------|---------|------|
| G1 | `chartRPM` h=120 | RPM · KPH · CLT°F | Triple: RPM left, KPH right, CLT°F 2nd right |
| G2 | `chartFuel` h=100 | EGO Corr · AFV · WUE · **Average** | Single % with dynamic range |
| G3 | `chartTPS` h=85 | TPS% | Left 0–100% |
| G4 | `chartSPK` h=95 | Spark1/2 °BTDC · PW1/2 ms | °BTDC left, ms right |
| G5 | `chartBatt` h=70 | Batt V | Auto ±0.3V with 12.5V reference line |

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **G2: Average line** — `(EGO + AFV + WUE) / 3` per sample, thick white dashed line.
  Shows the actual net fuel correction without the 3 curves visually canceling each other.
- **G1: 250°F threshold line** — visual reference for critical temperature on the CLT curve.
- **G4: Pulse Width** — `pw1` and `pw2` on right axis (ms). Allows visual correlation
  of ignition advance with injector pulse duration cycle by cycle.
- **G4: Spark=0° marker** — red dots when `spark1=0` and `fl_decel=0`. Identifies
  ECU-forced retard under `fl_hot=1` (confirmed behavior, not a parser artifact).
- **G1: fl_hot and fl_kill markers** — moved here from the former standalone CLT chart.
- **G2: Rich/Lean markers** — on the EGO curve when it crosses thresholds.

---

## [v1.15.0] — 2026-03-12
**GEAR DETECTION · AUTO TPS CAPTURE · FT232RL LATENCY TIMER · VSS_RPM_RATIO**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Gear detection** — `Gear` field (0=neutral/unknown, 1–5) calculated in
  `parse_rt_data()` from the `VS_KPH / (RPM/1000)` ratio compared against
  `GEAR_THRESHOLDS` for the stock XB12X transmission. Requires RPM>500 and
  VS_KPH>3. Displayed in header as `1st`–`5th` or `N`.

- **VSS_RPM_Ratio** — new field in CSV (offset 100, 1 byte).  
  Internal ratio calculated by the ECU for spark reduction at high speed.
  Confirmed in BUEIB.xml offset=405.

- **FT232RL latency timer** — on connect, attempts to set the latency timer to
  2ms via sysfs (`/sys/bus/usb-serial/devices/ttyUSB*/latency_timer`).
  Reduces serial response latency from 16ms to 2ms. Silent if path not found.

- **Automatic TPS capture** — "⏺ Auto Capture (10s)" button in Config tab.  
  Polls `live.json` every 500ms for 10s, records min/max of `TPS_10Bit` and
  auto-fills the calibration fields. Requires range >20 to be considered valid.

---

## [v1.14.0] — 2026-03-12
**DATE IN CHARTS · VE HEATMAP SORTED · USB RESET · FIX SESSIONS→CHART**

### Fixed
- **VE heatmap RPM unsorted** (`showMap` JS)

  *Before:* the heatmap X axis showed RPM periods in EEPROM order (random),
  making the table unreadable.

  *After:* `period → real RPM (60,000,000 / period)`. Columns with period=0
  are discarded. Sorted ascending left→right. Empty cells shown as `·` on dark background.

- **Race condition Sessions→Chart** (`openRideGraph` / `openLiveRideGraph` JS)

  *Before:* the [Chart] button depended on the dropdown select, which might not
  be synced yet → showed the wrong ride.

  *After:* `r.filename` is passed directly to `loadGraphRide()` bypassing the select.

- **`close_reason` missing in summary JSON**  
  The real field in the JSON is `"reason"`, not `"close_reason"`. Fixed with fallback:  
  `summary.get("reason", summary.get("close_reason", ""))`.

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Date and duration in chart selector** — each ride in the dropdown shows
  `YYMMDDHHMM · Xmin · N samples`.

- **FT232RL USB Reset** (`usb_reset` / `_reading_loop`)  
  Automatic escalation at 60s of ECU loss: finds the FT232RL in sysfs
  (vendor=0403 product=6001) and does `authorized=0 → sleep(0.8) → authorized=1 → sleep(2.0)`.
  Equivalent to physically unplugging and replugging the USB adapter.

- **`opened_utc` in summary JSON** — records the UTC timestamp of ride start
  for correct date calculations in the frontend.

---

## [v1.13.1] — 2026-03-11
**ERRORLOG CONTEXT · AUTOMATIC HARD RECONNECT**

### Fixed / Changed
- **Automatic hard reconnect at 30s** (`_reading_loop`)

  *Before:* reconnection after ECU loss only attempted a soft `get_version()`.
  If the FT232RL was in a hung state, it never recovered.

  *After:* at 30s of loss, performs a full `disconnect()` + `connect()` (DTR toggle)
  even with an active ride. Logged in the errorlog with `trigger="auto_30s"`.
  Soft VERSION logic remains as fallback when no ride is active.

- **Enriched context in errorlog** (`RideErrorLog.update_last_sample`)  
  Each event now includes a snapshot of `{vss, seconds, fl_learn}` in addition
  to existing fields. Makes it easier to correlate errors with bike state.

---

## [v1.13.0] — 2026-03-10
**RIDE ERROR LOG — STRUCTURED ERROR RECORDING**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **`RideErrorLog`** — new class that records communication error events per ride.  
  File `ride_NNN_errorlog.json` is created only if errors occurred.
  Clean ride = no file = immediate diagnosis.

  Recorded event types:
  | Type | Trigger |
  |------|---------|
  | `serial_exception` | exception on serial port |
  | `dirty_bytes` | dirty byte before SOH |
  | `bad_checksum` | incorrect RT checksum |
  | `ecu_timeout` | no response every 10s |
  | `ecu_reset` | ECU `Seconds` field goes backwards |
  | `reconnect_attempt` | reconnection attempt |

- **Error badge** in ride list: `🔴N` next to the ride if it has an errorlog.  
  Tooltip shows summary: `3 serial  2 dirty  1 timeout`.

- **`_flush_ride()` helper** — single point for ride close + errorlog flush.  
  Replaces all scattered direct `session.close_current_ride()` calls.

---

## [v1.12.1] — 2026-03-10
**MINOR VISUAL FIXES**

### Fixed
- `graphRideTitle` invisible when hidden under the chart scroll area → moved before `graphStatus`.
- `replace('_',' ')` → `replace(/_/g,' ')` — replaces **all** underscores, not just the first one.

---

## [v1.12.0] — 2026-03-10
**VE HEATMAP · ACTIVE RIDE BANNER · STATUS INDICATOR**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **VE Heatmap** in VE tab — 4 real EEPROM maps: Fuel Front/Rear, Spark Front/Rear.
  RPM and TPS axes, blue→red color scale by value. Active cell highlighted in real time.
- **Active ride banner** in Sessions tab with timer and "View Chart" button.
- **Pill indicator** — blinking green/yellow dot in header (no "IN RIDE" text).
- **`graphRideTitle`** — shows the name of the ride currently loaded in the chart.

---

## [v1.11.2] — 2026-03-10

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Battery chart** — `chartBatt`, height 70px. Auto Y axis from ride min/max ±0.3V.
  12.5V reference line.
- **WUE in AFV chart** — `WUE` added to the corrections chart as a dashed orange series.

---

## [v1.11.1] — 2026-03-10

### Fixed
- **Silent crash on serial exception** (`_reading_loop`)

  *Before:* an exception in `get_rt_data()` could terminate the loop without
  reaching the `waiting` state or activating the "Force reconnect" button —
  the logger died silently.

  *After:* `try/except` around `get_rt_data()` with correct fallthrough to the
  consecutive error counter.

- **`_force_reconnect` flag ignored during timeout**  
  *Before:* the flag was checked after `get_rt_data()`, which could block on
  timeout for up to 0.3s.  
  *After:* the flag is checked at the start of each iteration, before any I/O.

- **EGO 100% dashed reference line** — horizontal dataset on the TPS%/EGO chart
  as a visual closed-loop reference.

---

## [v1.11.0] — 2026-03-09
**SESSIONS REDESIGN · RIDE NOTES · USAGE TRACKER**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **"Sessions" tab** (formerly "Rides") — rides grouped by session/checksum,
  collapsible, sorted most recent first. `[View]` `[Chart]` `[📝]` buttons per ride.
- **Notes modal** — textarea per ride (`ride_NNN_notes.txt`). Auto-opens when
  closing a ride (800ms delay).
- **Usage Tracker** — usage counter per function (buttons, tabs). Visible in
  Config tab with count bars and download/reset option.

---

## [v1.10.3] — 2026-03-09

### Fixed
- `BUEIB_PARAMS`: `Fan_On/Off translate 200→50` (was showing 370°/330°C instead of 220°/180°C).
- `Fan_KO_On/Off translate 200→0` — same fix.
- `LOGGER_VERSION` moved to a single constant (previously duplicated in multiple places).

---

## [v1.10.1] — 2026-03-08
**WiFi NETWORK MANAGEMENT · FIX DURATION_S**

### Added- ANL12: added /tuning_report HTTP endpoint — reads tuning_report_{session}.json from the session directory and returns it as JSON- ANL7: added health_score (0-100) to ride summary JSON — computed from warmup (40pts), valid data ratio (30pts), and AFV proximity to 100 (30pts)
- **Networks tab** — WiFi scan, connect/forget networks, hotspot/WiFi switch from the dashboard.

### Fixed
- **Incorrect `duration_s`** in summary JSON  
  *Before:* used `time.monotonic()` at close — if the ride had pauses or
  reconnections, the time was wrong.  
  *After:* uses `last_elapsed_s` (actual accumulated time of data written to CSV).


---

- **Bug #14: No threading locks on shared state** — Added `threading.RLock()` in `web/server.py` (`_data_lock`) protecting `serial_stats`, `ecu_live`, `gps`, and `eeprom_maps` from concurrent access by HTTP threads, ECU loop, and sysmon loop. Used via `self.web._data_lock` in main.py.

<!-- CHANGELOG_TAIL
  You are reading the BOTTOM of the changelog.
  The MOST RECENT entries are at the TOP of this file.
  If you used tail to read this, go to head for the latest version.
  Current latest version: check ## [v2.7.XX] at the top.
  To read latest: head -50 /home/pi/buell/CHANGELOG.md
-->

