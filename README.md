# Buell XB12X — DDFI2 Datalogger + AI Tuning Platform

> Raspberry Pi · Python 3 · DDFI2 ECU · Alpha-N · Open Loop

Real-time datalogger and AI-assisted tuning platform for the **Buell XB12X** with a Delphi DDFI2 ECU.
Current version: see top of `CHANGELOG.md`.

---

## What this project does

```
LOG → ACOTAR → COMPARAR → PROPONER → QUEMAR
Dashboard  Session Events  Sessions VS + Launch  Tuner  VE tab
```

1. **LOG** — Pi connects to ECU via serial, captures 80+ parameters at 8Hz per ride
2. **ACOTAR** — F7 algorithm detects stable-condition events (Bucket A) and WOT transitions
3. **COMPARAR** — Cross-session comparison: which map accelerates better? Which cells are efficient?
4. **PROPONER** — Unified map proposal from F7 events + Sessions VS delta (FASE 6)
5. **QUEMAR** — Burn proposed EEPROM changes directly from the browser

---

## Hardware

| Component | Detail |
|-----------|--------|
| Bike | Buell XB12X, DDFI2 ECU (Delphi dual-fire, Alpha-N) |
| Logger | Raspberry Pi at 192.168.100.80, port 8080 |
| Sensors | BMP280 (baro/temp), AHT20 (humidity), CW2015 (battery), GPS |
| Serial | CH343P USB-Serial, 9600 8N1 |

**ECU mode:** Alpha-N (TPS + RPM only, no MAP sensor, no barometric correction in fueling).
**O2 sensor:** disconnected. Always Open Loop. EGO_Corr = AFV = 100 always.

---

## Key files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — ECU loop, sensor threads, watchdog |
| `web/server.py` | HTTP handlers + REST endpoints |
| `web/f7.py` | F7 event detection + DTW clustering |
| `web/launch.py` | Launch detection pipeline |
| `web/vs_engine.py` | Sessions VS comparison engine |
| `web/gear_detect.py` | Post-ride gear detection via RPM/VSS ratio |
| `ecu/eeprom.py` | EEPROM decode/encode (fuel + spark maps) |
| `CLAUDE.md` | Instructions for Claude Code AI agent |
| `FREEBUFF.md` | Instructions for freebuff analysis agent |
| `BACKLOG.md` | All pending work organized by FASE |
| `CHANGELOG.md` | Version history — newest entries at the TOP |

---

## AI agent system

This project uses two AI agents working in parallel:

### Claude Code (implementer)
- Writes and commits all code changes
- Reads instructions from `CLAUDE.md` on this Pi
- Checks `inbox/` after every commit for messages from freebuff
- Never modifies `BACKLOG.md` without removing completed items

### freebuff (analyst + validator)
- Runs on the user machine
- Task queue: `C:/Users/pacda/freebuff/TASKS.md`
- Role definition: `FREEBUFF.md` on this Pi
- Writes research responses to: `C:/Users/pacda/freebuff/responses/`
- Sends urgent tasks to Claude via: `/home/pi/buell/inbox/`
- Audits every Claude commit via SSH — adds `**Audited:**` line to CHANGELOG

### Workflow
```
User assigns task → freebuff researches → writes response
→ Claude applies + commits → freebuff audits → PASS/FAIL
→ Claude adds validation task → cycle repeats
```

---

## Session data structure

```
sessions/
└── [EEPROM-checksum]/
    ├── ride_NNN.csv              — raw ECU data (80+ cols, ~8Hz)
    ├── ride_NNN_f7events.json    — F7 events: Bucket A + accel curves + env stats
    ├── ride_NNN_summary.json     — ride summary
    ├── session_f7clusters_*.json — DTW-clustered events across all rides
    └── eeprom.bin                — EEPROM snapshot for this session
```

Each `f7events` file contains per-event fields including:
`mat_avg`, `spark_avg`, `baro_hpa`, `gps_alt_avg`, `gear_detected`, `tps_peak`, `vss_delta`

---

## Running the server

```bash
cd /home/pi/buell
nohup python3 main.py --port /dev/ttyECU --sessions-dir /home/pi/buell/sessions --buell-dir /home/pi/buell > /tmp/buell.log 2>&1 &
```

Validate:
```bash
curl -s http://localhost:8080/live | python3 -c 'import sys,json; print(json.load(sys.stdin).get("session_id","?"))'
```

---

## License

MIT — free for personal and community use.
