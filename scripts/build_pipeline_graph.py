# DEV NOTE: All code, comments, and variable names must be in English.
"""Build a standalone left-to-right layered DAG view of docs/PIPELINE_DATA_FLOW.md.

Parses the NODE/EDGE lines from that markdown file, computes a layered
("Sugiyama-style") column layout via longest-path from raw-data sources,
and emits a single self-contained SVG+HTML file: docs/pipeline_graph.html.

No JS charting library — plain SVG generated server-side plus a small
vanilla-JS layer for pan/zoom, click-to-inspect, and reliability filters,
consistent with the project's "no charting libraries" convention.

Re-run this after editing docs/PIPELINE_DATA_FLOW.md to refresh the view:
    python scripts/build_pipeline_graph.py
"""
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "PIPELINE_DATA_FLOW.md"
OUT = Path(__file__).resolve().parent.parent / "docs" / "pipeline_graph.html"
# Optional: exported from the "export layout" button in the HTML viewer and
# dropped here. When present, its positions win over the computed layout so
# a manual arrangement survives regeneration (and can be committed to git).
LAYOUT_OVERRIDE = Path(__file__).resolve().parent.parent / "docs" / "pipeline_layout.json"

FLOW_LABELS = {"computed_from", "feeds_into", "displayed_in", "gated_by"}
GAP_LABELS = {"not_consumed_by"}

RELIABILITY_COLOR = {
    "ACTIVE_VALID": "#3ddc84",
    "ACTIVE_UNVALIDATED": "#e8b923",
    "INACTIVE_NOISE": "#6b6b70",
    "CAPTURED_UNUSED": "#4a9eff",
    "DESIGN_ONLY": "#b06fe0",
}
TYPE_LABEL = {
    "raw_signal": "RAW",
    "sensor": "SENSOR",
    "json_artifact": "JSON",
    "annotation": "ANNOTATION",
    "analysis_stage": "ANALYSIS",
    "ui_page": "UI",
}
# color, dasharray ("" = solid), stroke width — solid = real data flow,
# dashed = either a design-time gate (not necessarily wired yet) or an
# explicitly documented gap (data that should feed something but doesn't).
EDGE_STYLE = {
    "computed_from": ("#9a9aa0", "", "1.6"),
    "feeds_into": ("#9a9aa0", "", "1.6"),
    "displayed_in": ("#4a9eff", "", "1.6"),
    "gated_by": ("#e8b923", "7,4", "2.2"),
    "not_consumed_by": ("#ff5c5c", "3,3", "2.2"),
}
LOOP_STYLE = ("#b06fe0", "9,5", "2.2")
EDGE_LEGEND = [
    ("#9a9aa0", "", "computed_from / feeds_into — real data flow"),
    ("#4a9eff", "", "displayed_in — reaches a UI page"),
    ("#e8b923", "7,4", "gated_by — intended gate/dependency"),
    ("#ff5c5c", "3,3", "not_consumed_by — documented GAP: exists, nothing reads it"),
    ("#b06fe0", "9,5", "feedback loop (e.g. QUEMAR → new session → LOG)"),
]


def parse(doc_text: str):
    nodes = {}
    edges = []
    for raw_line in doc_text.splitlines():
        line = raw_line.strip()
        if line.startswith("NODE |"):
            parts = [p.strip() for p in line.split("|")]
            parts = (parts + [""] * 6)[:6]
            _, nid, ntype, fileref, reliability, note = parts
            m = re.match(r"([A-Z_]+)\s*(\((.*)\))?", reliability)
            rel_cat = m.group(1) if m else reliability
            rel_extra = (m.group(3) if m and m.group(3) else "").strip()
            nodes[nid] = {
                "id": nid, "type": ntype, "fileref": fileref,
                "reliability": rel_cat, "reliability_extra": rel_extra,
                "note": note,
            }
        elif line.startswith("EDGE |"):
            parts = [p.strip() for p in line.split("|")]
            parts = (parts + [""] * 4)[:4]
            _, src, dst, label = parts
            edges.append({"src": src, "dst": dst, "label": label})
    return nodes, edges


