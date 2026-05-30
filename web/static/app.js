

function getGradientColor(speed) {
  const min = 0, max = 200;
  const ratio = Math.min(Math.max(speed, min), max) / max;

  const stops = [
    {pos: 0.0, r:0,   g:0,   b:255},   // Azul
    {pos: 0.3, r:0,   g:255, b:0},     // Verde
    {pos: 0.6, r:255, g:255, b:0},     // Amarillo
    {pos: 0.8, r:255, g:0,   b:0},     // Rojo
    {pos: 1.0, r:255, g:0,   b:255}    // Magenta
  ];

  let lower = stops[0], upper = stops[stops.length-1];
  for (let i=0; i<stops.length-1; i++) {
    if (ratio >= stops[i].pos && ratio <= stops[i+1].pos) {
      lower = stops[i];
      upper = stops[i+1];
      break;
    }
  }

  const t = (ratio - lower.pos) / (upper.pos - lower.pos);
  const r = Math.round(lower.r + t*(upper.r - lower.r));
  const g = Math.round(lower.g + t*(upper.g - lower.g));
  const b = Math.round(lower.b + t*(upper.b - lower.b));

  return `rgb(${r},${g},${b})`;
}


const RPM_BINS  = [0,800,1000,1350,1900,2400,2900,3400,4000,5000,6000,7000,8000];
const LOAD_BINS = [10,15,20,30,40,50,60,80,100,125,175,255];
let lastData = null;

// ── TABS ──────────────────────────────────────────────────────────
function showTab(id) {
  const ids = ['ride','rides','graph','ve','cfg','net','map'];
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab===id));
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.getElementById('pane-'+id).classList.add('active');
  if(id==="cfg")     { loadObj(); loadEcu(); loadEepromParams(); }
  if(id==='ve')      { setTimeout(loadEepromParams, 0); }
  if(id==='rides')   loadRidesList();
  if(id==='graph')   initGraphPane();
}

// ── GRID (Cobertura VE) ──────────────────────────────────────────
let _cobertMode = 'seconds';
let _cobertData = null;

function buildCobertGrid() {
  const t = document.getElementById('cobertGrid');
  if (!t) return;
  let h = '<thead><tr><th class="rh">L\\R</th>';
  for (const r of RPM_BINS) h += '<th>'+(r===0?'0':r>=1000?(r/1000)+'k':r)+'</th>';
  h += '</tr></thead><tbody>';
  for (let li = LOAD_BINS.length-1; li >= 0; li--) {
    h += '<tr><th class="rh">'+LOAD_BINS[li]+'</th>';
    for (let ri = 0; ri < RPM_BINS.length; ri++) {
      const k = RPM_BINS[ri]+'_'+LOAD_BINS[li];
      h += '<td id="gc_'+k+'" class="c0"><div class="cv" id="gs_'+k+'"></div></td>';
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
function confColor(v) {
  if(v<=0)return'rgba(100,100,100,0.5)';if(v<0.3)return'rgba(255,50,50,0.8)';
  if(v<0.6)return'rgba(255,160,50,0.85)';if(v<0.8)return'rgba(50,150,255,0.85)';
  return'rgba(50,200,50,0.9)';
}
function pctColor(p) {
  let r,g,b;
  if(p<=50){const t=p/50;r=231;g=Math.round(76+120*t);b=60;}
  else{const t=(p-50)/50;r=Math.round(231-185*t);g=Math.round(196+8*t);b=Math.round(60+53*t);}
  return'rgb('+r+','+g+','+b+')';
}

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
  } else if (m === 'confidence') {
    el.innerHTML = '<div class="leg"><div class="leg-dot" style="background:rgba(100,100,100,0.5)"></div>0%</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(255,50,50,0.8)"></div><30%</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(255,160,50,0.85)"></div>30-60%</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,150,255,0.85)"></div>60-80%</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,200,50,0.9)"></div>>80%</div>';
  } else if (m === 'o2_adc') {
    el.innerHTML = '<div class="leg" style="color:var(--dim)">O2 ADC</div>';
  } else if (m === 'ego') {
    el.innerHTML = '<div class="leg"><div class="leg-dot" style="background:rgba(255,50,50,.9)"></div><90</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(255,160,50,.85)"></div>90-95</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,200,50,.8)"></div>95-105</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(50,150,255,.85)"></div>105-110</div>'
      +'<div class="leg"><div class="leg-dot" style="background:rgba(80,80,255,.9)"></div>>110</div>';
  } else {
    const tgt = (_cobertData&&_cobertData.targets&&_cobertData.targets[m]) || '?';
    el.innerHTML = '<div class="leg" style="color:var(--dim)">'+m+' target: '+tgt+'s &middot; conf&ge;80% para converger</div>';
  }
}
function renderCobertGrid(d) {
  const cells = d.cells || {}, ac = d.active_cell || null, m = _cobertMode;
  let populated = 0;
  for (let li = 0; li < LOAD_BINS.length; li++) {
    for (let ri = 0; ri < RPM_BINS.length; ri++) {
      const k = RPM_BINS[ri]+'_'+LOAD_BINS[li];
      const td = document.getElementById('gc_'+k), sv = document.getElementById('gs_'+k);
      if (!td || !sv) continue;
      const c = cells[k] || {};
      let bg = 'c0', txt = '', isSt = false;
      if (m === 'seconds') {
        const s = c.seconds || 0;
        if (s > 0) populated++;
        bg = k===ac ? 'ca' : s<=0?'c0':s<2?'c1':s<5?'c2':s<10?'c3':'c4';
        txt = s > 0 ? (s<10?s.toFixed(1):Math.round(s))+'s' : '';
      } else if (m === 'confidence') {
        const cf = c.confidence;
        if (c.seconds > 0 && cf != null) {
          populated++;
          bg = 'background:' + confColor(cf); txt = (cf*100).toFixed(0) + '%'; isSt = true;
        }
      } else if (m === 'o2_adc') {
        const o2 = c.o2_adc_avg;
        if (c.seconds > 0 && o2 != null) {
          populated++;
          bg = 'background:' + egoColor(o2/5*100); txt = o2.toFixed(2); isSt = true;
        }
      } else if (m === 'ego') {
        const e = c.ego_avg;
        if (c.seconds > 0 && e != null) {
          populated++;
          bg = 'background:' + egoColor(e); txt = e.toFixed(1); isSt = true;
        }
      } else {
        const fl = (c.flavors || {})[m];
        if (fl) {
          populated++;
          const p = fl.pct || 0, col = pctColor(p);
          bg = 'background:' + col.replace('rgb','rgba').replace(')',',0.2)');
          txt = fl.done ? '\u2713' : p.toFixed(0) + '%';
          sv.style.color = col; isSt = true;
        }
      }
      td.className = isSt ? '' : bg;
      td.style.cssText = isSt ? bg : '';
      if (!isSt) sv.style.color = '';
      sv.textContent = txt;
    }
  }
  const st = document.getElementById('cobert-status');
  if (st) st.textContent = populated + ' / ' + (RPM_BINS.length * LOAD_BINS.length) + ' celdas con datos';
}

// ── BOTTOM SHEET ──────────────────────────────────────────────────


// ── HEADER ────────────────────────────────────────────────────────
function fmtTime(s){ return `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`; }

function updateHeader(d) {
  const lv = d.live || {};
  // Row 2: serial stats
  const ss = d.serial_stats || {};
  const ttlEl = document.getElementById('hTTL');
  const bpsEl = document.getElementById('hBPS');
  if(ttlEl){
    const pct = ss.pct || 0;
    ttlEl.textContent = pct ? pct.toFixed(0)+'%' : '--';
    ttlEl.className = 'hs-val ' + (pct > 97 || pct < 50 ? 'ac' : pct < 85 ? 'yw' : 'gn');
  }
  if(bpsEl) bpsEl.textContent = ss.bps ? ss.bps+'B/s' : '--';
  const bufEl = document.getElementById('hBuf');
  if(bufEl){
    const bp = ss.buf_pct || 0;
    bufEl.textContent = bp.toFixed(0)+'%';
    bufEl.className = 'hs-val ' + (bp > 50 ? 'ac' : bp > 20 ? 'yw' : 'gn');
  }
  const memEl = document.getElementById('hMem');
  if(memEl){
    const mp = ss.mem_pct || 0;
    memEl.textContent = mp.toFixed(0)+'%';
    memEl.className = 'hs-val ' + (mp > 80 ? 'ac' : mp > 60 ? 'yw' : 'gn');
  }
  const cpuEl = document.getElementById('hCpu');
  if(cpuEl){
    const cp = ss.cpu_pct || 0;
    cpuEl.textContent = cp.toFixed(0)+'%';
    cpuEl.className = 'hs-val ' + (cp > 80 ? 'ac' : cp > 60 ? 'yw' : 'gn');
  }
  const tempEl = document.getElementById('hTemp');
  if(tempEl){
    const tp = ss.cpu_temp || 0;
    tempEl.textContent = tp.toFixed(1)+'°';
    tempEl.className = 'hs-val ' + (tp > 75 ? 'ac' : tp > 60 ? 'yw' : 'gn');
  }
  const baroEl = document.getElementById('hBaro');
  if(baroEl){
    const bp = ss.baro_hPa || 0;
    baroEl.textContent = bp ? bp.toFixed(0) : '--';
    baroEl.className = 'hs-val gn';
  }
  const baroTempEl = document.getElementById('hBaroTemp');
  if(baroTempEl){
    const bt = ss.baro_temp_c || 0;
    baroTempEl.textContent = bt ? bt.toFixed(1) : '--';
    baroTempEl.className = 'hs-val gn';
  }
  const satEl = document.getElementById('hSat');
  if(satEl){
    const sat = lv.gps_satellites != null ? lv.gps_satellites : 0;
    const fix = lv.gps_valid === true || lv.gps_valid === 'True';
    satEl.textContent = sat;
    const _sc = 'hs-val ' + (fix ? 'gn' : sat > 0 ? 'yw' : 'ac');
    if(satEl.className !== _sc) satEl.className = _sc;
  }
  const serialEl = document.getElementById('hSerial');
  if(serialEl) serialEl.textContent = d.bike_serial ? '#'+d.bike_serial : '--';
  { const _e=document.getElementById('hEGO'); const _v=lv.EGO_Corr!=null?lv.EGO_Corr.toFixed(0)+'%':'--'; if(_e.textContent!==_v)_e.textContent=_v; }
  { const _m=document.getElementById('hMAT'); const _v=lv.MAT!=null?lv.MAT.toFixed(0)+'`':'--'; if(_m.textContent!==_v)_m.textContent=_v; }
  { const _b=document.getElementById('hBatt'); const _v=lv.Batt_V!=null?lv.Batt_V.toFixed(1)+'V':'--'; if(_b.textContent!==_v)_b.textContent=_v; }
  const gearEl = document.getElementById('hGear');
  if(gearEl){
    const g = lv.Gear;
    gearEl.textContent = (g!=null && g>0) ? g+'ª' : (g===0 ? 'N' : '--');
  }
  // Ride: show number + timer when active
  if(d.ride_active){
    document.getElementById('hRideLabel').textContent = 'R'+String(d.ride_num||0).padStart(3,'0');
    document.getElementById('hRide').textContent = fmtTime(d.elapsed_s||0);
  } else {
    document.getElementById('hRideLabel').textContent = 'Ride';
    document.getElementById('hRide').textContent = d.ride_num ? 'R'+String(d.ride_num).padStart(3,'0') : '--';
  }

  const pill = document.getElementById('hPill');
  if(d.ride_active)     { pill.textContent=''; pill.className='pill-dot on'; }
  else if(d.waiting)    { pill.textContent=''; pill.className='pill-dot yw'; }
  else                  { pill.textContent=''; pill.className='pill-dot off'; }

  // Close ride button
  const btnClose = document.getElementById('btnCloseRide');
  if(btnClose){
    btnClose.disabled = !d.ride_active;
    btnClose.style.opacity = d.ride_active ? '1' : '0.25';
    btnClose.style.cursor = d.ride_active ? 'pointer' : 'default';
  }

  // EGO color
  const egoEl = document.getElementById('hEGO');
  if(lv.EGO_Corr != null)
    egoEl.className = 'hs-val '+(lv.EGO_Corr>106?'ac':lv.EGO_Corr<94?'bl':'gn');

  // Big CHT
  const bcht = document.getElementById('bigCHT');
  if(lv.CLT != null){
    bcht.textContent = lv.CLT.toFixed(0);
    bcht.className = 'big-num';
    bcht.style.color = tempColor(lv.CLT);
  } else { bcht.textContent='--'; bcht.className='big-num ac'; }

  // Big KPH
  const bkph = document.getElementById('bigKPH');
  if(bkph) bkph.textContent = lv.VS_KPH != null ? lv.VS_KPH.toFixed(0) : '--';

  // Big RPM
  const brpm = document.getElementById('bigRPM');
  if(brpm) brpm.textContent = lv.RPM != null ? Math.round(lv.RPM) : '--';

  // Big TPS — show % (calibrated in Python) and degrees
  const tpsPct = lv.TPS_pct;
  const tpsDeg = lv.TPD;
  const bigTpsEl = document.getElementById('bigTPS');
  const bigTpsPctEl = document.getElementById('bigTPSPct');
  if(tpsPct != null){
    bigTpsEl.textContent = tpsPct.toFixed(0);
    bigTpsEl.style.color = tpsPct>80?'var(--accent)':tpsPct>50?'var(--accent2)':'var(--blue)';
    if(bigTpsPctEl) bigTpsPctEl.textContent = tpsDeg!=null ? tpsDeg.toFixed(1)+'°' : '';
  } else {
    bigTpsEl.textContent='--';
    if(bigTpsPctEl) bigTpsPctEl.textContent='';
  }

  // Config
  document.getElementById('cfgRide').textContent =
    d.ride_active ? `Ride R${d.ride_num} activo -- ${fmtTime(d.elapsed_s||0)}` : 'Standby -- esperando motor';
  if(d.ve_loaded)
    document.getElementById('cfgVeStatus').textContent = 'Mapa VE: cargado del EEPROM';
}

// ── COMPACT OBJECTIVES ───────────────────────────────────────────
function renderObjectives(objs) {
  const el = document.getElementById('objList');
  if(!objs?.length){ el.innerHTML=''; return; }
  el.innerHTML = objs.map(o => {
    const pct = Math.min(100, Math.round(o.pct));
    const cls = pct>=100?'done':pct>0?'partial':'';
    const shortLabel = o.label.replace('Zona ','').replace('Calentamiento ','Cal. ');
    return `<div class="obj-chip ${cls}">
      <div class="obj-chip-label">${shortLabel}</div>
      <div class="obj-chip-pct">${pct}%</div>
      <div class="obj-bar"><div class="obj-fill ${pct>=100?'done':''}" style="width:${pct}%"></div></div>
      <div class="obj-chip-sub">${o.done_cells}/${o.total_cells} &gt;=${o.target_s}s</div>
    </div>`;
  }).join('');
}

// ── INDICATORS ────────────────────────────────────────────────────
function renderIndicators(ind) {
  const el = document.getElementById('indicators');
  if(!ind || !Object.keys(ind).length){ el.innerHTML=''; return; }
  let html='';
  if(ind.max_cht){
    const cls=ind.max_cht.actual>260?'bad':ind.max_cht.actual>220?'warn':'ok';
    html+=`<div class="ind"><div class="dot ${cls}"></div>
      <div class="ind-text">CHT <span class="ind-val">${ind.max_cht.actual.toFixed(0)}</span>/${ind.max_cht.limit}</div></div>`;
  }
  if(ind.min_duration){
    html+=`<div class="ind"><div class="dot ${ind.min_duration.ok?'ok':'warn'}"></div>
      <div class="ind-text">Tiempo <span class="ind-val">${fmtTime(ind.min_duration.actual)}</span>/${fmtTime(ind.min_duration.limit)}</div></div>`;
  }
  el.innerHTML=html;
}

// ── FETCH LOOP ────────────────────────────────────────────────────
let _lastLiveOk = Date.now();
let _fetchingLive = false;
async function fetchLive() {
  if (_fetchingLive) return;
  _fetchingLive = true;
  document.title="LIVE";
  if(window._viewingHistory){
    try {
      const _r = await fetch('/live.json?t='+Date.now());
      if(_r.ok){
        const _d = await _r.json();
        if(_d.ride_active){
          updateHeader(_d);
        }
      }
    } catch(e){ console.warn('fetchLive(viewHistory):', e); }
    return;
  }
  try {
    const r = await fetch('/live.json?t='+Date.now());
    if(!r.ok) return;
    const d = await r.json();
    _lastLiveOk = Date.now();
    lastData = d;
    updateHeader(d);
    launchReadyTick(d);
    renderObjectives(d.objectives);
    renderIndicators(d.indicators);
    if(d.network_mode) updateNetStatus(d.network_mode, d.ip);
    if(d.logger_version){ const el=document.getElementById('hdrVersion'); if(el) el.textContent=d.logger_version; }
    // ECU disconnected banner
    const banner = document.getElementById('ecuLostBanner');
    if(banner){
      const lost = !d.ecu_connected && d.ride_active;
      banner.style.display = lost ? 'block' : 'none';
      banner.style.pointerEvents = lost ? 'auto' : 'none';
      if(lost) document.getElementById('ecuLostSecs').textContent = Math.round(d.ecu_lost_s||0);
    }
    // Active ride banner in Sessions
    const liveBanner = document.getElementById('liveRideBanner');
    if(liveBanner){
      liveBanner.style.display = d.ride_active ? 'block' : 'none';
      if(d.ride_active){
        const el = document.getElementById('liveRideNum');
        if(el) el.textContent = 'R'+String(d.ride_num||0).padStart(3,'0') + ' · ' + fmtTime(d.elapsed_s||0);
      }
    }
  } catch(e){ console.warn('fetchLive:', e); }
  finally { _fetchingLive = false; }
}


// -- LAUNCH READY STATE MACHINE ------------------------------------
let launchState = 'INACTIVE';
let launchBuffer = null;
let steadySeconds = 0;
let lastSampleElapsed = null;
let readyTimer = null;
let capturedLaunches = [];

function createRingBuffer(durationSec, sampleRateHz) {
  var maxLen = Math.ceil(durationSec * sampleRateHz) + 5;
  var buf = [];
  return {
    push: function(sample) {
      buf.push(sample);
      while (buf.length > maxLen) buf.shift();
    },
    getAll: function() { return buf.slice(); },
    getAvg: function(field) {
      if (!buf.length) return 0;
      var s = 0;
      for (var i = 0; i < buf.length; i++) s += (buf[i][field] || 0);
      return s / buf.length;
    },
    getStd: function(field) {
      if (buf.length < 2) return 0;
      var avg = this.getAvg(field);
      var s = 0;
      for (var i = 0; i < buf.length; i++) {
        var d = (buf[i][field] || 0) - avg;
        s += d * d;
      }
      return Math.sqrt(s / buf.length);
    },
    clear: function() { buf = []; },
    length: function() { return buf.length; }
  };
}

function checkBaseConditions(lv) {
  return lv.CLT > 70
      && lv.Gear >= 2
      && lv.RPM > 2000
      && lv.TPS_pct > 3
      && lv.TPS_pct < 20;
}

function captureLaunch(sample, dtps) {
  launchState = 'CAPTURED';
  var evt = {
    t: sample.t,
    gear: sample.Gear,
    pre_rpm: Math.round(launchBuffer.getAvg('RPM')),
    pre_spd: Math.round(launchBuffer.getAvg('VS_KPH') * 10) / 10,
    pre_tps: Math.round(launchBuffer.getAvg('TPS_pct') * 10) / 10,
    pre_ae: Math.round(launchBuffer.getAvg('Accel_Corr') * 10) / 10,
    tps_std: Math.round(launchBuffer.getStd('TPS_pct') * 10) / 10,
    rpm_std: Math.round(launchBuffer.getStd('RPM')),
    spd_std: Math.round(launchBuffer.getStd('VS_KPH') * 10) / 10,
    dtps_trigger: Math.round(dtps * 10) / 10,
    type: 'A'
  };
  capturedLaunches.push(evt);
  if (capturedLaunches.length > 50) capturedLaunches.shift();
  updateLaunchUI('CAPTURED', evt);
  fetch('/ride/launch_event', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(evt)
  }).catch(function(e){ console.warn('captureLaunch POST:', e); });
  if (readyTimer) clearTimeout(readyTimer);
  readyTimer = setTimeout(function() {
    launchState = 'INACTIVE';
    steadySeconds = 0;
    updateLaunchUI('INACTIVE');
  }, 2000);
}

