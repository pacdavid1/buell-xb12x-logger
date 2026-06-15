# Prompt para Claude — Análisis de Arquitectura EcmDefs

Copia y pega esto en una sesión de Claude (codebuff, claude.ai, etc.) para
que analice el problema y proponga la arquitectura ideal.

---

## Contexto

Eres un arquitecto de software especializado en sistemas embebidos para
motocicletas Buell con ECU DDFI2. Necesito tu ayuda para diseñar un sistema
que permita que el logger ECU funcione con MÚLTIPLES firmwares de ECU,
no solo con el BUEIB actual.

## El problema

Actualmente, TODO está hardcodeado para el firmware BUEIB (ECU de la XB12X):
- ~50 parámetros escalares con offsets fijos en BUEIB_PARAMS
- 8 mapas/ejes con offsets y dimensiones fijas en decode_eeprom_maps
- 6 páginas EEPROM fijas en BUEIB_PAGES
- RPM_BINS (13 valores) y LOAD_BINS (12 valores) fijos en protocol.py
- ~40 RT_VARIABLES con offsets fijos dentro del frame serial de 107 bytes

## El hallazgo

Existen 14 archivos XML de EcmSpy en ecu_defs/ que definen la estructura
COMPLETA de la EEPROM para diferentes firmwares. Al analizarlos,
descubrimos que hay 3 familias de ECU con estructuras drásticamente diferentes:

### Grupo 1: 13×12 con separador (BUEIB-like)
BUEIB, B2RIB, BUECB, BUEGB
- Fuel map: 13 cols × 12 rows, stride=14 (13 datos + 1 separador)
- RPM axis: 13 valores (2 bytes c/u)
- Load axis: 12 valores (1 byte c/u)

### Grupo 2: 13×12 denso (sin separador)
BUEGC, BUEIA, BUEKA
- Fuel map: 13 cols × 12 rows, stride=13 (denso, sin separador)
- Mismas dimensiones pero diferente formato de almacenamiento

### Grupo 3: 20×16 fuel + 12×8 secondary
BUE1D, BUE2D, BUE3D, BUEWD, BUEYD, BUEZD, BUEOD
- Fuel map: 20 cols × 16 rows (12x13 en BUEIB!)
- RPM axis: 20 valores
- Load axis: 16 valores
- 2nd Fuel Map: 12 cols × 8 rows (NO existe en BUEIB)

### Dato crítico
De las entradas que aparecen en 3+ firmwares, 217 tienen OFFSETS DIFERENTES
entre firmwares y solo 10 comparten el mismo offset.

## Archivos actuales a modificar

### ecu/eeprom.py
- BUEIB_PARAMS (~50 parámetros con offset hardcodeado)
- decode_eeprom_maps() — 8 offsets fijos para mapas y ejes
- encode_eeprom_maps() — 4 offsets fijos para escritura
- _validate_eeprom() — validación con offsets fijos

### ecu/connection.py
- BUEIB_PAGES — 6 páginas EEPROM con rangos fijos

### ecu/protocol.py
- RPM_BINS, LOAD_BINS — arrays de ejes fijos
- RT_VARIABLES — ~40 parámetros RT con offset en frame serial

### ecu/session.py
- CellTracker — importa RPM_BINS/LOAD_BINS como constantes de módulo
- _rebuild_summary — usa bins fijos para reconstruir rides
- _generate_suggested_msq — usa bins fijos para sugerencias

### Archivo NUEVO necesario
- ecu/ecm_defs.py — parser de XML EcmSpy, loader, factory

## Lo que necesito que hagas

1. **Diseña la clase EcmDefs** — estructura, métodos, factory
2. **Propón la arquitectura** de cómo fluyen los datos desde que se detecta
   la versión de la ECU hasta que se usan los offsets correctos
3. **Analiza el riesgo** de RT_VARIABLES — los XMLs de EcmSpy definen la
   EEPROM, pero NO sabemos si también definen el layout del frame RT
   (107 bytes en tiempo real). ¿Cómo investigar esto?
4. **Propón la migración** — orden de implementación para no romper
   la funcionalidad existente mientras se agrega soporte multi-firmware
5. **Diseña la UI dinámica** — el heatmap del tuner debe adaptarse a
   13×12, 20×16, 12×8 según el firmware detectado
6. **Estrategia de testing** — cómo verificar que los offsets del XML
   coinciden con la EEPROM real de la ECU

## Archivos de referencia (en ecu_defs/)

Los 14 XMLs están en ecu_defs/:
- BUEIB.xml, B2RIB.xml (Grupo 1, stride=14)
- BUECB.xml, BUEGB.xml (Grupo 1, stride=14)
- BUEGC.xml, BUEIA.xml, BUEKA.xml (Grupo 2, stride=13, denso)
- BUE1D.xml, BUE2D.xml, BUE3D.xml (Grupo 3, 20×16 + 12×8)
- BUEWD.xml, BUEYD.xml, BUEZD.xml (Grupo 3, 20×16 + 12×8)
- BUEOD.xml (Grupo 3, 20×16 + 12×8)
- files.xml (catálogo de firmwares)

## Documentación adicional

Ver inbox/ecm_defs_refactor.md para el análisis completo de los 14 XMLs,
el inventario de hardcodeos, y el plan de implementación tentativo.
