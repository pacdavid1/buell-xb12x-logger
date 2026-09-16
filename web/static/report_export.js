// DEV NOTE: All code, comments, and variable names must be in English.
// Standalone Map Editor report export.
//
// Bundles the current session's maps (base values with any staged/unburned
// edits merged in) plus a self-contained, dependency-free copy of the 3D
// rotate/zoom renderer from map-editor.html into a single downloadable
// .html file. The result has zero external references (no fetch, no CDN,
// no /static/*.js) -- it opens and rotates the same way whether the Pi is
// reachable or not. Only the DATA is frozen at export time; the rendering
// code is a trimmed, read-only fork of drawSurf3D/drawBar1D/buildTable from
// map-editor.html -- keep the two in sync if that renderer changes shape.

function _reportBuildPayload() {
  var mapsSnapshot = {};
  Object.keys(MAPS_DATA).forEach(function(key) {
    var m = MAPS_DATA[key];
    var stagedCells = Object.keys(STAGE[key] || {});
    var data = m.data.map(function(row, ri) {
      return row.map(function(v, ci) {
        var s = (STAGE[key] || {})[ri + ',' + ci];
        return s !== undefined ? s : v;
      });
    });
    mapsSnapshot[key] = {
      label: m.label, units: m.units, rows: m.rows, cols: m.cols,
      xaxis: m.xaxis, yaxis: m.yaxis, data: data, staged: stagedCells
    };
  });
  var verEl = document.querySelector('.ver');
  return {
    session: CUR_SESSION,
    loggerVersion: verEl ? verEl.textContent : '',
    generated: new Date().toISOString(),
    maps: mapsSnapshot,
    axes: AXES_DATA,
    scale: SC
  };
}

