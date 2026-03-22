# BACKLOG — Buell XB12X DDFI2 Logger

Items are grouped by area. Each item follows the format defined in WORKING_METHOD.md.
Status: OPEN / IN-PROGRESS / CLOSED vX.X.X

---

## ECU / EEPROM

**BACKLOG-ECU1** `OPEN`
ECM model detection

### Problem
`get_version()` returns `BUEIB310` but the physical ECU is a `B2RIB` variant.
The logger currently loads `BUEIB.xml` by default. The critical difference is at offset 574:
BUEIB uses BAS scale 0.01, B2RIB uses 10.0. Wrong XML = wrong parameter values.

### Context
- `ecu/connection.py` — `get_version()` returns raw version string
- `ecu_defs/` — 14 XML files for ECU variants
- `ecu/eeprom.py` — `decode_eeprom_maps()` uses hardcoded BUEIB.xml

### Reference
EcmSpy maps version string to model code internally.
`BUEIB310` → `B2RIB` mapping not yet understood.

### Prerequisites
None.

---

**BACKLOG-ECU2** `OPEN`
ECM model selector — manual XML override in cfg tab

### Problem
If auto-detection (ECU1) fails or is ambiguous, the user has no way to manually
select the correct XML. Wrong XML = wrong EEPROM parameter interpretation.

### Context
- `web/templates/index.html` — cfg tab
- `web/server.py` — would need a new endpoint to accept XML selection
- `ecu/eeprom.py` — XML loading logic

### Prerequisites
BACKLOG-ECU1 should be investigated first.

---

**BACKLOG-ECU3** `OPEN`
EEPROM parameter editor

### Problem
The cfg tab shows 173 EEPROM parameters read-only. There is no way to edit
a value and write it back to the ECU from the dashboard.
High risk: incorrect writes can brick ECU parameters. Checksum must be recalculated.

### Context
- `web/templates/index.html` — cfg tab, `loadEepromParams()`
- `web/server.py` — would need a write endpoint
- `ecu/connection.py` — no write method exists yet
- `ecu/eeprom.py` — checksum recalculation needed before write

### Prerequisites
BACKLOG-ECU1 (correct XML) must be resolved first.
BACKLOG-ECU4 (fetch history) recommended before enabling writes.

---

**BACKLOG-ECU4** `OPEN` (partial)
EEPROM fetch history with timestamps

### Problem
Every EEPROM fetch overwrites the stored blob. There is no way to see
when the EEPROM was last read or roll back to a previous version.

### Context
- `ecu/session.py` — `save_eeprom()` overwrites unconditionally
- `sessions/CHECKSUM/` — only one `eeprom.bin` per session folder

### Note
BACKLOG-ECU5 (session isolation by EEPROM checksum) was implemented in v2.5.11
and partially addresses this — each parameter change now creates a new session folder,
preserving the previous EEPROM blob. Full timestamped history within a session is still missing.

---

**BACKLOG-ECU5** `CLOSED` v2.5.9 / v2.5.11
VIN / bike ID + EEPROM-based session checksum

### Problem
Two related issues:
1. No way to identify which bike an EEPROM blob belongs to.
2. Session checksum was derived from version string (always `BUEIB310`),
   so parameter changes never opened a new session.

### Investigation
- ECM Serial Number lives at EEPROM offset 12, little-endian uint16.
- Validated: `int.from_bytes(blob[12:14], 'little')` → 651. Matches EcmSpy.
- Session checksum was `MD5(version_str)` → always `EF4995`. Never changed.

### Blockers
Chicken-and-egg: session needed to exist before EEPROM could be loaded,
but EEPROM needed to be read before session checksum could be calculated.
Solved by fetching EEPROM unconditionally on connect, before `open_session()`.

