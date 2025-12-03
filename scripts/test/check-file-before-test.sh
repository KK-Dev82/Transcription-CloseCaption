#!/bin/bash
# Script สำหรับตรวจสอบไฟล์ก่อนทดสอบ 50 Concurrency
#
# วิธีใช้งาน:
#   bash scripts/test/check-file-before-test.sh <file_path> [api_url]
#
# ตัวอย่าง:
#   bash scripts/test/check-file-before-test.sh uploads/v10-1.mp4 http://80.15.7.37:41462

set -e

FILE_PATH="${1}"
API_URL="${2:-http://80.15.7.37:41462}"

if [ -z "$FILE_PATH" ]; then
    echo "❌ Usage: $0 <file_path> [api_url]"
    echo ""
    echo "Example:"
    echo "  $0 uploads/v10-1.mp4 http://80.15.7.37:41462"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 ตรวจสอบไฟล์ก่อนทดสอบ 50 Concurrency                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "File Path: $FILE_PATH"
echo "API URL: $API_URL"
echo ""

# ตรวจสอบว่า API ทำงานอยู่หรือไม่
echo "1️⃣  ตรวจสอบ API Health..."
HEALTH_RESPONSE=$(curl -s -f "${API_URL}/health" 2>&1 || echo "ERROR")
if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
    echo "✅ API is healthy"
else
    echo "❌ API is not responding"
    echo "   Response: $HEALTH_RESPONSE"
    exit 1
fi
echo ""

# ตรวจสอบไฟล์ผ่าน API (ต้อง SSH เข้า Pod)
echo "2️⃣  ตรวจสอบไฟล์บน Server..."
echo "   (ต้อง SSH เข้า Pod เพื่อตรวจสอบ)"

echo ""
echo "💡 SSH เข้า Pod แล้วรันคำสั่งเหล่านี้:"
echo ""
echo "   ssh pytorch-pod"
echo "   cd /workspace/transcription-service"
echo ""

# สร้างคำสั่งสำหรับตรวจสอบ
CHECK_COMMANDS="
echo '📂 ตรวจสอบไฟล์: $FILE_PATH'
echo ''

# ตรวจสอบ path ต่างๆ ที่เป็นไปได้
POSSIBLE_PATHS=(
    '/workspace/transcription-service/$FILE_PATH'
    '/workspace/transcription-service/uploads/$(basename $FILE_PATH)'
    '/workspace/transcription-service/storage/videos/$(basename $FILE_PATH)'
    '/workspace/transcription-service/storage/uploads/$(basename $FILE_PATH)'
)

FOUND=false
for path in \"\${POSSIBLE_PATHS[@]}\"; do
    if [ -f \"\$path\" ]; then
        echo \"✅ พบไฟล์: \$path\"
        ls -lh \"\$path\"
        FOUND=true
        break
    fi
done

if [ \"\$FOUND\" = false ]; then
    echo \"❌ ไม่พบไฟล์: $FILE_PATH\"
    echo ''
    echo \"🔍 ตรวจสอบไฟล์ใน uploads directory:\"
    ls -lh /workspace/transcription-service/uploads/ | head -10
    echo ''
    echo \"🔍 ตรวจสอบไฟล์ใน storage directory:\"
    ls -lh /workspace/transcription-service/storage/videos/ 2>/dev/null | head -10 || echo '   (directory ไม่มี)'
fi
"

echo "$CHECK_COMMANDS" | sed 's/^/   /'
echo ""

# หรือใช้ SSH โดยตรงถ้าเป็นไปได้
if command -v ssh > /dev/null; then
    SSH_CONFIG=$(ssh -G pytorch-pod 2>/dev/null | grep -E "^hostname|^port|^user" | head -3 || echo "")
    if [ ! -z "$SSH_CONFIG" ]; then
        echo "3️⃣  พยายามตรวจสอบผ่าน SSH..."
        echo ""
        
        # พยายาม SSH และตรวจสอบไฟล์
        ssh pytorch-pod "cd /workspace/transcription-service && \
            if [ -f \"$FILE_PATH\" ]; then
                echo \"✅ พบไฟล์: $FILE_PATH\"
                ls -lh \"$FILE_PATH\"
            elif [ -f \"uploads/$(basename $FILE_PATH)\" ]; then
                echo \"✅ พบไฟล์: uploads/$(basename $FILE_PATH)\"
                ls -lh \"uploads/$(basename $FILE_PATH)\"
            else
                echo \"❌ ไม่พบไฟล์: $FILE_PATH\"
                echo ''
                echo \"🔍 ไฟล์ใน uploads directory:\"
                ls -lh uploads/ 2>/dev/null | head -10 || echo '   (directory ไม่มี)'
                exit 1
            fi" 2>&1 || {
            echo "⚠️  ไม่สามารถ SSH เข้า Pod ได้ หรือไฟล์ไม่พบ"
            echo ""
            echo "💡 ตรวจสอบด้วยตนเอง:"
            echo "   ssh pytorch-pod"
            echo "   cd /workspace/transcription-service"
            echo "   ls -lh $FILE_PATH"
        }
    else
        echo "3️⃣  ไม่พบ SSH config สำหรับ pytorch-pod"
        echo "   ตรวจสอบไฟล์ด้วยตนเองบน Pod"
    fi
else
    echo "3️⃣  SSH command ไม่พร้อมใช้งาน"
    echo "   ตรวจสอบไฟล์ด้วยตนเองบน Pod"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ ตรวจสอบเสร็จสิ้น"
echo ""
echo "💡 ถ้าไฟล์ไม่พบ:"
echo "   1. Upload ไฟล์ไปยัง Pod: scp file.mp4 pytorch-pod:/workspace/transcription-service/uploads/"
echo "   2. ใช้ file_url แทน file_path"
echo "   3. ตรวจสอบ path ในสคริปต์ว่าถูกต้อง"
echo ""

