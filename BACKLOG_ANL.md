# BACKLOG_ANL — Analysis & Tuning Pipeline
Separado de BACKLOG.md que cubre funcionalidad core.
Este backlog cubre el pipeline de análisis de datos y tuning del mapa VE.

Status: OPEN / IN-PROGRESS / CLOSED vX.X.X

---

**BACKLOG-ANL1** `PARTIAL` — CellTracker base funcionando
EGO heatmap por celda

### Done
- CellTracker acumula valid_seconds, confidence, clt_avg, wue_avg, afv_avg, inv_reasons
- Filtros de validez: WUE>102, CLT<70°C, RPM<1200, AFV fuera de rango, decel, fuel_cut, TPS_delta>5%
- snapshot() emite campos de calidad completos en cada summary.json

### Pending
- Overlay visual en dashboard (tab VE) coloreado por confidence/suggestion

---

**BACKLOG-ANL2** `OPEN`
O2_ADC rich/lean overlay en VE heatmap

### Problem
El heatmap VE muestra tiempo en celda pero no calidad de mezcla.
O2_ADC > 128 = rico, < 128 = pobre — útil como segunda señal además de EGO_Corr.

### Prerequisites
BACKLOG-ANL1 pipeline puede reutilizarse.

---

**BACKLOG-ANL3** `OPEN`
Export heatmap desde dashboard

### Problem
Generación de heatmap requiere herramientas externas.
Debería exportarse directo desde el dashboard como JSON o CSV.

### Context
- New endpoint en web/server.py
- Matriz 13 RPM × 12 Load bins — mismos ejes que EEPROM

---

**BACKLOG-ANL4** `CLOSED` — hoy
Tuning report incremental automático

### Done
- analyze_session.py — script standalone para procesar todos los CSVs de una sesión
- _update_tuning_report() en session.py — se ejecuta al cerrar cada ride
- Solo procesa rides con formato nuevo (valid_seconds en cells) — rides viejos ignorados
- Agrega agg_cells incrementalmente sin reprocesar CSVs
- Calcula suggestion por celda: factor, error_pct, action (subir/bajar VE)
- Target EGO diferenciado: WOT=95%, crucero=100%, parcial=100%
- AFV global promedio con acción sugerida si fuera de rango 95-105%
- Output: sessions/CHECKSUM/tuning_report_CHECKSUM.json

---

**BACKLOG-ANL5** `OPEN`
Tab de Tuning en dashboard

### Problem
El tuning_report existe en disco pero no hay UI para verlo.
Hay que abrir SSH para revisar sugerencias.

### Context
- Nueva tab "TUNING" en index.html
- Tabla RPM×Load coloreada por confidence (gris=sin datos, azul=poca conf, verde=ok)
- Celdas con suggestion resaltadas: verde=subir VE, rojo=bajar VE, número=factor
- Botón refresh que lee /tuning_report endpoint
- Muestra AFV global y acción sugerida al tope

### Prerequisites
BACKLOG-ANL12 (endpoint /tuning_report)

---

**BACKLOG-ANL6** `OPEN`
Ride válido flag para tuning

### Problem
Si CLT nunca llegó a 70°C el ride no es apto para tuning pero igual
se incluye en el reporte. Contamina el agregado con datos de motor frío.

### Context
- session.py close_current_ride() — agregar campo valid_for_tuning al summary
- Condición: al menos 30s con CLT >= 70°C durante el ride
- _update_tuning_report() — skip rides con valid_for_tuning=False
- Dashboard: badge en lista de rides indicando si es apto

---

**BACKLOG-ANL7** `OPEN`
Score de salud por ride

### Problem
No hay un número único que resuma la calidad del ride.
Hay que revisar múltiples campos para saber si algo estuvo mal.

### Context
- Componentes: EGO dispersión, CLT max, DTCs activos, AFV promedio, % datos válidos
- Score 0-100, visible en lista de rides y en header durante el ride
- Umbral: <70 = revisar, 70-90 = normal, >90 = excelente

---

**BACKLOG-ANL8** `OPEN`
AFV drift tracking ride a ride

### Problem
El AFV puede derivar lentamente (desgaste de bomba, altura, etc.)
sin que sea obvio en un solo ride.

### Context
- Graficar AFV promedio por ride en orden cronológico
- Si tendencia > 3% en 5 rides consecutivos: alerta
- Visible en tab de sesiones o tab de tuning

---

**BACKLOG-ANL9** `OPEN`
Análisis front vs rear cylinder independiente

### Problem
La Buell tiene 2 inyectores independientes (pw1/pw2, veCurr1/veCurr2).
El análisis actual los trata como uno solo usando EGO_Corr global.

### Context
- Separar acumuladores por cilindro en CellTracker
- pw1/veCurr1 = front, pw2/veCurr2 = rear
- Detectar desequilibrio entre cilindros por celda

---

**BACKLOG-ANL10** `OPEN`
Sugerencia de próximo ride

### Problem
No hay guía de qué zonas del mapa necesitan más datos.
El rider no sabe qué tipo de manejo maximiza la cobertura útil.

### Context
- Leer tuning_report, identificar celdas con confidence < 0.3
- Agrupar por zona: "necesitas más WOT entre 3000-5000 RPM"
- Mostrar en dashboard como checklist antes de salir

---

**BACKLOG-ANL11** `OPEN`
Comparar sesiones — moto roja vs azul

### Problem
Dos motos (#651 y #235) con diferente estado de tune.
No hay forma de comparar sus mapas o comportamiento celda por celda.

### Context
- Script compare_sessions.py — toma dos CHECKSUM, genera diff por celda
- Campos: ego_avg, valid_ego_avg, confidence, suggestion — lado a lado
- Output JSON o tabla ASCII

---

**BACKLOG-ANL12** `OPEN`
Endpoint /tuning_report en dashboard

### Problem
Ver el tuning_report requiere SSH. Debe ser accesible desde el browser.

### Context
- GET /tuning_report — retorna tuning_report_CHECKSUM.json de la sesión activa
- web/server.py — handler simple, mismo patrón que /maps o /eeprom_params

---

**BACKLOG-ANL13** `OPEN`
Export tuning_report como CSV

### Problem
El JSON no es fácil de leer para análisis rápido o para compartir.

### Context
- GET /tuning_report?format=csv
- Columnas: celda, zona, seconds, valid_seconds, confidence, ego_avg, valid_ego_avg, suggestion_factor, action
- Una fila por celda, ordenado por zona + valid_seconds desc

---

**BACKLOG-ANL14** `OPEN`
Watchdog de espacio en disco

### Problem
La SD puede llenarse silenciosamente. Los CSVs crecen ~2MB por ride.
Sin alerta el logger falla sin aviso cuando se llena.

### Context
- main.py o web/server.py — chequear df cada 5 min
- Si < 500MB libre: warning en log + badge en dashboard header
- Si < 100MB: parar grabación de rides nuevos, alerta crítica

---

**BACKLOG-ANL15** `OPEN`
Compresión automática de CSVs viejos

### Problem
CSVs de rides viejos ocupan espacio innecesario una vez que el summary existe.

### Context
- Script o cronjob: gzip rides con más de 7 días
- Dashboard sigue funcionando — leer .csv.gz con gzip.open()
- analyze_session.py debe soportar .gz también

---
