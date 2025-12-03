#!/bin/bash
# Script สำหรับ Debug ปัญหา 50 Concurrency Test
#
# วิธีใช้งาน:
#   bash scripts/test/debug-concurrency-issues.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

PROJECT_DIR="/workspace/transcription-service"
LOG_FILE="/tmp/transcription-service.log"
SERVICE_PORT="8010"

print_header "╔══════════════════════════════════════════════════════════════╗"
print_header "║  🔍 Debug Concurrency Test Issues                            ║"
print_header "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Checking for: Server disconnected, Connection reset by peer"
echo ""

cd "$PROJECT_DIR" 2>/dev/null || echo "⚠️  Project directory not found, continuing..."

# 1. Service Status
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 1️⃣  Service Status                                          │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

PID=$(pgrep -f "uvicorn.*app.main:app.*${SERVICE_PORT}" | head -1)
if [ ! -z "$PID" ]; then
    echo -e "${GREEN}✅ Service is RUNNING${NC}"
    echo "   PID: $PID"
    
    # Check CPU and Memory
    if command -v ps > /dev/null; then
        CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | xargs || echo "N/A")
        MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | xargs || echo "N/A")
        RSS=$(ps -p $PID -o rss --no-headers 2>/dev/null | xargs || echo "N/A")
        echo "   CPU: ${CPU}%"
        echo "   Memory: ${MEM}% (RSS: ${RSS} KB)"
        
        # Check file descriptors
        FD_COUNT=$(ls -1 /proc/$PID/fd 2>/dev/null | wc -l || echo "0")
        FD_LIMIT=$(ulimit -n 2>/dev/null || echo "1024")
        echo "   File Descriptors: ${FD_COUNT} / ${FD_LIMIT}"
    fi
    
    # Check if service is responsive
    if curl -s -f http://localhost:${SERVICE_PORT}/health > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Health check: OK${NC}"
    else
        echo -e "   ${RED}❌ Health check: FAILED${NC}"
    fi
else
    echo -e "${RED}❌ Service is NOT running${NC}"
fi
echo ""

# 2. Active Connections
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 2️⃣  Active Connections (Port ${SERVICE_PORT})                │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if command -v netstat > /dev/null; then
    CONN_COUNT=$(netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTABLISHED | wc -l || echo "0")
    echo "   Established connections: ${CONN_COUNT}"
    
    if [ "$CONN_COUNT" -gt 0 ]; then
        echo ""
        echo "   Top connections:"
        netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTABLISHED | head -10 | sed 's/^/   | /'
    fi
    
    TIME_WAIT=$(netstat -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep TIME_WAIT | wc -l || echo "0")
    if [ "$TIME_WAIT" -gt 0 ]; then
        echo ""
        echo -e "   ${YELLOW}⚠️  TIME_WAIT connections: ${TIME_WAIT}${NC}"
    fi
elif command -v ss > /dev/null; then
    CONN_COUNT=$(ss -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTAB | wc -l || echo "0")
    echo "   Established connections: ${CONN_COUNT}"
    
    if [ "$CONN_COUNT" -gt 0 ]; then
        echo ""
        echo "   Top connections:"
        ss -an 2>/dev/null | grep ":${SERVICE_PORT}" | grep ESTAB | head -10 | sed 's/^/   | /'
    fi
fi
echo ""

# 3. System Resources
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 3️⃣  System Resources                                         │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

