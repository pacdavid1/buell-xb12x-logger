# CLAUDE.md — Buell Logger / Tuner Project

> Read this first. It gives you the full context without having to excavate the codebase.

## What this project is

A Raspberry Pi datalogger + web dashboard for tuning a **Buell XB12X** with a DDFI2 ECU.
No dyno — tuning is entirely data-driven from real street rides.
Pi is at `192.168.100.80`. Web dashboard at `http://192.168.100.80:8080`.

## The tuning cycle (core mental model)

```
LOG → ACOTAR → COMPARAR → PROPONER → QUEMAR → LOG
```

| Step | Page | Description |
|------|------|-------------|
| LOG | Dashboard (`index.html`) | Live ECU data, session/ride management |
| ACOTAR | Session Events (`session_events.html`) | F7: detect stable-condition events, cluster by TPS curve similarity |
| COMPARAR (events) | Session Events | F7: cross-session event matching, ΔPW and ΔVSS |
| COMPARAR (cells) | Sessions VS (`sessions_vs.html`) | SWEET/SPICY/BITTER cell analysis: dpw_eff per RPM×TPS bin → feeds FASE 6 |
| PROPONER | Tuner (`tuner.html`) | Map diff, proposal generation |
| QUEMAR | VE tab (Dashboard) | Burn EEPROM to ECU via Pi |

Sessions Launch (`sessions_launch.html`) is **being migrated** to use F7 events.
Error Log (`errorlog_viz.html`) is a **diagnostic tool**, not part of the tuning cycle.

## Key files

```
main.py                        — entry point, ECU loop, sensor threads
web/server.py                  — HTTP handlers (~2100 lines)
web/f7.py                      — FASE7 event detection + DTW clustering (extracted v2.6.98)
web/templates/index.html       — Dashboard
web/templates/session_events.html
web/templates/sessions_vs.html
web/templates/sessions_launch.html
web/templates/tuner.html
web/templates/errorlog_viz.html
web/static/app.js              — Dashboard JS
ecu/connection.py              — ECU serial protocol + EEPROM read/write
ecu/session.py                 — ride recording
ecu/eeprom.py                  — EEPROM decode (fuel/spark maps)
BACKLOG.md                     — all pending work by FASE
CHANGELOG.md                   — version history (update before every commit)
```

## Architecture decisions you must know

**F7 is the canonical event pipeline.** `detect_launches()` in server.py is the old
approach (hard dtps>8 threshold, no caching). F7 uses rolling std over 3s,
caches per ride, clusters by PW DTW, matches cross-session by TPS DTW.
Everything new should use F7. Backlog 7.8 covers migrating Sessions Launch to F7.

**Sessions VS and Session Events are complementary, not redundant.**
- Sessions VS → aggregate cruising data (SWEET bins) → FASE 6 map proposal
- Session Events → discrete events (WOT accel/decel) → F7 cross-session compare

**Dead code in `_compare_sessions` (server.py):** The F7 cross-session block
is coded after the `return` statement — it never executes. Needs to be moved
before the return. It's in the backlog.

**`_compare_sessions_cached`** is the shared backend for both Sessions VS and Sessions Launch.

## Refactor state

| Module | Status |
|--------|--------|
| `web/f7.py` | ✅ Extracted from server.py at v2.6.98 (~669 lines) |
| `web/launch.py` | 🔲 Next — `detect_launches`, `cluster_launches`, `match_clusters`, `_compare_sessions` |
| `web/sessions_vs_engine.py` | 🔲 After launch — `_maps_differ`, `_merge_maps`, `_compare_sessions_cached` |

## Sensor configuration — OL mode (CRITICAL context)

The bike runs in **Open Loop (OL) without a wideband O2 sensor**.
The narrowband EGO sensor is intentionally disconnected.

**Confirmed in data (248AE2 sample, 500 rows):**
- `EGO_Corr` = 100.0 always (locked — no signal)
- `AFV`      = 100.0 always (long-term trim also locked)
- `WUE`      = 100–131 (warm-up enrichment — works normally)
- `Accel_Corr (AE)` = 0–25 (acceleration enrichment — works normally)

**Consequence for JSON pipeline:**

| Data / JSON | Status in OL | Reason |
|-------------|-------------|--------|
| `ride_*_f7events.json` | ✅ VALID | PW + TPS curves — pure physics |
| `session_f7clusters` | ✅ VALID | DTW on PW curves — no EGO |
| `sessions_vs delta` — dpw, ddvss | ✅ VALID | Injector pulse delta, speed delta |
| `sessions_vs delta` — dpw_eff | ✅ VALID (= dpw) | AFV=100 so dpw_eff == dpw |
| `eeprom_decoded.json` | ✅ VALID | Raw map data |
| `WUE` / `AE` filters in classify() | ✅ VALID | ECU-generated, not O2-based |
| `tuning_report_*.json` | ⛔ INACTIVE | ego_avg=100 always → 0 suggestions |
| `ego_avg` in ride_summary | ⛔ NOISE | Always 100 |
| `valid_ego_avg` in tuning cells | ⛔ NOISE | No valid EGO signal |

**Current valid tuning pipeline (OL):**
```
F7 events (PW curves)  →  cross-session compare  →  which map accelerates better?
Sessions VS (dpw/ddvss) →  cell-level compare    →  which map is more efficient?
         ↓
  unified map proposal (FASE 6 — pending)
         ↓
  burn EEPROM
```

