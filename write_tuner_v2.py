html = r'''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Buell Tuner Studio</title>
<style>
:root{--bg:#0a0a0b;--p:#111114;--bd:#1e1e24;--ac:#e8420a;--a2:#f5a623;--bl:#3d9eff;--dm:#555;--tx:#c8c8cc;--rd:#ff4444;--mn:monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--tx);font-family:sans-serif;font-size:13px;min-height:100dvh;display:flex;flex-direction:column}
.hd{background:var(--p);border-bottom:2px solid var(--ac);padding:8px 12px;display:flex;justify-content:space-between;align-items:center}
.hd h1{font-size:16px;font-weight:900;color:#fff}
.hd a{font-family:var(--mn);font-size:9px;color:var(--dm);text-decoration:none;border:1px solid var(--bd);padding:3px 6px;border-radius:2px}
.hd a:hover{color:var(--bl);border-color:var(--bl)}
.w{flex:1;padding:10px;display:flex;flex-direction:column;gap:8px;overflow:hidden}
.cd{background:var(--p);border:1px solid var(--bd);padding:10px;border-radius:4px}
.cd h2{font-family:var(--mn);font-size:9px;color:var(--ac);letter-spacing:.1em;margin-bottom:6px;text-transform:uppercase}
.ct{display:flex;gap:8px}
.cg{flex:1;display:flex;flex-direction:column;gap:2px}
.cg label{font-family:var(--mn);font-size:8px;color:var(--a2);text-transform:uppercase;letter-spacing:.08em}
.cg select{background:var(--bg);border:1px solid var(--bd);color:#fff;font-family:var(--mn);font-size:11px;padding:5px;border-radius:2px}
#st{font-family:var(--mn);font-size:9px;color:var(--dm)}
.tabs{display:flex;gap:0;background:var(--p);border:1px solid var(--bd);border-radius:4px;overflow:hidden;flex-shrink:0}
.tab{flex:1;padding:6px 2px;font-family:var(--mn);font-size:8px;font-weight:700;color:var(--dm);background:transparent;border:none;cursor:pointer;letter-spacing:.04em;text-transform:uppercase;border-right:1px solid var(--bd)}
.tab:last-child{border-right:none}
.tab.on{background:var(--ac);color:#fff}
.ps{overflow-x:auto;overflow-y:auto;background:var(--p);border:1px solid var(--bd);border-radius:4px;flex:1}
.pi{display:inline-flex;min-width:100%}
.tw{display:flex;flex-direction:column;flex-shrink:0}
.tw:first-child table{border-right:2px solid var(--a2)}
.tw:last-child table{border-left:2px solid var(--a2)}
table.v{border-collapse:collapse;font-family:var(--mn);white-space:nowrap}
table.v caption{font-size:7px;color:var(--ac);padding:2px 4px;text-align:left;letter-spacing:.1em;font-weight:700}
table.v th{font-size:6px;color:var(--dm);padding:1px 2px;text-align:center;min-width:24px}
table.v th.r{text-align:right;min-width:26px;padding-right:3px}
table.v td{width:28px;height:18px;border:1px solid rgba(255,255,255,.03);text-align:center;vertical-align:middle;font-size:7px;font-weight:700;color:#bbb}
.dp{color:var(--rd)}
.dn{color:var(--bl)}
.dz{color:#333}
.dpp{background:rgba(255,50,50,.18);color:var(--rd)}
.dnn{background:rgba(50,130,255,.18);color:var(--bl)}
.dzz{background:rgba(255,255,255,.01);color:#333}
</style></head><body>
<div class="hd"><h1>TUNER STUDIO</h1><a href="/">Dashboard</a></div>
<div class="w">
<div class="cd">
<h2>Comparador de Sesiones</h2>
<div class="ct">
<div class="cg"><label>Base</label><select id="sB"><option value="">--</option></select></div>
<div class="cg"><label>Modificada</label><select id="sM"><option value="">--</option></select></div>
</div>
<div id="st">Cargando sesiones...</div>
</div>
<div class="tabs" id="tabs">
<button class="tab on" data-m="fuel_front">FUEL FRONT</button>
<button class="tab" data-m="fuel_rear">FUEL REAR</button>
<button class="tab" data-m="spark_front">SPARK FRONT</button>
<button class="tab" data-m="spark_rear">SPARK REAR</button>
</div>
<div class="ps"><div class="pi" id="pw"></div></div>
</div>
<script>
var mB=null,mM=null,cur='fuel_front';
var AX={fuel_front:['fuel_rpm','fuel_load'],fuel_rear:['fuel_rpm','fuel_load'],spark_front:['spark_rpm','spark_load'],spark_rear:['spark_rpm','spark_load']};

async function init(){
  try{
    var r=await fetch('/tuner/sessions');
    var d=await r.json();
    if(!d.sessions||!d.sessions.length){st('No hay sesiones');return}
    var ok=[];
    for(var i=0;i<d.sessions.length;i++){
      var s=d.sessions[i];
      try{var mr=await fetch('/tuner/maps?session='+s.id);var md=await mr.json();if(md&&md.fuel_front)ok.push(s)}catch(e){}
    }
    if(!ok.length){st('Sin mapas legibles');return}
    var o='<option value="">--</option>';
    for(var i=0;i<ok.length;i++){var s=ok[i];o+='<option value="'+s.id+'">'+s.id+' ('+s.version+') '+s.rides+'r</option>'}
    document.getElementById('sB').innerHTML=o;
    document.getElementById('sM').innerHTML=o;
    st(ok.length+' sesiones validas');
  }catch(e){st('Error: '+e.message)}
}

function st(t){document.getElementById('st').textContent=t}

async function load(t){
  var id=document.getElementById(t==='base'?'sB':'sM').value;
  if(!id)return;
  st('Cargando '+id+'...');
  try{
    var r=await fetch('/tuner/maps?session='+id);
    var d=await r.json();
    if(!d||!d.fuel_front){st('Error: '+(d&&d.error||'sin mapa'));return}
    if(t==='base')mB=d;else mM=d;
    render();
  }catch(e){st('Error al cargar')}
}

function render(){
  if(!mB||!mM)return;
  var mk=cur;
  var ak=AX[mk];
  var bD=mB[mk],mD=mM[mk];
  if(!bD||!mD){document.getElementById('pw').innerHTML='<p style="padding:16px;color:var(--dm)">Mapa no disponible para esta sesion</p>';return}
  var rpm=mB.axes[ak[0]],lod=mB.axes[ak[1]];
  var rows=lod.length,cols=rpm.length;
  if(bD.length!==mD.length){st('Dimensiones diferentes entre sesiones');return}

  var mx=0;
  for(var i=0;i<rows;i++)for(var j=0;j<cols;j++){var v=Math.abs(mD[i][j]-bD[i][j]);if(v>mx)mx=v}

  function hdr(){var h='<tr><th></th>';for(var j=0;j<cols;j++)h+='<th>'+rpm[j]+'</th>';return h+'</tr>'}
  function tbl(data,cap){
    var h='<table class="v"><caption>'+cap+'</caption>'+hdr();
    for(var i=0;i<rows;i++){
      h+='<tr><th class="r">'+lod[i]+'</th>';
      for(var j=0;j<cols;j++) h+='<td>'+data[i][j].toFixed(0)+'</td>';
      h+='</tr>';
    }
    return h+'</table>';
  }
  function delta(){
    var h='<table class="v"><caption>DELTA</caption>'+hdr();
    for(var i=0;i<rows;i++){
      h+='<tr><th class="r">'+lod[i]+'</th>';
      for(var j=0;j<cols;j++){
        var d=mD[i][j]-bD[i][j],ad=Math.abs(d),cls='dzz',txt='\u00B7';
        if(ad>0.3){
          txt=(d>0?'+':'')+d.toFixed(1);
          var ratio=mx>0?ad/mx:0;
          cls=ratio>0.5?(d>0?'dpp':'dnn'):(d>0?'dp':'dn');
        }
        h+='<td class="'+cls+'">'+txt+'</td>';
      }
      h+='</tr>';
    }
    return h+'</table>';
  }

  document.getElementById('pw').innerHTML=
    '<div class="tw">'+tbl(bD,'BASE')+'</div>'+
    '<div class="tw">'+delta()+'</div>'+
    '<div class="tw">'+tbl(mD,'MOD')+'</div>';

  st(mk.toUpperCase().replace('_',' ')+' \u2014 Delta max: '+mx.toFixed(1));
}

document.getElementById('sB').onchange=function(){load('base')};
document.getElementById('sM').onchange=function(){load('mod')};
document.getElementById('tabs').onclick=function(e){
  var b=e.target.closest('.tab');
  if(!b)return;
  var all=document.querySelectorAll('.tab');
  for(var i=0;i<all.length;i++)all[i].classList.remove('on');
  b.classList.add('on');
  cur=b.dataset.m;
  render();
};
init();
</script></body></html>'''
with open('web/templates/tuner.html','w') as f:
    f.write(html)
print('tuner.html v2 escrito correctamente')
