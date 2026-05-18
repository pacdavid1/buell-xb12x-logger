#!/usr/bin/env python3
"""Unifica grid de Segundos + grid de Flavors en pestaña Cobertura."""
import re
from pathlib import Path

BASE = Path('/home/pi/buell')

def patch_cell_tracker():
    fp = BASE / 'ddfi2_logger.py'
    src = fp.read_text()
    i = src.index('class CellTracker:')
    j = src.index('\n\nclass LiveHandler', i)
    new = '''class CellTracker:
    """Acumula tiempo, EGO y flavor por celda VE 13x12."""
    FLAVORS = ("SWEET", "TIPIN", "TIPOUT", "WOT", "BITTER")

    def __init__(self):
        self.cells     = {}
        self.active    = None
        self._lock     = threading.Lock()
        self._dt       = 1.0 / 8.0
        self._prev_tps = None

    def reset(self):
        with self._lock:
            self.cells     = {}
            self.active    = None
            self._prev_tps = None

    def _classify_flavor(self, tps_10bit):
        tps_pct = (tps_10bit or 0) / 10.23
        if tps_pct > 80: return "WOT"
        if tps_pct < 10: return "BITTER"
        if self._prev_tps is not None:
            delta = (tps_10bit - self._prev_tps) / 10.23
            if delta > 1.5: return "TIPIN"
            if delta < -1.5: return "TIPOUT"
        return "SWEET"

    def update(self, data):
        rpm  = data.get("RPM",  0) or 0
        load = data.get("Load", 0) or 0
        ego  = data.get("EGO_Corr", 100) or 100
        tps  = data.get("TPS_10Bit", 0) or 0
        if rpm < 300:
            with self._lock:
                self.active = None
                self._prev_tps = None
            return
        key = cell_key(rpm, load)
        flavor = self._classify_flavor(tps)
        with self._lock:
            self.active = key
            self._prev_tps = tps
            c = self.cells.setdefault(key, {
                "seconds": 0.0, "ego_sum": 0.0, "count": 0,
                "flavor_seconds": {f: 0.0 for f in self.FLAVORS}
            })
            c["seconds"] += self._dt
            c["ego_sum"] += ego
            c["count"]   += 1
            c["flavor_seconds"][flavor] += self._dt

    def snapshot(self):
        with self._lock:
            snap = {}
            for k, v in self.cells.items():
                avg = round(v["ego_sum"]/v["count"], 1) if v["count"] else 100.0
                sweet = v["flavor_seconds"].get("SWEET", 0.0)
                conf = min(1.0, sweet / 20.0)
                snap[k] = {
                    "seconds":       round(v["seconds"], 1),
                    "ego_avg":       avg,
                    "confidence":    round(conf, 2),
                    "flavor_counts": {f: round(s, 1) for f, s in v["flavor_seconds"].items()},
                }
            return snap, self.active

'''
    src = src[:i] + new + src[j:]
    fp.write_text(src)
    print(f"  OK {fp.name}: CellTracker con flavor tracking")

