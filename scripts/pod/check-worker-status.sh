#!/bin/bash
# Script สำหรับตรวจสอบสถานะ Worker (RabbitMQ Mode)
#
# วิธีใช้งาน:
#   bash scripts/pod/check-worker-status.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔍 ตรวจสอบสถานะ Worker${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. ตรวจสอบ Worker Process
echo -e "${BLUE}1. Worker Process${NC}"
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ ! -z "$WORKER_PID" ]; then
    echo -e "   ${GREEN}✅ Worker Running${NC} (PID: $WORKER_PID)"
    ps aux | grep "$WORKER_PID" | grep -v grep | awk '{print "   Command: " $0}'
else
    echo -e "   ${RED}❌ Worker Not Running${NC}"
fi
echo ""

# 2. ตรวจสอบ Worker Health (port 8030)
echo -e "${BLUE}2. Worker Health Check (port 8030)${NC}"
HEALTH_RESPONSE=$(curl -s -m 3 http://localhost:8030/health 2>&1)
if [ $? -eq 0 ] && echo "$HEALTH_RESPONSE" | grep -q "status"; then
    echo -e "   ${GREEN}✅ Health Endpoint Available${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "   ${RED}❌ Health Endpoint Not Available${NC}"
    echo "   Response: $HEALTH_RESPONSE"
fi
echo ""

# 3. ตรวจสอบ RabbitMQ Connection
echo -e "${BLUE}3. RabbitMQ Connection${NC}"
if [ ! -z "$WORKER_PID" ]; then
    # ตรวจสอบจาก health endpoint
    RABBITMQ_CONNECTED=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('rabbitmq_connected', False))" 2>/dev/null)
    if [ "$RABBITMQ_CONNECTED" = "True" ]; then
        echo -e "   ${GREEN}✅ RabbitMQ Connected${NC}"
    else
        echo -e "   ${YELLOW}⚠️  RabbitMQ Not Connected${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Cannot check (Worker not running)${NC}"
fi
echo ""

# 4. ตรวจสอบ Queue Status (ผ่าน API)
echo -e "${BLUE}4. Queue Status${NC}"
QUEUE_STATUS=$(curl -s -m 3 http://localhost:8010/api/queue/status 2>&1)
if [ $? -eq 0 ] && echo "$QUEUE_STATUS" | grep -q "available"; then
    echo -e "   ${GREEN}✅ Queue Status Available${NC}"
    echo "$QUEUE_STATUS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"   Available: {data.get('available', 'N/A')}\")
    queues = data.get('queues', {})
    for qname, qinfo in queues.items():
        current = qinfo.get('current', 0)
        max_q = qinfo.get('max', 0)
        print(f\"   {qname}: {current}/{max_q} ({(current/max_q*100) if max_q > 0 else 0:.1f}%)\")
except:
    print('   (Error parsing JSON)')
" 2>/dev/null || echo "   (Error parsing response)"
else
    echo -e "   ${YELLOW}⚠️  Queue Status Not Available${NC}"
    echo "   Response: $QUEUE_STATUS"
fi
echo ""

# 5. ตรวจสอบ Worker Logs
echo -e "${BLUE}5. Worker Logs${NC}"
if [ -f "/tmp/video-worker.log" ]; then
    LOG_SIZE=$(du -h /tmp/video-worker.log | cut -f1)
    LOG_LINES=$(wc -l < /tmp/video-worker.log)
    echo -e "   ${GREEN}✅ Log File Exists${NC} (Size: $LOG_SIZE, Lines: $LOG_LINES)"
    echo -e "   ${CYAN}Last 5 lines:${NC}"
    tail -5 /tmp/video-worker.log | sed 's/^/   /'
else
    echo -e "   ${YELLOW}⚠️  Log File Not Found${NC} (/tmp/video-worker.log)"
fi
echo ""

# 6. สรุป
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📊 สรุป${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -z "$WORKER_PID" ]; then
    echo -e "${GREEN}✅ Worker: Running${NC}"
else
    echo -e "${RED}❌ Worker: Not Running${NC}"
    echo ""
    echo -e "${YELLOW}💡 วิธีแก้ไข:${NC}"
    echo "   bash scripts/pod/start-pod.sh"
fi

echo ""
echo -e "${BLUE}💡 คำสั่งเพิ่มเติม:${NC}"
echo "   - ดู worker logs: tail -f /tmp/video-worker.log"
echo "   - ตรวจสอบ queue: curl http://localhost:8010/api/queue/status"
echo "   - ตรวจสอบ health: curl http://localhost:8030/health"
echo ""

