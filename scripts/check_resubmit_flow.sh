#!/bin/bash
# ตรวจสอบ Resubmit flow: Job ไป Redis แล้ว Workers รับหรือไม่
cd "$(dirname "$0")/.."

echo "=========================================="
echo "1. Queue Status (preprocess, GPU)"
echo "=========================================="
curl -s http://localhost:8010/api/transcribe/debug/queue 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    q = d.get('queues', {})
    for k in ['preprocess', 'preprocess_video_record', 'upload_gpu0', 'upload_gpu1']:
        if k in q:
            v = q[k]
            print(f\"  {k}: queued={v.get('length',0)}, started={v.get('started',0)}, finished={v.get('finished',0)}, failed={v.get('failed',0)}\")
except: print('  (API not available)')
" 2>/dev/null || echo "  API not available - is Main API running?"

echo ""
echo "=========================================="
echo "2. RQ Workers กำลังรันหรือไม่"
echo "=========================================="
if pgrep -f "rq worker" > /dev/null; then
    echo "  Workers: running"
    pgrep -af "rq worker" | head -5
else
    echo "  Workers: NOT RUNNING!"
fi

echo ""
echo "=========================================="
echo "3. Tasks ล่าสุด (queued/processing)"
echo "=========================================="
python3 -c "
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env.runpod')
from app.utils.sqlite_storage import SQLiteStorage
s = SQLiteStorage()
all_list = s.list_all_transcriptions()
recent = [t for t in all_list if t.get('status') in ('queued','processing','pending','on_hold')][:5]
for t in recent:
    print(f\"  {t.get('task_id','')[:8]}... status={t.get('status')} stage={t.get('current_stage')}\")
if not recent:
    print('  (ไม่มี tasks ที่รออยู่)')
" 2>/dev/null || echo "  (script error)"

echo ""
echo "💡 ถ้า preprocess มี queued/started แต่ GPU=0 → รอ preprocess เสร็จก่อน"
echo "💡 ถ้า preprocess=0, GPU=0 → ตรวจสอบ Workers รันอยู่ และ REDIS_URL ตรงกัน"
