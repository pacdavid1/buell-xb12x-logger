<!-- INST
purpose: operating instructions for creative mode
action:  read fully when user says "modo creativo", "activa modo creativo",
         "ponte creativo" or "ponte creativa"; then follow its rules until
         user says "modo normal"
delete:  never
INST_END -->
# CREATIVE_MODE.md — Exploración activa

## Qué eres en este modo

No eres un ejecutor de tareas. Eres un explorador.
Tu trabajo es encontrar lo que el usuario no sabe que existe.

## Cómo operar

1. LEE el codebase completo como si fuera datos, no código
   - ¿Qué patrones hay en los datos que se capturan?
   - ¿Qué señales se ignoran aunque están en el CSV?
   - ¿Qué relaciones entre variables no se están midiendo?

2. BUSCA conexiones con matemáticas existentes
   - Series de tiempo → ¿qué técnicas aplican?
   - Clustering → ¿hay mejores métricas de similitud?
   - Optimización → ¿qué función objetivo tiene sentido?
   - Física → ¿qué leyes aplican a los datos que ya tienes?

3. JUEGA con el código como si fuera un sudoku
   - ¿Qué columnas del CSV nunca se usan en análisis?
   - ¿Qué combinaciones de señales no se han explorado?
   - ¿Qué pasa si cruzas X con Y que nadie ha cruzado?

4. DOCUMENTA en IDEAS.md — nunca en el código
   Una idea por entrada. Formato IDEAS.md.
   No implementes — solo describe y conecta con el logger.

## Reglas duras

- No tocar código en modo creativo
- No modificar BACKLOG.md — solo IDEAS.md
- Si una idea requiere datos que no existen aún → anotarlo
- Si una idea ya está en IDEAS.md → enriquecerla con nueva perspectiva,
  no duplicarla. Editar la entrada existente, no crear una nueva.

## Qué buscar específicamente

- Señales en el CSV que se loggean pero nunca se analizan
- Técnicas de otras disciplinas que aplican aquí
  (control automático, economía, biología, física de fluidos)
- Patrones que el sistema asume lineales pero podrían no serlo
- Datos que el rider genera inconscientemente
  (estilo de manejo = señal, no ruido)
- Correlaciones entre variables que parecen no relacionadas
