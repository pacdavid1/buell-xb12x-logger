#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
AHT20 Driver - Temperature and Humidity over I2C
Uses smbus2 with i2c_rdwr for raw I2C reads (no command byte).

Protocol:
  - I2C address: 0x38
  - Measure: [0xAC, 0x33, 0x00]
  - Read: 6 bytes via i2c_rdwr (no preceding command)
"""

import time
import smbus2

class AHT20:
    """Driver for the AHT20 temperature and humidity sensor."""

    I2C_ADDR = 0x38

    CMD_MEASURE   = [0xAC, 0x33, 0x00]
    CMD_INIT      = [0xBE, 0x08, 0x00]
    CMD_SOFTRESET = [0xBA]

    INIT_RETRIES  = 3
    INIT_DELAY_S  = 0.1

    def __init__(self, i2c_dev, i2c_addr=None):
        self._bus = i2c_dev
        self._addr = i2c_addr or self.I2C_ADDR
        self._initialized = False

    def _read_bytes(self, n=6):
        """Read n bytes from the sensor using i2c_rdwr (NO command byte)."""
        msg = smbus2.i2c_msg.read(self._addr, n)
        self._bus.i2c_rdwr(msg)
        return list(msg)

    def _write_bytes(self, data):
        """Write bytes to the sensor."""
        self._bus.write_i2c_block_data(self._addr, data[0], data[1:])

    def _try_begin_once(self) -> bool:
        """Single calibration attempt. Returns True if the sensor is calibrated."""
        # Read status byte
        data = self._read_bytes(1)
        status = data[0] if data else 0xFF

        if not (status & 0x08):
            # Not calibrated - send init
            self._write_bytes(self.CMD_INIT)
            time.sleep(0.02)
            data = self._read_bytes(1)
            status = data[0] if data else 0xFF

        return bool(status & 0x08)

    def begin(self) -> bool:
        """Initialize the sensor with retries.

        The AHT20 can be in a transient state right after power-up. Without
        retries a single failed attempt would disable the sensor permanently
        until process restart. Retry up to INIT_RETRIES times before giving up.
        """
        last_error = None
        for attempt in range(self.INIT_RETRIES):
            try:
                if self._try_begin_once():
                    self._initialized = True
                    return True
            except Exception as e:
                last_error = e
            if attempt < self.INIT_RETRIES - 1:
                time.sleep(self.INIT_DELAY_S)

        if last_error is not None:
            raise RuntimeError(f"AHT20 begin failed after {self.INIT_RETRIES} attempts: {last_error}")
        return False

    def read(self):
        """
        Read humidity and temperature from the AHT20.
        Returns:
            tuple (humidity_pct, temperature_c) or (None, None) on failure
        """
        if not self._initialized:
            try:
                if not self.begin():
                    return None, None
            except RuntimeError:
                return None, None

        try:
            # Trigger measurement
            self._write_bytes(self.CMD_MEASURE)
            time.sleep(0.09)  # > 80ms

            # Read 6 bytes via i2c_rdwr (NO command byte!)
            data = self._read_bytes(6)
            if len(data) < 6:
                return None, None

            status = data[0]

            # If busy, wait and retry once
            if status & 0x80:
                time.sleep(0.05)
                data = self._read_bytes(6)
                if len(data) < 6:
                    return None, None
                status = data[0]

            # Extract humidity (20 bits)
            raw_humidity = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
            humidity = (raw_humidity / 1048576.0) * 100.0

            # Extract temperature (20 bits)
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
