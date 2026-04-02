# ARCHITECTURE — Buell XB12X DDFI2 Logger
> Auto-generado por `tools/make_index.py` — no editar manualmente
> Última actualización: 2026-04-02 00:12 | versión: v1.16.3-191-g4f395ef

---

## Estructura del repo

```
buell-xb12x-logger/
├── docs
│   ├── 00_OVERVIEW.md
│   ├── 01_ARCHITECTURE.md
│   ├── 02_INSTALL_FLOW.md
│   ├── 03_NETWORKING.md
│   ├── 04_DECISIONS.md
│   ├── 05_TROUBLESHOOTING.md
│   ├── 06_INSTALLATION_GOALS.md
│   ├── 07_SENSOR_EXPANSION_PLAN.md
│   ├── 08_ANALYSIS_TUNING.md
│   └── 09_ROADMAP.md
├── ecu
│   ├── __init__.py
│   ├── connection.py
│   ├── eeprom.py
│   ├── eeprom_params.py
│   ├── protocol.py
│   ├── session.py
│   └── version_resolver.py
├── ecu_defs
│   ├── B2RIB.xml
│   ├── BUE1D.xml
│   ├── BUE2D.xml
│   ├── BUE3D.xml
│   ├── BUECB.xml
│   ├── BUEGB.xml
│   ├── BUEGC.xml
│   ├── BUEIA.xml
│   ├── BUEIB.xml
│   ├── BUEKA.xml
│   ├── BUEOD.xml
│   ├── BUEWD.xml
│   ├── BUEYD.xml
│   ├── BUEZD.xml
│   ├── README.md
│   └── files.xml
├── network
│   ├── __init__.py
│   └── manager.py
├── sessions
│   ├── 01B6AE
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_003_errorlog.json
│   │   ├── ride_004_errorlog.json
│   │   ├── ride_01B6AE_001.csv
│   │   ├── ride_01B6AE_002.csv
│   │   ├── ride_01B6AE_002_summary.json
│   │   ├── ride_01B6AE_003.csv
│   │   ├── ride_01B6AE_003_summary.json
│   │   ├── ride_01B6AE_004.csv
│   │   ├── ride_01B6AE_004_summary.json
│   │   └── session_metadata.json
│   ├── 243FAC
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_001_errorlog.tmp
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_006_errorlog.json
│   │   ├── ride_007_errorlog.json
│   │   ├── ride_008_errorlog.json
│   │   ├── ride_009_errorlog.json
│   │   ├── ride_010_errorlog.json
│   │   ├── ride_011_errorlog.json
│   │   ├── ride_012_errorlog.json
│   │   ├── ride_243FAC_001.csv
│   │   ├── ride_243FAC_001_notes.txt
│   │   ├── ride_243FAC_002.csv
│   │   ├── ride_243FAC_003.csv
│   │   ├── ride_243FAC_004.csv
│   │   ├── ride_243FAC_004_notes.txt
│   │   ├── ride_243FAC_005.csv
│   │   ├── ride_243FAC_005_notes.txt
│   │   ├── ride_243FAC_006.csv
│   │   ├── ride_243FAC_007.csv
│   │   ├── ride_243FAC_007_summary.json
│   │   ├── ride_243FAC_008.csv
│   │   ├── ride_243FAC_008_summary.json
│   │   ├── ride_243FAC_009.csv
│   │   ├── ride_243FAC_009_summary.json
│   │   ├── ride_243FAC_010.csv
│   │   ├── ride_243FAC_010_summary.json
│   │   ├── ride_243FAC_011.csv
│   │   ├── ride_243FAC_011_summary.json
│   │   ├── ride_243FAC_012.csv
│   │   ├── ride_243FAC_012_summary.json
│   │   └── session_metadata.json
│   ├── 5F94A1
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_001.csv
│   │   ├── ride_002.csv
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_002_summary.json
│   │   ├── ride_003.csv
│   │   └── session_metadata.json
│   ├── 6207C9
│   │   ├── eeprom.bin
│   │   ├── ride_6207C9_001.csv
│   │   └── session_metadata.json
│   ├── 653DC0
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── eeprom.json
│   │   ├── ride_653DC0_001.csv
│   │   ├── ride_653DC0_002.csv
│   │   ├── ride_653DC0_003.csv
│   │   ├── ride_653DC0_004.csv
│   │   └── session_metadata.json
│   ├── 917900
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_001.csv
│   │   ├── ride_001_errorlog.json
│   │   ├── ride_001_summary.json
│   │   ├── ride_002.csv
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_002_summary.json
│   │   ├── ride_003.csv
│   │   ├── ride_003_errorlog.json
│   │   ├── ride_003_summary.json
│   │   └── session_metadata.json
│   ├── 9ECD1E
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_001.csv
│   │   ├── ride_001_errorlog.json
│   │   ├── ride_001_summary.json
│   │   ├── ride_002.csv
│   │   ├── ride_003.csv
│   │   ├── ride_004.csv
│   │   ├── ride_004_errorlog.json
│   │   ├── ride_004_summary.json
│   │   ├── ride_005.csv
│   │   ├── ride_006.csv
│   │   ├── ride_006_summary.json
│   │   ├── ride_007.csv
│   │   ├── ride_007_summary.json
│   │   └── session_metadata.json
│   ├── AC501E
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── eeprom_state_ride_001.json
│   │   ├── eeprom_state_ride_002.json
│   │   ├── eeprom_state_ride_003.json
│   │   ├── ride_001_errorlog.json
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_AC501E_001.csv
│   │   ├── ride_AC501E_002.csv
│   │   ├── ride_AC501E_002_summary.json
│   │   ├── ride_AC501E_003.csv
│   │   ├── ride_AC501E_004.csv
│   │   └── session_metadata.json
│   ├── D7B333
│   │   ├── consolidated.csv
│   │   ├── eeprom.bin
│   │   ├── ride_001_errorlog.json
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_003_errorlog.json
│   │   ├── ride_D7B333_001.csv
│   │   ├── ride_D7B333_001_summary.json
│   │   ├── ride_D7B333_002.csv
│   │   ├── ride_D7B333_002_summary.json
│   │   ├── ride_D7B333_003.csv
│   │   ├── ride_D7B333_003_summary.json
│   │   └── session_metadata.json
│   ├── E8D511
│   │   ├── consolidated.csv
│   │   ├── consolidated.tmp
│   │   ├── eeprom.bin
│   │   ├── ride_001.csv
│   │   ├── ride_001_errorlog.json
│   │   ├── ride_001_summary.json
│   │   ├── ride_002.csv
│   │   ├── ride_002_errorlog.json
│   │   ├── ride_002_summary.json
│   │   ├── ride_003.csv
│   │   ├── ride_003_errorlog.json
│   │   ├── ride_003_summary.json
│   │   ├── ride_004.csv
│   │   ├── ride_004_summary.json
│   │   └── session_metadata.json
│   └── EF4995
│       ├── consolidated.csv
│       ├── eeprom.bin
│       ├── ride_001.csv
│       └── session_metadata.json
├── tools
│   ├── diagnose_pi.sh
│   ├── make_index.py
│   ├── test_ecu.py
│   └── test_ecu.py.save
├── web
│   ├── templates
│   │   └── index.html
│   ├── __init__.py
│   └── server.py
├── ARCHITECTURE.md
├── BACKLOG.md
├── CHANGELOG.md
├── DEV_TIPS.md
├── README.md
├── WORKING_METHOD.md
├── WORKING_METHOD.md.save
├── ddfi2_logger.py
├── fix_remove_extra_div_before_script.py.save
├── fix_server_rides.py.save
├── fix_server_rides.py.save.1
├── install.sh
├── main.py
├── network_state.json
├── objectives.json
├── tps_cal.json
└── vss_cal.json
```

