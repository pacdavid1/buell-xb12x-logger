<!-- INST
purpose: exploratory ideas — threads, not tasks
action:  read-only reference; never auto-convert to BACKLOG
         user decides which idea to pull; when they do, move entry to BACKLOG
add:     one entry per session max, only from creative mode or end-of-session finds
delete:  never (entries move to BACKLOG or Descartadas, file persists)
INST_END -->
# IDEAS.md — Vertientes sin explorar

> Generado por Claude en modo creativo o al cerrar sesiones.
> No son tareas. Son hilos. El usuario decide cuál jalar.
> Cuando una idea se convierte en tarea → mover a BACKLOG.md

## Pendientes de evaluar

### IDEA-001 — Kalman Filter fusión VSS + GPS
**Señal:** VS_KPH + gps_speed_kmh (ambas en CSV, nunca fusionadas)
**Técnica:** Filtro de Kalman — combina señales ruidosas con
pesos dinámicos según confianza de cada fuente
**Aplica a:** dv/dt para VDYNO — el talón de Aquiles actual
**Por qué importa:** mejor aceleración estimada = mejor dyno virtual

### IDEA-002 — Causal inference para veredicto de quemada
**Señal:** todas las variables ambientales + mapa + resultado
**Técnica:** inferencia causal (DoWhy, DAGs) — distingue
"mapa B produce más potencia" de "mapa B causa más potencia"
**Aplica a:** VDYNO veredicto — actualmente es correlación pura
**Por qué importa:** con ruido ambiental alto, la causalidad
es lo único que da veredicto confiable

### IDEA-003 — Estilo de manejo como señal, no como ruido
**Señal:** secuencias de TPS, RPM, gear a lo largo del tiempo
**Técnica:** Hidden Markov Models — detectar estados latentes
(agresivo, suave, ciudad, carretera) sin reglas hardcodeadas
**Aplica a:** normalización de comparaciones cross-session
**Por qué importa:** dos rides del mismo mapa con estilos
distintos no son comparables — HMM los clasifica automáticamente

### IDEA-004 — Fan + Voltage durante WOT: el estabilizador olvidado
**Señal:** Fan_Stat + Voltage + pw1 + spark1 (todas en CSV, nunca correlacionadas)
**Técnica:** Ventana deslizante — medir delta_V durante eventos WOT vs fan ON/OFF
**Aplica a:** VDYNO consistencia — pulls con fan ON tienen alternador bajo carga
**Por qué importa:** El fan consume ~3-4A. Si el voltaje cae durante un WOT pull porque el fan estaba encendido, la bobina recibe menos energía → chispa más débil → menos potencia. El VDYNO podría estar comparando pulls con fan ON vs OFF sin saberlo. Fan_Stat se loggea pero no se usa en ningún análisis.

### IDEA-005 — CDiag como minería de fallos incipientes
**Señal:** CDiag bytes (5 bytes, 40 bits de diagnóstico — loggeados pero nunca minados)
**Técnica:** Análisis de frecuencia — ¿qué bits de CDiag se activan en rides previas a un DTC?
**Aplica a:** Mantenimiento predictivo — detectar fallos eléctricos/actuadores antes de que fallen
**Por qué importa:** La ECU pone bits de diagnóstico mucho antes de encender la CEL. Podrían predecir: inyector degradándose, bobina perdiendo aislamiento, fallo de bujía incipiente. Todos los CDiag y HDiag bytes se descartan hoy.

### IDEA-006 — Micro-ciclos térmicos: CLT + fl_hot + do_fan como modelo de sistema
**Señal:** CLT + fl_hot + do_fan (todas loggeadas, nunca modeladas juntas)
**Técnica:** Modelo de primer orden — CLT(t) = CLT_inf + (CLT_0 - CLT_inf) * exp(-t/τ)
**Aplica a:** Normalización de comparaciones — etiquetar cada evento F7 con estado térmico real
**Por qué importa:** do_fan se cicla (CLT sube-baja ~6°C de histéresis). Un evento F7 en subida térmica (fan OFF) vs bajada (fan ON) son condiciones distintas. Hoy se clasifican igual si CLT > 80°C.

### IDEA-007 — gps_heading como etiquetador de tramo
**Señal:** gps_heading (rumbo cardinal absoluto, 0-360)
**Técnica:** Agrupar eventos F7 por heading → mismo tramo de ruta, diferentes sesiones
**Aplica a:** Normalización cross-session — comparar el mismo tramo elimina ruido geográfico
**Por qué importa:** gps_heading se loggea pero nadie lo analiza. En una ruta conocida, heading identifica exactamente qué segmento se estaba manejando, permitiendo comparar PW en ese tramo exacto entre sesiones con distintos mapas.

### IDEA-008 — fl_cam_active como filtro de calidad de ignición
**Señal:** fl_cam_active (flag de sensor de leva sincronizado)
**Técnica:** Si fl_cam_active se desactiva durante WOT, marcar ese evento F7 como baja confianza
**Aplica a:** F7 event quality — descartar eventos donde la sincronía de leva se perdió
**Por qué importa:** Si el sensor de leva pierde sincronía, el timing de chispa/inyección puede estar desfasado. La curva PW de ese evento no es confiable. Nadie lo verifica hoy.

