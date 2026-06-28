#!/usr/bin/env python3
"""
CW2015 Driver - Battery Fuel Gauge (UPS-Lite v1.3)
I2C address: 0x62
Registers:
  0x00: VER - Version (0x00A5 when battery present)
  0x02: VCELL - Voltage (14-bit, 0.305mV/LSB)
  0x04: SOC - State of Charge (8.8 fixed point)
  0x08: STATUS - Status register
    Bit 4: CHG_IND - Charging indicator (1 = charging, from charger pin)
    Bit 3: QUICKSTART
"""

class CW2015:
    I2C_ADDR = 0x62
    REG_VER = 0x00
    REG_VCELL = 0x02
    REG_SOC = 0x04
    REG_STATUS = 0x08

    def __init__(self, i2c_dev, i2c_addr=None):
        self._bus = i2c_dev
        self._addr = i2c_addr or self.I2C_ADDR

    def _read_word(self, reg):
        data = self._bus.read_i2c_block_data(self._addr, reg, 2)
        return (data[0] << 8) | data[1]

    def _read_byte(self, reg):
        data = self._bus.read_i2c_block_data(self._addr, reg, 1)
        return data[0]

    def get_voltage(self):
        raw = self._read_word(self.REG_VCELL) & 0x3FFF
        return raw * 0.305 / 1000.0

    def get_soc(self):
        data = self._bus.read_i2c_block_data(self._addr, self.REG_SOC, 2)
        return data[0] + data[1] / 256.0

    def get_charging(self):
        """Return True if charger circuit reports charging (Bit 4 of STATUS).
        Works even when battery is absent - driven by charger IC pin, not battery."""
        status = self._read_byte(self.REG_STATUS)
        return bool(status & 0x10)  # Bit 4 = CHG_IND

    def battery_present(self):
        """VER register is 0 when no battery is connected."""
        return self._read_word(self.REG_VER) != 0

    def get_version(self):
        return self._read_word(self.REG_VER)

    def read_all(self):
        try:
            charging = self.get_charging()
            present = self.battery_present()
            if not present:
                return {'bat_voltage': None, 'bat_soc': None,
                        'bat_charging': charging, 'bat_present': False}
            v = round(self.get_voltage(), 3)
            s = round(self.get_soc(), 1)
            return {
                'bat_voltage':  v if 0 < v < 6 else None,
                'bat_soc':      s if 0 < s <= 100 else None,
                'bat_charging': charging,
                'bat_present':  True,
            }
        except Exception:
            return {'bat_voltage': None, 'bat_soc': None,
                    'bat_charging': False, 'bat_present': False}
