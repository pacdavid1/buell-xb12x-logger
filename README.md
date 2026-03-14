# Buell XB12X — DDFI2 ECU Logger

> Raspberry Pi Zero 2W · FT232RL USB-Serial · Python 3 · 9600,8N1

Data logger en tiempo real para la ECU Delphi DDFI2 de la Buell XB12X.
Captura, almacena y visualiza más de 60 parámetros del motor a ~8Hz,
con dashboard web accesible desde cualquier dispositivo en la misma red.

---

## ¿Qué hace?

- **Captura RT** — lee la trama de 107 bytes del protocolo DDFI2 a ~8Hz
- **Dashboard web** en `http://[IP-Pi]:8080` con datos en vivo
- **Gráficas por ride** — RPM/KPH/CLT, correcciones de combustible, avance de encendido, pulso de inyectores, TPS, batería
- **Heatmap VE** — visualiza los mapas de combustible y encendido leídos del EEPROM
- **Sesiones** — cada arranque del motor es un ride independiente, agrupados por sesión (versión de ECU)
- **Error log** — registro estructurado de dirty bytes, timeouts y reconexiones por ride
- **Detector de marcha** — calcula la marcha actual (1ª–5ª) por ratio KPH/RPM
- **Reconexión automática** — DTR toggle + USB reset escalado si la ECU se pierde

## Parámetros capturados (selección)

| Parámetro | Descripción |
|-----------|-------------|
| RPM, Load | Régimen y carga del motor |
| CLT, MAT | Temperatura culata y aire de admisión |
| TPS%, TPD | Posición del acelerador calibrada |
| spark1/2 | Avance de encendido °BTDC por cilindro |
| pw1/2 | Pulso de inyectores ms por cilindro |
| EGO_Corr, AFV, WUE | Correcciones de combustible en tiempo real |
| VS_KPH, Gear | Velocidad y marcha calculada |
| Batt_V | Voltaje de batería |
| fl_hot, fl_decel, fl_wot | Flags de estado ECU |
| DTC | Códigos de falla activos |

## Hardware

```
Buell XB12X
  └── Conector diagnóstico (bajo asiento)
        └── FT232RL USB-Serial (9600,8N1)
              └── Raspberry Pi Zero 2W
                    └── WiFi → Dashboard web (cualquier browser)
```

## Instalación

```bash
# Clonar el repositorio
git clone git@github.com:pacdavid1/buell-xb12x-logger.git
cd buell-xb12x-logger

# Instalar dependencia
pip install pyserial

# Ejecutar
python3 ddfi2_logger.py --port /dev/ttyUSB0 --sessions /home/pi/buell/sessions
```

## Estructura de archivos generados

```
sessions/
└── [checksum-ECU]/
    ├── ride_001.csv              # Datos RT completos
    ├── ride_001_summary.json     # Resumen del ride
    ├── ride_001_notes.txt        # Notas del piloto (opcional)
    └── ride_001_errorlog.json    # Errores de comunicación (solo si los hubo)
```

## Protocolo DDFI2

Protocolo propietario Delphi sobre serial RS232 a 9600,8N1.
Implementación basada en ingeniería inversa de
[EcmDroid](https://github.com/ecmdroid/ecmdroid) (referencia de offsets y PDUs).

Trama RT: `SOH [len] [cmd] [data×107] [checksum] EOT`

## Versión actual

`v1.16.1` — ver [CHANGELOG.md](CHANGELOG.md) para historial completo.

## Licencia

MIT — libre para uso personal y comunitario.
Si lo usas en tu Buell, un star en el repo se agradece 🏍️
