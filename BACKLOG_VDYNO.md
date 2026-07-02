# BACKLOG — VDYNO: dyno virtual + veredicto de quemada

> NORTE DEL PROYECTO (confirmado por el usuario 2026-06-11): medir la
> potencia del motor; que el sistema recolecte en cada ride, compare entre
> rides/mapas, y al final proponga mejoras solo. Este backlog es el puente
> entre los análisis que ya existen (F7, Sessions VS) y ese norte.
>
> La tesis: con VS_KPH + RPM + gear + baro_hPa + baro_temp_c + gps_alt_m
> que YA están en el CSV, la física alcanza para estimar potencia en rueda
> en cada pull. No se necesita dyno ni wideband para COMPARAR mapas — la
> potencia relativa A vs B es el veredicto objetivo que le falta al ciclo
> LOG → ACOTAR → COMPARAR → PROPONER → QUEMAR.

---

## La física (todo ya está en el CSV)

```
P_rueda = (m·a  +  ½·ρ·CdA·v²  +  Crr·m·g  +  m·g·sin(θ)) · v
           ↑          ↑               ↑            ↑
        inercia    aero drag      rodadura     pendiente
```

| Término | Fuente de datos | Notas |
|---------|----------------|-------|
| v, a    | VS_KPH (derivada suavizada) | a = dv/dt con Savitzky-Golay o ventana |
| ρ (densidad aire) | baro_hPa + baro_temp_c (+ humidity_pct) | ¡por esto importan los BMP280/AHT20! |
| θ (pendiente) | gps_alt_m derivada vs distancia | el término que nadie compensa en la calle |
| m (masa total) | config: moto + piloto + tanque (fuel_tracker!) | fuel_tracker ya estima litros restantes |
| CdA, Crr | constantes config (~0.60 m², ~0.015) | el error absoluto da igual, ver abajo |
| RPM → T_motor | T = P/ω, con pérdida transmisión ~8-10% | torque en rueda → torque motor por marcha |

**Clave: el error absoluto no importa.** Si CdA real es 0.55 y pusimos
0.60, los HP absolutos salen 5% corridos — PERO el delta entre mapa A y
mapa B con MISMA moto y MISMO piloto es limpio. El dyno virtual es un
instrumento DIFERENCIAL, igual que toda la filosofía Sessions VS.

---

## FASE V1 — Curva de potencia por ride

### BL-VD-01 — web/vdyno.py: motor de cálculo
**Priority:** HIGH
- Entrada: ride CSV + eventos F7 WOT (ya detectados — son exactamente los
  segmentos estables que sirven: gas fijo, marcha fija)
- Por evento: serie P(t) y T(RPM); filtrar muestras con fl_decel,
  clutch, cambios de marcha (gear_detected inestable)
- Salida: ride_*_vdyno.json — curva P y T binned por RPM (bins de 250)
  con n muestras y σ por bin + condiciones (ρ media, temp, masa estimada)
- Mismo patrón lazy/cache que f7.py para cuidar la RAM de la Pi Zero

### BL-VD-02 — Pantalla "Dyno" (o subtab en Sessions VS)
**Priority:** HIGH
- Curva HP/torque vs RPM por ride, overlay de 2+ rides/sesiones
- Selector igual que Sessions VS (A vs B) — al comparar dos MAPAS:
  ΔP por bin de RPM con banda de confianza
- Es la gráfica que todo tuner entiende: "el mapa nuevo da +2.3 HP
  de 4000 a 5500 RPM y pierde 0.8 arriba de 6500"

## FASE V2 — Normalización ambiental

### BL-VD-03 — Corrección SAE J1349 / densidad
**Priority:** MEDIUM
- Normalizar curvas a condiciones estándar (ρ₀) para comparar rides de
  días distintos con clima distinto — el Alpha-N sin baro comp hace que
  esto sea doblemente importante en esta moto
- Mostrar "density altitude" del ride como stat (conecta BL-UX-03)

## FASE V3 — Veredicto de quemada (cierra el ciclo)


