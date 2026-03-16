#!/bin/bash
# Buell DDFI2 Logger - Instalador automático
# Uso: curl -sSL https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash

set -e  # Salir ante cualquier error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Instalador del Buell DDFI2 Logger ===${NC}"

# Detectar sistema
if [ ! -f /etc/debian_version ]; then
    echo -e "${RED}Este instalador solo funciona en sistemas Debian/Raspbian.${NC}"
    exit 1
fi

# Actualizar e instalar dependencias
echo -e "${YELLOW}Actualizando lista de paquetes...${NC}"
sudo apt update

echo -e "${YELLOW}Instalando dependencias (git, python3-serial, network-manager)...${NC}"
sudo apt install -y git python3-serial network-manager

# Clonar repositorio si no existe
if [ ! -d /home/pi/buell ]; then
    echo -e "${YELLOW}Clonando repositorio...${NC}"
    cd /home/pi
    git clone https://github.com/pacdavid1/buell-xb12x-logger.git buell
else
    echo -e "${YELLOW}El directorio /home/pi/buell ya existe. Actualizando...${NC}"
    cd /home/pi/buell
    git pull
fi

cd /home/pi/buell

# Crear archivos de configuración por defecto si no existen
[ ! -f tps_cal.json ] && echo '{"min":139,"max":479}' > tps_cal.json
[ ! -f vss_cal.json ] && echo '{"cpkm25":1368}' > vss_cal.json
[ ! -f objectives.json ] && cat > objectives.json <<EOF
{
  "cell_targets": [
    {"label":"Zona media (2900-4000, Load 40-80)","rpm_min":2900,"rpm_max":4000,"load_min":40,"load_max":80,"seconds":10},
    {"label":"WOT media (2900-4000, Load 80+)","rpm_min":2900,"rpm_max":4000,"load_min":80,"load_max":255,"seconds":5}
  ],
  "indicators": {"max_cht":250,"min_duration_s":300}
}
EOF

# Configurar hotspot
echo -e "${YELLOW}Configurando hotspot WiFi...${NC}"
if ! sudo nmcli con show buell-hotspot &>/dev/null; then
    # Generar SSID basado en hostname (últimos 4 caracteres)
    SSID="buell-$(hostname -s | tail -c 5)"
    PASSWORD="buell2024"
    sudo nmcli con add type wifi ifname wlan0 mode ap con-name buell-hotspot ssid "$SSID" password "$PASSWORD"
    sudo nmcli con modify buell-hotspot 802-11-wireless.band bg
    sudo nmcli con modify buell-hotspot ipv4.method shared
    echo -e "${GREEN}Hotspot creado: SSID=$SSID, contraseña=$PASSWORD${NC}"
else
    echo -e "${GREEN}El perfil buell-hotspot ya existe.${NC}"
fi

# Configurar servicio systemd
echo -e "${YELLOW}Configurando servicio systemd...${NC}"
sudo tee /etc/systemd/system/buell-logger.service > /dev/null <<EOF
[Unit]
Description=Buell DDFI2 Logger
After=network.target
Wants=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/buell/ddfi2_logger.py
WorkingDirectory=/home/pi/buell
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable buell-logger
sudo systemctl restart buell-logger

# Verificar estado
if sudo systemctl is-active --quiet buell-logger; then
    echo -e "${GREEN}✓ Servicio del logger iniciado correctamente.${NC}"
else
    echo -e "${RED}✗ Error al iniciar el servicio. Revisa con: sudo systemctl status buell-logger${NC}"
    exit 1
fi

echo -e "${GREEN}=== Instalación completada ===${NC}"
echo -e "Puedes acceder al dashboard en: ${YELLOW}http://10.42.0.1:8080${NC}"
echo -e "Conéctate a la WiFi con SSID: ${YELLOW}$SSID${NC} y contraseña: ${YELLOW}$PASSWORD${NC}"
echo -e "Si necesitas cambiar la contraseña, edita el script o modifica el perfil con nmcli."
