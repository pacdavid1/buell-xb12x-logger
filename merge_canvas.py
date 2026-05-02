h=open('web/templates/tuner.html').read()

# 1. CSS: reemplazar estilos de g3c por canvas unico
h=h.replace('.g3c canvas{display:block;flex:1;touch-action:none}','#c3all{display:block;touch-action:none}')
h=h.replace('.g3c{flex:1;min-width:200px;display:flex;flex-direction:column;overflow:visible;background:var(--p)}',
'.g3h{display:flex;font-family:var(--mn);font-size:9px;font-weight:700;color:var(--a2);padding:3px 12px;gap:25%;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02)}')

# 2. HTML: 3 divs -> header + 1 canvas
h=h.replace('<div class="g3c"><div class="g3t">BASE 3D</div><canvas id="c3b"></canvas><div class="leg" id="lb"></div></div>\n<div class="g3c"><div class="g3t">DELTA 3D</div><canvas id="c3d"></canvas><div class="leg" id="ld"></div></div>\n<div class="g3c"><div class="g3t">MOD 3D</div><canvas id="c3m"></canvas><div class="leg" id="lm"></div></div>',
'<div class="g3h"><span>BASE</span><span>DELTA</span><span>MOD</span></div>\n<canvas id="c3all"></canvas>')

# 3. init3D: un solo canvas
h=h.replace("['c3b','c3d','c3m'].forEach(function(cid){\n    var el=document.getElementById(cid);if(!el)return;\n    var key=cid==='c3b'?'base':cid==='c3d'?'delta':'mod';\n    function rs(){var r=el.getBoundingClientRect();el.width=r.width||300;el.height=r.height||250;drawAll()}\n    el.addEventListener(\"mousedown\",function(e){C3[key].drag=true;C3[key].lx=e.clientX})\n    el.addEventListener(\"touchstart\",function(e){C3[key].drag=true;C3[key].lx=e.touches[0].clientX},{passive:true})\n    rs();\n  });\n  window.addEventListener('resize',function(){\n    ['c3b','c3d','c3m'].forEach(function(cid){\n      var el=document.getElementById(cid);if(!el)return;\n      el.width=el.parentElement.clientWidth||300;\n      el.height=el.parentElement.clientHeight||250;\n    });\n    drawAll();\n  });",
"var el=document.getElementById('c3all');if(!el)return;\n  function rs(){el.width=el.parentElement.clientWidth||900;el.height=el.parentElement.clientHeight||300;drawAll()}\n  el.addEventListener('mousedown',function(e){for(var k in C3){C3[k].drag=true;C3[k].lx=e.clientX}});\n  el.addEventListener('touchstart',function(e){for(var k in C3){C3[k].drag=true;C3[k].lx=e.touches[0].clientX}},{passive:true});\n  rs();\n  window.addEventListener('resize',rs);")

# 4. drawAll: dibujar 3 secciones en 1 canvas
h=h.replace("drawSurf('c3b',bD,rpm,lod,'heat','lb');\n  drawSurf('c3d',dd,rpm,lod,'delta','ld');\n  drawSurf('c3m',mD,rpm,lod,'heat','lm');",
"var el=document.getElementById('c3all');if(!el)return;\n  var W=el.width,H=el.height,ctx=el.getContext('2d');\n  ctx.fillStyle='#111114';ctx.fillRect(0,0,W,H);\n  var w3=Math.floor(W/3);\n  drawSurf(ctx,bD,rpm,lod,'heat',0,w3,H);\n  drawSurf(ctx,dd,rpm,lod,'delta',w3,w3,H);\n  drawSurf(ctx,mD,rpm,lod,'heat',w3*2,w3,H);\n  ctx.font='9px monospace';ctx.fillStyle='#f5a623';\n  ctx.textAlign='center';\n  ctx.fillText('BASE',w3*0.5,H-4);\n  ctx.fillText('DELTA',w3*1.5,H-4);\n  ctx.fillText('MOD',w3*2.5,H-4);")

# 5. drawSurf: aceptar ctx+offset en vez de canvas id
h=h.replace("function drawSurf(cid,data,rpm,lod,mode,legId){\n  var el=document.getElementById(cid);if(!el||!data||!data.length)return;\n  var ctx=el.getContext('2d'),key=cid==='c3b'?'base':cid==='c3d'?'delta':'mod';\n  var c=C3[key],W=el.width,H=el.height,R=lod.length,Cl=rpm.length;\n  if(W<10||H<10)return;\n  ctx.fillStyle='#111114';ctx.fillRect(0,0,W,H);",
"function drawSurf(ctx,data,rpm,lod,mode,offX,secW,secH){\n  if(!ctx||!data||!data.length)return;\n  var c=C3['base'],W=secW,H=secH,R=lod.length,Cl=rpm.length;\n  if(W<10||H<10)return;")

# 6. Cambiar ox para usar offset
h=h.replace('var ox=W*0.5,oy=H*0.45','var ox=offX+W*0.5,oy=H*0.45')

# 7. Quitar legend individual de drawSurf
h=h.replace("var leg=document.getElementById(legId);\n  if(mode==='delta'){\n    leg.innerHTML='<span>-</span><div class=\"bar\" style=\"background:linear-gradient(to right,rgba(30,60,255,.9),#444,rgba(255,60,60,.9))\"></div><span>+</span><span style=\"margin-left:4px\">'+zN.toFixed(1)+'/+'+zX.toFixed(1)+'</span>';\n  }else{\n    leg.innerHTML='<span>'+zN.toFixed(0)+'</span><div class=\"bar\" style=\"background:linear-gradient(to right,rgba(15,10,80,.9),rgba(15,70,220,.9),rgba(35,200,255,.9),rgba(155,255,100,.9),rgba(255,195,30,.9),rgba(255,50,20,.9))\"></div><span>'+zX.toFixed(0)+'</span>';\n  }",
'#NOLEGEND#')

# 8. Quitar CSS de .leg y .g3t que ya no se usan
h=h.replace('.g3t{font-family:var(--mn);font-size:8px;font-weight:700;color:var(--a2);padding:2px 6px;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02);flex-shrink:0}\n','')
h=h.replace('.leg{display:flex;align-items:center;gap:3px;font-family:var(--mn);font-size:6px;color:var(--dm);padding:2px 6px;border-top:1px solid var(--bd);flex-shrink:0}\n.leg .bar{flex:1;height:5px;border-radius:2px}\n','')

open('web/templates/tuner.html','w').write(h)
print('Canvas unico: 3 graficos sin corte')
