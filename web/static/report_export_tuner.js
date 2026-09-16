// DEV NOTE: All code, comments, and variable names must be in English.
// Standalone Tuner report export.
//
// Bundles the currently-compared session pair (base vs mod, for the map
// tab and diff mode on screen right now) plus a self-contained,
// dependency-free copy of the BASE/DELTA/MOD 3D renderer and the
// BASE/DELTA/MOD/MERGED comparison tables from tuner.html into a single
// downloadable .html file. No external references -- opens and rotates
// the same whether the Pi is reachable or not.
//
// This is a read-only snapshot: no burn/reset/merge-recompute/INV-toggle
// controls are carried over, only the 3D drag-to-rotate + wheel-to-zoom
// interaction (synced across all three canvases, same as the live page).
// Keep this in sync with tuner.html's render()/drawSurf()/drawDelta() if
// those change shape.

function _tunerReportBuildPayload() {
  var bMap = (mB.maps || {})[cur], mMap = (mM.maps || {})[cur];
  if (!bMap || !mMap) return null;
  var xk = bMap.xaxis, yk = bMap.yaxis;
  var rpmAxis = xk && mB.axes[xk] ? mB.axes[xk] : { data: [], units: '' };
  var lodAxis = yk && mB.axes[yk] ? mB.axes[yk] : { data: [], units: '' };
  var sB = document.getElementById('sB'), sM = document.getElementById('sM');
  var baseLabel = sB && sB.options[sB.selectedIndex] ? sB.options[sB.selectedIndex].textContent : '';
  var modLabel = sM && sM.options[sM.selectedIndex] ? sM.options[sM.selectedIndex].textContent : '';
  var merge = null;
  if (mMerge && mMerge.maps && mMerge.maps[cur]) {
    merge = { mode: mergeMode, merged: mMerge.maps[cur].merged };
  }
  return {
    cur: cur, dm: DM,
    label: cur.toUpperCase().replace(/_/g, ' '),
    units: bMap.units || '',
    baseLabel: baseLabel, modLabel: modLabel,
    generated: new Date().toISOString(),
    rpm: rpmAxis.data || [], rpmUnits: rpmAxis.units || 'RPM',
    lod: lodAxis.data || [], lodUnits: lodAxis.units || 'TPS',
    bD: bMap.data, mD: mMap.data,
    staged: Object.keys(STAGE[cur] || {}),
    sc: SC[cur] || 0.4, scDelta: SC['delta'] || 0.08,
    inv: { X: !!INV.X, Y: !!INV.Y, Z: !!INV.Z },
    zoomAlt: parseFloat((document.getElementById('inZoom') || {}).value) || 0.7,
    opa: (parseFloat((document.getElementById('inOpa') || {}).value) || 20) / 100,
    cam: { ang: C3.base.ang, tilt: C3.base.tilt, roll: C3.base.roll, zoom: CAM.zoom },
    merge: merge
  };
}

