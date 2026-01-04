#!/bin/bash
# Script สำหรับตรวจสอบ Worker Health และ Heartbeat

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

# Load environment variables
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi

print_info "💓 ตรวจสอบ Worker Health และ Heartbeat"
echo "================================================================================"
echo ""

# ตรวจสอบ processes
print_info "1. ตรวจสอบ Worker Processes:"
worker_count=$(ps aux | grep "rq worker" | grep -v grep | wc -l)
if [ "$worker_count" -gt 0 ]; then
    print_success "พบ $worker_count worker processes"
    echo ""
    ps aux | grep "rq worker" | grep -v grep | awk '{print "   PID:", $2, "|", $11, $12, $13, $14, $15, $16, $17, $18, $19, $20}'
else
    print_error "ไม่พบ worker processes"
fi

echo ""
print_info "2. ตรวจสอบ Worker Heartbeat (ผ่าน RQ):"

# ใช้ Python เพื่อตรวจสอบ heartbeat
python3 << 'PYEOF'
from rq import Worker
from redis import Redis
import os
from datetime import datetime, timezone
import sys

redis_url = os.getenv('REDIS_URL')
if not redis_url:
    print("❌ REDIS_URL not set")
    sys.exit(1)

try:
    conn = Redis.from_url(redis_url, decode_responses=False)
    all_workers = Worker.all(connection=conn)
    
    if not all_workers:
        print("❌ ไม่พบ workers ใน RQ")
        sys.exit(1)
    
    now = datetime.now(timezone.utc)
    healthy_count = 0
    warning_count = 0
    dead_count = 0
    
    print(f"\n✅ พบ {len(all_workers)} workers:\n")
    
    for worker in all_workers:
        worker_name = worker.name
        queues = ', '.join([q.name for q in worker.queues])
        state = worker.state
        
        # ตรวจสอบ heartbeat
        if worker.last_heartbeat:
            last_heartbeat = worker.last_heartbeat
            if isinstance(last_heartbeat, str):
                last_heartbeat = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
            
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
            
            time_since_heartbeat = (now - last_heartbeat).total_seconds()
            
            if time_since_heartbeat < 60:
                status = "✅ Active"
                healthy_count += 1
                heartbeat_info = f"{time_since_heartbeat:.1f} วินาทีที่แล้ว"
            elif time_since_heartbeat < 300:
                status = "⚠️  Warning"
                warning_count += 1
                heartbeat_info = f"{time_since_heartbeat/60:.1f} นาทีที่แล้ว"
            else:
                status = "❌ Dead"
                dead_count += 1
                heartbeat_info = f"{time_since_heartbeat/60:.1f} นาทีที่แล้ว"
        else:
            status = "⚠️  No heartbeat"
            warning_count += 1
            heartbeat_info = "N/A"
        
        print(f"   {status} {worker_name}")
        print(f"      Queues: {queues}")
        print(f"      State: {state}")
        print(f"      Last Heartbeat: {heartbeat_info}")
        
        # ตรวจสอบ current job
        current_job = worker.get_current_job()
        if current_job:
            print(f"      🔄 Current Job: {current_job.id}")
        else:
            print(f"      💤 Idle")
        print()
    
    # สรุป
    print("================================================================================")
    print(f"📊 สรุป:")
    print(f"   ✅ Healthy: {healthy_count}")
    print(f"   ⚠️  Warning: {warning_count}")
    print(f"   ❌ Dead: {dead_count}")
    
    if dead_count > 0:
        print("\n⚠️  มี workers ที่อาจจะตาย - ควร restart workers")
        sys.exit(1)
    elif warning_count > 0:
        print("\n⚠️  มี workers ที่มี heartbeat เก่า - ควรตรวจสอบ")
        sys.exit(0)
    else:
        print("\n✅ Workers ทั้งหมด healthy!")
        sys.exit(0)
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    print_success "Worker health check completed"
else
    print_warning "Worker health check completed with warnings"
fi

