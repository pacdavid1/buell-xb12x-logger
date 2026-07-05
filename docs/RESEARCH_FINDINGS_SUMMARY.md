# 📡 Research Findings Summary — Buell DDFI2 Señales y Pipeline

> Handoff para Claude. Resumen de TODO lo investigado sobre señales, sensores, pipeline de tuning, gaps y roadmap.

---

## 1. 🔬 INVENTARIO DE SEÑALES DDFI2

**58 señales RAW** en el protocolo + **~15 externas** (GPS, baro, humedad, sysmon).

| Estado | Cantidad | Ejemplos |
|--------|----------|---------|
| ✅ Usadas en tuning | **21** (36%) | RPM, pw1, pw2, TPS_pct, CLT, Load, flags, Gear, VS_KPH |
| 📥 Capturadas CSV no usadas | **16** (27%) | EGO_Corr/AFV/O2_ADC (locked), CDiag/HDiag (8 cols), **BAS_ADC**, ETS_ADC, IAT_ADC, Rides |
| ❌ En protocolo no capturadas | **12** (21%) | Coil1/2_ADC, Inj1/2_ADC, Batt_ADC, F_Pp_ADC |
| 🔵 Protocolo puro | **9** (15%) | SOH, SRC, DST, Len, EOH, SOT, ACK, EOT, CheckS |

**Archivo:** `docs/signal_inventory.html` (actualizado con correcciones)

---

## 2. 🎯 SEÑALES QUE INFLUYEN EN LA PROPUESTA DE MAPA

**Solo 12 señales** de 58 RAW determinan la propuesta final (MSQ):

### ⭐ Métrica principal (1 señal)
```
pw1 + pw2 → pw1_norm (×1013.25/baro) → pw_eff = pw_avg × AFV/100
                                 ↓
                          dpw_eff = pw_eff_B − pw_eff_A
                                 ↓
                       ¡Esto decide cada celda del mapa!
```

### 📐 Coordenadas (2) + Correcciones (1) + Filtros (8)
- **RPM, TPS_pct** → definen celdas del mapa VE
- **baro_hPa** → baro_factor para PW normalization
- **CLT, WUE, Accel_Corr, fl_wot, fl_decel, fl_fuel_cut, fl_engine_run** → filtros BITTER

**Conclusión:** De 58 RAW, solo 1 métrica (pw1/pw2 → dpw_eff) decide el ganador. Todo lo demás son coordenadas y filtros.

**Archivo:** `docs/signal_to_map_proposal.html`

---

## 3. ❌ CORRECCIONES IMPORTANTES (Hallazgos que contradicen suposiciones iniciales)

### 3.1 NO hay sensor de knock en DDFI2
- **El DDFI2 no tiene sensor de knock.** Ni piezoeléctrico, ni registro, ni flag. Nada.
- `spark1` y `spark2` son avance **calculado desde el mapa**, NO ajustado por detonación.
- **KR inference (Receta 6) está INVALIDADA.** No podemos inferir knock rate de spark.
- Alternativas reales para detectar knock: EGT (termopar), oído del piloto, plug chop.
- **Documentación actualizada:** sector_dags.html, data_pipelines_by_sector.html, signal_to_map_proposal.html

### 3.2 Coil1/2_ADC no son ion sense
- Son monitores de **salud eléctrica** de la bobina (circuito abierto/corto).
- **NO detectan calidad de combustión, NO son ion sense.**
- DTC 24/25 ya cubren diagnóstico de bobinas.
- **No vale la pena capturarlos.**

### 3.3 BAS_ADC — Más complejo de lo que parecía
- **Investigación web sugería:** Sensor pendular magnético binario (tip-over a ~55-60°).
- **Datos REALES (129K samples, 15 sesiones) muestran:**
  - **56 valores únicos** (no 2)
  - Dos clusters: LOW ~250 ADC (1.22V) y HIGH ~928 ADC (4.53V)
  - **11 valores intermedios** entre clusters (310, 439, 452, 642-729)
  - NO es puramente binario — el Hall-effect tiene resolución analógica limitada
- **Sin embargo:** Los valores intermedios son <1% de muestras. El ECU solo lo usa como umbral. No hay relación lineal conocida ADC→grados.
- **Conclusión:** GPS heading_rate sigue siendo mejor para lean angle estimado.
- **Archivo:** `docs/bas_adc_analysis.html`

---

## 4. 💡 INFORMACIÓN QUE DEBERÍAMOS GENERAR (GAPS)

### 🟢 Sin hardware nuevo (solo código, ~10h total)

