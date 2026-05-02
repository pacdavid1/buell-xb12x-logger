h=open('web/templates/tuner.html').read()
h=h.replace(
'<div class="g3c"><div class="g3t">BASE 3D</div><canvas id="c3b"></canvas><div class="leg" id="lb"></div></div>\n<div class="g3c"><div class="g3t">DELTA 3D</div><canvas id="c3d"></canvas><div class="leg" id="ld"></div></div>\n<div class="g3c"><div class="g3t">MOD 3D</div><canvas id="c3m"></canvas><div class="leg" id="lm"></div></div>',
'<div class="g3h"><span>BASE</span><span>DELTA</span><span>MOD</span></div>\n<canvas id="c3all"></canvas>')
open('web/templates/tuner.html','w').write(h)
print('Paso 1: HTML cambiado')
