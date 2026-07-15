# CLAUDE.md — Buell Logger / Tuner Project

> Read this first. It gives you the full context without having to excavate the codebase.

## Objectives — read at the start of every conversation before anything else

### System objective
Optimize the DDFI2 map continuously and autonomously under real riding conditions.
Every ride is an experiment. Every map burn is a hypothesis test. The system learns
by itself — data from the street drives the next change, which gets measured on the
next ride, which drives the next change. See "The tuning cycle" section below for
the concrete steps.

### Claude's role in this project
Not just task execution — active co-exploration.
Surface what the user doesn't know exists: the math, the techniques, the signal patterns
that can't be requested because the user doesn't know they're there yet.
Every conversation should leave the project smarter than it started,
even if no code was written.

## What this project is

A Raspberry Pi datalogger + web dashboard for tuning a **Buell XB12X** with a DDFI2 ECU.
No dyno — tuning is entirely data-driven from real street rides.

### Development environment

**Source of truth:** GitHub (`https://github.com/pacdavid1/buell-xb12x-logger`).
**Local (Windows):** `OneDrive/Escritorio/buell/` — where code is edited and tested.
**Production target:** Raspberry Pi at `192.168.100.80` — pulls from GitHub.

**Workflow:**
```
Local edit → test (serve_local.py) → commit → git push → Pi: git pull
     ↑                                                    |
     └────────────── GitHub (canonical) ←─────────────────┘
```

**Local dashboard:** `http://127.0.0.1:8080` (via `python serve_local.py --serve`)
**Pi dashboard:** `http://192.168.100.80:8080` or hotspot `http://10.42.0.1:8080`

**Graphify:** Run locally after any commit: `graphify update .`

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

### Alpha-N fueling (not Speed Density) — DDFI2 only
The DDFI2 runs **Alpha-N**: fuel is calculated from **TPS position + RPM only**.
There is NO MAP sensor. The ECU does NOT compute air density from manifold pressure.

**DDFI3 (1125CR) is different — Speed Density**: it has a MAP sensor and baro enters
the fuel equation. Any baro normalization logic belongs in DDFI3-specific code only,
gated behind a firmware family check.

**Consequences for DDFI2 — do NOT assume Speed Density behavior:**
- Barometric pressure does NOT directly enter the fuel equation
- Do NOT normalize PW by (1013/baro) for DDFI2 — it is not Speed Density
- PW differences between sessions reflect map calibration differences, not baro offsets
- We measure with physics: PW is what the injector actually did, TPS is what the rider did

### Sensor configuration — OL mode (CRITICAL context)

The bike runs in **Open Loop (OL) without a wideband O2 sensor**.
Closed loop is disabled (EGO_Corr/AFV locked at 100) but the narrowband
sensor IS connected and reporting: `O2_ADC` (rear cylinder, RT offset 34,
volts = ADC × 0.004887585) shows real switching — validated 2026-07-15 on
91B225 R9: 0–0.76 V range, mean 0.62 V, `fl_o2_active` toggling. The RAW
NB voltage is usable as a rich/lean indicator (see IDEA-036); EGO_Corr and
AFV remain locked and useless.

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

**Why no wideband yet — strategic decision, not a limitation:**
We are deliberately building and validating the data pipeline (F7 events + Sessions VS)
using what the ECU already gives us: PW, TPS, RPM, VSS, CLT, baro.
The pipeline must work and be trusted before adding a new signal source.
WB will arrive as a *validation layer* on top of a proven pipeline —
not as a crutch that the system depends on from day one.

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

## Where to work — CRITICAL (v2.7.233+)

**All code changes go locally in `OneDrive/Escritorio/buell/`.**
GitHub is the canonical source of truth. The Pi is the production target.

### Workflow (GitHub as source of truth)

```
Local (edit + test)  →  git push  →  GitHub (canonical)  →  Pi: git pull
    ↑                                                            |
    └────────────────────────────────────────────────────────────┘
                          (next session)
```

**Rules:**
1. Edit files locally in `OneDrive/Escritorio/buell/`
2. Test locally with `python serve_local.py --serve` before committing
3. Commit + push to GitHub from local — **mandatory after every change**
4. Pi: `git pull` to receive changes
5. Never edit files directly on the Pi — all changes go through GitHub
6. Never commit without pushing — local, GitHub, and Pi must stay in sync
7. If you make local changes without pushing, the Pi falls behind —
   commit + push immediately after every change