### IDEA-009 — VSS_Count raw tiene más resolución que VS_KPH
**Señal:** VSS_Count (contador crudo de pulsos VSS, 0-255)
**Técnica:** Usar raw count en vez de VS_KPH para mediciones de corta distancia (lanzamientos)
**Aplica a:** Launch analysis — distancias <50m tienen error grande con KPH redondeado
**Por qué importa:** VS_KPH se deriva de VSS_Count pero redondea y filtra. El raw count tiene cuantización de ~1.2 km/h por pulso. Para aceleración en ventanas de 1-2s, el raw es mejor señal. VSS_Count se loggea pero nunca se usa directamente.

### IDEA-010 — ETS_ADC como ventana a la combustión real
**Señal:** ETS_ADC (sensor de temperatura de escape, ADC crudo)
**Técnica:** Correlacionar ETS + spark1 + pw1 — si ETS sube sin cambio de PW, hay combustión anómala
**Aplica a:** Detección de knocking sin sensor de knock — escape más caliente indica detonación
**Por qué importa:** ETS es el único sensor que mide calor real de salida del cilindro. Sin knock sensor, es la mejor señal indirecta de detonación. Nunca se usa en análisis.

### IDEA-011 — cpu_temp como indicador de calidad serial
**Señal:** cpu_temp + dirty_byte_count + tasa de error
**Técnica:** Correlación temporal — cuando cpu_temp > 75°C, ¿aumenta la tasa de dirty_bytes?
**Aplica a:** Diagnóstico de desconexiones — explicar patrones de pérdida de datos
**Por qué importa:** El FTDI puede tener errores cuando la Pi se calienta. Ambas señales están en el CSV. Si hay correlación, explica ciertos patrones de desconexión sin causa identificada hoy.

### IDEA-012 — do_coil + spark como detector de fallo de ignición
**Señal:** do_coil1/do_coil2 (comando ECU) + spark1/spark2 (avance real)
**Técnica:** Si do_coil1=1 pero spark1 no sube → ECU ordena pero no ejecuta
**Aplica a:** Mantenimiento predictivo — detectar bobina o bujía degradada antes de que falle
**Por qué importa:** La ECU ordena chispa (do_coil) pero el avance real (spark) es independiente. Una divergencia persistente es un DTC incipiente que nadie está minando.

### IDEA-013 — Perfil RPM como huella de estilo de manejo
**Señal:** Tiempo acumulado por celda (RPM × Load) del CellTracker
**Técnica:** Vector de distribución — % de tiempo en cada bin como feature de 12 dimensiones
**Aplica a:** Normalización cross-session — clasificar rides por perfil antes de comparar
**Por qué importa:** El CellTracker ya acumula tiempo por celda. Ese vector es una huella del estilo. Dos sesiones con mapas diferentes pero estilos diferentes no son directamente comparables. Similar a IDEA-003 (HMM) pero más simple — usa datos ya calculados.

### IDEA-014 — gps_turning como filtro de calidad en eventos F7
**Señal:** gps_heading_rate (Fase 2 GPS) — tasa de cambio de rumbo en deg/s durante el evento
**Técnica:** Filtrar eventos F7 donde el pre-event window incluye gps_turning=True
**Aplica a:** f7.py event detection — el detector actual asume que la moto va recto
**Por qué importa:** Un evento WOT en curva mezcla carga lateral con carga longitudinal.
La curva PW en curva no es comparable con PW en recta aunque RPM/TPS sean iguales.
Hoy se clasifican igual. Si gps_heading_rate > 15 deg/s durante el pre-event, el
evento debería marcarse como `quality: TURNING` y excluirse del promedio cross-session.
**Dato clave:** Require Fase 2 GPS (gps_heading_rate). Sin GPS, no se puede implementar.
**Impacto esperado:** Reduce ruido en comparaciones cross-session de eventos con motos
que toman curvas rápido antes del WOT (típico en calles de ciudad).

### IDEA-015 — GPS quality score compuesto como gate único para todo análisis
**Señal:** gps_mode + gps_epx + gps_snr_avg + gps_stale (Fase 1 + Fase 2 GPS)
**Técnica:** Score 0–1: `(mode==3)*0.4 + (epx<8)*0.3 + (snr_avg>30)*0.2 + (!stale)*0.1`
**Aplica a:** Cualquier análisis que consuma GPS: Sessions VS alt classification,
F7 event quality, VDYNO track mapping, BL-BUG-02 VSS calibration
**Por qué importa:** Hoy cada consumidor de GPS tiene su propio criterio ad-hoc:
launch.py usa `gps_valid`, BL-BUG-02 propone `hdop < 2.0`, Sessions VS usa `gps_valid`.
Un score único evita que se implemente n veces con distintos umbrales.
Threshold sugerido: `gps_quality >= 0.6` para análisis de precisión, `>= 0.4` para logging.
**Requiere:** Fase 1 (epx) + Fase 2 (snr_avg) ambas en CSV — ver BL-GPS-01 en BACKLOG.

## Descartadas

## Convertidas a BACKLOG
