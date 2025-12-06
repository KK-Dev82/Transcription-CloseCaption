#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Transcription Service บน Pod
#
# วิธีใช้งาน:
#   bash scripts/pod/check-service-status.sh [EXTERNAL_PORT]
#
# Parameters:
#   EXTERNAL_PORT  - External port (optional, default: 41462)
#
# Port Configuration:
#   - Internal Port: 8010 (บน Pod)
#   - External Port: 41462 (default) หรือระบุเอง

set -e

# Parse optional external port parameter
EXTERNAL_PORT="${1:-41462}"
INTERNAL_PORT="8010"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_DIR="/workspace/transcription-service"
LOG_FILE="/tmp/transcription-service.log"
PID_FILE="/tmp/transcription-service.pid"

echo "📊 Transcription Service Status"
echo "==============================="
echo ""

# Check 1: Process Status
echo "1️⃣  Process Status"
echo "─────────────────"
PID=$(pgrep -f "uvicorn.*app.main:app.*${INTERNAL_PORT}" | head -1)
if [ ! -z "$PID" ]; then
    echo -e "${GREEN}✅ Service is RUNNING${NC}"
    echo "   PID: $PID"
    
    # Check PID file
    if [ -f "$PID_FILE" ]; then
        STORED_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ "$STORED_PID" = "$PID" ]; then
            echo -e "   ${GREEN}✓${NC} PID file matches: $PID_FILE"
        else
            echo -e "   ${YELLOW}⚠${NC} PID file mismatch: $PID_FILE (stored: $STORED_PID, running: $PID)"
        fi
    fi
    
    # Process details
    if command -v ps > /dev/null; then
        CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | xargs || echo "N/A")
        MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | xargs || echo "N/A")
        TIME=$(ps -p $PID -o etime --no-headers 2>/dev/null | xargs || echo "N/A")
        echo "   CPU: ${CPU}%"
        echo "   Memory: ${MEM}%"
        echo "   Uptime: ${TIME}"
    fi
else
    echo -e "${RED}❌ Service is NOT running${NC}"
    if [ -f "$PID_FILE" ]; then
        STORED_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ ! -z "$STORED_PID" ] && ps -p "$STORED_PID" > /dev/null 2>&1; then
            # PID exists but doesn't match pattern (might be different port)
            PROCESS_CMD=$(ps -p "$STORED_PID" -o cmd --no-headers 2>/dev/null | head -1 || echo "")
            echo -e "   ${YELLOW}⚠${NC} PID file exists (PID: $STORED_PID) but doesn't match expected pattern"
            echo "   Process: ${PROCESS_CMD:0:80}..."
        else
            echo -e "   ${YELLOW}⚠${NC} PID file exists but process not found: $PID_FILE"
            if [ ! -z "$STORED_PID" ]; then
                echo "   Stored PID: $STORED_PID (process may have crashed)"
            fi
        fi
    fi
fi
echo ""

# Check 2: Port Status
echo "2️⃣  Port Status"
echo "──────────────"
if command -v netstat > /dev/null; then
    PORT_STATUS=$(netstat -tlnp 2>/dev/null | grep ":${INTERNAL_PORT}" || echo "")
elif command -v ss > /dev/null; then
    PORT_STATUS=$(ss -tlnp 2>/dev/null | grep ":${INTERNAL_PORT}" || echo "")
else
    PORT_STATUS=""
fi

if [ ! -z "$PORT_STATUS" ]; then
    echo -e "${GREEN}✅ Port ${INTERNAL_PORT} is LISTENING${NC}"
    echo "$PORT_STATUS" | head -1 | sed 's/^/   /'
else
    echo -e "${RED}❌ Port ${INTERNAL_PORT} is NOT listening${NC}"
fi
echo ""

