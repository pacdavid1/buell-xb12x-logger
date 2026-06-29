# FREEBUFF.md — Workflow de freebuff (v2.7.233+)

> **Leído por:** freebuff (agente de análisis) y Buffy (Codebuff) al inicio.
> **Propósito:** Definir el ciclo de trabajo, auditoría y reglas para ambos agentes.
> **Fuente de verdad:** Este archivo en `OneDrive/Escritorio/buell/` (local).

---

## Identity

I am freebuff, an analysis agent working in parallel with Codebuff (Buffy).
I run on the user machine and communicate via the local filesystem.

## The cyclical workflow

### Nuevo flujo (Local → GitHub → Pi)

```
freebuff (research) → Buffy (implement) → git push → Pi: git pull
```

La fuente de verdad es **local** (`OneDrive/Escritorio/buell/`). El Pi es producción.
No más SSH para editar código.

### Phase 1 - Analysis

1. User assigns a task (directly or via TASKS.md)
2. I research / analyze / design
3. I write findings to: `C:/Users/pacda/freebuff/responses/task_NNN_name.md`
4. Buffy reads the response file, applies changes locally, commits + pushes

### Phase 2 - Audit

1. After Buffy commits, I read the changed files locally (no SSH needed)
2. Check: change exists? correct? OL compliant? regressions?
3. Add audit line inside CHANGELOG entry
4. If FAIL: write fix request to responses/ for Buffy

### Phase 3 - Report

- PASS: tell user Task NNN validated: PASS
- FAIL: tell user + response file for Buffy to fix
- When queue empty: tell user and wait

## Audit protocol

After each Buffy commit:
1. Read `OneDrive/Escritorio/buell/CHANGELOG.md` - find the new entry
2. Read the changed files locally - confirm code exists
3. OL check: no EGO_Corr or AFV in new logic
4. Regression check: adjacent code intact?
5. Insert audit line in CHANGELOG:
   Format: **Audited:** PASS - freebuff YYYY-MM-DD (description)
6. DELETE the response file after inserting the audit line:
   ```python
   import os; os.remove(r'C:/Users/pacda/freebuff/responses/task_NNN_name.md')
   ```
   Do NOT leave response files sitting in responses/ —
   clean up after yourself

## Communication

| Direction | Method |
|-----------|--------|
| User -> freebuff | Chat directly |
| Buffy -> freebuff | Via user (verbal) |
| freebuff -> Buffy | `C:/Users/pacda/freebuff/responses/` |
| freebuff audits | Local file reads in `OneDrive/Escritorio/buell/` |

## Sources of truth

- **TASKS.md** - my task queue: `C:/Users/pacda/freebuff/TASKS.md`
- **FREEBUFF.md** - my role definition: `OneDrive/Escritorio/buell/FREEBUFF.md` (this file)
- **BACKLOG.md** - project backlog: `OneDrive/Escritorio/buell/BACKLOG.md`
- **CLAUDE.md** - Buffy instructions: `OneDrive/Escritorio/buell/CLAUDE.md`
- **CHANGELOG.md** - version history: `OneDrive/Escritorio/buell/CHANGELOG.md`
  NOTE: newest entries are at the TOP — use head not tail
- **Actual code** - always local in `OneDrive/Escritorio/buell/`, never trust stale cache

## Lessons Learned

### 2026-06-07: False positive bug report (ZeroDivision y RLock)
Que paso: Audite el source tree del proyecto en mi maquina local y reporte
5 ZeroDivision y 2 RLock faltantes como bugs. Pero Claude ya los habia
fixeado en commits ANTES de que yo auditara.

Por que paso: Use el source tree del proyecto que tengo cacheado en mi
contexto, en vez de leer el codigo ACTUAL local.

Protocolo correctivo:
1. ANTES de reportar un bug, leer el archivo actual local (`OneDrive/Escritorio/buell/`)
2. No confiar en cache del contexto. El repo local es la fuente de verdad.
3. Cross-check: si Buffy commitio algo que parece fixear el bug,
   verificar con `git log` antes de reportar.
4. `git log --oneline -10` para ver el estado real de commits.

Resultado: 70% de mis hallazgos eran falsos positivos. No volver a repetir.

### 2026-06-28: Migración a workflow local
Que cambio: Ya no hay SSH al Pi para editar código. Todo es local.
El Pi solo hace `git pull` para recibir cambios. freebuff ya no necesita
SSH para auditar — lee los archivos locales directamente.

## Dev tools available on the Windows host

### Graphify — codebase knowledge graph
Graphify runs on Windows. It maps the project into a queryable knowledge graph.

**Workflow:**
  Local commit → graphify update . → graph.html

**Key commands:**
```bash
cd OneDrive/Escritorio/buell
graphify update .              # rebuild after pull (no API key needed)
graphify query "question"      # query the graph without rebuilding
graphify explain "NodeName"    # explain a node and its neighbors
```

**Key god nodes:**
  DashboardHandler (server.py) — SessionManager (ecu/session.py) — BuellLogger (main.py)

**Output files:** graphify-out/graph.html (interactive), graphify-out/GRAPH_REPORT.md