### BL-VD-05 — Veredicto automático post-ride
**Priority:** HIGH
- Tras cerrar un ride con mapa "hijo": comparar automáticamente contra
  los rides del mapa "padre" (del burn ledger):
  - ΔP por bin RPM (vdyno) en celdas tocadas por la quemada
  - dpw_eff de Sessions VS en esas mismas celdas
  - condiciones matched: CLT caliente, density altitude similar
- Salida visible en el Dashboard al terminar el ride:
  "BURN #7: +1.8 HP @4500-5500 (conf 82%) · 3 celdas sin datos aún"
  VERDE = mejor / ROJO = peor / GRIS = faltan datos (y QUÉ datos faltan:
  "necesitas un pull WOT en 3a de 4000 a 6000")
- Esto convierte cada vuelta en un experimento con resultado — el sistema
  literalmente te dice qué ride hacer para completar la evidencia

## FASE V4 — Propuesta autónoma (el norte)
- Con vdyno (objetivo físico) + VS cells (dirección por celda) + burn
  ledger (historial causa→efecto), el motor de propuestas FASE 6 deja de
  ser heurístico: optimiza PW por celda hacia max potencia observada,
  con el historial de quemadas como conjunto de entrenamiento
- Cada iteración del ciclo afina el modelo: pasito a pasito, pies firmes
- ALCANCE MÁXIMO (regla 1): la propuesta llega al tab VE con checksum
  nuevo y AHÍ TERMINA — cargar y quemar es siempre decisión manual del
  usuario

---

## DECISIONES DE DISEÑO (usuario, 2026-06-11) — REGLAS DURAS

1. **HUMAN-IN-THE-LOOP = REVISIÓN Y APROBACIÓN, NO AUTORÍA DE VALORES.**
   (Aclarado 2026-07-02 — misma regla de siempre, precisada porque FASE 5.1
   se prestaba a leerse como "el usuario edita celdas a mano".)
   El sistema JAMÁS escribe la EEPROM solo. Pero el usuario tampoco decide
   a mano cuánto subir o bajar una celda — no tiene más base que la data,
   y la data es exactamente lo que el sistema ya procesa. El rol humano es:
     (a) decidir QUÉ información calcular / qué análisis construir, en
         colaboración con la IA (nuevas señales, nuevos cruces, nuevas
         iteraciones de propuesta) — esto SÍ es trabajo activo del usuario;
     (b) REVISAR la propuesta completa antes de quemarla (heatmap de diff,
         confianza por celda, qué cambió y por qué);
     (c) aprobar o rechazar la quemada — un click, no una edición celda
         por celda.
   El editor manual celda-por-celda (FASE 5.1 en BACKLOG.md) es herramienta
   de excepción/override, NO el camino principal de tuning.
   El pipeline automático termina en: PROPUESTA VISIBLE EN EL TAB VE,
   y el usuario la aprueba/quema. La quemada autónoma queda explícitamente
   FUERA de alcance (también en FASE V4).
2. **Cada propuesta = checksum/map_id NUEVO.** Así el burn ledger registra
   la genealogía padre → hijo sin ambigüedad y el veredicto sabe
   exactamente qué comparar contra qué.
3. **Glosario:** "quemada" = escribir un mapa a la EEPROM (tab VE).
   "burn ledger" = bitácora burns.json de cada quemada (celdas tocadas,
   mapa padre → hijo, fecha, sesión). Solo registra; nunca escribe ECU.
4. **Honestidad estadística:** preocupación abierta — el ruido ambiental
   (presión, temp, viento) puede ser mayor que el delta real entre mapas.
   Regla: medir primero el piso de ruido (varianza ride-a-ride DENTRO del
   mismo mapa) y solo declarar VERDE/ROJO si |ΔP| supera ese piso; si no,
   GRIS/inconcluso. El veredicto nunca se fuerza. Evaluar con datos reales.
5. **dv/dt ruidoso:** asumido, se resuelve cuando haya datos (candidatos:
   Savitzky-Golay, fusión VSS+GPS spd, mediana de múltiples pulls).
