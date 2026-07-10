# Sesión 2026-07-06 — Fable5 Rescue Analysis + Replay Sim

> Objetivo: comparar buell (original) vs buell_fable5 (fork), identificar qué
> rescatar, y construir un simulador de replay para comparar mapas.
> 
> Hallazgo principal: el simulador de replay no funciona como se esperaba
> por un problema de acoplamiento dinámico — documentado abajo.

---

## 1. Comparación buell vs buell_fable5

Se analizaron ambos repos archivo por archivo. Resumen:

### Archivos que AGREGA fable5 (rescatables)

| Archivo | Propósito | Líneas |
|---------|-----------|--------|
| `measure/__init__.py` | Package init + public API | ~20 |
| `measure/__main__.py` | CLI: events/steady/compare | ~80 |
| `measure/schema.py` | CSV loading con detección de capacidades | ~100 |
| `measure/physics.py` | Cinemática + fuerzas con metadata honesta | ~120 |
| `measure/events.py` | Steady states + step events con calidad | ~200 |
| `measure/compare.py` | Cross-session matching por TPS RMSE | ~150 |
| `tests/test_measure.py` | 7 golden tests con respuestas analíticas | ~120 |
| `docs/CALC_AUDIT.md` | Auditoría formal de cálculos (5 hallazgos mayores) | ~300 |
| `MASTER_PLAN.md` | Plan estratégico de 3 fases | ~100 |
| `research/pw_model/` | Modelo PW M5 (R²=0.957) + validación | 20+ archivos |
| `BACKLOG_FABLE5_RESCUE.md` | Este documento de backlog | ~400 |

### Archivos que ELIMINA fable5 (vs original)

| Archivo | Nota |
|---------|------|
| `web/f7.py` | FASE 7 event detection |
| `web/launch.py` | Launch detection |
| `web/vdyno.py` | Virtual dyno (reemplazable por measure/physics.py) |
| `web/vs_engine.py` | Session comparison (tiene bug C1: ECO sign) |
| `web/proposal.py` | Map proposal |
| `web/handlers/sessions.py` | Session handler |
| `web/handlers/tuner.py` | Tuner handler |
| `web/handlers/vdyno.py` | Vdyno handler |
| 6 templates HTML | Session events, Sessions VS, Tuner, etc. |

### Hallazgo crítico: bug C1 en vs_engine.py

El modo ECO **elige la mapa más rica** (signo invertido en `_build_ci()`).
`eco = 'A' if delta < 0` → cuando B inyecta MENOS (delta negativo), A gana ECO.
ECO selecciona la sesión que inyecta MÁS combustible — exactamente lo opuesto
a lo que el nombre sugiere.

**Decisión del usuario:** ignorar ECO. Enfocarse en SPORT (máxima aceleración).

---

## 2. Torneo de sesiones round-robin

Se ejecutó `python -m measure compare` en fable5 para las sesiones con más datos.

### Eventos por sesión

| Sesión | Rides | Eventos ok | Suspects |
|--------|-------|-----------|----------|
| 248AE2 | 23 | 78 | 7 |
| 653DC0 | 14 | 47 | 0 |
| 47BF04 | 16 | 34 | 3 |
| 91B225 | 8 | 9 | 3 |
| 243FAC | 6 | 9 | 0 |
| 1E447A | 4 | 4 | 1 |

### Resultados del torneo

```
653DC0 ─┬─ vs 248AE2 →  GANA 3-0  (+15.2, +8.4, +3.4 kph)
        ├─ vs 47BF04  →  1 match: 47BF04 gana (-10.1 kph)  
        └─ vs 91B225  →  0 matches

248AE2 ─┬─ vs 653DC0 →  PIERDE 0-3
        ├─ vs 47BF04  →  3 matches: EMPATE 1-1-1
        └─ vs 91B225  →  GANA 1-0

47BF04 ─┬─ vs 248AE2 →  EMPATE 1-1-1
         ├─ vs 653DC0 →  GANA 1-0  (-10.1 kph)
         └─ vs 91B225  →  0 matches
```

**La sesión más fuerte parece ser 653DC0.** Ganó TODOS los buckets contra
248AE2. Pero con n=1 en la mayoría de buckets, la confianza es baja.

### Mapa 653DC0 vs OEM (BUEIB310)

