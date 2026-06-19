# CLAUDE.md — Buell Logger / Tuner Project

> Read this first. It gives you the full context without having to excavate the codebase.

## Objectives — read every session before anything else

### System objective
Optimize the DDFI2 map continuously and autonomously under real riding conditions.
The cycle is: **LOG → ACOTAR → COMPARAR → PROPONER → QUEMAR → measure again.**
The system learns by itself. Every ride is an experiment. Every burn is a hypothesis test.

### Claude's objective in this project
Not just task execution — active co-exploration.
Surface what the user doesn't know exists: the math, the techniques, the signal patterns
that can't be requested because the user doesn't know they're there yet.
Every session should leave the project smarter than it started, even if no code was written.

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

## ECU logic — CRITICAL: read before writing any fuel/spark logic

### Alpha-N fueling (not Speed Density)
The DDFI2 runs **Alpha-N**: fuel is calculated from **TPS position + RPM only**.
There is NO MAP sensor. The ECU does NOT compute air density from manifold pressure.

**Consequences — do NOT assume Speed Density behavior:**
- Barometric pressure does NOT directly enter the fuel equation
- Do NOT normalize PW by (1013/baro) as if it were Speed Density
- PW differences between sessions reflect MAP calibration differences, not baro offsets
- We measure with physics: PW is what the injector actually did, TPS is what the rider did

### Sensor configuration — OL mode (CRITICAL context)

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

## Data reuse — CRITICAL principle

**Before creating any new JSON file or endpoint, check what already exists.**

- `eeprom.bin` is always present in every session — use `decode_eeprom_maps(bin)` directly
  Do NOT require `eeprom_decoded.json` — it may not exist in older sessions
- `session_f7clusters_0_85.json` — use it, don't regenerate unless stale
- `sessions_vs` cache — already computed, reuse via `_compare_sessions_cached()`
- If data exists in another JSON: read it from there, don't create a parallel file

**Before adding a new UI tab or panel, check if it fits in an existing one.**
New tabs are only justified when the workflow is genuinely different.
A new view mode or button within an existing tab is almost always better.

## Commit workflow (mandatory order)

1. Update CHANGELOG.md with the new version entry
2. git add ALL changed files INCLUDING CHANGELOG.md in the same command
3. git commit — code + changelog go in the same commit, never separate
4. Never commit code without a CHANGELOG entry in the same commit

### CHANGELOG format — CRITICAL

New entries go at the TOP of the file, immediately after the header block.
NEVER use `cat >> CHANGELOG.md` — that appends to the bottom.
Always use a Python prepend script:

```python
path = '/home/pi/buell/CHANGELOG.md'
entry = '''
## [vX.Y.Z] — YYYY-MM-DD
### Changed
- description
### AI
- Claude Sonnet 4.6, Anthropic
'''
with open(path) as f: content = f.read()
# Find insertion point AFTER PROMPT_END block (never inside the instruction comments)
import re
prompt_end = 'PROMPT_END -->'
after_header = content.index(prompt_end) + len(prompt_end)
m = re.search(r'
## \[v', content[after_header:])
insert_at = after_header + m.start()
content = content[:insert_at] + entry + content[insert_at:]
with open(path, 'w') as f: f.write(content)
```

> Why: if you update the changelog after the commit, the previous commit has no
> record of what changed. Future sessions see the old entry and get confused.

## Coding standards (mandatory)

## ENGLISH ONLY — NON-NEGOTIABLE (read this first)

**ALL code is in English. No exceptions. Ever.**

This means:
- Variable names, function names, class names → English
- Comments → English
- Docstrings → English
- Log messages → English
- Frontend labels, button text, UI strings → English
- Error messages → English
- HTML attributes, CSS class names → English
- New files → English from line 1
- Existing Spanish code you touch → rewrite it in English as part of the change
- Do NOT leave Spanish in any line you modify

If you find Spanish code in a file you are editing: translate it.
If you write new code: write it in English.
There is no gray area. English. Always. Every time.

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


## Dev tools

### Graphify — codebase knowledge graph

Graphify is installed on the Windows host (not the Pi) to avoid RAM pressure on the Pi Zero 2W.
It maps the project into a queryable knowledge graph.

**Workflow: Pi pushes to GitHub → Windows pulls → graphify update → view graph**



Outputs: graphify-out/graph.html (interactive), graphify-out/GRAPH_REPORT.md

Query the graph: graphify query "what functions read the EEPROM?"

Key god nodes: DashboardHandler (server.py), SessionManager (ecu/session.py), BuellLogger (main.py)

No API key needed for code-only updates.

## Priority backlog items

1. **Baro normalization** — fix dpw_eff in `_compare_sessions`: pw_norm = pw * (1013.25/baro)
2. FASE 6 — unified map proposal: F7 + Sessions VS delta -> EEPROM proposal
3. Backlog 7.8 — Sessions Launch consumes F7 clusters instead of detect_launches
4. Backlog 7.7 — all-sessions F7 event comparison, rank maps by acceleration win rate
5. FASE 5.1 — editable VE heatmap cells + burn from browser
6. FASE 6 — map proposal from Sessions VS delta → VE overlay

