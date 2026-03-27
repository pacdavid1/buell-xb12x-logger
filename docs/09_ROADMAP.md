# Roadmap — Buell XB12X Logger → Tuning Platform

This document captures the long-term vision and technical foundation
for evolving the logger into a full ECU tuning and telemetry platform.

---

## Vision

The Pi logger evolves through three phases:

1. **Read** — capture and visualize all ECU data (current)
2. **Analyze** — identify tuning opportunities from ride data (next)
3. **Write** — apply map changes to ECU from dashboard (future)

---

## Phase 1 — Communication Protocol (Reference)

### Command Set
- `0x56` — Get Version: returns firmware string e.g. `BUEIB310`
- `0x52` — Get Data: read EEPROM page by page
- `0x57` — Set Data: write EEPROM (HIGH RISK — see Phase 3)

### Version String Structure
Response to `0x56` follows pattern: `BUE` + layout_id + revision
Example: `BUEIB310` = `BUE` + `IB` + `310`

| Firmware prefix | Layout | XML file |
|----------------|--------|----------|
| BUEIA, BUEGC, BUEKA | CB050/CB060 | BUEIA.xml |
| BUEGB | GB231 | BUEGB.xml |
| BUEIB, BUEIC, B2RIB | IB310 | B2RIB.xml |

### Layout Page Boundaries
| Layout | Page 3 ends | Page 6 ends |
|--------|-------------|-------------|
| CB050/060 | 0x0259 | 0x0471 |
| GB231 | 0x0295 | 0x04ad |
| IB310 | 0x029d | 0x04b5 |

### Virtual Page 32
Read offset 0 before any write:
- `0x00` = ECU ready
- Any other value = ECU busy — do not write

---

## Phase 2 — Analysis (BACKLOG-ANL1/2/3)

### NB Sensor → EGO Correction Loop
- O2_ADC 128 = stoich (14.7 AFR)
- EGO_Corr > 105% = map is lean → increase VE cell
- EGO_Corr < 95% = map is rich → decrease VE cell
- Only use samples where fl_closed_loop=1 AND CLT > warmup threshold

### Wideband LSU 4.9 (BACKLOG-HW1)
- Bosch LSU 4.9 ordered
- Requires controller: Spartan 3 or Innovate LC-2
- Provides exact AFR — replaces estimated O2_ADC interpretation
- Essential for open-loop map validation

---

## Phase 3 — Map Management (BACKLOG-MAP1/2)

### Safety Prerequisites (NON-NEGOTIABLE ORDER)
1. BACKLOG-LOG6 resolved — stable connection
2. BACKLOG-ECU1 resolved — correct XML detection
3. BACKLOG-MAP1 implemented — Virtual Page 32 busy check
4. BACKLOG-ECU3 completed — single parameter write tested first

### Map Switching Concept
- Pi SD card stores multiple map files (JSON or binary)
- Dashboard UI: select map → apply to ECU via `0x57`
- Target: Pages 4-5 (fuel and timing tables, IB310 layout)
- Post-write checksum verification mandatory
- Example map profiles: Standard, Race, City/Cold

---

## Hardware Expansion Timeline

| Priority | Item | Backlog |
|----------|------|---------|
| 1 | Power filtering (buck converter) | HW3 |
| 2 | LSU 4.9 + wideband controller | HW1 |
| 3 | GPIO forensic button | HW2 |
| 4 | GPS NEO-6M/8M | HW4 |
| 5 | IMU LSM6DSOX | HW5 |

---

## Long-term Vision

- Multi-bike telemetry platform (BACKLOG-PROD1)
- Remote tuning via Tailscale (BACKLOG-NET1)
- Anonymized ride data aggregation for community tuning
- Open telemetry system for all Buell XB variants