def patch_get_coverage():
    fp = BASE / 'web' / 'server.py'
    src = fp.read_text()
    i = src.index('    def _get_coverage(self):')
    j = src.index('\n    def ', i + 10)
    new = '''    def _get_coverage(self):
        """Cobertura unificada: segundos, EGO, flavors por celda."""
        if not self.cell_tracker:
            return {"error": "tracker no disponible", "cells": {}, "summary": {}}
        snap, active = self.cell_tracker.snapshot()
        targets = self._coverage_targets
        flavors = [f for f in ("SWEET", "TIPIN", "TIPOUT", "WOT") if targets.get(f, 0) > 0]
        cells_out = {}
        summary = {f: {"done": 0, "total": 0, "pct": 0.0} for f in flavors}
        for key, c in snap.items():
            fc   = c.get("flavor_counts", {})
            conf = c.get("confidence", 0.0)
            entry = {
                "seconds": c.get("seconds", 0.0),
                "ego_avg": c.get("ego_avg", 100.0),
                "confidence": conf,
                "flavors": {},
            }
            for f in flavors:
                ts = targets[f]
                actual = fc.get(f, 0.0)
                conv = conf >= 0.8
                done = actual >= ts and conv
                pct = round(min(100.0, actual / ts * 100), 1) if ts > 0 else 0.0
                entry["flavors"][f] = {
                    "seconds": round(actual, 1), "target_s": ts,
                    "pct": pct, "converged": conv, "done": done
                }
                summary[f]["total"] += 1
                if done: summary[f]["done"] += 1
            cells_out[key] = entry
        for f in flavors:
            t, d = summary[f]["total"], summary[f]["done"]
            summary[f]["pct"] = round(d/t*100, 1) if t > 0 else 0.0
        return {
            "targets": targets, "cells": cells_out, "summary": summary,
            "active_cell": active, "n_cells": len(cells_out),
        }

'''
    src = src[:i] + new + src[j:]
    fp.write_text(src)
    print(f"  OK {fp.name}: _get_coverage unificado")