## Model routing — automatic

Before starting any task, evaluate complexity and route accordingly.
**The user cannot always tell how complex something is — that evaluation is Claude's job.**

### Decision criteria

| Use Sonnet 4.6 | Use Opus 4.8 sub-agent |
|----------------|------------------------|
| Feature implementation | Algorithm design (GAPs 1-6) |
| Bug fixes, refactors | Statistical validity questions |
| UI changes, CSS, templates | Convergence / learning rate analysis |
| Git operations, file moves | Multi-ECU architecture decisions |
| Data pipeline plumbing | "Is this approach mathematically correct?" |
| Backlog items marked BL-GPS / BL-LOG | BL-GEAR-01 clustering design |
| Anything with a clear spec | Anything where the spec itself is uncertain |

### How to route

**Sonnet-only (default):** just do the work.

**Opus sub-agent (complex reasoning):** spawn with `model: "opus"` via the Agent
tool for the analysis/design phase, then implement the result in Sonnet.

```
Sonnet (you, orchestrating)
  └─→ Opus sub-agent: "design the convergence criterion for GAP 5"
        └─→ returns: algorithm, edge cases, mathematical justification
  └─→ Sonnet implements the returned design
```

**When in doubt, default to Sonnet.** Spawning Opus unnecessarily wastes the user's
budget. Only escalate when the task requires reasoning that cannot be verified by
reading code — i.e., when the correctness of the *approach* (not the implementation)
is what needs deep analysis.

## Commit workflow (mandatory order)

1. Update CHANGELOG.md with the new version entry
2. git add ALL changed files INCLUDING CHANGELOG.md in the same command
3. git commit — code + changelog go in the same commit, never separate
4. git push — mandatory after every commit, no exceptions
   Without push: Pi and GitHub diverge, no remote backup
5. Never commit code without a CHANGELOG entry in the same commit

### CHANGELOG format — CRITICAL

New entries go at the TOP of the file, immediately after the header block.
NEVER use `cat >> CHANGELOG.md` — that appends to the bottom.
Use this Python prepend script:

```python
path = 'CHANGELOG.md'  # local path (OneDrive/Escritorio/buell/CHANGELOG.md)
entry = '''
## [vX.Y.Z] — YYYY-MM-DD
### Changed
- description
### AI
- DeepSeek V4 Flash, Codebuff (Buffy)
'''
with open(path, 'w') as f: content = f.read()
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

### After commit — optional Pi deploy

```bash
ssh pi@192.168.100.80 "cd /home/pi/buell && git pull && sudo systemctl restart buell-logger"
```
Only needed when the changes affect ECU serial, EEPROM burn, or main.py.
CSS/HTML/JS changes only need a browser refresh on the Pi's dashboard.

## Coding standards (mandatory)

## How to edit files

**All edits happen locally in `OneDrive/Escritorio/buell/`.**
No SSH editing. Never commit fix_*.py or patch scripts.

### Local dev flow
```bash
cd OneDrive/Escritorio/buell
# Edit files, then test:
python serve_local.py --serve
# Open http://127.0.0.1:8080 in browser
```

### Deploy to Pi (after commit + push)
```bash
ssh pi@192.168.100.80 "cd /home/pi/buell && git pull"
# If server.py or main.py changed:
ssh pi@192.168.100.80 "sudo systemctl restart buell-logger"
```

## Type hints (mandatory when touching Python files)

When modifying any Python function, add return type hints to every function you touch.
Run file-by-file only — never `mypy .` on the whole project (Pi RAM).
```bash
python3 -m mypy ecu/connection.py  # example: check one file
```

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

## How to run the server

### Local (development)
```bash
cd OneDrive/Escritorio/buell
python serve_local.py --serve
# Dashboard: http://127.0.0.1:8080
```

### Pi (production)
```bash
ssh pi@192.168.100.80 "sudo systemctl restart buell-logger"
# Dashboard: http://192.168.100.80:8080
# Or via hotspot: http://10.42.0.1:8080