6. **Múltiples caminos de procesamiento sobre el mismo raw data (2026-07-01).**
   El raw data (CSV por ride) es el mismo sin importar cómo se procese después —
   distintas normalizaciones, fusiones o pesos de confianza son "recetas"
   distintas sobre los mismos ingredientes, no teorías en competencia que haya
   que elegir de antemano. Generar varias propuestas candidatas es barato
   (cómputo en la Pi, segundos por ride); **validar una propuesta no es
   barato** — requiere quemar la EEPROM real y salir a andar, un experimento
   a la vez (regla 1). Por eso: el cómputo puede explorar en paralelo, la
   quemada nunca. Reglas:
   - Cada propuesta candidata debe cargar el mismo rigor estadístico (piso
     de ruido regla 4, significancia GAP1 cuando aplique) — comparar una
     receta con estadística contra una sin ella no es válido.
   - Caminos que se descartan durante la exploración quedan documentados
     con la RAZÓN del descarte (no solo el resultado en el JSON) — nota de
     una línea en esta sección o comentario `# ABANDONED: razón, fecha` en
     el código. Un JSON de resultado dice qué se probó, no por qué se dejó
     de desarrollar.
   - El burn ledger ya soporta un mapa padre con múltiples hijos (log
     append-only por hash) — no hace falta rediseñarlo para ramificar.
   - Expectativa realista: no se trata de generar decenas de propuestas
     sueltas — varios caminos de procesamiento tienden a converger al mismo
     resultado o casi; el valor está en no comprometerse con una única
     normalización/fusión antes de tener evidencia real de cuál rinde mejor.
7. **ESTRATIFICAR, NO EXCLUIR (2026-07-02).** Nunca descartar data por estar
   "fuera del ideal" — separar en estratos y comparar dentro de cada estrato.
   Caso que originó la regla: el "filtro térmico" (BL-DI-06) proponía excluir
   muestras con fl_hot=1/do_fan=1; pero en una Buell aire-enfriada la
   operación normal es 160-220°C, el umbral del fan (KTemp_Fan_On) es un
   byte EDITABLE de la EEPROM (no una verdad física), y un mapa podría ganar
   precisamente en el régimen caliente — excluir borraría ese hallazgo.
   Reglas derivadas:
   - Antes de filtrar cualquier señal, MEDIR su efecto real con la data
     existente (¿el flag cambia PW/spark en celdas matched, o es dogma?).
   - hot-vs-hot y cool-vs-cool comparan; hot-vs-cool se reporta separado
     con advertencia, nunca se mezcla silenciosamente ni se tira.
   - La ÚNICA data que se descarta por completo es la que no contiene
     información física (ej. EGO_Corr/AFV con el sensor desconectado:
     constante 100.0 — un cable que no existe no es un estrato).
   - Cálculos duales baratos se hacen y se documenta si convergen (ej.
     gear por RPM/VSS y por VSS/RPM: matemáticamente recíprocos, pero el
     ruido se comporta distinto cerca de VSS≈0 — verificar, no asumir).

### BL-VD-06 — Instructor de evidencia (confirmado por el usuario)
**Priority:** HIGH — "eso estaría de lujo"
El sistema detecta qué celdas/bins de la quemada activa siguen sin datos
suficientes y emite la instrucción concreta para el próximo ride:
"falta un pull WOT en 3a de 4000 a 6000 RPM" / "faltan 2 pasadas estables
TPS 40-60% @ 3500". Vive en el Dashboard como tarjeta post-ride y/o
pre-ride ("misión del día"). Se alimenta del coverage de BL-VD-05.

### BL-VD-07 — Propuesta entregada en el tab VE (cierre del pipeline)
**Priority:** HIGH
La salida de FASE 6/V4 aparece en el tab VE como mapa staged listo para
revisar (diff visible, celdas naranja como hoy) con su checksum nuevo.
El usuario decide cargar y quemar. Nada se escribe sin su confirmación
(regla 1).

---