---

## Archivos de datos (runtime)

| Archivo | Schema | Descripción |
|---------|--------|-------------|
| `network_state.json` | `{mode, ip, last_wifi_ip, last_switch_utc}` | Estado de red persistido |
| `tps_cal.json` | `{min, max}` | Calibración TPS 10bit |
| `vss_cal.json` | `{cpkm25}` | Calibración velocímetro |
| `objectives.json` | `{cell_targets[], indicators}` | Objetivos de celda VE |

---

## Módulos Python

### `ddfi2_logger.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `LOGGER_VERSION` | `v1.17.0-FORENSIC` |
| `MYSTERY_BYTES` | `{255: {'name': 'EOH_or_IDLE', 'desc': 'End of Header o línea idle', 'sospechoso': False}, 1: {'name': 'SOH', 'desc': 'Start of Header válido', 'sospechoso': False}, 64: {'name': 'BIT6_TPS_HIGH', 'desc': 'Bit 6 - posible DTC TPS alto', 'sospechoso': True}, 96: {'name': 'BITS_5_6_DUAL', 'desc': 'Bits 5+6 - error dual TPS', 'sospechoso': True}, 6: {'name': 'ACK', 'desc': 'Acknowledge válido', 'sospechoso': False}, 0: {'name': 'NULL_PAD', 'desc': 'Null padding', 'sospechoso': True}}` |
| `SOH` | `1` |
| `EOH` | `255` |
| `SOT` | `2` |
| `EOT` | `3` |
| `ACK` | `6` |
| `DROID_ID` | `0` |
| `STOCK_ECM_ID` | `66` |
| `CMD_GET` | `82` |
| `RT_RESPONSE_SIZE` | `107` |
| `RT_VARIABLES` | `{'RPM': (11, 2, 1.0, 0.0), 'Seconds': (9, 2, 1.0, 0.0), 'MilliSec': (8, 1, 0.01, 0.0), 'TPD': (25, 2, 0.1, 0.0), 'Load': (27, 1, 1.0, 0.0), 'TPS_10Bit': (90, 2, 1.0, 0.0), 'Batt_V': (28, 2, 0.01, 0.0), 'CLT': (30, 2, 0.1, -40.0), 'MAT': (32, 2, 0.1, -40.0), 'O2_ADC': (34, 2, 1.0, 0.0), 'WUE': (38, 2, 0.1, 0.0), 'IAT_Corr': (40, 2, 0.1, 0.0), 'Accel_Corr': (42, 2, 0.1, 0.0), 'Decel_Corr': (44, 2, 0.1, 0.0), 'WOT_Corr': (46, 2, 0.1, 0.0), 'Idle_Corr': (48, 2, 0.1, 0.0), 'OL_Corr': (50, 2, 0.1, 0.0), 'AFV': (52, 2, 0.1, 0.0), 'EGO_Corr': (54, 2, 0.1, 0.0), 'spark1': (13, 2, 0.0025, 0.0), 'spark2': (15, 2, 0.0025, 0.0), 'veCurr1_RAW': (17, 2, 1.0, 0.0), 'veCurr2_RAW': (19, 2, 1.0, 0.0), 'pw1': (21, 2, 0.00133, 0.0), 'pw2': (23, 2, 0.00133, 0.0), 'Flags0': (56, 1, 1.0, 0.0), 'Flags1': (57, 1, 1.0, 0.0), 'Flags2': (58, 1, 1.0, 0.0), 'Flags3': (59, 1, 1.0, 0.0), 'Flags4': (60, 1, 1.0, 0.0), 'Flags5': (61, 1, 1.0, 0.0), 'Flags6': (62, 1, 1.0, 0.0), 'Unk63': (63, 1, 1.0, 0.0), 'CDiag0': (67, 1, 1.0, 0.0), 'CDiag1': (68, 1, 1.0, 0.0), 'CDiag2': (69, 1, 1.0, 0.0), 'CDiag3': (70, 1, 1.0, 0.0), 'CDiag4': (71, 1, 1.0, 0.0), 'HDiag0': (75, 1, 1.0, 0.0), 'HDiag1': (76, 1, 1.0, 0.0), 'HDiag2': (77, 1, 1.0, 0.0), 'HDiag3': (78, 1, 1.0, 0.0), 'HDiag4': (79, 1, 1.0, 0.0), 'Unk80': (80, 1, 1.0, 0.0), 'Unk81': (81, 1, 1.0, 0.0), 'Unk82': (82, 1, 1.0, 0.0), 'Rides': (83, 1, 1.0, 0.0), 'DOut': (84, 1, 1.0, 0.0), 'DIn': (85, 1, 1.0, 0.0), 'ETS_ADC': (94, 1, 1.0, 0.0), 'IAT_ADC': (95, 1, 1.0, 0.0), 'SysConfig': (7, 1, 1.0, 0.0), 'BAS_ADC': (65, 2, 1.0, 0.0), 'VSS_Count': (99, 1, 1.0, 0.0), 'Fan_Duty_Pct': (98, 1, 1.0, 0.0), 'VSS_RPM_Ratio': (100, 1, 1.0, 0.0)}` |
| `CSV_COLUMNS` | `['ride_num', 'timestamp_iso', 'time_elapsed_s', 'RPM', 'Load', 'TPD', 'TPS_10Bit', 'CLT', 'MAT', 'Batt_V', 'spark1', 'spark2', 'veCurr1_RAW', 'veCurr2_RAW', 'pw1', 'pw2', 'EGO_Corr', 'WUE', 'AFV', 'IAT_Corr', 'Accel_Corr', 'Decel_Corr', 'WOT_Corr', 'Idle_Corr', 'OL_Corr', 'O2_ADC', 'Flags0', 'Flags1', 'Flags2', 'Flags3', 'Flags4', 'Flags5', 'Flags6', 'Unk63', 'CDiag0', 'CDiag1', 'CDiag2', 'CDiag3', 'CDiag4', 'HDiag0', 'HDiag1', 'HDiag2', 'HDiag3', 'HDiag4', 'Unk80', 'Unk81', 'Unk82', 'Rides', 'DIn', 'DOut', 'ETS_ADC', 'IAT_ADC', 'BAS_ADC', 'SysConfig', 'TPS_V', 'TPS_pct', 'VSS_Count', 'VS_KPH', 'Fan_Duty_Pct', 'VSS_RPM_Ratio', 'Gear', 'dirty_byte_hex', 'dirty_byte_name', 'forensic_event', 'fl_engine_run', 'fl_o2_active', 'fl_accel', 'fl_decel', 'fl_engine_stop', 'fl_wot', 'fl_ignition', 'fl_closed_loop', 'fl_rich', 'fl_learn', 'fl_cam_active', 'fl_kill', 'fl_immob', 'fl_fuel_cut', 'fl_hot', 'do_coil1', 'do_coil2', 'do_inj1', 'do_inj2', 'do_fuel_pump', 'do_tacho', 'do_cel', 'do_fan', 'di_cam', 'di_tacho_fb', 'di_vss', 'di_clutch', 'di_neutral', 'di_crank']` |
| `VSS_CPKM25` | `1368.0` |
| `GEAR_KPH_PER_KRPM` | `[0.0, 7.0, 11.8, 15.4, 19.1, 23.0]` |
| `DTC_MAP` | `{('CDiag0', 0): (14, 'ETS voltaje bajo'), ('CDiag0', 1): (14, 'ETS voltaje alto'), ('CDiag0', 2): (13, 'O2 trasero siempre rico'), ('CDiag0', 3): (13, 'O2 trasero siempre pobre'), ('CDiag0', 4): (13, 'O2 trasero inactivo'), ('CDiag0', 5): (11, 'TPS voltaje bajo'), ('CDiag0', 6): (11, 'TPS voltaje alto'), ('CDiag0', 7): (36, 'Ventilador 1 corto a tierra'), ('CDiag1', 0): (25, 'Bobina 1 voltaje bajo'), ('CDiag1', 1): (25, 'Bobina 1 voltaje alto'), ('CDiag1', 2): (23, 'Inyector 1 voltaje bajo'), ('CDiag1', 3): (23, 'Inyector 1 voltaje alto'), ('CDiag1', 4): (16, 'Batería voltaje bajo'), ('CDiag1', 5): (16, 'Batería voltaje alto'), ('CDiag1', 6): (15, 'IAT voltaje bajo'), ('CDiag1', 7): (15, 'IAT voltaje alto'), ('CDiag2', 0): (35, 'Tacómetro voltaje bajo'), ('CDiag2', 1): (35, 'Tacómetro voltaje alto'), ('CDiag2', 2): (33, 'Bomba combustible voltaje bajo'), ('CDiag2', 3): (33, 'Bomba combustible voltaje alto'), ('CDiag2', 4): (32, 'Inyector 2 voltaje bajo'), ('CDiag2', 5): (32, 'Inyector 2 voltaje alto'), ('CDiag2', 6): (24, 'Bobina 2 voltaje bajo'), ('CDiag2', 7): (24, 'Bobina 2 voltaje alto'), ('CDiag3', 0): (56, 'Sync failure'), ('CDiag3', 1): (55, 'ECM ADC error'), ('CDiag3', 2): (54, 'ECM EEPROM error'), ('CDiag3', 3): (53, 'ECM Flash checksum error'), ('CDiag3', 4): (52, 'ECM RAM failure'), ('CDiag3', 5): (36, 'Ventilador 1 voltaje alto'), ('CDiag3', 6): (44, 'BAS voltaje bajo'), ('CDiag3', 7): (44, 'BAS voltaje alto'), ('CDiag4', 0): (21, 'AMC siempre abierto'), ('CDiag4', 1): (21, 'AMC siempre cerrado'), ('CDiag4', 2): (21, 'AMC corto a tierra'), ('CDiag4', 3): (21, 'AMC corto a alimentación'), ('CDiag4', 4): (0, 'AIC failure'), ('CDiag4', 5): (0, 'Caballete siempre bajo'), ('CDiag4', 6): (0, 'Caballete siempre alto'), ('CDiag4', 7): (0, 'Caballete failure')}` |
| `HDIAG_NAMES` | `['HDiag0', 'HDiag1', 'HDiag2', 'HDiag3', 'HDiag4']` |
| `RPM_BINS` | `[0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]` |
| `LOAD_BINS` | `[10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]` |
| `BUEIB_PARAMS` | `{'KTemp_Fan_On': (498, 1.0, 50.0, '°C', 'Fan ON temperatura (key-on)'), 'KTemp_Fan_Off': (499, 1.0, 50.0, '°C', 'Fan OFF temperatura (key-on)'), 'KTemp_Soft_Hi': (488, 1.0, 200.0, '°C', 'Soft limit trigger (EGO baja)'), 'KTemp_Soft_Lo': (489, 1.0, 200.0, '°C', 'Soft limit release'), 'KTemp_Hard_Hi': (490, 1.0, 200.0, '°C', 'Hard limit trigger (corta chispa)'), 'KTemp_Hard_Lo': (491, 1.0, 200.0, '°C', 'Hard limit release'), 'KTemp_Kill_Hi': (494, 1.0, 200.0, '°C', 'Kill limit trigger (apaga motor)'), 'KTemp_Kill_Lo': (495, 1.0, 200.0, '°C', 'Kill limit release'), 'KTemp_CEL_Flash_Hi': (496, 1.0, 200.0, '°C', 'CEL encendido temperatura'), 'KTemp_Fan_KO_On': (521, 1.0, 0.0, '°C', 'Fan key-off ON temp'), 'KTemp_Fan_KO_Off': (522, 1.0, 0.0, '°C', 'Fan key-off OFF temp'), 'KTemp_RPM_Soft': (485, 50.0, 0.0, 'RPM', 'RPM min para soft limit temp'), 'KTemp_RPM_Hard': (487, 50.0, 0.0, 'RPM', 'RPM min para hard limit temp'), 'KTemp_TP_Soft': (484, 1.0, 0.0, 'TPS', 'TPS min para soft limit temp'), 'KTemp_TP_Hard': (486, 1.0, 0.0, 'TPS', 'TPS min para hard limit temp'), 'KRPM_Soft_Hi': (458, 50.0, 0.0, 'RPM', 'RPM soft limit trigger'), 'KRPM_Soft_Lo': (459, 50.0, 0.0, 'RPM', 'RPM soft limit release'), 'KRPM_Hard_Hi': (460, 50.0, 0.0, 'RPM', 'RPM hard limit trigger'), 'KRPM_Hard_Lo': (461, 50.0, 0.0, 'RPM', 'RPM hard limit release'), 'KRPM_Kill_Hi': (464, 50.0, 0.0, 'RPM', 'RPM kill limit trigger'), 'KRPM_Kill_Lo': (465, 50.0, 0.0, 'RPM', 'RPM kill limit release'), 'KO2_Midpoint': (186, 0.00196, 0.0, 'V', 'O2 target voltage'), 'KO2_Rich': (187, 0.00196, 0.0, 'V', 'O2 rich threshold'), 'KO2_Lean': (188, 0.00196, 0.0, 'V', 'O2 lean threshold'), 'KO2_Min_RPM': (190, 50.0, 0.0, 'RPM', 'Closed loop min RPM'), 'KFBFuel_Max': (379, 0.4, 0.0, '%', 'EGO correction max'), 'KFBFuel_Min': (380, 0.4, -102.0, '%', 'EGO correction min'), 'KLFuel_Max': (395, 0.4, 0.0, '%', 'AFV max'), 'KLFuel_Min': (396, 0.4, -102.0, '%', 'AFV min'), 'KTPS0': (200, 0.00244, 0.0, 'V', 'TPS cerrado voltage'), 'KTPSV_Range': (201, 0.00244, 0.0, 'V', 'TPS voltage range'), 'KMFG_Year': (3, 1.0, 0.0, '', 'Anio fabricacion ECM'), 'KMFG_Day': (4, 1.0, 0.0, '', 'Dia fabricacion ECM'), 'KEngineRun': (6, 50.0, 0.0, 'RPM', 'RPM minimo motor encendido'), 'Ride_Counter': (1, 1.0, 0.0, '', 'Contador de rides')}` |
| `PORT` | `8080` |
| `HOTSPOT_CON` | `buell-hotspot` |
| `WIFI_TIMEOUT_S` | `60` |
| `TARGET_LOOP_HZ` | `8.0` |
| `MAX_CONSECUTIVE_ERRORS` | `30` |
| `RPM_START_THRESHOLD` | `300` |
| `RPM_STOP_THRESHOLD` | `100` |
| `STOP_CONFIRM_SECS` | `5.0` |
| `ECU_LOST_TOLERANCE_S` | `10.0` |
| `WAITING_POLL_SECS` | `3.0` |
| `POWEROFF_AFTER_SECS` | `60` |
| `INIT_WAIT_SECS` | `5.0` |
| `DASHBOARD_UPDATE_HZ` | `1.0` |
| `BUEIB_PAGES` | `[(1, 0, 256), (2, 256, 256), (3, 512, 158), (4, 670, 256), (5, 926, 256), (6, 1182, 24)]` |

