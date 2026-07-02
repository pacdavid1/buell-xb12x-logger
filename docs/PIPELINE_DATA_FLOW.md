# Pipeline Data Flow — Buell Logger / Tuner

> DEV NOTE: All code, comments, and variable names must be in English.
> This document maps the DATA pipeline (not the code structure — see `graphify-out/` for that).
> It exists so the tuning-cycle mental model (`LOG → ACOTAR → COMPARAR → PROPONER → QUEMAR`)
> can be inspected as a graph: what raw data is captured, what gets used vs. sits idle,
> and how far the current pipeline is from the project's north star.

## 1. Framing

The bike has no dyno and no wideband O2 sensor — every ride is the only instrument.
`ecu/session.py` (`SessionManager`) writes one CSV row per ~125ms ECU frame plus GPS/env
sensor fields, and closes each ride into a `ride_*_summary.json` with per-cell VE-map
coverage. From there the pipeline splits into a live branch (Dashboard, `CellTracker`,
real-time cell coverage) and a post-ride analysis branch that reads the closed CSVs.
`web/f7.py` (FASE7) detects discrete acceleration/deceleration events per ride and
clusters them by injector pulse-width (PW) shape (DTW); `web/launch.py` /
`web/vs_engine.py` (Sessions VS) instead aggregate cruise samples into RPM×TPS cells and
compare two sessions cell-by-cell. Both branches feed the Tuner page (`web/handlers/tuner.py`,
`_merge_maps`), which is today the only PROPONER mechanism — a manual, per-cell
SWEET/SPICY winner-take-cell merge, not the unified statistically-gated proposal engine
described as FASE 6. QUEMAR (`web/burn_ledger.py`) only records burns after the fact; it
never writes to the ECU itself. The system runs in Open-Loop mode without a wideband
sensor, so `EGO_Corr`/`AFV`-derived artifacts (`tuning_report_*.json`) are architecturally
declared inactive noise, while PW- and TPS-based artifacts (F7, Sessions VS `dpw`) are the
only currently-trusted signal — with hygiene caveats detailed in the gap section below.

## 2. NODE list

Format: `NODE | id | type | file:function_or_line | reliability | note`

### 2.1 Raw signal / sensor groups (ecu/protocol.py CSV_COLUMNS, ecu/session.py)

