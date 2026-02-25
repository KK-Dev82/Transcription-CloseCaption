#!/bin/bash
# รันทดสอบ Record ก่อน Upload พร้อม monitor CPU/GPU
# Usage: ./scripts/run_test_with_monitor.sh

set -e
cd "$(dirname "$0")/.."
mkdir -p logs

LOG_FILE="logs/test_resources_$(date +%Y%m%d_%H%M%S).csv"
echo "📊 Resource log: $LOG_FILE"

# เริ่ม resource monitor ในพื้นหลัง
bash scripts/watch_resources.sh 2 --log "$LOG_FILE" &
WATCH_PID=$!
trap "kill $WATCH_PID 2>/dev/null || true" EXIT

sleep 2
echo "✅ Resource monitor started (PID $WATCH_PID)"
echo ""

# รันทดสอบ
python scripts/test_record_before_upload.py
EXIT_CODE=$?

# สรุป resource
echo ""
echo "=========================================="
echo "📈 Resource Summary (จาก $LOG_FILE)"
echo "=========================================="
if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE") -gt 1 ]; then
    echo "Format: timestamp,cpu,gpu0,gpu1,pwr_w,ram_pct"
    echo ""
    echo "Sample (first 5):"
    head -6 "$LOG_FILE"
    echo "..."
    echo "Sample (last 10):"
    tail -10 "$LOG_FILE"
    echo ""
    echo "Stats (excluding header):"
    tail -n +2 "$LOG_FILE" | awk -F',' '{
        cpu+=$2; g0+=$3; g1+=$4; pwr+=$5; ram+=$6; n++
    } END {
        if(n>0) {
            printf "  CPU avg: %.1f%%\n", cpu/n
            printf "  GPU0 avg: %.1f%%\n", g0/n
            printf "  GPU1 avg: %.1f%%\n", g1/n
            printf "  PWR avg: %.1fW\n", pwr/n
            printf "  RAM avg: %.1f%%\n", ram/n
            printf "  Samples: %d\n", n
        }
    }'
fi
echo "=========================================="

exit $EXIT_CODE
