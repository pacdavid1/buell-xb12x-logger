<!-- DEV NOTE: All code, comments, and variable names must be in English. -->
# HARDENING PLAN — 2026-07-15

Goal: the pipeline is functionally solid (education side + measurement side both
mature); this plan hardens what exists instead of adding surface. Three fronts:
(1) runtime robustness on the Pi, (2) RAM/CPU service separation, (3) backlog
hygiene so open items reflect reality.

## Measured baseline (Pi Zero 2W, idle, 2026-07-15 08:37)

| What | Value | Note |
|------|-------|------|
| RAM total | 416 MiB | 512 MB minus GPU split |
| RAM used | ~200 MiB (48%) | matches the "50%" seen on the dash |
| main.py RSS | 47.5 MB (11%) | web server + all analysis code + numpy/sklearn |
| logger_process RSS | 22.9 MB (5%) | the ride-critical process |
| tailscaled | 25.3 MB | remote access daemon — as big as the logger |
| Other daemons | ~100 MB | systemd, journald, NetworkManager, sshd, gpsd |
| Swap used | 24 MiB | something spiked in the past (BL-BUG-03 suspect) |
| **main.py CPU** | **~30% of one core, IDLE** | 17:49 CPU min in 58 min uptime |
| cpu_temp | 64.5 °C idle | consequence of the above |

Reading: buell code is only ~17% of RAM. The 15%→50% growth is mostly the OS
stack + daemons + web-process caches over uptime. RAM is not the emergency —
**the 30% idle CPU in main.py is**, and it costs heat and UPS runtime.

## Front 1 — Runtime robustness (ride-critical first)

| # | Item | Size | Status/source |
|---|------|------|---------------|
| 1.1 | IPC partial-JSON race: `_ipc_write` must write tmp + `os.replace` (atomic); reader must tolerate torn reads without degrading silently | S | glassbox round 3 finding |
| 1.2 | Errorlog misfiling: ride numbering in filename vs content mismatch; A295AD logs stored under 91B225 | M | DELTA-5 |
| 1.3 | Errorlog coverage: the 5×35 s gap ride (91B225 R2) produced NO errorlog — reconnect path must always journal | M | DELTA-5 |
| 1.4 | Port `bench/` from buell_fable5 (DDFI2 fault-injection bench, 8 golden tests) and run the HIL checklist — validates the PRODUCTION decoder/logger | M | DELTA-3, HIGH |
| 1.5 | UPS drain test on the bench: unplug, verify poweroff <30% and journal shows `chg_claim=True, discharging=True` | XS | validates v2.7.291 |
| 1.6 | Dashboard charge icon ("rayito") reads the raw CW2015 bit — show the trend-corrected state (`discharging` from battery_guard) so the UI stops lying too | S | user-confirmed symptom |
| 1.7 | Grow golden tests around the burn path: eeprom encode/decode round-trip + ±15% clamp + firmware-match guard (highest-risk code in the repo) | M | tests/ now exists |
| 1.8 | Cache-Control audit on data APIs in server.py (glassbox weight bug was a stale-HTTP-cache bug) | XS | DELTA-6 |

## Front 2 — CPU + RAM service separation (the user's ask)

**Design principle: what rides must be small and boring; what analyzes can be
big but must be mortal.**

Current layout: `main.py` = supervisor + sysmon + GPS + network + WebServer
with EVERY analysis endpoint (f7 DTW, vs_engine + sklearn GP, vdyno, proposal,
graf2 data). numpy+sklearn load at boot and their caches live forever in the
ride-time process. `logger_process` is already correctly isolated.

| # | Item | Size |
|---|------|------|
| 2.1 | **Profile the 30% idle CPU first** (`py-spy top --pid` or thread-level `top -H`): prime suspects are the 0.25 s IPC reader loop, 2 s sysmon loop, and live.json re-parsing. Fix before any architecture change — it may be a two-line sleep bug | S |
| 2.2 | Lazy-import sklearn/numpy in analysis modules (import inside handler, not at module top) — shrinks boot RSS of the ride-time process immediately, zero risk | S |
| 2.3 | **Analysis-as-worker**: analysis endpoints (`/compare*`, `/vdyno*`, `/eeprom/propose`, f7 recompute) spawn a short-lived worker subprocess per request; results return via file/pipe. Memory goes back to the OS when the worker dies — kills the BL-BUG-03 OOM class entirely and keeps the resident process lean. Cache stays on disk (sessions/_cache) as today | L |
| 2.4 | Ride-time guard: while a ride is active (RPM>0), analysis endpoints return 503 "riding" (or queue) — post-ride work should never compete with the serial loop for CPU | S |
| 2.5 | Consider `systemd` `MemoryMax=` on the analysis worker + `Nice=10` — the OOM killer must never pick logger_process | XS |
| 2.6 | tailscaled costs 25 MB + CPU wakeups; evaluate stopping it while a ride is active (`systemctl stop tailscaled` on ride start, start on ride end) — remote access is a parked-bike feature anyway | S (user decision) |

Order: 2.1 → 2.2 → 2.4 → 2.3 → 2.5/2.6. Measure after each (free -h + ps RSS
+ CPU time), one commit each.

## Front 3 — Backlog hygiene (executed 2026-07-15 + remaining sweep)

Archived (audit of 2026-07-03 finally actioned; files moved to `archive/`,
nothing deleted — developer diary preserved):
- `BACKLOG_PROPOSAL_V2.md` — all 4 phases shipped v2.7.271-275, finished log.
- `BACKLOG_ECM_DEFS.md` — superseded by BL-ECM-01; residuals tracked in BACKLOG.md.
- `BACKLOG_EEPROM_READ_LOGIC.md` — Fases A/C shipped; residual = BL-ECM-01-RESIDUAL.
- `BACKLOG.md` audit section → `archive/BACKLOG_AUDIT_2026-07-03.md` (its two
  reopens were fixed in v2.7.285).

**Remaining mechanical sweep** (safe, boring, one commit): remove the inline
DONE items the audit lists (BL-GEAR-01, BL-GPS-03, BL-ECM-01 body, BL-GRAF-03
copy, FASE6 baro-norm text, task015, task037 dup, BL-ECM-03) and merge the 7
confirmed duplicate pairs (PROPOSAL tab ×3, batch compare ×2, Launch→F7 ×2,
AI context ×2, watchdog heartbeat ×2, tire-wear ×2, UPS MOSFET ×2). Renumber
`BACKLOG_3D_VIZ.md`'s BL-GRAF-03 → BL-3DV-09 (ID collision).

### What stays OPEN (the fronts we keep working)

1. **Tuning loop completion (FASE 6)**: PROP_* burn loop untested in practice;
   PROPOSAL tab UI (backend ready, no consumer); GAP 1 sport-side CI; GAP 6
   learning rate. This is the core product.
2. **BL-VS-PERCYL** — per-cylinder winner split. Aligned with the pw1/pw2
   never-averaged principle and IDEA-035/036; next substantial feature.
3. **F7 completions**: GRAF2 Phase 2.2 (launch marks → PILOT-MARKED), 7.7 batch
   compare / win-rate ranking, 7.8 Launch→F7 migration.
4. **VDYNO V2/V3**: coast-down CdA/Crr calibration (BL-DI-03), bootstrap CI
   (IDEA-016), climb-rate term (IDEA-019) — unblocked now that J1349 is fixed.
5. **Rescue DELTAs 3-6** (bench port, graf2 overlay after measure/, glassbox
   logger findings, glassbox UI features under the house theme).
6. **Hardware queue**: clutch switch (first buy), brake flag input, MPU6050
   (FASE 3), stator watch (BL-DI-02/IDEA-022).
7. **Bugs**: BL-BUG-03 (absorbed by 2.3 above), BL-BUG-04 (map-editor dead
   burn button — fix or delete the page).
8. **Residuals**: BL-ECM-01-RESIDUAL (dynamic RPM/LOAD bins), 2nd fuel map in
   MAP_KEYS; BL-ECM-02 (DDFI3) only when a 1125CR actually appears.
9. **UI**: 3D_VIZ list (LOW, cosmetic), project-wide vertical-scroll layout
   refactor, IDEA-036 NB rich/lean gate (after one clean ride on the fixed ECO).

### Explicitly NOT continuing (stay archived / rejected)

- Baro normalization of PW for DDFI2 (task006 — wrong physics for Alpha-N, removed v2.7.276).
- Hall-effect transmission-shaft gear sensor (IDEA list: measures what VSS already gives).
- Logger rewrite in Rust (revisit only when the CSV schema freezes).
- tuning_report / EGO_Corr-based features (dead until a wideband exists — NB
  raw voltage is the only O2 signal in play, see IDEA-036).