```
NODE | raw_ecu_core        | raw_signal | ecu/protocol.py:CSV_COLUMNS (RPM,Load,TPD,TPS_10Bit,TPS_pct,VS_KPH,Gear) | ACTIVE_VALID   | Alpha-N inputs: TPS+RPM drive fueling; VS_KPH from calibrated VSS counts; Gear from GearFilter (statistical, 3s window)
NODE | raw_ecu_fuel        | raw_signal | ecu/protocol.py:CSV_COLUMNS (pw1,pw2,veCurr1_RAW,veCurr2_RAW)       | ACTIVE_VALID   | Injector pulse-width — "what the injector actually did"; primary physics signal for F7 and Sessions VS
NODE | raw_ecu_spark       | raw_signal | ecu/protocol.py:CSV_COLUMNS (spark1,spark2)                        | ACTIVE_VALID   | Read/logged and diffed (dspk1/dspk2) in Sessions VS, not yet fed into any spark-tuning stage (no spark FASE 6 equivalent exists)
NODE | raw_ecu_ego_afv     | raw_signal | ecu/protocol.py:CSV_COLUMNS (EGO_Corr,AFV)                          | INACTIVE_NOISE | Locked at 100.0 always — narrowband EGO physically disconnected, OL mode. Rule: no feature may depend on these until WB sensor installed
NODE | raw_ecu_enrich      | raw_signal | ecu/protocol.py:CSV_COLUMNS (WUE,Accel_Corr,Decel_Corr,WOT_Corr,Idle_Corr,OL_Corr) | ACTIVE_VALID | ECU-generated (not O2-derived); WUE/AE used as CellTracker validity filters
NODE | raw_ecu_temp        | raw_signal | ecu/protocol.py:CSV_COLUMNS (CLT,MAT)                              | ACTIVE_VALID   | CLT gates tuning validity (>=70C) and classify() flavor (BITTER if <170F); MAT logged, only descriptive today
NODE | raw_ecu_batt        | raw_signal | ecu/protocol.py:CSV_COLUMNS (Batt_V)                               | CAPTURED_UNUSED | Logged every sample; used only as RideErrorLog context. BL-DI-01 (BACKLOG_DATASET_INSIGHTS): injector dead-time varies 0.1-0.2ms/V with Batt_V — same magnitude as dpw deltas Sessions VS treats as map differences. Not yet used as a cell-matching confounder correction
NODE | raw_ecu_o2adc       | raw_signal | ecu/protocol.py:CSV_COLUMNS (O2_ADC)                               | CAPTURED_UNUSED | Raw ADC logged and aggregated (o2_adc_avg) in tuning_report cells, but tuning_report itself is INACTIVE_NOISE downstream
NODE | raw_ecu_flags       | raw_signal | ecu/protocol.py:decode_rt_packet (fl_*, do_*, di_* bit flags)      | ACTIVE_VALID   | fl_wot/fl_decel/fl_fuel_cut/fl_hot gate CellTracker validity, F7 event trimming, VDYNO segment extraction, launch detection
NODE | raw_ecu_diag        | raw_signal | ecu/protocol.py:CSV_COLUMNS (CDiag0-4,HDiag0-4)                    | CAPTURED_UNUSED | Diagnostic counters logged, no downstream consumer; IDEAS.md IDEA-005 proposes fault-mining, not implemented
NODE | raw_ecu_dirty_bytes | raw_signal | ecu/protocol.py:CSV_COLUMNS (dirty_byte_hex,dirty_byte_name,forensic_event) | CAPTURED_UNUSED | Serial-corruption forensics logged per-row; consumed only informally (manual debugging), no automated report
NODE | raw_gps             | sensor     | gps/reader.py -> CSV_COLUMNS (gps_lat,gps_lon,gps_alt_m,gps_speed_kmh,gps_heading,gps_satellites,gps_valid,gps_mode,gps_epx,gps_epy,gps_epv,gps_snr_avg,gps_heading_rate,gps_turning,gps_stale) | ACTIVE_UNVALIDATED | Absolute altitude has ~±10m per-session bias (documented in gps/slope_reference.py docstring); quality-gated via gps_epv/mode/sats (_gps_quality / _is_quality_fix) before any use
NODE | raw_env_baro        | sensor     | sensors (baro) -> CSV_COLUMNS (baro_hPa,baro_temp_c)               | ACTIVE_UNVALIDATED | Used for VDYNO SAE J1349 air-density correction (bug-fixed v2.7.163+) AND for a PW baro-normalization in f7.py/launch.py that contradicts CLAUDE.md's explicit "do NOT normalize PW by baro for DDFI2 Alpha-N" rule — see gap section
NODE | raw_env_humidity    | sensor     | sensors/aht20.py -> CSV_COLUMNS (humidity_pct)                    | CAPTURED_UNUSED | Logged and averaged into F7 event context (humidity_avg) but not read by any comparison or proposal logic
NODE | raw_sys_health      | sensor     | main.py -> CSV_COLUMNS (ttl_pct,cpu_pct,cpu_temp,mem_pct,buf_in)  | ACTIVE_VALID   | System health telemetry, consumed by system_health.json / Dashboard only, not tuning-relevant by design
NODE | raw_imu             | sensor     | (not present in CSV_COLUMNS)                                       | DESIGN_ONLY    | BACKLOG_MAPA_3D / IDEAS reference MPU6050 vibration (FASE 3) and lean-angle analytics (BL-DI-09) — no IMU hardware/fields exist yet in the schema
```

### 2.2 Per-ride / per-session JSON artifacts

