# Flujo de Instalación

1. SD limpia con Raspberry Pi OS Lite
2. Boot inicial de la Raspberry Pi
3. Ejecutar `install.sh` como usuario con permisos sudo
4. Instalación automática de dependencias del sistema
5. Configuración del hotspot WiFi persistente
6. Creación del servicio systemd del logger
7. Habilitación del arranque automático al boot
8. Reboot consciente del sistema

Resultado:
Tras el reinicio, la Raspberry Pi opera como un appliance dedicado:
- Inicia automáticamente el logger
- Expone el dashboard vía WiFi hotspot
- No requiere interacción adicional
