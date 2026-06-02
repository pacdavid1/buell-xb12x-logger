#!/usr/bin/env python3
"""tools/test_csv_humidity.py - Test humidity_pct CSV writing."""
import csv, os, sys
sys.path.insert(0, '/home/pi/buell')

try:
    from ecu.protocol import CSV_COLUMNS
    print(f"CSV_COLUMNS: {len(CSV_COLUMNS)} columns")
    print(f"humidity_pct index: {CSV_COLUMNS.index('humidity_pct')}")
except Exception as e:
    print(f"Error loading CSV_COLUMNS: {e}")
    sys.exit(1)

if 'humidity_pct' not in CSV_COLUMNS:
    print("ERROR: humidity_pct NOT in CSV_COLUMNS!")
    sys.exit(1)

csv_path = '/tmp/test_humidity.csv'

row = {c: 0 for c in CSV_COLUMNS}
row.update({
    'ride_num': 999,
    'timestamp_iso': '2026-06-02T12:00:00',
    'time_elapsed_s': 1.0,
    'RPM': 1500,
    'CLT': 85,
    'cpu_temp': 45.0,
    'baro_hPa': 1004.3,
    'baro_temp_c': 22.0,
    'humidity_pct': 57.8,
})

with open(csv_path, 'w', newline='') as f:
    f.write("# logger=v2.6.79\n")
    w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
    w.writeheader()
    w.writerow(row)
    row['time_elapsed_s'] = 2.0
    row['humidity_pct'] = 57.9
    w.writerow(row)

# Verify
with open(csv_path, 'r') as f:
    content = f.read()

print(f"\nFile: {csv_path} ({os.path.getsize(csv_path)} bytes)")
lines = content.strip().split('\n')
print(f"Lines: {len(lines)}")
print(f"First data line: {lines[1] if len(lines) > 1 else 'N/A'}")

if '57.8' in content:
    print("\nPASS: humidity_pct=57.8 FOUND in CSV!")
    # Show truncated line
    idx = content.index('57.8')
    start = max(0, idx - 40)
    end = min(len(content), idx + 40)
    print(f"  Context: ...{content[start:end]}...")
else:
    print("\nFAIL: humidity_pct value not found in CSV")

os.remove(csv_path)
print(f"Cleaned up: {csv_path}")