```
NODE | ride_csv            | json_artifact | ecu/session.py:SessionManager._open_csv_part / write_sample        | ACTIVE_VALID    | One row per ECU frame (~8Hz); source of truth for every downstream analysis stage
NODE | ride_summary_json   | json_artifact | ecu/session.py:close_current_ride                                   | ACTIVE_UNVALIDATED | Per-cell (RPM×Load) time/EGO/CLT/AFV aggregation from live CellTracker snapshot; drives objectives.json coverage %, health_score; ego_avg fields inside are NOISE (OL mode)
NODE | session_metadata_json | json_artifact | ecu/session.py:_load_or_create / _save_metadata                  | ACTIVE_VALID    | checksum, version_string, total_rides/samples, rpm_min/max_seen — read by nearly every handler (tuner sessions list, sessions_vs, vdyno)
NODE | rider_notes_field   | annotation    | ecu/session.py:_load_or_create (session_metadata["rider_notes"]=[]) | CAPTURED_UNUSED | Field is initialized empty on every new session. No write endpoint exists anywhere in web/server.py or handlers/. No read/UI consumer either. Proposed in BACKLOG.md ("agregar campo rider_notes... opciones normal/knock_heard") but never wired end-to-end — fully dead on both sides
NODE | ride_annotations_json | annotation | web/server.py:_handle_post_annotations / _handle_annotations, captured via GRAF2 (web/static/graf2.js:annotationsPlugin) | ACTIVE_UNVALIDATED | Rider marks time regions with type in {launch, diagnostic, note} (unclassified = amber warning in UI). Full CRUD via POST /annotations
NODE | eeprom_bin          | json_artifact | ecu/session.py:save_eeprom                                         | ACTIVE_VALID    | Always present per session; canonical source for map decode (do NOT require eeprom_decoded.json per CLAUDE.md data-reuse rule)
NODE | eeprom_decoded_json | json_artifact | ecu/eeprom.py:decode_eeprom_maps / decode_eeprom_maps_full (XML-driven via ecu/ecm_defs.py) | ACTIVE_VALID | Multi-firmware map decode (fuel_front/rear, spark_front/rear, axes); optional cache, not required
NODE | ride_errorlog_json  | json_artifact | ecu/session.py:RideErrorLog.flush                                   | ACTIVE_VALID    | Serial exceptions, dirty bytes, bad checksums, ECU timeouts/resets — diagnostic only, feeds errorlog_viz.html, not the tuning cycle
NODE | tuning_report_json  | json_artifact | ecu/session.py:_update_tuning_report                                | INACTIVE_NOISE  | Runs on EVERY ride close regardless of OL mode; computes ego_avg-based VE "suggestions" that are meaningless with EGO_Corr locked at 100. CLAUDE.md explicitly marks this ⛔ INACTIVE, yet the computation still executes and writes a file every ride
NODE | suggested_msq       | json_artifact | ecu/session.py:_generate_suggested_msq                              | INACTIVE_NOISE  | Auto-generated from tuning_report suggestions — inherits the same EGO-based noise; a burnable MSQ file built entirely from a signal that doesn't exist in OL mode
NODE | ride_f7events_json  | json_artifact | web/f7.py:_f7_load_session_clusters (per-ride cache)                | ACTIVE_VALID    | Cached per ride, regenerated when CSV is newer or schema version (_F7_EVENTS_V) bumps
NODE | session_f7clusters_json | json_artifact | web/f7.py:_f7_load_session_clusters                             | ACTIVE_VALID    | DTW-clustered accel/decel events (A/D prefixes) + pilot-marked clusters (P prefix, from launch annotations)
NODE | ride_vdyno_json     | json_artifact | web/vdyno.py:compute_ride                                          | ACTIVE_UNVALIDATED | Per-RPM-bin HP/torque from WOT segments; differential instrument (A-vs-B meaningful, absolute HP approximate); constants mass_kg/CdA/Crr/rho are fixed config defaults, not calibrated per BL-DI-03 (coastdown fitting still [PLAN])
NODE | ride_vdyno_rows_json | json_artifact | web/vdyno.py:compute_ride_rows                                     | ACTIVE_UNVALIDATED | Sparse per-row HP/torque overlay for ride chart, same physics/caveats as ride_vdyno_json
NODE | sessions_vs_cache   | json_artifact | web/vs_engine.py:_compare_sessions_cached (CACHE_VERSION=9)         | ACTIVE_UNVALIDATED | Cell-level A-vs-B delta cache; GAP1 Welch 95% CI (dpw_eff_sig) computed here but NOT yet consumed by any downstream gating (see gap section); contaminated by unaddressed Batt_V/thermal confounders (BACKLOG_DATASET_INSIGHTS Phase A, all [PLAN])
NODE | slope_reference_json | json_artifact | gps/slope_reference.py:SlopeReference._save                       | CAPTURED_UNUSED | Differential GPS altitude accumulator (BL-GPS-05); only updated via manual GET /slope_reference?update=... — no automatic trigger on ride close; get_slope_pct() is never called from f7.py or vs_engine.py despite GAP4 backlog explicitly proposing this wiring
NODE | gear_profile_json   | json_artifact | web/gear_learner.py:GearLearner._save                              | ACTIVE_VALID    | Data-driven RPM/VSS ratio thresholds, learned from ECU-reported Gear column across all sessions; consumed by gear_detect.detect_gear via thresholds param
NODE | burns_json          | json_artifact | web/burn_ledger.py:record_burn                                     | ACTIVE_VALID    | Append-only parent→child checksum lineage with per-cell diffs; only written after a verified burn, never writes to ECU itself
NODE | route_reference_json | json_artifact | gps/route_reference.py (GPS altitude trust reference)              | ACTIVE_UNVALIDATED | Enriches gps_analysis handler output with trusted reference altitude (BL-GPS-04); separate accumulator from slope_reference, also manually triggered
NODE | live_json           | json_artifact | main.py (IPC) -> web/server.py:_get_live/_handle_live_json          | ACTIVE_VALID    | Live RT state polled every 0.25s by the Dashboard; not persisted for analysis, ephemeral
NODE | objectives_json     | json_artifact | objectives.json + ecu/session.py cell_targets coverage check        | ACTIVE_VALID    | Static config of RPM/Load coverage goals; drives Dashboard "objectives" progress bars
NODE | fuel_consumption_cache | json_artifact | web/fuel_tracker.py:save_ride_consumption_cache                  | ACTIVE_VALID    | Persisted per ride close to avoid CSV re-scan; feeds fuel.html, not the tuning cycle
```

