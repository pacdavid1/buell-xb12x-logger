From: freebuff
Subject: VDYNO V1 head start — web/vdyno.py already exists

Claude: web/vdyno.py (7,347 bytes) is ALREADY implemented on the Pi.
Do NOT write it from scratch. Details:

FUNCTIONS (9 total):
  _load_cfg() / _smooth() / _read_csv() / _extract_segments()
  _seg_bins() / _build_result_bins() / compute_ride()
  session_bins() / compare_sessions()

compute_ride() takes (buell_dir, session_id, ride_num) → pulls CSV data,
extracts WOT segments, bins by 250 RPM, returns median power + sigma.
Uses numpy. Config in vdyno_config.json (mass=295, CdA=0.60, Crr=0.015,
rho=1.10, tps_min=70%, min_seg=1.5s).

WHAT'S MISSING (needs implementation):
  - Endpoint: GET /vdyno?session=X&ride=N in server.py
  - Comparison: GET /vdyno/compare?a=CS_A&b=CS_B
  - UI: Dyno subtab inside Sessions VS page (Chart.js line P vs RPM)
  - No ride_*_vdyno.json files exist yet (confirm with python3)

TEST DATA:
  Session 248AE2 — 23 rides. Best: ride_029 (12 accel events, 7181 rows)
  Session 00210A — 1 ride, 13 events, HAS baro/gps columns
  Check: python3 -c "from web.vdyno import compute_ride; r=compute_ride('/home/pi/buell','248AE2',29); print(r)"

Do NOT modify web/vdyno.py structure — just add the HTTP+UI layer.