### Solution
- `ecu/session.py`: `_checksum(blob)` now uses `MD5(blob[:64])` instead of version string
- `ecu/session.py`: `open_session(version_str, blob)` now accepts blob as argument
- `main.py`: EEPROM fetched before `open_session()` on both startup and reconnect
- `main.py`: Serial Number extracted from blob and exposed in `web.bike_serial`
- `web/server.py`: `bike_serial` added to `live.json`
- `index.html`: Serial cell added to dashboard header row 1

### Result
- Session `EF4995` (version-based) replaced by `9ECD1E` (EEPROM-based)
- Serial `#651` visible in dashboard header when ECU connected
- New session folder created automatically on every parameter change

---

## Logging / Data

**BACKLOG-LOG1** `CLOSED` v2.5.5
Auto-flush FIFO RX when buffer exceeds 50%

### Problem
FT232RL has a 384-byte RX FIFO. On low-quality USB hardware, the buffer
can accumulate stale bytes that corrupt the next valid frame.
No mechanism existed to clear the buffer proactively.

### Investigation
- `ser.in_waiting` available in `ecu/connection.py` via pyserial
- Buffer fill percentage already calculated in `serial_stats` for dashboard display
- Threshold of 50% (192 bytes) chosen: high enough to avoid false flushes,
  low enough to act before saturation

### Blockers
None.

### Solution
- `main.py`: after capturing `buf_in` for CSV, check if `> 192`
- If true: `ser.reset_input_buffer()` + WARNING log
- CSV records pre-flush value — forensic data preserved

### Result
Buffer flushes logged as `AUTO-FLUSH FIFO buf_in=Xb >50% — flushed`.
Pre-flush value visible in CSV for correlation analysis.


**BACKLOG-LOG6** `OPEN` — CONFIRMED BUG
RT data failure after multiple killswitch/reconnect cycles

### Problem
After 2-3 killswitch events and reconnect cycles, `get_rt_data()` returns None
consistently even though `get_version()` succeeds. The ECU appears to be stuck
in a state where it responds to version requests but not to RT data requests.
TTL% stays at 97%, BUF% stays at 0%, but no frames arrive.

### Context
- `ecu/connection.py` — `get_rt_data()` — `ser.read(1)` returns empty (timeout)
- DTR toggle happens on `connect()` but does not recover this state
- USB reset via sysfs fails with Permission denied (separate bug)
- Hard reconnect (disconnect + connect + DTR toggle) does not recover either

### Reference
Observed during first real ride test 2026-03-21. Multiple killswitch events,
ECU lost and recovered several times. After ~3 cycles, RT data stopped completely.
Ride data was lost — tracker had 15min of heatmap data in memory but no CSV saved.

### Investigation needed
- Check if ECM Droid has same issue after multiple killswitch cycles
- Try longer DTR toggle delay on reconnect (currently 0.2s)
- Try full serial port close/reopen with 1s delay between
- Check if issue is in FT232 chip state vs ECU protocol state

### Prerequisites
Requires moto connected and ability to reproduce killswitch cycles deliberately.

---

