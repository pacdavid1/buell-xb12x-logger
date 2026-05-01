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
.ps{overflow:auto;background:var(--p);border:1px solid var(--bd);border-radius:4px;flex:1;min-height:0}
.pi{display:inline-flex;min-width:100%;gap:0}
.tw{display:flex;flex-direction:column;flex-shrink:0;min-width:410px}
.tw.tb table{border-right:2px solid var(--a2)}
.tw.tm table{border-left:2px solid var(--a2)}
table.v{border-collapse:collapse;font-family:var(--mn);white-space:nowrap}
table.v caption{font-size:7px;color:var(--ac);padding:2px 4px;text-align:left;letter-spacing:.1em;font-weight:700}
table.v th{font-size:6px;color:var(--dm);padding:1px 2px;text-align:center;min-width:24px}
table.v th.r{text-align:right;min-width:26px;padding-right:3px}
table.v td{width:28px;height:18px;border:1px solid rgba(255,255,255,.03);text-align:center;vertical-align:middle;font-size:7px;font-weight:700;color:#bbb}
.dp{color:var(--rd)}.dn{color:var(--bl)}.dz{color:#333}
.dpp{background:rgba(255,50,50,.18);color:var(--rd)}.dnn{background:rgba(50,130,255,.18);color:var(--bl)}.dzz{background:rgba(255,255,255,.01);color:#333}
.c3w{border-top:1px solid var(--bd);background:var(--p);overflow:hidden;touch-action:none}
.c3w canvas{display:block}
.leg{display:flex;align-items:center;gap:4px;font-family:var(--mn);font-size:6px;color:var(--dm);padding:2px 4px}
.leg .bar{flex:1;height:6px;border-radius:2px}
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
var C3={base:{ang:-0.65,tilt:0.88,drag:false,lx:0},delta:{ang:-0.65,tilt:0.88,drag:false,lx:0},mod:{ang:-0.65,tilt:0.88,drag:false,lx:0}};

async function init(){
  try{
    var r=await fetch('/tuner/sessions');var d=await r.json();
    if(!d.sessions||!d.sessions.length){st('No hay sesiones');return}
    var ok=[];
    for(var i=0;i<d.sessions.length;i++){var s=d.sessions[i];try{var mr=await fetch('/tuner/maps?session='+s.id);var md=await mr.json();if(md&&md.fuel_front)ok.push(s)}catch(e){}}
    if(!ok.length){st('Sin mapas legibles');return}
    var o='<option value="">--</option>';
    for(var i=0;i<ok.length;i++){var s=ok[i];o+='<option value="'+s.id+'">'+s.id+' ('+s.version+') '+s.rides+'r</option>'}
    document.getElementById('sB').innerHTML=o;document.getElementById('sM').innerHTML=o;
    st(ok.length+' sesiones validas');
  }catch(e){st('Error: '+e.message)}
}
function st(t){document.getElementById('st').textContent=t}
async function load(t){
  var id=document.getElementById(t==='base'?'sB':'sM').value;if(!id)return;
  st('Cargando '+id+'...');
  try{
    var r=await fetch('/tuner/maps?session='+id);var d=await r.json();
    if(!d||!d.fuel_front){st('Error: '+(d&&d.error||'sin mapa'));return}
    if(t==='base')mB=d;else mM=d;render();
  }catch(e){st('Error al cargar')}
}

function render(){
  if(!mB||!mM)return;
  var mk=cur,ak=AX[mk],bD=mB[mk],mD=mM[mk];
  if(!bD||!mD){document.getElementById('pw').innerHTML='<p style="padding:16px;color:#555">Mapa no disponible</p>';return}
  var rpm=mB.axes[ak[0]],lod=mB.axes[ak[1]],rows=lod.length,cols=rpm.length;
  if(bD.length!==mD.length){st('Dimensiones diferentes');return}
  var mx=0;
  for(var i=0;i<rows;i++)for(var j=0;j<cols;j++){var v=Math.abs(mD[i][j]-bD[i][j]);if(v>mx)mx=v}
  function hdr(){var h='<tr><th></th>';for(var j=0;j<cols;j++)h+='<th>'+rpm[j]+'</th>';return h+'</tr>'}
  function tbl(data,cap){
    var h='<table class="v"><caption>'+cap+'</caption>'+hdr();
    for(var i=0;i<rows;i++){h+='<tr><th class="r">'+lod[i]+'</th>';for(var j=0;j<cols;j++)h+='<td>'+data[i][j].toFixed(0)+'</td>';h+='</tr>'}
    return h+'</table>';
  }
  function dtbl(){
    var h='<table class="v"><caption>DELTA</caption>'+hdr();
    for(var i=0;i<rows;i++){h+='<tr><th class="r">'+lod[i]+'</th>';for(var j=0;j<cols;j++){var d=mD[i][j]-bD[i][j],ad=Math.abs(d),cls='dzz',txt='\u00B7';if(ad>0.3){txt=(d>0?'+':'')+d.toFixed(1);var ratio=mx>0?ad/mx:0;cls=ratio>0.5?(d>0?'dpp':'dnn'):(d>0?'dp':'dn')}h+='<td class="'+cls+'">'+txt+'</td>'}h+='</tr>'}
    return h+'</table>';
  }
  document.getElementById('pw').innerHTML=
    '<div class="tw tb">'+tbl(bD,'BASE')+'<div class="c3w"><canvas id="c3b" height="260"></canvas></div><div class="leg" id="lb"></div></div>'+
    '<div class="tw">'+dtbl()+'<div class="c3w"><canvas id="c3d" height="260"></canvas></div><div class="leg" id="ld"></div></div>'+
    '<div class="tw tm">'+tbl(mD,'MOD')+'<div class="c3w"><canvas id="c3m" height="260"></canvas></div><div class="leg" id="lm"></div></div>';
  st(mk.toUpperCase().replace('_',' ')+' \u2014 Delta max: '+mx.toFixed(1));
  wireCanvas('c3b','base');wireCanvas('c3d','delta');wireCanvas('c3m','mod');
  drawAll(bD,mD,rpm,lod,mx);
}

function wireCanvas(cid,key){
  var el=document.getElementById(cid);if(!el)return;
  el.width=el.parentElement.clientWidth||400;
  el.addEventListener('mousedown',function(e){C3[key].drag=true;C3[key].lx=e.clientX});
  el.addEventListener('touchstart',function(e){C3[key].drag=true;C3[key].lx=e.touches[0].clientX},{passive:true});
}

document.addEventListener('mousemove',function(e){for(var k in C3){var c=C3[k];if(c.drag){c.ang+=(e.clientX-c.lx)*0.005;c.lx=e.clientX;drawAll()}}});
document.addEventListener('mouseup',function(){for(var k in C3)C3[k].drag=false});
document.addEventListener('touchmove',function(e){
  for(var k in C3){var c=C3[k];if(c.drag){c.ang+=(e.touches[0].clientX-c.lx)*0.005;c.lx=e.touches[0].clientX;drawAll();e.preventDefault();return}}
},{passive:false});
document.addEventListener('touchend',function(){for(var k in C3)C3[k].drag=false});

function drawAll(bD,mD,rpm,lod,mx){
  if(!mB||!mM)return;
  var mk=cur,ak=AX[mk];
  bD=bD||mB[mk];mD=mD||mM[mk];
  rpm=rpm||mB.axes[ak[0]];lod=lod||mB.axes[ak[1]];
  var dd=[];
  if(mD&&bD)for(var i=0;i<bD.length;i++){dd[i]=[];for(var j=0;j<bD[0].length;j++)dd[i][j]=mD[i][j]-bD[i][j]}
  drawSurf('c3b',bD,rpm,lod,'heat','lb','BASE');
  drawSurf('c3d',dd,rpm,lod,'delta','ld','DELTA');
  drawSurf('c3m',mD,rpm,lod,'heat','lm','MOD');
}

function drawSurf(cid,data,rpm,lod,mode,legId,label){
  var el=document.getElementById(cid);if(!el||!data||!data.length)return;
  var ctx=el.getContext('2d'),key=cid==='c3b'?'base':cid==='c3d'?'delta':'mod';
  var c=C3[key],W=el.width,H=el.height,R=lod.length,Cl=rpm.length;
  ctx.fillStyle='#111114';ctx.fillRect(0,0,W,H);
  var zN=1e9,zX=-1e9;
  for(var i=0;i<R;i++)for(var j=0;j<Cl;j++){if(data[i][j]<zN)zN=data[i][j];if(data[i][j]>zX)zX=data[i][j]}
  if(zX===zN)zX=zN+1;
  var sX=Math.min((W-50)/(Cl-1),28),sY=Math.min((H-40)/(R-1),20),sZ=(H*0.3)/(zX-zN);
  var ox=W*0.5,oy=H*0.85,ca=Math.cos(c.ang),sa=Math.sin(c.ang),ct=Math.cos(c.tilt),st2=Math.sin(c.tilt);
  function pr(j,i,z){
    var x=(j-(Cl-1)/2)*sX,y=((R-1)-i-(R-1)/2)*sY,z2=(z-zN)*sZ;
    var rx=x*ca-z2*sa,rz=x*sa+z2*ca,ry=y*ct-rz*st2;
    return[ox+rx,oy-ry];
  }
  function heat(t){
    var r,g,b;
    if(t<0.2){var s=t/0.2;r=15;g=Math.round(10+60*s);b=Math.round(80+140*s)}
    else if(t<0.4){var s=(t-0.2)/0.2;r=Math.round(15+20*s);g=Math.round(70+130*s);b=Math.round(220+35*s)}
    else if(t<0.6){var s=(t-0.4)/0.2;r=Math.round(35+120*s);g=Math.round(200+55*s);b=Math.round(255-155*s)}
    else if(t<0.8){var s=(t-0.6)/0.2;r=Math.round(155+100*s);g=Math.round(255-60*s);b=Math.round(100-70*s)}
    else{var s=(t-0.8)/0.2;r=255;g=Math.round(195-145*s);b=Math.round(30-10*s)}
    return'rgba('+r+','+g+','+b+',0.88)';
  }
  function dcol(v){
    var ma=Math.max(Math.abs(zN),Math.abs(zX));if(ma===0)ma=1;var t=v/ma,r,g,b;
    if(t>=0){r=Math.round(60+195*t);g=Math.round(30+30*t);b=30}
    else{var s=-t;r=30;g=Math.round(40+100*s);b=Math.round(60+195*s)}
    return'rgba('+r+','+g+','+b+',0.88)';
  }
  var faces=[];
  for(var i=0;i<R-1;i++)for(var j=0;j<Cl-1;j++){
    var p0=pr(j,i,data[i][j]),p1=pr(j+1,i,data[i][j+1]),p2=pr(j+1,i+1,data[i+1][j+1]),p3=pr(j,i+1,data[i+1][j]);
    var av=(data[i][j]+data[i][j+1]+data[i+1][j+1]+data[i+1][j])/4;
    var dp0=pr(j,i,zN),dp1=pr(j+1,i,zN),dp2=pr(j+1,i+1,zN),dp3=pr(j,i+1,zN);
    var dz=(dp0[1]+dp1[1]+dp2[1]+dp3[1])/4;
    faces.push({p:[p0,p1,p2,p3],z:dz,v:av});
  }
  faces.sort(function(a,b){return a.z-b.z});
  for(var f=0;f<faces.length;f++){
    var fc=faces[f];
    ctx.beginPath();ctx.moveTo(fc.p[0][0],fc.p[0][1]);
    for(var k=1;k<4;k++)ctx.lineTo(fc.p[k][0],fc.p[k][1]);
    ctx.closePath();
    var nm=(fc.v-zN)/(zX-zN);
    ctx.fillStyle=mode==='delta'?dcol(fc.v):heat(nm);
    ctx.fill();ctx.strokeStyle='rgba(255,255,255,0.06)';ctx.lineWidth=0.5;ctx.stroke();
  }
  ctx.font='6px monospace';ctx.fillStyle='#555';
  for(var j=0;j<Cl;j+=2){var p=pr(j,R-1,zN);ctx.fillText(rpm[j],p[0]-6,p[1]+9)}
  for(var i=0;i<R;i+=2){var p=pr(0,i,zN);ctx.fillText(lod[i],p[0]-24,p[1]+3)}
  var leg=document.getElementById(legId);
  if(mode==='delta'){
    leg.innerHTML='<span>-</span><div class="bar" style="background:linear-gradient(to right,rgba(30,60,255,.9),#444,rgba(255,60,60,.9))"></div><span>+</span><span style="margin-left:4px">'+zN.toFixed(1)+'/+'+zX.toFixed(1)+'</span>';
  }else{
    leg.innerHTML='<span>'+zN.toFixed(0)+'</span><div class="bar" style="background:linear-gradient(to right,rgba(15,10,80,.9),rgba(15,70,220,.9),rgba(35,200,255,.9),rgba(155,255,100,.9),rgba(255,195,30,.9),rgba(255,50,20,.9))"></div><span>'+zX.toFixed(0)+'</span>';
  }
}

document.getElementById('sB').onchange=function(){load('base')};
document.getElementById('sM').onchange=function(){load('mod')};
document.getElementById('tabs').onclick=function(e){
  var b=e.target.closest('.tab');if(!b)return;
  var all=document.querySelectorAll('.tab');for(var i=0;i<all.length;i++)all[i].classList.remove('on');
  b.classList.add('on');cur=b.dataset.m;render();
};
window.addEventListener('resize',function(){
  ['c3b','c3d','c3m'].forEach(function(id){var el=document.getElementById(id);if(el)el.width=el.parentElement.clientWidth||400});
  drawAll();
});
init();
</script></body></html>'''
with open('web/templates/tuner.html','w') as f: f.write(html)
print('tuner.html v5 - 3D bajo cada tabla')
