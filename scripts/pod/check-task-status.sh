#!/bin/bash
# Script สำหรับตรวจสอบ Task Status
# Usage: bash scripts/pod/check-task-status.sh [task_id]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TASK_ID="${1:-101101f0-6fa8-42c0-8015-c00ae05a8cf8}"
PROJECT_DIR="/workspace/transcription-service"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 ตรวจสอบ Task Status: $TASK_ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$PROJECT_DIR" || exit 1

# ตรวจสอบ metadata.json
METADATA_FILE="storage/transcriptions/$TASK_ID/metadata.json"

if [ ! -f "$METADATA_FILE" ]; then
    echo -e "${RED}❌ ไม่พบไฟล์ metadata.json: $METADATA_FILE${NC}"
    echo ""
    echo "📋 ตรวจสอบว่า task มีอยู่ใน storage หรือไม่:"
    ls -la "storage/transcriptions/$TASK_ID/" 2>/dev/null || echo "   Directory ไม่มีอยู่"
    exit 1
fi

echo -e "${GREEN}✅ พบไฟล์ metadata.json${NC}"
echo ""

# อ่าน metadata
echo "📄 Metadata:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 << EOF
import json
import sys
from pathlib import Path

metadata_file = Path("$METADATA_FILE")
if not metadata_file.exists():
    print("❌ ไม่พบไฟล์ metadata.json")
    sys.exit(1)

try:
    with open(metadata_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # แสดงข้อมูลสำคัญ
    print(f"Task ID: {data.get('task_id', 'N/A')}")
    print(f"Status: {data.get('status', 'N/A')}")
    print(f"Progress: {data.get('progress', 0)}%")
    print(f"Created At: {data.get('created_at', 'N/A')}")
    print(f"Completed At: {data.get('completed_at', 'N/A')}")
    print(f"Started At: {data.get('started_at', 'N/A')}")
    print(f"File Path: {data.get('file_path', 'N/A')}")
    print(f"File Name: {data.get('file_name', 'N/A')}")
    print(f"Language: {data.get('language', 'N/A')}")
    print(f"Model Size: {data.get('model_size', 'N/A')}")
    
    # ตรวจสอบ full_text
    full_text = data.get('full_text', '')
    chunks = data.get('chunks', [])
    print(f"\nFull Text Length: {len(full_text) if full_text else 0} ตัวอักษร")
    print(f"Chunks Count: {len(chunks) if chunks else 0}")
    
    if full_text:
        print(f"\nPreview (100 chars): {full_text[:100]}...")
    else:
        print("\n⚠️ ไม่พบ full_text")
    
    # ตรวจสอบ error
    error_msg = data.get('error_message', '')
    if error_msg:
        print(f"\n❌ Error Message: {error_msg}")
    
    # ตรวจสอบ processing_time
    processing_time = data.get('processing_time') or data.get('time_used')
    if processing_time:
        print(f"\n⏱️ Processing Time: {processing_time} วินาที")
    
except json.JSONDecodeError as e:
    print(f"❌ JSON decode error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ตรวจสอบ RabbitMQ Queue
echo ""
echo "📊 ตรวจสอบ RabbitMQ Queue Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 << 'EOF'
import sys
import os
sys.path.insert(0, '/workspace/transcription-service')

from app.services.rabbitmq_service import RabbitMQService
import json

try:
    rabbitmq = RabbitMQService()
    
    # ตรวจสอบ queue sizes
    queues_to_check = [
        'transcription_request_queue',
        'audio_extraction_queue',
        'transcription_queue'
    ]
    
    for queue_name in queues_to_check:
        try:
            method = rabbitmq.channel.queue_declare(queue=queue_name, passive=True)
            message_count = method.method.message_count
            consumer_count = method.method.consumer_count
            
            if message_count > 0:
                print(f"⚠️ {queue_name}: {message_count} messages, {consumer_count} consumers")
            else:
                print(f"✅ {queue_name}: {message_count} messages, {consumer_count} consumers")
        except Exception as e:
            print(f"❌ {queue_name}: Error - {e}")
    
except Exception as e:
    print(f"❌ Error connecting to RabbitMQ: {e}")
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ตรวจสอบ API status
echo ""
echo "🌐 ตรวจสอบ API Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v curl >/dev/null 2>&1; then
    API_URL="http://localhost:8010"
    
    echo "กำลังตรวจสอบ API health..."
    if curl -s -f "${API_URL}/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ API is healthy${NC}"
        
        echo ""
        echo "กำลังตรวจสอบ task status จาก API..."
        API_RESPONSE=$(curl -s "${API_URL}/transcribe/${TASK_ID}" 2>/dev/null || echo "{}")
        
        if echo "$API_RESPONSE" | grep -q "task_id"; then
            echo "$API_RESPONSE" | python3 -m json.tool | grep -E "(task_id|status|progress|full_text|error_message|created_at|completed_at)" | head -10
        else
            echo -e "${RED}❌ ไม่พบ task ใน API${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ API ไม่สามารถเข้าถึงได้${NC}"
    fi
else
    echo "⚠️ curl ไม่พบ - ข้ามการตรวจสอบ API"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ การตรวจสอบเสร็จสิ้น"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


