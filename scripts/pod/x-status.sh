#!/bin/bash
# Quick Status Check Script - ตรวจสอบสถานะ Transcription Service แบบเร็ว
#
# วิธีใช้งาน:
#   bash scripts/pod/status.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "📊 Transcription Service Status"
echo "==============================="
echo ""

# Quick checks
PID=$(pgrep -f "uvicorn.*app.main:app.*8001" | head -1)

if [ ! -z "$PID" ]; then
    echo -e "${GREEN}✅ Service: RUNNING${NC} (PID: $PID)"
    
    # Health check
    HEALTH=$(curl -s -m 3 http://localhost:8001/health 2>&1)
    if echo "$HEALTH" | grep -q "healthy\|status"; then
        echo -e "${GREEN}✅ Health: OK${NC}"
    else
        echo -e "${YELLOW}⚠️  Health: CHECK FAILED${NC}"
    fi
    
    # Port
    if netstat -tlnp 2>/dev/null | grep -q ":8001" || ss -tlnp 2>/dev/null | grep -q ":8001"; then
        echo -e "${GREEN}✅ Port: 8001 LISTENING${NC}"
    else
        echo -e "${RED}❌ Port: 8001 NOT LISTENING${NC}"
    fi
    
    # Log file
    if [ -f "/tmp/transcription-service.log" ]; then
        LOG_SIZE=$(du -h /tmp/transcription-service.log | cut -f1)
        echo -e "${GREEN}✅ Log: EXISTS${NC} (Size: $LOG_SIZE)"
    else
        echo -e "${YELLOW}⚠️  Log: NOT FOUND${NC}"
    fi
    
else
    echo -e "${RED}❌ Service: NOT RUNNING${NC}"
fi

echo ""
echo "💡 Run 'bash scripts/pod/check-service-status.sh' for detailed status"

