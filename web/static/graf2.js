// DEV NOTE: All code, comments, and variable names must be in English.
// GRAF2 — professional telemetry viewer (uPlot). Self-contained, no deps on app.js.
// Data source: GET /csv/<ride>.csv (raw rows) + GET /rides (ride list).
'use strict';

(function () {
  const $ = (id) => document.getElementById(id);
  const LS_KEY = 'graf2_cfg_v1';
  const SYNC = uPlot.sync('graf2');          // shared cursor group
  const ACCENT = '#e8420a';

  // ── state ──────────────────────────────────────────────────
  let DATA = null;          // { x:Float64Array, cols:{key:Array}, keys:[], dur }
  let BLOCKS = [];          // [{ id, keys:[], height }]
  let PLOTS = {};           // id -> uPlot
  let _zoomLock = false;    // re-entrancy guard for x-scale sync
  let _pickerBlock = null;  // block id being edited
  let _dragId = null;       // block id being dragged
  let READOUT = {};         // blockId -> { u, seriesKeys, valSpans } for the unified legend
  let _yFit = false;        // false = Y fixed to full-ride range; true = Y auto-fits the visible window

  // update the live values shown in each block's chips at the cursor position
  function updateReadout(blockId) {
    const r = READOUT[blockId]; if (!r) return;
    const idx = r.u.cursor.idx;
    for (const sIdx in r.valSpans) {
      const key = r.seriesKeys[+sIdx - 1];
      const raw = (idx != null && DATA.cols[key]) ? DATA.cols[key][idx] : null;
      r.valSpans[sIdx].textContent = raw == null ? '--'
        : isFlag(key) ? (raw > 0 ? '1' : '0')
          : (Math.abs(raw) >= 100 ? raw.toFixed(0) : raw.toFixed(2));
    }
  }

  // ── annotations (region markers persisted on the Pi, consumed by F7 later) ──
  let ANNOTATIONS = [];
  let _markMode = false;
  let _pendingT0 = null;
  let _curRide = '';

  function annotationsPlugin() {
    return {
      hooks: {
        draw: (u) => {
          const ctx = u.ctx, top = u.bbox.top, H = u.bbox.height;
          ctx.save();
          ANNOTATIONS.forEach((a) => {
            const x0 = u.valToPos(a.t0_s, 'x', true), x1 = u.valToPos(a.t1_s, 'x', true);
            ctx.fillStyle = 'rgba(80,170,255,0.13)';
            ctx.fillRect(x0, top, Math.max(1, x1 - x0), H);
            ctx.strokeStyle = 'rgba(80,170,255,0.7)'; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(x0, top); ctx.lineTo(x0, top + H);
            ctx.moveTo(x1, top); ctx.lineTo(x1, top + H); ctx.stroke();
            if (a.note) {
              ctx.fillStyle = 'rgba(150,200,255,0.95)';
              ctx.font = '9px monospace'; ctx.textBaseline = 'top';
              ctx.fillText(a.note.slice(0, 36), x0 + 3, top + 2);
            }
          });
          if (_pendingT0 != null) {                  // start marker waiting for its end
            const xp = u.valToPos(_pendingT0, 'x', true);
            ctx.strokeStyle = 'rgba(255,210,0,0.9)'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(xp, top); ctx.lineTo(xp, top + H); ctx.stroke();
            ctx.setLineDash([]);
          }
          ctx.restore();
        },
      },
    };
  }

  function redrawAll() { for (const id in PLOTS) { try { PLOTS[id].redraw(); } catch (e) {} } }

  async function loadAnnotations(fname) {
    _curRide = fname;
    try {
      const r = await fetch('/annotations?ride=' + encodeURIComponent(fname) + '&t=' + Date.now());
      const d = await r.json();
      ANNOTATIONS = (d && d.annotations) || [];
    } catch (e) { ANNOTATIONS = []; }
  }

  async function postAnnotation(body) {
    try {
      const r = await fetch('/annotations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ride: _curRide, ...body }),
      });
      const d = await r.json();
      if (d && d.annotations) ANNOTATIONS = d.annotations;
    } catch (e) { $('status').textContent = 'mark save error'; }
    redrawAll();
  }

  function setMarkMode(on) {
    _markMode = on; _pendingT0 = null;
    const b = $('markBtn'); if (b) b.classList.toggle('accent', on);
    $('status').textContent = on ? 'MARK: click start, then click end' : '';
    redrawAll();
  }

  function onMarkClick(t) {
    if (_pendingT0 == null) {
      _pendingT0 = t;
      $('status').textContent = 'start @ ' + t.toFixed(2) + 's — click end';
      redrawAll();
    } else {
      const t0 = Math.min(_pendingT0, t), t1 = Math.max(_pendingT0, t);
      _pendingT0 = null;
      openNoteModal(t0, t1);
    }
  }

  function openNoteModal(t0, t1) {
    const m = document.createElement('div');
    m.className = 'modal open'; m.id = 'noteModal';
    m.innerHTML = '<div class="picker" style="max-width:380px">'
      + '<div class="picker-head"><span class="t">MARK · ' + t0.toFixed(2) + 's → ' + t1.toFixed(2) + 's (' + (t1 - t0).toFixed(2) + 's)</span></div>'
      + '<div class="picker-body"><textarea id="noteText" rows="3" placeholder="what happens in this stretch? (note for F7)"></textarea></div>'
      + '<div class="picker-foot"><button id="noteCancel">cancel</button><button id="noteSave" class="accent">save mark</button></div>'
      + '</div>';
    document.body.appendChild(m);
    const txt = m.querySelector('#noteText'); txt.focus();
    const close = () => { m.remove(); setMarkMode(false); };
    m.querySelector('#noteCancel').onclick = close;
    m.querySelector('#noteSave').onclick = async () => { await postAnnotation({ t0_s: t0, t1_s: t1, note: txt.value.trim() }); m.remove(); setMarkMode(false); };
    m.onclick = (e) => { if (e.target === m) close(); };
  }

  function listMarks() {
    if (!ANNOTATIONS.length) { $('status').textContent = 'no marks on this ride'; return; }
    const lines = ANNOTATIONS.map((a, j) => (j + 1) + ') ' + a.t0_s.toFixed(1) + '-' + a.t1_s.toFixed(1) + 's: ' + (a.note || '(no note)'));
    const i = prompt('Marks on this ride — type a number to DELETE it, or cancel:\n' + lines.join('\n'));
    const idx = parseInt(i, 10) - 1;
    if (idx >= 0 && idx < ANNOTATIONS.length) postAnnotation({ action: 'delete', id: ANNOTATIONS[idx].id });
  }

  // ── signal metadata (built from CSV header) ────────────────
  const NON_PLOTTABLE = new Set(['timestamp_iso', 'dirty_byte_hex', 'dirty_byte_name',
    'forensic_event', 'time_elapsed_s']);
  const BASE_COLOR = {
    RPM: '#e8420a', VS_KPH: '#43aaff', CLT: '#ffaa00', MAT: '#ff8800', IAT_ADC: '#44ddff',
    TPS_pct: '#3388ff', TPS_V: '#88aaff', TPS_10Bit: '#6699ff', Load: '#77aaff', TPD: '#6688ff',
    pw1: '#ff9900', pw2: '#ffcc66', spark1: '#aa88ff', spark2: '#cc88ff',
    veCurr1_RAW: '#88ffee', veCurr2_RAW: '#aaffee',
    EGO_Corr: '#00ff88', AFV: '#ffff00', WUE: '#ffdd55', Accel_Corr: '#88ff88',
    Decel_Corr: '#ff8888', WOT_Corr: '#ffff88', Idle_Corr: '#aaaaff', OL_Corr: '#ffaaff',
    IAT_Corr: '#44dd ff', O2_ADC: '#00ffff', ETS_ADC: '#ff66aa',
    Batt_V: '#77ddff', BAS_ADC: '#ffff44', Fan_Duty_Pct: '#ff6600',
    Gear: '#bb99ff', VSS_RPM_Ratio: '#66aaff', VSS_Count: '#44aa88', VS_KPH2: '#4af',
    baro_hPa: '#99aadd', baro_temp_c: '#ffbb88',
    fl_hot: '#ff4444', do_fan: '#00ccff', fl_wot: '#ffdd00', fl_accel: '#88ff88',
    fl_decel: '#ff8888', fl_engine_run: '#888888', fl_fuel_cut: '#ff5555',
    gps_alt_m: '#88cc88', gps_speed_kmh: '#66bbff',
  };
  const FLAG_RE = /^(fl_|do_|di_)/;
  const isFlag = (k) => FLAG_RE.test(k) || k === 'gps_valid';

  function hashColor(k) {
    let h = 0; for (let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) | 0;
    return `hsl(${Math.abs(h) % 360},65%,62%)`;
  }
  const colorOf = (k) => (BASE_COLOR[k] || '').replace(/\s/g, '') || hashColor(k);

  function groupOf(k) {
    if (/^fl_/.test(k)) return 'FLAGS';
    if (/^do_/.test(k)) return 'OUTPUTS';
    if (/^di_/.test(k)) return 'INPUTS';
    if (/^gps_/.test(k)) return 'GPS';
    if (/Corr$|^pw|^veCurr|EGO|AFV|WUE|O2_ADC/.test(k)) return 'FUEL';
    if (/^spark/.test(k)) return 'SPARK';
    if (/CLT|MAT|IAT|ETS|Fan_Duty|baro_temp/.test(k)) return 'THERMAL';
    if (/RPM|TPS|Load|TPD|VS_|VSS|Gear/.test(k)) return 'ENGINE';
    if (/Batt|BAS_ADC|SysConfig|DIn|DOut/.test(k)) return 'ELEC';
    if (/cpu|mem|buf_in|ttl_pct|Rides|ride_num/.test(k)) return 'SYSTEM';
    return 'RAW / DIAG';
  }
  const GROUP_ORDER = ['ENGINE', 'FUEL', 'SPARK', 'THERMAL', 'ELEC', 'FLAGS',
    'OUTPUTS', 'INPUTS', 'GPS', 'SYSTEM', 'RAW / DIAG'];

  // ── presets (tuned for the fl_hot / fan investigations) ────
  const PRESETS = {
    'HOT FLAG / FUELING': [['RPM', 'TPS_pct'], ['pw1', 'pw2'], ['CLT', 'MAT'], ['fl_hot', 'do_fan', 'fl_wot']],
    'THERMAL / FAN': [['CLT', 'MAT', 'ETS_ADC'], ['Fan_Duty_Pct'], ['baro_temp_c', 'baro_hPa'], ['do_fan', 'fl_hot']],
    'TRANSIENTS / ACCEL': [['RPM', 'VS_KPH'], ['TPS_pct'], ['pw1', 'pw2', 'Accel_Corr'], ['fl_accel', 'fl_wot', 'fl_decel']],
  };

  // ── CSV parse to columnar ──────────────────────────────────
  function parseCSV(text) {
    const lines = text.split('\n');
    let h = 0; while (h < lines.length && lines[h].startsWith('#')) h++;
    const headers = lines[h].split(',').map((s) => s.trim());
    const xi = headers.indexOf('time_elapsed_s');
    const cols = {}; headers.forEach((k) => { cols[k] = []; });
    const x = [];
    for (let i = h + 1; i < lines.length; i++) {
      const ln = lines[i]; if (!ln) continue;
      const v = ln.split(',');
      const t = parseFloat(v[xi]); if (isNaN(t)) continue;
      x.push(t);
      for (let j = 0; j < headers.length; j++) {
        const raw = v[j];
        const n = (raw === '' || raw === undefined || raw === 'None') ? null : +raw;
        cols[headers[j]].push(Number.isNaN(n) ? null : n);
      }
    }
    const keys = headers.filter((k) => !NON_PLOTTABLE.has(k) && cols[k].some((z) => z != null));
    return { x, cols, keys, dur: x.length ? x[x.length - 1] : 0 };
  }

  // ── x-scale zoom sync across all blocks ────────────────────
  function syncX(srcU) {
    if (_zoomLock) return;
    _zoomLock = true;
    const { min, max } = srcU.scales.x;
    for (const id in PLOTS) { const u = PLOTS[id]; if (u !== srcU) u.setScale('x', { min, max }); }
    _zoomLock = false;
  }

  // ── flag shading plugin (background bands where flag>0) ─────
  function flagShadePlugin() {
    return {
      hooks: {
        draw: (u) => {
          const key = $('flagShade').value;
          if (!key || !DATA || !DATA.cols[key]) return;
          const fd = DATA.cols[key], xs = DATA.x;
          const ctx = u.ctx, top = u.bbox.top, hgt = u.bbox.height;
          ctx.save();
          ctx.fillStyle = 'rgba(232,66,10,0.13)';
          let runStart = -1;
          for (let i = 0; i < fd.length; i++) {
            const on = fd[i] != null && fd[i] > 0;
            if (on && runStart < 0) runStart = i;
            if ((!on || i === fd.length - 1) && runStart >= 0) {
              const x0 = u.valToPos(xs[runStart], 'x', true);
              const x1 = u.valToPos(xs[on ? i : i - 1], 'x', true);
              ctx.fillRect(x0, top, Math.max(1, x1 - x0), hgt);
              runStart = -1;
            }
          }
          ctx.restore();
        },
      },
    };
  }

  // ── trackpad / wheel gestures ──────────────────────────────
  // ctrlKey (pinch) = zoom X · deltaX (2-finger horizontal) = pan time
  // deltaY (2-finger vertical) = let the page scroll normally
  function wheelZoomPlugin() {
    const ZOOM_GAIN = 0.0025;   // pinch zoom sensitivity — lower = slower
    const PAN_GAIN = 1.0;       // horizontal pan sensitivity
    return {
      hooks: {
        ready: (u) => {
          const over = u.over;
          over.addEventListener('wheel', (e) => {
            const ax = Math.abs(e.deltaX), ay = Math.abs(e.deltaY);
            const { min, max } = u.scales.x;
            const span = max - min;
            const rect = over.getBoundingClientRect();
            if (e.ctrlKey) {
              // trackpad pinch (or ctrl+wheel): zoom X around the cursor
              e.preventDefault();
              const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
              const k = Math.exp(e.deltaY * ZOOM_GAIN);   // spread (deltaY<0) -> k<1 -> zoom in
              const nspan = span * k, cx = min + span * frac;
              u.setScale('x', { min: cx - nspan * frac, max: cx + nspan * (1 - frac) });
            } else if (ax > ay) {
              // two-finger horizontal swipe: pan in time
              e.preventDefault();
              const dv = (e.deltaX / rect.width) * span * PAN_GAIN;
              u.setScale('x', { min: min + dv, max: max + dv });
            }
            // else: vertical scroll -> do nothing, the page scrolls
          }, { passive: false });
        },
      },
    };
  }

  // ── two-finger touch gestures ──────────────────────────────
  // pinch = zoom X · horizontal = pan time · vertical = let the page scroll
  function touchGesturePlugin() {
    return {
      hooks: {
        ready: (u) => {
          const over = u.over;
          let mode = null, sDist = 0, sCx = 0, sMin = 0, sMax = 0, sMidX = 0, sMidY = 0;
          const dist = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
          const midX = (t) => (t[0].clientX + t[1].clientX) / 2;
          const midY = (t) => (t[0].clientY + t[1].clientY) / 2;

          over.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 2) return;
            mode = null;
            sDist = dist(e.touches); sMidX = midX(e.touches); sMidY = midY(e.touches);
            sMin = u.scales.x.min; sMax = u.scales.x.max;
            const rect = over.getBoundingClientRect();
            sCx = (sMidX - rect.left) / rect.width;
          }, { passive: true });

          // tunables — ZOOM_GAIN<1 = slower zoom (0.5 ≈ half speed); START_PX = gesture deadzone
          const ZOOM_GAIN = 0.5, START_PX = 8;

          over.addEventListener('touchmove', (e) => {
            if (e.touches.length !== 2) return;
            const d = dist(e.touches), mx = midX(e.touches), my = midY(e.touches);
            const dDist = d - sDist, dx = mx - sMidX, dy = my - sMidY;
            if (!mode) {
              // ratio-based: pinch only wins if distance-change clearly dominates centroid movement
              const move = Math.hypot(dx, dy), ad = Math.abs(dDist);
              if (ad < START_PX && move < START_PX) return;          // wait for a clear gesture
              if (ad > move * 1.4 && ad > 12) mode = 'zoom';         // fingers spread/close -> zoom
              else if (Math.abs(dx) >= Math.abs(dy)) mode = 'panx';  // slide sideways -> pan time
              else { mode = 'scroll'; return; }                      // slide vertically -> page scroll
            }
            if (mode === 'scroll') return;                 // do NOT preventDefault: page scrolls
            e.preventDefault();
            const span = sMax - sMin;
            const rect = over.getBoundingClientRect();
            if (mode === 'zoom') {
              // damped pinch: ratio^ZOOM_GAIN moves gradually instead of 1:1
              const k = Math.max(0.04, Math.pow(sDist / Math.max(1, d), ZOOM_GAIN));
              const nspan = span * k, cx = sMin + span * sCx;
              u.setScale('x', { min: cx - nspan * sCx, max: cx + nspan * (1 - sCx) });
            } else {                                       // panx -> shift in time
              const dv = (dx / rect.width) * span;
              u.setScale('x', { min: sMin - dv, max: sMax - dv });
            }
          }, { passive: false });

          over.addEventListener('touchend', (e) => { if (e.touches.length < 2) mode = null; }, { passive: true });
        },
      },
    };
  }

  // ── lane labels (logic-analyzer style, left-aligned per stacked lane) ──
  function laneLabelPlugin(laned, laneH, nL) {
    return {
      hooks: {
        draw: (u) => {
          if (!nL) return;
          const ctx = u.ctx, x = u.bbox.left + 4, top = u.bbox.top, H = u.bbox.height;
          ctx.save();
          ctx.font = '9px monospace'; ctx.textBaseline = 'middle'; ctx.globalAlpha = 0.92;
          laned.forEach((k, i) => {
            const frac = (i + 0.5) * laneH;             // lane center, fraction from bottom
            ctx.fillStyle = colorOf(k);
            ctx.fillText(k, x, top + H * (1 - frac));
          });
          ctx.restore();
        },
      },
    };
  }

  // ── build one uPlot block ──────────────────────────────────
  function makeOpts(block, width) {
    const keys = block.keys.filter((k) => DATA.cols[k]);
    const laneSet = new Set(block.lanes || []);
    const laned = keys.filter((k) => isFlag(k) || laneSet.has(k));   // flags always laned + manually-laned signals
    const free = keys.filter((k) => !isFlag(k) && !laneSet.has(k));  // analog signals sharing the top area
    const nL = laned.length;
    const LANE_FRAC = 0.20;                             // each stacked lane ≈20% of panel height
    const band = nL === 0 ? 0 : Math.min(0.95, nL * LANE_FRAC);
    const laneH = nL ? band / nL : 0;                   // height fraction of a single lane

    const minmax = (k) => {
      const c = DATA.cols[k]; let mn = Infinity, mx = -Infinity;
      for (let i = 0; i < c.length; i++) { const v = c[i]; if (v != null) { if (v < mn) mn = v; if (v > mx) mx = v; } }
      if (mn === Infinity) return [0, 1];
      return mn === mx ? [mn, mn + 1] : [mn, mx];
    };

    const series = [{}];
    const scales = { x: { time: false } };
    const data = [DATA.x];

    // free analog signals — padded below so the trace stays ABOVE the lane band.
    // _yFit=false: fixed to the full-ride range (Y does NOT re-scale on zoom, keeps absolute magnitude).
    // _yFit=true : auto-fits the visible window (amplifies small variations under zoom).
    const confineLo = (lo, hi) => (band <= 0 ? lo : (lo - band * hi) / (1 - band));
    free.forEach((k) => {
      const sc = 's_' + k;
      if (_yFit) {
        scales[sc] = {
          range: (u, dmin, dmax) => {
            if (dmin == null) return [0, 1];
            if (dmax === dmin) dmax = dmin + 1;
            const pad = (dmax - dmin) * 0.06;
            return [confineLo(dmin - pad, dmax + pad), dmax + pad];
          },
        };
      } else {
        const [fmn, fmx] = minmax(k);
        const pad = (fmx - fmn) * 0.06 || 1;
        const hi = fmx + pad;
        scales[sc] = { range: [confineLo(fmn - pad, hi), hi] };   // fixed full-ride range
      }
      series.push({
        label: k, stroke: colorOf(k), width: 1.4, scale: sc, points: { show: false },
        value: (u, v) => (v == null ? '--' : (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2))),
      });
      data.push(DATA.cols[k]);
    });

    // laned signals — stacked lanes from the bottom, sharing one [0,1] scale; never overlap
    if (nL) scales.y_lanes = { range: [0, 1] };
    laned.forEach((k, i) => {
      const col = DATA.cols[k], bottom = i * laneH, flag = isFlag(k);
      let remap;
      if (flag) {
        remap = col.map((v) => (v == null ? null : bottom + (v > 0 ? 0.82 : 0.10) * laneH));
      } else {
        const [mn, mx] = minmax(k), span = mx - mn;     // analog: auto-scale within its own lane
        remap = col.map((v) => (v == null ? null : bottom + (0.08 + 0.84 * (v - mn) / span) * laneH));
      }
      series.push({
        label: k, stroke: colorOf(k), width: flag ? 1.3 : 1.4, scale: 'y_lanes', points: { show: false },
        paths: flag ? uPlot.paths.stepped({ align: 1 }) : undefined,
        // legend shows the real value, not the remapped lane position
        value: (u, _v, _si, di) => {
          if (di == null || col[di] == null) return '--';
          const o = col[di];
          return flag ? (o > 0 ? '1' : '0') : (Math.abs(o) >= 100 ? o.toFixed(0) : o.toFixed(2));
        },
      });
      data.push(remap);
    });

    return {
      opts: {
        width, height: block.height,
        cursor: { sync: { key: SYNC.key }, drag: { x: true, y: false, uni: 10 } },
        legend: { show: false },          // replaced by the unified chips in the block header
        scales,
        axes: [
          { stroke: '#555', grid: { stroke: 'rgba(255,255,255,.05)' }, ticks: { stroke: '#333' },
            font: '10px monospace', values: (u, sp) => sp.map((v) => v + 's') },
          { show: false },
        ],
        series,
        plugins: [flagShadePlugin(), annotationsPlugin(), wheelZoomPlugin(), touchGesturePlugin(), laneLabelPlugin(laned, laneH, nL)],
        hooks: {
          setScale: [(u, key) => { if (key === 'x') syncX(u); }],
          setCursor: [() => updateReadout(block.id)],
        },
      },
      data,
      seriesKeys: [...free, ...laned],   // series order after the x base, for the legend chips
    };
  }

  // ── render all blocks ──────────────────────────────────────
  function renderBlocks() {
    const host = $('blocks');
    for (const id in PLOTS) { try { PLOTS[id].destroy(); } catch (e) {} }
    PLOTS = {};
    host.innerHTML = '';
    if (!DATA) { host.innerHTML = '<div class="empty">Load a ride to start.</div>'; return; }
    if (!BLOCKS.length) { host.innerHTML = '<div class="empty">No blocks. Click “+ Block”.</div>'; return; }

    BLOCKS.forEach((block) => {
      const el = document.createElement('div');
      el.className = 'block'; el.dataset.id = block.id; el.draggable = false;
      el.innerHTML =
        `<div class="block-head" draggable="true">
           <span class="block-title">BLOCK</span>
           <div class="block-chips"></div>
           <div class="block-btns">
             <button class="iconbtn" data-act="cfg" title="signals">⚙</button>
             <button class="iconbtn" data-act="del" title="delete block">✕</button>
           </div>
         </div>
         <div class="uwrap"></div>
         <div class="resize" title="drag to resize height"></div>`;
      host.appendChild(el);

      el.querySelector('[data-act=cfg]').onclick = () => openPicker(block.id);
      el.querySelector('[data-act=del]').onclick = () => { delete READOUT[block.id]; BLOCKS = BLOCKS.filter((b) => b.id !== block.id); save(); renderBlocks(); };

      // plot first so we know the series order
      const wrap = el.querySelector('.uwrap');
      const width = wrap.clientWidth || host.clientWidth - 22;
      const { opts, data, seriesKeys } = makeOpts(block, width);
      const u = new uPlot(opts, data, wrap);
      PLOTS[block.id] = u;

      // click on the plot while in mark mode captures a time point
      u.over.addEventListener('click', (e) => {
        if (!_markMode) return;
        const rect = u.over.getBoundingClientRect();
        onMarkClick(u.posToVal(e.clientX - rect.left, 'x'));
      });

      // unified legend chips: color · name · live value · click=toggle · ×=remove
      const chips = el.querySelector('.block-chips');
      const valSpans = {};
      block.keys.forEach((k) => {
        if (!DATA.cols[k]) return;
        const sIdx = seriesKeys.indexOf(k) + 1;        // series[0] is the x base
        const inLane = (block.lanes || []).includes(k);
        const c = document.createElement('span'); c.className = 'chip';
        // flags are always laned; analog signals get a ≡ toggle to stack them into their own lane
        const laneBtn = isFlag(k) ? '' : `<span class="lane${inLane ? ' on' : ''}" title="stack in its own lane">≡</span>`;
        c.innerHTML = `<span class="dot" style="background:${colorOf(k)}"></span>`
          + `<span class="cname">${k}</span><span class="cval">--</span>${laneBtn}<span class="x" title="remove">×</span>`;
        c.onclick = (ev) => {
          if (ev.target.classList.contains('x') || ev.target.classList.contains('lane')) return;
          const show = !u.series[sIdx].show;
          u.setSeries(sIdx, { show });
          c.classList.toggle('off', !show);
        };
        const lb = c.querySelector('.lane');
        if (lb) lb.onclick = (ev) => {
          ev.stopPropagation();
          const cur = block.lanes || [];
          block.lanes = cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k];
          save(); renderBlocks();
        };
        c.querySelector('.x').onclick = (ev) => { ev.stopPropagation(); block.keys = block.keys.filter((x) => x !== k); save(); renderBlocks(); };
        chips.appendChild(c);
        valSpans[sIdx] = c.querySelector('.cval');
      });
      READOUT[block.id] = { u, seriesKeys, valSpans };

      bindResize(el, block);
      bindDrag(el, block);
    });
    refreshFlagOptions();
  }

  // ── per-block height resize ────────────────────────────────
  function bindResize(el, block) {
    const handle = el.querySelector('.resize');
    const wrap = el.querySelector('.uwrap');
    handle.addEventListener('pointerdown', (e) => {
      e.preventDefault(); handle.setPointerCapture(e.pointerId);
      const y0 = e.clientY, h0 = block.height;
      const move = (ev) => {
        block.height = Math.max(90, h0 + (ev.clientY - y0));
        const u = PLOTS[block.id];
        // uPlot width is already CSS px — keep the block's real width, only change height.
        if (u) u.setSize({ width: wrap.clientWidth, height: block.height });
      };
      const up = () => { handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', up); save(); };
      handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', up);
    });
  }

  // ── block reorder (drag header) ────────────────────────────
  function bindDrag(el, block) {
    const head = el.querySelector('.block-head');
    head.addEventListener('dragstart', () => { _dragId = block.id; el.style.opacity = '.4'; });
    head.addEventListener('dragend', () => { _dragId = null; el.style.opacity = ''; document.querySelectorAll('.block').forEach((b) => b.classList.remove('dragover')); });
    el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('dragover'); });
    el.addEventListener('dragleave', () => el.classList.remove('dragover'));
    el.addEventListener('drop', (e) => {
      e.preventDefault(); el.classList.remove('dragover');
      if (_dragId == null || _dragId === block.id) return;
      const from = BLOCKS.findIndex((b) => b.id === _dragId);
      const to = BLOCKS.findIndex((b) => b.id === block.id);
      const [m] = BLOCKS.splice(from, 1); BLOCKS.splice(to, 0, m);
      save(); renderBlocks();
    });
  }

  // ── signal picker (with search) ────────────────────────────
  function openPicker(blockId) {
    _pickerBlock = blockId;
    const block = BLOCKS.find((b) => b.id === blockId);
    $('pickerTitle').textContent = 'BLOCK SIGNALS';
    $('pickerSearch').value = '';
    buildPickerList(block, '');
    $('pickerModal').classList.add('open');
    $('pickerSearch').focus();
  }
  function buildPickerList(block, filter) {
    const body = $('pickerBody'); body.innerHTML = '';
    const sel = new Set(block.keys);
    const f = filter.trim().toLowerCase();
    const groups = {};
    DATA.keys.forEach((k) => {
      if (f && !k.toLowerCase().includes(f) && !groupOf(k).toLowerCase().includes(f)) return;
      (groups[groupOf(k)] ||= []).push(k);
    });
    GROUP_ORDER.forEach((g) => {
      if (!groups[g]) return;
      const gh = document.createElement('div'); gh.className = 'grp'; gh.textContent = g; body.appendChild(gh);
      groups[g].forEach((k) => {
        const row = document.createElement('div');
        row.className = 'sig' + (sel.has(k) ? ' on' : '');
        row.innerHTML = `<span class="dot" style="background:${colorOf(k)}"></span><span class="k">${k}</span><span class="u">${isFlag(k) ? 'flag' : ''}</span>`;
        row.onclick = () => {
          if (sel.has(k)) { sel.delete(k); row.classList.remove('on'); }
          else { sel.add(k); row.classList.add('on'); }
          block.keys = [...sel];
        };
        body.appendChild(row);
      });
    });
    if (!body.children.length) body.innerHTML = '<div class="empty">no match</div>';
  }
  function closePicker() { $('pickerModal').classList.remove('open'); _pickerBlock = null; }

  // ── flag-shade dropdown options ────────────────────────────
  function refreshFlagOptions() {
    const sel = $('flagShade'); const cur = sel.value;
    const flags = DATA ? DATA.keys.filter(isFlag) : [];
    sel.innerHTML = '<option value="">none</option>' + flags.map((k) => `<option value="${k}">${k}</option>`).join('');
    if (flags.includes(cur)) sel.value = cur;
  }

  // ── persistence ────────────────────────────────────────────
  function save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify({ blocks: BLOCKS, flag: $('flagShade').value, yfit: _yFit })); } catch (e) {}
  }
  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (s && Array.isArray(s.blocks) && s.blocks.length) { _yFit = !!s.yfit; BLOCKS = s.blocks; return s.flag || ''; }
    } catch (e) {}
    BLOCKS = PRESETS['HOT FLAG / FUELING'].map((keys, i) => ({ id: 'b' + i + '_' + Date.now(), keys: [...keys], height: 160 }));
    return 'fl_hot';
  }

  // ── ride loading ───────────────────────────────────────────
  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso); if (isNaN(d.getTime())) return '';
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  async function loadRideList() {
    try {
      const r = await fetch('/rides?t=' + Date.now());
      const d = await r.json();
      const list = (Array.isArray(d) ? d : d.rides) || [];   // /rides returns { rides:[...] }
      // most recent first
      list.sort((a, b) => new Date(b.opened_utc || b.closed_utc || 0) - new Date(a.opened_utc || a.closed_utc || 0));
      const sel = $('rideSel');
      sel.innerHTML = `<option value="">-- ride (${list.length}) --</option>` + list.map((rd) => {
        const f = rd.filename; const lbl = f.replace('_summary.json', '').replace(/_/g, ' ').toUpperCase();
        const dt = fmtDate(rd.opened_utc || rd.closed_utc);
        return `<option value="${f}">${dt} · ${lbl} · ${Math.round(rd.duration_s || 0)}s · ${rd.samples || '?'}smp</option>`;
      }).join('');
      if (!list.length) $('status').textContent = 'no rides found';
    } catch (e) { $('status').textContent = 'rides list error: ' + e.message; }
  }
  async function loadRide(fname) {
    if (!fname) return;
    const csv = fname.replace('_summary.json', '.csv');
    $('status').textContent = 'loading…';
    try {
      const r = await fetch('/csv/' + csv + '?t=' + Date.now());
      if (!r.ok) throw new Error('HTTP ' + r.status);
      DATA = parseCSV(await r.text());
      await loadAnnotations(fname);
      $('status').textContent = `${DATA.x.length} smp · ${Math.round(DATA.dur)}s · ${DATA.keys.length} signals`;
      renderBlocks();
    } catch (e) { $('status').textContent = 'error: ' + e.message; }
  }

  // ── boot ───────────────────────────────────────────────────
  function init() {
    const flag = load();
    // preset dropdown
    const ps = $('presetSel'); ps.innerHTML = '<option value="">preset…</option>' + Object.keys(PRESETS).map((p) => `<option>${p}</option>`).join('');
    ps.onchange = () => {
      if (!ps.value) return;
      BLOCKS = PRESETS[ps.value].map((keys, i) => ({ id: 'p' + i + '_' + Date.now(), keys: [...keys], height: 160 }));
      save(); renderBlocks(); ps.value = '';
    };
    $('flagShade').value = flag;
    $('flagShade').onchange = () => { save(); for (const id in PLOTS) PLOTS[id].redraw(); };
    $('loadBtn').onclick = () => loadRide($('rideSel').value);
    $('rideSel').onchange = () => loadRide($('rideSel').value);
    $('addBlock').onclick = () => { BLOCKS.push({ id: 'n_' + Date.now(), keys: [], height: 160 }); save(); renderBlocks(); openPicker(BLOCKS[BLOCKS.length - 1].id); };
    $('markBtn').onclick = () => setMarkMode(!_markMode);
    $('marksBtn').onclick = listMarks;
    const updateYfitBtn = () => { const b = $('yfitBtn'); if (b) { b.textContent = _yFit ? 'Y: fit' : 'Y: full'; b.classList.toggle('accent', _yFit); } };
    $('yfitBtn').onclick = () => { _yFit = !_yFit; save(); updateYfitBtn(); renderBlocks(); };
    updateYfitBtn();
    $('pickerClose').onclick = closePicker;
    $('pickerSearch').oninput = (e) => { const b = BLOCKS.find((x) => x.id === _pickerBlock); if (b) buildPickerList(b, e.target.value); };
    $('pickerClear').onclick = () => { const b = BLOCKS.find((x) => x.id === _pickerBlock); if (b) { b.keys = []; buildPickerList(b, $('pickerSearch').value); } };
    $('pickerApply').onclick = () => { save(); renderBlocks(); closePicker(); };
    $('pickerModal').onclick = (e) => { if (e.target.id === 'pickerModal') { save(); renderBlocks(); closePicker(); } };
    window.addEventListener('resize', () => { for (const id in PLOTS) { const b = BLOCKS.find((x) => x.id === id); const wrap = document.querySelector(`.block[data-id="${id}"] .uwrap`); if (b && wrap) PLOTS[id].setSize({ width: wrap.clientWidth, height: b.height }); } });

    loadRideList();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