**Clase `CellTracker`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `reset` | — |
| `update` | — |
| `snapshot` | Retorna copia thread-safe del estado. |

**Clase `LiveHandler`**

| Método | Docstring |
|--------|-----------|
| `log_message` | — |
| `_json` | — |
| `do_GET` | — |
| `do_POST` | — |
| `do_OPTIONS` | — |

**Clase `LiveDashboard`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_load_json` | — |
| `_save_json` | — |
| `_default_objectives` | — |
| `save_ve_tables` | — |
| `save_objectives` | — |
| `update_state` | Llamado desde el reading loop del logger, ~1Hz. |
| `get_live_json` | — |
| `keepalive` | — |
| `browser_alive` | True si el browser hizo keepalive en los últimos window_s se |
| `request_shutdown` | — |
| `_errorlog_meta` | Retorna has_errorlog, errorlog_events, errorlog_summary para |
| `get_rides` | Lista rides usando summary JSON — sin leer CSVs. |
| `get_ride_summary` | Carga el summary JSON del ride — sin leer el CSV. |
| `start` | — |
| `stop` | — |

**Clase `NetworkManager`**

| Método | Docstring |
|--------|-----------|
| `ensure_hotspot` | Crea el perfil buell-hotspot si no existe. |
| `_run` | — |
| `_wifi_connected` | — |
| `_hotspot_active` | — |
| `setup` | Configura red al arrancar: crea hotspot si no hay WiFi, o de |
| `ssh_active` | — |
| `current_mode` | Retorna 'wifi', 'hotspot' o 'none'. |
| `switch_to_wifi` | Baja hotspot y conecta al perfil WiFi guardado explícitament |
| `switch_to_hotspot` | Baja WiFi y activa hotspot. |
| `connect_to_profile` | Conecta a un perfil NM guardado por nombre. |
| `add_and_connect` | Agrega perfil nuevo y conecta. |
| `scan_wifi` | Escanea redes disponibles. |
| `saved_wifi` | Lista perfiles WiFi guardados con su SSID. |
| `forget_wifi` | Elimina un perfil guardado. |
| `start_monitor` | Thread que vigila la conexión cada 30s y activa hotspot si s |

**Clase `DDFI2Connection`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `connect` | — |
| `disconnect` | — |
| `usb_reset` | Fuerza un reset USB del FT232RL via sysfs (authorized toggle |
| `_send` | — |
| `_read_exact` | — |
| `get_version` | Reintentar hasta 5 veces con flush — ECU puede estar en modo |
| `_sync_to_soh` | Descarta basura del buffer hasta encontrar SOH (0x01). |
| `_flush_and_retry_soh` | Segundo intento: vacía el buffer, reenvía PDU_RT_DATA y busc |
| `get_rt_data` | — |
| `read_eeprom_page` | — |
| `read_full_eeprom` | Lee las 6 páginas del BUEIB/DDFI-2 → 1206 bytes. |

**Clase `RideErrorLog`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `start` | — |
| `update_last_sample` | Llamar con cada sample válido para tener contexto en caso de |
| `_elapsed` | Tiempo elapsed actual — se lo pasa el caller. |
| `_event` | — |
| `serial_exception` | SerialException — puerto físicamente roto o USB dropout. |
| `dirty_bytes` | Primer byte del paquete no es SOH — interferencia eléctrica. |
| `bad_checksum` | Paquete completo recibido pero checksum incorrecto. |
| `ecu_timeout` | ECU dejó de responder — timeout acumulado. |
| `ecu_reset` | Contador seconds de la ECU retrocedió — killswitch o reset E |
| `reconnect_attempt` | Intento de reconexión — manual o automático. |
| `flush` | Escribe el archivo solo si hubo eventos. Retorna path o None |
| `counts` | Conteo rápido en memoria para live.json — sin I/O de disco. |
| `has_events` | — |
| `clear` | — |

**Clase `SessionManager`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_checksum` | — |
| `_load_or_create` | — |
| `open_session` | — |
| `start_ride` | — |
| `_open_csv_part` | Abre el archivo CSV de la parte actual del ride. |
| `write_sample` | — |
| `close_current_ride` | — |
| `_save_metadata` | — |
| `_generate_consolidated` | — |

