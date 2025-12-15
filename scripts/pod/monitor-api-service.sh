#!/bin/bash
# Script สำหรับ Monitor และ Auto-restart API Service
# ใช้สำหรับตรวจสอบว่า service ทำงานอยู่หรือไม่ และ restart ถ้าจำเป็น
#
# วิธีใช้งาน:
#   bash scripts/pod/monitor-api-service.sh [INTERNAL_PORT] [CHECK_INTERVAL]
#
# Parameters:
#   INTERNAL_PORT  - Internal port (optional, default: 8010)
#   CHECK_INTERVAL - Check interval in seconds (optional, default: 30)

set -e

# Parse optional parameters
INTERNAL_PORT="${1:-8010}"
CHECK_INTERVAL="${2:-30}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || cd "/workspace/transcription-close-caption-service" 2>/dev/null || {
    echo "❌ Error: Cannot find project directory"
    exit 1
}

LOG_FILE="/tmp/transcription-service.log"
PID_FILE="/tmp/transcription-service.pid"
RESTART_LOG="/tmp/api-service-restart.log"

# Function to check if service is running
check_service() {
    # Check if process exists
    if ! pgrep -f "uvicorn.*app.main.*${INTERNAL_PORT}" > /dev/null; then
        return 1
    fi
    
    # Check if port is listening
    if ! (netstat -tuln 2>/dev/null | grep ":${INTERNAL_PORT} " > /dev/null || \
          ss -tuln 2>/dev/null | grep ":${INTERNAL_PORT} " > /dev/null || \
          lsof -i :${INTERNAL_PORT} 2>/dev/null | grep LISTEN > /dev/null); then
        return 1
    fi
    
    # Check if health endpoint responds
    if ! curl -s -f "http://localhost:${INTERNAL_PORT}/health" > /dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

# Function to restart service
restart_service() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] 🔄 Restarting API Service..." >> "$RESTART_LOG"
    
    # Stop existing service
    if pgrep -f "uvicorn.*app.main.*${INTERNAL_PORT}" > /dev/null; then
        local pid=$(pgrep -f "uvicorn.*app.main.*${INTERNAL_PORT}" | head -1)
        print_warning "Stopping existing service (PID: $pid)..."
        kill $pid 2>/dev/null || true
        sleep 2
        
        if pgrep -f "uvicorn.*app.main.*${INTERNAL_PORT}" > /dev/null; then
            pkill -9 -f "uvicorn.*app.main.*${INTERNAL_PORT}" 2>/dev/null || true
            sleep 1
        fi
    fi
    
    # Start service using start-service-daemon.sh
    if [ -f "scripts/pod/start-service-daemon.sh" ]; then
        print_status "Starting API Service..."
        bash scripts/pod/start-service-daemon.sh "${INTERNAL_PORT}" >> "$RESTART_LOG" 2>&1
        
        # Wait for service to be ready
        local max_wait=60
        local elapsed=0
        while [ $elapsed -lt $max_wait ]; do
            if check_service; then
                print_success "✅ Service restarted successfully"
                echo "[$timestamp] ✅ Service restarted successfully" >> "$RESTART_LOG"
                return 0
            fi
            sleep 2
            elapsed=$((elapsed + 2))
        done
        
        print_error "❌ Service did not start within ${max_wait} seconds"
        echo "[$timestamp] ❌ Service did not start within ${max_wait} seconds" >> "$RESTART_LOG"
        return 1
    else
        print_error "❌ start-service-daemon.sh not found"
        echo "[$timestamp] ❌ start-service-daemon.sh not found" >> "$RESTART_LOG"
        return 1
    fi
}

# Main monitoring loop
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 API Service Monitor                                      ║"
echo "║  Port: ${INTERNAL_PORT}                                        ║"
echo "║  Check Interval: ${CHECK_INTERVAL}s                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Initialize restart log
echo "=== API Service Monitor Started at $(date) ===" > "$RESTART_LOG"

while true; do
    if ! check_service; then
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        print_warning "⚠️  Service is not running or not responding (${timestamp})"
        echo "[$timestamp] ⚠️  Service check failed" >> "$RESTART_LOG"
        
        # Get last few lines of service log
        if [ -f "$LOG_FILE" ]; then
            echo "[$timestamp] Last 10 lines of service log:" >> "$RESTART_LOG"
            tail -10 "$LOG_FILE" >> "$RESTART_LOG" 2>/dev/null || true
        fi
        
        # Restart service
        restart_service
    else
        local pid=$(pgrep -f "uvicorn.*app.main.*${INTERNAL_PORT}" | head -1)
        print_success "✅ Service is running (PID: $pid)"
    fi
    
    sleep "$CHECK_INTERVAL"
done

