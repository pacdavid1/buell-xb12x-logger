#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
MAX31850 Driver - K-Type Thermocouple Amplifier over 1-Wire

Uses the Linux kernel w1-gpio + w1-therm drivers, NOT manual GPIO bit-banging --
pure-Python bit-banging cannot meet 1-Wire timing requirements reliably
(confirmed via Raspberry Pi forum reports: manual bit-bang readings never
change; switching to the kernel driver + sysfs fixed it, with 11 MAX31850
sensors running on a single bus).

Requires on the Pi:
  - dtoverlay=w1-gpio in /boot/firmware/config.txt (reboot after adding)
  - w1-gpio and w1-therm kernel modules (auto-load with the overlay above)

Multiple MAX31850 sensors can share a single 1-Wire bus/GPIO pin -- each has
a unique factory-programmed 64-bit ROM ID, exposed as
/sys/bus/w1/devices/3b-<id>/w1_slave. Family code 0x3b identifies MAX31850/
MAX31850K; the kernel driver exposes the same two-line text format for all
w1-therm family devices regardless of family code.
"""

import time

FAMILY_CODE = "3b"
W1_DEVICES_PATH = "/sys/bus/w1/devices"

READ_RETRIES = 3
READ_RETRY_DELAY_S = 0.05


def list_connected() -> list[str]:
    """Return the 1-Wire IDs (e.g. '3b-000000123456') of all MAX31850 sensors
    currently visible on the bus. Empty list if none connected, not wired yet,
    or 1-Wire is not enabled on this Pi."""
    import glob
    pattern = f"{W1_DEVICES_PATH}/{FAMILY_CODE}-*"
    return sorted(path.split("/")[-1] for path in glob.glob(pattern))


def parse_w1_slave(lines: list[str]) -> float | None:
    """Parse the kernel w1-therm sysfs 'w1_slave' file format:
        <hex bytes> : crc=<hex> YES
        <hex bytes> t=<millidegrees_c>
    Returns temperature in Celsius, or None if CRC failed or malformed."""
    if len(lines) < 2 or "YES" not in lines[0]:
        return None
    idx = lines[1].find("t=")
    if idx == -1:
        return None
    try:
        millidegrees = int(lines[1][idx + 2:].strip())
    except ValueError:
        return None
    return millidegrees / 1000.0


class MAX31850:
    """Driver for one MAX31850 K-type thermocouple amplifier channel.

    device_id is the 1-Wire ROM id as it appears under /sys/bus/w1/devices/,
    e.g. '3b-000000123456' -- see list_connected() to discover connected ids."""

    def __init__(self, device_id: str) -> None:
        self._device_id = device_id
        self._path = f"{W1_DEVICES_PATH}/{device_id}/w1_slave"

    def read(self) -> float | None:
        """Read the thermocouple hot-junction temperature.

        Returns:
            temperature_c or None on failure (device absent/unplugged, or
            CRC mismatch after retries -- common on 1-Wire under electrical
            noise, e.g. long leads near ignition wiring on a motorcycle).
        """
        for attempt in range(READ_RETRIES):
            try:
                with open(self._path, "r") as f:
                    lines = f.readlines()
            except OSError:
                return None

            temperature = parse_w1_slave(lines)
            if temperature is not None:
                return temperature
            if attempt < READ_RETRIES - 1:
                time.sleep(READ_RETRY_DELAY_S)
        return None

    def get_temperature(self) -> float | None:
        return self.read()