Se comparó el XPR OEM contra el EEPROM de 653DC0:
- **140 celdas diferentes** en fuel_front (>5 unidades de diferencia)
- 653DC0 es **masivamente más rico**: diferencias de +14 a +31 unidades
- OEM promedio: ~55 unidades | 653DC0 promedio: ~72 unidades

---

## 3. Replay Simulator (`tools/replay_sim.py`)

### Qué se construyó

Un script que carga un ride CSV real + mapas "what-if" (XPR o EEPROM de otra
sesión) y simula el PW que se habría inyectado en cada punto del ride si la
moto hubiera tenido ese otro mapa.

### Componentes

1. **Map decoder** — usa `ecu.eeprom.decode_eeprom_maps()` para leer XPR/EEPROM
2. **Bilinear interpolation** — lookup de (RPM, TPS) → fuel map value (0-250)
3. **Correction ratio** — preserva las correcciones de la ECU (WUE, AE, EGO)
4. **PW Model M5** — `PW = -2.664 + 0.001278·veCurr + (-0.00336)·veCurr/RPM + ...`
5. **HTML output** — Chart.js interactive charts

### Resultado de la simulación

```
Ride: 653DC0 ride_001 (7021 filas válidas)
PW real medio: 4.286 ms

OEM (BUEIB310):  0.862 ms  (-79.9%)  LEANER
47BF04:          0.872 ms  (-79.7%)  LEANER
```

### 🚫 Hallazgo: por qué NO funciona

**Problema fundamental de acoplamiento dinámico:**

El simulador asume que el rider INPUT (TPS trace) determina el RPM en cada
punto. Pero en realidad:

```
TPS (input) → MAP lookup → PW → Torque → Aceleración → RPM cambia
                                                          |
                                                   Próximo lookup
                                                   usa nuevo RPM
```

Si el mapa alternativo inyecta MENOS combustible:
1. La moto acelera MENOS
2. Las RPM suben MÁS LENTO
3. El siguiente lookup en el mapa (RPM×TPS) es DISTINTO
4. La trayectoria completa diverge

**El simulador ignora el paso 2-4.** Usa el RPM real del ride original,
que asume una aceleración que el mapa simulado no puede producir. Por eso
la diferencia de 80% es absurda — el ride real con 653DC0 aceleró hasta
ciertas RPM porque inyectaba MUCHO combustible. Si inyectara como OEM,
nunca habría alcanzado esas RPM.

### Conclusión

La simulación de "replay" con RPM fijo **no es válida**. Para simular
correctamente el efecto de un mapa diferente, se necesita un modelo
dinámico completo:
- Modelo de torque del motor (PW → torque)
- Modelo de transmisión (torque → aceleración → RPM → velocidad)
- Integración temporal paso a paso

Eso está fuera del alcance actual del proyecto. **Puerta cerrada.**

---

## 4. Lo que queda vivo (próximos pasos)

### Para implementar en buell original

| Prioridad | Item | Archivo | Esfuerzo |
|-----------|------|---------|----------|
| 🔴 HIGH | Fix C1 (ECO sign) | vs_engine.py:196 | 1 línea |
| 🟡 MEDIUM | Integrar measure/ | measure/ (5 archivos) | 1 sesión |
| 🟡 MEDIUM | Portar golden tests | tests/test_measure.py | Bajo |
| 🟡 MEDIUM | Ranking por celda (torunéo) | measure/compare.py ya lo hace | CLI |
| 🟢 LOW | PW model endpoint | web/pw_model.py | Medio |

### Herramientas creadas hoy

| Archivo | Propósito |
|---------|-----------|
| `tools/replay_sim.py` | Simulador de replay (no funcional por acoplamiento dinámico) |
| `docs/BACKLOG_FABLE5_RESCUE.md` | 11 backlog entries detallados |
| `docs/2026-07-06_FABLE5_RESCUE_SESSION.md` | Este documento |

### Ranking por celda (el camino correcto)

La alternativa que sí funciona y que el usuario identificó:

1. Por cada sesión, extraer eventos measure → buckets RPM×TPS
2. Dentro de cada bucket, calcular PW medio por sesión
3. Rankear: menor PW para la misma aceleración = mejor
4. Construir híbrido: por cada celda, tomar el valor de la sesión rankeada #1
5. Guard: solo mezclar celdas de sesiones con mismo contexto (WUE, AE, Batt)

Esto no requiere simulación — usa datos REALES de cada sesión.
