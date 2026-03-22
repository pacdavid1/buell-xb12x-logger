# BACKLOG — Buell XB12X DDFI2 Logger

Items are grouped by area and roughly ordered by priority within each group.
Status: OPEN / IN-PROGRESS / CLOSED

---

## ECU / EEPROM

**BACKLOG-ECU1** `OPEN`
ECM model detection — `version_string=BUEIB310` should map to `B2RIB.xml`.
Currently using `BUEIB.xml`. Critical difference at offset 574 (BAS scale 0.01 vs 10.0).
Investigate how EcmSpy maps version string to model code.

**BACKLOG-ECU2** `OPEN`
ECM model selector — allow user to manually select the correct XML in cfg tab
if auto-detection fails or is ambiguous.

**BACKLOG-ECU3** `OPEN`
EEPROM parameter editor — table with current value + editable field per parameter.
Warning on checksum change before writing back to ECU.
High risk: incorrect write can brick ECU parameters.

**BACKLOG-ECU4** `OPEN`
EEPROM fetch history — save each fetch with timestamp, allow rollback
to a previous version from the dashboard.

**BACKLOG-ECU5** `OPEN`
VIN / bike ID — use ECM Serial Number (offset 12, value 651) to identify
the bike. Warn if loaded EEPROM belongs to a different bike.

---

## Logging / Data

**BACKLOG-LOG1** `OPEN`
Auto-flush FIFO — `reset_input_buffer()` when `buf_pct > threshold`
to prevent FT232 saturation on low-quality hardware.
→ Implemented in v2.5.5 at 50% threshold (192b). Consider making threshold configurable.

**BACKLOG-LOG2** `OPEN` — CONFIRMED BUG
EEPROM map heatmap RPM axis wrong — affects FUEL FRONT/REAR and SPARK FRONT/REAR tabs in VE pane.

Problem:
- RPM axis shows garbled values (1.7k, 2.1k, 2.2k...) instead of correct bins
  (0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000)
- Values in cells do not match EcmSpy reference
- Some cells appear black (missing data)
- Root cause: period→RPM conversion in showMap() JS function is reading
  wrong axis data from the XML-derived maps

Note: This is NOT the VE coverage heatmap (buildGrid) — that one is correct.
This bug is in the EEPROM map viewer (showMap / loadMaps endpoints).

Reference: EcmSpy screenshot shows correct layout with BUEIB.xml bins.
EcmSpy also shows cruise/WOT overlay lines — document but low priority.

Files to investigate:
- web/templates/index.html — showMap(), loadMaps(), heatColor()
- web/server.py — /maps endpoint
- ecu/eeprom.py — decode_eeprom_maps()

Prerequisite: BACKLOG-ECU1 (correct XML selection) may affect this bug.

**BACKLOG-LOG3** `OPEN`
USB reset field validation — PENDING-R1, validate field before triggering USB reset.

**BACKLOG-LOG4** `OPEN`
sysfs latency timer path verification — PENDING-F7, verify correct sysfs path
for FT232 latency timer on current kernel.

**BACKLOG-LOG5** `OPEN`
Gear detection threshold calibration — PENDING-R3, calibrate gear detection
thresholds against real ride data.

---

## GPS

**BACKLOG-GPS1** `OPEN`
GPS module integration — NEO-6M or NEO-8M via UART GPIO.
Log lat/lon/altitude/GPS-speed per sample in CSV.
GPS speed provides independent cross-validation of VSS.

**BACKLOG-GPS2** `OPEN`
Ride map view — Leaflet.js route rendered in browser from CSV data.
Line colored by speed: blue→green→yellow→orange→red gradient.

**BACKLOG-GPS3** `OPEN`
Elevation profile — D3.js chart, X=distance Y=altitude.
Line color = speed gradient. Renders in browser, zero Pi load.

**BACKLOG-GPS4** `OPEN`
GPS speed vs VSS cross-validation — calibration tool for speedometer
using GPS ground truth.

---

## Dashboard / UX

**BACKLOG-UX1** `OPEN`
IP address in Network tab — tap to open dashboard URL directly in
new browser tab. Works regardless of current network or assigned IP.

**BACKLOG-UX2** `OPEN`
Game Boy emulator tab — serve EmulatorJS + ROM statically from Pi.
Runs entirely in browser, zero Pi load during gameplay.
Disabled during active ride, enabled when ECU idle or disconnected.

---

## Sync / Connectivity

**BACKLOG-SYNC1** `OPEN`
Auto-upload rides to Google Drive when internet is available.
Upload CSV + metadata + eeprom.bin per session.
Queue pending uploads, retry on next connection.

**BACKLOG-SYNC2** `OPEN`
Sync status indicator per ride in dashboard — pending / synced / error.

**BACKLOG-NET1** `OPEN`
Tailscale integration — remote access over cell data without port forwarding.
Foundation for remote tuning service.

---

## Platform / Business

**BACKLOG-PROD1** `OPEN`
Multi-device telemetry platform — anonymized ride data aggregation
across multiple loggers. Foundation for remote tuning service.
Requires BACKLOG-SYNC1 and BACKLOG-NET1 as prerequisites.

---

## Closed

_Items moved here when completed._

**BACKLOG-LOG1** `CLOSED` v2.5.5
Auto-flush FIFO RX at 50% threshold (192b) — implemented in `main.py`.

---

**BACKLOG-UX3** `OPEN`
VE table 3D view — interactive 3D surface chart of the VE map.
X=RPM, Y=Load, Z=coverage or correction value.
Color gradient by value. Renders in browser using Three.js or Plotly.
Prerequisite: VE table data collection working correctly (BUG-3 RPM sort fixed first).

---

**BACKLOG-UX5** `OPEN`
Dashboard freeze indicator — visual alert when live.json stops updating.
Show timestamp of last successful fetch. Animation or color change
when no data received for >5s. Helps detect ECU/TTL loss while riding.

---