function updateLaunchUI(state, data) {
  var cardCHT = document.querySelector('.big-card.hot');
  var cardTPSEl = document.querySelector('.big-card.tps');
  var cardRPM = document.getElementById('cardRPM');
  var gearHs = document.getElementById('hGear');
  var gearParent = gearHs ? gearHs.closest('.hs') : null;
  var bar = document.getElementById('launchBar');
  var fill = document.getElementById('launchBarFill');

  if(cardCHT) { cardCHT.className = 'big-card hot'; }
  if(cardTPSEl) { cardTPSEl.className = 'big-card tps'; }
  if(cardRPM) { cardRPM.className = 'big-card'; cardRPM.style.borderTopColor = '#ff4444'; }
  if(gearParent) { gearParent.className = 'hs'; }
  if(bar) { bar.className = 'launch-bar'; bar.classList.remove('active', 'blink'); }
  if(fill) { fill.className = 'launch-bar-fill'; fill.style.width = '0%'; }

  switch (state) {
    case 'INACTIVE':
      break;

    case 'ACCUMULATING':
      if(cardCHT) cardCHT.classList.add('launch-clt');
      if(cardTPSEl) cardTPSEl.classList.add('launch-tps');
      if(cardRPM) cardRPM.classList.add('launch-rpm');
      if(gearParent) gearParent.classList.add('launch-gear');
      if(bar) bar.classList.add('active');
      if(fill) {
        fill.classList.add('accum');
        var pct = Math.min((data.progress || 0) * 100, 100);
        fill.style.width = pct + '%';
      }
      break;

    case 'READY':
      if(cardCHT) cardCHT.classList.add('launch-ready');
      if(cardTPSEl) cardTPSEl.classList.add('launch-ready');
      if(cardRPM) cardRPM.classList.add('launch-ready');
      if(gearParent) gearParent.classList.add('launch-gear');
      if(bar) { bar.classList.add('active', 'blink'); }
      if(fill) {
        fill.classList.add('ready');
        fill.style.width = '100%';
      }
      break;

    case 'CAPTURED':
      if(cardCHT) cardCHT.classList.add('launch-ready');
      if(cardTPSEl) cardTPSEl.classList.add('launch-ready');
      if(cardRPM) cardRPM.classList.add('launch-ready');
      if(gearParent) gearParent.classList.add('launch-gear');
      if(bar) { bar.classList.add('active'); }
      if(fill) {
        fill.classList.add('ready');
        fill.style.width = '100%';
      }
      break;
  }
}

function launchReadyTick(d) {
  var lv = d.live || {};
  if (!d.ride_active || !lv.RPM) {
    if (launchState !== 'INACTIVE') {
      launchState = 'INACTIVE';
      steadySeconds = 0;
      lastSampleElapsed = null;
      updateLaunchUI('INACTIVE');
      if (readyTimer) { clearTimeout(readyTimer); readyTimer = null; }
    }
    return;
  }

  var now = d.elapsed_s;
  var dt = lastSampleElapsed ? (now - lastSampleElapsed) : 0;
  lastSampleElapsed = now;
  if (dt <= 0 || dt > 2.0) dt = 0.5;

  var sample = {
    t: now,
    RPM: lv.RPM,
    TPS_pct: lv.TPS_pct,
    VS_KPH: lv.VS_KPH,
    CLT: lv.CLT,
    Gear: lv.Gear,
    Accel_Corr: lv.Accel_Corr,
    WUE: lv.WUE
  };

  switch (launchState) {
    case 'INACTIVE':
      updateLaunchUI('INACTIVE');
      if (checkBaseConditions(lv)) {
        launchState = 'ACCUMULATING';
        launchBuffer = createRingBuffer(3.0, 2.0);
        steadySeconds = 0;
        launchBuffer.push(sample);
      }
      break;

    case 'ACCUMULATING':
      launchBuffer.push(sample);
      if (!checkBaseConditions(lv)) {
        launchState = 'INACTIVE';
        steadySeconds = 0;
        updateLaunchUI('INACTIVE');
        break;
      }
      var ts = launchBuffer.getStd('TPS_pct');
      var rs = launchBuffer.getStd('RPM');
      var ss = launchBuffer.getStd('VS_KPH');
      if (ts < 5 && rs < 100 && ss < 3) {
        steadySeconds += dt;
        if (steadySeconds >= 3.0) {
          launchState = 'READY';
          readyTimer = setTimeout(function() {
            if (launchState === 'READY') {
              launchState = 'INACTIVE';
              updateLaunchUI('INACTIVE');
            }
          }, 8000);
          updateLaunchUI('READY');
          break;
        }
      } else {
        steadySeconds = 0;
      }
      updateLaunchUI('ACCUMULATING', {
        progress: Math.min(steadySeconds / 3.0, 1.0),
        seconds: steadySeconds,
        ae: launchBuffer.getAvg('Accel_Corr')
      });
      break;

    case 'READY':
      var bufAll = launchBuffer.getAll();
      if (bufAll.length >= 1) {
        var dtps = sample.TPS_pct - bufAll[bufAll.length - 1].TPS_pct;
        if (dtps > 15) {
          clearTimeout(readyTimer);
          readyTimer = null;
          captureLaunch(sample, dtps);
          break;
        }
      }
      launchBuffer.push(sample);
      updateLaunchUI('READY');
      break;

    case 'CAPTURED':
      break;
  }
}

setInterval(fetchLive, 500);
setInterval(()=>{
  const frozen = (Date.now() - _lastLiveOk) > 5000;
  const tabs = document.querySelector('.tabs');
  const ind = document.getElementById('freezeIndicator');
  if(frozen){
    if(tabs) tabs.style.borderBottom = '2px solid #e74c3c';
    if(ind){ ind.textContent='凍結'; ind.style.color='#e74c3c'; }
  } else {
    if(tabs) tabs.style.borderBottom = '';
    if(ind){ ind.textContent='正常'; ind.style.color='#2ecc71'; }
  }
}, 3000);

// ── EEPROM MAPS ──────────────────────────────────────────────────
let _mapsData = null;
let _activeMap = 'fuel_front';

async function loadMaps(sessionId){
  const status = document.getElementById('veMapStatus');
  if(status) status.textContent = 'Leyendo EEPROM...';
  try{
    let url = '/maps?t='+Date.now();
    if(sessionId) url += '&session=' + encodeURIComponent(sessionId);
    const r = await fetch(url);
    if(!r.ok) throw new Error('HTTP '+r.status);
    _mapsData = await r.json();
    if(_mapsData && _mapsData.error){
      if(status) status.textContent = 'Error: '+_mapsData.error;
      return;
    }
    if(!_mapsData || !_mapsData.fuel_front){
      if(status) status.textContent = 'Sin mapas — conecta la ECU primero';
      return;
    }
    if(status) status.textContent = 'Mapas leídos del EEPROM ✓';
    document.getElementById('mapLegend').style.display='block';
    showMap(_activeMap);
  }catch(e){
    if(status) status.textContent = 'Error: '+e;
  }
}

