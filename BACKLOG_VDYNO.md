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

1. **HUMAN-IN-THE-LOOP OBLIGATORIO.** El sistema JAMÁS escribe la EEPROM
   solo. Antes de quemar cualquier cambio SIEMPRE pregunta al usuario.
   El pipeline automático termina en: PROPUESTA VISIBLE EN EL TAB VE,
   y el usuario la carga/quema manualmente. La quemada autónoma queda
   explícitamente FUERA de alcance (también en FASE V4).
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