### 2.3 Analysis stages / engines

```
NODE | cell_tracker        | analysis_stage | ecu/session.py:CellTracker.update  | ACTIVE_VALID    | Live per-cell bilinear-weighted accumulation (seconds, ego, valid_seconds, flavor_counts); runs every sample during a ride
NODE | f7_event_detect     | analysis_stage | web/f7.py:_f7_detect_events        | ACTIVE_VALID    | Stable-bucket-then-break detector (rolling std over 3s); pure PW/TPS physics, no EGO dependency
NODE | f7_dtw_cluster      | analysis_stage | web/f7.py:_f7_cluster / _f7_dtw     | ACTIVE_VALID    | Complete-linkage DTW clustering on PW curves, sub-divided by Bucket-A consistency (gear/RPM/VSS/TPS)
NODE | f7_cross_session_match | analysis_stage | web/f7.py:_f7_match_cross_session | ACTIVE_VALID  | TPS-curve DTW matches clusters across sessions; PW delta at matched points is the "which map accelerates better" signal
NODE | f7_pilot_marked     | analysis_stage | web/f7.py:_f7_events_from_annotations | ACTIVE_VALID | Builds F7-shaped events directly from type=launch annotations (F7 Phase 2.2, "juntas pero no revueltas" — pooled but tagged separately, P-prefix clusters)
NODE | vs_classify         | analysis_stage | web/launch.py:classify()            | ACTIVE_UNVALIDATED | Buckets every sample into SWEET/SPICY_TIPIN/SPICY_TIPOUT/SPICY_WOT/SALTY_UP/SALTY_DOWN/BITTER; does NOT exclude fl_hot/do_fan thermal-protection samples (BL-DI-06, [PLAN]) or correct for Batt_V (BL-DI-01, [PLAN])
NODE | vs_baro_normalize   | analysis_stage | web/launch.py:load_csv (pw1_norm/pw2_norm = pw * REF_BARO/baro) | INACTIVE_NOISE (contradicts doctrine) | Applies Speed-Density-style baro correction to PW before every Sessions VS comparison, directly contradicting CLAUDE.md's Alpha-N rule ("do NOT normalize PW by baro for DDFI2"). Feeds dpw1/dpw2/dpw_eff — the metrics the OL reliability table calls ✅ VALID
NODE | vs_cell_index       | analysis_stage | web/launch.py:build_index()          | ACTIVE_UNVALIDATED | Welford-online per-cell mean/std for pw/spark/afv/dvss/pw_eff; MIN_N=5 gate; feeds GAP1 significance calc
NODE | vs_gap1_significance | analysis_stage | web/launch.py:_compare_sessions (Welch 95% CI block) | ACTIVE_UNVALIDATED | dpw_eff_se/ci_lo/ci_hi/dpw_eff_sig computed per cell (v2.7.230); UI attenuates non-significant cells in sessions_vs.html, but CI treats autocorrelated samples as independent N (acknowledged optimistic in BACKLOG.md GAP1 remaining item)
NODE | vs_gap5_convergence | analysis_stage | web/vs_engine.py:compute_convergence | ACTIVE_VALID    | DONE v2.7.253. Residual variance of dpw_eff across consecutive session pairs; converged when last 3 pairs < 0.002 threshold. Not yet surfaced in Tuner UI (badge pending)
NODE | vs_merge_maps       | analysis_stage | web/vs_engine.py:_merge_maps         | ACTIVE_UNVALIDATED | Current PROPONER mechanism: per-cell winner-take-cell between two eeprom maps based on SWEET/SPICY_WOT flavor sign of dpw_eff/ddvss. Does NOT check dpw_eff_sig (GAP1 significance) before picking a winner — the gate that should exist is not wired
NODE | launch_detect       | analysis_stage | web/launch.py:detect_launches        | ACTIVE_VALID    | Legacy dtps>8 threshold detector (CLAUDE.md: "old approach... Everything new should use F7"); still the only source for cluster_launches/vdyno_launch
NODE | launch_cluster      | analysis_stage | web/launch.py:cluster_launches       | ACTIVE_VALID    | Groups launches by pre-conditions only (gear/rpm/tps), outcome metrics intentionally excluded from clustering to avoid bias
NODE | launch_cross_match  | analysis_stage | web/launch.py:match_clusters         | ACTIVE_VALID    | Matches launch clusters across sessions by Euclidean distance in (rpm,spd,tps); feeds sessions_launch.html (being migrated to F7 per backlog 7.8)
NODE | vdyno_physics        | analysis_stage | web/vdyno.py:_seg_physics             | ACTIVE_UNVALIDATED | F=ma+drag+rolling; SAE J1349 correction applied (bug-fixed v2.7.163, was silently skipped due to IAT vs IAT_Corr field-name mismatch); mass_kg/CdA/Crr are fixed config, not measured (BL-DI-03 coastdown calibration still [PLAN])
NODE | vdyno_compare        | analysis_stage | web/vdyno.py:compare_sessions         | DESIGN_ONLY (partial) | Returns delta_kw/delta_hp/delta_pct per RPM bin with NO noise-floor gating and no VERDE/ROJO/GRIS verdict — BACKLOG_VDYNO.md's noise-floor rule ("measure ride-to-ride variance within the same map first, only declare VERDE/ROJO if |delta| > 2*sigma of that floor") is designed but not implemented in code
NODE | vdyno_fase_v4        | analysis_stage | BACKLOG_VDYNO.md "FASE V4 — Optimizador Iterativo de Mapas (el norte completo)" | DESIGN_ONLY | Autonomous proposal engine combining vdyno + VS cells + burn ledger causal history; explicitly documents that autonomous burning stays OUT of scope even at V4 — human always loads/burns the proposal manually
NODE | gear_learner_fit    | analysis_stage | web/gear_learner.py:GearLearner._fit  | ACTIVE_VALID    | Brute-force per-boundary threshold fit from ECU-reported Gear ground truth, bike-agnostic
NODE | fase6_unified_proposal | analysis_stage | CLAUDE.md priority backlog #1, BACKLOG.md "FASE 6 -- Propuesta de mapa desde Sessions VS" | DESIGN_ONLY | The unified F7 + Sessions VS -> EEPROM proposal engine described as the core of PROPONER does not exist yet; _merge_maps is a stand-in
```

