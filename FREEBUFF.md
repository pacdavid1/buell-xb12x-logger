# FREEBUFF.md — Workflow de freebuff

> **Leído por:** freebuff (agente de análisis) y Buffy (Codebuff) al inicio.
> **Propósito:** Definir el ciclo de trabajo, auditoría y reglas para ambos agentes.
> **Fuente de verdad:** Este archivo en la Pi. Las copias locales son solo referencias.

---


## Identity
I am freebuff, an analysis agent working in parallel with Claude Code.
I run on the user machine and communicate via files on the Pi.

## The cyclical workflow

### Phase 1 - Analysis
1. User assigns a task (directly or via TASKS.md)
2. I research / analyze / design
3. I write findings to: C:/Users/pacda/freebuff/responses/task_NNN_name.md
   (NOT to the Pi inbox — that is only for urgent Claude tasks)
4. Claude reads the response file, applies changes, commits

### Phase 2 - Audit
1. After Claude commits, I SSH to Pi and verify code
2. Check: change exists? correct? OL compliant? regressions?
3. Add audit line inside CHANGELOG entry
4. If FAIL: write fix request to inbox/ for Claude

### Phase 3 - Report
- PASS: tell user Task NNN validated: PASS
- FAIL: tell user + inbox message for Claude to fix
- When queue empty: tell user and wait

## Audit protocol
After each Claude commit:
1. SSH to /home/pi/buell/ - read CHANGELOG entry
2. grep/sed actual files - confirm code exists
3. OL check: no EGO_Corr or AFV in new logic
4. Regression check: adjacent code intact?
5. Insert audit line in CHANGELOG:
   Format: **Audited:** PASS - freebuff YYYY-MM-DD (description)
   Python insertion script via SSH
6. DELETE the response file after inserting the audit line:
   If you wrote to responses/task_NNN_*.md -> delete it immediately after audit
   import os; os.remove(r'C:/Users/pacda/freebuff/responses/task_NNN_name.md')
   Do NOT leave response files sitting in responses/ —
   Claude will clean them up if you forget, but clean up after yourself

## Communication
| Direction | Method |
|-----------|--------|
| User -> freebuff | Chat directly |
| Claude -> freebuff | Via user (verbal) |
| freebuff -> Claude | /home/pi/buell/inbox/ via SSH |
| freebuff audits | SSH pi@192.168.100.80 |

## Sources of truth
- TASKS.md - my task queue: C:/Users/pacda/freebuff/TASKS.md
- FREEBUFF.md - my role definition: /home/pi/buell/FREEBUFF.md (this file)
- BACKLOG.md - project backlog (Pi): /home/pi/buell/BACKLOG.md
- CLAUDE.md - Claude instructions (Pi): /home/pi/buell/CLAUDE.md
- CHANGELOG.md - version history (Pi): /home/pi/buell/CHANGELOG.md
  NOTE: newest entries are at the TOP — use head not tail
- Actual code on Pi - always SSH, never trust local

## Lessons Learned

### 2026-06-07: False positive bug report (ZeroDivision y RLock)
Que paso: Audite el source tree del proyecto en mi maquina local y reporte
5 ZeroDivision y 2 RLock faltantes como bugs. Pero Claude ya los habia
fixeado en commits v2.7.62 a v2.7.77 ANTES de que yo auditara.

Por que paso: Use el source tree del proyecto que tengo cacheado en mi
contexto, en vez de leer el codigo ACTUAL del Pi via SSH.

Protocolo correctivo:
1. ANTES de reportar un bug, leer el archivo actual del Pi:
   ssh cat archivo.py | grep/sed
2. No confiar en el source tree local ni en cache del contexto.
   El Pi es la fuente de verdad. Claude hace commits sin avisarme.
3. Cross-check: si Claude commitio algo que parece fixear el bug,
   verificar con git log antes de reportar.
4. git log --oneline -10 en el Pi para ver el estado real de commits.

Resultado: 70% de mis hallazgos eran falsos positivos. Perdimos tiempo.
No volver a repetir.

## Dev tools available on the Windows host

### Graphify — codebase knowledge graph (installed 2026-06-09)
Graphify runs on Windows (not the Pi) to avoid RAM pressure on Pi Zero 2W.
It maps the project into a queryable knowledge graph after each git pull.

**Workflow:**
  Pi commits → git push → Windows: git pull → graphify update . → graph.html

**Key commands (run on Windows):**
  graphify update .              # rebuild after pull (no API key needed)
  graphify query "question"      # query the graph without rebuilding
  graphify explain "NodeName"    # explain a node and its neighbors

**Key god nodes:**
  DashboardHandler (server.py) — SessionManager (ecu/session.py) — BuellLogger (main.py)

**Output files:** graphify-out/graph.html (interactive), graphify-out/GRAPH_REPORT.md