## Por qué este orden
1. BL-VD-01/02 dan VALOR inmediato (curva de potencia visible) sin tocar
   nada del pipeline existente — solo leen lo que ya se loggea
2. BL-VD-04 es trivial y empieza a acumular historial desde YA — cada
   quemada sin ledger es un experimento perdido
3. BL-VD-05 reusa F7 + VS + vdyno — es integración, no código nuevo
4. FASE V4 llega sola cuando V1-V3 tienen datos

## Riesgos honestos
- VSS a 10Hz puede ser ruidoso para dv/dt → suavizado obligatorio; GPS
  spd como segunda fuente (fusión simple o el que tenga menos σ)
- gps_alt_m tiene ruido de varios metros → pendiente solo con suavizado
  fuerte y rides largos; en circuito plano el término es ~0
- Viento no se puede medir → mitigar con múltiples pulls y mediana
- Pi Zero RAM: cálculo por ride al cerrarlo (no on-demand de sesiones
  completas), cache JSON como f7

---

## FASE V4 — Optimizador Iterativo de Mapas (el norte completo)

> Documentado 2026-06-27 tras análisis de sesiones 47BF04 vs 91B225.
> La filosofía: optimización sin wideband — el acelerómetro/vdyno es el
> fitness function. Se mide el resultado real (HP/torque en rueda), no el
> teórico (AFR). Mismo principio que el tuning pre-electrónica pero con
> medición objetiva en lugar de feeling del piloto.

---

### Filosofía base

**El wideband da el mejor valor teórico. El mejor valor real viene de las
iteraciones con aceleración medida.**

Señales físicas disponibles: VSS, GPS, RPM, PW, CLT, MAT, baro, gear.
Fitness function: HP/torque estimado por vdyno (aceleración real).
Guardrail de seguridad: CLT — si sube, el mapa se fue de pobre.
Sin correcciones electrónicas. Sin EGO. Sin narrowband. Solo física.

---

### Los dos modos de operación

#### MODO 1 — Híbrido (cuando existen ≥2 mapas con datos medidos)

Dado un conjunto de sesiones con mapas distintos y curvas vdyno:

1. Para cada celda del mapa (RPM_x, Load_y), identificar qué sesión
   produjo mayor HP/torque en el bin de RPM correspondiente.
2. Construir un mapa híbrido tomando el valor ganador celda por celda.
3. El híbrido es teóricamente mejor que cualquier padre — tomó lo mejor
   de cada uno. En la práctica puede tener zonas sin datos suficientes
   (ver umbral de confianza abajo).
4. Quemar el híbrido → nueva sesión → medir → si el híbrido supera a
   todos los padres en todas las zonas con datos, pasar a MODO 2.

**Regla de confianza:** si una celda tiene menos de N muestras WOT en
algún padre, no se cambia esa celda (se hereda del mapa base actual).
El sistema indica exactamente qué rides faltan para completar la evidencia
(BL-VD-06).

**El tuner puede aportar:** si el tuner hace un cambio manual agresivo
(+13% a una zona por intuición), ese resultado entra al pool. El siguiente
ciclo lo procesa via híbrido — si la zona mejoró, el híbrido lo incorpora;
si empeoró, lo ignora. El proceso digiere exploraciones humanas sin riesgo
de perder el historial base.

#### MODO 2 — Propuesta conservadora (cuando ya no hay mapas competidores)

Cuando el mapa actual supera a todos los anteriores en todas las zonas
con datos confiables:

1. Generar variantes sistemáticas: +3% global, -3% zona baja, +5% zona
   WOT, etc. Una propuesta por experimento — cambios pequeños y medibles.
2. Quemar propuesta → nueva sesión → medir vdyno → comparar contra
   baseline bajo mismas condiciones (ver normalización ambiental abajo).
3. Si la propuesta gana → nueva baseline → puede volver a MODO 1 si
   el delta es suficientemente grande para justificar un híbrido.
4. Si pierde → descartar propuesta, el baseline queda intacto.

