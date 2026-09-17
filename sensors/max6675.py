#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
MAX6675 Driver - K-Type Thermocouple-to-Digital Converter over SPI

Replaces an earlier MAX31850 (1-Wire) attempt at the same TC1 measurement:
the MAX31850 gave erratic, drifting readings (-21C to -160C) that never
tripped its own fault bit, reproducible across two different physical
MAX31850 units and two different thermocouple probes, so the fault was
narrowed to something specific to that chip/protocol rather than the probe,
the wiring, or this project's code (verified bit-for-bit against an old,
untouched driver version). The MAX6675 read directly on the same bench, via
SPI0 CE0, matched the ECU's own CLT reading within 0.5C across 15 samples.

16-bit read-only transfer (MSB first), no MOSI needed -- the chip only ever
shifts data out:
  D15    : dummy sign bit, always 0
  D14-D3 : 12-bit temperature, 0.25 C/LSB
  D2     : 1 = thermocouple input open (no probe connected)
  D1     : device ID, always 0
  D0     : tri-state output state, always 0

Each read starts a new conversion; the chip needs ~220ms between reads for a
fresh value, but reading faster just returns the previous (still valid)
conversion rather than garbage.
"""

import spidev

OPEN_CIRCUIT_BIT = 0x4


class MAX6675:
    """Driver for one MAX6675 SPI thermocouple amplifier channel."""

    def __init__(self, bus: int = 0, device: int = 0, max_speed_hz: int = 1000000) -> None:
        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.max_speed_hz = max_speed_hz
        self._spi.mode = 0

    def get_temperature(self) -> float | None:
        """Read the thermocouple temperature in Celsius.

        Returns None on an SPI error or when the chip's own open-circuit
        fault bit is set (no thermocouple connected).
        """
        try:
            raw = self._spi.xfer2([0x00, 0x00])
        except Exception:
            return None
        value = (raw[0] << 8) | raw[1]
        if value & OPEN_CIRCUIT_BIT:
            return None
        return ((value >> 3) & 0xFFF) * 0.25

    def close(self) -> None:
        self._spi.close()
