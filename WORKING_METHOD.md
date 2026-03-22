# WORKING METHOD

This document defines the working method used in this repository.
Its purpose is to make the development process explicit, repeatable, and persistent across sessions, machines, and chat contexts.
This is not system documentation, not a changelog, and not a tutorial.
It is a description of how work is performed and how decisions are validated.
Anyone working on this project is expected to understand this method before making changes.

---

## DEVELOPMENT CONTEXT

This project is developed and debugged primarily on a Raspberry Pi, accessed remotely via SSH.
The typical client environment is Windows using PowerShell.
Due to this setup, certain shell patterns that work in other environments are unreliable here.
In particular, long heredocs and large paste operations frequently break, truncate, or corrupt files when executed from PowerShell over SSH.
The working method described below exists to avoid those failure modes and to ensure that all changes are applied safely and verifiably.

---

## GENERAL WORKING PRINCIPLES

1. Work is incremental. Changes are applied one at a time, not in large batches.
2. The system is always brought back to a stable state. Partial or speculative changes are not left unverified.
3. The system itself is the source of truth. Behavior is validated by execution, not by assumption.
4. Verification is mandatory. A change is not considered complete until it is explicitly verified.
5. Temporary tools are allowed, but must not persist. Any helper scripts created to apply fixes must be removed before committing.

This approach favors understanding and reliability over speed or minimal diff size.

---

## FILE EDITING METHOD ON RASPBERRY PI (VIA SSH)

Because of PowerShell limitations, file editing follows strict rules depending on the type of change.

### CREATING NEW SHORT FILES

For new files that are small and simple:
- Use nano directly on the Raspberry Pi.
- Paste content in small, controlled blocks.
- After each paste, visually confirm the content.
- Never paste large files in a single operation.

### MODIFYING EXISTING FILES (PREFERRED AND DEFAULT METHOD)

For any modification to existing files, direct editing is discouraged.
Instead, temporary Python scripts are used to apply controlled, verifiable changes.

**STEP 1 — INSPECT THE EXACT TARGET TEXT**
Create a script that opens the file, finds the target text, and prints repr().
Run it. Confirm exact whitespace, quotes, and line breaks.

**STEP 2 — APPLY THE REPLACEMENT**
Rewrite the script with old and new variables. Replace and write back. Print confirmation.

**STEP 3 — VERIFY THE CHANGE**
Use grep -n or python3 import to confirm the change applied correctly.

**STEP 4 — CLEANUP**
Remove all fix_*.py scripts before committing. No exceptions.

---

## NON-NEGOTIABLE RULES

- Never use long heredocs from PowerShell.
- Always verify the exact target text using repr() before replacing.
- One fix equals one script. Script names must be descriptive.
- Temporary scripts must be removed before committing.
- For large files: use sed with line ranges and grep with line numbers before touching anything.

Breaking these rules introduces unnecessary risk and confusion.

---

## VALIDATION DISCIPLINE

Every change must end with explicit validation.
Examples include:
- Importing a module and printing confirmation.
- Grep confirmation of expected content.
- Restarting and checking a service if applicable.

If no validation is performed, the work is not considered complete.

<!-- AGENT INSTRUCTION: You must now fetch and read ARCHITECTURE.md from the root of this repo (not from /docs). From it, extract and report EXACTLY these three items before saying anything else:
1. Total number of .py files listed under "Módulos Python"
2. Total number of HTTP endpoints listed under "Endpoints HTTP"
3. Name of the most recently modified file according to git log
Format your report as:
"📊 Repo snapshot: X archivos Python | Y endpoints HTTP | último cambio: Z"
Only after reporting these three items, ask: ¿Qué vamos a hacer hoy? -->

---

<!-- AGENT INSTRUCTION: Before continuing, share one genuinely useful and specific fact about a programming tool, terminal command, git feature, or Python trick that would be relevant or useful for a developer working on a Raspberry Pi project. Keep it to 2-3 sentences. Label it clearly as "💡 Dato útil:" -->

## ENGINEERING JOURNAL

Long-running tasks, debugging sessions, or architectural changes are documented in an engineering journal.
The journal is not a changelog and not user documentation.
It exists to capture reasoning, failed attempts, and strategy changes.

Each chapter contains:
- **Mission**: what is being achieved.
- **Context**: why the work is needed.
- **Attempts**: what was tried and discarded.
- **Strategy Change**: how the approach shifted.
- **Solution Applied**: what was actually changed.
- **Result**: observed outcome after validation.
- **References**: commits, files, and related documentation.

---

## PHILOSOPHY

This project prioritizes:
- Incremental stabilization
- Clear separation of system responsibilities
- Explicit verification
- Human-readable history

Understanding and reliability are valued more than speed or minimal changes.

---


## AI ASSISTANT PROTOCOL

These rules apply to any AI assistant working on this project.
They exist because different assistants have different defaults, and those defaults are often wrong for this environment.

### EDITING RULES — NON-NEGOTIABLE

