#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Pod Services ทั้งหมด
# วิธีใช้งาน: bash scripts/pod/check-pod.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔍 ตรวจสอบสถานะ Pod Services${NC}"
echo -e "${CYAN}📅 $(date)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Counters
SERVICES_OK=0
SERVICES_FAIL=0

# 1. ตรวจสอบ Whisper API (port 8002)
echo -e "${BLUE}1. Whisper API (port 8002)${NC}"
WHISPER_PID=$(pgrep -f "python.*whisper_api" | head -1)
if [ ! -z "$WHISPER_PID" ]; then
    if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Running${NC} (PID: $WHISPER_PID) - Health OK"
        ((SERVICES_OK++))
    else
        echo -e "   ${YELLOW}⚠️  Running${NC} (PID: $WHISPER_PID) - Health check failed"
        ((SERVICES_FAIL++))
    fi
else
    echo -e "   ${RED}❌ Not Running${NC}"
    ((SERVICES_FAIL++))
fi
echo ""

# 2. ตรวจสอบ Video Worker
echo -e "${BLUE}2. Video Worker${NC}"
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ ! -z "$WORKER_PID" ]; then
    echo -e "   ${GREEN}✅ Running${NC} (PID: $WORKER_PID)"
    ((SERVICES_OK++))
else
    echo -e "   ${RED}❌ Not Running${NC}"
    ((SERVICES_FAIL++))
fi
echo ""

# 3. ตรวจสอบ Main API (port 8010)
echo -e "${BLUE}3. Main API (port 8010)${NC}"
API_PID=$(pgrep -f "python.*uvicorn.*app.main" | head -1)
if [ ! -z "$API_PID" ]; then
    if curl -sf http://localhost:8010/health > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Running${NC} (PID: $API_PID) - Health OK"
        ((SERVICES_OK++))
    else
        echo -e "   ${YELLOW}⚠️  Running${NC} (PID: $API_PID) - Health check failed"
        ((SERVICES_FAIL++))
    fi
else
    echo -e "   ${RED}❌ Not Running${NC}"
    ((SERVICES_FAIL++))
fi
echo ""

# 4. ตรวจสอบ RQ Workers (ถ้ามี)
echo -e "${BLUE}4. RQ Workers (optional)${NC}"
RQ_COUNT=$(pgrep -f "rq worker" | wc -l)
if [ "$RQ_COUNT" -gt 0 ]; then
    echo -e "   ${GREEN}✅ Running${NC} ($RQ_COUNT workers)"
else
    echo -e "   ${YELLOW}ℹ️  Not Running${NC} (optional for RQ mode)"
fi
echo ""

# สรุป
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📊 สรุป${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $SERVICES_FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ All core services are running! ($SERVICES_OK/3)${NC}"
else
    echo -e "${RED}❌ Some services are not running ($SERVICES_OK/3 OK)${NC}"
    echo ""
    echo -e "${YELLOW}💡 วิธีแก้ไข:${NC}"
    echo "   bash scripts/pod/start-pod.sh"
fi

echo ""
echo -e "${BLUE}💡 คำสั่งเพิ่มเติม:${NC}"
echo "   - ดู logs: bash scripts/pod/logs-pod.sh"
echo "   - Start services: bash scripts/pod/start-pod.sh"
echo "   - Restart services: bash scripts/pod/restart-pod.sh"
echo ""
