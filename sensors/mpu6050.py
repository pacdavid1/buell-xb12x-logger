#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
MPU-6050 Driver - 6-axis IMU (3-axis accelerometer + 3-axis gyroscope) over I2C

Uses the reset-default full-scale ranges (+/-2g accel, +/-250 deg/s gyro) --
ACCEL_CONFIG/GYRO_CONFIG are never written, so the fixed sensitivities below
apply directly. Lean angle is NOT computed here: a raw accelerometer angle is
corrupted by cornering/braking acceleration exactly when lean angle matters
most. That needs sensor fusion (gyro + accel) layered on top of these raw
readings, not a change to this driver.
"""

import time

I2C_ADDR = 0x68

REG_PWR_MGMT_1   = 0x6B
REG_WHO_AM_I     = 0x75
REG_ACCEL_XOUT_H = 0x3B
REG_TEMP_OUT_H   = 0x41
REG_GYRO_XOUT_H  = 0x43

ACCEL_SENS_LSB_PER_G    = 16384.0  # +/-2g full scale (reset default)
GYRO_SENS_LSB_PER_DEG_S = 131.0    # +/-250 deg/s full scale (reset default)

INIT_RETRIES = 3
INIT_DELAY_S = 0.05


def _to_signed16(high: int, low: int) -> int:
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value


class MPU6050:
    """Driver for the MPU-6050 6-axis IMU."""

    def __init__(self, i2c_dev, i2c_addr: int = I2C_ADDR) -> None:
        self._bus = i2c_dev
        self._addr = i2c_addr
        self._initialized = False

    def begin(self) -> bool:
        """Wake the sensor from its power-on sleep state.

        PWR_MGMT_1 defaults to SLEEP=1 on power-up -- without clearing it,
        the data registers never update and every read returns stale zeros.
        """
        last_error = None
        for attempt in range(INIT_RETRIES):
            try:
                self._bus.write_byte_data(self._addr, REG_PWR_MGMT_1, 0x00)
                time.sleep(0.01)
                who = self._bus.read_i2c_block_data(self._addr, REG_WHO_AM_I, 1)[0]
                if who == 0x68:  # fixed value regardless of AD0/actual address
                    self._initialized = True
                    return True
            except Exception as e:
                last_error = e
            if attempt < INIT_RETRIES - 1:
                time.sleep(INIT_DELAY_S)
        if last_error is not None:
            raise RuntimeError(f"MPU6050 begin failed after {INIT_RETRIES} attempts: {last_error}")
        return False

    def read_all(self) -> dict:
        """Read accelerometer (g), gyroscope (deg/s) and die temperature (C).

        Returns a dict with every field None on failure, mirroring
        CW2015.read_all() so callers merge it into serial_stats the same way.
        """
        if not self._initialized:
            try:
                if not self.begin():
                    return self._empty()
            except RuntimeError:
                return self._empty()

        try:
            accel = self._bus.read_i2c_block_data(self._addr, REG_ACCEL_XOUT_H, 6)
            gyro  = self._bus.read_i2c_block_data(self._addr, REG_GYRO_XOUT_H, 6)
            temp  = self._bus.read_i2c_block_data(self._addr, REG_TEMP_OUT_H, 2)

            ax = _to_signed16(accel[0], accel[1]) / ACCEL_SENS_LSB_PER_G
            ay = _to_signed16(accel[2], accel[3]) / ACCEL_SENS_LSB_PER_G
            az = _to_signed16(accel[4], accel[5]) / ACCEL_SENS_LSB_PER_G
            gx = _to_signed16(gyro[0], gyro[1]) / GYRO_SENS_LSB_PER_DEG_S
            gy = _to_signed16(gyro[2], gyro[3]) / GYRO_SENS_LSB_PER_DEG_S
            gz = _to_signed16(gyro[4], gyro[5]) / GYRO_SENS_LSB_PER_DEG_S
            temp_c = _to_signed16(temp[0], temp[1]) / 340.0 + 36.53

            return {
                'imu_accel_x_g':  round(ax, 3),
                'imu_accel_y_g':  round(ay, 3),
                'imu_accel_z_g':  round(az, 3),
                'imu_gyro_x_dps': round(gx, 2),
                'imu_gyro_y_dps': round(gy, 2),
                'imu_gyro_z_dps': round(gz, 2),
                'imu_temp_c':     round(temp_c, 1),
            }
        except Exception:
            return self._empty()

    @staticmethod
    def _empty() -> dict:
        return {
            'imu_accel_x_g': None, 'imu_accel_y_g': None, 'imu_accel_z_g': None,
            'imu_gyro_x_dps': None, 'imu_gyro_y_dps': None, 'imu_gyro_z_dps': None,
            'imu_temp_c': None,
        }