**Gradiente implícito:** aunque no hay derivada analítica (no hay WB),
el sistema construye un gradiente empírico: +3% en zona X dio +1.2 HP,
+3% en zona Y dio -0.8 HP. Eso informa la siguiente propuesta.

---

### Atribución celda → HP (el puente técnico)

Para poder comparar sesiones celda por celda se necesita saber qué celda
del mapa estaba activa durante cada bin de potencia del vdyno.

Aproximación:
- Durante WOT a RPM_r: la celda activa es fuel_map[RPM_bucket(RPM_r)][TPS_bucket(alto)]
- El vdyno bin @ RPM_r da el HP de esa celda en esa sesión
- Cruzar con agg_cells para saber cuántos segundos WOT tuvo esa celda

Implementación: para cada vdyno bin (RPM_r, HP_med), buscar la celda del
mapa EEPROM cuyo breakpoint de RPM más se acerca a RPM_r, asumiendo carga
alta (TPS 60%+). Registrar HP_med, HP_p25, HP_p75 como fitness score de
esa celda en esa sesión.

---

### Normalización ambiental — filtros de ruido

**Problema:** el mismo mapa puede dar 78 HP un día frío a nivel del mar
y 73 HP un día caliente a 1500m. Sin normalizar, dos sesiones no son
comparables directamente.

**Factores a normalizar antes de declarar veredicto:**

| Factor | Fuente | Corrección |
|--------|--------|------------|
| Densidad del aire (ρ) | baro_hPa + baro_temp_c + humidity_pct | SAE J1349: P_corr = P_medido × (ρ₀/ρ) |
| Pendiente (θ) | gps_alt_m derivada vs distancia | m·g·sin(θ)·v se resta de P_rueda |
| Masa total | moto + piloto + fuel_tracker (litros) | afecta término inercial m·a |
| Temperatura motor | CLT_avg al inicio del pull | solo comparar pulls con CLT caliente (>80°C) |
| Viento | no medible directamente | mitigar: mediana de múltiples pulls, misma dirección |

**Regla de ruido (DECISIÓN DE DISEÑO, 2026-06-11 + ampliada 2026-06-27):**
Medir varianza ride-a-ride DENTRO del mismo mapa (mismo eeprom checksum,
misma ruta). Ese es el piso de ruido del instrumento. Solo declarar
VERDE/ROJO si |ΔHP| > 2σ del piso de ruido. Si no, GRIS/inconcluso.
El veredicto nunca se fuerza.

**Pendiente es el mayor contaminante:** un 2% de pendiente a 100 km/h
representa ~1.5 kW (~2 HP) de carga adicional. Rides en rutas con perfil
conocido son más comparables que rutas variables. Documentar la ruta de
cada sesión para poder filtrar comparaciones de ruta similar.

---

### El loop completo



---

### Backlog items nuevos de esta fase

**BL-VD-10**  — Atribuidor celda→HP
Cruzar vdyno bins con breakpoints del mapa EEPROM para obtener HP score
por celda por sesión. Salida: session_cell_scores.json por sesión.

**BL-VD-11**  — Motor híbrido
Dado ≥2 session_cell_scores.json, generar mapa híbrido con valor ganador
por celda (respetando umbral de confianza mínimo). Output: propuesta
staged en tab VE.

**BL-VD-12**  — Normalización ambiental por pull
Corregir cada segmento WOT por ρ (SAE J1349) y θ (pendiente GPS) antes
de calcular HP. Agregar density_altitude al resumen de cada vdyno.json.

**BL-VD-13**  — Piso de ruido empírico
Calcular varianza ride-a-ride del mismo checksum en la misma ruta.
Solo declarar veredicto si ΔHP > 2σ. Visible como banda de confianza en
la gráfica vdyno del verdedicto.

**BL-VD-14**  — Detector de modo (híbrido vs propuesta)
El sistema determina automáticamente en qué modo está según el burn
ledger y los session_cell_scores disponibles. Muestra en dashboard:
MODO HÍBRIDO — 2 mapas disponibles / MODO PROPUESTA — 1 mapa líder.

