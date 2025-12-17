#!/bin/bash
# Monitor logs during test to identify which script causes worker to stop

set -e

LOG_DIR="logs"
TEST_LOG="logs/test_monitor_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"
touch "$TEST_LOG"

echo "🔍 Starting log monitoring..." | tee -a "$TEST_LOG"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$TEST_LOG"
echo "" | tee -a "$TEST_LOG"

# Monitor worker log for signals
echo "📋 Monitoring worker logs for signals..." | tee -a "$TEST_LOG"
tail -f "$LOG_DIR/video-worker.log" 2>/dev/null | grep --line-buffered -E "signal|SIGTERM|SIGINT|kill|restart|health" | while read line; do
    echo "[$(date '+%H:%M:%S')] WORKER LOG: $line" | tee -a "$TEST_LOG"
done &
WORKER_LOG_PID=$!

# Monitor health check log
if [ -f "$LOG_DIR/worker-health-check.log" ]; then
    echo "📋 Monitoring health check logs..." | tee -a "$TEST_LOG"
    tail -f "$LOG_DIR/worker-health-check.log" 2>/dev/null | while read line; do
        echo "[$(date '+%H:%M:%S')] HEALTH CHECK: $line" | tee -a "$TEST_LOG"
    done &
    HEALTH_CHECK_LOG_PID=$!
fi

# Monitor system processes that might kill worker
echo "📋 Monitoring processes that might kill worker..." | tee -a "$TEST_LOG"
while true; do
    # Check for pkill/kill commands targeting video_worker
    ps aux | grep -E "pkill.*video_worker|kill.*video_worker|restart.*worker" | grep -v grep | while read line; do
        echo "[$(date '+%H:%M:%S')] PROCESS: $line" | tee -a "$TEST_LOG"
    done
    
    # Check worker status
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1 || echo "")
    if [ -z "$WORKER_PID" ]; then
        echo "[$(date '+%H:%M:%S')] ⚠️  WORKER STOPPED!" | tee -a "$TEST_LOG"
        echo "[$(date '+%H:%M:%S')] Checking recent processes..." | tee -a "$TEST_LOG"
        
        # Check recent commands
        history | tail -20 | grep -E "kill|pkill|restart|worker" | while read line; do
            echo "[$(date '+%H:%M:%S')] RECENT COMMAND: $line" | tee -a "$TEST_LOG"
        done
    fi
    
    sleep 2
done &
PROCESS_MONITOR_PID=$!

# Cleanup function
cleanup() {
    echo "" | tee -a "$TEST_LOG"
    echo "🛑 Stopping log monitoring..." | tee -a "$TEST_LOG"
    kill $WORKER_LOG_PID 2>/dev/null || true
    kill $HEALTH_CHECK_LOG_PID 2>/dev/null || true
    kill $PROCESS_MONITOR_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for test to complete
echo "⏳ Waiting for test to complete (press Ctrl+C to stop monitoring)..." | tee -a "$TEST_LOG"
wait