**BACKLOG-LOG2** `CLOSED v2.5.15
EEPROM map heatmap RPM axis wrong
### Investigation
- Compared B2RIB.xml axis offsets against live eeprom.bin dump (Serial #651, checksum 9ECD1E)
- XML offset 644: fuel RPM axis 13x uint16 little-endian, stored as [8000, 7000...0] descending
- XML offset 612: spark RPM axis 10x uint16 little-endian, stored descending
- Code was reading with big-endian ('>H') and no reversal — axis and map data both mirrored
- LOAD axis (offset 632) was correct — stored ascending, read correctly

### Solution
- `ecu/eeprom.py`: `read_axis_2b()` changed to little-endian + reversed result
- `ecu/eeprom.py`: `read_map()` now reverses each row to match corrected RPM axis

### Result
- fuel_rpm: [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000] ✓
- spark_rpm: [800, 1000, 1350, 2000, 3000, 4000, 4500, 5500, 6500, 7000] ✓
- VE/FUEL/SPARK heatmaps now display correct RPM axis and correct cell values
### Problem
The FUEL and SPARK map heatmaps in the VE tab show garbled RPM axis values
(1.7k, 2.1k, 2.2k...) instead of the correct bins
(0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000).
Cell values do not match EcmSpy reference. Some cells appear black (missing data).

### Context
- `web/templates/index.html` — `showMap()`, `loadMaps()`, `heatColor()`
- `web/server.py` — `/maps` endpoint
- `ecu/eeprom.py` — `decode_eeprom_maps()`

### Reference
EcmSpy screenshot shows correct FUEL FRONT map with proper RPM bins and matching values.
Logger screenshot shows same map with wrong RPM axis and mismatched values.
EcmSpy also shows cruise/WOT overlay lines — separate feature, low priority.

### Note
This is NOT the VE coverage heatmap (`buildGrid`) — that one is correct.
Root cause likely in period→RPM conversion or wrong axis data from XML.

### Prerequisites
BACKLOG-ECU1 (correct XML selection) may affect this bug.

### Investigation
- Compared B2RIB.xml axis offsets against live eeprom.bin dump (Serial #651, checksum 9ECD1E)
- XML offset 644: fuel RPM axis 13x uint16 little-endian, stored as [8000, 7000...0] descending
- XML offset 612: spark RPM axis 10x uint16 little-endian, stored descending
- Code was reading with big-endian ('>H') and no reversal — axis and map data both mirrored
- LOAD axis (offset 632) was correct — stored ascending, read correctly

### Solution
- `ecu/eeprom.py`: `read_axis_2b()` changed to little-endian + reversed result
- `ecu/eeprom.py`: `read_map()` now reverses each row to match corrected RPM axis

### Result
- fuel_rpm: [0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000] ✓
- spark_rpm: [800, 1000, 1350, 2000, 3000, 4000, 4500, 5500, 6500, 7000] ✓
- VE/FUEL/SPARK heatmaps now display correct RPM axis and correct cell values

### Additional Fix (v2.5.16)
- Map rows were still reversed after axis fix — `read_map()` now reverses each row
- Checksum expanded to full 1206 bytes — fuel/spark map changes now trigger new session
- Validated with unique-value test matrix burned to ECU via EcmSpy
---

**BACKLOG-LOG3** `CLOSED` — FALSE POSITIVE
USB reset field validation

### Investigation
No user-facing input field exists for USB reset. The reset is triggered
automatically after 60s of ECU loss. The `usb_reset()` method in
`ecu/connection.py` already handles all error cases with try/except and
returns True/False. No validation was missing.

### Result
No code change needed. Item closed as false positive.

---

**BACKLOG-LOG4** `CLOSED` — VERIFIED
sysfs latency timer path verification

### Investigation
- Path `/sys/bus/usb-serial/devices/ttyUSB0/latency_timer` — not found without device connected.
- `find /sys -name latency_timer` returns empty without FT232 plugged in.
- Driver confirmed: `ftdi_sio` kernel `6.12.47+rpt-rpi-v8` — latency_timer is supported.
- Path only appears in sysfs when FT232 is physically connected.

### Result
Path is correct. No code change needed. Behavior is expected.

---

**BACKLOG-LOG5** `OPEN`
Gear detection threshold calibration

### Problem
Gear detection uses fixed `GEAR_KPH_PER_KRPM` thresholds that have not been
validated against real ride data. Detection may be inaccurate at certain RPM/speed combinations.

### Context
- `ecu/protocol.py` — `GEAR_KPH_PER_KRPM = [0.0, 7.0, 11.8, 15.4, 19.1, 23.0]`
- `sessions/*/ride_*.csv` — `Gear`, `VS_KPH`, `RPM` columns available for analysis

### Prerequisites
Requires real ride CSV data with known gear changes for validation.

---

## GPS

**BACKLOG-GPS1** `OPEN`
GPS module hardware integration

### Problem
No position, altitude, or GPS-derived speed data is logged.
This limits post-ride analysis and prevents map visualization.

### Context
- Pi Zero 2W has UART GPIO available (pins 14/15)
- Recommended modules: NEO-6M (1Hz, ~$3) or NEO-8M (5Hz, better sensitivity)
- Libraries: `gpsd` + `pynmea2`
- GPS speed provides independent VSS cross-validation

### Prerequisites
Hardware purchase and physical installation required first.

---

**BACKLOG-GPS2** `OPEN`
Ride map view — route colored by speed

### Problem
No visual route map exists. Cannot see where on a road a specific
engine event occurred.

### Context
- Leaflet.js — runs in browser, zero Pi load
- Polyline with per-segment color based on speed
- Color gradient: blue→green→yellow→orange→red

### Prerequisites
BACKLOG-GPS1 (hardware) must be completed first.

---

**BACKLOG-GPS3** `OPEN`
Elevation profile with speed overlay

### Problem
No altitude data is captured or visualized. Cannot correlate engine
behavior with terrain (climbs, descents).

### Context
- D3.js or Chart.js — runs in browser
- X = distance, Y = altitude, line color = speed gradient
- Same color scale as GPS2 map view

### Prerequisites
BACKLOG-GPS1 (hardware) must be completed first.

---

**BACKLOG-GPS4** `OPEN`
GPS speed vs VSS cross-validation

### Problem
VSS calibration (`vss_cal.json`) is set manually. No ground truth exists
to verify speedometer accuracy across the RPM/gear range.

### Prerequisites
BACKLOG-GPS1 (hardware) must be completed first.

---

## Dashboard / UX

**BACKLOG-UX1** `CLOSED` v2.5.10
IP address tappable in Network tab

### Problem
When the Pi connects to a new network (hotspot or WiFi), the assigned IP changes.
Users had to manually type the IP and port into the browser to reconnect.

### Investigation
- IP already available in `live.json` via `net.get_ip()`
- `updateNetStatus()` in JS already displayed the IP as plain text
- Simple change: replace `textContent` with `innerHTML` containing an anchor tag

### Blockers
None.

### Solution
- `index.html`: `updateNetStatus()` now renders IP as `<a href="http://IP:8080" target="_blank">`
- Works for both WiFi and Hotspot modes
- IP always reflects current Pi assignment from `live.json`

### Result
Tapping the IP in the Network tab opens the dashboard directly in a new browser tab.

---

**BACKLOG-UX2** `OPEN`
Game Boy emulator tab

### Problem
Pure quality-of-life feature. EmulatorJS can run Game Boy ROMs entirely
in the browser with zero Pi CPU load after initial file transfer.

### Context
- New static route in `web/server.py` — serve EmulatorJS + ROM files
- New tab in dashboard or standalone page at `/games`
- Must be disabled during active ride (ECU loop running)
- EmulatorJS: https://emulatorjs.org

### Prerequisites
None technical. Low priority — implement after core features are stable.

---

**BACKLOG-UX3** `OPEN`
VE table 3D view

### Problem
The 2D VE coverage heatmap shows time-in-cell but lacks depth perception.
A 3D surface would make gaps, peaks, and lean/rich zones immediately visible.

### Context
- Three.js or Plotly — both available via CDN, run in browser
- X = RPM, Y = Load, Z = coverage seconds or correction value
- Color gradient by Z value
- New view mode button in VE tab

### Prerequisites
BACKLOG-LOG2 (EEPROM map axis bug) should be fixed first for reference comparison.

---

**BACKLOG-UX4** `OPEN`
Dashboard freeze indicator

### Problem
When ECU or TTL connection is lost, `live.json` stops updating but the dashboard
shows no visual indication. The user cannot tell if the system is frozen or
simply idle. Especially problematic while riding.

### Context
- `fetchLive()` in `index.html` — already runs every 2s
- Need to track timestamp of last successful fetch
- If no update received for >5s: change header color, show alert, animate indicator

### Prerequisites
None.

---

## Sync / Connectivity

**BACKLOG-SYNC1** `OPEN`
Auto-upload rides to Google Drive

### Problem
Ride data is stored only on the Pi SD card. No remote backup exists.
Required foundation for the remote tuning service concept.

### Context
- Google Drive API or `rclone` — both viable on Pi Zero 2W
- Upload trigger: ride closes + internet available
- Payload: CSV + session metadata + eeprom.bin
- Queue pending uploads, retry on next connection

### Prerequisites
BACKLOG-NET1 (remote connectivity) recommended first.

---

**BACKLOG-SYNC2** `OPEN`
Sync status indicator per ride in dashboard

### Problem
No visual indication of whether a ride has been backed up or is pending upload.

### Context
- `session_metadata.json` — add `sync_status` field per ride
- `index.html` — rides list shows sync badge: pending / synced / error

### Prerequisites
BACKLOG-SYNC1 must be implemented first.

---

**BACKLOG-NET1** `OPEN`
Tailscale integration — remote access over cell data

### Problem
When the Pi connects to the phone hotspot, it gets a private IP only accessible
from that phone. No way to access the dashboard remotely or push data to a server.

### Context
- Tailscale: mesh VPN, free up to 3 devices, one-line install
- Pi gets a stable Tailscale IP accessible from anywhere
- No port forwarding or router config needed
- Foundation for remote tuning service

### Prerequisites
None.

---

## Platform / Business

**BACKLOG-PROD1** `OPEN`
Multi-device telemetry platform

### Problem
Each logger operates in isolation. Aggregating anonymized ride data across
multiple bikes would enable data-driven remote tuning at scale.

### Context
- Each bike identified by ECM Serial Number (already implemented)
- EEPROM checksum identifies exact tune version per bike
- Data pipeline: Pi → Google Drive → aggregation backend → tuning dashboard
- Privacy: user consent required, data anonymized by default

### Prerequisites
BACKLOG-SYNC1, BACKLOG-NET1, and BACKLOG-ECU3 (EEPROM editor) must be completed first.

---

**BACKLOG-LOG7** `CLOSED` v2.5.14
Ride not recorded when Pi boots with engine already running

### Problem
If the Pi boots while the engine is already running above RPM_START (300 RPM),
the ride is never recorded despite full telemetry being visible in the dashboard.

### Context
- `main.py` `_ecu_loop()`: reconnect path called `read_full_eeprom()` but had no
  fallback if the fetch failed -- current_checksum stayed None
- ride start guard `if self.session.current_checksum is None` silently skipped ride
- Dashboard and heatmap receive samples via `web.ecu_live` regardless of ride state

### Investigation
- Confirmed `buffering=1` on CSV file handle -- flush was not the issue
- Traced silence to `current_checksum is None` guard in ride start block
- Startup path in `run()` had full fallback logic; reconnect path did not

### Solution
- `main.py`: reconnect path now mirrors startup fallback logic
- Fallback 1: use most recent eeprom.bin from disk if live fetch fails
- Fallback 2: use version string as checksum seed if no blob on disk
- `open_session()` always called after connect

### Result
- Session always opens on reconnect regardless of EEPROM fetch success
- Ride starts correctly even when Pi boots with engine already running

---

## Closed Items Index

| Item | Version | Summary |
|------|---------|---------|
| BACKLOG-ECU5 | v2.5.9 / v2.5.11 | VIN serial + EEPROM-based session checksum |
| BACKLOG-LOG1 | v2.5.5 | Auto-flush FIFO RX at 50% threshold |
| BACKLOG-LOG3 | — | False positive — no code change needed |
| BACKLOG-LOG4 | — | Verified — path correct, device must be connected |
| BACKLOG-UX1 | v2.5.10 | IP tappable in Network tab |
| BACKLOG-LOG7 | v2.5.14 | Ride not recorded when Pi boots with engine already running |
| BACKLOG-LOG2 | v2.5.15 | FUEL/SPARK RPM axis wrong — big-endian + descending order |
| BACKLOG-LOG2 | v2.5.15/v2.5.16 | FUEL/SPARK RPM axis wrong + map rows reversed |
