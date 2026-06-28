#!/usr/bin/env python3
"""Compress CSV files older than 30 days to save disk space.
Run via cron weekly or manually."""
import gzip
import os
import time
import shutil
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"
MAX_AGE_DAYS = 30
MIN_AGE_SECS = 300  # 5 min buffer — skip files possibly being written

def main():
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    count = 0
    saved_bytes = 0
    for csv_path in sorted(SESSIONS_DIR.rglob("*.csv")):
        gz_path = csv_path.with_suffix(".csv.gz")
        if gz_path.exists():
            continue
        mtime = os.path.getmtime(str(csv_path))
        if mtime > cutoff:
            continue  # too recent
        if mtime > time.time() - MIN_AGE_SECS:
            continue  # possibly being written right now
        orig_size = csv_path.stat().st_size
        try:
            with open(csv_path, "rb") as fin:
                with gzip.open(gz_path, "wb", mtime=0) as fout:
                    shutil.copyfileobj(fin, fout)
            csv_path.unlink()
            count += 1
            saved_bytes += orig_size - gz_path.stat().st_size
        except (OSError, PermissionError) as e:
            # File might be locked — clean up partial gz and skip
            if gz_path.exists():
                gz_path.unlink()
            print(f"  Skipped {csv_path.name}: {e}")
    print(f"Compressed {count} files, saved {saved_bytes // 1024} KB")

if __name__ == "__main__":
    main()
