#!/bin/bash
# Script สำหรับตรวจสอบสถานะและ Logs ของ 2 Servers สำหรับการเปรียบเทียบ
#
# วิธีใช้งาน:
#   bash scripts/pod/check-server-comparison.sh [server1] [server2]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SERVER1="${1:-4080s}"
SERVER2="${2:-4000-ada}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 Server Comparison Health Check                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to check server
check_server() {
    local server=$1
    local url=$2
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🔍 Checking: $server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # 1. SSH Connection
    echo -e "${CYAN}1. SSH Connection${NC}"
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$server" "echo 'OK'" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Connected${NC}"
    else
        echo -e "${RED}   ❌ Connection failed${NC}"
        echo ""
        return 1
    fi
    echo ""
    
    # 2. Service Status
    echo -e "${CYAN}2. Service Status${NC}"
    local api_status=$(ssh "$server" "curl -sf $url/health 2>/dev/null && echo 'OK' || echo 'FAILED'")
    local worker_status=$(ssh "$server" "systemctl is-active video-worker 2>/dev/null || echo 'inactive'")
    
    if [ "$api_status" = "OK" ]; then
        echo -e "${GREEN}   ✅ API Service: Running${NC}"
    else
        echo -e "${RED}   ❌ API Service: Not responding${NC}"
    fi
    
    if [ "$worker_status" = "active" ]; then
        echo -e "${GREEN}   ✅ Worker Service: Active${NC}"
    else
        echo -e "${RED}   ❌ Worker Service: $worker_status${NC}"
    fi
    echo ""
    
    # 3. RabbitMQ Connection
    echo -e "${CYAN}3. RabbitMQ Connection${NC}"
    local rmq_check=$(ssh "$server" "python3 -c \"
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
                'amqp://senate:qP2VtHz6fAX4xDksEpMrLT@178.128.105.100:5672/'
            )
            await connection.close()
            print('OK')
        except Exception as e:
            print(f'ERROR: {e}')
            sys.exit(1)
    
    asyncio.run(test())
except Exception as e:
    print(f'IMPORT_ERROR: {e}')
    sys.exit(1)
\"" 2>&1)
    
    if echo "$rmq_check" | grep -q "OK"; then
        echo -e "${GREEN}   ✅ RabbitMQ: Connected${NC}"
    else
        echo -e "${RED}   ❌ RabbitMQ: Failed${NC}"
        echo "      Error: $(echo "$rmq_check" | tail -1)"
    fi
    echo ""
    
    # 4. Queue Status
    echo -e "${CYAN}4. RabbitMQ Queue Status${NC}"
    local queue_info=$(ssh "$server" "curl -s -u senate:qP2VtHz6fAX4xDksEpMrLT 'http://178.128.105.100:15672/api/queues' 2>/dev/null | python3 -c \"
import sys, json
data = json.load(sys.stdin)
queues = {q['name']: {'messages': q.get('messages', 0), 'consumers': q.get('consumers', 0)} for q in data if 'transcription' in q['name'].lower()}
for name, info in queues.items():
    print(f'{name}: {info[\"messages\"]} messages, {info[\"consumers\"]} consumers')
\"" 2>&1)
    
    if [ -n "$queue_info" ]; then
        echo "$queue_info" | while read -r line; do
            if echo "$line" | grep -q "consumers.*[1-9]"; then
                echo -e "${GREEN}   ✅ $line${NC}"
            else
                echo -e "${YELLOW}   ⚠️  $line${NC}"
            fi
        done
    else
        echo -e "${YELLOW}   ⚠️  Could not fetch queue info${NC}"
    fi
    echo ""
    
    # 5. Recent Logs (Errors)
    echo -e "${CYAN}5. Recent Errors (Last 10 lines)${NC}"
    local errors=$(ssh "$server" "tail -100 /workspace/transcription-service/logs/video_worker.log 2>/dev/null | grep -i 'error\\|failed\\|exception' | tail -10" || echo "No errors found")
    
    if [ "$errors" != "No errors found" ] && [ -n "$errors" ]; then
        echo -e "${RED}   Recent errors:${NC}"
        echo "$errors" | while read -r line; do
            echo "      $line"
        done
    else
        echo -e "${GREEN}   ✅ No recent errors${NC}"
    fi
    echo ""
    
    # 6. Resource Usage
    echo -e "${CYAN}6. Resource Usage${NC}"
    local resources=$(ssh "$server" "echo 'CPU:' \$(top -bn1 | grep 'Cpu(s)' | awk '{print \$2}') '| Memory:' \$(free -h | awk '/^Mem:/ {print \$3\"/\"\$2}') '| GPU:' \$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo 'N/A')")
    echo "   $resources"
    echo ""
    
    # 7. Active Tasks
    echo -e "${CYAN}7. Active Transcription Tasks${NC}"
    local active_tasks=$(ssh "$server" "ps aux | grep -E 'video_worker|transcription' | grep -v grep | wc -l")
    echo "   Active processes: $active_tasks"
    echo ""
}

# Get URLs
get_url() {
    case $1 in
        "4080s")
            echo "http://80.15.7.37:41314"
            ;;
        "4000-ada")
            echo "http://87.197.119.40:41314"
            ;;
        *)
            echo "http://localhost:8001"
            ;;
    esac
}

URL1=$(get_url "$SERVER1")
URL2=$(get_url "$SERVER2")

# Check both servers
check_server "$SERVER1" "$URL1"
echo ""
check_server "$SERVER2" "$URL2"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Health check completed${NC}"
echo ""

