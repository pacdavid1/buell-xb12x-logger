# Sensor Expansion Plan (Roadmap)

This document defines the integration of external telemetry sensors into the Buell XB12X DDFI2 Logger.

## 1. Rationale
The stock DDFI2 ECU provides critical engine data but lacks high-fidelity environmental and performance metrics (AFR, EGT, GPS, Lean Angle). This plan outlines how to bridge that gap using the Raspberry Pi's I2C/SPI/UART interfaces.

## 2. Sensor Suite

### Combustion & Tuning (High Priority)
- **Wideband O2 (Spartan 3 OEM):** For precise VE table tuning. Interface: I2C.
- **Thermocouples K-Type — mixed interfaces, corrected 2026-09-06:** hardware in
  hand is NOT a single uniform batch. Two units (boards silkscreened "HW-550")
  are confirmed **MAX6675** (SPI) — each needs its own dedicated CS line; the Pi
  Zero 2W's two native hardware chip-selects (CE0/CE1, see section 4) cover
  exactly these 2 with no GPIO expander needed. A separate, third unit is
  labeled **MAX31850** (genuine 1-Wire) — goes on GPIO4 via the kernel
  `w1-gpio`/`w1-therm` driver, unrelated to the SPI units. Net result: the rig
  needs BOTH SPI (`spidev`, 2x MAX6675) and 1-Wire (1x MAX31850) drivers, not
  either/or as earlier revisions of this doc assumed.
  Rollout plan (see `BACKLOG.md` BL-PWMODEL-01): Phase 1 non-invasive clamp
  sensors at each spark plug boss (front + rear cylinder head proxy) and each
  exhaust pipe exterior (front + rear EGT proxy); Phase 2 replaces the exhaust
  clamps with real EGT + wideband lambda sensors inside the exhaust once bungs
  are welded in.
- **Oil Pressure/Temp:** 0-5V Analog sensors via **ADS1115** (16-bit I2C ADC+PGA,
  2 units in hand as of 2026-09-06) — replaces the MCP3008/SPI plan below; I2C
  is simpler here since the bus is already in use and keeps SPI free for the
  two MAX6675 CS lines.

### Environmental (Forensic Data)
- **Airbox Condition (BME280):** Temp, Pressure, and Humidity inside the intake. Interface: I2C.
- **Ambient Condition (BME280):** External weather reference behind the dashboard. Interface: I2C.

### Dynamics
- **GPS (Ublox M8N/M9N):** For track mapping and real speed vs VSS comparison. Interface: UART.
- **IMU (LSM6DSO/MPU6050):** For Lean Angle and Braking/Acceleration G-forces. Interface: I2C.

## 3. System Requirements
To support these sensors, the host system MUST have:
1. **I2C Bus Enabled:** `dtparam=i2c_arm=on` in `/boot/config.txt`.
2. **System Packages:** `i2c-tools`, `libi2c0`, `python3-smbus`.
3. **Python Libraries:** `smbus2`, `spidev`.

## 4. Pi Zero 2W — GPIO disponibles

I2C y SPI NO están habilitados por defecto.
Habilitar via: sudo raspi-config → Interface Options

Pines físicos disponibles (sin conflicto con FT232 en USB):
- I2C: GPIO2 (SDA, pin 3) + GPIO3 (SCL, pin 5) — nativo
- I2C bit-banged (ya en uso, ver `/boot/firmware/config.txt`): GPIO22 (SDA) + GPIO23 (SCL), bus=2
- SPI: GPIO10 (MOSI), GPIO9 (MISO), GPIO11 (SCLK), GPIO8 (CE0), GPIO7 (CE1) — deshabilitado
  hoy. **Se necesita** (corregido 2026-09-06): los 2 MAX6675 en mano usan
  SPI real, uno en CE0 y otro en CE1 — cubre exactamente las 2 unidades sin
  necesitar un GPIO expander. Habilitar con `dtparam=spi=on`.
- UART: GPIO14 (TX, pin 8) + GPIO15 (RX, pin 10) — compartido con consola serial
- 1-Wire (MAX31850): GPIO4 (pin 7) — libre, confirmado sin conflicto (2026-07-05).
  **Vigente** (aclarado 2026-09-06): hay un tercer termopar, separado de los 2
  MAX6675, cuya placa sí dice MAX31850 — este va aquí, no en SPI. Habilitar con
  `dtoverlay=w1-gpio` en `/boot/firmware/config.txt` (requiere reboot).
- Analógico: **ADS1115 (I2C+PGA, 2 en mano)** — reemplaza el plan de MCP3008/SPI;
  comparte el bus I2C ya en uso, sin pelear por pines SPI con los MAX6675.

## 5. Limitaciones de hardware

La Pi Zero 2W tiene recursos limitados:
- 512MB RAM — no saturar con múltiples threads de sensores
- I2C comparte bus — todos los sensores I2C en la misma línea (dirección única por sensor)
- Integrar sensores de uno en uno — validar cada uno antes de agregar el siguiente

## 6. Estado de integración

| Sensor | Prioridad | Interfaz | Módulo futuro | Estado |
|--------|-----------|----------|---------------|--------|
| Wideband O2 (Spartan 3) | Alta | I2C | sensors/lambda.py | Pendiente |
| Termopares K-Type (MAX31850 x2-4) | Alta | 1-Wire | `sensors/max31850.py` | **Driver escrito (2026-07-05), sin hardware conectado aun** |
| GPS (Ublox M8N) | Media | UART | sensors/gps.py | Pendiente |
| IMU (LSM6DSO) | Media | I2C | sensors/imu.py | Pendiente |
| BME280 Airbox | Baja | I2C | sensors/environment.py | Pendiente |
| BME280 Ambient | Baja | I2C | sensors/environment.py | Pendiente |
| Oil Pressure/Temp | Media | ADC+SPI | sensors/oil.py | Pendiente |
