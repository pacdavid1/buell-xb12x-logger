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

## FASE 1 — Núcleo (lo mínimo para que exista)

### BL-M3D-01 — Vista 3D del track GPS bajo el perfil de altitud
**Priority:** HIGH (es el feature estrella)
**Pages:** Dashboard (index.html — subtab Mapa), app.js

Nueva sección en el subtab Mapa, debajo del altitudeChart:
- `<canvas id="track3d">` de ~40dvh con su barrita de título estilo actual
- Conversión GPS → metros locales (plano local, no proyección web):
  - `x = (lon - lon0) * 111320 * cos(lat0)`  (este)
  - `z = (lat - lat0) * 110540`              (norte)
  - `y = alt - alt_min`                      (altura)
  - lat0/lon0 = centroide del track
- Reutilizar la función `project()` de tuner.html (extraer a helper común o
  copiar — decidir: helper compartido en app.js vs duplicado autocontenido)
- Línea del track coloreada por velocidad (reusar getGradientColor, misma
  semántica de color que el mapa 2D y el perfil — consistencia visual)
- **Exageración vertical configurable** (slider o botones 1x/3x/5x/10x).
  Crítico: un ride de 40 km con 300 m de desnivel se ve PLANO a escala real.
  Default sugerido: auto — escalar para que el rango vertical sea ~15% del
  span horizontal
- Auto-centrado con bounding box (mismo truco que drawSurf en tuner)
- Si el ride no tiene alt (puntos sin fix 3D): mostrar el track plano con
  aviso "sin datos de altitud"

### BL-M3D-02 — Auto-rotación "modo videojuego"
**Priority:** HIGH (es lo que le da el alma)
**Pages:** app.js

- requestAnimationFrame con yaw lento continuo (~0.15 rad/s, tilt fijo
  agradable tipo vista isométrica ~25-30°)
- Pausa al hacer mousedown/touchstart; reanuda solo tras ~4 s sin interacción
  (transición suave, no arrancón)
- Page Visibility API + IntersectionObserver: NO renderizar si el tab del
  navegador está oculto o si el canvas no está en viewport — ahorra batería
  en el teléfono y evita trabajo inútil
- Solo animar cuando el subtab Mapa está activo

### BL-M3D-03 — Interacción manual (drag / touch / zoom)
**Priority:** HIGH
**Pages:** app.js

- Drag para rotar yaw+tilt: mismo patrón de listeners que C3 en tuner.html
  (mousedown/mousemove/mouseup + touchstart/touchmove con preventDefault)
- Rueda del mouse = zoom; pinch en móvil (nice-to-have, puede ser FASE 2)
- Doble click/tap = reset de cámara y reanudar auto-rotación

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

### BL-MAP-01 — Tracks y marcadores se apilan al cambiar de ride ✅ HECHO v2.7.120
**Priority:** HIGH (bug real, fix barato)
**Pages:** app.js (loadMapTrack)

`_mapPolyline` se "limpia" pero nunca se asigna: los segmentos se agregan
como L.polyline individuales sueltos y los circleMarker de inicio/fin
también — al seleccionar otro ride todo lo anterior queda dibujado.
Fix: usar un `L.layerGroup()` (`_trackLayer`), agregarle todos los
segmentos y marcadores, y hacer `_trackLayer.clearLayers()` al recargar.

### BL-MAP-02 — Distancia sobreestimada (falta cos(lat)) ✅ HECHO v2.7.120
**Priority:** LOW
**Pages:** app.js (loadMapTrack, perfil de altitud)

`Math.hypot(dlat, dlon) * 111.32` trata los grados de longitud como si
midieran lo mismo que los de latitud. A ~32° lat, 1° lon ≈ 94 km, no 111.
Fix: `dx = dlon * 111.32 * Math.cos(lat_rad)`, `dy = dlat * 110.54`.
La conversión de BL-M3D-01 ya lo hace bien — reusar gpsKm() (app.js, v2.7.120).

### BL-MAP-03 — Leyenda de colores de velocidad
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