**Clase `BuellLogger`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_handle_signal` | — |
| `_update_dashboard` | — |
| `_flush_ride` | Cierra el ride + flushea el errorlog. Usar en lugar de llama |
| `_handle_sample` | — |
| `_reading_loop` | — |
| `_waiting_loop` | — |
| `_do_poweroff` | — |
| `run` | — |

---

### `ecu/__init__.py`

---

### `ecu/connection.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `SOH` | `1` |
| `EOH` | `255` |
| `SOT` | `2` |
| `EOT` | `3` |
| `ACK` | `6` |
| `DROID_ID` | `0` |
| `STOCK_ECM_ID` | `66` |
| `CMD_GET` | `82` |
| `RT_RESPONSE_SIZE` | `107` |
| `BUEIB_PAGES` | `[(1, 0, 256), (2, 256, 256), (3, 512, 158), (4, 670, 256), (5, 926, 256), (6, 1182, 24)]` |

**Clase `DDFI2Connection`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `connect` | — |
| `disconnect` | — |
| `usb_reset` | Fuerza reset USB del FT232RL via sysfs (authorized toggle).
 |
| `_send` | — |
| `_read_exact` | — |
| `get_version` | Reintentar hasta 5 veces con flush — ECU puede estar en modo |
| `_sync_to_soh` | Descarta basura del buffer hasta encontrar SOH (0x01). |
| `_flush_and_retry_soh` | Segundo intento: vacía el buffer, reenvía PDU_RT_DATA y busc |
| `get_rt_data` | Lee un frame RT de la ECU. Retorna dict de parámetros o None |
| `read_eeprom_page` | — |
| `read_full_eeprom` | Lee las 6 páginas del BUEIB/DDFI-2 → 1206 bytes. |