## Freebuff - inbox protocol

Freebuff is a second AI agent running on the user machine.
It writes research, audits, and task assignments to the inbox folder below.

### How it works

1. freebuff writes to /home/pi/buell/inbox/NNN_topic.md via SSH
2. Claude reads inbox after every commit - process ALL files in order
3. Claude processes each file:
   - Code changes -> apply immediately, commit with version bump
   - Research findings -> save to BACKLOG.md if not actionable
   - Audits -> add Audited line to CHANGELOG.md
4. Claude deletes the inbox file after processing (signals done)
5. Claude reports to user about what was processed

### Mandatory: check inbox at these moments

1. AFTER every git commit - run: ls /home/pi/buell/inbox/
2. At session start - check inbox before anything else
3. When user mentions freebuff - check inbox immediately
4. At natural pauses while waiting for user input

### Also check: local responses folder

freebuff writes validation/research responses to:
  C:/Users/pacda/freebuff/responses/

Check this folder at session start and after every commit.
For each .md file found:
1. Read it
2. If audit already in CHANGELOG (freebuff inserted it): just delete the file
3. If audit NOT in CHANGELOG: insert the Audited line, then delete the file
4. If it has Action items: apply them, commit, then delete the file
Never leave response files sitting there — freebuff expects Claude to consume and delete them

### Inbox file format

Files are named NNN_topic.md (e.g. 001_pending_priorities.md).
Each file starts with a header: # NNN - Topic, then content.

### CRITICAL: Evaluate before executing (freebuff is not infallible)

Before applying ANY freebuff proposal (code fix, architecture, research finding):

1. **Read critically** — freebuff can be wrong. It has made errors before:
   - Inserted CHANGELOG entries inside the PROMPT_START comment block
   - Reported false-positive bugs (e.g. ZeroDivisionError VSS that already had a guard)
   - Made assumptions about code that don't match what's actually on the Pi

2. **Verify the claim** — if freebuff says line X has bug Y, read the actual line.
   If it says field Z is missing, check the actual code. Never trust the report blindly.

3. **Assess risk** — before changing production code:
   - Is this change safe? Could it break something that works?
   - Is it consistent with OL mode constraints (no EGO/AFV dependencies)?
   - Does it respect the coding standards (English, immutable, <50 lines)?

4. **If something seems wrong or risky** — stop and ask the user before proceeding.
   Example: freebuff proposes X but I see a problem with Y — do you want me to proceed?

5. **Research findings** — treat as input, not commands. If freebuff says
   the root cause is X, verify against the actual code/data before accepting.

### Processing rules

1. Process files in numeric order (001 before 002)
2. After processing: delete the file: rm /home/pi/buell/inbox/001_*
3. If a file needs user decision: keep it, flag to user, wait
4. Never skip an inbox file - every file is there for a reason

## INST block standard

Any `.md` file in this project may carry processing instructions in an
`INST/INST_END` block at the top (first 20 lines). Always read it before
acting on the file content.

Format:
```
<!-- INST
purpose: what this file is
action:  what to do with it
delete:  when to delete (if ever)
INST_END -->
```

### Audit files from freebuff

When an inbox file has `action: audit`:
1. Validate each finding against live code on the Pi
2. If finding is a false positive: note it, no CHANGELOG needed
3. If finding is a real issue: fix it, add CHANGELOG entry, commit
4. Delete the file after all findings are resolved either way

### BACKLOG files are plans, not instructions

`BACKLOG*.md` files never carry INST blocks — they are action items.
Read them as task lists, not as processing directives.

## Git branch policy

Check `git branch` before the first commit of every session.

If the working directory is NOT on `main`:
- Stop and flag it to the user before committing anything
- Never create a new branch without explicit user approval

Only create a branch when the user explicitly asks, OR the work touches:
- `ecu/connection.py` — serial protocol to ECU
- `main.py` ECU loop — crash here = lost ride data
- EEPROM burn paths — bad write = corrupted ECU map

Everything else (UI, CSS, dead code, new pages, backlog items) goes
directly to `main`.

## MODO CREATIVO

Cuando el usuario diga "modo creativo", "activa modo creativo", "ponte creativo" o "ponte creativa":
1. Leer CREATIVE_MODE.md para instrucciones completas
2. Leer IDEAS.md para ver qué ya se exploró
3. Operar según esas instrucciones hasta que el usuario
   diga "modo normal"

Al cerrar cualquier sesión de código (después del commit):
- Si Claude encuentra algo mientras trabaja que aplica
  a IDEAS.md — agregarlo sin que el usuario lo pida
- Una entrada por sesión máximo — no interrumpir el trabajo