# Check 3: Health Check
echo "3️⃣  Health Check"
echo "───────────────"
HEALTH_RESPONSE=$(curl -s -m 5 http://localhost:${INTERNAL_PORT}/health 2>&1 || echo "ERROR")
if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
    echo -e "${GREEN}✅ Health check PASSED${NC}"
    echo "   Response: $(echo "$HEALTH_RESPONSE" | head -1 | cut -c1-100)"
elif echo "$HEALTH_RESPONSE" | grep -q "502\|Bad Gateway"; then
    echo -e "${RED}❌ Health check FAILED${NC}"
    echo "   Error: 502 Bad Gateway (nginx running but service not responding)"
elif echo "$HEALTH_RESPONSE" | grep -q "ERROR\|Connection refused"; then
    echo -e "${RED}❌ Health check FAILED${NC}"
    echo "   Error: Cannot connect to service"
else
    echo -e "${YELLOW}⚠️  Health check UNKNOWN${NC}"
    echo "   Response: $(echo "$HEALTH_RESPONSE" | head -1 | cut -c1-100)"
fi
echo ""

# Check 4: API Endpoint
echo "4️⃣  API Endpoint"
echo "───────────────"
API_RESPONSE=$(curl -s -m 5 http://localhost:${INTERNAL_PORT}/ 2>&1 || echo "ERROR")
if echo "$API_RESPONSE" | grep -q "Transcription\|message"; then
    echo -e "${GREEN}✅ API is responding${NC}"
    MESSAGE=$(echo "$API_RESPONSE" | grep -o '\"message\":\"[^\"]*\"' | head -1 || echo "")
    if [ ! -z "$MESSAGE" ]; then
        echo "   $MESSAGE"
    fi
else
    echo -e "${YELLOW}⚠️  API may not be ready${NC}"
fi
echo ""

# Check 5: Log File
echo "5️⃣  Log File"
echo "────────────"
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    LOG_LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
    LAST_MODIFIED=$(stat -c %y "$LOG_FILE" 2>/dev/null | cut -d'.' -f1 || stat -f "%Sm" "$LOG_FILE" 2>/dev/null || echo "N/A")
    
    echo -e "${GREEN}✅ Log file exists${NC}"
    echo "   Path: $LOG_FILE"
    echo "   Size: $LOG_SIZE"
    echo "   Lines: $LOG_LINES"
    echo "   Last modified: $LAST_MODIFIED"
    
    # Show last few lines
    echo ""
    echo "   Last 5 lines:"
    tail -5 "$LOG_FILE" | sed 's/^/   | /' || echo "   (empty)"
else
    echo -e "${YELLOW}⚠️  Log file not found${NC}"
    echo "   Expected: $LOG_FILE"
fi
echo ""

# Check 6: GPU Environment (if available)
echo "6️⃣  GPU Environment"
echo "──────────────────"
if command -v nvidia-smi > /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1 || echo "")
    if [ ! -z "$GPU_INFO" ]; then
        echo -e "${GREEN}✅ GPU Available${NC}"
        echo "   $GPU_INFO"
    else
        echo -e "${YELLOW}⚠️  GPU information unavailable${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  nvidia-smi not available${NC}"
fi

# Check GPU usage in environment
if [ ! -z "$CUDA_VISIBLE_DEVICES" ]; then
    echo "   CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
fi
echo ""

# Check 7: External Access
echo "7️⃣  External Access"
echo "───────────────────"
EXTERNAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || curl -s ifconfig.me 2>/dev/null || echo "80.15.7.37")
EXTERNAL_URL="http://${EXTERNAL_IP}:${EXTERNAL_PORT}"
INTERNAL_URL="http://localhost:${INTERNAL_PORT}"

echo "   Internal URL: $INTERNAL_URL/health"
echo "   External URL: $EXTERNAL_URL/health"
echo "   Port mapping: ${EXTERNAL_PORT} -> ${INTERNAL_PORT}"
echo ""

# Check internal access
echo "   Checking internal access..."
INTERNAL_RESPONSE=$(curl -s -m 5 "$INTERNAL_URL/health" 2>&1 || echo "ERROR")
if echo "$INTERNAL_RESPONSE" | grep -q "healthy\|status"; then
    echo -e "   ${GREEN}✅ Internal access OK${NC}"
else
    echo -e "   ${RED}❌ Internal access FAILED${NC}"
fi

# Check external access
echo "   Checking external access..."
EXTERNAL_RESPONSE=$(curl -s -m 5 "$EXTERNAL_URL/health" 2>&1 || echo "ERROR")

if echo "$EXTERNAL_RESPONSE" | grep -q "healthy\|status"; then
    echo -e "   ${GREEN}✅ External access OK${NC}"
    echo "   External port mapping: ${EXTERNAL_PORT} -> ${INTERNAL_PORT}"
elif echo "$EXTERNAL_RESPONSE" | grep -q "ERROR\|Connection refused\|Network is unreachable"; then
    echo -e "   ${YELLOW}⚠️  External access blocked or port not exposed${NC}"
    echo "   Port mapping: ${EXTERNAL_PORT} -> ${INTERNAL_PORT}"
    echo "   💡 Check RunPod port mapping: ${EXTERNAL_PORT} should forward to ${INTERNAL_PORT}"
else
    echo -e "   ${YELLOW}⚠️  External access status unknown${NC}"
fi
echo ""

# Summary
echo "==============================="
echo "📋 Summary"
echo "==============================="

if [ ! -z "$PID" ]; then
    echo -e "${GREEN}✅ Service Status: RUNNING${NC}"
else
    echo -e "${RED}❌ Service Status: NOT RUNNING${NC}"
fi

if [ -f "$LOG_FILE" ]; then
    echo -e "${GREEN}✅ Log File: EXISTS${NC}"
else
    echo -e "${YELLOW}⚠️  Log File: NOT FOUND${NC}"
fi

echo ""
echo "💡 Useful Commands:"
echo "   View logs:    tail -f $LOG_FILE"
echo "   Stop service: bash scripts/pod/stop-service.sh"
echo "   Start service: bash scripts/pod/start-service-daemon.sh"
echo ""

