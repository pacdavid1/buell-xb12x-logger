<!-- DEV NOTE: planning doc (Spanish per project convention). All CODE remains English. -->

# BACKLOG_GRAF2 — Visor de telemetría pro + anotaciones para F7

> Plan de trabajo de la página `/graf2`. Para cualquier IA que retome esto:
> lee este archivo completo antes de tocar código. Respeta las reglas del proyecto
> (CLAUDE.md): English-only en código, CHANGELOG antes de cada commit, funciones <50
> líneas, archivos <800, sin mutación, validar paso a paso.

## Qué es GRAF2

Visor de telemetría profesional (uPlot), página **separada** del Dashboard viejo.
- Ruta: `GET /graf2` → `_handle_graf2` en `web/handlers/rides.py`.
- Frontend self-contained: `web/templates/graf2.html` + `web/static/graf2.js` + `web/static/uPlot.*`.
- Datos: `GET /csv/<ride>.csv` (filas crudas, parser columnar) + `GET /rides` (devuelve `{rides:[...]}`).
- **Se usa en el trackpad de una laptop** (no pantalla táctil): gestos por eventos `wheel`
  (ctrlKey=zoom, deltaX=pan tiempo, deltaY=scroll de página).

## Estado actual — HECHO (v2.7.140 → v2.7.148, en main)

- v2.7.140: uPlot; zoom+cursor sincronizado entre bloques; sombreado de flags; carriles de flags; leyenda unificada.
- v2.7.141: carriles manuales — toggle `≡` en el chip manda cualquier señal analógica a su propio carril apilado (~20%, `LANE_FRAC`).
- v2.7.142: anotaciones Fase 1 (botón 🔖 Mark, span de 2 clicks + nota, bandas azules, persistidas en `sessions/<sesion>/ride_*_annotations.json`) + toggle de eje Y (`Y: full` fijo al rango del ride [default] / `Y: fit` auto a lo visible).
- v2.7.143: editar/borrar anotación (click en una banda fuera de modo marca → editar/borrar; `POST /annotations` actualiza por id).
- v2.7.145: FASE 2.1 — selector `launch` / `diagnostic` / `note` en el modal; `type` persistido y validado server-side; bandas coloreadas por tipo (launch=azul, diagnostic=gris, note=verde); anotaciones sin `type` renderizan como launch.
- v2.7.148: `type` ahora REQUERIDO (antes default `launch`); modal bloquea guardar sin tipo seleccionado con aviso inline; backend rechaza POST sin tipo válido con HTTP 400; anotaciones legacy sin tipo renderizan en ámbar para reclasificar.

Backend anotaciones (`web/handlers/rides.py`): `GET /annotations?ride=<f>` y `POST /annotations`
(add / update-by-id / `action:delete`). JSON por ride: `{ride, annotations:[{id,t0_s,t1_s,note,type,created_utc}]}`.

---

## FASE 2 — SIGUIENTE (2.2 pendiente)

### 2.1 Campo `type` en las anotaciones — ✅ DONE (v2.7.145 + v2.7.148)

### 2.2 F7 consume las marcas — OPCIÓN B (elegida): "juntas pero no revueltas"
Objetivo del usuario: que el tramo marcado se procese **de pe a pa por F7**, pero **sin
contaminar** los clusters automáticos.

Diseño:
1. F7 lee `ride_*_annotations.json` de cada ride de la sesión.
2. Para cada marca `type=launch`, construir un evento F7:
   - `pw_curve` = `_f7_resample(pw1 de las filas en [t0,t1])` (reusar el resampler existente).
   - `bucket_a` = condiciones del arranque del tramo (gear/rpm/tps/vss promedio del inicio).
   - Etiquetar `source:'manual'` + copiar la nota.
3. Estos eventos pasan por el **mismo motor**: DTW, clustering, comparación cross-session.
4. PERO se reportan en una **categoría aparte "PILOT-MARKED"**, NO mezclados con los
   clusters automáticos. El usuario quiere verlos juntos en la UI pero diferenciados.

Archivos: `web/f7.py` (CANÓNICO — cuidado, validar import + endpoint tras cada cambio).
Entrada: `_f7_load_session_clusters(buell_dir, sid, threshold)` es el punto de carga/cómputo.
Salida: extender el dict de clusters con una sección `pilot_marked`.
UI: mostrar la categoría PILOT-MARKED en `session_events.html` (y/o resaltar en graf2).

---

## FASE 3 — Overlay A/B (después)
Superponer dos rides alineados (tiempo o RPM) + traza de delta. Es lo que **cuantifica**
efectos (p.ej. fl_hot ≈ -15% → ΔPW). No empezado.

## Pendientes menores
- `Fan_Duty_Pct` en modo compacto (opcional; el usuario lo decide).
- Afinar tunables de gestos si hace falta (graf2.js: `ZOOM_GAIN`, `PAN_GAIN`).

---

## Hallazgos validados (contexto técnico — NO re-descubrir)

Análisis del ride `47BF04_006` cruzando las 16 marcas del usuario con los datos:

- **CLT está en °C** (manual del usuario: idle 160 / fan ON 220 / fan OFF 180). Confirmado:
  el fan se activa cuando CLT≈220 en el CSV. Decode: `protocol.py` `CLT=(30,2,0.1,-40)`.
- **Enriquecimiento WOT = +10% exacto:** `WOT_Corr=110` cuando `fl_wot=1` (base 100, escala 0.1).
  `fl_wot` activo 1.7-4.1s por launch (porción WOT sostenida, no un pulso).
- **REGLA para comparar mapas (insight del usuario, crítico para "IA que ve mapas"):**
  el PW en WOT lleva ese +10%. Las comparaciones deben **segregarse por `fl_wot`**
  (y `fl_hot`/`do_fan`, ver task_061) o un mapa base pobre + corrector se ve idéntico
  a un mapa base rico sin corrector. Debe entrar en `vs_engine.py`/`f7.py`.
- **"Pérdida de señal" = bug real:** las marcas de ese tipo caen en huecos de ~11s con
  0-1 filas donde debería haber ~120. Es el bug `task_052` (timeouts en `logger_process.py`).
- **Brinco de CLT al activar el fan (~+49°C en 3s) = probable artefacto eléctrico**
  [hipótesis]: el arranque del fan jala corriente, Batt cae a 13.38V, distorsiona la
  lectura ADC del sensor resistivo de temperatura. Validar contra `Batt_V`. NO es cambio
  térmico real del metal.
- El enriquecimiento WOT es configurable en la EEPROM DDFI2 pero `eeprom.py` NO lo decodifica
  (solo VE + spark). El usuario consideró ponerlo a 0%; se le **desaconsejó** en OL sin
  wideband (riesgo de detonación a fondo).

## Norte
Esto alimenta el North Star: que el algoritmo proponga mejoras de mapa solo. Las marcas
del piloto + F7 + segregación por correctores = base para "entrenar a la IA a ver los mapas".
