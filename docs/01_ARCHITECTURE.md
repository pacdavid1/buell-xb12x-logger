# Arquitectura del Sistema

## Capas
1. Raspberry Pi OS Lite
2. NetworkManager (hotspot)
3. systemd (servicio)
4. Backend Python (ddfi2_logger.py)
5. Servidor HTTP embebido

## Filosofía
El sistema (network + arranque) es responsabilidad del OS,
no del código Python.
