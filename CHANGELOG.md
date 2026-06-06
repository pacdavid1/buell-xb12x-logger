# Changelog

<!-- PROMPT_START — read ALL instructions until PROMPT_END before doing anything.
  If you only see part of this block (e.g. via head -5), scroll or read further —
  there are more instructions below.

  INSTRUCTIONS FOR AI ASSISTANTS:
  1. All changelog entries MUST be written in English.
  2. Each new entry follows this format:
       ## [vX.Y.Z] — YYYY-MM-DD
       ### Changed / Added / Fixed / Removed
       - file: description of change
       ### AI
       - <AI name and provider> (e.g. "Claude Sonnet 4.6, Anthropic")
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

## [v2.7.16] — 2026-06-06

### Added
- web/proposal.py: smoothing integration (task 014) — IDW + Laplacian applied
  to delta_fuel_front and delta_fuel_rear. Returns both raw and smoothed deltas.
  signal_mask built from source grid (not delta values).

### Docs
- BACKLOG.md: added PROP_* session output spec from freebuff task 015.
  encode_eeprom_maps() in ecu/eeprom.py. Tuner needs session_metadata.json
  (scans sessions/*/session_metadata.json, not eeprom_decoded.json).

## [v2.7.16] — 2026-06-06

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

## [v2.6.27] - 2026-05-26
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
- Claude Sonnet 4.6, Anthropic

## [v2.6.20] — 2026-05-24
### Changed
- web/server.py: refactored monolithic do_GET (~26 routes) and do_POST (~12 routes)
  into named _handle_* methods with clean dict-based dispatchers.
  Each route block keeps its exact original logic — zero behavioral changes.
- do_GET: dict dispatcher for exact matches + if/elif chain for prefix routes
  (static, csv, ride, errorlog, wifi/redirect_url).
- do_POST: dict dispatcher dispatching to _handle_post_* methods.

## [v2.6.20] — 2026-05-24
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
