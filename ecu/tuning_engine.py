#!/usr/bin/env python3
"""
ecu/tuning_engine.py — Motor de Suavizado Delta Blend (Portado del Excel VBA PRO V3)
Evita escalones en el mapa VE manteniendo la geometría original de los bins de la XB12X.
"""

def smooth_delta(base, suggested, rpm_bins, tps_bins, lam=0.25, threshold=6.0, iterations=2):
    """
    Aplica suavizado Weighted Geometric al Delta (Sugerido - Base).
    Preserva los bordes y evita aplanar zonas que no se modificaron.
    
    Args:
        base: Lista de listas 2D (Mapa VE original desde EEPROM)
        suggested: Lista de listas 2D (Mapa sugerido por el Auto-Tuner)
        rpm_bins: Lista de breakpoints de RPM (ej. [0, 800, 1000...])
        tps_bins: Lista de breakpoints de TPS (ej. [10, 15, 20...])
        lam: Factor de suavizado (0.25 = conservador, 0.4 = agresivo)
        threshold: Máximo cambio permitido por celda antes de descartar (en unidades VE)
        iterations: Veces que se aplica el suavizado (2 es ideal)
    
    Returns:
        Lista de listas 2D con el mapa final suavizado.
    """
    rows = len(base)
    cols = len(base[0]) if rows > 0 else 0
    
    if rows != len(suggested) or cols != len(suggested[0]):
        raise ValueError("Base y Suggested deben tener las mismas dimensiones")

    # 1. Copiar el mapa base intacto
    final = [row[:] for row in base]

    # 2. Calcular el Delta puro (lo que queremos cambiar)
    delta = [[suggested[i][j] - base[i][j] for j in range(cols)] for i in range(rows)]

    # 3. Suavizar SOLO el Delta (respetando bordes y geometría)
    temp_delta = [row[:] for row in delta]
    
    for _ in range(iterations):
        for i in range(1, rows - 1):  # No tocar la primera ni última fila
            for j in range(1, cols - 1):  # No tocar la primera ni última columna
                
                w_sum = 0.0
                v_sum = 0.0
                
                # Vecinos cardinales (arriba, abajo, izquierda, derecha)
                for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ni, nj = i + di, j + dj
                    
                    # Calcular distancia real basada en los bins (no asume grilla cuadrada)
                    dist_rpm = abs(rpm_bins[j] - rpm_bins[nj])
                    dist_tps = abs(tps_bins[i] - tps_bins[ni])
                    dist = dist_rpm + dist_tps
                    if dist == 0: dist = 1  # Evitar división por cero
                    
                    w = 1.0 / dist
                    w_sum += w
                    v_sum += w * delta[ni][nj]
                
                if w_sum > 0:
                    weighted_avg = v_sum / w_sum
                    d = weighted_avg - delta[i][j]
                    
                    # PROTECCIÓN CONTRA DEFORMACIÓN DE FORMA
                    # Si el salto es demasiado brusco (> threshold), no tocar la celda
                    if abs(d) < threshold:
                        temp_delta[i][j] = delta[i][j] + lam * d
                    else:
                        temp_delta[i][j] = delta[i][j]  # Mantener pico intencional
                        
        # Actualizar delta para la siguiente iteración
        delta = [row[:] for row in temp_delta]

    # 4. Aplicar el Delta suavizado al mapa original
    for i in range(rows):
        for j in range(cols):
            final[i][j] = round(base[i][j] + delta[i][j], 0)
            
    return final