function exportTunerReport() {
  if (!mB || !mM || !cur) { st('Load base and mod sessions first'); return; }
  var payload = _tunerReportBuildPayload();
  if (!payload) { st('Current map not available in both sessions'); return; }
  var html = _tunerReportBuildHtml(payload);
  var blob = new Blob([html], { type: 'text/html' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'tuner_report_' + payload.cur + '_' + payload.generated.slice(0, 10) + '.html';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  st('Tuner report downloaded');
}

function _tunerReportBuildHtml(payload) {
  var dataJson = JSON.stringify(payload).replace(/</g, '\\u003c');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tuner Report -- ${payload.label}</title>
<style>
:root{--bg:#0a0a0b;--p:#111114;--bd:#1e1e24;--ac:#e8420a;--a2:#f5a623;--bl:#3d9eff;--dm:#555;--tx:#c8c8cc;--rd:#ff4444;--staged:#a07800;--mn:'JetBrains Mono',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:sans-serif;font-size:13px}
.rpt-hd{background:var(--p);border-bottom:2px solid var(--ac);padding:12px 20px}
.rpt-title{font-family:var(--mn);font-size:16px;font-weight:700;color:var(--ac);letter-spacing:.12em;text-transform:uppercase}
.rpt-meta{font-family:var(--mn);font-size:11px;color:var(--dm);margin-top:4px;letter-spacing:.04em}
.rpt-meta b{color:var(--a2)}
.hint{font-family:var(--mn);font-size:10px;color:var(--dm);padding:6px 20px;letter-spacing:.04em}
.tblbar{display:flex;gap:0;overflow-x:auto;padding:8px 20px;flex-wrap:wrap}
.tw{display:flex;flex-direction:column;flex-shrink:0}
.tw.tb table{border-right:2px solid var(--a2)}
.tw.tm table{border-left:2px solid var(--a2)}
table.v{border-collapse:collapse;font-family:var(--mn);white-space:nowrap}
table.v caption{font-size:9px;color:var(--ac);padding:2px 3px;text-align:left;letter-spacing:.1em;font-weight:700}
table.v th{font-size:8px;color:var(--dm);padding:0 2px;text-align:center;min-width:26px}
table.v th.r{text-align:right;min-width:28px;padding-right:3px}
table.v td{width:30px;height:18px;border:1px solid rgba(255,255,255,.03);text-align:center;vertical-align:middle;font-size:9px;font-weight:700;color:#fff}
.dpp{color:#fff;background:rgba(255,50,50,.25)!important}.dp{color:var(--rd)}
.dnn{color:#fff;background:rgba(50,130,255,.25)!important}.dn{color:var(--bl)}
.dzz{color:#444!important;background:rgba(255,255,255,.01)!important}
.g3{display:flex;gap:0;min-height:280px;border-top:1px solid rgba(255,255,255,.03)}
.g3c{flex:1;min-width:220px;display:flex;flex-direction:column;background:var(--p)}
.g3t{font-family:var(--mn);font-size:10px;font-weight:700;color:var(--a2);padding:3px 6px;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02)}
.g3c canvas{display:block;flex:1;touch-action:none;width:100%;min-height:260px;cursor:grab}
.leg{display:flex;align-items:center;gap:4px;font-family:var(--mn);font-size:8px;color:var(--dm);padding:3px 6px;border-top:1px solid var(--bd)}
.leg .bar{flex:1;height:6px;border-radius:2px}
#cellTip{position:fixed;pointer-events:none;z-index:50;display:none;background:var(--p);border:1px solid var(--bd);padding:3px 8px;border-radius:2px;font-family:var(--mn);font-size:11px;color:var(--tx);line-height:1.7;white-space:nowrap}
</style>
</head>
<body>
<div class="rpt-hd">
  <div class="rpt-title">&#9670; Tuner Report</div>
  <div class="rpt-meta">${payload.label} &middot; base <b>${payload.baseLabel || '?'}</b> vs mod <b>${payload.modLabel || '?'}</b> &middot; mode ${payload.dm.toUpperCase()}${payload.staged.length ? ' &middot; <span style="color:var(--staged)">' + payload.staged.length + ' staged (unburned)</span>' : ''}</div>
  <div class="rpt-meta">generated ${payload.generated.slice(0, 19).replace('T', ' ')} UTC</div>
</div>
<div class="hint">Static snapshot &mdash; drag any 3D view to rotate (synced), scroll to zoom. No live data, no server connection needed.</div>
<div class="tblbar" id="tblbar"></div>
<div class="g3">
<div class="g3c"><div class="g3t">BASE 3D</div><canvas id="c3b"></canvas><div class="leg" id="lb"></div></div>
<div class="g3c"><div class="g3t">DELTA 3D</div><canvas id="c3d"></canvas><div class="leg" id="ld"></div></div>
<div class="g3c"><div class="g3t">MOD 3D</div><canvas id="c3m"></canvas><div class="leg" id="lm"></div></div>
</div>
<div id="cellTip"></div>
<script>
(function() {
'use strict';
var DATA = ${dataJson};
var bD = DATA.bD, mD = DATA.mD, rpm = DATA.rpm, lod = DATA.lod;
var rows = lod.length, cols = rpm.length;
var STAGE = {}; STAGE[DATA.cur] = {};
DATA.staged.forEach(function(stk) { STAGE[DATA.cur][stk] = true; });
var SC = {}; SC[DATA.cur] = DATA.sc; SC['delta'] = DATA.scDelta;
var INV = DATA.inv;
var DM = DATA.dm;
var CAM = { zoom: DATA.cam.zoom || 1 };
var C3 = {
  base: { ang: DATA.cam.ang, tilt: DATA.cam.tilt, roll: DATA.cam.roll, drag: false, lx: 0, ly: 0 },
  delta: { ang: DATA.cam.ang, tilt: DATA.cam.tilt, roll: DATA.cam.roll, drag: false, lx: 0, ly: 0 },
  mod: { ang: DATA.cam.ang, tilt: DATA.cam.tilt, roll: DATA.cam.roll, drag: false, lx: 0, ly: 0 }
};

function axisPositions(vals, count) {
  var arr = [];
  for (var k = 0; k < count; k++) arr.push(vals[k] !== undefined ? vals[k] : k);
  var mn = Math.min.apply(null, arr), mx = Math.max.apply(null, arr);
  if (mx === mn) mx = mn + 1;
  var span = mx - mn;
  return arr.map(function(v) { return (v - mn) / span * (count - 1); });
}
var MAP_RANGES = { fuel: { mn: 0, mx: 200 }, timing: { mn: 0, mx: 50 }, dflt: { mn: 0, mx: 255 } };
function computeDataRange(data) {
  var mn = Infinity, mx = -Infinity;
  (data || []).forEach(function(row) { (Array.isArray(row) ? row : [row]).forEach(function(v) { var n = parseFloat(v); if (!isNaN(n)) { mn = Math.min(mn, n); mx = Math.max(mx, n); } }); });
  if (!isFinite(mn)) return MAP_RANGES.dflt;
  var span = mx - mn; if (span < 1) { mn -= 1; mx += 1; }
  return { mn: mn, mx: mx };
}
function getRange(units, data) {
  if (!units) return computeDataRange(data);
  var u = units.toLowerCase();
  if (u.indexOf('fuel') >= 0) return MAP_RANGES.fuel;
  if (u.indexOf('timing') >= 0 || u.indexOf('spark') >= 0 || u.indexOf('degree') >= 0) return MAP_RANGES.timing;
  return computeDataRange(data);
}
function heat3D(t) {
  var r, g, b;
  if (t < 0.2) { var s = t / 0.2; r = 15; g = Math.round(10 + 60 * s); b = Math.round(80 + 140 * s); }
  else if (t < 0.4) { var s = (t - 0.2) / 0.2; r = Math.round(15 + 20 * s); g = Math.round(70 + 130 * s); b = Math.round(220 + 35 * s); }
  else if (t < 0.6) { var s = (t - 0.4) / 0.2; r = Math.round(35 + 120 * s); g = Math.round(200 + 55 * s); b = Math.round(255 - 155 * s); }
  else if (t < 0.8) { var s = (t - 0.6) / 0.2; r = Math.round(155 + 100 * s); g = Math.round(255 - 60 * s); b = Math.round(100 - 70 * s); }
  else { var s = (t - 0.8) / 0.2; r = 255; g = Math.round(195 - 145 * s); b = Math.round(30 - 10 * s); }
  return 'rgba(' + r + ',' + g + ',' + b + ',0.9)';
}
function heatRGB(t) {
  var r, g, b;
  if (t < 0.2) { var s = t / 0.2; r = 15; g = Math.round(10 + 60 * s); b = Math.round(80 + 140 * s); }
  else if (t < 0.4) { var s = (t - 0.2) / 0.2; r = Math.round(15 + 20 * s); g = Math.round(70 + 130 * s); b = Math.round(220 + 35 * s); }
  else if (t < 0.6) { var s = (t - 0.4) / 0.2; r = Math.round(35 + 120 * s); g = Math.round(200 + 55 * s); b = Math.round(255 - 155 * s); }
  else if (t < 0.8) { var s = (t - 0.6) / 0.2; r = Math.round(155 + 100 * s); g = Math.round(255 - 60 * s); b = Math.round(100 - 70 * s); }
  else { var s = (t - 0.8) / 0.2; r = 255; g = Math.round(195 - 145 * s); b = Math.round(30 - 10 * s); }
  return 'rgba(' + r + ',' + g + ',' + b + ',0.7)';
}
function shadeRGBA(col, f) {
  var m = col.match(/rgba?\\(([\\d.]+),([\\d.]+),([\\d.]+)(?:,([\\d.]+))?\\)/);
  if (!m) return col;
  return 'rgba(' + Math.round(m[1] * f) + ',' + Math.round(m[2] * f) + ',' + Math.round(m[3] * f) + ',' + (m[4] !== undefined ? m[4] : 1) + ')';
}

// ── comparison tables (read-only port of tuner.html's render()) ─────────────
function hdr() { var h = '<tr><th></th>'; for (var j = 0; j < cols; j++) h += '<th>' + rpm[j] + '</th>'; return h + '</tr>'; }
function rangeOf(data) { var n = 1e9, x = -1e9; for (var i = 0; i < data.length; i++) for (var j = 0; j < data[0].length; j++) { if (data[i][j] < n) n = data[i][j]; if (data[i][j] > x) x = data[i][j]; } if (x === n) x = n + 1; return [n, x]; }
function tbl(data, cap) {
  var rng = rangeOf(data), zN = rng[0], zX = rng[1];
  var h = '<table class="v"><caption>' + cap + '</caption>' + hdr();
  for (var i = rows - 1; i >= 0; i--) {
    h += '<tr><th class="r">' + lod[i] + '</th>';
    for (var j = 0; j < cols; j++) {
      var t = (data[i][j] - zN) / (zX - zN);
      var sk = i + ',' + j, isStaged = !!(STAGE[DATA.cur] || {})[sk];
      var bg = isStaged ? '#a07800' : heatRGB(t);
      h += '<td data-rpm="' + rpm[j] + '" data-tps="' + lod[i] + '" data-val="' + data[i][j].toFixed(1) + '" style="background:' + bg + '">' + data[i][j].toFixed(0) + '</td>';
    }
    h += '</tr>';
  }
  return h + '</table>';
}
function dtbl() {
  var mx = 0;
  for (var i = 0; i < rows; i++) for (var j = 0; j < cols; j++) { var v = Math.abs(mD[i][j] - bD[i][j]); if (v > mx) mx = v; }
  var h = '<table class="v"><caption>DELTA</caption>' + hdr();
  for (var i2 = rows - 1; i2 >= 0; i2--) {
    h += '<tr><th class="r">' + lod[i2] + '</th>';
    for (var j2 = 0; j2 < cols; j2++) {
      var d = mD[i2][j2] - bD[i2][j2], ad = Math.abs(d), cls = 'dzz', txt = '\\u00B7';
      if (ad > 0.3) { txt = (d > 0 ? '+' : '') + d.toFixed(1); var ratio = mx > 0 ? ad / mx : 0; cls = ratio > 0.5 ? (d > 0 ? 'dpp' : 'dnn') : (d > 0 ? 'dp' : 'dn'); }
      h += '<td class="' + cls + '" data-rpm="' + rpm[j2] + '" data-tps="' + lod[i2] + '" data-val="' + d.toFixed(2) + '">' + txt + '</td>';
    }
    h += '</tr>';
  }
  return h + '</table>';
}
function mergeTbl() {
  var md = DATA.merge, mr = md.merged;
  var mv = mr.map(function(rw) { return rw.map(function(c) { return c.v; }); });
  var rng = rangeOf(mv), mn = rng[0], mx = rng[1];
  var h = '<table class="v"><caption>MERGED (' + md.mode + ')</caption>' + hdr();
  for (var i = rows - 1; i >= 0; i--) {
    h += '<tr><th class="r">' + lod[i] + '</th>';
    for (var j = 0; j < cols; j++) {
      var c = mr[i][j], ct = (c.v - mn) / (mx - mn);
      var bg = c.s === 'A' ? 'rgba(50,180,80,0.4)' : c.s === 'B' ? 'rgba(60,120,220,0.4)' : c.s === 'AVG' ? 'rgba(80,80,80,0.25)' : heatRGB(ct);
      h += '<td style="background:' + bg + '" title="' + c.s + '">' + c.v.toFixed(0) + '</td>';
    }
    h += '</tr>';
  }
  return h + '</table>';
}
function renderTables() {
  var html = '<div class="tw tb">' + tbl(bD, 'BASE') + '</div>' +
             '<div class="tw">' + dtbl() + '</div>' +
             '<div class="tw tm">' + tbl(mD, 'MOD') + '</div>';
  if (DATA.merge) html += '<div class="tw tm" style="border-left:2px solid var(--a2)">' + mergeTbl() + '</div>';
  document.getElementById('tblbar').innerHTML = html;
  var tip = document.getElementById('cellTip');
  document.getElementById('tblbar').addEventListener('mouseover', function(e) {
    var td = e.target.closest('td'); if (!td || !td.dataset.rpm) return;
    tip.innerHTML = DATA.rpmUnits + ': <b>' + td.dataset.rpm + '</b>  ' + DATA.lodUnits + ': <b>' + td.dataset.tps + '</b>  val: <b>' + td.dataset.val + '</b>';
    tip.style.display = 'block';
  });
  document.getElementById('tblbar').addEventListener('mousemove', function(e) { tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY - 30) + 'px'; });
  document.getElementById('tblbar').addEventListener('mouseleave', function() { tip.style.display = 'none'; });
}

// ── 3D renderer (read-only port of tuner.html's drawSurf/drawDelta) ─────────
function drawSurf(cid, data, mode, legId, units) {
  var el = document.getElementById(cid); if (!el || !data || !data.length) return;
  var ctx = el.getContext('2d'), key = cid === 'c3b' ? 'base' : cid === 'c3d' ? 'delta' : 'mod';
  var c = C3[key], W = el.width, H = el.height, R = lod.length, Cl = rpm.length;
  if (W < 10 || H < 10) return;
  ctx.fillStyle = '#111114'; ctx.fillRect(0, 0, W, H);
  var xPos = axisPositions(rpm, Cl), yPos = axisPositions(lod, R);
  var range = getRange(units, data);
  var zMinObs = 1e9, zX = -1e9;
  for (var i = 0; i < R; i++) for (var j = 0; j < Cl; j++) { if (data[i][j] < zMinObs) zMinObs = data[i][j]; if (data[i][j] > zX) zX = data[i][j]; }
  var zN = Math.min(range.mn, zMinObs);
  if (zX === zN) zX = zN + 1;
  var pad = 40, sX = Math.min((W - pad) / (Cl - 1), 30) * CAM.zoom, sY = Math.min((H - pad) / (R - 1), 24) * CAM.zoom;
  var zRange = zX - zN; if (zRange < 1) zRange = 1;
  var sf = SC[DATA.cur] || 0.4; if (mode === 'delta') sf = SC['delta'] || 0.08;
  var sZ = (H * sf * DATA.zoomAlt * CAM.zoom) / zRange;
  var cy = Math.cos(c.ang), sy = Math.sin(c.ang);
  var cp = Math.cos(c.tilt), sp = Math.sin(c.tilt);
  var cr = Math.cos(c.roll), sr = Math.sin(c.roll);
  function project(j, i, z) {
    var mx = (INV.X ? -1 : 1) * (xPos[j] - (Cl - 1) / 2) * sX;
    var my = (INV.Y ? -1 : 1) * (z - zN) * sZ;
    var mz = (INV.Z ? -1 : 1) * ((R - 1) / 2 - yPos[i]) * sY;
    var x1 = mx * cy + mz * sy, y1 = my, z1 = -mx * sy + mz * cy;
    var x2 = x1, y2 = y1 * cp - z1 * sp, z2 = y1 * sp + z1 * cp;
    var fx = x2 * cr - y2 * sr, fy = x2 * sr + y2 * cr;
    return [fx, fy, z2];
  }
  var mnX = 1e9, mxX = -1e9, mnY = 1e9, mxY = -1e9;
  for (var i2 = 0; i2 < R; i2++) for (var j2 = 0; j2 < Cl; j2++) {
    var p = project(j2, i2, data[i2][j2]);
    if (p[0] < mnX) mnX = p[0]; if (p[0] > mxX) mxX = p[0];
    if (-p[1] < mnY) mnY = -p[1]; if (-p[1] > mxY) mxY = -p[1];
  }
  var ox = W * 0.5 - (mnX + mxX) * 0.5, oy = H * 0.5 - (mnY + mxY) * 0.5;
  function pr(j, i, z) { var p = project(j, i, z); return [ox + p[0], oy - p[1], p[2]]; }
  function dcol(v) {
    var ma = Math.max(Math.abs(zN), Math.abs(zX)); if (ma === 0) ma = 1; var t = v / ma, r, g, b;
    if (t >= 0) { r = Math.round(60 + 195 * t); g = Math.round(30 + 30 * t); b = 30; }
    else { var s = -t; r = 30; g = Math.round(40 + 100 * s); b = Math.round(60 + 195 * s); }
    return 'rgba(' + r + ',' + g + ',' + b + ',0.9)';
  }
  var faces = [];
  for (var i3 = 0; i3 < R - 1; i3++) for (var j3 = 0; j3 < Cl - 1; j3++) {
    var p0 = pr(j3, i3, data[i3][j3]), p1 = pr(j3 + 1, i3, data[i3][j3 + 1]), p2 = pr(j3 + 1, i3 + 1, data[i3 + 1][j3 + 1]), p3 = pr(j3, i3 + 1, data[i3 + 1][j3]);
    var av = (data[i3][j3] + data[i3][j3 + 1] + data[i3 + 1][j3 + 1] + data[i3 + 1][j3]) / 4;
    var dp0 = pr(j3, i3, zN), dp1 = pr(j3 + 1, i3, zN), dp2 = pr(j3 + 1, i3 + 1, zN), dp3 = pr(j3, i3 + 1, zN);
    var dz = (dp0[2] + dp1[2] + dp2[2] + dp3[2]) / 4;
    var ux = p1[0] - p0[0], uy = p1[1] - p0[1], uz = p1[2] - p0[2];
    var vx = p3[0] - p0[0], vy = p3[1] - p0[1], vz = p3[2] - p0[2];
    var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    var nl = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
    var lam = Math.abs((nx * -0.35 + ny * -0.55 + nz * 0.76) / nl);
    faces.push({ p: [p0, p1, p2, p3], z: dz, v: av, sh: 0.55 + 0.45 * lam, i: i3, j: j3 });
  }
  faces.sort(function(a, b) { return a.z - b.z; });
  var stagd = (cid === 'c3m') ? (STAGE[DATA.cur] || {}) : {};
  for (var f = 0; f < faces.length; f++) {
    var fc = faces[f];
    ctx.beginPath(); ctx.moveTo(fc.p[0][0], fc.p[0][1]);
    for (var k = 1; k < 4; k++) ctx.lineTo(fc.p[k][0], fc.p[k][1]);
    ctx.closePath();
    var nm = (fc.v - zN) / (zX - zN);
    ctx.fillStyle = shadeRGBA(mode === 'delta' ? dcol(fc.v) : heat3D(nm), fc.sh);
    ctx.fill();
    var isStagedFace = stagd[fc.i + ',' + fc.j] || stagd[fc.i + ',' + (fc.j + 1)] || stagd[(fc.i + 1) + ',' + fc.j] || stagd[(fc.i + 1) + ',' + (fc.j + 1)];
    if (isStagedFace) { ctx.strokeStyle = 'rgba(245,166,35,0.9)'; ctx.lineWidth = 1.5; }
    else { ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5; }
    ctx.stroke();
  }
  var o3 = pr(0, 0, zN), x3 = pr(Cl - 1, 0, zN), y3 = pr(0, 0, zX), z3 = pr(0, R - 1, zN);
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#ff3333'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(x3[0], x3[1]); ctx.stroke();
  ctx.strokeStyle = '#3399ff'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(y3[0], y3[1]); ctx.stroke();
  ctx.strokeStyle = '#33ff33'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(z3[0], z3[1]); ctx.stroke();
  ctx.font = '8px monospace';
  ctx.fillStyle = '#ff3333'; ctx.fillText('RPM', x3[0] + 3, x3[1] + 3);
  ctx.fillStyle = '#3399ff'; ctx.fillText('VAL', y3[0] + 3, y3[1] + 3);
  ctx.fillStyle = '#33ff33'; ctx.fillText('TPS', z3[0] + 3, z3[1] - 5);
  ctx.font = '7px monospace'; ctx.fillStyle = '#666';
  for (var jj = 0; jj < Cl; jj += 2) { var pp = pr(jj, R - 1, zN); ctx.fillText(rpm[jj], pp[0] - 8, pp[1] + 10); }
  for (var ii = 0; ii < R; ii += 2) { var pp2 = pr(0, ii, zN); ctx.fillText(lod[ii], pp2[0] - 26, pp2[1] + 3); }
  var leg = document.getElementById(legId);
  if (mode === 'delta') {
    leg.innerHTML = '<span>-</span><div class="bar" style="background:linear-gradient(to right,rgba(30,60,255,.9),#444,rgba(255,60,60,.9))"></div><span>+</span><span style="margin-left:4px">' + zN.toFixed(1) + '/+' + zX.toFixed(1) + '</span>';
  } else {
    leg.innerHTML = '<span>' + zN.toFixed(0) + '</span><div class="bar" style="background:linear-gradient(to right,rgba(15,10,80,.9),rgba(15,70,220,.9),rgba(35,200,255,.9),rgba(155,255,100,.9),rgba(255,195,30,.9),rgba(255,50,20,.9))"></div><span>' + zX.toFixed(0) + '</span>';
  }
}

function drawDelta(cid, legId) {
  var el = document.getElementById(cid); if (!el) return;
  var ctx = el.getContext('2d'), key = 'delta';
  var c = C3[key], W = el.width, H = el.height, R = lod.length, Cl = rpm.length;
  if (W < 10 || H < 10) return;
  ctx.fillStyle = '#111114'; ctx.fillRect(0, 0, W, H);
  var dN = 1e9, dX = -1e9;
  for (var i = 0; i < R; i++) for (var j = 0; j < Cl; j++) { var d = mD[i][j] - bD[i][j]; if (d < dN) dN = d; if (d > dX) dX = d; }
  if (dX === dN) dX = dN + 1;
  var bN = 1e9, bX = -1e9, mN = 1e9, mXX = -1e9;
  for (var i2 = 0; i2 < R; i2++) for (var j2 = 0; j2 < Cl; j2++) {
    if (bD[i2][j2] < bN) bN = bD[i2][j2]; if (bD[i2][j2] > bX) bX = bD[i2][j2];
    if (mD[i2][j2] < mN) mN = mD[i2][j2]; if (mD[i2][j2] > mXX) mXX = mD[i2][j2];
  }
  if (bX === bN) bX = bN + 1; if (mXX === mN) mXX = mN + 1;
  var pad = 40, sX = Math.min((W - pad) / (Cl - 1), 30) * CAM.zoom, sY = Math.min((H - pad) / (R - 1), 24) * CAM.zoom;
  var xPos = axisPositions(rpm, Cl), yPos = axisPositions(lod, R);
  var zRange = mXX - mN; if (zRange < 1) zRange = 1;
  var sZ = (H * (SC[DATA.cur] || 0.4) * DATA.zoomAlt * CAM.zoom) / zRange;
  var cy = Math.cos(c.ang), sy = Math.sin(c.ang);
  var cp = Math.cos(c.tilt), sp = Math.sin(c.tilt);
  var cr = Math.cos(c.roll), sr = Math.sin(c.roll);
  function proj(j, i, z) {
    var mx = (INV.X ? -1 : 1) * (xPos[j] - (Cl - 1) / 2) * sX;
    var my = (INV.Y ? -1 : 1) * (z - mN) * sZ;
    var mz = (INV.Z ? -1 : 1) * ((R - 1) / 2 - yPos[i]) * sY;
    var x1 = mx * cy + mz * sy, y1 = my, z1 = -mx * sy + mz * cy;
    var x2 = x1, y2 = y1 * cp - z1 * sp, z2 = y1 * sp + z1 * cp;
    var fx = x2 * cr - y2 * sr, fy = x2 * sr + y2 * cr;
    return [fx, fy, z2];
  }
  var mnX = 1e9, mxX = -1e9, mnY = 1e9, mxY = -1e9;
  for (var i3 = 0; i3 < R; i3++) for (var j3 = 0; j3 < Cl; j3++) {
    var p = proj(j3, i3, mD[i3][j3]);
    if (p[0] < mnX) mnX = p[0]; if (p[0] > mxX) mxX = p[0];
    if (-p[1] < mnY) mnY = -p[1]; if (-p[1] > mxY) mxY = -p[1];
  }
  var ox = W * 0.5 - (mnX + mxX) * 0.5, oy = H * 0.5 - (mnY + mxY) * 0.5;
  function pr(j, i, z) { var p = proj(j, i, z); return [ox + p[0], oy - p[1], p[2]]; }
  function dcol(v) {
    var ma = Math.max(Math.abs(dN), Math.abs(dX)); if (ma === 0) ma = 1; var t = v / ma, r, g, b;
    if (t >= 0) { r = Math.round(60 + 195 * t); g = Math.round(30 + 30 * t); b = 30; }
    else { var s = -t; r = 30; g = Math.round(40 + 100 * s); b = Math.round(60 + 195 * s); }
    return 'rgba(' + r + ',' + g + ',' + b + ',0.9)';
  }
  function sortedFaces(dataZ) {
    var faces = [];
    for (var i4 = 0; i4 < R - 1; i4++) for (var j4 = 0; j4 < Cl - 1; j4++) {
      var p0 = pr(j4, i4, dataZ[i4][j4]), p1 = pr(j4 + 1, i4, dataZ[i4][j4 + 1]), p2 = pr(j4 + 1, i4 + 1, dataZ[i4 + 1][j4 + 1]), p3 = pr(j4, i4 + 1, dataZ[i4 + 1][j4]);
      var av = (dataZ[i4][j4] + dataZ[i4][j4 + 1] + dataZ[i4 + 1][j4 + 1] + dataZ[i4 + 1][j4]) / 4;
      var dp0 = pr(j4, i4, mN), dp1 = pr(j4 + 1, i4, mN), dp2 = pr(j4 + 1, i4 + 1, mN), dp3 = pr(j4, i4 + 1, mN);
      var dz = (dp0[2] + dp1[2] + dp2[2] + dp3[2]) / 4;
      faces.push({ p: [p0, p1, p2, p3], z: dz, v: av, i: i4, j: j4 });
    }
    faces.sort(function(a, b) { return a.z - b.z; });
    return faces;
  }
  if (DM === 'delta') {
    var dd = []; for (var i5 = 0; i5 < R; i5++) { dd[i5] = []; for (var j5 = 0; j5 < Cl; j5++) dd[i5][j5] = mD[i5][j5] - bD[i5][j5] + (mN + mXX) * 0.5; }
    var faces = sortedFaces(dd);
    for (var f = 0; f < faces.length; f++) {
      var fc = faces[f];
      ctx.beginPath(); ctx.moveTo(fc.p[0][0], fc.p[0][1]);
      for (var k = 1; k < 4; k++) ctx.lineTo(fc.p[k][0], fc.p[k][1]);
      ctx.closePath();
      var dv = mD[fc.i][fc.j] - bD[fc.i][fc.j];
      ctx.fillStyle = dcol(dv); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5; ctx.stroke();
    }
  } else if (DM === 'overlay') {
    var bf = sortedFaces(bD);
    for (var f2 = 0; f2 < bf.length; f2++) {
      var fc2 = bf[f2];
      ctx.beginPath(); ctx.moveTo(fc2.p[0][0], fc2.p[0][1]);
      for (var k2 = 1; k2 < 4; k2++) ctx.lineTo(fc2.p[k2][0], fc2.p[k2][1]);
      ctx.closePath();
      var nm = (fc2.v - bN) / (bX - bN);
      ctx.fillStyle = heat3D(nm); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5; ctx.stroke();
    }
    var mf = sortedFaces(mD);
    for (var f3 = 0; f3 < mf.length; f3++) {
      var fc3 = mf[f3];
      ctx.beginPath(); ctx.moveTo(fc3.p[0][0], fc3.p[0][1]);
      for (var k3 = 1; k3 < 4; k3++) ctx.lineTo(fc3.p[k3][0], fc3.p[k3][1]);
      ctx.closePath();
      ctx.fillStyle = 'rgba(40,80,220,' + DATA.opa + ')'; ctx.fill();
      ctx.strokeStyle = 'rgba(60,120,255,' + (DATA.opa + 0.2) + ')'; ctx.lineWidth = 1.5; ctx.stroke();
    }
  } else if (DM === 'spikes') {
    var bf2 = sortedFaces(bD);
    for (var f4 = 0; f4 < bf2.length; f4++) {
      var fc4 = bf2[f4];
      ctx.beginPath(); ctx.moveTo(fc4.p[0][0], fc4.p[0][1]);
      for (var k4 = 1; k4 < 4; k4++) ctx.lineTo(fc4.p[k4][0], fc4.p[k4][1]);
      ctx.closePath();
      var nm2 = (fc4.v - bN) / (bX - bN);
      ctx.fillStyle = heat3D(nm2); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5; ctx.stroke();
    }
    for (var i6 = 0; i6 < R; i6++) for (var j6 = 0; j6 < Cl; j6++) {
      var d2 = mD[i6][j6] - bD[i6][j6]; if (Math.abs(d2) < 0.5) continue;
      var pBase = pr(j6, i6, bD[i6][j6]), pTop = pr(j6, i6, mD[i6][j6]);
      ctx.strokeStyle = d2 > 0 ? 'rgba(255,60,60,0.85)' : 'rgba(60,130,255,0.85)';
      ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(pBase[0], pBase[1]); ctx.lineTo(pTop[0], pTop[1]); ctx.stroke();
    }
  } else if (DM === 'wire') {
    var mf2 = sortedFaces(mD);
    for (var f5 = 0; f5 < mf2.length; f5++) {
      var fc5 = mf2[f5];
      ctx.beginPath(); ctx.moveTo(fc5.p[0][0], fc5.p[0][1]);
      for (var k5 = 1; k5 < 4; k5++) ctx.lineTo(fc5.p[k5][0], fc5.p[k5][1]);
      ctx.closePath();
      ctx.strokeStyle = 'rgba(120,170,255,0.5)'; ctx.lineWidth = 0.7; ctx.stroke();
    }
  }
  var leg = document.getElementById(legId);
  leg.innerHTML = '<span>-</span><div class="bar" style="background:linear-gradient(to right,rgba(30,60,255,.9),#444,rgba(255,60,60,.9))"></div><span>+</span><span style="margin-left:4px">' + dN.toFixed(1) + '/+' + dX.toFixed(1) + '</span>';
}

function drawAll() {
  try {
    drawSurf('c3b', bD, 'heat', 'lb', DATA.units);
    drawDelta('c3d', 'ld');
    drawSurf('c3m', mD, 'heat', 'lm', DATA.units);
  } catch (e) { console.error(e); }
}

['c3b', 'c3d', 'c3m'].forEach(function(cid) {
  var el = document.getElementById(cid); if (!el) return;
  var key = cid === 'c3b' ? 'base' : cid === 'c3d' ? 'delta' : 'mod';
  function rs() { var r = el.getBoundingClientRect(); el.width = r.width || 300; el.height = r.height || 260; drawAll(); }
  el.addEventListener('mousedown', function(e) { C3[key].drag = true; C3[key].lx = e.clientX; C3[key].ly = e.clientY; });
  el.addEventListener('touchstart', function(e) { C3[key].drag = true; C3[key].lx = e.touches[0].clientX; C3[key].ly = e.touches[0].clientY; }, { passive: true });
  el.addEventListener('wheel', function(e) { e.preventDefault(); CAM.zoom = Math.min(2.5, Math.max(0.3, Math.round((CAM.zoom + (e.deltaY < 0 ? 0.05 : -0.05)) * 100) / 100)); drawAll(); }, { passive: false });
  rs();
});
window.addEventListener('resize', function() {
  ['c3b', 'c3d', 'c3m'].forEach(function(cid) {
    var el = document.getElementById(cid); if (!el) return;
    el.width = el.parentElement.clientWidth || 300;
    var r = el.getBoundingClientRect(); el.height = r.height || 260;
  });
  drawAll();
});
document.addEventListener('mousemove', function(e) {
  for (var k in C3) {
    var c = C3[k];
    if (c.drag) {
      var da = (e.clientX - c.lx) * 0.005, dt = (e.clientY - c.ly) * 0.005;
      for (var kk in C3) { C3[kk].ang += da; C3[kk].tilt += dt; }
      c.lx = e.clientX; c.ly = e.clientY;
      drawAll();
      break;
    }
  }
});
document.addEventListener('mouseup', function() { for (var k in C3) C3[k].drag = false; });
document.addEventListener('touchmove', function(e) {
  for (var k in C3) {
    var c = C3[k];
    if (c.drag) {
      var da = (e.touches[0].clientX - c.lx) * 0.005, dt = (e.touches[0].clientY - c.ly) * 0.005;
      for (var kk in C3) { C3[kk].ang += da; C3[kk].tilt += dt; }
      c.lx = e.touches[0].clientX; c.ly = e.touches[0].clientY;
      drawAll();
      e.preventDefault();
      break;
    }
  }
}, { passive: false });
document.addEventListener('touchend', function() { for (var k in C3) C3[k].drag = false; });

renderTables();
drawAll();
})();
</script>
</body>
</html>`;
}