function showMap(which){
  _activeMap = which;
  if(!_mapsData) return;
  const axes  = _mapsData.axes || {};
  const table = _mapsData[which];
  if(!table){ return; }

  // Axes by map type
  const isFuel  = which.startsWith('fuel');
  const unit    = isFuel ? '' : '°';
  const label   = {'fuel_front':'Fuel Front (VE)','fuel_rear':'Fuel Rear (VE)',
                   'spark_front':'Spark Advance Front (°)','spark_rear':'Spark Advance Rear (°)'}[which];
  const rawXAxis = isFuel ? (axes.fuel_rpm  || []) : (axes.spark_rpm  || []);
  const yAxis    = isFuel ? (axes.fuel_load || []) : (axes.spark_load || []);

  // RPM axis is already in ascending order (0..8000) — use directly
  const sortedRPM   = rawXAxis;
  const sortedTable = table;

  // Min/max for heatmap (ignore structural zeros for color scale)
  const allVals = sortedTable.flat().filter(v=>v>0);
  const vMin = allVals.length ? Math.min(...allVals) : 0;
  const vMax = allVals.length ? Math.max(...allVals) : 1;

  // Highlight active button
  ['FuelF','FuelR','SpkF','SpkR'].forEach(k=>{
    const btn = document.getElementById('mapBtn'+k);
    if(btn) btn.style.borderColor = '';
  });
  const btnMap = {'fuel_front':'FuelF','fuel_rear':'FuelR','spark_front':'SpkF','spark_rear':'SpkR'};
  const activeBtn = document.getElementById('mapBtn'+btnMap[which]);
  if(activeBtn) activeBtn.style.borderColor = 'var(--accent2)';

  // Build HTML table
  const cellW = 40, cellH = 22;
  let html = `<div style="font-family:var(--mono);font-size:9px;color:#aaa;margin-bottom:6px">${label}</div>`;
  html += '<table style="border-collapse:collapse;font-family:monospace;font-size:9px">';

  // Header row — actual RPM
  html += '<tr><td style="padding:2px 4px;color:var(--dim);font-size:8px">TPS↓ RPM→</td>';
  for(const rpm of sortedRPM){
    const rpmLabel = rpm>=1000 ? (rpm/1000).toFixed(1)+'k' : rpm;
    html += `<td style="padding:2px 3px;color:var(--dim);font-size:8px;text-align:center;
             min-width:${cellW}px">${rpmLabel}</td>`;
  }
  html += '</tr>';

  // Rows — iterate top to bottom (high load at top)
  const yReversed    = [...yAxis].reverse();
  const tableReversed= [...sortedTable].reverse();
  for(let ri=0; ri<tableReversed.length; ri++){
    const row     = tableReversed[ri];
    const loadVal = yReversed[ri] !== undefined ? yReversed[ri] : ri;
    html += '<tr>';
    html += `<td style="padding:2px 4px;color:var(--dim);font-size:8px;white-space:nowrap">${loadVal}%</td>`;
    for(const val of row){
      if(val === 0 || val === null){
        // Empty cell — structural zero or out-of-range region
        html += `<td style="background:#1a1a22;color:#333;padding:1px 2px;text-align:center;
                 min-width:${cellW}px;height:${cellH}px;border:1px solid rgba(255,255,255,0.04);
                 font-size:7px" title="sin datos">·</td>`;
      } else {
        const t  = (val - vMin) / (vMax - vMin || 1);
        const bg = heatColor(t);
        const fg = t > 0.55 ? '#000' : '#fff';
        html += `<td style="background:${bg};color:${fg};padding:1px 2px;text-align:center;
                 min-width:${cellW}px;height:${cellH}px;border:1px solid rgba(255,255,255,0.06)">${val.toFixed(isFuel?0:1)}${unit}</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</table>';

  const container = document.getElementById('mapContainer');
  if(container) container.innerHTML = html;
}

function tempColor(c){
  // Linear interpolation blue→white→red by °C
  // Buell XB range: 90°C normal, >225°C alert, >235°C critical
  const pts=[
    [300,[255,0,0]],[272,[255,165,0]],[244,[255,255,0]],
    [216,[255,255,150]],[188,[255,255,220]],[160,[255,255,255]],
    [115,[150,255,150]],[70,[100,200,255]],[25,[0,0,255]],[-20,[0,0,128]]
  ];
  if(c>=300)return'rgb(255,0,0)';
  if(c<=-20)return'rgb(0,0,128)';
  for(let i=0;i<pts.length-1;i++){
    const[t1,c1]=pts[i],[t2,c2]=pts[i+1];
    if(c<=t1&&c>=t2){
      const f=(c-t2)/(t1-t2);
      const r=Math.round(c2[0]+(c1[0]-c2[0])*f);
      const g=Math.round(c2[1]+(c1[1]-c2[1])*f);
      const b=Math.round(c2[2]+(c1[2]-c2[2])*f);
      return`rgb(${r},${g},${b})`;
    }
  }
  return'rgb(255,255,255)';
}
function heatColor(t){
  // Dark blue → orange → red
  const stops = [
    [0.00, [10, 30, 80]],
    [0.35, [20, 80,160]],
    [0.60, [50,160, 80]],
    [0.80, [200,120,  0]],
    [1.00, [200, 30,  0]],
  ];
  let lo=stops[0], hi=stops[stops.length-1];
  for(let i=0;i<stops.length-1;i++){
    if(t>=stops[i][0] && t<=stops[i+1][0]){ lo=stops[i]; hi=stops[i+1]; break; }
  }
  const f=(t-lo[0])/(hi[0]-lo[0]||1);
  const r=Math.round(lo[1][0]+(hi[1][0]-lo[1][0])*f);
  const g=Math.round(lo[1][1]+(hi[1][1]-lo[1][1])*f);
  const b=Math.round(lo[1][2]+(hi[1][2]-lo[1][2])*f);
  return `rgb(${r},${g},${b})`;
}

// ── OBJECTIVES EDITOR ──────────────────────────────────────────────
async function loadObj() {
  try {
    const d = await (await fetch('/live.json?t='+Date.now())).json();
    document.getElementById('objJson').value = JSON.stringify(d.raw_objectives||{}, null, 2);
  } catch(e){ document.getElementById('objJson').value='{}'; }
}
async function saveObj() {
  try {
    const v = JSON.parse(document.getElementById('objJson').value);
    await fetch('/obj',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)});
    showTab('ride');
  } catch(e){ alert('JSON invalido: '+e); }
}

// ── MSQ ────────────────────────────────────────────────────────────
function handleMsqDrop(e){ e.preventDefault(); handleMsqFile(e.dataTransfer.files[0]); }
function handleMsqFile(file){
  if(!file) return;
  const r=new FileReader();
  r.onload=e=>parseMsq(e.target.result,file.name);
  r.readAsText(file);
}
function parseMsq(xml,fname){
  try{
    const doc=new DOMParser().parseFromString(xml,'text/xml');
    let front=null,rear=null;
    doc.querySelectorAll('*').forEach(el=>{
      const n=el.getAttribute&&el.getAttribute('name');
      if(n==='veBins1'&&!front) front=el.textContent.trim();
      if(n==='veBins2'&&!rear)  rear =el.textContent.trim();
    });
    if(!front){alert('No se encontraron tablas VE');return;}
    const parse=s=>{const nums=s.trim().split(/\s+/).map(Number);const rows=[];for(let i=0;i<nums.length;i+=13)rows.push(nums.slice(i,i+13));return rows;};
    fetch('/ve',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({front:parse(front),rear:rear?parse(rear):parse(front),source:'msq',filename:fname})});
    document.getElementById('msqDrop').textContent='Cargado: '+fname;
    document.getElementById('msqDrop').className='msq-drop loaded';
  }catch(err){alert('Error: '+err);}
}

// ── CLOSE RIDE ─────────────────────────────────────────────────────
async function closeRide(){
  trackUsage('btn_close_ride');
  try{
    const r=await fetch('/close_ride',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    if(d.ok && d.session && d.ride_num){
      setTimeout(()=>{ openNoteModal(d.session, d.ride_num); }, 800);
    } else {
      // Ride was auto-closed (auto-reconnect) — open notes of last ride
      setTimeout(async()=>{
        try{
          const lr = await (await fetch('/rides?t='+Date.now())).json();
          const rides = lr.rides || [];
          if(rides.length){
            const last = rides[rides.length-1];
            openNoteModal(last.session, last.ride_num);
          }
        }catch(e){ console.warn('closeRide(fallback):', e); }
      }, 800);
    }
  }catch(e){ console.warn("closeRide:", e); }
  setTimeout(fetchLive,1000);
}

// ── NETWORK ────────────────────────────────────────────────────────
async function switchNet(action){
  const lbl=document.getElementById('netLabel');
  if(lbl) lbl.textContent=action==='wifi'?'Buscando WiFi...':'Activando hotspot...';
  let redirectUrl=null;
  try{
    const r=await fetch('/wifi/redirect_url?action='+action);
    const d=await r.json();
    redirectUrl=d.url;
  }catch(e){}
  if(redirectUrl) window.open(redirectUrl,'_blank');
  try{
    await fetch('/network',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action})});
  }catch(e){}
  _showSwitchModal(action,redirectUrl);
  _pollSwitchStatus(action,redirectUrl);
}
function _showSwitchModal(action,url){
  const msg=action==='wifi'
    ?'Conectando a WiFi...<br>La Pi cambiará de red en ~15 segundos.'
    :'Activando Hotspot...<br>Conéctate a la red buell-XXXX.';
  const urlLine=url
    ?'<br><br>Dashboard en:<br><b style="color:var(--green)">'+url+'</b>'
    :'<br><br>Espera a que la Pi confirme la nueva IP.';
  const el=document.getElementById('switchModal');
  if(el){el.innerHTML=msg+urlLine;el.style.display='block';}
}
function _hideSwitchModal(){
  const el=document.getElementById('switchModal');
  if(el) el.style.display='none';
}
async function _pollSwitchStatus(action,redirectUrl){
  for(let i=0;i<20;i++){
    await new Promise(r=>setTimeout(r,2000));
    try{
      const d=await fetch('/wifi/status').then(r=>r.json());
      const st=d.switch_status||{};
      if(st.stage==='connected'||st.stage==='fallback'||st.stage==='failed'){
        _hideSwitchModal();
        updateNetStatus(d.mode,d.ip);
        if(st.stage==='connected'&&st.ip&&!redirectUrl&&action==='wifi'){
          window.open('http://'+st.ip+':8080','_blank');
        }
        if(st.stage==='fallback') alert('No se pudo conectar. Volviendo a hotspot.');
        loadNetPane();
        return;
      }
    }catch(e){}
  }
  _hideSwitchModal();
}
function updateNetStatus(mode,ip){
  const label=document.getElementById('netLabel');
  const dot=document.getElementById('netDot');
  if(!label) return;
  document.getElementById('btnWifi')?.classList.toggle('on',mode==='wifi');
  document.getElementById('btnHotspot')?.classList.toggle('on',mode==='hotspot');
  if(mode==='wifi'){
    const url='http://'+(ip||'')+':8080';
    label.innerHTML='WiFi — <a href="'+url+'" target="_blank" style="color:var(--green);text-decoration:underline;">'+( ip||'conectado')+'</a>';
    dot.style.background='var(--green)';dot.style.animation='';
  }else if(mode==='hotspot'){
    const url='http://10.42.0.1:8080';
    label.innerHTML='Hotspot — <a href="'+url+'" target="_blank" style="color:var(--blue);text-decoration:underline;">'+(ip||'10.42.0.1')+'</a>';
    dot.style.background='var(--blue)';dot.style.animation='';
  }else{
    label.textContent='Sin red';
    dot.style.background='var(--dim)';dot.style.animation='none';
  }
}

async function loadNetPane(){
  // Load saved networks
  const sv = await fetch('/wifi/saved').then(r=>r.json()).catch(()=>({saved:[]}));
  const el = document.getElementById('savedList');
  if(!el) return;
  if(!sv.saved.length){
    el.innerHTML='<div style="font-family:var(--mono);font-size:9px;color:var(--dim)">Sin redes guardadas</div>';
    return;
  }
  el.innerHTML = sv.saved.map(s=>`
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:7px 0;border-bottom:1px solid var(--border)">
      <div>
        <span style="font-family:var(--mono);font-size:10px">${s.ssid}</span>
        <span style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-left:6px">${s.name}</span>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn g" style="font-size:9px;padding:4px 8px"
          onclick="doConnect('${s.name.replace(/'/g,"\\'")}')">Conectar</button>
        <button class="btn" style="font-size:9px;padding:4px 8px;color:var(--red)"
          onclick="doForget('${s.name.replace(/'/g,"\\'")}','${s.ssid.replace(/'/g,"\\'")}')">✕</button>
      </div>
    </div>`).join('');
}

async function doConnect(profileName){
  if(!confirm(`¿Conectar a "${profileName}"?\nEl hotspot se apagará.`)) return;
  await fetch('/wifi/connect',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({profile:profileName})});
  setTimeout(()=>{fetchLive();loadNetPane();}, 6000);
}

async function doForget(name, ssid){
  if(!confirm(`¿Eliminar red "${ssid}"?`)) return;
  await fetch('/wifi/forget',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name})});
  setTimeout(loadNetPane, 1000);
}

async function doWifiScan(e){
  const btn=e.target;
  btn.textContent='Escaneando...'; btn.disabled=true;
  const sv = await fetch('/wifi/saved').then(r=>r.json()).catch(()=>({saved:[]}));
  const savedSsids = new Set(sv.saved.map(s=>s.ssid));
  const r = await fetch('/wifi/scan').then(r=>r.json()).catch(()=>({networks:[]}));
  btn.textContent='📶 Buscar redes'; btn.disabled=false;
  const el=document.getElementById('scanList');
  if(!r.networks.length){
    el.innerHTML='<div style="font-family:var(--mono);font-size:9px;color:var(--dim)">No se encontraron redes</div>';
    return;
  }
  el.innerHTML=r.networks.map(n=>{
    const saved=savedSsids.has(n.ssid);
    return `
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:6px 0;border-bottom:1px solid var(--border)">
      <div>
        <span style="font-family:var(--mono);font-size:10px">${n.ssid}</span>
        <span style="font-family:var(--mono);font-size:8px;color:var(--dim);margin-left:6px">${n.signal}%</span>
        ${saved?'<span style="font-family:var(--mono);font-size:8px;color:var(--green);margin-left:4px">✓</span>':''}
      </div>
      <button class="btn ${saved?'g':''}" style="font-size:9px;padding:4px 8px"
        onclick="prefillWifi('${n.ssid.replace(/'/g,"\\'")}')">
        ${saved?'Conectar':'Agregar'}</button>
    </div>`}).join('');
}

function prefillWifi(ssid){
  document.getElementById('newSsid').value=ssid;
  document.getElementById('newPass').value='';
  document.getElementById('newPass').focus();
}

async function doAddWifi(){
  const ssid=document.getElementById('newSsid').value.trim();
  const pass=document.getElementById('newPass').value;
  if(!ssid||!pass){alert('Falta SSID o contraseña');return;}
  if(!confirm(`¿Conectar a "${ssid}"?\nEl hotspot se apagará.`)) return;
  await fetch('/wifi/add',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ssid,password:pass})});
  document.getElementById('newSsid').value='';
  document.getElementById('newPass').value='';
  setTimeout(()=>{fetchLive();loadNetPane();}, 8000);
}

// ── RIDES (multi-select + summary) ──────────────────────────────────
let ridesCache=[];
let selectedRides=new Set();
let _noteCtx={session:'',ride_num:0};

// ── GPS MAP ─────────────────────────────────────────────────────────
let _mapInstance = null;
let _mapPolyline = null;

async function loadMapPane() {
  // Populate selector with available rides
  const sel = document.getElementById('mapRideSelect');
  if (!sel) return;
  try {
    const d = await (await fetch('/rides?t=' + Date.now())).json();
    const rides = (d.rides || []).slice().sort((a,b) => new Date(b.opened_utc||0) - new Date(a.opened_utc||0));
    sel.innerHTML = '<option value="">-- Selecciona un ride --</option>';
    for (const r of rides) {
      const label = `${r.session} · Ride ${r.ride_num} · ${r.opened_utc ? new Date(r.opened_utc).toLocaleString() : ''}`;
      const opt = document.createElement('option');
      opt.value = JSON.stringify({session: r.session, ride: r.ride_num});
      opt.textContent = label;
      sel.appendChild(opt);
    }
  } catch(e) {
    console.error('loadMapPane error', e);
  }
  // Initialize map if not exists
  if (!_mapInstance) {
    _mapInstance = L.map('mapLeaflet').setView([32.5, -116.9], 13);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      attribution: '© OSM'
    }).addTo(_mapInstance);
  }
}

async function loadMapTrack() {
  const sel = document.getElementById('mapRideSelect');
  const info = document.getElementById('mapInfo');
  if (!sel || !sel.value) { if(info) info.textContent = 'Selecciona un ride'; return; }
  const {session, ride} = JSON.parse(sel.value);
  if(info) info.textContent = 'Cargando...';
  try {
    const d = await (await fetch(`/gps_track?session=${session}&ride=${ride}&t=${Date.now()}`)).json();
    if (!d.ok || !d.points || d.points.length === 0) {
      if(info) info.textContent = 'Sin datos GPS en este ride';
      return;
    }
    // Remove previous track
    if (_mapPolyline) { _mapInstance.removeLayer(_mapPolyline); _mapPolyline = null; }
    const latlngs = d.points.map(p => [p.lat, p.lon]);
    // Color by speed
    function getSpeedColor(spd) {
      if (spd <=  20) return '#0000FF'; // Blue
      if (spd <=  60) return '#00FF00'; // Green
      if (spd <= 120) return '#FFFF00'; // Yellow
      if (spd <= 160) return '#FF0000'; // Red
      return '#FF00FF';                 // Magenta 160+
    }
    for (let i = 0; i < latlngs.length - 1; i++) {
      L.polyline([latlngs[i], latlngs[i+1]], {
        color: getGradientColor(d.points[i].spd), weight: 4, opacity: 0.85
      }).addTo(_mapInstance);
    }
    // Start and end marker
    L.circleMarker(latlngs[0], {radius:7, color:'#00ff88', fillColor:'#00ff88', fillOpacity:1}).addTo(_mapInstance).bindPopup('Inicio');
    L.circleMarker(latlngs[latlngs.length-1], {radius:7, color:'#ff4444', fillColor:'#ff4444', fillOpacity:1}).addTo(_mapInstance).bindPopup('Fin');
    _mapInstance.fitBounds(latlngs);
    const maxSpd2 = Math.max(...d.points.map(p=>p.spd)).toFixed(1);
    const dist = d.points.reduce((acc,p,i)=> i===0 ? 0 : acc + Math.hypot(p.lat-d.points[i-1].lat, p.lon-d.points[i-1].lon)*111.32, 0).toFixed(2);
    if(info) info.textContent = `${d.count} puntos · Vel max ${maxSpd2} km/h · ~${dist} km`;
    // ── Perfil de altitud ──────────────────────────────────────────
    const altCanvas = document.getElementById('altitudeChart');
    if (altCanvas) {
      if (window._altChart) { window._altChart.destroy(); window._altChart = null; }
      // Calculate cumulative distance
      let distAcc = 0;
      const altLabels = [];
      const altData = [];
      const altColors = [];
      const spdData = [];
      const spdColors = [];
      for (let i = 0; i < d.points.length; i++) {
        if (i > 0) {
          distAcc += Math.hypot(
            d.points[i].lat - d.points[i-1].lat,
            d.points[i].lon - d.points[i-1].lon
          ) * 111.32;
        }
        if (d.points[i].alt !== null && d.points[i].alt !== undefined) {
          altLabels.push(distAcc.toFixed(2));
          altData.push(d.points[i].alt);
          altColors.push(getSpeedColor(d.points[i].spd));
          spdData.push(d.points[i].spd);
          spdColors.push(getGradientColor(d.points[i].spd));
        }
      }
      window._altChart = new Chart(altCanvas, {
        type: 'line',
        data: {
          labels: altLabels,
          datasets: [{
            label: 'Altitud (m)',
            data: altData,
            borderColor: altColors,
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            fill: {
              target: 'origin',
              above: 'rgba(0,100,255,0.08)'
            },
            segment: {
              borderColor: ctx => altColors[ctx.p0DataIndex] || '#fff'
            }
          },
          {
            label: 'Velocidad (km/h)',
            data: spdData,
            borderColor: spdColors,
            borderWidth: 2.5,
            pointRadius: 0,
            tension: 0.2,
            segment: {
              borderColor: ctx => spdColors[ctx.p0DataIndex] || '#fff'
            },
            yAxisID: 'y1'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(ctx) { return ctx.dataset.label === "Altitud (m)" ? "Alt: " + ctx.parsed.y.toFixed(1) + "m" : "Vel: " + ctx.parsed.y.toFixed(1) + " km/h"; }
              }
            }
          },
          scales: {
            x: {
              ticks: { color: '#666', font: { size: 8 }, maxTicksLimit: 8 },
              grid: { color: '#1e1e24' },
              title: { display: true, text: 'Distancia (km)', color: '#666', font: { size: 8 } }
            },
            y: {
              ticks: { color: '#aaa', font: { size: 8 } },
              grid: { color: '#1e1e24' },
              title: { display: true, text: 'Altitud (m)', color: '#666', font: { size: 8 } }
            },
            y1: {
              position: 'right',
              ticks: { color: '#4af', font: { size: 8 },
                callback: function(value) { return value + ' km/h'; }
              },
              grid: { display: false },
              title: { display: true, text: 'Velocidad (km/h)', color: '#4af', font: { size: 8 } }
            }
          }
        }
      });
    }
  } catch(e) {
    if(info) info.textContent = 'Error: ' + e;
  }
}
// ────────────────────────────────────────────────────────────────────

async function loadSessions(){
  const el=document.getElementById('ridesList'); if(!el) return;
  el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px;text-align:center">Cargando...</div>';
  try{
    const d=await(await fetch('/rides?t='+Date.now())).json();
    const rides=(d.rides||[]);
    ridesCache=rides.slice().reverse();
    if(!ridesCache.length){
      el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px;text-align:center">Sin rides guardados</div>';
      return;
    }
    const sessions={};
    for(const r of ridesCache){
      if(!sessions[r.session]) sessions[r.session]={rides:[],latest:0,latestUtc:''};
      sessions[r.session].rides.push(r);
      if((r.ride_num||0)>sessions[r.session].latest) sessions[r.session].latest=r.ride_num||0;
      if((r.opened_utc||'')>sessions[r.session].latestUtc) sessions[r.session].latestUtc=r.opened_utc||'';
    }
    const sesKeys=Object.keys(sessions).sort((a,b)=>(sessions[b].latestUtc||'').localeCompare(sessions[a].latestUtc||''));
    const live=lastData?.ride_active;
    let html='';
    if(live) html+='<div style="font-family:var(--mono);font-size:9px;color:var(--accent);padding:4px 0 10px">⚡ Ride activo — historial disponible al terminar</div>';
    for(const sk of sesKeys){
      const s=sessions[sk];
      html+=`<div style="margin-bottom:12px">
        <div onclick="toggleSession('ses_${sk}')" style="cursor:pointer;display:flex;justify-content:space-between;
             align-items:center;background:#1a1a1a;border:1px solid var(--border);padding:7px 10px;margin-bottom:2px">
          <span style="font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.1em">${sk}<span style="font-size:8px;margin-left:8px;color:#666">${s.latestUtc?new Date(s.latestUtc).toLocaleDateString():''}</span></span>
          <span style="font-family:var(--mono);font-size:9px;color:var(--dim)">${s.rides.length} rides ▾</span>
        </div>
        <div id="ses_${sk}">`;
      for(const r of s.rides){
        const ri=ridesCache.indexOf(r);
        const dur=r.duration_s?Math.round(r.duration_s)+'s':'--';
        const dtcBadge=(r.dtc_events&&r.dtc_events.length)?`<span style="color:var(--accent);font-size:9px">⚠${r.dtc_events.length}</span>`:'';
        const noteBadge=r.has_note?'<span style="color:#7df;font-size:9px">📝</span>':'';
const errBadge=r.has_errorlog?`<span style="color:#f90;font-size:9px;cursor:pointer;text-decoration:underline dotted rgba(255,153,0,0.4)" title="${r.errorlog_summary||'errores'} — clic para ver" onclick="event.stopPropagation();openErrorLog('${sk}',${r.ride_num})">⚠️${r.errorlog_events||''}</span>`:'';
        const closeR=r.close_reason?` · ${r.close_reason}`:'';
        html+=`<div class="ride-item" style="gap:4px;opacity:${live?0.5:1};pointer-events:${live?'none':'auto'}">
          <div style="flex:1;min-width:0">
            <div class="ride-name" style="display:flex;align-items:center;gap:5px">
              ${r.filename.replace('_summary.json','')} ${dtcBadge} ${noteBadge} ${errBadge}
            </div>
            <div class="ride-meta">${dur} · ${r.samples} muestras${closeR}</div>
            ${r.has_note?`<div style="font-family:var(--mono);font-size:8px;color:#888;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r.note_preview}</div>`:''}
          </div>
          <div style="display:flex;gap:4px;flex-shrink:0">
            <button class="btn" style="font-size:9px;padding:4px 7px" onclick="viewSingleRide(${ri})">Ver</button>
            <button class="btn p" style="font-size:9px;padding:4px 7px" onclick="openRideGraph(${ri})">Graf</button>
            <button class="btn" style="font-size:9px;padding:4px 7px" onclick="openNoteModal('${sk}',${r.ride_num})">📝</button>
            <a href="/csv/${r.filename}?t=${Date.now()}" download="${r.filename.replace('_summary.json','.csv')}"
               onclick="event.stopPropagation()"
               style="font-family:var(--mono);font-size:9px;color:var(--blue);text-decoration:none;
                      border:1px solid var(--blue);padding:4px 6px">CSV</a>
          </div>
        </div>`;
      }
      html+=`</div></div>`;
    }
    el.innerHTML=html;
  }catch(e){
    el.innerHTML='<div style="font-family:var(--mono);font-size:10px;color:var(--dim);padding:20px">Error: '+e+'</div>';
  }
}

function toggleSession(id){
  const el=document.getElementById(id); if(!el) return;
  el.style.display=el.style.display==='none'?'':'none';
}

function openNoteModal(session,ride_num){
  _noteCtx={session,ride_num};
  document.getElementById('noteModalTitle').textContent=`NOTA — ${session} ride_${String(ride_num).padStart(3,'0')}`;
  document.getElementById('noteText').value='';
  document.getElementById('noteStatus').textContent='Cargando...';
  document.getElementById('noteModal').style.display='flex';
  fetch(`/ride_note?session=${encodeURIComponent(session)}&ride=${ride_num}&t=${Date.now()}`)
    .then(r=>r.json()).then(d=>{
      document.getElementById('noteText').value=d.note||'';
      document.getElementById('noteStatus').textContent='';
    }).catch(()=>{ document.getElementById('noteStatus').textContent=''; });
}

function closeNoteModal(){
  document.getElementById('noteModal').style.display='none';
  loadSessions();
}

async function saveNote(){
  const text=document.getElementById('noteText').value;
  trackUsage('btn_guardar_nota');
  document.getElementById('noteStatus').textContent='Guardando...';
  try{
    const r=await fetch('/ride_note',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session:_noteCtx.session,ride_num:_noteCtx.ride_num,note:text})});
    const d=await r.json();
    document.getElementById('noteStatus').textContent=d.ok?'✓ Guardado':'Error al guardar';
    if(d.ok) setTimeout(()=>{ document.getElementById('noteStatus').textContent=''; },1500);
  }catch(e){ document.getElementById('noteStatus').textContent='Error: '+e; }
}

async function viewSingleRide(idx){
  trackUsage('btn_ver_ride');
  selectedRides=new Set([idx]);
  await viewSelectedRides();
}

function openRideGraph(idx){
  trackUsage('btn_graf_ride');
  const r=ridesCache[idx]; if(!r) return;
  // Load VE map from the session this ride belongs to
  if(r.session) loadMaps(r.session);
  showTab('graph');
  // Pass filename directly — don't depend on select being populated
  setTimeout(()=>{ if(r.filename) loadGraphRide(r.filename); },120);
}

function openLiveRideGraph(){
  if(!ridesCache || !ridesCache.length){ alert('Cargando rides...'); loadSessions(); return; }
  showTab('graph');
  setTimeout(()=>{ loadGraphRide(ridesCache[0].filename); },120);
}

// loadRidesList alias for compatibility with initGraphPane
function loadRidesList(){ return loadSessions(); }

async function viewSelectedRides(){
  if(!selectedRides.size) return;
  const indices=[...selectedRides];
  const rides=indices.map(i=>ridesCache[i]).filter(Boolean);
  const summaries=await Promise.all(rides.map(r=>
    fetch('/ride/'+r.filename+'?t='+Date.now()).then(x=>x.json()).catch(()=>null)
  ));
  const merged={};
  for(const s of summaries){
    if(!s) continue;
    for(const [key,val] of Object.entries(s.cells||{})){
      if(!merged[key]) merged[key]={seconds:0,ego_sum:0,count:0,valid_seconds:0,valid_ego_sum:0,valid_count:0,flavor_sum:{}};
      const useValid = val.valid_seconds != null && val.valid_seconds > 0;
      const vs  = useValid ? val.valid_seconds : (val.seconds || 0);
      const vea = useValid && val.valid_ego_avg != null ? val.valid_ego_avg : (val.ego_avg != null ? val.ego_avg : 100.0);
      merged[key].valid_seconds += vs;
      merged[key].ego_sum       += (val.ego_avg || 100.0) * vs;
      merged[key].count         += vs;
      merged[key].valid_ego_sum += vea * vs;
      merged[key].valid_count   += vs;
      if(val.flavor_counts) { for(const [fl,secs] of Object.entries(val.flavor_counts)) { merged[key].flavor_sum[fl]=(merged[key].flavor_sum[fl]||0)+secs; } }
    }
  }
  const cells={};
  for(const [k,v] of Object.entries(merged))
    cells[k]={seconds:parseFloat((v.valid_seconds||0).toFixed(1)),ego_avg:parseFloat(((v.valid_ego_sum||0)/(v.valid_count||1)).toFixed(1)),valid_ego_avg:parseFloat(((v.valid_ego_sum||0)/(v.valid_count||1)).toFixed(1))};
  const objCfg=lastData?.raw_objectives||{};
  const objectives=(objCfg.cell_targets||[]).map(ct=>{
    const matching=RPM_BINS.flatMap(r=>LOAD_BINS.filter(l=>r>=ct.rpm_min&&r<=ct.rpm_max&&l>=ct.load_min&&l<=ct.load_max).map(l=>`${r}_${l}`));
    const done=matching.filter(k=>cells[k]?.seconds>=(ct.seconds||5)).length;
    return {label:ct.label,target_s:ct.seconds,done_cells:done,total_cells:matching.length,pct:matching.length?done/matching.length*100:0};
  });
  const rideLabel=rides.length===1?rides[0].filename.replace('.csv','').replace('_',' '):
                  `${rides.length} rides sumados`;
  // Convert to cobertura grid format
  const cobertCells = {};
  const fTargets = (objCfg.flavor_targets || {});
  for (const [k, v] of Object.entries(cells)) {
    const ego = v.valid_ego_avg != null ? v.valid_ego_avg : v.ego_avg;
    const flavors = {};
    const fs = (merged[k] || {}).flavor_sum || {};
    for (const [fl, secs] of Object.entries(fs)) {
      if (secs > 0) {
        const ts = fTargets[fl] || 30;
        const pct = Math.round(Math.min(100, secs / ts * 100) * 10) / 10;
        flavors[fl] = {seconds: Math.round(secs * 10) / 10, pct, target: ts, done: pct >= 100};
      }
    }
    cobertCells[k] = {
      seconds: v.seconds || 0,
      ego_avg: ego || 100.0,
      confidence: 0.0,
      flavors
    };
  }
  _cobertData = { cells: cobertCells, active_cell: null, summary: {}, targets: fTargets, n_cells: Object.keys(cobertCells).length };
  setCobertMode(_cobertMode);
  lastData={...(lastData||{}),cells,objectives,ride_active:false,
            ride_num:null,elapsed_s:0,active_cell:null};
  renderObjectives(objectives);
  window._viewingHistory=true;
  showTab('ride');
  document.getElementById('objList').insertAdjacentHTML('afterbegin',
    `<div style="background:rgba(232,66,10,.12);border:1px solid var(--accent);padding:8px 10px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;font-family:var(--mono);font-size:9px;color:var(--accent);width:100%">
      <span>${rideLabel}</span>
      <span onclick="exitHistory()" style="cursor:pointer;padding:2px 8px;border:1px solid var(--accent)">LIVE</span>
    </div>`);
}

let _pollingCobert = false;
async function pollCobertGrid() {
  if (window._viewingHistory) return;
  if (_pollingCobert) return;
  _pollingCobert = true;
  try {
    const r = await fetch('/coverage.json?t='+Date.now());
    if (!r.ok) return;
    const d = await r.json();
    _cobertData = d;
    renderCobertGrid(d);
  } catch(e) { console.warn('pollCobertGrid:', e); }
  finally { _pollingCobert = false; }
}

function exitHistory(){
  window._viewingHistory=false;
  fetchLive();
}

// ── USAGE TRACKER ─────────────────────────────────────────────────
function trackUsage(action){}






// ── CHARTS ─────────────────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════
// CHARTS — Chart.js with event markers
// ═══════════════════════════════════════════════════════════════

const CHART_DEFAULTS = {
  animation: false,
  responsive: false,
  maintainAspectRatio: false,
  interaction: { mode:'index', intersect:false },
  plugins: { legend:{ display:false }, tooltip:{ enabled:true,
    callbacks:{ label: ctx => `${ctx.dataset.label||''}: ${ctx.parsed.y!=null?ctx.parsed.y.toFixed(1):''}` }
  }},
  scales:{
    x:{ type:'linear', ticks:{ font:{family:'monospace',size:8}, color:'#555',
          callback: v => v%30===0 ? (v+'s') : '' },
        grid:{ color:'rgba(255,255,255,.04)' }},
    y:{ ticks:{ font:{family:'monospace',size:8}, color:'#777' },
        grid:{ color:'rgba(255,255,255,.06)' }}
  }
};

let _charts = {};

function destroyCharts(){
  for(const ch of Object.values(_charts)) try{ ch.destroy(); }catch(e){}
  _charts={};
}

// Color palette
const C = {
  rpm:'#e8420a', kph:'#4af', clt:'#fa0', clt_hot:'#f80',
  tps:'#38f', ego:'#0f8', spk1:'#a8f', spk2:'#c8f',
  afv:'#ff0', wue:'#f90', batt:'#7df', cel:'#8af', dtc:'#ff4', kill:'#f44',
  wot:'#0f8', gear:'#a8f', hot:'#f80', cold:'#4af',
};

// Scatter marker dataset
function markerSet(label, data, color, symbol='circle', r=4){
  return { label, data, type:'scatter', pointStyle:symbol,
           pointRadius:r, pointHoverRadius:r+2,
           backgroundColor:color+'cc', borderColor:color,
           borderWidth:1, showLine:false, order:-1 };
}

// ── CSV PARSING ──────────────────────────────────────────────────
function parseCSVtoRows(text){
  const lines = text.trim().split('\n').filter(l=>!l.startsWith('#'));
  const headers = lines[0].split(',').map(h=>h.trim());
  const rows = [];
  for(let i=1;i<lines.length;i++){
    const vals = lines[i].split(',');
    const row = {};
    headers.forEach((h,j) => {
      const v = vals[j]?.trim();
      row[h] = (v===''||v===undefined||v==='None') ? null : isNaN(v) ? v : parseFloat(v);
    });
    rows.push(row);
  }
  return rows;
}

// ── EXTRACT BIT CHANGE EVENTS ────────────────────────────────────
function extractTransitions(rows, field, targetVal=1){
  const events=[]; let prev=null;
  for(const r of rows){
    const v = r[field];
    if(prev!=null && prev!==targetVal && v===targetVal)
      events.push({x: r.time_elapsed_s, y: null});
    prev = v;
  }
  return events;
}


// Detect gear changes by RPM jumps with stable VSS
function detectGearChanges(rows){
  const events=[];
  for(let i=2;i<rows.length;i++){
    const r=rows[i], p=rows[i-2];
    const drpm = Math.abs((r.RPM||0)-(p.RPM||0));
    const vss  = r.VSS_Count||0;
    if(drpm>400 && vss>10) events.push({x:r.time_elapsed_s, y:null});
  }
  return events;
}

// Detect WOT (TPS > 80%)
function detectWOT(rows){
  const ev=[]; let inWOT=false;
  for(const r of rows){
    if(!inWOT && (r.TPS_pct||0)>80){ ev.push({x:r.time_elapsed_s,y:null}); inWOT=true; }
    if(inWOT  && (r.TPS_pct||0)<60){ inWOT=false; }
  }
  return ev;
}

// Detect new DTC (CDiag0-4 changes to nonzero)
function detectDTC(rows){
  const ev=[]; let prev=0;
  for(const r of rows){
    const sum=(r.CDiag0||0)+(r.CDiag1||0)+(r.CDiag2||0)+(r.CDiag3||0)+(r.CDiag4||0);
    if(sum>0 && prev===0) ev.push({x:r.time_elapsed_s,y:null});
    prev=sum;
  }
  return ev;
}

// ── BUILD CHARTS ────────────────────────────────────────────────────
function buildCharts(rows){
  window._lastBuildRows = rows;
  destroyCharts();
  if(!rows || rows.length < 2) return;

  const t      = rows.map(r=>r.time_elapsed_s);
  const tFirst = t[0]  ?? 0;
  const tLast  = t[t.length-1] ?? 1;
  const durS   = tLast - tFirst || 1;

  // Dynamic width — 4px/s, max 16000px, no Y-axis padding
  const PX_PER_SEC = 4;
  const outerW = document.getElementById('chartsOuter')?.clientWidth || 360;
  const dataW  = Math.min(Math.max(outerW, Math.ceil(durS * PX_PER_SEC)), 16000);
  const totalW = dataW;

  document.getElementById('chartsInner').style.width = totalW + 'px';
  document.querySelectorAll('#chartsInner .chart-inner').forEach(d => {
    d.style.width = totalW + 'px';
  });

  // Scrollbar proxy
  const sb  = document.getElementById('chartScrollbar');
  const sbi = document.getElementById('chartScrollbarInner');
  if(sbi) sbi.style.width = totalW + 'px';

  // Sync scroll — attach once per buildCharts call
  const outer = document.getElementById('chartsOuter');
  if(sb && outer){
    const _sb  = sb._buellScrollHandler;
    const _out = outer._buellScrollHandler;
    if(_sb)  sb.removeEventListener('scroll', _sb);
    if(_out) outer.removeEventListener('scroll', _out);
    let _lock = false;
    sb._buellScrollHandler = ()=>{ if(_lock)return; _lock=true; outer.scrollLeft=sb.scrollLeft; _lock=false; };
    outer._buellScrollHandler = ()=>{ if(_lock)return; _lock=true; sb.scrollLeft=outer.scrollLeft; _lock=false; };
    sb.addEventListener('scroll', sb._buellScrollHandler);
    outer.addEventListener('scroll', outer._buellScrollHandler);
  }

  // ── Full signal catalogue ─────────────────────────────────
  // Each entry: { key, label, color, dash? }
  const ALL_SIGNALS = [
    // Engine
    { key:'RPM',         label:'RPM',          color:'#e8420a' },
    { key:'VS_KPH',      label:'KPH',           color:'#4af' },
    { key:'CLT',         label:'CLT °C',        color:'#fa0' },
    { key:'MAT',         label:'MAT °C',        color:'#f90' },
    { key:'TPS_pct',     label:'TPS %',         color:'#38f' },
    { key:'Load',        label:'Load',          color:'#7af' },
    { key:'TPD',         label:'TPD',           color:'#68f' },
    // Fuel
    { key:'EGO_Corr',    label:'EGO Corr %',    color:'#0f8' },
    { key:'AFV',         label:'AFV %',         color:'#ff0' },
    { key:'WUE',         label:'WUE %',         color:'#f90', dash:[3,2] },
    { key:'IAT_Corr',    label:'IAT Corr %',    color:'#4df' },
    { key:'Accel_Corr',  label:'Accel Corr %',  color:'#8f8' },
    { key:'Decel_Corr',  label:'Decel Corr %',  color:'#f88' },
    { key:'WOT_Corr',    label:'WOT Corr %',    color:'#ff8' },
    { key:'Idle_Corr',   label:'Idle Corr %',   color:'#aaf' },
    { key:'OL_Corr',     label:'OL Corr %',     color:'#faf' },
    { key:'pw1',         label:'PW1 ms',        color:'#f90' },
    { key:'pw2',         label:'PW2 ms',        color:'#fa6', dash:[3,2] },
    // Ignition
    { key:'spark1',      label:'Spark1 °BTDC',  color:'#a8f' },
    { key:'spark2',      label:'Spark2 °BTDC',  color:'#c8f', dash:[3,2] },
    { key:'veCurr1_RAW', label:'VE Curr1 RAW',  color:'#8ff' },
    { key:'veCurr2_RAW', label:'VE Curr2 RAW',  color:'#aff', dash:[3,2] },
    // Electrical
    { key:'Batt_V',      label:'Batt V',        color:'#7df' },
    { key:'Fan_Duty_Pct',label:'Fan Duty %',    color:'#f80' },
    // Sensors/ADC
    { key:'O2_ADC',      label:'O2 ADC',        color:'#0ff' },
    { key:'ETS_ADC',     label:'ETS ADC',       color:'#f4f' },
    { key:'IAT_ADC',     label:'IAT ADC',       color:'#4ff' },
    { key:'BAS_ADC',     label:'BAS ADC',       color:'#ff4' },
    { key:'TPS_V',       label:'TPS V',         color:'#8af' },
    // Speed/Gear
    { key:'VSS_Count',   label:'VSS Count',     color:'#4a8' },
    { key:'VSS_RPM_Ratio',label:'VSS/RPM',      color:'#6af' },
    { key:'Gear',        label:'Gear',          color:'#a8f' },
    // System
    { key:'ttl_pct',     label:'TTL %',         color:'#0f4' },
    { key:'cpu_pct',     label:'CPU %',         color:'#f44' },
    { key:'cpu_temp',    label:'CPU Temp',      color:'#f84' },
    { key:'mem_pct',     label:'MEM %',         color:'#48f' },
    { key:'buf_in',      label:'Buf In',        color:'#888' },
    // Flags
    { key:'fl_engine_run',  label:'FL: Engine Run',   color:'#0f8' },
    { key:'fl_wot',         label:'FL: WOT',           color:'#0f8' },
    { key:'fl_accel',       label:'FL: Accel Enrich',  color:'#4af' },
    { key:'fl_decel',       label:'FL: Decel Cut',     color:'#aaf' },
    { key:'fl_closed_loop', label:'FL: Closed Loop',   color:'#ff0' },
    { key:'fl_rich',        label:'FL: Rich',          color:'#f44' },
    { key:'fl_learn',       label:'FL: Learn',         color:'#fa0' },
    { key:'fl_hot',         label:'FL: Overtemp',      color:'#f80' },
    { key:'fl_kill',        label:'FL: Kill',          color:'#f44' },
    { key:'fl_fuel_cut',    label:'FL: Fuel Cut',      color:'#f44' },
    { key:'fl_o2_active',   label:'FL: O2 Active',     color:'#0ff' },
    { key:'fl_engine_stop', label:'FL: Engine Stop',   color:'#f88' },
    { key:'fl_ignition',    label:'FL: Ignition',      color:'#ff8' },
    { key:'fl_cam_active',  label:'FL: Cam Active',    color:'#8f8' },
    { key:'fl_immob',       label:'FL: Immob',         color:'#f8f' },
    { key:'do_coil1',       label:'DO: Coil1',         color:'#a8f' },
    { key:'do_coil2',       label:'DO: Coil2',         color:'#c8f' },
    { key:'do_inj1',        label:'DO: Inj1',          color:'#f90' },
    { key:'do_inj2',        label:'DO: Inj2',          color:'#fa6' },
    { key:'do_fuel_pump',   label:'DO: Fuel Pump',     color:'#4f8' },
    { key:'do_tacho',       label:'DO: Tacho',         color:'#8af' },
    { key:'do_cel',         label:'DO: CEL',           color:'#8af' },
    { key:'do_fan',         label:'DO: Fan',           color:'#f80' },
    { key:'di_cam',         label:'DI: Cam',           color:'#4af' },
    { key:'di_tacho_fb',    label:'DI: Tacho FB',      color:'#7af' },
    { key:'di_vss',         label:'DI: VSS',           color:'#4f8' },
    { key:'di_clutch',      label:'DI: Clutch',        color:'#fa8' },
    { key:'di_neutral',     label:'DI: Neutral',       color:'#af8' },
    { key:'di_crank',       label:'DI: Crank',         color:'#8fa' },
    // Raw/Unknown
    { key:'Flags0',      label:'Flags0 RAW',    color:'#666' },
    { key:'Flags1',      label:'Flags1 RAW',    color:'#666' },
    { key:'Flags2',      label:'Flags2 RAW',    color:'#666' },
    { key:'Flags3',      label:'Flags3 RAW',    color:'#666' },
    { key:'Flags4',      label:'Flags4 RAW',    color:'#666' },
    { key:'Flags5',      label:'Flags5 RAW',    color:'#666' },
    { key:'Flags6',      label:'Flags6 RAW',    color:'#666' },
    { key:'Unk63',       label:'Unk63',         color:'#555' },
    { key:'Unk80',       label:'Unk80',         color:'#555' },
    { key:'Unk81',       label:'Unk81',         color:'#555' },
    { key:'Unk82',       label:'Unk82',         color:'#555' },
    { key:'CDiag0',      label:'CDiag0',        color:'#f44' },
    { key:'CDiag1',      label:'CDiag1',        color:'#f44' },
    { key:'CDiag2',      label:'CDiag2',        color:'#f44' },
    { key:'CDiag3',      label:'CDiag3',        color:'#f44' },
    { key:'CDiag4',      label:'CDiag4',        color:'#f44' },
    { key:'HDiag0',      label:'HDiag0',        color:'#f84' },
    { key:'HDiag1',      label:'HDiag1',        color:'#f84' },
    { key:'HDiag2',      label:'HDiag2',        color:'#f84' },
    { key:'HDiag3',      label:'HDiag3',        color:'#f84' },
    { key:'HDiag4',      label:'HDiag4',        color:'#f84' },
    { key:'SysConfig',   label:'SysConfig',     color:'#888' },
    { key:'DIn',         label:'DIn RAW',       color:'#666' },
    { key:'DOut',        label:'DOut RAW',      color:'#666' },
    { key:'Rides',       label:'Rides',         color:'#888' },
  ];

  // Signal lookup by key
  const SIG_MAP = {};
  ALL_SIGNALS.forEach(s => SIG_MAP[s.key] = s);

  // ── Default configs per chart (6 charts) ─────────────────
  const CHART_DEFAULTS = [
    { id:'chartRPM',  title:'CHART 1', keys:['RPM','VS_KPH','CLT'] },
    { id:'chartFuel', title:'CHART 2', keys:['EGO_Corr','AFV','WUE'] },
    { id:'chartTPS',  title:'CHART 3', keys:['TPS_pct'] },
    { id:'chartSPK',  title:'CHART 4', keys:['spark1','spark2','pw1','pw2'] },
    { id:'chartBatt', title:'CHART 5', keys:['Batt_V'] },
    { id:'chartFlags',title:'CHART 6', keys:['fl_engine_run','fl_wot','fl_accel','fl_decel','fl_closed_loop','fl_rich','fl_learn','fl_hot','fl_kill','fl_fuel_cut','do_cel'] },
  ];

  // Load saved config from localStorage
  const LS_KEY = 'buell_chart_cfg_v1';
  let chartCfgs;
  try {
    const saved = localStorage.getItem(LS_KEY);
    chartCfgs = saved ? JSON.parse(saved) : CHART_DEFAULTS.map(d=>({id:d.id, keys:[...d.keys]}));
  } catch(e) {
    chartCfgs = CHART_DEFAULTS.map(d=>({id:d.id, keys:[...d.keys]}));
  }
  // Ensure all 6 charts exist in config
  CHART_DEFAULTS.forEach((def,i) => {
    if(!chartCfgs[i]) chartCfgs[i] = {id:def.id, keys:[...def.keys]};
  });

  function saveChartCfgs(){ try{ localStorage.setItem(LS_KEY, JSON.stringify(chartCfgs)); }catch(e){} }

  // Crosshair plugin (synced vertical line)
  const crosshairPlugin = {
    id: 'crosshair',
    afterDraw: (chart) => {
      if (chart.tooltip?._active?.length) {
        const ctx = chart.ctx;
        const x = chart.tooltip._active[0].element.x;
        
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x, chart.chartArea.top);
        ctx.lineTo(x, chart.chartArea.bottom);
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.setLineDash([3, 3]); // Dashed line
        ctx.stroke();
        ctx.restore();
      }
    }
  };


  // ── Base chart options — NO Y axes ───────────────────────
  const CHART_BASE = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode:'index', intersect:false },
    layout: { padding: 0 },
    plugins: {
      legend: { display:false },
      tooltip: {
        enabled: true,
        mode: 'index',
        intersect: false,
        position: 'nearest',
        backgroundColor: 'rgba(0, 0, 0, 0)',
        borderColor: 'transparent',
        borderWidth: 0,
        titleColor: '#aaa',
        titleFont: { family:'monospace', size:11 },
        bodyFont:  { family:'monospace', size:10 },
        padding: 0,
        xAlign: 'left',
        caretPadding: 15,
        external: function(context) {
          // Tooltip invisible, we only use data for the side panel
          const tooltip = context.tooltip;
          if (tooltip.dataPoints && tooltip.dataPoints.length > 0) {
            const t = tooltip.dataPoints[0].parsed.x;
            const panelTime = document.getElementById('panelTime');
            const panelItems = document.getElementById('panelItems');
            
            if (panelTime) panelTime.textContent = t.toFixed(2) + 's';
            
            if (panelItems) {
              panelItems.innerHTML = '';
              tooltip.dataPoints.forEach(dp => {
                const sig = SIG_MAP[dp.dataset._key];
                if (!sig) return;
                const v = dp.parsed.y;
                const div = document.createElement('div');
                div.style.cssText = 'display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;';
                div.innerHTML = '<div style="display:flex; align-items:center; gap:6px;">' +
                  '<div style="width:8px; height:8px; background:' + sig.color + '; border-radius:1px;"></div>' +
                  '<span style="color:#aaa; font-size:10px;">' + sig.label + '</span>' +
                '</div>' +
                '<span style="color:#fff; font-size:12px; font-weight:bold;">' + (v != null ? v.toFixed(1) : '--') + '</span>';
                panelItems.appendChild(div);
              });
            }
          }
        },
        callbacks: {
          title: () => '',  // Empty, we use the side panel
          label: () => ''   // Empty, we use the side panel
        }
      }
    },
    scales: {
      x: {
        type: 'linear',
        min: tFirst, max: tLast,
        ticks: { font:{family:'monospace',size:8}, color:'#444',
                 callback: v => v%60===0 ? (v+'s') : '',
                 maxTicksLimit: Math.ceil(durS/60)+1 },
        grid: { color:'rgba(255,255,255,.04)' }
      },
      y: { display:false }
    }
  };

  // Register crosshair plugin globally (vertical line)
  if (typeof Chart !== 'undefined') {
    Chart.register({
      id: 'crosshair',
      afterDraw: (chart) => {
        if (chart.tooltip && chart.tooltip._active && chart.tooltip._active.length) {
          const ctx = chart.ctx;
          const activePoint = chart.tooltip._active[0];
          const x = activePoint.element.x;
          const top = chart.chartArea.top;
          const bottom = chart.chartArea.bottom;
          
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(x, top);
          ctx.lineTo(x, bottom);
          ctx.lineWidth = 1;
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
          ctx.setLineDash([4, 4]);
          ctx.stroke();
          ctx.restore();
        }
      }
    });
  }

  // ── Build dataset from key — each signal gets its own hidden Y axis ──
  function makeDataset(key, rows, tFirst, tLast){
    const sig = SIG_MAP[key];
    if(!sig) return null;
    const data = rows.map(r=>({ x:r.time_elapsed_s, y: r[key]??null }));
    return {
      _key: key,
      label: sig.label,
      data,
      borderColor: sig.color,
      borderWidth: 1.5,
      borderDash: sig.dash || [],
      pointRadius: 0,
      fill: false,
      tension: 0,  // Straight lines between points (more accurate for tuning)
      yAxisID: 'y_'+key,
    };
  }

  // Build hidden Y scales — one per signal, auto-range from data
  function buildYScales(keys, rows){
    const scales = { x: CHART_BASE.scales.x };
    keys.forEach(key => {
      const vals = rows.map(r=>r[key]).filter(v=>v!=null&&!isNaN(v));
      const mn = vals.length ? Math.min(...vals) : 0;
      const mx = vals.length ? Math.max(...vals) : 1;
      const pad = (mx-mn)*0.1 || 1;
      scales['y_'+key] = {
        type: 'linear',
        display: false,
        min: mn - pad,
        max: mx + pad,
      };
    });
    // fallback empty scale
    if(!keys.length) scales['y__empty'] = { type:'linear', display:false };
    return scales;
  }

  // ── Render one chart ──────────────────────────────────────
  function renderChart(chartId, keys, chartKey){
    const canvas = document.getElementById(chartId);
    if(!canvas) return null;
    const ctx = canvas.getContext('2d');
    const datasets = keys.map(k=>makeDataset(k,rows,tFirst,tLast)).filter(Boolean);
    if(!datasets.length){
      datasets.push({ _key:'_empty', label:'—', data:[{x:tFirst,y:0},{x:tLast,y:0}],
                      borderColor:'#333', borderWidth:1, pointRadius:0, fill:false,
                      yAxisID:'y__empty' });
    }
    const scales = buildYScales(keys, rows);
    return new Chart(ctx, { type:'line', data:{ datasets },
      options:{ ...CHART_BASE, scales }
    });
  }

  // ── Build all 6 charts ────────────────────────────────────
  _charts.rpm   = renderChart('chartRPM',   chartCfgs[0].keys, 0);
  _charts.fuel  = renderChart('chartFuel',  chartCfgs[1].keys, 1);
  _charts.tps   = renderChart('chartTPS',   chartCfgs[2].keys, 2);
  _charts.spk   = renderChart('chartSPK',   chartCfgs[3].keys, 3);
  _charts.batt  = renderChart('chartBatt',  chartCfgs[4].keys, 4);
  _charts.flags = renderChart('chartFlags', chartCfgs[5].keys, 5);

  // ── Signal selector UI ────────────────────────────────────
  // Inject ⚙ button into each chart-wrap if not already present
  CHART_DEFAULTS.forEach((def, ci) => {
    const canvas = document.getElementById(def.id);
    if(!canvas) return;
    const wrap = canvas.closest('.chart-wrap');
    if(!wrap || wrap.querySelector('.chart-title .chart-cfg-btn')) return;

    const btn = document.createElement('button');
    btn.className = 'chart-cfg-btn btn';
    btn.textContent = '⚙';
    btn.onclick = (e) => { e.stopPropagation(); openChartCfg(ci, def, wrap, rows, tFirst, tLast, chartCfgs, saveChartCfgs); };
    const titleEl = wrap.querySelector('.chart-title');
    if(titleEl) titleEl.appendChild(btn);
    else wrap.appendChild(btn);
  });

  document.getElementById('graphLegend').style.display='flex';
}

// ── Chart signal selector panel ───────────────────────────────
function openChartCfg(ci, def, wrap, rows, tFirst, tLast, chartCfgs, saveChartCfgs){
  // Remove existing panel
  const existing = document.getElementById('chartCfgPanel');
  if(existing){ existing.remove(); if(existing._forChart===ci) return; }

  const ALL_SIGNALS_KEYS = [
    'RPM','VS_KPH','CLT','MAT','TPS_pct','Load','TPD',
    'EGO_Corr','AFV','WUE','IAT_Corr','Accel_Corr','Decel_Corr','WOT_Corr','Idle_Corr','OL_Corr','pw1','pw2',
    'spark1','spark2','veCurr1_RAW','veCurr2_RAW',
    'Batt_V','Fan_Duty_Pct',
    'O2_ADC','ETS_ADC','IAT_ADC','BAS_ADC','TPS_V',
    'VSS_Count','VSS_RPM_Ratio','Gear',
    'ttl_pct','cpu_pct','cpu_temp','mem_pct','buf_in',
    'fl_engine_run','fl_wot','fl_accel','fl_decel','fl_closed_loop','fl_rich','fl_learn',
    'fl_hot','fl_kill','fl_fuel_cut','fl_o2_active','fl_engine_stop','fl_ignition',
    'fl_cam_active','fl_immob',
    'do_coil1','do_coil2','do_inj1','do_inj2','do_fuel_pump','do_tacho','do_cel','do_fan',
    'di_cam','di_tacho_fb','di_vss','di_clutch','di_neutral','di_crank',
    'Flags0','Flags1','Flags2','Flags3','Flags4','Flags5','Flags6',
    'Unk63','Unk80','Unk81','Unk82',
    'CDiag0','CDiag1','CDiag2','CDiag3','CDiag4',
    'HDiag0','HDiag1','HDiag2','HDiag3','HDiag4',
    'SysConfig','DIn','DOut','Rides',
  ];

  const panel = document.createElement('div');
  panel.id = 'chartCfgPanel';
  panel._forChart = ci;
  panel.style.cssText = `
    position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
    background:#111114; border:1px solid #e8420a; border-radius:4px;
    padding:12px; z-index:1000; max-height:70vh; overflow-y:auto;
    min-width:220px; max-width:280px; font-family:monospace; font-size:9px;
  `;

  const selected = new Set(chartCfgs[ci].keys);

  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="color:#e8420a;font-size:10px">CHART ${ci+1} — SELECT SIGNALS</span>
      <span id="chartCfgClose" style="cursor:pointer;color:#666;padding:0 4px">✕</span>
    </div>
    <div style="margin-bottom:8px;display:flex;gap:4px">
      <button class="btn" style="font-size:8px;padding:2px 6px" id="chartCfgClear">CLEAR</button>
      <button class="btn" style="font-size:8px;padding:2px 6px" id="chartCfgApply">APPLY</button>
    </div>
    <div id="chartCfgList"></div>
  `;

  const list = panel.querySelector('#chartCfgList');
  ALL_SIGNALS_KEYS.forEach(key => {
    const row = document.createElement('label');
    row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:2px 0;cursor:pointer;';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = key;
    cb.checked = selected.has(key);
    cb.onchange = () => { if(cb.checked) selected.add(key); else selected.delete(key); };
    // Get signal color
    const sigColors = {
      RPM:'#e8420a',VS_KPH:'#4af',CLT:'#fa0',MAT:'#f90',TPS_pct:'#38f',Load:'#7af',
      EGO_Corr:'#0f8',AFV:'#ff0',WUE:'#f90',pw1:'#f90',pw2:'#fa6',
      spark1:'#a8f',spark2:'#c8f',Batt_V:'#7df',O2_ADC:'#0ff',
    };
    const col = sigColors[key] || '#888';
    const lbl = document.createElement('span');
    lbl.style.color = col;
    lbl.textContent = key;
    row.appendChild(cb);
    row.appendChild(lbl);
    list.appendChild(row);
  });

  panel.querySelector('#chartCfgClose').onclick = () => panel.remove();
  panel.querySelector('#chartCfgClear').onclick = () => {
    selected.clear();
    panel.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked=false);
  };
  panel.querySelector('#chartCfgApply').onclick = () => {
    chartCfgs[ci].keys = [...selected];
    saveChartCfgs();
    panel.remove();
    // Rebuild only this chart
    const chartKeys = ['rpm','fuel','tps','spk','batt','flags'];
    const chartIds  = ['chartRPM','chartFuel','chartTPS','chartSPK','chartBatt','chartFlags'];
    const ck = chartKeys[ci];
    if(_charts[ck]) try{ _charts[ck].destroy(); }catch(e){}
    const canvas = document.getElementById(chartIds[ci]);
    if(canvas){
      const SIG_MAP2 = {};
      const ALL_S = [
        {key:'RPM',color:'#e8420a'},{key:'VS_KPH',color:'#4af'},{key:'CLT',color:'#fa0'},
        {key:'MAT',color:'#f90'},{key:'TPS_pct',color:'#38f'},{key:'Load',color:'#7af'},
        {key:'TPD',color:'#68f'},{key:'EGO_Corr',color:'#0f8'},{key:'AFV',color:'#ff0'},
        {key:'WUE',color:'#f90',dash:[3,2]},{key:'IAT_Corr',color:'#4df'},
        {key:'Accel_Corr',color:'#8f8'},{key:'Decel_Corr',color:'#f88'},
        {key:'WOT_Corr',color:'#ff8'},{key:'Idle_Corr',color:'#aaf'},
        {key:'OL_Corr',color:'#faf'},{key:'pw1',color:'#f90'},{key:'pw2',color:'#fa6',dash:[3,2]},
        {key:'spark1',color:'#a8f'},{key:'spark2',color:'#c8f',dash:[3,2]},
        {key:'veCurr1_RAW',color:'#8ff'},{key:'veCurr2_RAW',color:'#aff',dash:[3,2]},
        {key:'Batt_V',color:'#7df'},{key:'Fan_Duty_Pct',color:'#f80'},
        {key:'O2_ADC',color:'#0ff'},{key:'ETS_ADC',color:'#f4f'},
        {key:'IAT_ADC',color:'#4ff'},{key:'BAS_ADC',color:'#ff4'},{key:'TPS_V',color:'#8af'},
        {key:'VSS_Count',color:'#4a8'},{key:'VSS_RPM_Ratio',color:'#6af'},{key:'Gear',color:'#a8f'},
        {key:'ttl_pct',color:'#0f4'},{key:'cpu_pct',color:'#f44'},{key:'cpu_temp',color:'#f84'},
        {key:'mem_pct',color:'#48f'},{key:'buf_in',color:'#888'},
      ];
      // flags + di/do
      ['fl_engine_run','fl_wot','fl_accel','fl_decel','fl_closed_loop','fl_rich','fl_learn',
       'fl_hot','fl_kill','fl_fuel_cut','fl_o2_active','fl_engine_stop','fl_ignition',
       'fl_cam_active','fl_immob','do_coil1','do_coil2','do_inj1','do_inj2','do_fuel_pump',
       'do_tacho','do_cel','do_fan','di_cam','di_tacho_fb','di_vss','di_clutch','di_neutral','di_crank',
       'Flags0','Flags1','Flags2','Flags3','Flags4','Flags5','Flags6',
       'Unk63','Unk80','Unk81','Unk82','CDiag0','CDiag1','CDiag2','CDiag3','CDiag4',
       'HDiag0','HDiag1','HDiag2','HDiag3','HDiag4','SysConfig','DIn','DOut','Rides'
      ].forEach(k=>ALL_S.push({key:k,color:'#666'}));
      ALL_S.forEach(s=>SIG_MAP2[s.key]=s);

      const t0 = window._lastBuildRows ? window._lastBuildRows[0]?.time_elapsed_s??0 : 0;
      const t1 = window._lastBuildRows ? window._lastBuildRows[window._lastBuildRows.length-1]?.time_elapsed_s??1 : 1;
      const durS2 = t1-t0||1;

      const datasets = chartCfgs[ci].keys.map(key=>{
        const sig=SIG_MAP2[key]; if(!sig) return null;
        return { _key:key, label:sig.label,
          data:(window._lastBuildRows||[]).map(r=>({x:r.time_elapsed_s,y:r[key]??null})),
          borderColor:sig.color, borderWidth:1.5, borderDash:sig.dash||[],
          pointRadius:0, fill:false, tension:0.1 };
      }).filter(Boolean);

      if(!datasets.length) datasets.push({
        _key:'_empty',label:'—',data:[{x:t0,y:0},{x:t1,y:0}],
        borderColor:'#333',borderWidth:1,pointRadius:0,fill:false
      });

      _charts[ck] = new Chart(canvas.getContext('2d'), { type:'line', data:{datasets},
        options:{
          animation:false, responsive:false, maintainAspectRatio:false,
          interaction:{mode:'index',intersect:false},
          layout:{padding:0},
          plugins:{
            legend:{display:false},
            tooltip:{
              enabled:true, backgroundColor:'rgba(0,0,0,0.0)',
              borderColor:'transparent', borderWidth:0,
              titleColor:'#aaa', titleFont:{family:'monospace',size:9},
              bodyFont:{family:'monospace',size:9},
              callbacks:{
                label:ctx=>`${ctx.dataset.label}: ${ctx.parsed.y!=null?ctx.parsed.y.toFixed(1):'--'}`,
                labelColor:ctx=>{ const s=SIG_MAP2[ctx.dataset._key]; return {borderColor:s?.color||'#fff',backgroundColor:s?.color||'#fff'}; }
              }
            }
          },
          scales:{
            x:{type:'linear',min:t0,max:t1,
               ticks:{font:{family:'monospace',size:8},color:'#444',callback:v=>v%60===0?(v+'s'):'',maxTicksLimit:Math.ceil(durS2/60)+1},
               grid:{color:'rgba(255,255,255,.04)'}},
            y:{display:false}
          }
        }
      });
    }
  };

  document.body.appendChild(panel);
}