### 2.4 UI pages

```
NODE | ui_dashboard        | ui_page | web/templates/index.html            | ACTIVE_VALID | LOG stage — live ECU data, session/ride management, VE tab burn UI, fuel status widget
NODE | ui_session_events   | ui_page | web/templates/session_events.html   | ACTIVE_VALID | ACOTAR + COMPARAR(events) — F7 cluster browser, cross-session ΔPW/ΔVSS
NODE | ui_sessions_vs      | ui_page | web/templates/sessions_vs.html      | ACTIVE_UNVALIDATED | COMPARAR(cells) — SWEET/SPICY/BITTER delta grid, attenuates non-significant (dpw_eff_sig=False) cells, embeds VDYNO compare tab
NODE | ui_tuner            | ui_page | web/templates/tuner.html            | ACTIVE_UNVALIDATED | PROPONER — map diff/merge UI, convergence badge (GAP5), burn trigger
NODE | ui_map_editor       | ui_page | web/templates/map-editor.html       | ACTIVE_VALID | Manual cell-by-cell VE map edit + burn, independent of the auto-proposal path
NODE | ui_sessions_launch  | ui_page | web/templates/sessions_launch.html  | ACTIVE_UNVALIDATED | Being migrated to consume F7 clusters instead of legacy detect_launches (backlog 7.8, not done)
NODE | ui_launch_power     | ui_page | web/templates/launch_power.html     | ACTIVE_UNVALIDATED | VDYNO launch-cluster HP/torque view
NODE | ui_errorlog_viz     | ui_page | web/templates/errorlog_viz.html     | ACTIVE_VALID | Diagnostic tool, explicitly NOT part of the tuning cycle per CLAUDE.md
NODE | ui_gps_analysis     | ui_page | web/templates/gps_analysis.html     | ACTIVE_VALID | 3D replay + 2D Leaflet + quality-strip cache; consumes /gps_analysis_data
NODE | ui_graf2            | ui_page | web/templates/graf2.html            | ACTIVE_VALID | uPlot pro telemetry viewer; the actual annotation-capture surface (region markers, type selector)
NODE | ui_fuel             | ui_page | web/templates/fuel.html             | ACTIVE_VALID | Consumption/reserve/refuel tracking, independent of the tuning cycle
```