---

### `ecu/eeprom.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `BUEIB_PARAMS` | `{'KTemp_Fan_On': (498, 1.0, 50.0, '°C', 'Fan ON temperatura (key-on)'), 'KTemp_Fan_Off': (499, 1.0, 50.0, '°C', 'Fan OFF temperatura (key-on)'), 'KTemp_Soft_Hi': (488, 1.0, 200.0, '°C', 'Soft limit trigger (EGO baja)'), 'KTemp_Soft_Lo': (489, 1.0, 200.0, '°C', 'Soft limit release'), 'KTemp_Hard_Hi': (490, 1.0, 200.0, '°C', 'Hard limit trigger (corta chispa)'), 'KTemp_Hard_Lo': (491, 1.0, 200.0, '°C', 'Hard limit release'), 'KTemp_Kill_Hi': (494, 1.0, 200.0, '°C', 'Kill limit trigger (apaga motor)'), 'KTemp_Kill_Lo': (495, 1.0, 200.0, '°C', 'Kill limit release'), 'KTemp_CEL_Flash_Hi': (496, 1.0, 200.0, '°C', 'CEL encendido temperatura'), 'KTemp_Fan_KO_On': (521, 1.0, 0.0, '°C', 'Fan key-off ON temp'), 'KTemp_Fan_KO_Off': (522, 1.0, 0.0, '°C', 'Fan key-off OFF temp'), 'KTemp_RPM_Soft': (485, 50.0, 0.0, 'RPM', 'RPM min para soft limit temp'), 'KTemp_RPM_Hard': (487, 50.0, 0.0, 'RPM', 'RPM min para hard limit temp'), 'KTemp_TP_Soft': (484, 1.0, 0.0, 'TPS', 'TPS min para soft limit temp'), 'KTemp_TP_Hard': (486, 1.0, 0.0, 'TPS', 'TPS min para hard limit temp'), 'KRPM_Soft_Hi': (458, 50.0, 0.0, 'RPM', 'RPM soft limit trigger'), 'KRPM_Soft_Lo': (459, 50.0, 0.0, 'RPM', 'RPM soft limit release'), 'KRPM_Hard_Hi': (460, 50.0, 0.0, 'RPM', 'RPM hard limit trigger'), 'KRPM_Hard_Lo': (461, 50.0, 0.0, 'RPM', 'RPM hard limit release'), 'KRPM_Kill_Hi': (464, 50.0, 0.0, 'RPM', 'RPM kill limit trigger'), 'KRPM_Kill_Lo': (465, 50.0, 0.0, 'RPM', 'RPM kill limit release'), 'KO2_Midpoint': (186, 0.00196, 0.0, 'V', 'O2 target voltage'), 'KO2_Rich': (187, 0.00196, 0.0, 'V', 'O2 rich threshold'), 'KO2_Lean': (188, 0.00196, 0.0, 'V', 'O2 lean threshold'), 'KO2_Min_RPM': (190, 50.0, 0.0, 'RPM', 'Closed loop min RPM'), 'KFBFuel_Max': (379, 0.4, 0.0, '%', 'EGO correction max'), 'KFBFuel_Min': (380, 0.4, -102.0, '%', 'EGO correction min'), 'KLFuel_Max': (395, 0.4, 0.0, '%', 'AFV max'), 'KLFuel_Min': (396, 0.4, -102.0, '%', 'AFV min'), 'KTPS0': (200, 0.00244, 0.0, 'V', 'TPS cerrado voltage'), 'KTPSV_Range': (201, 0.00244, 0.0, 'V', 'TPS voltage range'), 'KMFG_Year': (3, 1.0, 0.0, '', 'Anio fabricacion ECM'), 'KMFG_Day': (4, 1.0, 0.0, '', 'Dia fabricacion ECM'), 'KEngineRun': (6, 50.0, 0.0, 'RPM', 'RPM minimo motor encendido'), 'Ride_Counter': (1, 1.0, 0.0, '', 'Contador de rides')}` |