// ── LOAD RIDES IN SELECTOR ────────────────────────────────────────
function initGraphPane(){
  if(!ridesCache || !ridesCache.length){
    loadRidesList().then(()=>_fillGraphSelect());
    return;
  }
  _fillGraphSelect();
}
function _fillGraphSelect(){
  const sel = document.getElementById('graphRideSelect');
  if(!ridesCache || !ridesCache.length){
    sel.innerHTML='<option value="">Sin rides guardados</option>';
    return;
  }
  sel.innerHTML = '<option value="">-- Selecciona un ride --</option>' +
    ridesCache.map(r=>{
      const dateStr = _rideDate(r);
      const label = r.filename.replace('_summary.json','').replace(/_/g,' ').toUpperCase();
      return `<option value="${r.filename}">${label} · ${dateStr} · ${Math.round(r.duration_s||0)}s · ${r.samples} muestras${(r.dtc_events&&r.dtc_events.length)?'  ⚠':''}</option>`;
    }).join('');
}

function _rideDate(r){
  // Use opened_utc (ride start) with fallback to closed_utc
  const iso = r.opened_utc || r.closed_utc || '';
  if(!iso) return '';
  try{
    const d = new Date(iso);
    const yy = String(d.getFullYear()).slice(2);
    const MM = String(d.getMonth()+1).padStart(2,'0');
    const dd = String(d.getDate()).padStart(2,'0');
    const hh = String(d.getHours()).padStart(2,'0');
    const mm = String(d.getMinutes()).padStart(2,'0');
    return yy+MM+dd+hh+mm;
  }catch(e){ return ''; }
}

