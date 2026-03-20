#!/bin/bash
# Buell DDFI2 Logger - Instalador automático
# Uso:
#   curl -sSL https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash

set -e

# ─────────────────────────────────────────────────────────────
# Colores
# ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Instalador del Buell DDFI2 Logger ===${NC}"

# ─────────────────────────────────────────────────────────────
# Verificar sistema
# ─────────────────────────────────────────────────────────────
if [ ! -f /etc/debian_version ]; then
    echo -e "${RED}Este instalador solo funciona en sistemas Debian/Raspbian.${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# Dependencias
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}Actualizando lista de paquetes...${NC}"
sudo apt update

echo -e "${YELLOW}Instalando dependencias (git, python3-serial, network-manager)...${NC}"
sudo apt install -y git python3-serial python3-flask network-manager avahi-daemon avahi-utils

# ─────────────────────────────────────────────────────────────
# Clonar / actualizar repo
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
# Configuración por defecto
# ─────────────────────────────────────────────────────────────
[ ! -f network_state.json ] && echo '{"mode":"hotspot","ip":"10.42.0.1"}' > network_state.json
[ ! -f tps_cal.json ] && echo '{"min":139,"max":479}' > tps_cal.json
[ ! -f vss_cal.json ] && echo '{"cpkm25":1368}' > vss_cal.json

if [ ! -f objectives.json ]; then
cat > objectives.json <<EOF
{
  "cell_targets": [
    {"label":"Zona media (2900-4000, Load 40-80)","rpm_min":2900,"rpm_max":4000,"load_min":40,"load_max":80,"seconds":10},
    {"label":"WOT media (2900-4000, Load 80+)","rpm_min":2900,"rpm_max":4000,"load_min":80,"load_max":255,"seconds":5}
  ],
  "indicators": {"max_cht":250,"min_duration_s":300}
}
EOF
fi

mkdir -p /home/pi/buell/sessions
INSTALL_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
chown -R "${INSTALL_USER}:${INSTALL_USER}" /home/pi/buell

# ─────────────────────────────────────────────────────────────
# Hotspot WiFi (forzado y verificado)
# ─────────────────────────────────────────────────────────────

SSID="buell-$(hostname -s | tail -c 5)"
PASSWORD="buell2024"

echo -e "${YELLOW}Configurando hotspot WiFi...${NC}"

# Asegurar que WiFi no esté bloqueado
sudo rfkill unblock wifi || true
sudo ip link set wlan0 up || true

# Crear perfil si no existe
if ! sudo nmcli con show buell-hotspot >/dev/null 2>&1; then
    sudo nmcli con add type wifi ifname wlan0 mode ap con-name buell-hotspot ssid "$SSID"
    sudo nmcli con modify buell-hotspot 802-11-wireless.band bg
    sudo nmcli con modify buell-hotspot ipv4.method shared
    sudo nmcli con modify buell-hotspot wifi-sec.key-mgmt wpa-psk
    sudo nmcli con modify buell-hotspot wifi-sec.psk "$PASSWORD"
    echo -e "${GREEN}Perfil de hotspot creado.${NC}"
else
    SSID=$(nmcli -g 802-11-wireless.ssid con show buell-hotspot)
    echo -e "${GREEN}Perfil buell-hotspot ya existe (SSID=$SSID).${NC}"
fi

# Forzar activación del hotspot
echo -e "${YELLOW}Activando hotspot WiFi...${NC}"

sudo nmcli radio wifi off
sleep 2
sudo nmcli radio wifi on
sleep 2

sudo nmcli con down buell-hotspot >/dev/null 2>&1 || true
sudo nmcli con up buell-hotspot

# Verificación final
sleep 2
if nmcli con show --active | grep -q buell-hotspot; then
    echo -e "${GREEN}✓ Hotspot activo y emitiendo.${NC}"
