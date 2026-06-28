#!/usr/bin/env python3
# DEV NOTE: All code, comments, and variable names must be in English.
"""
Local dashboard launcher -- runs the Buell WebServer against local session data,
no Pi / no hardware. The Pi only does logging; all analysis + dashboard is pure
software over the recorded CSVs.

Usage:
  py serve_local.py            # self-test: start, hit endpoints, stop
  py serve_local.py --serve    # keep serving at http://127.0.0.1:8080
"""
import logging
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')

# buell_dir = this script's directory (works regardless of cwd)
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from web.server import WebServer

HOST, PORT = '127.0.0.1', 8080
ws = WebServer(host=HOST, port=PORT, buell_dir=str(BASE))
ws.start()
time.sleep(1.5)

base_url = f'http://{HOST}:{PORT}'
endpoints = ['/', '/sessions_vs', '/tuner/sessions']
ok = True
for ep in endpoints:
    try:
        r = urllib.request.urlopen(base_url + ep, timeout=8)
        print(f'  {ep:24} -> HTTP {r.status}')
    except Exception as e:
        ok = False
        print(f'  {ep:24} -> FAILED: {e}')

if ok:
    print(f'\nLOCAL DASHBOARD OK -> {base_url}')
else:
    print('\nSELF-TEST had failures (see above)')

if '--serve' in sys.argv:
    print('Serving... Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
ws.stop()