// ── LOAD CSV AND RENDER ────────────────────────────────────────
async function loadGraphRide(directFile){
  const sel   = document.getElementById('graphRideSelect');
  const fname = directFile || sel.value;
  const status= document.getElementById('graphStatus');
  if(!fname){ status.textContent='Selecciona un ride'; return; }
  // Sync select if called from openRideGraph
  if(directFile && sel) sel.value = directFile;

  const csvName = fname.replace('_summary.json','.csv');
  const cleanName = fname.replace('_summary.json','').replace(/_/g,' ');
  const rideLabel = cleanName.toUpperCase();

  // Look up date in ridesCache
  const rideInfo = (ridesCache||[]).find(r=>r.filename===fname);
  const dateStr = rideInfo ? _rideDate(rideInfo) : '';

  status.textContent='Cargando...';
  const titleEl = document.getElementById('graphRideTitle');
  if(titleEl){ titleEl.textContent=''; titleEl.style.display='none'; }
  destroyCharts();
  document.getElementById('graphLegend').style.display='none';
  try{
    const resp = await fetch('/csv/'+csvName+'?t='+Date.now());
    if(!resp.ok) throw new Error('HTTP '+resp.status);
    const text = await resp.text();
    const rows = parseCSVtoRows(text);
    const dur = Math.round(rows[rows.length-1]?.time_elapsed_s||0);
    status.textContent = `${rows.length} muestras · ${dur}s`;
    if(titleEl){
      const datePart = dateStr ? `  <span style="color:#888;font-size:10px">${dateStr}</span>` : '';
      titleEl.innerHTML = '▶ ' + rideLabel + datePart;
      titleEl.style.display='block';
    }
    buildCharts(rows);
  }catch(e){
    status.textContent = 'Error: '+e;
  }
}


