#!/bin/bash
# Script สำหรับตรวจสอบและแก้ไขปัญหาการ Transcription
#
# วิธีใช้งาน:
#   bash scripts/pod/fix-transcription-issues.sh [server]
#
# ตัวอย่าง:
#   bash scripts/pod/fix-transcription-issues.sh 4080s
#   bash scripts/pod/fix-transcription-issues.sh 4000-ada

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SERVER="${1:-4080s}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔧 Fix Transcription Issues - $SERVER                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to run command on server
run_ssh() {
    ssh "$SERVER" "$@"
}

# 1. Check RabbitMQ Connection
echo -e "${CYAN}1. ตรวจสอบ RabbitMQ Connection${NC}"
echo "──────────────────────────────────────────"

RABBITMQ_CHECK=$(run_ssh "python3 -c \"
import os
import sys
sys.path.insert(0, '/workspace/transcription-service')
os.environ['RABBITMQ_HOST'] = '178.128.105.100'
os.environ['RABBITMQ_PORT'] = '5672'
os.environ['RABBITMQ_USER'] = 'senate'
os.environ['RABBITMQ_PASSWORD'] = 'qP2VtHz6fAX4xDksEpMrLT'

try:
    import aio_pika
    import asyncio
    
    async def test():
        try:
            connection = await aio_pika.connect_robust(
                'amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/',
                timeout=5
            )
            await connection.close()
            print('OK')
        except Exception as e:
            print(f'ERROR: {e}')
            sys.exit(1)
    
    asyncio.run(test())
except ImportError as e:
    print(f'IMPORT_ERROR: {e}')
    sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
\"" 2>&1)

if echo "$RABBITMQ_CHECK" | grep -q "OK"; then
    echo -e "${GREEN}   ✅ RabbitMQ: Connected${NC}"
else
    echo -e "${RED}   ❌ RabbitMQ: Failed${NC}"
    echo "      Error: $(echo "$RABBITMQ_CHECK" | tail -1)"
    echo ""
    echo -e "${YELLOW}   💡 Solution: ตรวจสอบ env.runpod และ restart service${NC}"
fi
echo ""

# 2. Check Queue Arguments Consistency
echo -e "${CYAN}2. ตรวจสอบ Queue Arguments${NC}"
echo "──────────────────────────────────────────"

QUEUE_CHECK=$(run_ssh "curl -s -u senate:qP2VtHz6fAX4xDksEpMrLT 'http://178.128.105.100:15672/api/queues' | python3 -c \"
import sys, json
try:
    data = json.load(sys.stdin)
    queues = [q for q in data if 'transcription' in q['name'].lower()]
    
    if not queues:
        print('NO_QUEUES')
    else:
        for q in queues:
            name = q['name']
            messages = q.get('messages', 0)
            consumers = q.get('consumers', 0)
            args = q.get('arguments', {})
            
            print(f'{name}:')
            print(f'  Messages: {messages}')
            print(f'  Consumers: {consumers}')
            if args:
                print(f'  Args: {args}')
            print()
except Exception as e:
    print(f'ERROR: {e}')
\"" 2>&1)

if echo "$QUEUE_CHECK" | grep -q "NO_QUEUES"; then
    echo -e "${YELLOW}   ⚠️  ไม่พบ Transcription queues${NC}"
elif echo "$QUEUE_CHECK" | grep -q "ERROR"; then
    echo -e "${RED}   ❌ Error checking queues${NC}"
    echo "$QUEUE_CHECK"
else
    echo "$QUEUE_CHECK" | while read -r line; do
        if echo "$line" | grep -q "Consumers: 0"; then
            echo -e "${RED}   ⚠️  $line${NC}"
        else
            echo "   $line"
        fi
    done
fi
echo ""

# 3. Check Recent Errors
echo -e "${CYAN}3. ตรวจสอบ Recent Errors${NC}"
echo "──────────────────────────────────────────"

ERRORS=$(run_ssh "tail -200 /workspace/transcription-service/logs/video_worker.log 2>/dev/null | grep -iE 'error|failed|exception|traceback' | tail -20" || echo "No errors found")

if [ "$ERRORS" != "No errors found" ] && [ -n "$ERRORS" ]; then
    echo -e "${RED}   Recent errors:${NC}"
    echo "$ERRORS" | while read -r line; do
        echo "      $line"
    done
else
    echo -e "${GREEN}   ✅ No recent errors${NC}"
fi
echo ""

