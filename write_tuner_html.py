h='''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Buell Tuner Studio</title>
<style>
:root{--bg:#0a0a0b;--p:#111114;--bd:#1e1e24;--ac:#e8420a;--a2:#f5a623;--bl:#3d9eff;--dm:#555;--tx:#c8c8cc;--rd:#ff4444;--mn:monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--tx);font-family:sans-serif;font-size:14px;min-height:100dvh;display:flex;flex-direction:column}
.hd{background:var(--p);border-bottom:2px solid var(--ac);padding:10px 15px;display:flex;justify-content:space-between;align-items:center}
.hd h1{font-size:17px;font-weight:900;color:#fff}
.hd a{font-family:var(--mn);font-size:10px;color:var(--dm);text-decoration:none;border:1px solid var(--bd);padding:4px 8px;border-radius:2px}
.hd a:hover{color:var(--bl);border-color:var(--bl)}
.w{flex:1;padding:12px;display:flex;flex-direction:column;gap:10px;overflow-x:hidden}
.cd{background:var(--p);border:1px solid var(--bd);padding:16px;border-radius:4px}
.cd h2{font-family:var(--mn);font-size:10px;color:var(--ac);letter-spacing:.12em;margin-bottom:8px;text-transform:uppercase}
.cd p{font-family:var(--mn);font-size:10px;color:var(--dm);line-height:1.5}
.ct{display:flex;gap:8px;margin-top:8px}
.cg{flex:1;display:flex;flex-direction:column;gap:2px}
.cg label{font-family:var(--mn);font-size:8px;color:var(--a2);text-transform:uppercase;letter-spacing:.1em}
.cg select{background:var(--bg);border:1px solid var(--bd);color:#fff;font-family:var(--mn);font-size:11px;padding:6px;border-radius:2px}
#st{font-family:var(--mn);font-size:10px;color:var(--dm);padding:2px 4px}
.gw{overflow-x:auto;background:var(--p);border:1px solid var(--bd);border-radius:4px;padding:6px}
table.v{border-collapse:collapse;font-family:var(--mn);white-space:nowrap}
table.v th{font-size:6px;color:var(--dm);padding:1px 2px;text-align:center;min-width:24px}
table.v th.r{text-align:right;min-width:30px;padding-right:3px}
table.v td{width:36px;height:24px;border:1px solid rgba(255,255,255,.03);text-align:center;vertical-align:middle;font-size:8px;font-weight:700;color:#fff}
</style></head><body>
<div class="hd"><h1>TUNER STUDIO</h1><a href="/">Dashboard</a></div>
<div class="w">
<div class="cd">
<h2>Comparador VE Frontal</h2>
<p><span style="color:var(--rd)">Rojo</span> = +VE (enriquecido) · <span style="color:var(--bl)">Azul</span> = -VE (empobrecido) · Gris = sin cambio</p>
<div class="ct">
<div class="cg"><label>Base (original)</label><select id="sB"><option value="">--</option></select></div>
<div class="cg"><label>Modificada</label><select id="sM"><option value="">--</option></select></div>
</div>
<div id="st">Cargando sesiones...</div>
</div>
<div class="gw"><table class="v" id="gr"></table></div>
</div>
<script>
let mB=null,mM=null;
async function init(){
  try{
    const r=await fetch('/tuner/sessions');
    const d=await r.json();
    if(!d.sessions||!d.sessions.length){document.getElementById('st').textContent='No hay sesiones';return}
    const ok=[];
    for(const s of d.sessions){
      try{const mr=await fetch('/tuner/maps?session='+s.id);const md=await mr.json();if(md&&md.fuel_front)ok.push(s)}catch(e){}
    }
    if(!ok.length){document.getElementById('st').textContent='Ninguna sesion tiene mapas legibles';return}
    const o='<option value="">--</option>'+ok.map(s=>'<option value="'+s.id+'">'+s.id+' ('+s.version+') '+s.rides+' rides</option>').join('');
    document.getElementById('sB').innerHTML=o;
    document.getElementById('sM').innerHTML=o;
    document.getElementById('st').textContent=ok.length+' sesiones validas';
  }catch(e){document.getElementById('st').textContent='Error: '+e.message}
}
async function load(t){
  const id=document.getElementById(t==='base'?'sB':'sM').value;
  if(!id)return;
  document.getElementById('st').textContent='Cargando '+id+'...';
  try{
    const r=await fetch('/tuner/maps?session='+id);
    const d=await r.json();
    if(!d||!d.fuel_front){document.getElementById('st').textContent='Error: '+(d&&d.error||'sin mapa');return}
    if(t==='base')mB=d;else mM=d;
    render();
  }catch(e){document.getElementById('st').textContent='Error al cargar'}
}
function render(){
  if(!mB||!mM)return;
  const b=mB.fuel_front,m=mM.fuel_front,rb=mB.rpm_bins,rm=mM.rpm_bins,tb=mB.tps_bins,tm=mM.tps_bins;
  if(rb.length!==rm.length||tb.length!==tm.length){document.getElementById('st').textContent='Dimensiones diferentes';return}
  let h='<tr><th></th>';
  for(let j=0;j<rb.length;j++)h+='<th>'+rb[j]+'</th>';
  h+='</tr>';
  for(let i=0;i<tb.length;i++){
    h+='<tr><th class="r">'+tb[i]+'</th>';
    for(let j=0;j<rb.length;j++){
      const d=m[i][j]-b[i][j];
      let bg='rgba(255,255,255,.02)',c='#555';
      if(d>0.3){const a=Math.min(d/6,.75);bg='rgba(255,50,50,'+a+')';c='#fff'}
      else if(d<-0.3){const a=Math.min(Math.abs(d)/6,.75);bg='rgba(50,130,255,'+a+')';c='#fff'}
      h+='<td style="background:'+bg+';color:'+c+'">'+(Math.abs(d)<0.3?'·':(d>0?'+':'')+d.toFixed(1))+'</td>';
    }
    h+='</tr>';
  }
  document.getElementById('gr').innerHTML=h;
  document.getElementById('st').textContent='Delta lista';
}
document.getElementById('sB').onchange=function(){load('base')};
document.getElementById('sM').onchange=function(){load('mod')};
init();
</script></body></html>'''
with open('web/templates/tuner.html','w') as f: f.write(h)
print('tuner.html reescrito correctamente')
