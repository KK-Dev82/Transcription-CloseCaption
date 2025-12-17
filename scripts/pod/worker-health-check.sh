#!/bin/bash
# Worker Health Check Script
# ตรวจสอบ worker health และ auto-restart ถ้าไม่ healthy
# ใช้สำหรับ cron job หรือ monitoring system

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

# Setup environment
export PYTHONPATH=/workspace/transcription-service
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
python_site_packages="/workspace/.local/lib/python${python_version}/site-packages"
export PYTHONUSERBASE="/workspace/.local"
export PYTHONPATH="${python_site_packages}:${PYTHONPATH}"

# Health check results
HEALTH_ISSUES=0
WORKER_PID=""

# Check 1: Worker process running
print_info "Checking worker process..."
# Try multiple patterns to find worker process
# Priority: app.workers.video_worker > python3.*video_worker > python.*video_worker > video_worker
WORKER_PID=""
for pattern in "app.workers.video_worker" "python3.*video_worker" "python.*video_worker" "video_worker"; do
    WORKER_PID=$(pgrep -f "$pattern" 2>/dev/null | head -1)
    if [ -n "$WORKER_PID" ]; then
        break
    fi
done

# If still not found, try checking PID file
if [ -z "$WORKER_PID" ] && [ -f "/tmp/video-worker.pid" ]; then
    PID_FROM_FILE=$(cat /tmp/video-worker.pid 2>/dev/null | tr -d '[:space:]')
    if [ -n "$PID_FROM_FILE" ] && ps -p "$PID_FROM_FILE" > /dev/null 2>&1; then
        WORKER_PID="$PID_FROM_FILE"
    fi
fi

if [ -z "$WORKER_PID" ]; then
    print_error "Worker process not running"
    HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
else
    print_success "Worker process running (PID: $WORKER_PID)"
    
    # Check process uptime
    if [ -n "$WORKER_PID" ]; then
        UPTIME=$(ps -o etime= -p "$WORKER_PID" 2>/dev/null | tr -d ' ' || echo "unknown")
        print_info "   Uptime: $UPTIME"
    fi
fi

# Check 2: Worker log file exists and recent
print_info "Checking worker logs..."
WORKER_LOG="logs/video-worker.log"
WORKER_ERROR_LOG="logs/video-worker-errors.log"

if [ -f "$WORKER_LOG" ]; then
    # Check if log was updated in last 5 minutes
    if [ -n "$WORKER_PID" ]; then
        LOG_AGE=$(find "$WORKER_LOG" -mmin -5 2>/dev/null | wc -l)
        if [ "$LOG_AGE" -gt 0 ]; then
            print_success "Worker log is recent (updated in last 5 minutes)"
        else
            print_warning "Worker log is stale (not updated in last 5 minutes)"
            HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
        fi
    fi
    
    # Check for recent errors
    if [ -f "$WORKER_ERROR_LOG" ]; then
        ERROR_COUNT=$(tail -100 "$WORKER_ERROR_LOG" 2>/dev/null | grep -cE "ERROR|CRITICAL|Fatal" || echo "0")
        # Ensure ERROR_COUNT is a number
        ERROR_COUNT=$(echo "$ERROR_COUNT" | tr -d '[:space:]' || echo "0")
        if [ -z "$ERROR_COUNT" ] || [ "$ERROR_COUNT" = "" ]; then
            ERROR_COUNT=0
        fi
        # Convert to integer for comparison
        ERROR_COUNT=$((ERROR_COUNT + 0))
        if [ "$ERROR_COUNT" -gt 10 ]; then
            print_warning "High error count in last 100 lines: $ERROR_COUNT"
            HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
        fi
    fi
else
    print_warning "Worker log file not found"
    HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
fi

# Check 3: RabbitMQ connection and consumers
print_info "Checking RabbitMQ consumers..."
RABBITMQ_CHECK_RESULT=$(python3 << 'EOF' 2>&1
import sys
import os
import pika
from dotenv import load_dotenv

# Load environment
env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'env.runpod')
if os.path.exists(env_file):
    load_dotenv(env_file)

try:
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = int(os.getenv('RABBITMQ_PORT', '5672'))
    rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
    rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=pika.PlainCredentials(rabbitmq_user, rabbitmq_password),
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=5
        )
    )
    channel = connection.channel()
    
    # Check critical queues
    queues = {
        'transcription_request_queue': 0,
        'audio_extraction_queue': 0,
        'transcription_queue': 0
    }
    
    all_ok = True
    total_consumers = 0
    
    for queue_name in queues.keys():
        try:
            method = channel.queue_declare(queue=queue_name, passive=True)
            consumer_count = method.method.consumer_count
            queues[queue_name] = consumer_count
            total_consumers += consumer_count
            
            if consumer_count == 0:
                print(f"❌ No consumers for {queue_name}", file=sys.stderr)
                all_ok = False
            else:
                print(f"✅ {queue_name}: {consumer_count} consumer(s)", file=sys.stderr)
        except Exception as e:
            print(f"❌ Error checking {queue_name}: {e}", file=sys.stderr)
            all_ok = False
    
    connection.close()
    
    if all_ok:
        print(f"✅ Total consumers: {total_consumers}", file=sys.stderr)
        sys.exit(0)
    else:
        sys.exit(1)
        
except pika.exceptions.AMQPConnectionError as e:
    print(f"❌ RabbitMQ connection failed: {e}", file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f"❌ Health check failed: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)

RABBITMQ_CHECK_EXIT=$?

if [ $RABBITMQ_CHECK_EXIT -eq 2 ]; then
    print_error "RabbitMQ connection failed"
    HEALTH_ISSUES=$((HEALTH_ISSUES + 2))  # More severe
elif [ $RABBITMQ_CHECK_EXIT -ne 0 ]; then
    print_error "Consumers not registered properly"
    echo "$RABBITMQ_CHECK_RESULT" | grep -E "❌|✅" || true
    HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
else
    print_success "RabbitMQ consumers are healthy"
    echo "$RABBITMQ_CHECK_RESULT" | grep -E "✅" || true
fi

# Check 4: Memory usage (if worker is running)
if [ -n "$WORKER_PID" ]; then
    print_info "Checking worker memory usage..."
    MEMORY_MB=$(ps -o rss= -p "$WORKER_PID" 2>/dev/null | awk '{print int($1/1024)}' || echo "0")
    if [ "$MEMORY_MB" -gt 0 ]; then
        if [ "$MEMORY_MB" -gt 8192 ]; then
            print_warning "High memory usage: ${MEMORY_MB}MB"
            HEALTH_ISSUES=$((HEALTH_ISSUES + 1))
        else
            print_success "Memory usage: ${MEMORY_MB}MB"
        fi
    fi
fi

# Summary and action
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $HEALTH_ISSUES -eq 0 ]; then
    print_success "Worker is healthy (all checks passed)"
    exit 0
else
    print_error "Worker health check failed ($HEALTH_ISSUES issue(s) found)"
    echo ""
    print_warning "Attempting to restart worker..."
    
    # Log health check failure
    HEALTH_LOG="logs/worker-health-check.log"
    mkdir -p logs
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Health check failed ($HEALTH_ISSUES issues)" >> "$HEALTH_LOG"
    
    # Restart worker
    if bash scripts/pod/restart-worker-only.sh > /tmp/worker-restart.log 2>&1; then
        print_success "Worker restarted successfully"
        exit 0
    else
        print_error "Failed to restart worker"
        print_info "Check logs: tail -50 /tmp/worker-restart.log"
        exit 1
    fi
fi