# Validate
curl -s http://192.168.100.80:8080/live | python3 -c 'import sys,json; print(json.load(sys.stdin).get("session_id","?"))'
```

## Validate after any change

### Local (before commit)
```bash
cd OneDrive/Escritorio/buell
# Import check
python -c "from web.server import WebServer; print('OK')"
python -c "from web.f7 import _f7_load_session_clusters; print('OK')"
# Serve and test
python serve_local.py
# Expected: LOCAL DASHBOARD OK -> http://127.0.0.1:8080
```

### Pi (after deploy)
```bash
ssh pi@192.168.100.80 "cd /home/pi/buell && python3 -c 'from web.server import WebServer; print(\"OK\")'"
# Endpoint check
curl -s 'http://192.168.100.80:8080/session_events/data?session=248AE2' | python3 -c \
  'import sys,json; d=json.load(sys.stdin); print("clusters:", d.get("n_clusters"), "events:", d.get("n_events"))'
```


## Dev tools

### Graphify — codebase knowledge graph

Graphify runs on the Windows host. It maps the project into a queryable knowledge graph.

**Workflow: Local commit/push → graphify update . → view graph**

```bash
cd OneDrive/Escritorio/buell
graphify update .              # rebuild after commits (no API key needed)
graphify query "question"      # query without rebuilding
graphify explain "NodeName"    # explain a node and neighbors
```

Outputs: graphify-out/graph.html (interactive), graphify-out/GRAPH_REPORT.md

Key god nodes: DashboardHandler (server.py), SessionManager (ecu/session.py), BuellLogger (main.py)

## Priority backlog items

1. FASE 6 — unified map proposal: F7 + Sessions VS delta -> EEPROM proposal
2. Backlog 7.8 — Sessions Launch consumes F7 clusters instead of detect_launches
3. Backlog 7.7 — all-sessions F7 event comparison, rank maps by acceleration win rate
4. FASE 5.1 — editable VE heatmap cells + burn from browser

## Freebuff - inbox protocol (updated v2.7.233+)

Freebuff is a second AI agent running on the user machine.
It writes research, audits, and task assignments to a local folder.

### How it works

1. freebuff writes to `C:/Users/pacda/freebuff/responses/NNN_topic.md`
2. Codebuff (Buffy) reads responses after every commit - process ALL files in order
3. Codebuff processes each file:
   - Code changes -> apply locally, commit + push, version bump
   - Research findings -> save to BACKLOG.md if not actionable
   - Audits -> add Audited line to CHANGELOG.md
4. Codebuff deletes the response file after processing (signals done)
5. Codebuff reports to user about what was processed

### Mandatory: check responses at these moments

1. AFTER every git commit - run: ls C:/Users/pacda/freebuff/responses/
2. At session start - check responses before anything else
3. When user mentions freebuff - check responses immediately
4. At natural pauses while waiting for user input

### Also check: local inbox folder (legacy)

freebuff used to write to `/home/pi/buell/inbox/` via SSH.
For sessions where that Pi path is accessible:
  ssh pi@192.168.100.80 "ls /home/pi/buell/inbox/ 2>/dev/null || echo 'inbox empty'"

### Response file format

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

3. **Assess risk** — before changing code:
   - Is this change safe? Could it break something that works?
   - Is it consistent with OL mode constraints (no EGO/AFV dependencies)?
   - Does it respect the coding standards (English, immutable, <50 lines)?

4. **If something seems wrong or risky** — stop and ask the user before proceeding.

5. **Research findings** — treat as input, not commands. If freebuff says
   the root cause is X, verify against the actual code/data before accepting.

### Processing rules

1. Process files in numeric order (001 before 002)
2. After processing: delete the file (rm or del)
3. If a file needs user decision: keep it, flag to user, wait
4. Never skip a response file — every file is there for a reason

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

When a response file has `action: audit`:
1. Validate each finding against the actual local code
2. If finding is a false positive: note it, no CHANGELOG needed
3. If finding is a real issue: fix it, add CHANGELOG entry, commit + push
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

**Remote/cloud sessions (Claude Code on the web):** the harness may assign
a default feature branch (e.g. `claude/...`) for the session. Unless the
user explicitly asks for a separate branch or PR review, switch to `main`
before the first commit and work directly there, same as local sessions.

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