---

### `ecu/eeprom_params.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `HEADER_OFFSET` | `0` |

---

### `ecu/protocol.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `SOH` | `1` |
| `EOH` | `255` |
| `SOT` | `2` |
| `EOT` | `3` |
| `ACK` | `6` |
| `RT_RESPONSE_SIZE` | `107` |
| `RT_VARIABLES` | `{'RPM': (11, 2, 1.0, 0.0), 'Seconds': (9, 2, 1.0, 0.0), 'MilliSec': (8, 1, 0.01, 0.0), 'TPD': (25, 2, 0.1, 0.0), 'Load': (27, 1, 1.0, 0.0), 'TPS_10Bit': (90, 2, 1.0, 0.0), 'Batt_V': (28, 2, 0.01, 0.0), 'CLT': (30, 2, 0.1, -40.0), 'MAT': (32, 2, 0.1, -40.0), 'O2_ADC': (34, 2, 1.0, 0.0), 'WUE': (38, 2, 0.1, 0.0), 'IAT_Corr': (40, 2, 0.1, 0.0), 'Accel_Corr': (42, 2, 0.1, 0.0), 'Decel_Corr': (44, 2, 0.1, 0.0), 'WOT_Corr': (46, 2, 0.1, 0.0), 'Idle_Corr': (48, 2, 0.1, 0.0), 'OL_Corr': (50, 2, 0.1, 0.0), 'AFV': (52, 2, 0.1, 0.0), 'EGO_Corr': (54, 2, 0.1, 0.0), 'spark1': (13, 2, 0.0025, 0.0), 'spark2': (15, 2, 0.0025, 0.0), 'veCurr1_RAW': (17, 2, 1.0, 0.0), 'veCurr2_RAW': (19, 2, 1.0, 0.0), 'pw1': (21, 2, 0.00133, 0.0), 'pw2': (23, 2, 0.00133, 0.0), 'Flags0': (56, 1, 1.0, 0.0), 'Flags1': (57, 1, 1.0, 0.0), 'Flags2': (58, 1, 1.0, 0.0), 'Flags3': (59, 1, 1.0, 0.0), 'Flags4': (60, 1, 1.0, 0.0), 'Flags5': (61, 1, 1.0, 0.0), 'Flags6': (62, 1, 1.0, 0.0), 'Unk63': (63, 1, 1.0, 0.0), 'CDiag0': (67, 1, 1.0, 0.0), 'CDiag1': (68, 1, 1.0, 0.0), 'CDiag2': (69, 1, 1.0, 0.0), 'CDiag3': (70, 1, 1.0, 0.0), 'CDiag4': (71, 1, 1.0, 0.0), 'HDiag0': (75, 1, 1.0, 0.0), 'HDiag1': (76, 1, 1.0, 0.0), 'HDiag2': (77, 1, 1.0, 0.0), 'HDiag3': (78, 1, 1.0, 0.0), 'HDiag4': (79, 1, 1.0, 0.0), 'Unk80': (80, 1, 1.0, 0.0), 'Unk81': (81, 1, 1.0, 0.0), 'Unk82': (82, 1, 1.0, 0.0), 'Rides': (83, 1, 1.0, 0.0), 'DOut': (84, 1, 1.0, 0.0), 'DIn': (85, 1, 1.0, 0.0), 'ETS_ADC': (94, 1, 1.0, 0.0), 'IAT_ADC': (95, 1, 1.0, 0.0), 'SysConfig': (7, 1, 1.0, 0.0), 'BAS_ADC': (65, 2, 1.0, 0.0), 'VSS_Count': (99, 1, 1.0, 0.0), 'Fan_Duty_Pct': (98, 1, 1.0, 0.0), 'VSS_RPM_Ratio': (100, 1, 1.0, 0.0)}` |
| `VSS_CPKM25` | `1368.0` |
| `GEAR_KPH_PER_KRPM` | `[0.0, 7.0, 11.8, 15.4, 19.1, 23.0]` |
| `RPM_BINS` | `[0, 800, 1000, 1350, 1900, 2400, 2900, 3400, 4000, 5000, 6000, 7000, 8000]` |
| `LOAD_BINS` | `[10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 175, 255]` |
| `CSV_COLUMNS` | `['ride_num', 'timestamp_iso', 'time_elapsed_s', 'RPM', 'Load', 'TPD', 'TPS_10Bit', 'CLT', 'MAT', 'Batt_V', 'spark1', 'spark2', 'veCurr1_RAW', 'veCurr2_RAW', 'pw1', 'pw2', 'EGO_Corr', 'WUE', 'AFV', 'IAT_Corr', 'Accel_Corr', 'Decel_Corr', 'WOT_Corr', 'Idle_Corr', 'OL_Corr', 'O2_ADC', 'Flags0', 'Flags1', 'Flags2', 'Flags3', 'Flags4', 'Flags5', 'Flags6', 'Unk63', 'CDiag0', 'CDiag1', 'CDiag2', 'CDiag3', 'CDiag4', 'HDiag0', 'HDiag1', 'HDiag2', 'HDiag3', 'HDiag4', 'Unk80', 'Unk81', 'Unk82', 'Rides', 'DIn', 'DOut', 'ETS_ADC', 'IAT_ADC', 'BAS_ADC', 'SysConfig', 'TPS_V', 'TPS_pct', 'VSS_Count', 'VS_KPH', 'Fan_Duty_Pct', 'VSS_RPM_Ratio', 'Gear', 'dirty_byte_hex', 'dirty_byte_name', 'forensic_event', 'fl_engine_run', 'fl_o2_active', 'fl_accel', 'fl_decel', 'fl_engine_stop', 'fl_wot', 'fl_ignition', 'fl_closed_loop', 'fl_rich', 'fl_learn', 'fl_cam_active', 'fl_kill', 'fl_immob', 'fl_fuel_cut', 'fl_hot', 'do_coil1', 'do_coil2', 'do_inj1', 'do_inj2', 'do_fuel_pump', 'do_tacho', 'do_cel', 'do_fan', 'di_cam', 'di_tacho_fb', 'di_vss', 'di_clutch', 'di_neutral', 'di_crank', 'buf_in', 'ttl_pct', 'cpu_pct', 'cpu_temp', 'mem_pct']` |