// ── KEEPALIVE ──────────────────────────────────────────────────────
async function doKeepalive(){
  try{
    await fetch('/keepalive',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const btn=document.querySelector('.btn.g');
    if(btn){const o=btn.textContent;btn.textContent='5 min activos';setTimeout(()=>btn.textContent=o,2500);}
  }catch(e){}
}


// ── SHUTDOWN ────────────────────────────────────────────────────────
function confirmShutdown(){
  const modal = document.createElement('div');
  modal.id = 'shutdownModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:200;display:flex;align-items:center;justify-content:center';
  modal.innerHTML = `
    <div style="background:var(--panel);border:1px solid var(--border);padding:20px;max-width:280px;width:90%;font-family:var(--mono)">
      <div style="font-size:11px;color:var(--accent);letter-spacing:2px;margin-bottom:12px">電源關閉</div>
      <div style="font-size:12px;line-height:1.7;margin-bottom:16px;color:var(--fg)">
        Se cerrará el ride activo y la Pi se apagará.<br>
        <span style="font-size:9px;color:var(--dim)">Asegúrate de estar detenido.</span>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn" style="flex:1;padding:10px" onclick="document.getElementById('shutdownModal').remove()">取消</button>
        <button class="btn-danger" style="flex:1;margin:0;padding:10px" onclick="doShutdown()">關閉</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
}
async function doShutdown(){
  trackUsage('btn_poweroff');
  const m = document.getElementById('shutdownModal');
  if(m) m.remove();
  try{await fetch('/shutdown',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch(e){}
  document.body.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100dvh;font-family:var(--mono);font-size:12px;color:var(--dim);background:#0a0a0b">Apagando Pi...</div>';
}

// ── ECU CONFIG (EEPROM) ───────────────────────────────────────────
let ecuPanelOpen = true;
function toggleEcu(){
  ecuPanelOpen = !ecuPanelOpen;
  document.getElementById('ecuPanel').style.display = ecuPanelOpen ? '' : 'none';
  document.getElementById('ecuToggleIcon').innerHTML = ecuPanelOpen ? '&#9660;' : '&#9654;';
}
function ecuRow(label, val, units, color){
  const c = color || '#ccc';
  return `<div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;padding:3px 0;border-bottom:1px solid #1e1e1e"><span style="color:var(--dim)">${label}</span><span style="color:${c};font-weight:600">${val} <span style="color:var(--dim);font-weight:400">${units}</span></span></div>`;
}
async function loadEepromParams(){
  const container = document.getElementById('eepromParamsTable');
  if(!container) return;
  container.textContent = 'Cargando...';
  try {
    const resp = await fetch('/eeprom');
    const data = await resp.json();
    if(!data || data.error){ container.textContent = data?.error || 'Sin datos - Conecta la ECU'; return; }
    const params = Object.values(data);
    if(!params.length){ container.textContent = 'Sin datos'; return; }
    // Group by category using remark as fallback
    const groups = {};
    for(const p of params){
      const cat = p.remark ? p.remark.split(' ').slice(0,3).join(' ') : 'General';
      if(!groups[cat]) groups[cat] = [];
      groups[cat].push(p);
    }
    let html = '';
    for(const [cat, items] of Object.entries(groups)){
      html += `<div style="color:var(--accent2);margin:8px 0 3px;font-size:8px;letter-spacing:.1em">${cat.toUpperCase()}</div>`;
      for(const p of items){
        const val = typeof p.value === 'number' ? p.value.toFixed(p.value%1===0?0:1) : p.value;
        const units = p.units ? ' '+p.units : '';
        html += `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--border)">
          <span style="color:var(--dim);max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${p.remark||''}">${p.name}</span>
          <span style="color:#fff;font-weight:700">${val}${units}</span>
        </div>`;
      }
    }
    container.innerHTML = html;
  } catch(e){ container.textContent = 'Error: '+e; }
}

async function loadEcu(){
  try{
    const d = await (await fetch('/eeprom?t='+Date.now())).json();
    if(!d || Object.keys(d).length===0){
      document.getElementById('ecuVersion').textContent='No disponible (llave ON y reiniciar)'; return;
    }
    document.getElementById('ecuVersion').textContent='OK';
    const tempMap=[['Fan ON','KTemp_Fan_On','#ccc'],['Fan OFF','KTemp_Fan_Off','#ccc'],
      ['CEL ON','KTemp_CEL_Flash_Hi','#fa0'],['Soft limit','KTemp_Soft_Hi','#ff0'],
      ['Hard limit','KTemp_Hard_Hi','#fa0'],['Kill limit','KTemp_Kill_Hi','#f55'],
      ['RPM min soft','KTemp_RPM_Soft','#8af'],['RPM min hard','KTemp_RPM_Hard','#8af'],
      ['TPS min soft','KTemp_TP_Soft','#8af'],['TPS min hard','KTemp_TP_Hard','#8af']];
    let h='';
    for(const [lbl,k,col] of tempMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(0),d[k].units,col);}
    document.getElementById('ecuTempRows').innerHTML=h;
    const rpmMap=[['Soft trigger','KRPM_Soft_Hi','#ff0'],['Soft release','KRPM_Soft_Lo','#ff0'],
      ['Hard trigger','KRPM_Hard_Hi','#fa0'],['Hard release','KRPM_Hard_Lo','#fa0'],
      ['Kill trigger','KRPM_Kill_Hi','#f55'],['Kill release','KRPM_Kill_Lo','#f55']];
    h='';
    for(const [lbl,k,col] of rpmMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(0),d[k].units,col);}
    document.getElementById('ecuRpmRows').innerHTML=h;
    const egoMap=[['O2 target','KO2_Midpoint','#6ef'],['O2 rich','KO2_Rich','#f88'],
      ['O2 lean','KO2_Lean','#8f8'],['CL min RPM','KO2_Min_RPM','#8af'],
      ['EGO max','KFBFuel_Max','#6ef'],['EGO min','KFBFuel_Min','#6ef'],
      ['AFV max','KLFuel_Max','#6ef'],['AFV min','KLFuel_Min','#6ef']];
    h='';
    for(const [lbl,k,col] of egoMap){if(d[k]) h+=ecuRow(lbl,d[k].val.toFixed(3),d[k].units,col);}
    document.getElementById('ecuEgoRows').innerHTML=h;
  }catch(e){ document.getElementById('ecuVersion').textContent='Error: '+e.message; }
}