**Future — when WB sensor is added:**
- WB reads real AFR → compare vs target AFR map
- EGO/AFV become meaningful again
- tuning_report becomes useful: cell-level EGO trend = map correction signal
- Integrate as third input to unified proposal (don't replace F7 + VS, add to it)

**Rule: do NOT build any feature that depends on EGO_Corr or AFV
until the WB sensor is installed and validated.**

## Commit workflow (mandatory order)

1. Update CHANGELOG.md with the new version entry
2.  ALL changed files INCLUDING CHANGELOG.md in the same command
3.  — code + changelog go in the same commit, never separate
4. Never commit code without a CHANGELOG entry in the same commit

> Why: if you update the changelog after the commit, the previous commit has no
> record of what changed. Future sessions see the old entry and get confused.

## Coding standards (mandatory)

- **English only** — all code, comments, variable names, docstrings, frontend labels
- Every file you touch that lacks a DEV NOTE: add one at the top
  - Python: `# DEV NOTE: All code, comments, and variable names must be in English.`
  - HTML: `<!-- DEV NOTE: All code, comments... must be in English. -->`
- Completed backlog item → remove from BACKLOG.md, add entry to CHANGELOG.md, commit
- Never leave [x] items in BACKLOG.md — remove them entirely
- Functions < 50 lines, files < 800 lines (refactor on touch)
- No mutation — return new objects

## How to restart the server

```bash
# Find PID
ps aux | grep main.py | grep -v grep

# Kill + restart
kill <PID>
cd /home/pi/buell
nohup python3 main.py --port /dev/ttyECU --sessions-dir /home/pi/buell/sessions --buell-dir /home/pi/buell > /tmp/buell_restart.log 2>&1 &

# Validate
curl -s http://localhost:8080/live | python3 -c 'import sys,json; print(json.load(sys.stdin).get("session_id","?"))'
```

## Validate after any change

```bash
# Import check (before restart)
cd /home/pi/buell
python3 -c "from web.server import WebServer; print('OK')"
python3 -c "from web.f7 import _f7_load_session_clusters; print('OK')"

# Endpoint check (after restart)
curl -s 'http://localhost:8080/session_events/data?session=248AE2' | python3 -c \
  'import sys,json; d=json.load(sys.stdin); print("clusters:", d.get("n_clusters"), "events:", d.get("n_events"))'
```

## Priority backlog items

1. **Baro normalization** — fix dpw_eff in `_compare_sessions`: pw_norm = pw * (1013.25/baro)
2. FASE 6 — unified map proposal: F7 + Sessions VS delta -> EEPROM proposal
3. Backlog 7.8 — Sessions Launch consumes F7 clusters instead of detect_launches
4. Backlog 7.7 — all-sessions F7 event comparison, rank maps by acceleration win rate
5. FASE 5.1 — editable VE heatmap cells + burn from browser
6. FASE 6 — map proposal from Sessions VS delta → VE overlay

## Freebuff — parallel AI agent workflow

Freebuff is a second AI agent running in the user's terminal (`freebuff` CLI).
It works on research/analysis tasks in parallel while Claude codes.
It also validates code we write and acts as a supervisor.

### Files
- Tasks queue:  C:/Users/pacda/freebuff/TASKS.md  (Claude writes here)
- Responses:    C:/Users/pacda/freebuff/responses/task_NNN_name.md  (freebuff writes here)

### Claude's role

**MANDATORY: check responses at these moments:**
1. Session start — FIRST thing: glob C:/Users/pacda/freebuff/responses/*.md
   If files exist: read them, evaluate, delete consumed ones, add follow-up tasks.
   Report to user: 'Freebuff respondio task NNN — [2-line summary].'
2. After every git commit — check responses/ and remind user of pending tasks.
3. At any natural pause (waiting for user input) — quick check, don't block.
4. When user asks 'what's next?' — include freebuff pending task count.

**How to consume a response:**
1. Read the file with the Read tool
2. Evaluate: what's useful, what changes the plan, what needs a follow-up task
3. DELETE the file (rm command) — deletion = consumed signal to freebuff
4. If finding changes the plan: add new TASK to TASKS.md BEFORE next freebuff run
5. Tell user what freebuff said in 2-3 lines

**When to ADD a task to freebuff (do this proactively, not when asked):**
- After EVERY git commit with new code -> add validation task immediately
- Any algorithm decision you're unsure about -> research task
- Any 'Questions for Claude' in a freebuff response -> follow-up task
- User says 'que piensas de X' -> delegate to freebuff
- Freebuff queue has < 2 PENDING tasks -> proactively add the next one

**After every git commit (mandatory checklist):**
1. Check responses/ for new freebuff files
2. Add TASK NNN — Validate: [what we just built] to TASKS.md
3. Tell user: 'Agregue task NNN a freebuff. Dile siguiente cuando puedas.'
4. If freebuff has > 3 pending tasks: mention it so user can pace freebuff

**Validation task format (use after every coding session):**
```
## TASK NNN - Validate: [what we built]
File: web/X.py lines A-B. What it does: Z.
Key decisions made: ...
Review for: correctness, edge cases, OL mode compliance (no EGO/AFV logic),
pipeline consistency, anything that looks risky or wrong.
```

**Reminder protocol (proactive, not passive):**
- After git commit: check responses/ + tell user 'freebuff tiene [N] tareas pendientes'
- If >1 session with no freebuff check: remind user 'hay tasks de freebuff sin revisar'
- Never block coding waiting for freebuff — always work in parallel
- If user says 'lo pongo a trabajar': add the next task to TASKS.md immediately
