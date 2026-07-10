# BACKLOG — Mapa 3D del recorrido GPS (subtab Mapa)

> Sueño guajiro: ver el recorrido GPS como un circuito 3D rotando solo,
> estilo selección de pista en videojuego de carreras, debajo del mapa 2D
> y el perfil de altitud. Tocarlo con el mouse = rotarlo a mano.
>
> Viabilidad: ALTA. El motor 3D de tuner.html (project() con yaw/tilt/roll,
> drag para rotar, canvas puro sin librerías) es directamente reutilizable.
> /gps_track ya entrega lat/lon/alt/spd por punto. Todo el render corre en
> el navegador del cliente — cero carga extra para la Pi Zero.

---

## FASE 2 — Presentación estilo racing game

### BL-M3D-04 — Cortina, piso y sombra
**Priority:** MEDIUM (es lo que lo hace verse PRO)
**Pages:** app.js

- "Cortina" translúcida bajo la línea: por cada segmento, un quad desde el
  track hasta el plano base (alt_min), relleno rgba con el color de velocidad
  al ~12% — da la sensación inmediata de elevación
- Grid del plano base (líneas tenues #1e1e24, estilo de los paneles actuales)
- Sombra del track proyectada en el piso (la "vista 2D" como sombra gris)
- Marcadores 3D de inicio (verde #00ff88) y fin (rojo #ff4444) — mismos
  colores que en el Leaflet
- Painter's algorithm: ordenar segmentos por profundidad z2 antes de dibujar
  (igual que las caras en drawSurf) para que la cortina no se dibuje encima
  de la línea cuando queda atrás

### BL-M3D-05 — Downsampling de puntos
**Priority:** HIGH (va junto con BL-M3D-01, la Pi Zero lo agradece)
**Pages:** server.py (/gps_track), app.js

Un ride largo puede tener decenas de miles de puntos GPS:
- Server-side: parámetro `?max_points=N` en /gps_track con stride simple
  (cada k-ésimo punto). Reduce el JSON que la Pi arma y manda (memoria —
  ver BL-BUG-03, la Pi ya sufrió OOM con requests grandes)
- Client-side: si aún hace falta, Douglas-Peucker o stride a ~800-1500
  puntos para el render 3D (60 fps con rAF se logra fácil a ese tamaño)
- El mapa 2D y el perfil pueden seguir usando la resolución completa o
  también beneficiarse del mismo parámetro

---

## FASE 3 — Caramelo (después de que lo básico funcione)

### BL-M3D-06 — Replay fantasma
**Priority:** LOW (pero es el más divertido)
- Punto animado que recorre el track a velocidad proporcional a spd real
  (o tiempo comprimido, ej. ride de 1 h en 30 s)
- Botón play/pause; mientras corre el replay, la cámara puede seguir al
  punto (modo "chase cam") o quedarse en órbita
- HUD mini: km/h y altitud del punto actual

### BL-M3D-07 — Sincronización 3D ↔ perfil ↔ mapa 2D
**Priority:** LOW
- Hover en el altitudeChart → marcar el punto correspondiente en el 3D y
  en el Leaflet (y viceversa)
- Click en el 3D → popup con spd/alt/distancia acumulada del punto más
  cercano

---

## Bugs/mejoras del subtab Mapa encontrados durante el análisis

### ~~BL-MAP-03~~ ✅ (v2.7.186) — Leyenda de colores de velocidad

🔍 **AUDITED 2026-07-03: NOT-ACTUALLY-DONE — genuine regression, not a false original claim.** The 5-swatch legend (`spd2color()` buckets: 0-20/20-60/60-120/120-160/160+ km/h) really did ship in the old "Mapa" tab of `index.html` — but was silently deleted in commit `89fefe0` (v2.7.233, "Mapa removal — superseded by gps_analysis page") when that tab was replaced by `gps_analysis.html`. The new page never got the legend ported over, and dead `.map-legend-bar` CSS was left behind in `index.html:740-742`. The color function itself (`spd2color()`) IS still used for both 2D and 3D tracks in `gps_analysis.html` — only the visible legend key is missing. Full detail in the AUDIT REPORT section at the top of `BACKLOG.md`. **Action: reopen as a small task** — port the 5-swatch legend markup into `gps_analysis.html`, delete the dead CSS from `index.html`. Good candidate for a "smallest first" pass. Delete the incorrect strikethrough above when actioning.

**Priority:** LOW
Barrita de leyenda (azul→verde→amarillo→rojo→magenta con sus rangos km/h)
visible en el mapa 2D y el 3D. Hoy el código de colores es implícito.

---

## Decisiones a discutir antes de implementar

1. **¿Helper 3D compartido o copia?** Extraer project()/drag de tuner.html
   a un módulo común es más limpio (DRY) pero toca el tuner que ya funciona.
   Copia autocontenida en app.js = cero riesgo de romper el tuner.
2. **Layout:** ¿3D debajo del perfil (scroll más largo) o como toggle
   2D/3D en el mismo espacio del Leaflet? Propuesta original: debajo.
3. **Exageración vertical:** ¿auto, slider, o presets 1x/3x/5x/10x?
4. **¿FASE 2 (cortina/piso) entra desde el inicio** o primero se valida la
   línea pelona rotando?