// VSS CALIBRATION
let vssCal={cpkm25:1368};
async function doReconnect(){
  trackUsage('btn_reconnect_ecu');
  try{
    const r=await fetch('/reconnect',{method:'POST',
      headers:{'Content-Type':'application/json'},body:'{}'});
    const d=await r.json();
    alert(d.msg||'Reconexión solicitada — espera unos segundos');
  }catch(e){alert('Error al reconectar: '+e);}
}

async function doRestartLogger(){
  trackUsage('btn_restart_logger');
  try{
    await fetch('/restart_logger',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    alert('Logger reiniciando... reconecta en ~10 segundos');
  }catch(e){ /* normal — el proceso muere antes de responder */ }
}



async function gitPull() {
  const status = document.getElementById('gitPullStatus');
  status.textContent = 'Ejecutando git pull...';
  status.style.color = 'var(--dim)';
  try {
    const res = await fetch('/git_pull', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      if (data.changes) {
        status.innerHTML = '✅ Git pull completado. Hubo cambios.<br>Reinicia el logger para aplicarlos.';
      } else {
        status.textContent = '✅ Ya estaba actualizado.';
      }
      status.style.color = 'var(--green)';
    } else {
      status.textContent = '❌ Error: ' + (data.error || 'desconocido');
      status.style.color = 'var(--red)';
    }
  } catch (e) {
    status.textContent = 'Error de red: ' + e;
    status.style.color = 'var(--red)';
  }
}


// Load cal on startup (not only on tab open)
document.addEventListener("DOMContentLoaded", ()=>{ buildCobertGrid(); renderCobertLegend(); fetchLive(); setInterval(pollCobertGrid, 1000); });


// ── Error Log Viewer ──
function openErrorLog(session,ride_num){
  document.getElementById('errLogModalTitle').textContent=`ERROR LOG — ${session} ride_${String(ride_num).padStart(3,'0')}`;
  document.getElementById('errLogContent').innerHTML='Cargando...';
  document.getElementById('errorLogModal').style.display='flex';
  fetch(`/errorlog/${session}/${String(ride_num).padStart(3,'0')}?t=${Date.now()}`)
    .then(r=>r.json()).then(d=>{
      if(!d.events || d.events.length===0){
        document.getElementById('errLogContent').innerHTML='<div style="color:var(--dim);padding:12px">No se encontraron eventos de error para este ride.</div>';
        return;
      }
      // Summary table
      const sumKeys=Object.keys(d.summary).filter(k=>k!=='total_events'&&d.summary[k]>0);
      let html='<div style="margin-bottom:10px;background:#111;border:1px solid var(--border);border-radius:3px;padding:8px">';
      html+='<div style="color:var(--dim);font-size:8px;letter-spacing:.1em;margin-bottom:4px">RESUMEN</div>';
      html+='<table style="width:100%;border-collapse:collapse">';
      for(let i=0;i<sumKeys.length;i++){
        const k=sumKeys[i];
        const label=k.replace(/_/g,' ');
        html+=`<tr><td style="padding:1px 4px;color:#999">${label}</td><td style="padding:1px 4px;text-align:right;color:#f90">${d.summary[k]}</td></tr>`;
      }
      html+=`<tr><td style="padding:1px 4px;color:#999;border-top:1px solid var(--border)">total eventos</td><td style="padding:1px 4px;text-align:right;color:#fff;border-top:1px solid var(--border)">${d.events.length}</td></tr>`;
      html+='</table></div>';

      // Events list
      html+='<div style="color:var(--dim);font-size:8px;letter-spacing:.1em;margin-bottom:4px">EVENTOS</div>';
      for(let i=0;i<d.events.length;i++){
        const ev=d.events[i];
        const icon=ev.type==='reconnect'?'⚡':'⏱';
        let ctxHtml='';
        if(ev.ctx){
          const parts=[];
          if(ev.ctx.rpm!==undefined) parts.push('RPM: '+ev.ctx.rpm);
          if(ev.ctx.clt!==undefined) parts.push('CLT: '+ev.ctx.clt+'°');
          if(ev.ctx.tps!==undefined) parts.push('TPS: '+ev.ctx.tps+'%');
          if(ev.ctx.vss!==undefined) parts.push('VSS: '+ev.ctx.vss);
          if(ev.ctx.batt!==undefined) parts.push('BATT: '+ev.ctx.batt.toFixed(1)+'V');
          if(ev.ctx.ego!==undefined) parts.push('EGO: '+ev.ctx.ego.toFixed(1));
          if(ev.ctx.afv!==undefined) parts.push('AFV: '+ev.ctx.afv.toFixed(2));
          if(parts.length) ctxHtml='<div style="color:#888;font-size:9px;padding-left:4px">'+parts.join('  ')+'</div>';
        }
        let extra='';
        if(ev.lost_s) extra+=' <span style="color:#f66">perdida '+ev.lost_s.toFixed(1)+'s</span>';
        if(ev.trigger) extra+=' <span style="color:#6af">trigger: '+ev.trigger+'</span>';
        const timeStr=Math.floor(ev.t/60)+':'+String(Math.floor(ev.t%60)).padStart(2,'0');
        html+=`<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">`;
        html+=`<div>${icon} <span style="color:#aaa">t=${timeStr}</span> <span style="color:${ev.type==='reconnect'?'#6af':'#f90'}">${ev.type}</span>${extra}</div>`;
        html+=ctxHtml;
        html+=`</div>`;
      }
      document.getElementById('errLogContent').innerHTML=html;
    }).catch(function(e){
      document.getElementById('errLogContent').innerHTML='<div style="color:#f66;padding:12px">Error al cargar: '+e.message+'</div>';
    });
}
function closeErrorLog(){
  document.getElementById('errorLogModal').style.display='none';
}

// ── EEPROM / MSQ Download ──
function _dlFile(url, filename) {
  var a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(function(){
    document.body.removeChild(a);
    if (url.startsWith('blob:')) URL.revokeObjectURL(url);
  }, 100);
}
function downloadEeprom(session) {
  var url = '/eeprom/download' + (session ? '?session=' + session : '');
  fetch(url).then(function(r){
    if (!r.ok) { return r.json().then(function(d){ alert('Error: ' + (d.error || r.status)); }); }
    return r.blob().then(function(b){
      _dlFile(URL.createObjectURL(b), 'eeprom_' + (session || 'current') + '.bin');
    });
  }).catch(function(e){ alert('Download error: ' + e.message); });
}
function downloadMsq(session) {
  var url = '/msq/download' + (session ? '?session=' + session : '');
  fetch(url).then(function(r){
    if (!r.ok) { return r.json().then(function(d){ alert('Error: ' + (d.error || r.status)); }); }
    return r.blob().then(function(b){
      _dlFile(URL.createObjectURL(b), 'suggested_' + (session || 'current') + '.msq');
    });
  }).catch(function(e){ alert('Download error: ' + e.message); });
}