else
    echo -e "${RED}✗ No se pudo activar el hotspot automáticamente.${NC}"
    echo -e "${YELLOW}Intentando recuperación...${NC}"

    sudo systemctl restart NetworkManager
    sleep 5
    sudo nmcli con up buell-hotspot

    if nmcli con show --active | grep -q buell-hotspot; then
        echo -e "${GREEN}✓ Hotspot activo tras recuperación.${NC}"
    else
        echo -e "${RED}✗ Hotspot no pudo ser activado.${NC}"
        echo -e "${RED}Revisa NetworkManager o el driver WiFi.${NC}"
    fi
fi

# ─────────────────────────────────────────────────────────────
# Servicio systemd
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}Configurando servicio systemd...${NC}"
sudo tee /etc/systemd/system/buell-logger.service >/dev/null <<EOF
[Unit]
Description=Buell DDFI2 Logger
After=network.target
Wants=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/buell/main.py --port /dev/ttyUSB0 --sessions-dir /home/pi/buell/sessions --buell-dir /home/pi/buell
WorkingDirectory=/home/pi/buell
Restart=on-failure
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
EOF

# Regla polkit para que el servicio pueda apagar la Pi sin contraseña
sudo mkdir -p /etc/polkit-1/rules.d
sudo tee /etc/polkit-1/rules.d/99-buell-poweroff.rules >/dev/null <<\'POLKIT\'
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.login1.power-off" &&
        subject.user == "pi") {
        return polkit.Result.YES;
    }
});
\'POLKIT\'
sudo systemctl restart polkit

# Permisos sudoers para systemctl restart sin contraseña
echo "${INSTALL_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart buell-logger" | sudo tee /etc/sudoers.d/buell-poweroff
sudo chmod 440 /etc/sudoers.d/buell-poweroff

sudo systemctl daemon-reload
sudo systemctl enable buell-logger
sudo systemctl restart buell-logger

if sudo systemctl is-active --quiet buell-logger; then
    echo -e "${GREEN}✓ Servicio del logger iniciado correctamente.${NC}"
else
    echo -e "${RED}✗ Error al iniciar el servicio.${NC}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# Mensajes finales
# ─────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}=== Instalación completada ===${NC}"
echo -e "Conéctate a la WiFi con:"
echo -e "  SSID: ${YELLOW}$SSID${NC}"
echo -e "  Contraseña: ${YELLOW}$PASSWORD${NC}"
echo -e "Dashboard: ${YELLOW}http://10.42.0.1:8080${NC}"
echo
echo -e "${YELLOW}Si estás conectado por SSH, la conexión se cerrará al reiniciar.${NC}"
echo

# ─────────────────────────────────────────────────────────────
# Función de confirmación (compatible con curl | bash)
# ─────────────────────────────────────────────────────────────
ask_yes_no() {
    local PROMPT="$1"
    local ANSWER=""

    while true; do
        printf "%s [Y/YES/N/NO]: " "$PROMPT" > /dev/tty
        if ! read -r ANSWER < /dev/tty; then
            ANSWER="no"
        fi
        ANSWER=$(echo "${ANSWER:-no}" | tr '[:upper:]' '[:lower:]')
        case "$ANSWER" in
            y|yes) return 0 ;;
            n|no)  return 1 ;;
            *) echo "Respuesta no válida. Escribe Y, YES, N o NO." > /dev/tty ;;
        esac
    done
}

echo -e "${YELLOW}⚠️  Confirmación antes del reinicio${NC}"
echo

ask_yes_no "¿Ya anotaste el SSID y la contraseña del hotspot WiFi?"
C1=$?
ask_yes_no "¿Sabes que después del reinicio debes abrir http://10.42.0.1:8080?"
C2=$?
ask_yes_no "¿Confirmas que estás listo para reiniciar ahora?"
C3=$?

if [[ $C1 -eq 0 && $C2 -eq 0 && $C3 -eq 0 ]]; then
    echo -e "${YELLOW}Reiniciando el sistema...${NC}"
    sleep 3
    sudo reboot
else
    echo -e "${GREEN}Reinicio cancelado. Puedes reiniciar manualmente con: sudo reboot${NC}"
fi
``