---

### `ecu/session.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `LOGGER_VERSION` | `v2.3.0-MODULAR` |
| `MAX_CSV_ROWS` | `10000` |

**Clase `SessionManager`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_checksum` | Calculate session checksum from tune region of EEPROM blob.
 |
| `_load_or_create` | — |
| `open_session` | Open or resume session based on EEPROM blob checksum.
A new  |
| `save_eeprom` | Guarda blob EEPROM en sessions/CHECKSUM/eeprom.bin. |
| `load_eeprom` | Carga eeprom.bin de la sesión actual. Retorna bytes o None. |
| `start_ride` | — |
| `_open_csv_part` | Abre el archivo CSV de la parte actual del ride. |
| `write_sample` | — |
| `close_current_ride` | — |
| `_save_metadata` | — |
| `_generate_consolidated` | — |

**Clase `CellTracker`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `reset` | — |
| `update` | — |
| `snapshot` | Retorna copia thread-safe del estado. |

**Clase `RideErrorLog`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `start` | — |
| `update_last_sample` | — |
| `_event` | — |
| `serial_exception` | — |
| `dirty_bytes` | — |
| `bad_checksum` | — |
| `ecu_timeout` | — |
| `ecu_reset` | — |
| `reconnect_attempt` | — |
| `flush` | — |
| `counts` | — |
| `has_events` | — |
| `clear` | — |

---

### `ecu/version_resolver.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `_ECM_TABLE` | `None` |

