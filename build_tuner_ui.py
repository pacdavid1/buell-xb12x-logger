filepath = 'web/templates/tuner.html'
with open(filepath, 'r') as f:
    html = f.read()

# Reemplazar el cuerpo de la página por el comparador real
old_body = """<div class="content">
  <div class="card">
    <h2>Módulo de Análisis y Modificación</h2>
    <p>
      Aquí se procesarán los mapas de VE, se aplicará el algoritmo 
      <strong>Delta Blend + Smoothing</strong> y se generarán los archivos <code>.msq</code> 
      para TunerStudio sin escalones ni aplanamiento no deseado.
    </p>
    <p>
      Funcionará 100% offline, cargando los <code>tuning_report.json</code> 
      generados por el Logger durante los rides.
    </p>
    <div class="badge">PRÓXIMAMENTE: Motor de Smoothing V3 + Visor de Deltas</div>
  </div>
</div>"""

new_body = """<div class="content" style="align-items:stretch;justify-content:flex-start;padding:15px">
  <div class="card">
    <h2>Comparador de Sesiones (Mapa VE Frontal)</h2>
    <p style="text-align:left">
      Selecciona dos sesiones para ver la diferencia exacta entre sus mapas de VE. 
      <span style="color:var(--red)">Rojo</span> = Más combustible (Enriquecido) · 
      <span style="color:var(--blue)">Azul</span> = Menos combustible (Empobrecido) · 
      <span style="color:var(--dim)">Gris</span> = Sin cambios.
    </p>
    <div class="controls">
      <div class="ctrl-group">
        <label>BASE (Original)</label>
        <select id="selBase" onchange="loadSession('base')"><option value="">Cargando sesiones...</option></select>
      </div>
      <div class="ctrl-group">
        <label>MODIFICADA</label>
        <select id="selMod" onchange="loadSession('mod')"><option value="">Cargando sesiones...</option></select>
      </div>
    </div>
    <div id="diffStatus" style="font-family:var(--mono);font-size:10px;color:var(--dim);margin:10px 0">Esperando selección de sesiones...</div>
  </div>
  
  <div class="grid-wrap">
    <table class="veg" id="diffGrid"></table>
  </div>
</div>

<style>
.controls { display:flex; gap:10px; margin-bottom:15px; width:100% }
.ctrl-group { flex:1; display:flex; flex-direction:column; gap:4px }
.ctrl-group label { font-family:var(--mono); font-size:9px; color:var(--accent2); text-transform:uppercase; letter-spacing:.1em }
.ctrl-group select { background:var(--bg); border:1px solid var(--border); color:#fff; font-family:var(--mono); font-size:11px; padding:8px; border-radius:2px }
table.veg { border-collapse:collapse; font-family:var(--mono); white-space:nowrap }
table.veg th { font-size:7px; color:var(--dim); padding:2px 3px; text-align:center; min-width:28px }
table.veg th.rh { text-align:right; min-width:26px; padding-right:4px }
table.veg td { width:40px; height:28px; border:1px solid rgba(255,255,255,0.04); text-align:center; vertical-align:middle; font-size:9px; font-weight:700; color:#fff }
.grid-wrap { overflow-x:auto; width:100%; background:var(--panel); border:1px solid var(--border); border-radius:4px; padding:8px }
</style>

<script>
const RPM_BINS = [0,800,1000,1350,1900,2400,2900,3400,4000,5000,6000,7000,8000];
const TPS_BINS = [10,15,20,30,40,50,60,80,100,125,175,255];
let mapBase = null, mapMod = null;

async function init() {
  try {
    const r = await fetch('/tuner/sessions');
    const d = await r.json();
    const opts = d.sessions.map(s => `<option value="${s.id}">${s.id} (${s.version}) - ${s.rides} rides</option>`).join('');
    document.getElementById('selBase').innerHTML = opts;
    document.getElementById('selMod').innerHTML = opts;
  } catch(e) { console.error(e); }
}

async function loadSession(type) {
  const selId = type === 'base' ? 'selBase' : 'selMod';
  const sess = document.getElementById(selId).value;
  if(!sess) return;
  
  const st = document.getElementById('diffStatus');
  st.textContent = `Cargando mapa de ${sess}...`;
  
  try {
    const r = await fetch(`/tuner/maps?session=${sess}`);
    const d = await r.json();
    if(!d || !d.fuel_front) { st.textContent = 'Error: No se encontró mapa fuel_front'; return; }
    
    if(type === 'base') mapBase = d.fuel_front;
    else mapMod = d.fuel_front;
    
    renderDiff();
  } catch(e) { st.textContent = 'Error al cargar'; console.error(e); }
}

function deltaColor(val) {
  if (val > 0) { const i = Math.min(Math.abs(val)/5, 1); return `rgba(255, 50, 50, ${0.3 + i*0.6})`; }
  if (val < 0) { const i = Math.min(Math.abs(val)/5, 1); return `rgba(50, 150, 255, ${0.3 + i*0.6})`; }
  return '#1a1a1e';
}

function renderDiff() {
  const grid = document.getElementById('diffGrid');
  if(!mapBase || !mapMod) return;
  
  document.getElementById('diffStatus').textContent = `Comparando sesiones...`;
  
  let html = '<thead><tr><th class="rh">TPS\\RPM</th>';
  RPM_BINS.forEach(r => html += `<th>${r>=1000?(r/1000)+'k':r}</th>`);
  html += '</tr></thead><tbody>';
  
  for(let li=TPS_BINS.length-1; li>=0; li--) {
    html += `<tr><th class="rh">${TPS_BINS[li]}</th>`;
    for(let ri=0; ri<RPM_BINS.length; ri++) {
      const val = (mapMod[li][ri] || 0) - (mapBase[li][ri] || 0);
      const bg = deltaColor(val);
      const txt = val === 0 ? '-' : (val > 0 ? '+' : '') + val;
      html += `<td style="background:${bg}">${txt}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody>';
  grid.innerHTML = html;
  document.getElementById('diffStatus').textContent = 'Diferencia calculada. (Rojo = +VE, Azul = -VE)';
}

window.addEventListener('DOMContentLoaded', init);
</script>"""

if old_body in html:
    html = html.replace(old_body, new_body)
    print("EXITO: Interfaz de Comparador creada en tuner.html")
else:
    print("AVISO: No se encontró el cuerpo de tuner.html")

with open(filepath, 'w') as f:
    f.write(html)