def patch_html():
    fp = BASE / 'web' / 'templates' / 'index.html'
    src = fp.read_text()

    # A) Tab "Cobertura" después de "Ride"
    src = src.replace(
        "showTab('ride');trackUsage('tab_ride')\">Ride</div>\n  <div class=\"tab\" onclick=\"showTab('rides')",
        "showTab('ride');trackUsage('tab_ride')\">Ride</div>\n  <div class=\"tab\" onclick=\"showTab('cobert');loadCobert();trackUsage('tab_cobert')\">Cobertura</div>\n  <div class=\"tab\" onclick=\"showTab('rides')"
    )

    # B) Sacar grid-section viejo del pane-ride
    src = re.sub(
        r'\n    <div class="grid-section">.*?id="objList"></div>',
        '\n    <div class="obj-row-compact" id="objList"></div>',
        src, count=1, flags=re.DOTALL
    )

    # C) Pane cobert antes de pane-rides
    pane = '''
  <!-- PANE COBERTURA -->
  <div class="pane content" id="pane-cobert" style="user-select:none;-webkit-user-select:none">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px">
      <div class="grid-label" style="margin:0;border:none;padding:0">Cobertura de celdas</div>
      <div style="display:flex;gap:3px;flex-wrap:wrap" id="cobert-btns">
        <button class="btn cobert-btn active" data-mode="seconds" onclick="setCobertMode('seconds')" style="font-size:8px;padding:3px 6px">Segundos</button>
        <button class="btn cobert-btn" data-mode="ego" onclick="setCobertMode('ego')" style="font-size:8px;padding:3px 6px">EGO</button>
        <button class="btn cobert-btn" data-mode="SWEET" onclick="setCobertMode('SWEET')" style="font-size:8px;padding:3px 6px;color:#7df">SWEET</button>
        <button class="btn cobert-btn" data-mode="TIPIN" onclick="setCobertMode('TIPIN')" style="font-size:8px;padding:3px 6px;color:#3d3">TIPIN</button>
        <button class="btn cobert-btn" data-mode="TIPOUT" onclick="setCobertMode('TIPOUT')" style="font-size:8px;padding:3px 6px;color:#fa3">TIPOUT</button>
        <button class="btn cobert-btn" data-mode="WOT" onclick="setCobertMode('WOT')" style="font-size:8px;padding:3px 6px;color:#f74">WOT</button>
      </div>
    </div>
    <div class="grid-wrap"><table class="veg" id="cobertGrid"></table></div>
    <div class="legend" id="cobert-legend"></div>
    <div class="obj-row-compact" id="cobert-summary"></div>
  </div>
'''
    src = src.replace('  <!-- PANE RIDES -->', pane + '  <!-- PANE RIDES -->')

    # D) Reemplazar seccion GRID vieja con nueva COBERTURA
    new_js = '''// ── COBERTURA UNIFICADA ──────────────────────────────────
let _cobertMode = 'seconds';
let _cobertData = null;
let _cobertTimer = null;

function setCobertMode(mode) {
  _cobertMode = mode;
  document.querySelectorAll('.cobert-btn').forEach(b => {
    const a = b.dataset.mode === mode;
    b.style.borderColor = a ? 'var(--accent2)' : '';
    b.style.color = a ? 'var(--accent2)' : '';
  });
  renderCobertLegend();
  if (_cobertData) renderCobertGrid(_cobertData);
}

function buildCobertGrid() {
  const t = document.getElementById('cobertGrid');
  if (!t || t.children.length) return;
  let h = '<thead><tr><th class="rh">L\\\\R</th>';
  for (const r of RPM_BINS) h += `<th>${r===0?'0':r>=1000?(r/1000)+'k':r}</th>`;
  h += '</tr></thead><tbody>';
  for (let li = LOAD_BINS.length-1; li >= 0; li--) {
    h += `<tr><th class="rh">${LOAD_BINS[li]}</th>`;
    for (let ri = 0; ri < RPM_BINS.length; ri++) {
      const k = `${RPM_BINS[ri]}_${LOAD_BINS[li]}`;
      h += `<td id="gc_${k}" class="c0"><div class="cv" id="gs_${k}"></div></td>`;
    }
    h += '</tr>';
  }
  h += '</tbody>';
  t.innerHTML = h;
}

function egoColor(e) {
  if(e<90)return'rgba(255,50,50,0.9)';if(e<95)return'rgba(255,160,50,0.85)';
  if(e<105)return'rgba(50,200,50,0.8)';if(e<110)return'rgba(50,150,255,0.85)';
  return'rgba(80,80,255,0.9)';
}
function pctColor(p) {
  let r,g,b;
  if(p<=50){const t=p/50;r=231;g=Math.round(76+120*t);b=60;}
  else{const t=(p-50)/50;r=Math.round(231-185*t);g=Math.round(196+8*t);b=Math.round(60+53*t);}
  return`rgb(${r},${g},${b})`;
}

function renderCobertLegend() {
  const el = document.getElementById('cobert-legend');
  if(!el) return;
  const m = _cobertMode;
  if (m === 'seconds') {
    el.innerHTML = '<div class="leg"><div class="leg-dot c0"></div>Sin datos</div>'
      +'<div class="leg"><div class="leg-dot c1"></div>&lt;2s</div>'
      +'<div class="leg"><div class="leg-dot c2"></div>2-5s</div>'
      +'<div class="leg"><div class="leg-dot c3"></div>5-10s</div>'
      +'<div class="leg"><div class="leg-dot c4"></div>&gt;10s</div>'
      +'<div class="leg"><div class="leg-dot ca"></div>Activa</div>';
  } else if (m === 'ego') {
    el.innerHTML = '<div class="leg"><div class="leg-dot" style="background:rgba(255,50,50,.9)"></div>&lt;90</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(255,160,50,.85)"></div>90-95</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,200,50,.8)"></div>95-105</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,150,255,.85)"></div>105-110</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(80,80,255,.9)"></div>&gt;110</div>';
  } else {
    const tgt = (_cobertData&&_cobertData.targets&&_cobertData.targets[m]) || '?';
    el.innerHTML = `<div class="leg" style="color:var(--dim)">${m} target: ${tgt}s \\u00b7 conf\\u226580% para converger</div>`;
  }
}

function renderCobertGrid(d) {
  const cells = d.cells || {}, ac = d.active_cell || null, m = _cobertMode;
  for (let li = 0; li < LOAD_BINS.length; li++) {
    for (let ri = 0; ri < RPM_BINS.length; ri++) {
      const k = `${RPM_BINS[ri]}_${LOAD_BINS[li]}`;
      const td = document.getElementById(`gc_${k}`), sv = document.getElementById(`gs_${k}`);
      if (!td || !sv) continue;
      const c = cells[k] || {};
      let bg = 'c0', txt = '', isSt = false;
      if (m === 'seconds') {
        const s = c.seconds || 0;
        bg = k===ac ? 'ca' : s<=0?'c0':s<2?'c1':s<5?'c2':s<10?'c3':'c4';
        txt = s > 0 ? (s<10?s.toFixed(1):Math.round(s))+'s' : '';
      } else if (m === 'ego') {
        const e = c.ego_avg;
        if (c.seconds > 0 && e != null) {
          bg = 'background:' + egoColor(e); txt = e.toFixed(1); isSt = true;
        }
      } else {
        const fl = (c.flavors || {})[m];
        if (fl) {
          const p = fl.pct || 0, col = pctColor(p);
          bg = 'background:' + col.replace('rgb','rgba').replace(')',',0.2)');
          txt = fl.done ? '\\u2713' : p.toFixed(0) + '%';
          sv.style.color = col; isSt = true;
        }
      }
      td.className = isSt ? '' : bg;
      td.style.cssText = isSt ? bg : '';
      if (!isSt) sv.style.color = '';
      sv.textContent = txt;
    }
  }
  // Summary chips
  const sel = document.getElementById('cobert-summary');
  if (sel && d.summary) {
    const cols = {SWEET:'#7df',TIPIN:'#3d3',TIPOUT:'#fa3',WOT:'#f74'};
    sel.innerHTML = Object.entries(d.summary).map(([f, s]) => {
      const p = s.pct||0, col = p>=100?'#2ecc71':p>=50?'#f1c40f':'#e74c3c';
      return `<div class="obj-chip ${p>=100?'done':p>0?'partial':''}"><div class="obj-chip-label" style="color:${cols[f]||'#aaa'}">${f}</div><div class="obj-chip-pct" style="color:${col}">${p.toFixed(0)}%</div><div class="obj-bar"><div class="obj-fill ${p>=100?'done':''}" style="width:${p}%"></div></div><div class="obj-chip-sub">${s.done}/${s.total}</div></div>`;
    }).join('');
  }
}

async function loadCobert() {
  buildCobertGrid();
  renderCobertLegend();
  if (_cobertTimer) clearInterval(_cobertTimer);
  const poll = async () => {
    try {
      const r = await fetch('/coverage.json?t='+Date.now());
      if (!r.ok) return;
      const d = await r.json();
      _cobertData = d;
      renderCobertGrid(d);
    } catch(e) {}
  };
  poll();
  _cobertTimer = setInterval(poll, 1000);
}

'''
    gs = src.index('// ── GRID ─')
    ge = src.index('// ── BOTTOM SHEET ─', gs)
    src = src[:gs] + new_js + src[ge:]

    # E) Sacar Coverage Tracker viejo completo
    cs = src.index('// ── Coverage Tracker ─')
    ce = src.index('// ── /Coverage Tracker ─', cs) + len('// ── /Coverage Tracker ─') + 1
    src = src[:cs] + src[ce:]

    # F) Limpiar variables viejas
    for pat in ['let _cobertFlavor', 'let _cobertInterval', 'const RPM_BINS_COV', 'const LOAD_BINS_COV']:
        src = re.sub(pat + r' .+;\n', '', src)

    # G) Sacar updateGrid del fetchLive
    src = src.replace("updateGrid(d.cells||{}, d.active_cell);\n", '')
    src = src.replace("updateGrid(_d.cells||{}, _d.active_cell);\n", '')
    src = src.replace("updateGrid(cells,null);\n", '')

    # H) DOMContentLoaded: buildCobertGrid en vez de buildGrid
    src = src.replace('buildGrid();', 'buildCobertGrid();')

    fp.write_text(src)
    print(f"  OK {fp.name}: pestaña Cobertura unificada")

if __name__ == '__main__':
    print("Parcheando archivos...")
    patch_cell_tracker()
    patch_get_coverage()
    patch_html()
    print("Listo. Ejecutá: sudo systemctl restart buell-logger")
