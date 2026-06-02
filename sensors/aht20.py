#!/usr/bin/env python3
"""
AHT20 Driver - Temperatura y Humedad via I2C
Usa smbus2 con i2c_rdwr para lecturas I2C puras (sin command byte).

Protocolo:
  - Direccion I2C: 0x38
  - Medicion: [0xAC, 0x33, 0x00]
  - Lectura: 6 bytes via i2c_rdwr (sin comando previo)
"""

import time
import smbus2

class AHT20:
    """Driver para sensor AHT20 de temperatura y humedad."""

    I2C_ADDR = 0x38

    CMD_MEASURE   = [0xAC, 0x33, 0x00]
    CMD_INIT      = [0xBE, 0x08, 0x00]
    CMD_SOFTRESET = [0xBA]

    def __init__(self, i2c_dev, i2c_addr=None):
        self._bus = i2c_dev
        self._addr = i2c_addr or self.I2C_ADDR
        self._initialized = False

    def _read_bytes(self, n=6):
        """Lee n bytes del sensor usando i2c_rdwr (SIN command byte)."""
        msg = smbus2.i2c_msg.read(self._addr, n)
        self._bus.i2c_rdwr(msg)
        return list(msg)

    def _write_bytes(self, data):
        """Escribe bytes al sensor."""
        self._bus.write_i2c_block_data(self._addr, data[0], data[1:])

    def begin(self):
        """Inicializa el sensor si es necesario.
        Revisa si ya esta calibrado - si no, envia init."""
        try:
                # Leer status byte
            data = self._read_bytes(1)
            status = data[0] if data else 0xFF

            if not (status & 0x08):
                # No calibrado - enviar init
                self._write_bytes(self.CMD_INIT)
                time.sleep(0.02)
                data = self._read_bytes(1)
                status = data[0] if data else 0xFF

            if status & 0x08:
                self._initialized = True
                return True
            else:
                return False
        except Exception as e:
            raise RuntimeError(f"AHT20 begin failed: {e}")

    def read(self):
        """
        Lee humedad y temperatura del AHT20.
        Returns:
            tuple (humidity_pct, temperature_c) o (None, None) si falla
        """
        if not self._initialized:
            if not self.begin():
                return None, None

        try:
            # Disparar medicion
            self._write_bytes(self.CMD_MEASURE)
            time.sleep(0.09)  # > 80ms

            # Leer 6 bytes via i2c_rdwr (SIN command byte!)
            data = self._read_bytes(6)
            if len(data) < 6:
                return None, None

            status = data[0]

            # Si esta ocupado, esperar y reintentar
            if status & 0x80:
                time.sleep(0.05)
                data = self._read_bytes(6)
                if len(data) < 6:
                    return None, None
                status = data[0]

            # Extraer humedad (20 bits)
            raw_humidity = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
            humidity = (raw_humidity / 1048576.0) * 100.0

            # Extraer temperatura (20 bits)
            raw_temp = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
            temperature = (raw_temp / 1048576.0) * 200.0 - 50.0

            hum = round(humidity, 1) if 0 <= humidity <= 100 else None
            temp = round(temperature, 1) if -40 <= temperature <= 85 else None

            return hum, temp

        except Exception:
            return None, None

    def get_humidity(self):
        hum, _ = self.read()
        return hum

    def get_temperature(self):
        _, temp = self.read()
        return temp