## 3. EDGE list

Format: `EDGE | from_id | to_id | label`

```
EDGE | raw_ecu_core | ride_csv | computed_from
EDGE | raw_ecu_fuel | ride_csv | computed_from
EDGE | raw_ecu_spark | ride_csv | computed_from
EDGE | raw_ecu_ego_afv | ride_csv | computed_from
EDGE | raw_ecu_enrich | ride_csv | computed_from
EDGE | raw_ecu_temp | ride_csv | computed_from
EDGE | raw_ecu_batt | ride_csv | computed_from
EDGE | raw_ecu_o2adc | ride_csv | computed_from
EDGE | raw_ecu_flags | ride_csv | computed_from
EDGE | raw_ecu_diag | ride_csv | computed_from
EDGE | raw_ecu_dirty_bytes | ride_csv | computed_from
EDGE | raw_gps | ride_csv | computed_from
EDGE | raw_env_baro | ride_csv | computed_from
EDGE | raw_env_humidity | ride_csv | computed_from
EDGE | raw_sys_health | ride_csv | computed_from
EDGE | raw_imu | ride_csv | not_consumed_by

EDGE | ride_csv | cell_tracker | feeds_into
EDGE | cell_tracker | ride_summary_json | computed_from
EDGE | ride_summary_json | tuning_report_json | feeds_into
EDGE | raw_ecu_ego_afv | tuning_report_json | feeds_into
EDGE | tuning_report_json | suggested_msq | computed_from
EDGE | eeprom_decoded_json | suggested_msq | feeds_into
EDGE | ride_summary_json | objectives_json | feeds_into
EDGE | ride_csv | fuel_consumption_cache | computed_from
EDGE | ride_csv | ride_errorlog_json | feeds_into

EDGE | ride_csv | f7_event_detect | feeds_into
EDGE | raw_gps | f7_event_detect | feeds_into
EDGE | raw_env_baro | f7_event_detect | feeds_into
EDGE | f7_event_detect | ride_f7events_json | computed_from
EDGE | ride_f7events_json | f7_dtw_cluster | feeds_into
EDGE | ride_annotations_json | f7_pilot_marked | feeds_into
EDGE | f7_pilot_marked | session_f7clusters_json | feeds_into
EDGE | f7_dtw_cluster | session_f7clusters_json | computed_from
EDGE | session_f7clusters_json | f7_cross_session_match | feeds_into
EDGE | f7_cross_session_match | ui_session_events | displayed_in

EDGE | ride_csv | vs_baro_normalize | feeds_into
EDGE | raw_env_baro | vs_baro_normalize | feeds_into
EDGE | vs_baro_normalize | vs_classify | feeds_into
EDGE | raw_ecu_flags | vs_classify | feeds_into
EDGE | raw_ecu_temp | vs_classify | feeds_into
EDGE | vs_classify | vs_cell_index | feeds_into
EDGE | raw_ecu_batt | vs_cell_index | not_consumed_by
EDGE | vs_cell_index | vs_gap1_significance | feeds_into
EDGE | vs_gap1_significance | sessions_vs_cache | computed_from
EDGE | vs_cell_index | sessions_vs_cache | computed_from
EDGE | launch_detect | sessions_vs_cache | feeds_into
EDGE | f7_cross_session_match | sessions_vs_cache | feeds_into
EDGE | sessions_vs_cache | ui_sessions_vs | displayed_in
EDGE | sessions_vs_cache | vs_gap5_convergence | feeds_into
EDGE | vs_gap5_convergence | ui_tuner | displayed_in
EDGE | slope_reference_json | f7_event_detect | not_consumed_by
EDGE | route_reference_json | ui_gps_analysis | displayed_in
EDGE | ride_csv | slope_reference_json | computed_from
EDGE | ride_csv | route_reference_json | computed_from

EDGE | ride_csv | launch_detect | feeds_into
EDGE | launch_detect | launch_cluster | feeds_into
EDGE | launch_cluster | launch_cross_match | feeds_into
EDGE | launch_cross_match | ui_sessions_launch | displayed_in
EDGE | launch_cluster | vdyno_physics | feeds_into
EDGE | ride_csv | vdyno_physics | feeds_into
EDGE | raw_env_baro | vdyno_physics | feeds_into
EDGE | vdyno_physics | ride_vdyno_json | computed_from
EDGE | vdyno_physics | ride_vdyno_rows_json | computed_from
EDGE | ride_vdyno_json | vdyno_compare | feeds_into
EDGE | vdyno_compare | ui_sessions_vs | displayed_in
EDGE | vdyno_compare | ui_launch_power | displayed_in
EDGE | ride_vdyno_rows_json | ui_dashboard | displayed_in

EDGE | ride_csv | gear_learner_fit | feeds_into
EDGE | gear_learner_fit | gear_profile_json | computed_from
EDGE | gear_profile_json | f7_event_detect | feeds_into
EDGE | gear_profile_json | vs_classify | feeds_into
EDGE | gear_profile_json | launch_detect | feeds_into

EDGE | eeprom_bin | eeprom_decoded_json | computed_from
EDGE | eeprom_bin | vs_merge_maps | feeds_into
EDGE | sessions_vs_cache | vs_merge_maps | feeds_into
EDGE | vs_gap1_significance | vs_merge_maps | not_consumed_by
EDGE | vs_merge_maps | ui_tuner | displayed_in
EDGE | vs_merge_maps | fase6_unified_proposal | not_consumed_by
EDGE | session_f7clusters_json | fase6_unified_proposal | not_consumed_by
EDGE | vs_gap5_convergence | fase6_unified_proposal | not_consumed_by
EDGE | fase6_unified_proposal | burns_json | gated_by
EDGE | vs_gap1_significance | fase6_unified_proposal | gated_by

EDGE | ui_tuner | eeprom_bin | feeds_into
EDGE | ui_map_editor | eeprom_bin | feeds_into
EDGE | eeprom_bin | burns_json | computed_from
EDGE | burns_json | vs_gap5_convergence | not_consumed_by
EDGE | burns_json | vdyno_fase_v4 | feeds_into
EDGE | ride_vdyno_json | vdyno_fase_v4 | feeds_into
EDGE | sessions_vs_cache | vdyno_fase_v4 | feeds_into
EDGE | vdyno_fase_v4 | burns_json | gated_by

EDGE | rider_notes_field | fase6_unified_proposal | not_consumed_by
EDGE | rider_notes_field | ui_dashboard | not_consumed_by
EDGE | ride_annotations_json | vs_cell_index | not_consumed_by
EDGE | ride_annotations_json | vdyno_physics | not_consumed_by
EDGE | ride_annotations_json | ui_graf2 | displayed_in

EDGE | live_json | ui_dashboard | displayed_in
EDGE | ride_errorlog_json | ui_errorlog_viz | displayed_in
EDGE | fuel_consumption_cache | ui_fuel | displayed_in
EDGE | session_metadata_json | ui_tuner | feeds_into
EDGE | session_metadata_json | ui_sessions_vs | feeds_into
EDGE | session_metadata_json | ui_dashboard | feeds_into
EDGE | raw_imu | ui_gps_analysis | not_consumed_by
```

