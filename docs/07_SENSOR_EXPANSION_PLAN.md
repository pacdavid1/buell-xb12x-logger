# Sensor Expansion Plan (Roadmap)

This document defines the integration of external telemetry sensors into the Buell XB12X DDFI2 Logger.

## 1. Rationale
The stock DDFI2 ECU provides critical engine data but lacks high-fidelity environmental and performance metrics (AFR, EGT, GPS, Lean Angle). This plan outlines how to bridge that gap using the Raspberry Pi's I2C/SPI/UART interfaces.

## 2. Sensor Suite

### Combustion & Tuning (High Priority)
- **Wideband O2 (Spartan 3 OEM):** For precise VE table tuning. Interface: I2C.
- **EGT (Exhaust Gas Temp):** K-Type thermocouples with MAX31855. Interface: SPI.
- **Oil Pressure/Temp:** 0-5V Analog sensors via ADC.

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
- I2C: GPIO2 (SDA, pin 3) + GPIO3 (SCL, pin 5)
- SPI: GPIO10 (MOSI), GPIO9 (MISO), GPIO11 (SCLK), GPIO8 (CE0), GPIO7 (CE1)
- UART: GPIO14 (TX, pin 8) + GPIO15 (RX, pin 10) — compartido con consola serial
- Analógico: requiere ADC externo (MCP3008 vía SPI) — Pi Zero no tiene ADC nativo

## 5. Limitaciones de hardware

La Pi Zero 2W tiene recursos limitados:
- 512MB RAM — no saturar con múltiples threads de sensores
- I2C comparte bus — todos los sensores I2C en la misma línea (dirección única por sensor)
- Integrar sensores de uno en uno — validar cada uno antes de agregar el siguiente

## 6. Estado de integración

| Sensor | Prioridad | Interfaz | Módulo futuro | Estado |
|--------|-----------|----------|---------------|--------|
| Wideband O2 (Spartan 3) | Alta | I2C | sensors/lambda.py | Pendiente |
| EGT K-Type (MAX31855) | Alta | SPI | sensors/egt.py | Pendiente |
| GPS (Ublox M8N) | Media | UART | sensors/gps.py | Pendiente |
| IMU (LSM6DSO) | Media | I2C | sensors/imu.py | Pendiente |
| BME280 Airbox | Baja | I2C | sensors/environment.py | Pendiente |
| BME280 Ambient | Baja | I2C | sensors/environment.py | Pendiente |
| Oil Pressure/Temp | Media | ADC+SPI | sensors/oil.py | Pendiente |
