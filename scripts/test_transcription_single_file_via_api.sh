#!/bin/bash
# ทดสอบ transcription ผ่าน API (Internal Transcribe)
# ใช้เมื่อ Main API รันอยู่แล้ว (localhost:8010 หรือ URL อื่น)
# ไฟล์ WAV เดียวกับที่ใช้ทดสอบ /transcription และ FE-CC

set -e
API_BASE="${API_BASE:-http://localhost:8010}"
WAV_PATH="/workspace/transcription-service/uploads/f89a1ae1-08f0-4e84-bb33-808b331a5c8c_S20260115009049C02.wav"
MODEL="${MODEL:-Vinxscribe/biodatlab-whisper-th-medium-faster}"

if [ ! -f "$WAV_PATH" ]; then
  echo "❌ ไม่พบไฟล์: $WAV_PATH"
  exit 1
fi

echo "📂 ไฟล์: $WAV_PATH"
echo "📦 Model: $MODEL"
echo "🌐 API: $API_BASE/api/internal/transcribe"
echo "🔄 กำลังเรียก API..."
echo ""

RESP=$(curl -s -X POST "$API_BASE/api/internal/transcribe" \
  -H "Content-Type: application/json" \
  -d "{\"audio_path\":\"$WAV_PATH\",\"model_size\":\"$MODEL\",\"language\":\"th\",\"use_thai_processor\":true}")

if echo "$RESP" | grep -q '"success":true'; then
  echo "=============================================="
  echo "📝 ผลลัพธ์ (text):"
  echo "=============================================="
  echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
t = d.get('text', '')[:2000]
print(t + ('...' if len(d.get('text','')) > 2000 else ''))
"
  echo ""
  SEGS=$(echo "$RESP" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('segments',[])))" 2>/dev/null || echo "?")
  echo "📊 จำนวน segments: $SEGS"
  echo "✅ ทดสอบ transcription ผ่าน API สำเร็จ"
else
  echo "❌ API ส่งกลับข้อความผิดพลาด:"
  echo "$RESP" | head -20
  exit 1
fi
