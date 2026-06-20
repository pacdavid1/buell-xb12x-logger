#!/usr/bin/env python3
"""Generate ARCHITECTURE.md from the actual file tree on disk.

Scans the repo directory, extracts Python module-level docstrings
for descriptions, and writes a living architecture document that
mirrors what's actually on disk. Run after any major structural change.

Usage: python3 scripts/gen_architecture.py
"""

import os
import sys
import ast
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", "sessions",
    ".mypy_cache", ".pytest_cache",
}
SKIP_FILES = {".gitkeep", ".DS_Store", "__init__.py"}


def get_py_summary(path):
    """Extract first line of module-level docstring from a .py file."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            src = f.read()
        tree = ast.parse(src)
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            first = tree.body[0].value.value.strip().split("\n")[0]
            if 0 < len(first) < 120:
                return first
    except Exception:
        pass
    return None


def walk(root, depth=0, max_depth=4):
    """Recursively walk the directory and build markdown lines."""
    if depth > max_depth:
        return []
    lines = []
    indent = "  " * depth
    try:
        items = sorted(os.listdir(root))
    except PermissionError:
        return lines
    for name in items:
        full = os.path.join(root, name)
        if os.path.isdir(full):
            if name in SKIP_DIRS:
                continue
            lines.append(f"{indent}- **{name}/**")
            lines.extend(walk(full, depth + 1, max_depth))
        else:
            if name in SKIP_FILES:
                continue
            ext = os.path.splitext(name)[1].lower()
            summary = get_py_summary(full) if ext == ".py" else None
            if summary:
                lines.append(f"{indent}- `{name}` -- {summary}")
            else:
                lines.append(f"{indent}- `{name}`")
    return lines


def build():
    """Build the full ARCHITECTURE.md content."""
    # Get git HEAD info
    git_desc = ""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%h %ai"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            git_desc = r.stdout.strip()
    except Exception:
        pass

    lines = [
        "# ARCHITECTURE -- Buell XB12X DDFI2 Logger",
        "",
    ]
    if git_desc:
        lines.append(f"> *{git_desc}*")
    lines.append("> Mapa vivo del repositorio. Generado automaticamente del directorio real.")
    lines.append("> Regenerar: `python3 scripts/gen_architecture.py`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Mapa del proyecto")
    lines.append("")
    lines.append("Cada entrada corresponde a un archivo o directorio real en disco.")
    lines.append("Los archivos `.py` muestran su docstring de modulo como descripcion.")
    lines.append("")
    lines.append("### Directorios principales")
    lines.append("")
    lines.append("- `ecu/` -- Comunicacion con ECU DDFI-2 (protocolo, sesiones, EEPROM)")
    lines.append("- `ecu_defs/` -- Definiciones XML por modelo de ECM")
    lines.append("- `web/` -- Servidor HTTP, handlers, frontend (dashboard, GRAF2, VDYNO, F7)")
    lines.append("- `gps/` -- Lector GPS serial")
    lines.append("- `network/` -- Gestor WiFi/Hotspot")
    lines.append("- `sensors/` -- Sensores I2C (AHT20 temp/humedad, CW2015 bateria)")
    lines.append("- `tools/` -- Diagnostico y salud del sistema")
    lines.append("- `docs/` -- Documentacion detallada en markdown")
    lines.append("- `archive/` -- Scripts y docs obsoletos preservados")
    lines.append("- `inbox/` -- Ideas, notas y archivos en proceso")
    lines.append("- `scripts/` -- Utilidades (gen_architecture.py)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Arbol completo")
    lines.append("")
    lines.extend(walk(ROOT))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> Generado automaticamente. Para actualizar: `python3 scripts/gen_architecture.py`")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    output = build()
    dst = os.path.join(ROOT, "ARCHITECTURE.md")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"ARCHITECTURE.md regenerated ({len(output)} chars, {len(output.splitlines())} lines) at {dst}")
