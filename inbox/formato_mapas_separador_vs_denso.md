# Formato de Mapas VE: Separador (0x00) vs Denso

## Fecha
2026-06-14

## Contexto

Los mapas de combustible en el EEPROM de la ECU DDFI2 pueden almacenarse
en dos formatos diferentes, dependiendo del firmware. Usar el formato
incorrecto al leer o escribir produce datos corruptos.

## Los dos formatos

### Formato con separador (BUEIB, B2RIB, BUECB, BUEGB)

Cada fila del mapa ocupa `cols + 1` bytes en el EEPROM:
- `cols` bytes de datos (valores VE en orden descendente de RPM)
- 1 byte separador `0x00`

```
EEPROM raw:
  offset 0: [dato_12][dato_11]...[dato_0][0x00]  ← fila 0 + separador
  offset 14: [dato_12][dato_11]...[dato_0][0x00]  ← fila 1 + separador
  ...
```

- Stride = `cols + 1` (14 para un fuel map 13×12)
- Size = `rows × (cols + 1)` (168 para fuel map 13×12)
- El separador **no se lee**, solo se salta al calcular el offset de cada fila
- Al escribir, el separador **no se toca** — solo se modifican los `cols` bytes de datos

### Formato denso (BUEGC, BUEIA, BUEKA)

Cada fila del mapa ocupa exactamente `cols` bytes — **no hay separador**:

```
EEPROM raw:
  offset 0: [dato_12][dato_11]...[dato_0]  ← fila 0, sin separador
  offset 13: [dato_12][dato_11]...[dato_0]  ← fila 1, sin separador
  ...
```

- Stride = `cols` (13 para fuel map 13×12)
- Size = `rows × cols` (156 para fuel map 13×12)

### Grupo 20×16 + 2do mapa (BUE1D, BUE2D, BUE3D, BUEWD, BUEYD, BUEZD, BUEOD)

Todos los mapas en este grupo son **densos** (sin separador):
- Fuel maps 20×16: size=320, stride=20 (cols)
- 2nd Fuel maps 12×8: size=96, stride=12 (cols)
- Spark maps no existen en este grupo (usar naming diferente)

## ¿Qué pasa si usas el stride incorrecto?

Ejemplo con mapa 13×12 real:

| Formato | Size | Stride correcto | Código actual (si stride=14) |
|:-------:|:----:|:---------------:|:---------------------------:|
| Separador | 168 | 14 (cols+1) | ✅ Correcto |
| Denso | 156 | 13 (cols) | ❌ **Incorrecto** |

Si se lee un mapa denso con stride=14:
- Fila 0 → offset 0 + 13 datos → **OK** (cabe en los 13 bytes)
- Fila 1 → offset 14 + 13 datos → **lee 1 byte de fila 0 + 12 de fila 1**
- Fila 2 → offset 28 + 13 datos → cada vez más desplazado
- Fila 11 → offset 154 + 13 = 167 → **FUERA DEL MAPA** (size=156)

Si se ESCRIBE con stride=14 en un mapa denso:
1. El byte `0x00` del separador sobrescribe el primer dato de la siguiente fila
2. Todos los datos quedan desplazados 1 byte por fila
3. Al leerlo después con stride=13, TODO sale incorrecto
4. **Corrupción garantizada de datos**

## Cómo detectar el formato automáticamente

El XML de EcmSpy ya contiene toda la información necesaria:

```python
stride = size // rows
if stride == cols + 1:
    formato = "separador"  # BUEIB-like
elif stride == cols:
    formato = "denso"      # BUEGC, BUE1D, etc.
else:
    raise ValueError(f"Stride {stride} no coincide con cols {cols}")
```

Solución: `read_map()` y `write_fuel_map()` deben usar el stride desde
las definiciones del XML, no calcularlo como `cols + 1`.

## Los spark maps

Los mapas de chispa (spark_front, spark_rear) son SIEMPRE densos en
todos los firmwares. El código actual ya los maneja con `read_map_spark()`
que usa `rows * cols` (sin separador). Esto no necesita cambio.

## Resumen de strides por grupo

| Grupo | Fuel Map | Stride | Fórmula |
|:-----:|:--------:|:-----:|:-------:|
| BUEIB, B2RIB, BUECB, BUEGB | 168 bytes | **14** | cols + 1 (separador) |
| BUEGC, BUEIA, BUEKA | 156 bytes | **13** | cols (denso) |
| BUE1D-BUEOD (fuel) | 320 bytes | **20** | cols (denso) |
| BUE1D-BUEOD (2nd fuel) | 96 bytes | **12** | cols (denso) |
| Spark maps (todos) | 100 bytes | **10** | cols (denso) |