# Memory
if command -v free > /dev/null; then
    TOTAL_MEM=$(free -h | grep Mem | awk '{print $2}')
    USED_MEM=$(free -h | grep Mem | awk '{print $3}')
    AVAIL_MEM=$(free -h | grep Mem | awk '{print $7}')
    MEM_PERCENT=$(free | grep Mem | awk '{printf "%.1f", ($3/$2) * 100.0}')
    
    echo "   Memory: ${USED_MEM} / ${TOTAL_MEM} used (${MEM_PERCENT}%)"
    echo "   Available: ${AVAIL_MEM}"
    
    if (( $(echo "$MEM_PERCENT > 90" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "   ${RED}❌ Memory usage is HIGH (>90%)${NC}"
    elif (( $(echo "$MEM_PERCENT > 80" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "   ${YELLOW}⚠️  Memory usage is HIGH (>80%)${NC}"
    else
        echo -e "   ${GREEN}✅ Memory usage is OK${NC}"
    fi
fi

# CPU Load
if [ -f /proc/loadavg ]; then
    LOAD=$(cat /proc/loadavg | awk '{print $1}')
    CPU_CORES=$(nproc 2>/dev/null || echo "1")
    
    echo ""
    echo "   Load Average: ${LOAD} (${CPU_CORES} cores)"
fi
echo ""

# 4. Recent Logs - Connection Errors
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 4️⃣  Recent Logs - Connection Errors (Last 100 lines)        │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    LOG_LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
    
    echo "   Log file: $LOG_FILE"
    echo "   Size: $LOG_SIZE"
    echo "   Total lines: $LOG_LINES"
    echo ""
    
    # Count errors
    ERROR_COUNT=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "error|exception|traceback|failed" | wc -l || echo "0")
    CONN_ERROR_COUNT=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | wc -l || echo "0")
    
    echo "   Errors (last 100 lines): ${ERROR_COUNT}"
    echo "   Connection errors: ${CONN_ERROR_COUNT}"
    echo ""
    
    if [ "$CONN_ERROR_COUNT" -gt 0 ]; then
        echo -e "   ${RED}❌ Connection errors found!${NC}"
        echo ""
        echo "   Recent connection errors:"
        tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | tail -10 | sed 's/^/   | /' || echo "   (none found)"
    else
        echo -e "   ${GREEN}✅ No recent connection errors in logs${NC}"
    fi
    
    echo ""
    echo "   Recent errors (last 20 lines):"
    tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "error|exception|traceback|failed" | tail -20 | sed 's/^/   | /' | head -10 || echo "   (no errors found)"
else
    echo -e "   ${YELLOW}⚠️  Log file not found: $LOG_FILE${NC}"
fi
echo ""

# 5. Recent Logs - All Entries
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 5️⃣  Recent Log Entries (Last 50 lines)                      │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    tail -50 "$LOG_FILE" 2>/dev/null | sed 's/^/   | /' || echo "   (empty)"
else
    echo "   ⚠️  Log file not found"
fi
echo ""

# 6. Check for recent transcription requests
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 6️⃣  Recent Transcription Requests (Last 100 lines)          │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    echo "   Requests in last 100 lines:"
    tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "POST /transcribe|GET /transcribe|transcription" | tail -20 | sed 's/^/   | /' || echo "   (no requests found)"
    
    echo ""
    echo "   Failed requests:"
    tail -100 "$LOG_FILE" 2>/dev/null | grep -iE "POST /transcribe.*[45][0-9][0-9]|GET /transcribe.*[45][0-9][0-9]" | tail -10 | sed 's/^/   | /' || echo "   (no failed requests found)"
else
    echo "   ⚠️  Log file not found"
fi
echo ""

# 7. Network Statistics
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 7️⃣  Network Statistics                                       │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f /proc/net/sockstat ]; then
    TCP_INUSE=$(grep TCP /proc/net/sockstat | awk '{print $3}')
    TCP_ORPHAN=$(grep TCP /proc/net/sockstat | awk '{print $7}')
    TCP_TW=$(grep TCP /proc/net/sockstat | awk '{print $9}')
    
    echo "   TCP sockets in use: ${TCP_INUSE}"
    echo "   TCP orphan: ${TCP_ORPHAN}"
    echo "   TCP time wait: ${TCP_TW}"
    
    if [ ! -z "$TCP_ORPHAN" ] && [ "$TCP_ORPHAN" -gt 100 ]; then
        echo -e "   ${YELLOW}⚠️  High number of orphan sockets (>100)${NC}"
    fi
    
    if [ ! -z "$TCP_TW" ] && [ "$TCP_TW" -gt 1000 ]; then
        echo -e "   ${YELLOW}⚠️  High number of TIME_WAIT sockets (>1000)${NC}"
        echo "   (May indicate connection churn)"
    fi
fi
echo ""

# 8. Check Video Worker and RabbitMQ
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 8️⃣  Video Worker & RabbitMQ                                  │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

# Check Video Worker
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ ! -z "$WORKER_PID" ]; then
    echo -e "${GREEN}✅ Video Worker is running (PID: $WORKER_PID)${NC}"
else
    echo -e "${RED}❌ Video Worker is NOT running${NC}"
fi

# Check RabbitMQ connection (if .env exists)
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod 2>/dev/null || true
    set +a
    
    RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
    RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
    
    python3 << EOF 2>/dev/null || echo "   ⚠️  Cannot check RabbitMQ"
import pika
import sys

try:
    credentials = pika.PlainCredentials('${RABBITMQ_USER:-senate}', '${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}')
    parameters = pika.ConnectionParameters(
        host='${RABBITMQ_HOST}',
        port=${RABBITMQ_PORT},
        credentials=credentials,
        connection_attempts=1,
        retry_delay=1
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    queue_name = 'transcription_queue'
    method = channel.queue_declare(queue=queue_name, passive=True)
    message_count = method.method.message_count
    consumer_count = method.method.consumer_count
    
    print("✅ RabbitMQ connection OK")
    print(f"   Queue: {queue_name}")
    print(f"   Messages in queue: {message_count}")
    print(f"   Active consumers: {consumer_count}")
    
    connection.close()
except Exception as e:
    print(f"❌ RabbitMQ connection failed: {e}")
    sys.exit(1)
EOF
else
    echo "   ⚠️  .env.runpod not found, skipping RabbitMQ check"
fi
echo ""

# 9. Check recent task IDs from logs
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 9️⃣  Recent Task IDs (Last 100 lines)                        │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LOG_FILE" ]; then
    # Extract task IDs from logs (UUID pattern)
    TASK_IDS=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | sort -u | head -10)
    
    if [ ! -z "$TASK_IDS" ]; then
        echo "   Recent Task IDs found:"
        echo "$TASK_IDS" | while read task_id; do
            if [ ! -z "$task_id" ]; then
                echo "   • $task_id"
            fi
        done
    else
        echo "   ⚠️  No task IDs found in recent logs"
    fi
fi
echo ""

# 10. Recommendations
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 📊 Diagnostic Summary & Recommendations                      │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

RECOMMENDATIONS=()

if [ -z "$PID" ]; then
    RECOMMENDATIONS+=("❌ Service is not running - Start service: bash scripts/pod/start-service-daemon.sh")
fi

if [ ! -z "$CONN_COUNT" ] && [ "$CONN_COUNT" -gt 50 ]; then
    RECOMMENDATIONS+=("⚠️  High number of concurrent connections (${CONN_COUNT}) - May need to limit concurrent requests")
fi

if [ "$CONN_ERROR_COUNT" -gt 5 ]; then
    RECOMMENDATIONS+=("❌ High number of connection errors (${CONN_ERROR_COUNT}) - Check service stability")
    RECOMMENDATIONS+=("💡 Possible causes: 1) Server overload 2) Connection timeout 3) Service crash")
fi

if [ ! -z "$TCP_TW" ] && [ "$TCP_TW" -gt 1000 ]; then
    RECOMMENDATIONS+=("⚠️  High TIME_WAIT sockets (${TCP_TW}) - May indicate connection churn")
fi

if [ -z "$WORKER_PID" ]; then
    RECOMMENDATIONS+=("❌ Video Worker is not running - Tasks may not be processed")
fi

if [ ${#RECOMMENDATIONS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ No critical issues detected in logs${NC}"
    echo ""
    echo "💡 If you're still experiencing connection issues:"
    echo "   1. Check if 50 concurrent requests is too many for the server"
    echo "   2. Try reducing to 20-30 concurrent requests"
    echo "   3. Monitor logs in real-time: tail -f $LOG_FILE"
    echo "   4. Check external network/firewall settings"
else
    echo "Issues detected:"
    for rec in "${RECOMMENDATIONS[@]}"; do
        echo "   • $rec"
    done
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Diagnostic complete!"
echo ""
echo "💡 Useful commands:"
echo "   View logs: tail -f $LOG_FILE"
echo "   Check status: bash scripts/pod/check-service-status.sh"
echo "   Check connections: bash scripts/pod/check-connection-issues.sh"
echo ""

