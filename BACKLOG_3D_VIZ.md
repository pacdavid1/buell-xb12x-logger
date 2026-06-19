# BACKLOG — 3d_visualization_makeup + Graf presets

> Alcance: mejorar los 3D de mapas de inyección (hoy solo existen en
> tuner.html: BASE/DELTA/MOD) y agregar grupos predeterminados de señales
> al Graf para tuning.
>
> Hallazgo del análisis: el único motor 3D real está en tuner.html
> (drawSurf/drawDelta, canvas puro). El subtab VE del Dashboard es heatmap
> 2D en tabla HTML. El Graf YA es configurable por chart (localStorage
> buell_chart_cfg_v2) — los presets son la pieza que falta, no hay que
> reconstruir nada.

---

## A — Maquillaje del 3D del Tuner (BASE / DELTA / MOD)

### BL-3DV-02 — Hover picking en el 3D (leer celda con el mouse)
**Priority:** HIGH — convierte el 3D de adorno a herramienta
Hoy el hover solo funciona en la tabla HTML. Propuesta:
- Al dibujar, guardar los polígonos proyectados de cada cara con su (ri,ci)
- En mousemove (sin drag): point-in-polygon sobre las caras ordenadas por
  profundidad → celda bajo el cursor
- Mostrar RPM / TPS / VAL en el status (st()) y resaltar la cara (borde
  brillante)
- Bidireccional: hover en la tabla → resaltar la cara en el 3D