# 4. Check Service Status
echo -e "${CYAN}4. ตรวจสอบ Service Status${NC}"
echo "──────────────────────────────────────────"

API_STATUS=$(run_ssh "curl -sf http://localhost:8010/health 2>/dev/null && echo 'OK' || echo 'FAILED'")
WORKER_STATUS=$(run_ssh "systemctl is-active video-worker 2>/dev/null || ps aux | grep -E 'video_worker|python.*workers' | grep -v grep | wc -l")

if [ "$API_STATUS" = "OK" ]; then
    echo -e "${GREEN}   ✅ API Service: Running${NC}"
else
    echo -e "${RED}   ❌ API Service: Not responding${NC}"
fi

if [ "$WORKER_STATUS" = "active" ] || [ "$WORKER_STATUS" -gt 0 ]; then
    echo -e "${GREEN}   ✅ Worker Service: Active${NC}"
else
    echo -e "${RED}   ❌ Worker Service: Not running${NC}"
fi
echo ""

# 5. Check Environment Variables
echo -e "${CYAN}5. ตรวจสอบ Environment Variables${NC}"
echo "──────────────────────────────────────────"

ENV_CHECK=$(run_ssh "cd /workspace/transcription-service && cat env.runpod 2>/dev/null | grep -E '^RABBITMQ_|^VIDEO_WORKER_TYPE' | head -10" || echo "")

if [ -n "$ENV_CHECK" ]; then
    echo "$ENV_CHECK" | while read -r line; do
        if echo "$line" | grep -q "RABBITMQ_HOST=178.128.105.100"; then
            echo -e "${GREEN}   ✅ $line${NC}"
        elif echo "$line" | grep -q "RABBITMQ_HOST="; then
            echo -e "${YELLOW}   ⚠️  $line (ควรเป็น 178.128.105.100)${NC}"
        else
            echo "   $line"
        fi
    done
else
    echo -e "${YELLOW}   ⚠️  ไม่พบ env.runpod${NC}"
fi
echo ""

# 6. Suggest Fixes
echo -e "${CYAN}6. แนะนำการแก้ไข${NC}"
echo "──────────────────────────────────────────"

FIXES_NEEDED=false

if ! echo "$RABBITMQ_CHECK" | grep -q "OK"; then
    echo -e "${YELLOW}   🔧 Fix RabbitMQ Connection:${NC}"
    echo "      1. ตรวจสอบ env.runpod: RABBITMQ_HOST=178.128.105.100"
    echo "      2. Restart service: bash scripts/pod/restart-service-daemon.sh"
    FIXES_NEEDED=true
fi

if [ "$API_STATUS" != "OK" ]; then
    echo -e "${YELLOW}   🔧 Fix API Service:${NC}"
    echo "      1. Restart API: bash scripts/pod/restart-service-daemon.sh"
    FIXES_NEEDED=true
fi

if [ "$WORKER_STATUS" != "active" ] && [ "$WORKER_STATUS" -eq 0 ]; then
    echo -e "${YELLOW}   🔧 Fix Worker Service:${NC}"
    echo "      1. Start worker: bash scripts/pod/start-service-daemon.sh"
    FIXES_NEEDED=true
fi

if echo "$QUEUE_CHECK" | grep -q "Consumers: 0"; then
    echo -e "${YELLOW}   🔧 Fix Queue Consumers:${NC}"
    echo "      1. ตรวจสอบ queue arguments ตรงกัน"
    echo "      2. ลบ queue เก่าและ restart service (ถ้าจำเป็น)"
    echo "      3. ตรวจสอบ logs: tail -100 logs/video_worker.log"
    FIXES_NEEDED=true
fi

if [ "$FIXES_NEEDED" = false ]; then
    echo -e "${GREEN}   ✅ ไม่พบปัญหาที่ต้องแก้ไข${NC}"
fi
echo ""

# 7. Quick Fix Commands
echo -e "${CYAN}7. Quick Fix Commands${NC}"
echo "──────────────────────────────────────────"
echo "  # Restart Service"
echo "  ssh $SERVER 'bash /workspace/transcription-service/scripts/pod/restart-service-daemon.sh'"
echo ""
echo "  # Check Logs"
echo "  ssh $SERVER 'tail -100 /workspace/transcription-service/logs/video_worker.log'"
echo ""
echo "  # Check RabbitMQ Queues"
echo "  ssh $SERVER 'bash /workspace/transcription-service/scripts/pod/check-rabbitmq-queue.sh'"
echo ""