# Edges that are semantically the "feedback" side of a cycle, even when DFS
# traversal order would have picked a different (technically valid but less
# intuitive) edge to break. E.g. ui_tuner -> eeprom_bin is the QUEMAR
# write-back that closes the LOG->...->QUEMAR->LOG cycle; without this,
# DFS order alone might instead arc vs_merge_maps -> ui_tuner, which reads
# as a normal forward step, not a loop.
FORCED_LOOP_EDGES = {
    ("ui_tuner", "eeprom_bin"),        # QUEMAR write-back closes LOG->...->QUEMAR->LOG
    ("ui_map_editor", "eeprom_bin"),   # same pattern: reads then writes back
    ("vdyno_fase_v4", "burns_json"),   # a new proposal becomes a new burn, same pattern
}


def break_cycles(node_ids, succ):
    """DFS-based back-edge detection. Returns set of (u, v) back edges."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in node_ids}
    back_edges = set()
    sys.setrecursionlimit(10000)

    def dfs(u):
        color[u] = GRAY
        for v in succ[u]:
            if color[v] == WHITE:
                dfs(v)
            elif color[v] == GRAY:
                back_edges.add((u, v))
        color[u] = BLACK

    for n in node_ids:
        if color[n] == WHITE:
            dfs(n)
    return back_edges


def compute_layers(nodes, flow_edges):
    node_ids = list(nodes.keys())
    succ = {n: [] for n in node_ids}
    pred = {n: [] for n in node_ids}
    for e in flow_edges:
        if e["src"] in nodes and e["dst"] in nodes:
            succ[e["src"]].append(e["dst"])
            pred[e["dst"]].append(e["src"])

    forced = {(s, d) for (s, d) in FORCED_LOOP_EDGES if s in nodes and d in nodes}
    # Remove forced-loop edges before DFS so they can't also get "naturally"
    # detected, and so removing them can legitimately break the cycle they're
    # part of instead of leaving DFS to pick some other edge in it.
    succ_minus_forced = {n: [v for v in succ[n] if (n, v) not in forced] for n in node_ids}
    back_edges = break_cycles(node_ids, succ_minus_forced) | forced
    acyc_pred = {n: [p for p in pred[n] if (p, n) not in back_edges] for n in node_ids}
    acyc_succ = {n: [s for s in succ[n] if (n, s) not in back_edges] for n in node_ids}

    indeg = {n: len(acyc_pred[n]) for n in node_ids}
    layer = {n: 0 for n in node_ids}
    q = deque([n for n in node_ids if indeg[n] == 0])
    seen = set(q)
    while q:
        u = q.popleft()
        for v in acyc_succ[u]:
            layer[v] = max(layer[v], layer[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0 and v not in seen:
                q.append(v)
                seen.add(v)
    return layer, back_edges


def order_layers(nodes, cols, flow_edges, iterations=8):
    """Barycenter heuristic: iteratively reorder each column by the average
    row-position of its connected neighbors (regardless of their column),
    alternating sweep direction, to reduce edge crossings/overlaps."""
    neighbors = defaultdict(list)
    for e in flow_edges:
        if e["src"] in nodes and e["dst"] in nodes:
            neighbors[e["src"]].append(e["dst"])
            neighbors[e["dst"]].append(e["src"])

    pos_in_col = {}
    for ns in cols.values():
        for i, n in enumerate(ns):
            pos_in_col[n] = i

    sorted_cols = sorted(cols.keys())
    for it in range(iterations):
        sweep = sorted_cols if it % 2 == 0 else list(reversed(sorted_cols))
        for c in sweep:
            ns = cols[c]

            def barycenter(n):
                neigh_pos = [pos_in_col[m] for m in neighbors[n] if m in pos_in_col]
                return sum(neigh_pos) / len(neigh_pos) if neigh_pos else pos_in_col[n]

            ns_sorted = sorted(ns, key=lambda n: (barycenter(n), pos_in_col[n]))
            cols[c] = ns_sorted
            for i, n in enumerate(ns_sorted):
                pos_in_col[n] = i
    return cols


def load_layout_override():
    if not LAYOUT_OVERRIDE.exists():
        return {}
    try:
        return json.loads(LAYOUT_OVERRIDE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def assign_positions(nodes, layer, flow_edges, col_w=280, row_h=84, pad=50):
    cols = defaultdict(list)
    decl_order = {n: i for i, n in enumerate(nodes.keys())}
    for n in nodes:
        cols[layer[n]].append(n)
    for c in cols:
        cols[c].sort(key=lambda n: decl_order[n])

    cols = order_layers(nodes, cols, flow_edges)

    pos = {}
    for c, ns in cols.items():
        for i, n in enumerate(ns):
            pos[n] = (c * col_w + pad, i * row_h + pad)

    overrides = load_layout_override()
    max_x = max_y = 0
    for nid, xy in overrides.items():
        if nid in nodes and isinstance(xy, (list, tuple)) and len(xy) == 2:
            pos[nid] = (xy[0], xy[1])
    for x, y in pos.values():
        max_x, max_y = max(max_x, x), max(max_y, y)

    max_col = max(cols.keys()) if cols else 0
    max_rows = max((len(ns) for ns in cols.values()), default=0)
    width = max((max_col + 1) * col_w + pad * 2 + 220, max_x + 300)
    height = max(max_rows * row_h + pad * 2, max_y + 150)
    return pos, width, height


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _marker_id(color: str) -> str:
    return "arrow-" + re.sub(r"[^a-zA-Z0-9]", "", color)


def build_svg(nodes, flow_edges, gap_edges, back_edges, pos, width, height):
    box_w, box_h = 220, 54
    parts = [f'<svg id="graph-svg" xmlns="http://www.w3.org/2000/svg" '
             f'width="{width}" height="{max(height, 600)}" '
             f'viewBox="0 0 {width} {max(height, 600)}">']
    parts.append('<g id="pan-group">')

    def anchor_right(n):
        x, y = pos[n]
        return x + box_w, y + box_h / 2

    def anchor_left(n):
        x, y = pos[n]
        return x, y + box_h / 2

    used_colors = set()

    # Edges first (under nodes)
    def draw_edge(e, is_back):
        src, dst, label = e["src"], e["dst"], e["label"]
        if src not in pos or dst not in pos:
            return ""
        color, dash, w = EDGE_STYLE.get(label, ("#666", "", "1.4"))
        x1, y1 = anchor_right(src)
        x2, y2 = anchor_left(dst)
        if is_back:
            color, dash, w = LOOP_STYLE
            dy = 60
            path = f"M {x1} {y1} C {x1+40} {y1+dy}, {x2-40} {y2+dy}, {x2} {y2}"
        else:
            dx = max(40, (x2 - x1) / 2)
            path = f"M {x1} {y1} C {x1+dx} {y1}, {x2-dx} {y2}, {x2} {y2}"
        used_colors.add(color)
        dash_attr = f'stroke-dasharray="{dash}" ' if dash else ""
        marker = f' marker-end="url(#{_marker_id(color)})"'
        return (f'<path class="edge" data-src="{esc(src)}" data-dst="{esc(dst)}" '
                f'data-label="{esc(label)}" data-back="{"1" if is_back else "0"}" '
                f'd="{path}" stroke="{color}" stroke-width="{w}" {dash_attr}'
                f'fill="none" opacity="0.6"{marker}>'
                f'<title>{esc(src)} --[{esc(label)}]--&gt; {esc(dst)}</title></path>')

    for e in flow_edges:
        is_back = (e["src"], e["dst"]) in back_edges
        parts.append(draw_edge(e, is_back))
    for e in gap_edges:
        parts.append(draw_edge(e, False))

    # Nodes on top
    for nid, n in nodes.items():
        if nid not in pos:
            continue
        x, y = pos[nid]
        color = RELIABILITY_COLOR.get(n["reliability"], "#888")
        dashed = 'stroke-dasharray="5,3"' if n["reliability"] == "DESIGN_ONLY" else ""
        type_label = TYPE_LABEL.get(n["type"], n["type"].upper())
        note_full = n["note"] + (f" [{n['reliability_extra']}]" if n["reliability_extra"] else "")
        label = nid if len(nid) <= 24 else nid[:22] + "…"
        parts.append(
            f'<g class="node" data-id="{esc(nid)}" data-x="{x}" data-y="{y}" '
            f'data-reliability="{esc(n["reliability"])}" '
            f'data-note="{esc(note_full)}" data-fileref="{esc(n["fileref"])}" '
            f'data-type="{esc(n["type"])}" transform="translate({x},{y})">'
            f'<rect width="{box_w}" height="{box_h}" rx="6" fill="#15151a" '
            f'stroke="{color}" stroke-width="2" {dashed}></rect>'
            f'<rect width="{box_w}" height="16" rx="6" fill="{color}" opacity="0.18"></rect>'
            f'<text x="8" y="12" class="type-label" fill="{color}">{esc(type_label)}</text>'
            f'<text x="8" y="34" class="node-label">{esc(label)}</text>'
            f'<title>{esc(nid)} [{esc(n["reliability"])}]\n{esc(n["fileref"])}\n{esc(note_full)}</title>'
            f'</g>'
        )

    # One arrowhead marker per distinct edge color used, colored to match.
    marker_defs = ["<defs>"]
    for color in used_colors:
        marker_defs.append(
            f'<marker id="{_marker_id(color)}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"></path></marker>'
        )
    marker_defs.append("</defs>")
    parts.insert(0, "".join(marker_defs))
    parts.append("</g></svg>")
    return "\n".join(parts)


HTML_TEMPLATE = """<!DOCTYPE html>
<!-- DEV NOTE: All code, comments, and variable names must be in English. -->
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pipeline Data Flow — Buell Logger</title>
<style>
  :root {{
    --bg: #0a0a0b; --panel: #111114; --accent: #e8420a; --fg: #d8d8dc; --muted: #7a7a80;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background: var(--bg); color: var(--fg);
          font-family: 'Share Tech Mono', 'Consolas', monospace; overflow: hidden; }}
  #topbar {{ position: fixed; top:0; left:0; right:0; height:56px; background: var(--panel);
             border-bottom: 1px solid #222; display:flex; align-items:center; gap:16px;
             padding: 0 16px; z-index: 10; }}
  #topbar h1 {{ font-size: 14px; color: var(--accent); margin:0; letter-spacing:1px;
                white-space:nowrap; }}
  #legend {{ display:flex; gap:10px; flex-wrap:wrap; font-size:11px; }}
  .legend-item {{ display:flex; align-items:center; gap:4px; cursor:pointer; opacity:1;
                   user-select:none; padding:2px 6px; border-radius:4px; }}
  .legend-item.off {{ opacity:0.3; }}
  .swatch {{ width:10px; height:10px; border-radius:2px; display:inline-block; }}
  #edge-legend {{ position:fixed; top:64px; left:8px; background:var(--panel); border:1px solid #222;
                   padding:8px 10px; font-size:10px; z-index:9; border-radius:4px; }}
  #edge-legend .row {{ display:flex; align-items:center; gap:6px; margin:3px 0; }}
  #edge-legend .line {{ width:22px; height:0; border-top-width:2px; border-top-style:solid; }}
  #canvas-wrap {{ position:absolute; top:56px; left:0; right:340px; bottom:0; overflow:hidden;
                  cursor:grab; transition: right 0.15s; }}
  #canvas-wrap.dragging {{ cursor:grabbing; }}
  #canvas-wrap.panel-hidden {{ right:0; }}
  #sidepanel {{ position:fixed; top:56px; right:0; bottom:0; width:340px; background:var(--panel);
                border-left:1px solid #222; padding:16px; overflow-y:auto; font-size:12px;
                transition: transform 0.15s; }}
  #sidepanel.hidden {{ transform: translateX(340px); }}
  #panel-toggle {{ background:var(--panel); color:var(--fg); border:1px solid #333;
                    font-size:10px; padding:4px 8px; cursor:pointer; margin-left:auto; }}
  #showall-toggle {{ font-size:11px; display:flex; align-items:center; gap:5px; cursor:pointer;
                      user-select:none; }}
  #sidepanel h2 {{ font-size:13px; color: var(--accent); margin-top:0; word-break:break-all; }}
  #sidepanel .field {{ margin-bottom:10px; }}
  #sidepanel .field-label {{ color: var(--muted); font-size:10px; text-transform:uppercase; }}
  #sidepanel .edge-row {{ font-size:11px; padding:3px 4px; cursor:pointer; border-radius:3px; }}
  #sidepanel .edge-row:hover {{ background:#1c1c22; }}
  #sidepanel .muted {{ color: var(--muted); font-size:11px; }}
  .node {{ cursor:grab; }}
  .node text.type-label {{ font-size:8px; letter-spacing:1px; }}
  .node text.node-label {{ font-size:10px; fill: var(--fg); }}
  .node.dim {{ opacity: 0.12; }}
  .node.hi rect:first-of-type {{ stroke-width:3; }}
  .node.upstream rect:first-of-type {{ filter: drop-shadow(0 0 5px #4a9eff); }}
  .node.downstream rect:first-of-type {{ filter: drop-shadow(0 0 5px #e8420a); }}
  .edge {{ transition: opacity 0.15s; }}
  .edge.dim {{ opacity: 0.05 !important; }}
  .edge.hi {{ opacity: 1 !important; stroke-width: 3 !important; }}
  body.show-all .edge {{ opacity: 1 !important; }}
  body.show-all .node.dim {{ opacity: 1; }}
  #hint {{ position:fixed; bottom:8px; left:8px; font-size:10px; color: var(--muted); z-index:10; }}
  #zoomctl {{ position:fixed; bottom:8px; right:352px; z-index:10; display:flex; gap:6px; }}
  #zoomctl button {{ background:var(--panel); color:var(--fg); border:1px solid #333;
                      width:26px; height:26px; cursor:pointer; }}
  #zoomctl button#reset-layout {{ width:auto; padding:0 8px; font-size:10px; color:#ff5c5c;
                                   border-color:#5a2020; }}
  #zoomctl button.safe {{ width:auto; padding:0 8px; font-size:10px; }}
  #save-status {{ font-size:10px; color: var(--muted); opacity:0.4; transition: opacity 0.3s;
                   align-self:center; }}
</style>
</head>
<body>
<div id="topbar">
  <h1>PIPELINE DATA FLOW</h1>
  <div id="legend"></div>
  <label id="showall-toggle"><input type="checkbox" id="showall-check"> show ALL connections at full brightness</label>
  <button id="panel-toggle">hide info panel</button>
</div>
<div id="edge-legend">{edge_legend_html}</div>
<div id="canvas-wrap">{svg}</div>
<div id="sidepanel"><p style="color:var(--muted)">Click a node to inspect it — the panel lists
exactly what feeds it and what it feeds. Drag a node to reposition it (saved automatically).
Two-finger scroll / wheel pans; pinch or Ctrl+wheel zooms.</p></div>
<div id="zoomctl"><button id="zin">+</button><button id="zout">-</button><button id="zreset">1:1</button>
<button id="export-layout" class="safe" title="Download current node positions as a JSON file">export layout ⬇</button>
<label class="safe" style="background:var(--panel); border:1px solid #333; padding:0 8px;
  font-size:10px; cursor:pointer; display:inline-flex; align-items:center;">
  import layout ⬆<input id="import-layout-file" type="file" accept="application/json" style="display:none">
</label>
<span id="save-status"></span>
<button id="reset-layout">reset positions</button></div>
<div id="hint">source: docs/PIPELINE_DATA_FLOW.md — regenerate with scripts/build_pipeline_graph.py</div>
<script>
const RELIABILITY_COLOR = {reliability_color_json};
const legend = document.getElementById('legend');
const active = new Set(Object.keys(RELIABILITY_COLOR));
for (const [rel, color] of Object.entries(RELIABILITY_COLOR)) {{
  const el = document.createElement('div');
  el.className = 'legend-item';
  el.dataset.rel = rel;
  el.innerHTML = `<span class="swatch" style="background:${{color}}"></span>${{rel}}`;
  el.onclick = () => {{
    if (active.has(rel)) {{ active.delete(rel); el.classList.add('off'); }}
    else {{ active.add(rel); el.classList.remove('off'); }}
    applyFilter();
  }};
  legend.appendChild(el);
}}

function applyFilter() {{
  document.querySelectorAll('.node').forEach(n => {{
    n.style.display = active.has(n.dataset.reliability) ? '' : 'none';
  }});
}}

const svg = document.getElementById('graph-svg');
const wrap = document.getElementById('canvas-wrap');
const sidepanel = document.getElementById('sidepanel');
const BOX_W = 220, BOX_H = 54;
const LS_KEY = 'buell_pipeline_graph_pos_v1';

const nodeById = {{}};
document.querySelectorAll('.node').forEach(n => {{ nodeById[n.dataset.id] = n; }});

let scale = 0.85, panX = 40, panY = 0;
function applyTransform() {{
  document.getElementById('pan-group').setAttribute('transform',
    `translate(${{panX}},${{panY}}) scale(${{scale}})`);
}}
applyTransform();

// ---- canvas pan/zoom (two-finger scroll = pan, pinch/ctrl+wheel = zoom) ----
let panning = false, lastX = 0, lastY = 0;
wrap.addEventListener('mousedown', e => {{
  if (e.target.closest('.node')) return; // node drag handles itself
  panning = true; lastX = e.clientX; lastY = e.clientY; wrap.classList.add('dragging');
}});
window.addEventListener('mouseup', () => {{ panning = false; wrap.classList.remove('dragging'); }});
window.addEventListener('mousemove', e => {{
  if (!panning) return;
  panX += (e.clientX - lastX); panY += (e.clientY - lastY);
  lastX = e.clientX; lastY = e.clientY;
  applyTransform();
}});
wrap.addEventListener('wheel', e => {{
  e.preventDefault();
  if (e.ctrlKey || e.metaKey) {{
    const dy = Math.max(-60, Math.min(60, e.deltaY));
    const factor = Math.exp(-dy * 0.012);
    scale = Math.min(3, Math.max(0.15, scale * factor));
  }} else {{
    panX -= e.deltaX;
    panY -= e.deltaY;
  }}
  applyTransform();
}}, {{passive: false}});
document.getElementById('showall-check').addEventListener('change', e => {{
  document.body.classList.toggle('show-all', e.target.checked);
}});
document.getElementById('panel-toggle').onclick = () => {{
  const hidden = sidepanel.classList.toggle('hidden');
  wrap.classList.toggle('panel-hidden', hidden);
  document.getElementById('panel-toggle').textContent = hidden ? 'show info panel' : 'hide info panel';
}};
document.getElementById('zin').onclick = () => {{ scale = Math.min(3, scale*1.2); applyTransform(); }};
document.getElementById('zout').onclick = () => {{ scale = Math.max(0.15, scale/1.2); applyTransform(); }};
document.getElementById('zreset').onclick = () => {{ scale=0.85; panX=40; panY=0; applyTransform(); }};
document.getElementById('reset-layout').onclick = () => {{
  const ok = confirm('This discards your saved node positions and reloads the computed ' +
    'layout. This cannot be undone unless you already exported a backup with ' +
    '"export layout". Continue?');
  if (!ok) return;
  localStorage.removeItem(LS_KEY);
  location.reload();
}};

document.getElementById('export-layout').onclick = () => {{
  const data = {{}};
  document.querySelectorAll('.node').forEach(n => {{ data[n.dataset.id] = [+n.dataset.x, +n.dataset.y]; }});
  const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'pipeline_layout.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}};

document.getElementById('import-layout-file').addEventListener('change', e => {{
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {{
    try {{
      const data = JSON.parse(reader.result);
      document.querySelectorAll('.node').forEach(n => {{
        const saved = data[n.dataset.id];
        if (!saved) return;
        n.dataset.x = saved[0]; n.dataset.y = saved[1];
        n.setAttribute('transform', `translate(${{saved[0]}},${{saved[1]}})`);
      }});
      document.querySelectorAll('.node').forEach(n => updateEdgesFor(n.dataset.id));
      saveLayout();
      alert('Layout imported from file and saved.');
    }} catch (err) {{ alert('Could not read that file as a layout JSON: ' + err.message); }}
  }};
  reader.readAsText(file);
  e.target.value = '';
}});

// ---- edge geometry (mirrors the Python layout math) ----
function anchorRight(n) {{ return [+n.dataset.x + BOX_W, +n.dataset.y + BOX_H/2]; }}
function anchorLeft(n)  {{ return [+n.dataset.x, +n.dataset.y + BOX_H/2]; }}
function pathFor(x1, y1, x2, y2, isBack) {{
  if (isBack) {{
    const dy = 60;
    return `M ${{x1}} ${{y1}} C ${{x1+40}} ${{y1+dy}}, ${{x2-40}} ${{y2+dy}}, ${{x2}} ${{y2}}`;
  }}
  const dx = Math.max(40, (x2 - x1) / 2);
  return `M ${{x1}} ${{y1}} C ${{x1+dx}} ${{y1}}, ${{x2-dx}} ${{y2}}, ${{x2}} ${{y2}}`;
}}
function updateEdgesFor(nodeId) {{
  document.querySelectorAll('.edge').forEach(edge => {{
    if (edge.dataset.src !== nodeId && edge.dataset.dst !== nodeId) return;
    const s = nodeById[edge.dataset.src], d = nodeById[edge.dataset.dst];
    if (!s || !d) return;
    const [x1, y1] = anchorRight(s);
    const [x2, y2] = anchorLeft(d);
    edge.setAttribute('d', pathFor(x1, y1, x2, y2, edge.dataset.back === '1'));
  }});
}}

// ---- drag-to-reposition, persisted per node id in localStorage ----
function saveLayout() {{
  const data = {{}};
  document.querySelectorAll('.node').forEach(n => {{ data[n.dataset.id] = [+n.dataset.x, +n.dataset.y]; }});
  localStorage.setItem(LS_KEY, JSON.stringify(data));
  const status = document.getElementById('save-status');
  if (status) {{
    status.textContent = 'saved to browser ' + new Date().toLocaleTimeString();
    status.style.opacity = '1';
    clearTimeout(saveLayout._t);
    saveLayout._t = setTimeout(() => {{ status.style.opacity = '0.4'; }}, 2500);
  }}
}}
(function restoreLayout() {{
  const raw = localStorage.getItem(LS_KEY);
  if (!raw) return;
  try {{
    const data = JSON.parse(raw);
    document.querySelectorAll('.node').forEach(n => {{
      const saved = data[n.dataset.id];
      if (!saved) return;
      n.dataset.x = saved[0]; n.dataset.y = saved[1];
      n.setAttribute('transform', `translate(${{saved[0]}},${{saved[1]}})`);
    }});
    document.querySelectorAll('.node').forEach(n => updateEdgesFor(n.dataset.id));
  }} catch (err) {{ /* ignore corrupt saved layout */ }}
}})();

let dragNode = null, dragStart = null, dragMoved = false;
document.querySelectorAll('.node').forEach(n => {{
  n.addEventListener('mousedown', e => {{
    e.stopPropagation();
    dragNode = n; dragMoved = false;
    dragStart = {{ mx: e.clientX, my: e.clientY, x: +n.dataset.x, y: +n.dataset.y }};
    n.style.cursor = 'grabbing';
  }});
}});
window.addEventListener('mousemove', e => {{
  if (!dragNode) return;
  const dx = (e.clientX - dragStart.mx) / scale;
  const dy = (e.clientY - dragStart.my) / scale;
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dragMoved = true;
  const nx = dragStart.x + dx, ny = dragStart.y + dy;
  dragNode.dataset.x = nx; dragNode.dataset.y = ny;
  dragNode.setAttribute('transform', `translate(${{nx}},${{ny}})`);
  updateEdgesFor(dragNode.dataset.id);
}});
window.addEventListener('mouseup', () => {{
  if (dragNode) {{
    dragNode.style.cursor = 'grab';
    if (dragMoved) saveLayout();
    else selectNode(dragNode.dataset.id);
    dragNode = null;
  }}
}});

// ---- full-graph adjacency for transitive (multi-hop) ancestor/descendant highlight ----
// "not_consumed_by" edges are excluded here on purpose: they document an
// ABSENCE of flow, so nothing should be considered "reached" through them.
const succAdj = {{}}, predAdj = {{}};
document.querySelectorAll('.node').forEach(n => {{ succAdj[n.dataset.id] = []; predAdj[n.dataset.id] = []; }});
document.querySelectorAll('.edge').forEach(e => {{
  if (e.dataset.label === 'not_consumed_by') return;
  const s = e.dataset.src, d = e.dataset.dst;
  if (succAdj[s]) succAdj[s].push(d);
  if (predAdj[d]) predAdj[d].push(s);
}});
function bfs(startId, adj) {{
  const visited = new Set([startId]);
  const queue = [startId];
  while (queue.length) {{
    const u = queue.shift();
    for (const v of (adj[u] || [])) {{
      if (!visited.has(v)) {{ visited.add(v); queue.push(v); }}
    }}
  }}
  visited.delete(startId);
  return visited;
}}

// ---- selection: full upstream/downstream chain highlighted, immediate edges listed by name ----
function selectNode(id) {{
  const n = nodeById[id];
  if (!n) return;
  const ancestors = bfs(id, predAdj);     // everything upstream, any number of hops
  const descendants = bfs(id, succAdj);   // everything downstream, any number of hops
  const relevant = new Set([id, ...ancestors, ...descendants]);

  document.querySelectorAll('.node').forEach(x => {{
    x.classList.remove('hi', 'dim', 'upstream', 'downstream');
    const xid = x.dataset.id;
    if (xid === id) {{ x.classList.add('hi'); return; }}
    if (ancestors.has(xid)) x.classList.add('upstream');
    else if (descendants.has(xid)) x.classList.add('downstream');
    else x.classList.add('dim');
  }});
  document.querySelectorAll('.edge').forEach(x => {{
    const direct = x.dataset.src === id || x.dataset.dst === id;
    const chained = relevant.has(x.dataset.src) && relevant.has(x.dataset.dst);
    x.classList.toggle('hi', direct || chained);
    x.classList.toggle('dim', !(direct || chained));
  }});

  const out = [], inn = [];
  document.querySelectorAll('.edge').forEach(x => {{
    if (x.dataset.src === id) out.push({{to: x.dataset.dst, label: x.dataset.label}});
    if (x.dataset.dst === id) inn.push({{from: x.dataset.src, label: x.dataset.label}});
  }});
  const fmt = (label) => label === 'not_consumed_by' ? '⚠ NOT USED by' : label;
  const rowHtml = (other, label) =>
    `<div class="edge-row" data-jump="${{other}}">${{fmt(label)}} → <b>${{other}}</b></div>`;
  const outHtml = out.length ? out.map(o => rowHtml(o.to, o.label)).join('') : '<div class="muted">(nothing)</div>';
  const inHtml = inn.length ? inn.map(o => rowHtml(o.from, o.label)).join('') : '<div class="muted">(nothing)</div>';

  sidepanel.innerHTML = `
    <h2>${{id}}</h2>
    <div class="field"><div class="field-label">type</div>${{n.dataset.type}}</div>
    <div class="field"><div class="field-label">reliability</div>
      <span style="color:${{RELIABILITY_COLOR[n.dataset.reliability] || '#888'}}">${{n.dataset.reliability}}</span></div>
    <div class="field"><div class="field-label">source</div>${{n.dataset.fileref}}</div>
    <div class="field"><div class="field-label">note</div>${{n.dataset.note}}</div>
    <div class="field"><div class="field-label" style="color:#4a9eff">full upstream chain — ${{ancestors.size}} node(s)</div>
      everything that eventually feeds this, any number of hops (glowing blue on canvas)</div>
    <div class="field"><div class="field-label" style="color:#e8420a">full downstream chain — ${{descendants.size}} node(s)</div>
      everything this eventually affects, any number of hops (glowing orange on canvas)</div>
    <div class="field"><div class="field-label">← feeds INTO this directly (${{inn.length}})</div>${{inHtml}}</div>
    <div class="field"><div class="field-label">this feeds → directly (${{out.length}})</div>${{outHtml}}</div>
  `;
  sidepanel.querySelectorAll('.edge-row').forEach(row => {{
    row.onclick = () => selectNode(row.dataset.jump);
  }});
}}
</script>
</body>
</html>
"""


def main():
    text = DOC.read_text(encoding="utf-8")
    nodes, edges = parse(text)
    flow_edges = [e for e in edges if e["label"] in FLOW_LABELS]
    gap_edges = [e for e in edges if e["label"] in GAP_LABELS]

    layer, back_edges = compute_layers(nodes, flow_edges)
    pos, width, height = assign_positions(nodes, layer, flow_edges)
    svg = build_svg(nodes, flow_edges, gap_edges, back_edges, pos, width, height)

    edge_legend_rows = []
    for color, dash, desc in EDGE_LEGEND:
        style = f"border-top-color:{color};" + (
            "border-top-style:dashed;" if dash else "border-top-style:solid;")
        edge_legend_rows.append(
            f'<div class="row"><span class="line" style="{style}"></span>{esc(desc)}</div>')
    edge_legend_html = "\n".join(edge_legend_rows)

    html = HTML_TEMPLATE.format(
        svg=svg,
        edge_legend_html=edge_legend_html,
        reliability_color_json=str(RELIABILITY_COLOR).replace("'", '"'),
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} — {len(nodes)} nodes, {len(flow_edges)} flow edges, "
          f"{len(gap_edges)} gap edges, {len(back_edges)} loop-back edges, "
          f"{max(layer.values())+1 if layer else 0} columns")


if __name__ == "__main__":
    main()
