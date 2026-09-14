#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
Calibrate the MPU-6050's accel/gyro offset against its current resting pose.

Run on the Pi with the sensor held perfectly still (and level, if you care
about which axis reads "up" -- level isn't required for gyro, only for a
clean accel offset). Stops the running buell-logger service first so it
isn't fighting over the I2C bus, then restarts it after saving.

Usage:
    sudo systemctl stop buell-logger
    python3 tools/calibrate_imu.py
    sudo systemctl start buell-logger
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import smbus2
from sensors.mpu6050 import MPU6050, save_calibration

CALIBRATION_PATH = Path(__file__).resolve().parent.parent / 'mpu6050_calibration.json'


def main():
    bus = smbus2.SMBus(1)
    imu = MPU6050(i2c_dev=bus)
    if not imu.begin():
        print("MPU6050 did not respond -- check wiring/power before calibrating.")
        sys.exit(1)

    print("Hold the sensor still... calibrating (about 1s of sampling)")
    offsets = imu.calibrate()

    print("\nOffsets (subtracted from every future reading):")
    for k, v in offsets.items():
        print(f"  {k}: {v:+.4f}")

    save_calibration(CALIBRATION_PATH, offsets)
    print(f"\nSaved to {CALIBRATION_PATH}")
    print("Restart buell-logger to pick it up: sudo systemctl restart buell-logger")


if __name__ == '__main__':
    main()