---

### `main.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `TARGET_HZ` | `8.0` |
| `RPM_START` | `300` |
| `RPM_STOP` | `100` |
| `STOP_CONFIRM_S` | `5.0` |
| `MAX_CONSEC` | `30` |

**Clase `BuellLogger`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_handle_signal` | — |
| `_sysmon_loop` | System monitor thread — runs always, independent of ECU.
Upd |
| `_ecu_loop` | Thread de lectura RT — 8Hz, actualiza web.ecu_live y graba r |
| `run` | Loop principal. |
| `shutdown` | Limpieza al salir. |

---

### `network/__init__.py`

---

### `network/manager.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `HOTSPOT_CON` | `buell-hotspot` |
| `HOTSPOT_IP` | `10.42.0.1` |
| `WIFI_TIMEOUT_S` | `35` |
| `DEFAULT_PASSWORD` | `buell2024` |

**Clase `NetworkManager`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_run` | — |
| `_wifi_connected` | — |
| `_hotspot_active` | — |
| `current_mode` | — |
| `get_ip` | — |
| `get_wifi_ip` | — |
| `_save_state` | — |
| `load_state` | — |
| `get_redirect_url` | — |
| `get_switch_status` | — |
| `_set_switch_status` | — |
| `ensure_hotspot_profile` | — |
| `setup` | — |
| `switch_to_wifi` | — |
| `switch_to_hotspot` | — |
| `connect_to_profile` | — |
| `add_and_connect` | — |
| `scan_wifi` | — |
| `saved_wifi` | — |
| `forget_wifi` | — |
| `start_monitor` | — |
| `stop_monitor` | — |
| `ssh_active` | — |

---

### `tools/test_ecu.py`

**Constantes**

| Nombre | Valor |
|--------|-------|
| `PORT` | `/dev/ttyUSB0` |
| `BAUD` | `9600` |
| `SOH` | `1` |
| `EOH` | `255` |
| `SOT` | `2` |
| `EOT` | `3` |
| `ACK` | `6` |

---

### `web/__init__.py`

---

### `web/server.py`

**Clase `DashboardHandler`**

| Método | Docstring |
|--------|-----------|
| `log_message` | — |
| `_json` | — |
| `_html` | — |
| `do_OPTIONS` | — |
| `do_GET` | — |
| `do_POST` | — |
| `_load_html` | — |
| `_get_live` | — |

**Clase `WebServer`**

| Método | Docstring |
|--------|-----------|
| `__init__` | — |
| `_get_rides` | — |
| `start` | — |
| `stop` | — |

---

## Endpoints HTTP (`web/server.py`)

**GET**

- `/live.json`
- `/csv/`

**POST**

- `/ride/`
- `/errorlog/`
- `/rides`
- `/maps`
- `/eeprom`
- `/wifi/saved`
- `/wifi/scan`
- `/wifi/status`
- `/wifi/redirect_url`
- `/ride_note`
- `/network`
- `/wifi/connect`
- `/wifi/add`
- `/wifi/forget`
- `/shutdown`
- `/keepalive`
- `/git_pull`
- `/close_ride`
- `/restart_logger`
- `/reboot_pi`

---

## Dashboard (`web/templates/index.html`)

**Tabs**

- `ride`
- `rides`
- `graph`
- `ve`
- `cfg`
- `net`

**Funciones JS**

- `showTab()`
- `buildGrid()`
- `updateGrid()`
- `fmtTime()`
- `updateHeader()`
- `renderObjectives()`
- `renderIndicators()`
- `fetchLive()`
- `loadMaps()`
- `showMap()`
- `heatColor()`
- `loadObj()`
- `saveObj()`
- `handleMsqDrop()`
- `handleMsqFile()`
- `parseMsq()`
- `closeRide()`
- `switchNet()`
- `_showSwitchModal()`
- `_hideSwitchModal()`
- `_pollSwitchStatus()`
- `updateNetStatus()`
- `loadNetPane()`
- `doConnect()`
- `doForget()`
- `doWifiScan()`
- `prefillWifi()`
- `doAddWifi()`
- `loadSessions()`
- `toggleSession()`
- `openNoteModal()`
- `closeNoteModal()`
- `saveNote()`
- `viewSingleRide()`
- `openRideGraph()`
- `openLiveRideGraph()`
- `loadRidesList()`
- `viewSelectedRides()`
- `exitHistory()`
- `trackUsage()`
- `loadUsageStats()`
- `clearUsageStats()`
- `destroyCharts()`
- `markerSet()`
- `parseCSVtoRows()`
- `extractTransitions()`
- `detectGearChanges()`
- `detectWOT()`
- `detectDTC()`
- `buildCharts()`
- `initGraphPane()`
- `_fillGraphSelect()`
- `_rideDate()`
- `loadGraphRide()`
- `doKeepalive()`
- `confirmShutdown()`
- `doShutdown()`
- `toggleEcu()`
- `ecuRow()`
- `loadEepromParams()`
- `loadEcu()`
- `doReconnect()`
- `doRestartLogger()`
- `doRebootPi()`
- `loadVssCal()`
- `gitPull()`
- `saveVssCal()`
- `loadTpsCal()`
- `calcTpsPct()`
- `saveTpsCal()`
- `startTpsCapture()`

---

## `install.sh`

_Sin pasos numerados detectados._
