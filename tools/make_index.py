#!/usr/bin/env python3
"""
tools/make_index.py — Generador automático de ARCHITECTURE.md
Uso manual : python3 tools/make_index.py
Git hook   : .git/hooks/pre-commit (corre automático en cada commit)
"""
import ast
import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.parent
OUT  = REPO / "ARCHITECTURE.md"

def git_version():
    try:
        r = subprocess.run(["git","describe","--tags","--always"],
                           capture_output=True, text=True, cwd=REPO)
        return r.stdout.strip() or "sin-tag"
    except Exception:
        return "sin-tag"

def scan_python(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}
    result = {"classes": [], "functions": [], "constants": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    doc = ast.get_docstring(item) or ""
                    methods.append({"name": item.name, "doc": doc[:60]})
            result["classes"].append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    try:
                        val = ast.literal_eval(node.value)
                        result["constants"].append({"name": t.id, "value": val})
                    except Exception:
                        pass
    return result

def scan_endpoints(path):
    text = path.read_text(encoding="utf-8")
    gets  = re.findall(r"path\s*==\s*['\"]([^'\"]+)['\"]", text)
    posts = re.findall(r"path\s*==\s*['\"]([^'\"]+)['\"].*?POST|POST.*?path\s*==\s*['\"]([^'\"]+)['\"]", text)
    get_routes  = []
    post_routes = []
    for line in text.splitlines():
        if "path ==" in line or "path.startswith" in line:
            route = re.search(r"['\"](/[^'\"]*)['\"]", line)
            if route:
                if "do_GET" in text[max(0,text.find(line)-2000):text.find(line)]:
                    get_routes.append(route.group(1))
                else:
                    post_routes.append(route.group(1))
    return {"get": list(dict.fromkeys(get_routes)),
            "post": list(dict.fromkeys(post_routes))}

def scan_html(path):
    text = path.read_text(encoding="utf-8")
    tabs = re.findall(r"showTab\('(\w+)'\)", text)
    fns  = re.findall(r"^(?:async\s+)?function\s+(\w+)\s*\(", text, re.MULTILINE)
    return {"tabs": list(dict.fromkeys(tabs)),
            "functions": list(dict.fromkeys(fns))}

def scan_install(path):
    steps = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'echo.*\[(\d+)/\d+\]\s+(.+?)\.\.\.', line)
        if m:
            steps.append({"step": m.group(1), "desc": m.group(2)})
    return steps

def file_tree(repo):
    lines = []
    skip = {".git", "__pycache__", ".gitignore", "node_modules"}
    def walk(p, prefix=""):
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        for i, entry in enumerate(entries):
            if entry.name in skip:
                continue
            connector = "└── " if i == len(entries)-1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries)-1 else "│   "
                walk(entry, prefix + extension)
    walk(repo)
    return "\n".join(lines)

def generate():
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    version = git_version()
    lines   = []

    lines.append("# ARCHITECTURE — Buell XB12X DDFI2 Logger")
    lines.append("> Auto-generado por `tools/make_index.py` — no editar manualmente")
    lines.append(f"> Última actualización: {now} | versión: {version}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Estructura del repo")
    lines.append("")
    lines.append("```")
    lines.append("buell-xb12x-logger/")
    lines.append(file_tree(REPO))
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Archivos de datos en runtime
    lines.append("## Archivos de datos (runtime)")
    lines.append("")
    lines.append("| Archivo | Schema | Descripción |")
    lines.append("|---------|--------|-------------|")
    lines.append("| `network_state.json` | `{mode, ip, last_wifi_ip, last_switch_utc}` | Estado de red persistido |")
    lines.append("| `tps_cal.json` | `{min, max}` | Calibración TPS 10bit |")
    lines.append("| `vss_cal.json` | `{cpkm25}` | Calibración velocímetro |")
    lines.append("| `objectives.json` | `{cell_targets[], indicators}` | Objetivos de celda VE |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Módulos Python
    lines.append("## Módulos Python")
    lines.append("")
    skip_files = {"tools/make_index.py"}
    for py in sorted(REPO.rglob("*.py")):
        rel = py.relative_to(REPO)
        if any(str(rel) == s for s in skip_files):
            continue
        if "__pycache__" in str(rel):
            continue
        lines.append(f"### `{rel}`")
        lines.append("")
        data = scan_python(py)
        if "error" in data:
            lines.append(f"_Error al parsear: {data['error']}_")
            lines.append("")
            continue
        if data["constants"]:
            lines.append("**Constantes**")
            lines.append("")
            lines.append("| Nombre | Valor |")
            lines.append("|--------|-------|")
            for c in data["constants"]:
                lines.append(f"| `{c['name']}` | `{c['value']}` |")
            lines.append("")
        for cls in data["classes"]:
            lines.append(f"**Clase `{cls['name']}`**")
            lines.append("")
            if cls["methods"]:
                lines.append("| Método | Docstring |")
                lines.append("|--------|-----------|")
                for m in cls["methods"]:
                    doc = m['doc'].replace('|','\\|') if m['doc'] else "—"
                    lines.append(f"| `{m['name']}` | {doc} |")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Endpoints
    server = REPO / "web" / "server.py"
    if server.exists():
        lines.append("## Endpoints HTTP (`web/server.py`)")
        lines.append("")
        ep = scan_endpoints(server)
        if ep["get"]:
            lines.append("**GET**")
            lines.append("")
            for r in ep["get"]:
                lines.append(f"- `{r}`")
            lines.append("")
        if ep["post"]:
            lines.append("**POST**")
            lines.append("")
            for r in ep["post"]:
                lines.append(f"- `{r}`")
            lines.append("")
        lines.append("---")
        lines.append("")

    # HTML
    html = REPO / "web" / "templates" / "index.html"
    if html.exists():
        lines.append("## Dashboard (`web/templates/index.html`)")
        lines.append("")
        data = scan_html(html)
        if data["tabs"]:
            lines.append("**Tabs**")
            lines.append("")
            for t in data["tabs"]:
                lines.append(f"- `{t}`")
            lines.append("")
        if data["functions"]:
            lines.append("**Funciones JS**")
            lines.append("")
            for f in data["functions"]:
                lines.append(f"- `{f}()`")
            lines.append("")
        lines.append("---")
        lines.append("")

    # install.sh
    install = REPO / "install.sh"
    if install.exists():
        lines.append("## `install.sh`")
        lines.append("")
        steps = scan_install(install)
        if steps:
            lines.append("| Paso | Descripción |")
            lines.append("|------|-------------|")
            for s in steps:
                lines.append(f"| {s['step']} | {s['desc']} |")
        else:
            lines.append("_Sin pasos numerados detectados._")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK — {OUT.relative_to(REPO)} generado ({len(lines)} líneas)")

if __name__ == "__main__":
    generate()