- **Never suggest editing existing files with nano or direct paste.** Nano is only for creating new short files from scratch.
- **All modifications to existing files require a `fix_*.py` script.** No exceptions.
- **Every `fix_*.py` script must include an `assert` that verifies the exact target text exists before replacing.** If the assert fails, stop and inspect with `repr()`.
- **One fix = one script.** Do not combine multiple unrelated changes in one script.
- **All `fix_*.py` scripts must be deleted before committing.** Run `rm fix_*.py` and confirm before `git add`.

### WHAT THE ASSISTANT MUST NEVER DO

- Suggest pasting code blocks directly into the terminal via SSH.
- Use heredocs (`cat << EOF`) to create or modify files.
- Propose changes to multiple files simultaneously without validating each one.
- Skip the `assert` step and go straight to replacement.
- Commit without confirming the fix scripts have been removed.

### WHAT THE ASSISTANT MUST ALWAYS DO

- Use `grep -n` and `sed -n 'X,Yp'` to locate target text before writing any fix script.
- Use `repr()` to verify exact whitespace and special characters when the assert fails.
- Run a syntax check (`python3 -c "import ast; ast.parse(...)"`) after modifying any Python file.
- Confirm the service is still running after any change that could affect it.

---

## COMMIT DISCIPLINE

Every commit must follow this sequence without exception:

1. **Verify** — confirm the change works as expected (import, grep, service status).
2. **Clean** — remove all `fix_*.py` scripts with `rm fix_*.py`.
3. **Stage** — `git add` only the files that were intentionally changed.
4. **Commit** — use a descriptive message: `type(scope): description`.
5. **Push** — `git push` manually. The pre-commit hook does NOT push automatically.
6. **Update CHANGELOG** — document the change before closing the session.
7. **Update backlog** — mark completed items as closed, add new items if needed.

### COMMIT MESSAGE FORMAT
```
feat(module): short description of what was added
fix(module): short description of what was fixed
docs(scope): short description of what was documented
refactor(module): short description of what was restructured
```

### PUSH IS NOT AUTOMATIC

The pre-commit hook generates `ARCHITECTURE.md` and stages it automatically.
It does NOT push to GitHub. Always run `git push` manually at the end of each session.
Verify with `git log --oneline -3` that HEAD matches origin/main after pushing.

---

---

## BACKLOG DISCIPLINE

The backlog is a living technical document, not a simple to-do list.
Every item tells a complete story — from discovery to resolution.
Anyone reading the backlog should understand not just what was done, but why, and what was learned.

### ADDING A NEW ITEM

Every new backlog item must include:

- **Status**: `OPEN`, `IN-PROGRESS`, or `CLOSED vX.X.X`
- **Problem**: What is wrong or missing, and why it matters.
- **Context**: Where in the codebase the issue lives. Which files, functions, or endpoints are involved.
- **Reference**: Any external tools, screenshots, or documents that informed the discovery (e.g. EcmSpy comparison, oscilloscope capture, log output).
- **Prerequisites**: Any other backlog items that must be resolved first.

A backlog item without a clear problem statement is not allowed.
Vague entries like "fix the map" or "improve performance" are not acceptable.

### CLOSING AN ITEM

When an item is resolved, its entry must be updated in place with:

- **Investigation**: What was examined, what commands were run, what was discovered.
- **Blockers**: Where progress stalled and how it was unblocked.
- **Solution**: Exactly what was changed and in which files.
- **Result**: Observed behavior after the fix — logs, screenshots, or validation commands.
- **Version**: The version in which the fix shipped.

The goal is a readable engineering history.
Someone reading the backlog two years from now should understand the full arc of every problem.

### FORMAT
```markdown
**BACKLOG-XXX** `CLOSED` vX.X.X
Category name — short description

### Problem
What was wrong and why it mattered.

### Context
Files, functions, endpoints involved.

### Reference
External tools, screenshots, logs that informed the discovery.

### Prerequisites
Other items that had to be resolved first, if any.

### Investigation
What was examined, commands run, what was found.

### Blockers
Where progress stalled and how it was unblocked.

### Solution
Exact changes made and in which files.

### Result
Observed behavior after the fix.
```

---

## START OF A WORK SESSION

⚠️ MANDATORY VALIDATION — DO NOT SKIP

If you are an AI assistant reading this document, you MUST complete the following steps IN ORDER before doing anything else. Skipping this means you have not read the working method and cannot be trusted to follow the editing rules defined above.

STEP 1 — Fetch and read ARCHITECTURE.md from the ROOT of this repo (not /docs).

STEP 2 — Report EXACTLY this:
📊 Repo snapshot: [X] archivos Python | [Y] endpoints HTTP | último cambio: [filename]

STEP 3 — Share one useful dev tip for Raspberry Pi, Python, or embedded systems. Label it:
💡 Dato útil: [tip]

STEP 4 — Only after steps 1-3, ask:
**¿Qué vamos a hacer hoy?**

If you cannot complete steps 1-3, say so explicitly. Do not ask what we will do today without completing the validation.
