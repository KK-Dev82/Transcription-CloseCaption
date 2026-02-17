#!/bin/bash
# ทดสอบ End-to-End: Transcription + Diarization (/newSpeaker)
# ต้อง: API รันอยู่, RQ Worker รันอยู่, Redis พร้อม, ไฟล์เสียงมีอยู่

set -e
API_BASE="${API_BASE:-http://localhost:8010}"
WAV_PATH="${WAV_PATH}"
TIMEOUT="${TIMEOUT:-600}"  # รอสูงสุด 10 นาที

if [ -z "$WAV_PATH" ]; then
  echo "❌ ตั้ง WAV_PATH ก่อน"
  echo "   ตัวอย่าง: WAV_PATH=/path/to/audio.wav ./scripts/test_diarization_e2e.sh"
  echo ""
  echo "หรือสร้างไฟล์ทดสอบก่อน:"
  echo "   python3 scripts/test_diarization.py --create-test"
  echo "   WAV_PATH=uploads/test_diarization_silence.wav ./scripts/test_diarization_e2e.sh"
  exit 1
fi

if [ ! -f "$WAV_PATH" ]; then
  echo "❌ ไม่พบไฟล์: $WAV_PATH"
  exit 1
fi

# ใช้ path แบบ absolute ถ้าเป็น relative
if [[ "$WAV_PATH" != /* ]]; then
  PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  WAV_PATH="$PROJECT_ROOT/$WAV_PATH"
fi

echo "📂 ไฟล์: $WAV_PATH"
echo "🌐 API: $API_BASE"
echo "🔄 enable_diarization: true"
echo ""

# 1) เริ่ม transcription พร้อม diarization
echo "1️⃣ ส่ง request ไป POST /api/transcribe-enhanced/start (enable_diarization: true)..."
RESP=$(curl -s -X POST "$API_BASE/api/transcribe-enhanced/start" \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"$WAV_PATH\",\"language\":\"th\",\"enable_diarization\":true}")

TASK_ID=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('task_id',''))" 2>/dev/null)
if [ -z "$TASK_ID" ]; then
  echo "❌ ไม่ได้ task_id จาก API:"
  echo "$RESP" | head -20
  exit 1
fi
echo "   task_id: $TASK_ID"
echo ""

# 2) Poll สถานะ (ใช้ /api/v2/tasks/{id} หรือ /transcribe-enhanced/status)
echo "2️⃣ รอให้งานเสร็จ (poll ทุก 5 วินาที, timeout ${TIMEOUT}s)..."
START=$(date +%s)
while true; do
  ELAPSED=$(($(date +%s) - START))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "❌ Timeout หลัง $TIMEOUT วินาที"
    exit 1
  fi
  STATUS_RESP=$(curl -s "$API_BASE/api/v2/tasks/$TASK_ID?format=full" 2>/dev/null || curl -s "$API_BASE/api/transcribe-enhanced/status/$TASK_ID" 2>/dev/null || echo "{}")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','') or d.get('data',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")
  PROGRESS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0) or d.get('data',{}).get('progress',0))" 2>/dev/null || echo "0")
  echo "   [${ELAPSED}s] status=$STATUS progress=$PROGRESS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "done" ]; then
    echo "✅ งานเสร็จแล้ว"
    break
  fi
  if [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
    echo "❌ งานล้มเหลว:"
    echo "$STATUS_RESP" | python3 -m json.tool 2>/dev/null | head -30
    exit 1
  fi
  sleep 5
done
echo ""

# 3) ดึงผลลัพธ์และตรวจสอบ /newSpeaker
echo "3️⃣ ตรวจสอบผลลัพธ์..."
TEXT_RESP=$(curl -s "$API_BASE/api/v2/tasks/$TASK_ID?format=full" 2>/dev/null || curl -s "$API_BASE/api/transcribe-enhanced/status/$TASK_ID" 2>/dev/null || echo "{}")
FULL_TEXT=$(echo "$TEXT_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
t = d.get('full_text') or d.get('text') or d.get('data', {}).get('full_text') or d.get('data', {}).get('text') or ''
print(t)
" 2>/dev/null)

echo "=============================================="
echo "📝 ผลลัพธ์ (ตัด 1500 ตัวอักษรแรกลำ):"
echo "=============================================="
echo "${FULL_TEXT:0:1500}$([ ${#FULL_TEXT} -gt 1500 ] && echo '...')"
echo ""

if echo "$FULL_TEXT" | grep -q '/newSpeaker'; then
  COUNT=$(echo "$FULL_TEXT" | grep -o '/newSpeaker' | wc -l)
  echo "✅ พบ /newSpeaker ในผลลัพธ์ ($COUNT ครั้ง) - Diarization ทำงาน"
else
  echo "⚠️ ไม่พบ /newSpeaker ในผลลัพธ์"
  echo "   (ถ้าไฟล์เป็นความเงียบหรือผู้พูดคนเดียว อาจไม่มี)"
fi
echo ""
echo "✅ ทดสอบ End-to-End เสร็จสิ้น"
