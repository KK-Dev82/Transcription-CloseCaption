#!/bin/bash
# ลบ FE Live Caption temp files (processed_tmp_*.wav, typhoon_proc_*.wav)
# ใช้เมื่อ storage เต็มหรือต้องการ clear เอง

set -e
cd "$(dirname "$0")/../.."
PROJECT_ROOT="$(pwd)"

TEMP_DIR="${FE_CC_TEMP_DIR:-storage/cc_temp}"
MAX_AGE_HOURS="${1:-0}"  # 0 = ลบทั้งหมด, ไม่ระบุก็ลบทั้งหมด

echo "🧹 CC Temp Cleanup"
echo "   Temp dir: $TEMP_DIR"
echo "   Max age: ${MAX_AGE_HOURS:-0} hours (0 = all)"

python3 -c "
from pathlib import Path
import time
import os

temp_dir = Path('$TEMP_DIR').resolve()
project_root = Path('$PROJECT_ROOT')
max_age = float('$MAX_AGE_HOURS') if '$MAX_AGE_HOURS' else 0
cutoff = time.time() - (max_age * 3600) if max_age > 0 else 0

patterns = ('processed_tmp*.wav', 'typhoon_proc_*.wav')
dirs_to_scan = [temp_dir]
if project_root != temp_dir:
    dirs_to_scan.append(project_root)

deleted = 0
bytes_freed = 0
for scan_dir in dirs_to_scan:
    if not scan_dir.exists():
        continue
    for pattern in patterns:
        for f in scan_dir.glob(pattern):
            try:
                if max_age <= 0 or f.stat().st_mtime < cutoff:
                    sz = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    bytes_freed += sz
            except Exception as e:
                print(f'  ⚠️ {f}: {e}')

print(f'✅ Deleted {deleted} files ({bytes_freed / 1024 / 1024:.2f} MB)')
"