### BL-3DV-03 — Celdas staged visibles en el 3D
**Priority:** MEDIUM
Las celdas en escala para BURN se ven naranjas (#f5a623) en la tabla pero
el 3D MOD no las distingue. Pintar esas caras con borde/glow naranja en
el 3D MOD: de un vistazo ves QUÉ vas a quemar y DÓNDE está en la superficie.

### BL-3DV-04 — Modo overlay: BASE fantasma bajo MOD
**Priority:** MEDIUM — la mejor forma de "ver" una propuesta
Toggle que dibuja en un solo canvas la superficie MOD sólida + BASE como
wireframe translúcido gris. Donde se separan las mallas = el cambio.
Más intuitivo que el DELTA 3D para magnitudes pequeñas. (El DELTA se
queda para ver signo/distribución.)

### BL-3DV-05 — Cobertura de datos reales sobre la superficie
**Priority:** HIGH — el feature de tuning más valioso de esta lista
Proyectar sobre la superficie 3D las celdas RPM×TPS realmente visitadas
en la(s) sesión(es) (mismos bins que sessions_vs): puntos o tinte de
saturación por nº de muestras. Responde la pregunta clave antes de quemar:
"¿esta propuesta toca celdas donde tengo datos reales o estoy extrapolando?"
Conectar con la clasificación SWEET/SPICY/BITTER (verde/amarillo/rojo
sobre la malla) si la sesión tiene cache VS.

### BL-3DV-06 — Cámara: auto-rotación idle + presets + reset
**Priority:** LOW
- Auto-rotación lenta cuando no hay interacción (mismo motor que el mapa
  GPS 3D de BACKLOG_MAPA_3D.md — consistencia "racing game" en toda la GUI)
- Doble click = reset a vista isométrica
- Botones de vista: ISO / TOP (vista de heatmap) / FRONT (perfil RPM)
- Toggle "link": hoy arrastrar uno rota los tres (bueno para comparar);
  poder desacoplar

### BL-3DV-07 — Snapshot PNG
**Priority:** LOW
Botón que exporta los 3 canvas (o el activo) a PNG con título
sesión/mapa/fecha — para documentar antes/después de cada burn y
compartir. canvas.toBlob, trivial.

---

## B — Subtab VE del Dashboard

### BL-3DV-08 — Vista 3D del VE en el Dashboard (motor compartido)
**Priority:** MEDIUM
El subtab VE solo tiene la tabla heatmap 2D. Propuesta:
- Extraer el motor de tuner.html (project/drawSurf/drag/Lambert) a
  `web/static/surface3d.js` reutilizable
- Toggle "2D/3D" en el subtab VE: misma superficie con celdas staged
  en naranja (BL-3DV-03 aplica igual aquí)
- El mapa GPS 3D (BACKLOG_MAPA_3D.md) usaría el mismo módulo
- Riesgo: refactor toca tuner.html que ya funciona → hacerlo DESPUÉS de
  validar el motor compartido con el caso nuevo (GPS), no antes

---

## C — Graf: grupos predeterminados para tuning

### BL-GRAF-02 — Indicador de preset activo + volver a Custom
**Priority:** LOW
Mostrar el preset activo en el header del Graf; si el usuario edita una
señal manualmente, cambia a "Custom (basado en X)". El custom del usuario
nunca se pierde (se guarda aparte en localStorage).

---

## Orden sugerido de implementación (a discutir)

1. BL-GRAF-01 (presets) — barato, útil mañana mismo
2. BL-3DV-01 (Lambert) — una tarde, transforma el look
3. BL-3DV-02 (hover picking) — convierte el 3D en herramienta
4. BL-3DV-05 (cobertura de datos) — el de más valor para tunear
5. BL-3DV-03/04 (staged + overlay fantasma)
6. BL-3DV-08 (motor compartido + VE 3D) — después del GPS 3D

---

## Ideas nuevas (vistas durante el sprint v2.7.117-120)

### BL-3DV-09 — Lambert también en DELTA 3D
drawDelta tiene varios modos de render (dcol sólido, heat, ghost azul,
barras rojo/azul) — hoy solo BASE/MOD tienen sombreado. Aplicar shadeRGBA
a los modos sólidos de drawDelta para consistencia visual.

### BL-3DV-10 — Persistir cámara del tuner 3D
CAM.zoom + ángulos (inTps/inRpm/inVal) y ALT en localStorage para que la
vista preferida sobreviva el reload. Hoy todo resetea a default.

### BL-GRAF-03 — Persistir señales custom POR preset
Hoy editar con ⚙ siempre cae a CUSTOM (un solo slot). Idea: recordar
ajustes finos por preset (ej. SPARK + cpu_temp) en localStorage separado.

### BL-MAP-04 — Rendimiento del track Leaflet
Cada segmento es un L.polyline individual (858 layers en un ride de 857
puntos). Para rides largos: usar L.canvas() como renderer o decimar puntos
(conecta con BL-M3D-05 ?max_points). Medir primero en un ride de >5k puntos.

### BL-GRAF-04 — Ventana "Datos Cursor" que huye del cursor
**Priority:** LOW — fácil, ideal para otro modelo
La ventana flotante de datos del cursor se sobrepone a las gráficas.
Propuesta del usuario: que huya — si el cursor se acerca a su mitad de
pantalla, la ventana brinca al extremo opuesto (izq ↔ der) con una
transición corta. Implementación: en el mousemove del crosshair, comparar
e.clientX con window.innerWidth/2 y togglear left/right de la ventana
(con histéresis de ~80px para que no parpadee en el centro).

### BL-GRAF-05 — Engrane ⚙ visible (parcialmente resuelto v2.7.121)
Título clickeable ya implementado. Queda opcional: hacer el ⚙ sticky al
borde derecho VISIBLE del viewport (position:sticky; right:0 dentro del
scroll horizontal) para que también se vea sin scrollear.

### BL-GRAF-06 — Señal derivada gear_detected en el Graf
gear_detect.py calcula la marcha post-ride (96.9% accuracy) pero el Graf
solo grafica columnas crudas del CSV. Idea: calcular gear_detected
client-side en parseCSVtoRows (mismos thresholds VSS/RPM) o exponerla en
el CSV servido — así la marcha discreta 1-5 se grafica limpia en vez de
inferirla del ratio.
