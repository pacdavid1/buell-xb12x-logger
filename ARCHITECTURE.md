# ARCHITECTURE -- Buell XB12X DDFI2 Logger

> *4cf1969 2026-06-18 23:17:11 -0700*
> Mapa vivo del repositorio. Generado automaticamente del directorio real.
> Regenerar: `python3 scripts/gen_architecture.py`

---

## Mapa del proyecto

Cada entrada corresponde a un archivo o directorio real en disco.
Los archivos `.py` muestran su docstring de modulo como descripcion.

### Directorios principales

- `ecu/` -- Comunicacion con ECU DDFI-2 (protocolo, sesiones, EEPROM)
- `ecu_defs/` -- Definiciones XML por modelo de ECM
- `web/` -- Servidor HTTP, handlers, frontend (dashboard, GRAF2, VDYNO, F7)
- `gps/` -- Lector GPS serial
- `network/` -- Gestor WiFi/Hotspot
- `sensors/` -- Sensores I2C (AHT20 temp/humedad, CW2015 bateria)
- `tools/` -- Diagnostico y salud del sistema
- `docs/` -- Documentacion detallada en markdown
- `archive/` -- Scripts y docs obsoletos preservados
- `inbox/` -- Ideas, notas y archivos en proceso
- `scripts/` -- Utilidades (gen_architecture.py)

---

## Arbol completo

- `.gitignore`
- `ARCHITECTURE.md`
- `BACKLOG.md`
- `BACKLOG_3D_VIZ.md`
- `BACKLOG_ANL.md`
- `BACKLOG_DATASET_INSIGHTS.md`
- `BACKLOG_ECM_DEFS.md`
- `BACKLOG_EEPROM_READ_LOGIC.md`
- `BACKLOG_GRAF2.md`
- `BACKLOG_MAPA_3D.md`
- `BACKLOG_VDYNO.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `CREATIVE_MODE.md`
- `DESIGN.md`
- `DEV_TIPS.md`
- `FREEBUFF.md`
- `IDEAS.md`
- `README.md`
- **archive/**
  - `ARCHITECTURE_v2.6.10.md`
- **docs/**
  - `00_OVERVIEW.md`
  - `01_ARCHITECTURE.md`
  - `02_INSTALL_FLOW.md`
  - `03_NETWORKING.md`
  - `04_DECISIONS.md`
  - `05_TROUBLESHOOTING.md`
  - `06_INSTALLATION_GOALS.md`
  - `07_SENSOR_EXPANSION_PLAN.md`
  - `08_ANALYSIS_TUNING.md`
  - `09_ROADMAP.md`
  - `10_DDFI2_PROTOCOL.md`
  - `11_VDYNO_PLAN.md`
  - **assets/**
    - `architecture.svg`
    - `dashboard_mockup.svg`
    - `pipeline.svg`
  - `presentation.html`
- **ecu/**
  - `connection.py` -- ecu/connection.py — Conexión serial DDFI2 ECU
  - `debug.md`
  - `ecm_defs.py` -- ecu/ecm_defs.py — XML-driven EEPROM map/axis decoder (EcmSpy defs).
  - `eeprom.py` -- ecu/eeprom.py — Decodificación del EEPROM BUEIB/DDFI2
  - `eeprom_params.py` -- ecu/eeprom_params.py — EEPROM parameter parser from EcmSpy XMLs.
  - `logger_process.py` -- ECU CSV logger — standalone subprocess, independent of the web server.
  - `protocol.py` -- ecu/protocol.py — Constantes y decodificación del protocolo DDFI2
  - `session.py` -- ecu/session.py — SessionManager: records rides to CSV + JSON summaries.
  - `version_resolver.py` -- ecu/version_resolver.py
- **ecu_defs/**
  - `B2RIB.xml`
  - `BUE1D.xml`
  - `BUE2D.xml`
  - `BUE3D.xml`
  - `BUECB.xml`
  - `BUEGB.xml`
  - `BUEGC.xml`
  - `BUEIA.xml`
  - `BUEIB.xml`
  - `BUEKA.xml`
  - `BUEOD.xml`
  - `BUEWD.xml`
  - `BUEYD.xml`
  - `BUEZD.xml`
  - `README.md`
  - `files.xml`
- **gps/**
  - `reader.py`
- **inbox/**
  - `CREATIVE_MODE.md`
  - `IDEAS.md`
  - **archive/**
    - `998_vdyno_v1_tip.md`
    - `999_audit_v27132.md`
  - `prompt_para_claude.md`
- `install.sh`
- `main.py` -- Buell Logger — main process.
- **network/**
  - `manager.py` -- NetworkManager - Gestión de WiFi/Hotspot via nmcli
- `network_state.json`
- `objectives.json`
- `requirements.txt`
- **scripts/**
  - `gen_architecture.py` -- Generate ARCHITECTURE.md from the actual file tree on disk.
- **sensors/**
  - `aht20.py` -- AHT20 Driver - Temperatura y Humedad via I2C
  - `cw2015.py` -- CW2015 Driver - Battery Fuel Gauge (UPS-Lite v1.3)
- `server.log`
- `system_health.json`
- **tools/**
  - `diagnose_pi.sh`
  - `health_journal.py`
- **web/**
  - `0 debug.md`
  - `burn_ledger.py` -- Burn ledger — append-only record of every EEPROM burn (VDYNO phase V0).
  - `f7.py`
  - `fuel_tracker.py` -- Fuel tracking — reserve activation, fill-up logging, consumption estimate, fuel gauge.
  - `gear_detect.py` -- gear_detect.py — Post-ride gear detection from RPM/VSS ratio.
  - **handlers/**
    - `eeprom.py`
    - `fuel.py`
    - `gps.py`
    - `rides.py`
    - `sessions.py`
    - `system.py`
    - `tuner.py`
    - `vdyno.py` -- Vdyno handler mixin -- VDYNO Phase V1 (BL-VD-01).
    - `wifi.py`
  - `launch.py`
  - `server.py` -- WebServer - HTTP server con endpoints para red y status
  - **static/**
    - `app.js`
    - `graf2.js`
    - `uPlot.iife.min.js`
    - `uPlot.min.css`
  - **templates/**
    - `errorlog_viz.html`
    - `fuel.html`
    - `graf2.html`
    - `index.html`
    - `launch_power.html`
    - `session_events.html`
    - `sessions_launch.html`
    - `sessions_vs.html`
    - `tuner.html`
    - `tuner.html.bak`
  - `utils.py`
  - `vdyno.py` -- Virtual dyno engine -- VDYNO Phase V1 (BL-VD-01).
  - `vs_engine.py`

---

> Generado automaticamente. Para actualizar: `python3 scripts/gen_architecture.py`
