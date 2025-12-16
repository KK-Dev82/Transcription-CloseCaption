#!/bin/bash
# Video Worker Daemon - Auto-restart on crash
# ใช้สำหรับ restart Video Worker อัตโนมัติเมื่อ crash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

WORKER_LOG="/tmp/video-worker.log"
WORKER_PID_FILE="/tmp/video-worker.pid"
RESTART_DELAY=10
MAX_RESTARTS=10
RESTART_COUNT=0

# Setup environment
export PYTHONPATH=/workspace/transcription-service
export TZDIR=/workspace/.local/share/zoneinfo
export TZ=Asia/Bangkok

# Function to start worker
start_worker() {
    print_header "🚀 Starting Video Worker (Attempt $((RESTART_COUNT + 1)))"
    
    # Kill old worker if exists
    if [ -f "$WORKER_PID_FILE" ]; then
        OLD_PID=$(cat "$WORKER_PID_FILE" 2>/dev/null || echo "")
        if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
            print_warning "Killing old worker (PID: $OLD_PID)"
            kill -9 "$OLD_PID" 2>/dev/null || true
            sleep 2
        fi
        rm -f "$WORKER_PID_FILE"
    fi
    
    # Start worker
    cd /workspace/transcription-service
    nohup python3 -m app.workers.video_worker > "$WORKER_LOG" 2>&1 &
    WORKER_PID=$!
    echo "$WORKER_PID" > "$WORKER_PID_FILE"
    
    print_success "Video Worker started (PID: $WORKER_PID)"
    
    # Wait a bit and check if still running
    sleep 5
    if ps -p "$WORKER_PID" > /dev/null 2>&1; then
        print_success "Video Worker is running"
        return 0
    else
        print_error "Video Worker failed to start"
        tail -20 "$WORKER_LOG" 2>/dev/null | tail -10
        return 1
    fi
}

# Function to check worker health
check_worker_health() {
    if [ ! -f "$WORKER_PID_FILE" ]; then
        return 1
    fi
    
    WORKER_PID=$(cat "$WORKER_PID_FILE" 2>/dev/null || echo "")
    if [ -z "$WORKER_PID" ]; then
        return 1
    fi
    
    if ! ps -p "$WORKER_PID" > /dev/null 2>&1; then
        return 1
    fi
    
    # Check if worker is consuming messages
    python3 -c "
import pika
import os
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', '178.128.105.100')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'senate')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'qP2VtHz6fAX4xDksEpMrLT')
try:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials))
    channel = connection.channel()
    method = channel.queue_declare('audio_extraction_queue', passive=True)
    consumer_count = method.method.consumer_count
    connection.close()
    exit(0 if consumer_count > 0 else 1)
except:
    exit(1)
" 2>/dev/null && return 0 || return 1
}

# Main loop
print_header "🔄 Video Worker Daemon - Auto-restart on crash"

while true; do
    if ! check_worker_health; then
        print_warning "Video Worker is not healthy or not running"
        
        if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
            print_error "Max restarts ($MAX_RESTARTS) reached. Stopping daemon."
            exit 1
        fi
        
        RESTART_COUNT=$((RESTART_COUNT + 1))
        print_warning "Restarting Video Worker (attempt $RESTART_COUNT/$MAX_RESTARTS)..."
        
        if start_worker; then
            RESTART_COUNT=0  # Reset counter on successful start
            print_success "Video Worker restarted successfully"
        else
            print_error "Failed to restart Video Worker"
            print_warning "Waiting $RESTART_DELAY seconds before next attempt..."
            sleep $RESTART_DELAY
        fi
    else
        # Worker is healthy, reset restart count
        if [ $RESTART_COUNT -gt 0 ]; then
            RESTART_COUNT=0
            print_success "Video Worker is healthy again"
        fi
    fi
    
    # Check every 30 seconds
    sleep 30
done