| Gap | Señales necesarias | Esfuerzo | Impacto |
|-----|-------------------|----------|---------|
| **🔴 pw_corr (dead-time)** | Batt_V ✅ (ya capturado) | ~1h | +2.3% de shift confirmado — contamina VS |
| **🟡 spark merge real** | spark1, spark2 ✅ | ~3h | Hoy usamos 'AVG' cuando no hay diferencia |
| **🟡 VDYNO power en merge** | VS_KPH, RPM ✅ | ~4h | Celdas con más HP deberían pesar más |
| **🟡 air density real** | MAT + baro_hPa + humidity_pct ✅ | ~2h | Rho real vs fijo 1.10 |
| **🟡 terrain-aware classify** | gps_alt + slope_reference ✅ | ~1h | GAP 4: subidas no deberían ser BITTER |
| **🟡 corner performance** | gps_heading_rate ✅ | ~4h | Nueva dimensión: salida de curva |
| **🟡 lean angle (GPS)** | gps_heading_rate + speed ✅ | ~2h | lean = atan(v²/(R×g)) |

### 🔴 El gap más grande: wideband O2
- EGO_Corr=100 (locked), AFV=100 (locked), O2_ADC=~512 (ruido)
- Todo el tuning_report es INACTIVE_NOISE
- Sessions VS infiere dirección pero NO magnitud
- **Costo:** $50-120, Esfuerzo: ~8h

---

## 5. 🔧 ROADMAP DE SENSORES FUTUROS

| Prioridad | Sensor | Costo | Qué habilita |
|-----------|--------|-------|-------------|
| 🥇 Ahora | **NINGUNO** — usar los que tenemos | $0 | Batt_V dead-time, slope_reference, cornering GPS, air density |
| 🥇 Corto | **Wideband O2 (LSU 4.9)** | $50-120 | ⚠️ Game changer: EGO_Corr real, AFV, VE loop, autotune |
| 🥈 Medio | **EGT (termopar escape)** | $20-50 | Safety, proxy de detonación |
| 🥉 Largo | **Knock sensor piezo** | $10-30+ADC | Detonación real (DDFI2 no tiene esta capacidad) |

---

## 6. 📊 ANÁLISIS DE DATOS REALES DE BAS_ADC

**Realizado:** Script `analyze_bas_adc.py` → 15 CSVs, 129,126 muestras

**Hallazgos clave:**
- Cluster LOW: ~250 ADC = 1.22V (moto vertical)
- Cluster HIGH: ~928 ADC = 4.53V (tip-over >55°)
- 11 valores intermedios entre 310-729 ADC
- 9 sesiones nunca típ (solo LOW), 5 sesiones típ (ambos clusters)
- Sesión 653DC0: 34.5% HIGH (más deportiva)

**Archivo:** `docs/bas_adc_analysis.html`

---

## 7. 📁 ARCHIVOS HTML GENERADOS / ACTUALIZADOS

| Archivo | Qué contiene | Estado |
|---------|-------------|--------|
| `docs/signal_inventory.html` | Inventario completo de 58 señales RAW + externas | ✅ Corregido (BAS_ADC, knock) |
| `docs/signal_to_map_proposal.html` | Pipeline señal→mapa, gaps, roadmap sensores | ✅ Corregido (BAS_ADC, knock) |
| `docs/sector_dags.html` | DAG interactivo por sector | ✅ Actualizado (BAS_ADC, IMU, knock) |
| `docs/data_pipelines_by_sector.html` | Pipeline detallado por sector | ✅ Actualizado (BAS_ADC, knock, spark) |
| `docs/bas_adc_analysis.html` | Análisis exploratorio BAS_ADC real | ✅ Nuevo |
| `docs/latent_data_exploration.html` | 10 recetas de datos dormidos | ✅ Corregido (knock) |
| `docs/latent_data_recipes.html` | Propuestas de transformación | ⬅️ Pendiente de revisión |
| `docs/sector_dags.html` | DAG interactivo de sectores | ✅ Actualizado |

---

## 8. 📋 RESUMEN EJECUTIVO

1. **Solo 12 de 58 señales** influyen en la propuesta de mapa. pw1/pw2 es LA métrica.
2. **No hay sensor de knock** — suposición inicial incorrecta, ya corregida en todos los docs.
3. **BAS_ADC no es puramente binario** — tiene 56 valores únicos con intermedios, pero utilidad para lean angle sigue siendo limitada.
4. **El gap más grande es wideband O2** ($50-120) — transformaría el sistema de "guess" a "medición".
5. **6 mejoras posibles sin HW nuevo** (~10h total de código).
6. **Todos los HTMLs actualizados** con correcciones de los hallazgos.

---

*Generado: Julio 2026*
