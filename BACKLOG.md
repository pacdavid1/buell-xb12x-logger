# BACKLOG — Buell Logger / Tuner

## FASE 1 — Merge RAW de mapas
- [ ] Auto-detección de qué mapa cambió entre sesiones (comparar eeprom.bin byte a byte)
- [ ] Si cambió más de 1 mapa → marcar como "no atribuible", no generar merge
- [ ] Merge RAW por celda:
  - SWEET → tomar mapa que gana en dpw_eff (ECO/fuel)
  - SPICY_WOT → tomar mapa que gana en ddvss (SPORT/accel)
  - SPICY_TIPIN/TIPOUT → ignorar (AE activo, mapa no manda)
  - Sin datos → promedio de ambos mapas (neutro)
- [ ] Etiquetar cada celda: `A` / `B` / `AVG` (origen del dato)
- [ ] Visualización en Tuner Studio: 4ta pestaña "MERGED" al lado de BASE/DELTA/MOD
- [ ] Exportar merge como JSON descargable

## FASE 2 — Suavizado asimétrico del merge
- [ ] Detectar transiciones A↔B o A/B↔AVG (fronteras entre orígenes)
- [ ] Suavizado DIRECCIONAL: siempre hacia el pico sugerido, nunca en contra
  - Pico más alto que vecinos → vecinos se bajan hacia el pico
  - Pico más bajo que vecinos → vecinos se suben hacia el pico
  - Pico entre dos valores → interpolar hacia el lado correcto
- [ ] Respetar celdas del mismo origen (ya vienen suaves de fábrica)
- [ ] Parámetro de intensidad del suavizado (lambda)
- [ ] Comparación visual antes/después del suavizado

## FASE 3 — MPU6050 (vibración FR/RR)
- [ ] Hardware: MPU6050 + cables al Pi (I2C: VCC 3.3V, GND, SDA, SCL)
- [ ] Montaje: chasis aluminio (triángulo delantero o subchasis), con aislamiento goma
- [ ] Driver: lectura I2C a ~100-200Hz, integrar al loop del logger
- [ ] CSV: agregar columnas accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
- [ ] Sessions VS: nueva métrica de vibración por bin RPM/TPS
- [ ] Merge de spark: usar vibración como métrica "quién gana" para balance FR/RR
- [ ] Flujo: cambiar spark_front → ride → comparar vibración → decidir si mejoró

## FASE 4 — Exportar mapa mergeado
- [ ] Generar .msq compatible con ECMSpy desde el merge suavizado
- [ ] Opción de exportar solo 1 mapa (ej: solo fuel_front)
- [ ] Validación: no exceder rangos válidos del ECU (0-250 fuel, 0-45 spark)

## NOTAS / REGLAS
- Solo mover UN mapa a la vez entre sesiones (fuel_front, fuel_rear, spark_front, spark_rear)
- Si se mueven 2+ mapas → datos no atribuibles → no merge
- Knock sensor: NO por ahora (ruido mecánico alto en Buell air-cooled, falsos positivos)
- Spark sin knock: tunear por dACC (si avanzás spark y aceleración sube sin subir vibración, no hay knock)