function exportMapReport() {
  if (!CUR_SESSION || !Object.keys(MAPS_DATA).length) { toast('Load a session first', true); return; }
  var payload = _reportBuildPayload();
  var html = _reportBuildHtml(payload);
  var blob = new Blob([html], { type: 'text/html' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'map_report_' + payload.session + '_' + payload.generated.slice(0, 10) + '.html';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  toast('Report downloaded (' + Object.keys(payload.maps).length + ' maps)');
}

function _reportBuildHtml(payload) {
  // Neutralize "</script>" inside the embedded JSON so it can't close the
  // report's own <script> tag early.
  var dataJson = JSON.stringify(payload).replace(/</g, '\\u003c');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Map Report -- ${payload.session}</title>
<style>
:root{--bg:#0a0a0b;--p:#111114;--bd:#1e1e24;--ac:#e8420a;--a2:#f5a623;--bl:#3d9eff;--dm:#555;--tx:#c8c8cc;--staged:#a07800;--staged-bg:rgba(160,120,0,.18);--mn:'JetBrains Mono',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:sans-serif;font-size:13px}
.rpt-hd{background:var(--p);border-bottom:2px solid var(--ac);padding:12px 20px}
.rpt-title{font-family:var(--mn);font-size:16px;font-weight:700;color:var(--ac);letter-spacing:.12em;text-transform:uppercase}
.rpt-meta{font-family:var(--mn);font-size:11px;color:var(--dm);margin-top:4px;letter-spacing:.04em}
.rpt-meta b{color:var(--a2)}
.hint{font-family:var(--mn);font-size:10px;color:var(--dm);padding:6px 20px;letter-spacing:.04em}
.main{padding:16px 20px;display:flex;flex-direction:column;gap:24px}
.map-block{background:var(--p);border:1px solid var(--bd);border-radius:4px;overflow:hidden}
.map-block.rear{border-color:#1a2535}
.map-block.rear .map-name{color:var(--bl)}
.map-header{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02);flex-wrap:wrap}
.map-name{font-family:var(--mn);font-size:12px;font-weight:700;color:var(--ac);letter-spacing:.1em;text-transform:uppercase}
.map-axes{opacity:.5}
.map-meta{font-family:var(--mn);font-size:10px;color:var(--dm);letter-spacing:.06em;margin-left:auto}
.staged-badge{font-family:var(--mn);font-size:10px;color:var(--staged);background:var(--staged-bg);border:1px solid rgba(160,120,0,.35);padding:1px 5px;border-radius:2px}
.map-body{display:flex;min-height:200px;flex-wrap:wrap}
.tbl-wrap{overflow:auto;flex:0 0 auto;border-right:1px solid var(--bd);padding:4px}
table.em{border-collapse:collapse;font-family:var(--mn);white-space:nowrap;font-size:11px}
table.em th.axis-label{font-size:9px;color:var(--dm);padding:1px 3px;text-align:center;background:rgba(255,255,255,.02);border:1px solid var(--bd);min-width:22px}
table.em th.row-label{font-size:9px;color:var(--dm);padding:0 3px;text-align:right;min-width:20px;border:1px solid var(--bd);background:rgba(255,255,255,.02)}
table.em td{color:var(--tx);padding:2px 4px;text-align:center;border:1px solid var(--bd);min-width:22px}
table.em td.staged{background:var(--staged-bg)!important;color:var(--staged)}
.c3-wrap{flex:1;min-width:280px;display:flex;flex-direction:column;background:var(--p);min-height:220px}
.c3-label{font-family:var(--mn);font-size:10px;color:var(--a2);padding:3px 6px;border-bottom:1px solid var(--bd);letter-spacing:.08em;text-transform:uppercase}
.c3-wrap canvas{display:block;flex:1;touch-action:none;width:100%;min-height:200px;cursor:grab}
#cellTip{position:fixed;pointer-events:none;z-index:50;display:none;background:var(--p);border:1px solid var(--bd);padding:3px 8px;border-radius:2px;font-family:var(--mn);font-size:11px;color:var(--tx);line-height:1.7;white-space:nowrap}
</style>
</head>
<body>
<div class="rpt-hd">
  <div class="rpt-title">&#9670; Map Report</div>
  <div class="rpt-meta">Session <b>${payload.session}</b> &middot; ${payload.loggerVersion} &middot; generated ${payload.generated.slice(0, 19).replace('T', ' ')} UTC</div>
</div>
<div class="hint">Static snapshot &mdash; drag a 3D view to rotate, scroll to zoom. No live data, no server connection needed.</div>
<div class="main" id="main"></div>
<div id="cellTip"></div>
<script>
(function() {
'use strict';
var DATA = ${dataJson};
var MAPS_DATA = DATA.maps, AXES_DATA = DATA.axes, SC = DATA.scale || {};
var CAMS = {};
var CANVAS_FS = 11;
function cfont(mult) { return (CANVAS_FS * (mult || 1)).toFixed(1) + "px 'JetBrains Mono', monospace"; }

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
function cellBg(val, range) {
  var t = Math.max(0, Math.min(1, (val - range.mn) / (range.mx - range.mn)));
  var stops = [[10, 25, 60], [10, 80, 120], [30, 130, 90], [160, 130, 20], [200, 50, 20], [180, 10, 10]];
  var seg = t * (stops.length - 1), i = Math.min(Math.floor(seg), stops.length - 2), f = seg - i;
  var r = Math.round(stops[i][0] + f * (stops[i + 1][0] - stops[i][0]));
  var g = Math.round(stops[i][1] + f * (stops[i + 1][1] - stops[i][1]));
  var b = Math.round(stops[i][2] + f * (stops[i + 1][2] - stops[i][2]));
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function setupCanvas(cv) {
  var dpr = window.devicePixelRatio || 1;
  var r = cv.getBoundingClientRect();
  var w = Math.max(10, r.width), h = Math.max(10, r.height);
  var tw = Math.round(w * dpr), th = Math.round(h * dpr);
  if (cv.width !== tw || cv.height !== th) { cv.width = tw; cv.height = th; }
  var ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  cv._lw = w; cv._lh = h;
  return ctx;
}

function heat(t) {
  var r, g, b;
  if (t < 0.2) { var s = t / 0.2; r = 15; g = Math.round(10 + 60 * s); b = Math.round(80 + 140 * s); }
  else if (t < 0.4) { var s = (t - 0.2) / 0.2; r = Math.round(15 + 20 * s); g = Math.round(70 + 130 * s); b = Math.round(220 + 35 * s); }
  else if (t < 0.6) { var s = (t - 0.4) / 0.2; r = Math.round(35 + 120 * s); g = Math.round(200 + 55 * s); b = Math.round(255 - 155 * s); }
  else if (t < 0.8) { var s = (t - 0.6) / 0.2; r = Math.round(155 + 100 * s); g = Math.round(255 - 60 * s); b = Math.round(100 - 70 * s); }
  else { var s = (t - 0.8) / 0.2; r = 255; g = Math.round(195 - 145 * s); b = Math.round(30 - 10 * s); }
  return 'rgba(' + r + ',' + g + ',' + b + ',0.9)';
}
function shadeRGBA(col, f) {
  var m = col.match(/rgba?\\(([\\d.]+),([\\d.]+),([\\d.]+)/);
  if (!m) return col;
  return 'rgba(' + Math.round(m[1] * f) + ',' + Math.round(m[2] * f) + ',' + Math.round(m[3] * f) + ',0.9)';
}

function wire3D(cv, key) {
  cv.addEventListener('mousedown', function(e) { CAMS[key].drag = true; CAMS[key].lx = e.clientX; CAMS[key].ly = e.clientY; });
  cv.addEventListener('wheel', function(e) {
    e.preventDefault();
    CAMS[key].zoom = Math.min(2.5, Math.max(0.3, Math.round(((CAMS[key].zoom || 1) + (e.deltaY < 0 ? 0.07 : -0.07)) * 100) / 100));
    drawSurf3D(key);
  }, { passive: false });
  cv.addEventListener('touchstart', function(e) { CAMS[key].drag = true; CAMS[key].lx = e.touches[0].clientX; CAMS[key].ly = e.touches[0].clientY; }, { passive: true });
}
document.addEventListener('mousemove', function(e) {
  Object.keys(CAMS).forEach(function(key) {
    var c = CAMS[key]; if (!c.drag) return;
    c.ang += (e.clientX - c.lx) * 0.005; c.tilt += (e.clientY - c.ly) * 0.005;
    c.lx = e.clientX; c.ly = e.clientY;
    drawSurf3D(key);
  });
});
document.addEventListener('mouseup', function() { Object.keys(CAMS).forEach(function(k) { CAMS[k].drag = false; }); });
document.addEventListener('touchend', function() { Object.keys(CAMS).forEach(function(k) { CAMS[k].drag = false; }); });
document.addEventListener('touchmove', function(e) {
  Object.keys(CAMS).forEach(function(key) {
    var c = CAMS[key]; if (!c.drag) return;
    c.ang += (e.touches[0].clientX - c.lx) * 0.005; c.tilt += (e.touches[0].clientY - c.ly) * 0.005;
    c.lx = e.touches[0].clientX; c.ly = e.touches[0].clientY;
    drawSurf3D(key);
    e.preventDefault();
  });
}, { passive: false });

function drawSurf3D(key) {
  var cv = document.getElementById('c3-' + key);
  if (!cv) return;
  var m = MAPS_DATA[key];
  if (!m) return;
  var ctx = setupCanvas(cv);
  var W = cv._lw, H = cv._lh;
  if (W < 10 || H < 10) return;
  var data = m.data;
  var xAxis = AXES_DATA[m.xaxis] || { data: [] };
  var yAxis = AXES_DATA[m.yaxis] || { data: [] };
  var rpm = xAxis.data || [], lod = yAxis.data || [];
  var R = m.rows, Cl = m.cols;
  var staged = {};
  (m.staged || []).forEach(function(stk) { staged[stk] = true; });

  var bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, '#0e0e13'); bgGrad.addColorStop(1, '#060608');
  ctx.fillStyle = bgGrad; ctx.fillRect(0, 0, W, H);

  var zN = 1e9, zX = -1e9;
  for (var i = 0; i < R; i++) for (var j = 0; j < Cl; j++) { var v = data[i][j]; if (v < zN) zN = v; if (v > zX) zX = v; }
  if (zX === zN) zX = zN + 1;
  var zRange = zX - zN; if (zRange < 1) zRange = 1;

  var c = CAMS[key];
  var zoom = c.zoom || 1;
  var sf = SC[key] || 0.4;
  var pad = 40;
  var sX = Math.min((W - pad) / Math.max(Cl - 1, 1), 30) * zoom;
  var sY = Math.min((H - pad) / Math.max(R - 1, 1), 24) * zoom;
  var sZ = (H * sf * zoom) / zRange;

  var cy = Math.cos(c.ang), sy = Math.sin(c.ang);
  var cp = Math.cos(c.tilt), sp = Math.sin(c.tilt);

  function project(j, i, z) {
    var mx = (j - (Cl - 1) / 2) * sX;
    var my = (z - zN) * sZ;
    var mz = ((R - 1) - i - (R - 1) / 2) * sY;
    var x1 = mx * cy + mz * sy, y1 = my, z1 = -mx * sy + mz * cy;
    var x2 = x1, y2 = y1 * cp - z1 * sp, z2 = y1 * sp + z1 * cp;
    return [x2, y2, z2];
  }
  var mnX = 1e9, mxX = -1e9, mnY = 1e9, mxY = -1e9;
  for (var i2 = 0; i2 < R; i2++) for (var j2 = 0; j2 < Cl; j2++) {
    var p = project(j2, i2, data[i2][j2]);
    if (p[0] < mnX) mnX = p[0]; if (p[0] > mxX) mxX = p[0];
    if (-p[1] < mnY) mnY = -p[1]; if (-p[1] > mxY) mxY = -p[1];
  }
  var ox = W * 0.5 - (mnX + mxX) * 0.5, oy = H * 0.5 - (mnY + mxY) * 0.5;
  function pr(j, i, z) { var p = project(j, i, z); return [ox + p[0], oy - p[1], p[2]]; }

  ctx.strokeStyle = 'rgba(120,150,200,0.07)'; ctx.lineWidth = 0.5;
  for (var j3 = 0; j3 < Cl; j3++) { var a = pr(j3, 0, zN), b = pr(j3, R - 1, zN); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
  for (var i3 = 0; i3 < R; i3++) { var a2 = pr(0, i3, zN), b2 = pr(Cl - 1, i3, zN); ctx.beginPath(); ctx.moveTo(a2[0], a2[1]); ctx.lineTo(b2[0], b2[1]); ctx.stroke(); }

  var faces = [];
  for (var i4 = 0; i4 < R - 1; i4++) {
    for (var j4 = 0; j4 < Cl - 1; j4++) {
      var v00 = data[i4][j4], v01 = data[i4][j4 + 1], v10 = data[i4 + 1][j4], v11 = data[i4 + 1][j4 + 1];
      var p0 = pr(j4, i4, v00), p1 = pr(j4 + 1, i4, v01), p2 = pr(j4 + 1, i4 + 1, v11), p3 = pr(j4, i4 + 1, v10);
      var av = Math.max(v00, v01, v11, v10);
      var dp0 = pr(j4, i4, zN), dp1 = pr(j4 + 1, i4, zN), dp2 = pr(j4 + 1, i4 + 1, zN), dp3 = pr(j4, i4 + 1, zN);
      var dz = (dp0[2] + dp1[2] + dp2[2] + dp3[2]) / 4;
      var ux = p1[0] - p0[0], uy = p1[1] - p0[1], uz = p1[2] - p0[2];
      var vx = p3[0] - p0[0], vy = p3[1] - p0[1], vz = p3[2] - p0[2];
      var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      var nl = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      var lam = Math.abs((nx * -0.35 + ny * -0.55 + nz * 0.76) / nl);
      var isStaged = staged[i4 + ',' + j4] || staged[i4 + ',' + (j4 + 1)] || staged[(i4 + 1) + ',' + j4] || staged[(i4 + 1) + ',' + (j4 + 1)];
      faces.push({ p: [p0, p1, p2, p3], z: dz, v: av, sh: 0.55 + 0.45 * lam, staged: isStaged });
    }
  }
  faces.sort(function(a, b) { return a.z - b.z; });
  for (var f = 0; f < faces.length; f++) {
    var fc = faces[f];
    ctx.beginPath();
    ctx.moveTo(fc.p[0][0], fc.p[0][1]);
    for (var k = 1; k < 4; k++) ctx.lineTo(fc.p[k][0], fc.p[k][1]);
    ctx.closePath();
    var nm = (fc.v - zN) / (zX - zN);
    ctx.fillStyle = shadeRGBA(heat(nm), fc.sh);
    ctx.fill();
    if (fc.staged) { ctx.strokeStyle = 'rgba(245,166,35,0.9)'; ctx.lineWidth = 1.5; }
    else { ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5; }
    ctx.stroke();
  }

  var o3 = pr(0, 0, zN), x3 = pr(Cl - 1, 0, zN), y3 = pr(0, 0, zX), z3 = pr(0, R - 1, zN);
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#ff3333'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(x3[0], x3[1]); ctx.stroke();
  ctx.strokeStyle = '#3399ff'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(y3[0], y3[1]); ctx.stroke();
  ctx.strokeStyle = '#33ff33'; ctx.beginPath(); ctx.moveTo(o3[0], o3[1]); ctx.lineTo(z3[0], z3[1]); ctx.stroke();
  ctx.font = cfont(1); ctx.lineWidth = 1;

  var xAngle = Math.atan2(x3[1] - o3[1], x3[0] - o3[0]);
  ctx.save(); ctx.translate(x3[0] + Math.cos(xAngle) * 14, x3[1] + Math.sin(xAngle) * 14); ctx.rotate(xAngle);
  ctx.fillStyle = '#ff5555'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(xAxis.units || 'RPM', 0, 0); ctx.restore();

  var yAngle = Math.atan2(y3[1] - o3[1], y3[0] - o3[0]);
  ctx.save(); ctx.translate(y3[0] + Math.cos(yAngle) * 14, y3[1] + Math.sin(yAngle) * 14); ctx.rotate(yAngle);
  ctx.fillStyle = '#5599ff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('VAL', 0, 0); ctx.restore();

  ctx.fillStyle = '#55cc55'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.fillText(yAxis.units || 'TPS', z3[0] + 4, z3[1] - 6);
  ctx.font = cfont(0.82); ctx.fillStyle = '#8a8a90';
  var rpmS = rpm.slice().sort(function(a, b) { return (a || 0) - (b || 0); });
  var lodS = lod.slice().sort(function(a, b) { return (a || 0) - (b || 0); });
  for (var jj = 0; jj < Cl; jj += 2) { var pp = pr(jj, R - 1, zN); ctx.fillText(rpmS[jj] !== undefined ? rpmS[jj] : jj, pp[0] - 8, pp[1] + 11); }
  for (var ii = 0; ii < R; ii += 2) { var pp2 = pr(0, ii, zN); ctx.fillText(lodS[ii] !== undefined ? lodS[ii] : ii, pp2[0] - 26, pp2[1] + 3); }
}

function drawBar1D(key) {
  var cv = document.getElementById('c3-' + key);
  if (!cv) return;
  var m = MAPS_DATA[key];
  var ctx = setupCanvas(cv);
  var W = cv._lw, H = cv._lh;
  var bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, '#0e0e13'); bgGrad.addColorStop(1, '#060608');
  ctx.fillStyle = bgGrad; ctx.fillRect(0, 0, W, H);
  var xAxis = AXES_DATA[m.xaxis] || { data: [] };
  var yAxis = m.yaxis ? (AXES_DATA[m.yaxis] || { data: [] }) : { data: [] };
  var staged = {}; (m.staged || []).forEach(function(stk) { staged[stk] = true; });
  var items = [];
  if (m.rows === 1) {
    for (var ci = 0; ci < m.cols; ci++) { var stk = '0,' + ci; items.push({ label: xAxis.data[ci] !== undefined ? String(xAxis.data[ci]) : String(ci), val: m.data[0][ci], stk: stk }); }
  } else {
    for (var ri = 0; ri < m.rows; ri++) { var stk2 = ri + ',0'; items.push({ label: yAxis.data[ri] !== undefined ? String(yAxis.data[ri]) : String(ri), val: m.data[ri][0], stk: stk2 }); }
  }
  var n = items.length; if (!n) return;
  var mn = Math.min.apply(null, items.map(function(x) { return x.val; }));
  var mx = Math.max.apply(null, items.map(function(x) { return x.val; }));
  if (mx === mn) mx = mn + 1;
  var padL = 14 + CANVAS_FS * 2.2, padR = 12, padT = 8 + CANVAS_FS, padB = 14 + CANVAS_FS * 1.4;
  var bW = Math.floor((W - padL - padR) / n) - 4;
  var range = getRange(m.units, m.data);
  items.forEach(function(item, idx) {
    var t = (item.val - mn) / (mx - mn);
    var barH = Math.max(4, Math.round(t * (H - padT - padB)));
    var x = padL + idx * ((W - padL - padR) / n) + 2;
    var y = H - padB - barH;
    var isStaged = !!staged[item.stk];
    ctx.fillStyle = isStaged ? 'rgba(160,120,0,0.85)' : cellBg(item.val, range);
    ctx.fillRect(x, y, bW, barH);
    if (isStaged) { ctx.strokeStyle = 'rgba(245,166,35,0.9)'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, bW, barH); }
    ctx.font = cfont(0.92); ctx.fillStyle = '#d8d8dc'; ctx.textAlign = 'center';
    ctx.fillText(item.val.toFixed(0), x + bW / 2, y - 4);
    ctx.font = cfont(0.82); ctx.fillStyle = '#8a8a90';
    ctx.fillText(item.label, x + bW / 2, H - padB + CANVAS_FS + 2);
  });
  ctx.textAlign = 'right'; ctx.fillStyle = '#8a8a90'; ctx.font = cfont(0.82);
  [0, 0.5, 1].forEach(function(t) {
    var v = mn + t * (mx - mn);
    var y = H - padB - Math.round(t * (H - padT - padB));
    ctx.fillText(v.toFixed(0), padL - 5, y + 3);
    ctx.strokeStyle = 'rgba(120,150,200,0.07)'; ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
  });
}

function redrawViz(key) {
  var m = MAPS_DATA[key];
  if (m.rows === 1 || m.cols === 1) drawBar1D(key); else drawSurf3D(key);
}

function escH(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

function buildTable(key, m, xAxis, yAxis, range, staged) {
  var tbl = document.createElement('table'); tbl.className = 'em';
  var xData = xAxis.data || [];
  var xOrder = xData.map(function(_, i) { return i; });
  xOrder.sort(function(a, b) { return (xData[a] || 0) - (xData[b] || 0); });
  var yData = yAxis.data || [];
  var yOrder = yData.map(function(_, i) { return i; });
  yOrder.sort(function(a, b) { return (yData[b] || 0) - (yData[a] || 0); });
  if (!yData.length) { for (var r = m.rows - 1; r >= 0; r--) yOrder[m.rows - 1 - r] = r; }
  var thead = tbl.createTHead(); var hrow = thead.insertRow();
  var corner = document.createElement('th'); corner.className = 'axis-label'; hrow.appendChild(corner);
  xOrder.forEach(function(ci) {
    var th = document.createElement('th'); th.className = 'axis-label';
    th.textContent = xData[ci] !== undefined ? xData[ci] : ci; th.style.color = '#ff6666';
    hrow.appendChild(th);
  });
  var tbody = tbl.createTBody();
  yOrder.forEach(function(ri) {
    var tr = tbody.insertRow();
    var rowTh = document.createElement('th'); rowTh.className = 'row-label';
    rowTh.textContent = yData[ri] !== undefined ? yData[ri] : ri; rowTh.style.color = '#55cc55';
    tr.appendChild(rowTh);
    xOrder.forEach(function(ci) {
      var td = document.createElement('td');
      var val = m.data[ri][ci];
      td.style.background = cellBg(val, range);
      td.textContent = val.toFixed(0);
      if (staged[ri + ',' + ci]) td.classList.add('staged');
      td.addEventListener('mouseenter', function() {
        var tip = document.getElementById('cellTip');
        tip.innerHTML = (xAxis.units || 'X') + ': <b>' + (xAxis.data[ci] !== undefined ? xAxis.data[ci] : ci) + '</b>  ' +
                        (yAxis.units || 'Y') + ': <b>' + (yAxis.data[ri] !== undefined ? yAxis.data[ri] : ri) + '</b>  ' +
                        'val: <b>' + val.toFixed(1) + '</b>' + (staged[ri + ',' + ci] ? '  <span style="color:var(--staged)">staged</span>' : '');
        tip.style.display = 'block';
      });
      td.addEventListener('mouseleave', function() { document.getElementById('cellTip').style.display = 'none'; });
      td.addEventListener('mousemove', function(e) {
        var tip = document.getElementById('cellTip');
        tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY - 30) + 'px';
      });
      tr.appendChild(td);
    });
  });
  return tbl;
}

function buildMapBlock(key) {
  var m = MAPS_DATA[key];
  var xAxis = AXES_DATA[m.xaxis] || { data: [], units: '' };
  var yAxis = AXES_DATA[m.yaxis] || { data: [], units: '' };
  var range = getRange(m.units, m.data);
  var staged = {}; (m.staged || []).forEach(function(stk) { staged[stk] = true; });
  CAMS[key] = { ang: -0.65, tilt: 0.88, drag: false, lx: 0, ly: 0 };

  var block = document.createElement('div');
  block.className = 'map-block' + (key.indexOf('rear') >= 0 ? ' rear' : '');

  var hdr = document.createElement('div'); hdr.className = 'map-header';
  var axisInline = (xAxis.units || yAxis.units) ? '<span class="map-axes"> &middot; ' + escH([xAxis.units, yAxis.units].filter(Boolean).join(' &middot; ')) + '</span>' : '';
  var nStaged = Object.keys(staged).length;
  var stagedBadge = nStaged ? '<span class="staged-badge">' + nStaged + ' staged (unburned)</span>' : '';
  hdr.innerHTML = '<span class="map-name">' + escH(m.label) + axisInline + '</span>' + stagedBadge +
                  '<span class="map-meta">' + m.rows + '&times;' + m.cols + ' &middot; ' + escH(m.units || '') + '</span>';
  block.appendChild(hdr);

  var body = document.createElement('div'); body.className = 'map-body';
  var tblWrap = document.createElement('div'); tblWrap.className = 'tbl-wrap';
  tblWrap.appendChild(buildTable(key, m, xAxis, yAxis, range, staged));
  body.appendChild(tblWrap);

  var c3Wrap = document.createElement('div'); c3Wrap.className = 'c3-wrap';
  var is1D = m.rows === 1 || m.cols === 1;
  var cv = document.createElement('canvas'); cv.id = 'c3-' + key; cv.width = 400; cv.height = 220;
  if (!is1D) wire3D(cv, key);
  c3Wrap.appendChild(cv);
  body.appendChild(c3Wrap);

  block.appendChild(body);
  return block;
}

function renderAll() {
  var main = document.getElementById('main');
  var keys = Object.keys(MAPS_DATA);
  keys.forEach(function(k) { main.appendChild(buildMapBlock(k)); });
  requestAnimationFrame(function() { keys.forEach(redrawViz); });
}
var _rzTimer;
window.addEventListener('resize', function() { clearTimeout(_rzTimer); _rzTimer = setTimeout(function() { Object.keys(MAPS_DATA).forEach(redrawViz); }, 150); });

renderAll();
})();
</script>
</body>
</html>`;
}
