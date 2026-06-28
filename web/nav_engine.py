#!/usr/bin/env python3
"""
Nav Engine — reads pages.json, generates nav HTML, injects into templates.
Edit pages.json to add/remove/reorder pages in the hamburger menu.
"""

import json
from pathlib import Path

_WEB_DIR = Path(__file__).parent

def _load_pages():
    """Load pages.json. Returns {"nav": [...], "tabs": {...}}"""
    p = _WEB_DIR / "pages.json"
    if not p.exists():
        return {"nav": [], "tabs": {}}
    return json.loads(p.read_text(encoding="utf-8"))

def _render_nav(current_path):
    """Generate nav <a> tags from pages.json.
    current_path: the URL path of the current page (e.g. '/fuel').
    Returns string of <a> tags with active class on current page.
    """
    cfg = _load_pages()
    items = []
    for p in cfg.get("nav", []):
        active = ' class="active"' if p["path"] == current_path else ""
        items.append(f'      <a href="{p["path"]}"{active}>{p["title"]}</a>')
    
    # Add tab links for index.html
    tabs = cfg.get("tabs", {}).get("index.html", [])
    if tabs and current_path == "/":
        items.append('      <div style="border-top:1px solid var(--border);margin:4px 0"></div>')
        # Determine active tab from hash or default
        for t in tabs:
            items.append(f'      <a href="#" class="nav-tab" onclick="{t["js"]}">{t["label"]}</a>')
    
    return "\n".join(items)

def _inject_html(html, current_path):
    """Replace <!--NAV_ITEMS--> placeholder with generated nav HTML."""
    if "<!--NAV_ITEMS-->" not in html:
        return html
    nav = _render_nav(current_path)
    return html.replace("<!--NAV_ITEMS-->", nav)