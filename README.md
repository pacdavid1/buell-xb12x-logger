# Buell XB12X — DDFI2 ECU Logger

Raspberry Pi Zero 2W · FT232RL USB-Serial · Python 3 · 9600,8N1

> **Developers:** Before starting any work session, read [WORKING_METHOD.md](./WORKING_METHOD.md) first.

Real-time data logger for the **Delphi DDFI2 ECU** used in Buell XB motorcycles.

This project captures ECU data, stores it, and provides a live dashboard accessible from any device on the same network.

The long-term goal is to build an **open telemetry and tuning platform for Buell motorcycles**.

---

# What it Does

• Real-time capture — reads the 107-byte DDFI2 protocol frame at ~8Hz  
• Live web dashboard available at:  
http://[PI-IP]:8080  

• Ride graphs — RPM, KPH, CLT, ignition advance, injector pulse width, TPS, battery voltage  
• Fuel map heatmap — visualize fuel and ignition maps read from EEPROM  
• Ride sessions — every engine start becomes a new ride  
• Structured error logs — dirty bytes, timeouts, reconnection events  
• Gear detection — calculates current gear (1–5) from KPH/RPM ratio  
• Automatic reconnection — DTR toggle + USB reset if ECU connection is lost  

---

# Captured Parameters (Selection)

| Parameter | Description |
|-----------|-------------|
| RPM, Load | Engine speed and load |
| CLT, MAT | Cylinder head and intake air temperature |
| TPS%, TPD | Calibrated throttle position |
| spark1 / spark2 | Ignition advance per cylinder (°BTDC) |
| pw1 / pw2 | Injector pulse width per cylinder |
| EGO_Corr | Closed loop fuel correction |
| AFV | Adaptive fuel value |
| WUE | Warm-up enrichment |
| VS_KPH | Vehicle speed |
| Gear | Calculated gear |
| Batt_V | Battery voltage |
| fl_hot / fl_wot | ECU state flags |
| DTC | Active diagnostic trouble codes |

The logger currently records **80+ ECU parameters per cycle**.

---

# Hardware

Minimum hardware required:

• Buell XB12X motorcycle  
• Raspberry Pi Zero 2 W  
• FT232RL USB-Serial adapter  
• microSD card (32GB+ recommended)  
• USB OTG adapter  

Connection diagram:

Buell XB12X  
└── Diagnostic connector (under seat)  
  └── FT232RL USB-Serial (9600,8N1)  
    └── Raspberry Pi Zero 2 W  
      └── WiFi → Web dashboard  

---

# Installation

## Manual Installation (Current)

Clone the repository:

```
git clone https://github.com/pacdavid1/buell-xb12x-logger.git
cd buell-xb12x-logger
```

Install dependency:

```
pip install pyserial
```

Run the logger:

```
python3 ddfi2_logger.py --port /dev/ttyUSB0 --sessions /home/pi/buell/sessions
```

---

# Easy Install

One-command installation on a clean Raspberry Pi OS image:

Example:

```
curl -s https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash
```

The script will automatically:

• update the system  
• install Python dependencies  
• download the latest code  
• configure the logger  
• enable automatic startup  

---

# Preconfigured Image (Future)

A ready-to-use **Raspberry Pi image (.img)** will also be available.

Steps:

1. Download the image  
2. Flash it using Raspberry Pi Imager  
3. Insert the SD card  
4. Boot the Pi  

The logger will start automatically.

This option is designed for users with no Linux experience.

---

# Generated File Structure

Logs are stored per ECU session:

```
sessions/
└── [checksum-ECU]/
    ├── ride_001.csv
    ├── ride_001_summary.json
    ├── ride_001_notes.txt
    └── ride_001_errorlog.json
```

File descriptions:

ride_001.csv — full real-time ECU log  
ride_001_summary.json — ride summary  
ride_001_notes.txt — optional rider notes  
ride_001_errorlog.json — communication errors  

---

# DDFI2 Protocol

The Buell DDFI2 ECU uses a **Delphi proprietary protocol over RS232**.

Communication parameters:

9600 baud  
8 data bits  
no parity  
1 stop bit  

Real-time frame structure:

```
SOH [len] [cmd] [data×107] [checksum] EOT
```

The implementation is based on reverse engineering and references from **EcmDroid**.

---

# Future Goals

This project aims to evolve into a **complete telemetry platform for Buell motorcycles**.

Planned features include:

• GPS logging  
• IMU sensors (acceleration / lean angle)  
• Wideband lambda integration  
• Lap timing  
• Power estimation  
• Acceleration maps  
• Remote ride analysis  
• ECU tuning assistance  

Long-term vision:

Create an open telemetry system for Buell motorcycles similar to motorsport data loggers.

---

# Contributing

Contributions are welcome.

Possible areas:

• ECU protocol research  
• sensor integrations  
• ride analysis tools  
• dashboard improvements  
• documentation

---

# Version

Current version:

v2.1.0

See CHANGELOG.md for full history.

---

# License

MIT License.

Free for personal and community use.

If you use it on your Buell, a ⭐ on the repo is appreciated.

---

## Documentation

Detailed technical documentation, architecture decisions, and
installation flow live in the `/docs` directory of this repository.

If you are developing, debugging, or modifying the system,
start there.

---

## Installation Modes

### Development / Manual Run
This mode is intended for development and testing.
The logger is started manually using Python.

### Appliance Mode (Recommended)
The system is installed on a clean Raspberry Pi OS image

---

## Quick Start — Appliance Mode (Recommended)

The recommended way to use this project is as a dedicated headless appliance
installed on a clean Raspberry Pi OS image.

This mode is intended for users who want a plug‑and‑play system with
automatic startup, networking, and web dashboard access.

```bash
curl -sSL https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash
