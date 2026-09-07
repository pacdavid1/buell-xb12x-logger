# Hardware Inventory

Physical parts and tools for the Buell XB12X logger project. Update this whenever
something is bought, arrives, or gets soldered in — this is the single source of
truth for "what do I actually have," so it doesn't live only in chat history.

## Tools

| Tool | Status | Notes |
|------|--------|-------|
| Soldering iron (cautín) | ❌ Needed | Required for new sensor wiring on the Pi |
| Hot air gun (pistola de calor) | ❌ Needed | For heat-shrink / SMD rework |

## On hand (confirmed 2026-09-06 — photos + parts list)

| Part | Qty | Notes |
|------|-----|-------|
| AHT20 + BMP280 (temp/humidity + pressure combo) | 7 | Covers airbox + ambient env sensing from the plan, with spares |
| 25W DC-DC converter | 2 | One confirmed in photo: **EV50-K2405**, IN 12V/24V (8V-40V) → OUT 5V/10A. ⚠️ label says 5V10A = 50W max, not 25W — confirm if the 2 units are the same model or different wattage |
| Deutsch 4-pin connector | 2 | Automotive-grade, presumably for a sensor harness pigtail |
| Thermocouple K-type, assembled (probe + amp board, "HW-550") | 2 | **Confirmed 2026-09-06: MAX6675** (SPI). Needs SPI enabled + one dedicated CS pin per sensor (CE0 + CE1) — cannot share a bus the way 1-Wire does. See `07_SENSOR_EXPANSION_PLAN.md` |
| Thermocouple K-type, labeled MAX31850 | 1 | **Also on hand (2026-09-06)** — genuine 1-Wire part this time, separate from the two MAX6675 units above. Goes on GPIO4 via `w1-gpio`/`w1-therm`. So the rig now uses BOTH interfaces: SPI (2x MAX6675) + 1-Wire (1x MAX31850) |
| FT232RL (isolated USB-UART) | 1 | |
| CH343 (isolated USB-serial) | 2 | This is the adapter used to talk to the ECU (see prior sessions) |
| MPU-6050 (IMU) | 1 | Per sensor plan section "Dynamics" — lean angle / accel |
| ADS1115 (16-bit I2C ADC+PGA) | 2 | Seen in photo. **Replaces MCP3008 in the sensor plan** (plan specified MCP3008 via SPI; ADS1115 is I2C instead — simpler since I2C bus is already in use and SPI is currently disabled per the plan doc). Update `07_SENSOR_EXPANSION_PLAN.md` section 3/4 once confirmed |
| 4-channel optocoupler isolation module (SN: ZMY-0264) | 1 | Pre-built module, NPN-conversion outputs (OUT1-OUT4), screw terminals for 4 isolated inputs. Not the same as raw 6N137 DIP chips — need to decide if this replaces or supplements the 6N137 order below |
| UPS-Lite HAT (Pi Zero power backup) | 1 | Small LiPo backup cell on the Pi Zero stack, for clean shutdown on power loss. Physical LED confirmed working correctly (see resolved item below); the dashboard indicator was the actual bug, fixed in `main.py` v2.7.302 |

## On order / pending

| Part | Qty | Source | Order ref | Notes |
|------|-----|--------|-----------|-------|
| 6N137 (optocoupler, raw DIP-8) | 2 | Taobao | item 532996446554, skuId 5483836885050 | In cart as of 2026-06-30, purchase status unconfirmed. Compare against the ZMY-0264 module above before buying more |

## Resolved

- [x] **UPS-Lite "charging" indicator (2026-09-06)** — two separate things were
  conflated. The **physical LED on the board was never broken**: confirmed
  live (charger connected/disconnected) that it turns on with power present
  and off with no power, exactly as expected. The **dashboard icon** was the
  real bug — `main.py` trusted the CW2015 hardware "charging" bit unconditionally,
  and that bit is documented (`sensors/battery_guard.py`) to be able to get
  stuck reporting "charging" indefinitely. Fixed in v2.7.302: a demonstrated
  discharge trend (voltage/SOC falling over >=5 min) now overrides the bit.
  Verified live: `bat_charging` flipped to `false` / `bat_trend` to `"down"`
  within the expected window after disconnecting.

## Open questions (need user confirmation)

- [ ] Second SBC in the black finned aluminum case (seen in main photo, right side, with its own green terminal GPIO breakout) — what device is it?
- [ ] Confirm both "25W DC-DC converter" units are the same EV50-K2405 model

## Planned (not yet ordered)

See `docs/07_SENSOR_EXPANSION_PLAN.md` section 2 for the full sensor roadmap
(wideband O2, GPS).

## Pi hardware state (current build)

<!-- Update after each physical rebuild -->
- 2026-09-06: Pi disassembled and reassembled with a new connection to allow
  wiring more sensors in — added UPS-Lite HAT + two stacked screw-terminal GPIO
  breakout boards. A second SBC (unidentified, black finned case) is now sitting
  alongside it with its own GPIO breakout. New 12V-40V-in DC-DC converter
  (EV50-K2405) suggests direct power from the bike's 12V system instead of a
  USB power bank.
