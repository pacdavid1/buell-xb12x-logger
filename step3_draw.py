h=open('web/templates/tuner.html').read()

# 3a. drawAll: dibujar 3 secciones
h=h.replace(
"drawSurf('c3b',bD,rpm,lod,'heat','lb');\n  drawSurf('c3d',dd,rpm,lod,'delta','ld');\n  drawSurf('c3m',mD,rpm,lod,'heat','lm');",
"var el=document.getElementById('c3all');if(!el)return;\n  var W=el.width,H=el.height,ctx=el.getContext('2d');\n  ctx.fillStyle='#111114';ctx.fillRect(0,0,W,H);\n  var w3=Math.floor(W/3);\n  drawSurf(ctx,bD,rpm,lod,'heat',0,w3,H);\n  drawSurf(ctx,dd,rpm,lod,'delta',w3,w3,H);\n  drawSurf(ctx,mD,rpm,lod,'heat',w3*2,w3,H);\n  ctx.font='9px monospace';ctx.fillStyle='#f5a623';ctx.textAlign='center';\n  ctx.fillText('BASE',w3*0.5,H-4);\n  ctx.fillText('DELTA',w3*1.5,H-4);\n  ctx.fillText('MOD',w3*2.5,H-4);")

# 3b. drawSurf: aceptar ctx+offX+secW+secH
h=h.replace(
"function drawSurf(cid,data,rpm,lod,mode,legId){\n  var el=document.getElementById(cid);if(!el||!data||!data.length)return;\n  var ctx=el.getContext('2d'),key=cid==='c3b'?'base':cid==='c3d'?'delta':'mod';\n  var c=C3[key],W=el.width,H=el.height,R=lod.length,Cl=rpm.length;\n  if(W<10||H<10)return;\n  ctx.fillStyle='#111114';ctx.fillRect(0,0,W,H);",
"function drawSurf(ctx,data,rpm,lod,mode,offX,secW,secH){\n  if(!ctx||!data||!data.length)return;\n  var c=C3['base'],W=secW,H=secH,R=lod.length,Cl=rpm.length;\n  if(W<10||H<10)return;")

# 3c. Mover ox al centro de cada seccion
h=h.replace('var ox=W*0.5,oy=H*0.45','var ox=offX+W*0.5,oy=H*0.45')

# 3d. Quitar legendas individuales (ya no hay divs .leg)
h=h.replace("var leg=document.getElementById(legId);\n  if(mode==='delta'){\n    leg.innerHTML='<span>-</span><div class=\"bar\" style=\"background:linear-gradient(to right,rgba(30,60,255,.9),#444,rgba(255,60,60,.9))\"></div><span>+</span><span style=\"margin-left:4px\">'+zN.toFixed(1)+'/+'+zX.toFixed(1)+'</span>';\n  }else{\n    leg.innerHTML='<span>'+zN.toFixed(0)+'</span><div class=\"bar\" style=\"background:linear-gradient(to right,rgba(15,10,80,.9),rgba(15,70,220,.9),rgba(35,200,255,.9),rgba(155,255,100,.9),rgba(255,195,30,.9),rgba(255,50,20,.9))\"></div><span>'+zX.toFixed(0)+'</span>';\n  }",
'#NOLEGEND#')

# 3e. Agregar CSS del header
h=h.replace('.g3c canvas{display:block;flex:1;touch-action:none}',
'.g3h{display:flex;font-family:var(--mn);font-size:9px;font-weight:700;color:var(--a2);padding:3px 12px;gap:25%;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02)}\n#c3all{display:block;touch-action:none}')

open('web/templates/tuner.html','w').write(h)
print('Paso 3: drawAll y drawSurf cambiados')
