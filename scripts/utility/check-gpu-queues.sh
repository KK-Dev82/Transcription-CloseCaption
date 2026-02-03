#!/usr/bin/env bash
# ตรวจสอบความยาวคิว GPU และ Preprocess (สำหรับดูว่า GPU ได้งานเต็มหรือไม่)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"
if [ -f ".env.runpod" ]; then
    set -a
    source .env.runpod
    set +a
fi
NUM_GPUS=${NUM_GPUS:-2}
echo "=== Queue lengths (RQ) ==="
echo "REDIS_URL from env (masked)"
for i in $(seq 0 $((NUM_GPUS - 1))); do
    q="transcription_gpu$i"
    count=$(python3 -c "
import os
from redis import Redis
from rq import Queue
r = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'), decode_responses=True)
q = Queue('$q', connection=r)
print(q.count)
" 2>/dev/null || echo "?")
    echo "  $q: $count jobs"
done
preprocess_count=$(python3 -c "
import os
from redis import Redis
from rq import Queue
r = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'), decode_responses=True)
q = Queue('transcription_preprocess', connection=r)
print(q.count)
" 2>/dev/null || echo "?")
echo "  transcription_preprocess: $preprocess_count jobs"
echo ""
echo "=== GPU workers (process count) ==="
workers=$(pgrep -fc "rq worker.*transcription_gpu" 2>/dev/null || echo "0")
expected=$((NUM_GPUS * ${GPU_WORKERS_PER_GPU:-3}))
echo "  RQ workers listening to transcription_gpu*: $workers (expected: $expected)"
echo ""
echo "=== nvidia-smi (if available) ==="
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total --format=csv,noheader
else
    echo "  nvidia-smi not found"
fi
