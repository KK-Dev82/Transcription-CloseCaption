#!/bin/bash
# Release on_hold tasks เมื่อ record_backlog == 0
# ใช้เมื่อ: tasks ค้าง on_hold, Main API ไม่รัน, หรือต้องการ release แบบ manual
#
# วิธีใช้:
#   ./scripts/run_release_on_hold.sh
#   ./scripts/run_release_on_hold.sh --loop 30   # รันทุก 30 วินาที (สำหรับ cron/background)
set -e
cd "$(dirname "$0")/.."
[[ -f .venv/bin/activate ]] && source .venv/bin/activate

if [[ "$1" == "--loop" ]]; then
  INTERVAL="${2:-30}"
  echo "Releasing on_hold every ${INTERVAL}s (Ctrl+C to stop)"
  while true; do
    python3 -c "
from app.services.on_hold_release import try_release_on_hold_tasks
r = try_release_on_hold_tasks()
if r > 0:
    print(f'Released {r} task(s)')
"
    sleep "$INTERVAL"
  done
else
  python3 -c "
from app.services.on_hold_release import try_release_on_hold_tasks
r = try_release_on_hold_tasks()
print(f'Released: {r}')
"
fi
