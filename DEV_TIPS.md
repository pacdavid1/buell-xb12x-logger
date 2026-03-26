# DEV TIPS — Buell XB12X DDFI2 Logger

Useful commands, tricks, and tools collected during development sessions.
Add new tips as they come up — one per entry, dated.

---

## Raspberry Pi / SSH

**2026-03-25** — Locate a function across all project files instantly:
```bash
grep -rn "def my_function\|my_keyword" /home/pi/buell/
```
Faster than opening files one by one. Use when tracing a broken JS → endpoint → backend chain.

---

## Git

**2026-03-25** — Check that local HEAD matches origin after push:
```bash
git log --oneline -3
```
If the top commit hash matches what GitHub shows, the push succeeded.

---

## Python / Debugging

**2026-03-25** — Before replacing text in a fix script, always verify exact whitespace:
```python
with open("file.py") as f:
    content = f.read()
idx = content.find("target text")
print(repr(content[idx-20:idx+60]))
```
repr() reveals hidden spaces, tabs, and newlines that would cause silent assert failures.

---
