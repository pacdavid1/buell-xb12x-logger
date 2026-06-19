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

## Descartadas

## Convertidas a BACKLOG