## 4. Gap to north star

The north star is autonomous, trustworthy map-tuning proposals; the current pipeline is
closer to "trustworthy measurement, manual proposal" and has three distinct kinds of gaps.
First, **captured but never used**: the `rider_notes` field in `session_metadata.json` is
dead on both ends (no write endpoint, no reader) despite being explicitly proposed in
BACKLOG.md; GRAF2 annotations of type `note`/`diagnostic` are fully captured through a real
UI but only `type=launch` is ever read again (by F7 Phase 2.2); `slope_reference.json`
accumulates differential GPS slope but is only populated through a manual endpoint call and
its `get_slope_pct()` is never invoked by `f7.py` or `vs_engine.py`, even though GAP4 in
BACKLOG.md explicitly names this exact wiring as low-effort. Second, **used but
statistically unvalidated**: every current Sessions VS verdict is built on `pw1_norm`/`pw2_norm`,
a baro-normalization of injector pulse-width that is applied unconditionally in `launch.py`
and `f7.py` and directly contradicts CLAUDE.md's own Alpha-N doctrine ("do NOT normalize PW
by baro for DDFI2 — it is not Speed Density"); this is the metric the OL reliability table
calls `dpw_eff == dpw` and marks `✅ VALID`, so the table's own premise is compromised by code
that predates or bypassed that written rule. On top of that, none of BACKLOG_DATASET_INSIGHTS'
Phase A hygiene items are implemented — Batt_V confounder correction, thermal-protection
sample exclusion (`fl_hot`/`do_fan`), and per-sample density normalization are all `[PLAN]` —
so every dpw/dpw_eff comparison mixes electrical and thermal noise into what's presented as a
map-calibration signal. GAP1's Welch confidence interval is computed and shown in the UI, but
it is not consumed as a gate anywhere: `_merge_maps` (the only working PROPONER path today)
picks cell winners purely from the sign of `dpw_eff`/`ddvss`, ignoring `dpw_eff_sig` entirely.
Third, **designed but not built**: FASE 6 (the unified F7 + Sessions VS → EEPROM proposal
engine) does not exist — `_merge_maps` is a manual per-cell heuristic stand-in with no
significance gating, no convergence-rate coupling (GAP5 exists and works but isn't wired to
proposal magnitude), and no learning-rate dampening (GAP6, not started). VDYNO's noise-floor
rule (declare VERDE/ROJO only when `|ΔHP|` exceeds the ride-to-ride variance floor within the
same map) is fully specified in BACKLOG_VDYNO.md but `compare_sessions()` in `vdyno.py` returns
raw deltas with no such gate. VDYNO's physical constants (`mass_kg`, `CdA`, `Crr`) are static
config, not fit from the coastdown data that already exists in every ride (BL-DI-03). FASE V4,
the fully autonomous optimizer that would close the loop using vdyno + Sessions VS + burn
ledger causal history, is explicitly a "not yet started" design document that itself declares
autonomous burning permanently out of scope — a human always stays in the loop for QUEMAR.
Given all this, the single shortest path to the north star is not FASE V4 — it's finishing
what's already half-built: (1) fix or deliberately remove the baro PW-normalization so Sessions
VS measures what CLAUDE.md says it measures, (2) implement BACKLOG_DATASET_INSIGHTS Phase A
(Batt_V regression + thermal filter — both described as "one-afternoon script" / "one-line
filter"), (3) wire `dpw_eff_sig` as an actual gate in `_merge_maps` so PROPONER stops
proposing changes it cannot statistically justify, and only then (4) build FASE 6 as the
convergence-aware, significance-gated successor to `_merge_maps`. Everything else — GAP2
Bayesian optimization, VDYNO FASE V4, wideband integration — depends on that foundation being
trustworthy first, which is exactly the sequencing CLAUDE.md itself already states as strategy
("the pipeline must work and be trusted before adding a new signal source").

## 5. Graphify markdown ingestion — findings (report only, not applied)

`graphify-out/manifest.json` was inspected directly (no `.graphify/`, `graphify.config.*`, or
any other graphify config file exists anywhere in the repo or under the user's home directory —
searched both). The manifest currently tracks **every** `.md` file in the project, including
`CHANGELOG.md`, `BACKLOG.md`, and all `BACKLOG_*.md` files — for example `BACKLOG.md`,
`BACKLOG_DATASET_INSIGHTS.md`, `BACKLOG_VDYNO.md`, `CHANGELOG.md` all appear as tracked entries,
and `GRAPH_REPORT.md` shows real graph nodes/edges extracted from `CHANGELOG.md` and `BACKLOG.md`
content. So: there is no blanket `*.md` exclusion rule, and there is no filename-specific
exclusion for `CHANGELOG.md`/`BACKLOG*.md` either — despite the prior memory note that the user
asked for that exclusion, it does not appear to have been implemented (or graphify has no
config surface for it and the request was never actioned). Practically, this means the new
`docs/PIPELINE_DATA_FLOW.md` will be picked up automatically on the next `graphify update .`
with no special include needed — `docs/*.md` files are already tracked (`docs/00_OVERVIEW.md`
through `docs/11_VDYNO_PLAN.md` all appear in the manifest). If the user still wants
CHANGELOG/BACKLOG excluded as noise, that requires either a graphify config feature that
doesn't currently exist in this checkout, or manual post-processing of `graph.json` — worth
raising with the user rather than assuming it's already handled.
