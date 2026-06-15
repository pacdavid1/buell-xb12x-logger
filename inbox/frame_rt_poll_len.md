# Frame RT (Real-Time) — poll_len y diferencias entre firmwares

## Fecha
2026-06-14

## Hallazgo crítico

El `files.xml` en `ecu_defs/` revela que el **tamaño del frame RT cambia**
entre firmwares. El campo `poll_len` define el tamaño en bytes.

## Tabla de tamaños por firmware

| Grupo | FW | poll_len | Generación |
|:-----:|:--:|:--------:|:----------:|
| DDFI (1ra gen) | BUEIA | **100** | DDFI |
| DDFI (1ra gen) | BUEKA, BUEJA, BUEGC | **99** | DDFI |
| DDFI-2 | BUECB | **103** | DDFI-2 |
| DDFI-2 | BUEIB, BUEIC, B2RIB, BUEGB | **107** | DDFI-2 ← tu ECU |
| DDFI-3 | BUEOD, BUEWD, BUEYD, BUEZD, BUE1D, B3R1D, BUE2D, B3R2D, BUE3D, B3R3D | **135** | DDFI-3 |

## Implicaciones

1. **RT_VARIABLES actual SOLO funciona para DDFI-2 con poll_len=107**
   - Los ~40 offsets dentro del frame de 107 bytes NO son válidos para otros firmwares
   - Para DDFI (99-100 bytes), los offsets son diferentes
   - Para DDFI-3 (135 bytes), hay más variables y los offsets cambiaron

2. **No tenemos las definiciones RT para otras familias**
   - Los XMLs de EcmSpy en `ecu_defs/` solo definen la EEPROM (memoria no volátil)
   - Las definiciones RT están en archivos `.adx` de TunerPro RT
   - No hay archivos .adx en el repositorio

3. **Estrategia para el refactor**
   - El refactor EcmDefs (EEPPROM) sigue adelante porque los XMLs tienen TODA la info
   - RT_VARIABLES se queda como está, documentado como "DDFI-2 only"
   - Cuando se necesite soportar otra ECU físicamente, buscar los .adx correspondientes

## Referencias

- files.xml en ecu_defs/ contiene poll_len para todos los firmwares
- Los archivos .adx de TunerPro RT son la fuente para mapear el frame RT
- La nomenclatura DDFI/DDFI-2/DDFI-3 no está oficialmente documentada
  pero los campos ddfi y category en files.xml lo confirman

