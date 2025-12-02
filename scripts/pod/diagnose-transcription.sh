#!/bin/bash
# Script สำหรับตรวจสอบปัญหา Transcription

TASK_ID="${1}"
API_URL="${API_URL:-http://localhost:8010}"

if [ -z "$TASK_ID" ]; then
    echo "❌ Usage: $0 <task_id>"
    echo ""
    echo "Example:"
    echo "  $0 6cbcc34f-cd8e-4f9b-b3fb-264c41ab8760"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 Transcription Diagnostic Tool                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Task ID: $TASK_ID"
echo ""

cd /workspace/transcription-service 2>/dev/null || cd "$(dirname "$0")/../.."

# 1. ตรวจสอบ Task Status จาก API
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 1️⃣  Task Status (API)                                       │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

API_RESPONSE=$(curl -s "${API_URL}/transcribe/${TASK_ID}" 2>/dev/null)
if [ -z "$API_RESPONSE" ] || echo "$API_RESPONSE" | grep -q "404\|Not Found\|ไม่พบ"; then
    echo "❌ Task not found in API"
    exit 1
fi

echo "$API_RESPONSE" | python3 -c "
import json
import sys
try:
    data = json.load(sys.stdin)
    print(f\"Status: {data.get('status', 'N/A')}\")
    print(f\"Progress: {data.get('progress', 0)}%\")
    print(f\"File Name: {data.get('file_name', 'N/A')}\")
    print(f\"File URL: {data.get('file_url', 'N/A')}\")
    print(f\"Total Duration: {data.get('total_duration', 'N/A')}\")
    print(f\"Full Text Length: {len(data.get('full_text', '') or '')} chars\")
    print(f\"Chunks Count: {len(data.get('chunks', []) or [])}\")
    print(f\"Error Message: {data.get('error_message', 'None')}\")
    print(f\"Language: {data.get('language', 'N/A')}\")
    print(f\"Created At: {data.get('created_at', 'N/A')}\")
    print(f\"Completed At: {data.get('completed_at', 'N/A')}\")
    
    # Flags
    has_text = bool(data.get('full_text', ''))
    has_chunks = bool(data.get('chunks'))
    is_completed = data.get('status') == 'completed'
    
    print(f\"\n⚠️  Issues:\")
    if is_completed and not has_text and not has_chunks:
        print(f\"  ❌ Completed but NO TEXT or CHUNKS (empty transcription)\")
    if not data.get('total_duration'):
        print(f\"  ⚠️  Total Duration is NULL (file may be invalid)\")
except Exception as e:
    print(f\"Error parsing JSON: {e}\")
" 2>/dev/null

echo ""

# 2. ตรวจสอบ Metadata ใน Storage
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 2️⃣  Metadata (Storage)                                      │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

METADATA_FILE="storage/transcriptions/${TASK_ID}/metadata.json"
if [ -f "$METADATA_FILE" ]; then
    echo "📄 Metadata file: $METADATA_FILE"
    cat "$METADATA_FILE" | python3 -m json.tool | grep -E "(status|progress|full_text|chunks|error|file_name|total_duration|file_path|file_url)" | head -15
else
    echo "❌ Metadata file not found: $METADATA_FILE"
fi

echo ""

# 3. ตรวจสอบไฟล์ใน Storage
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 3️⃣  Files in Storage                                        │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

TASK_DIR="storage/transcriptions/${TASK_ID}"
if [ -d "$TASK_DIR" ]; then
    echo "📁 Task directory: $TASK_DIR"
    ls -lah "$TASK_DIR/"
    echo ""
    
    # ตรวจสอบว่ามี full_text.txt หรือไม่
    if [ -f "$TASK_DIR/full_text.txt" ]; then
        TEXT_SIZE=$(stat -f%z "$TASK_DIR/full_text.txt" 2>/dev/null || stat -c%s "$TASK_DIR/full_text.txt" 2>/dev/null || echo "0")
        echo "✅ full_text.txt exists (${TEXT_SIZE} bytes)"
        if [ "$TEXT_SIZE" -gt 0 ]; then
            echo "📝 Preview (first 200 chars):"
            head -c 200 "$TASK_DIR/full_text.txt"
            echo ""
        else
            echo "⚠️  File is empty"
        fi
    else
        echo "❌ full_text.txt not found"
    fi
else
    echo "❌ Task directory not found: $TASK_DIR"
fi

echo ""

# 4. ตรวจสอบ Logs
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 4️⃣  Recent Logs (Task ID)                                   │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

# ตรวจสอบ logs จาก service
LOG_DIRS=("logs" "/var/log" "/tmp")
FOUND_LOGS=false

for log_dir in "${LOG_DIRS[@]}"; do
    if [ -d "$log_dir" ]; then
        find "$log_dir" -name "*.log" -type f -mtime -1 2>/dev/null | while read logfile; do
            if grep -q "$TASK_ID" "$logfile" 2>/dev/null; then
                FOUND_LOGS=true
                echo "📋 Found in: $logfile"
                echo ""
                grep "$TASK_ID" "$logfile" 2>/dev/null | tail -10 | head -10
                echo ""
            fi
        done
    fi
done

if [ "$FOUND_LOGS" = false ]; then
    echo "⚠️  No logs found in standard locations"
    echo "💡 Check service logs manually or check if logging is enabled"
fi

echo ""

# 5. ตรวจสอบไฟล์ต้นฉบับ (ถ้ามี file_url)
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 5️⃣  Source File Check                                       │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

FILE_URL=$(echo "$API_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d.get('file_url', ''))" 2>/dev/null)
FILE_NAME=$(echo "$API_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print(d.get('file_name', ''))" 2>/dev/null)

if [ -n "$FILE_URL" ] && [ "$FILE_URL" != "None" ] && [ "$FILE_URL" != "null" ]; then
    echo "📂 File URL: $FILE_URL"
    echo "📄 File Name: $FILE_NAME"
    echo ""
    echo "💡 To check if file has audio:"
    echo "   curl -I \"$FILE_URL\"  # Check if file is accessible"
    echo ""
    echo "💡 To download and check audio (requires ffprobe):"
    echo "   curl -o /tmp/check_audio.${FILE_NAME##*.} \"$FILE_URL\""
    echo "   ffprobe -v error -show_entries stream=codec_type,codec_name,duration \"\$_\";"
else
    echo "⚠️  No file_url found in task metadata"
fi

echo ""

# 6. สรุปและคำแนะนำ
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│ 📊 Diagnostic Summary                                        │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

IS_COMPLETED=$(echo "$API_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print('yes' if d.get('status') == 'completed' else 'no')" 2>/dev/null)
HAS_TEXT=$(echo "$API_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print('yes' if d.get('full_text') else 'no')" 2>/dev/null)
HAS_CHUNKS=$(echo "$API_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print('yes' if d.get('chunks') else 'no')" 2>/dev/null)

echo "Status: $IS_COMPLETED"
echo "Has Text: $HAS_TEXT"
echo "Has Chunks: $HAS_CHUNKS"
echo ""

if [ "$IS_COMPLETED" = "yes" ] && [ "$HAS_TEXT" = "no" ] && [ "$HAS_CHUNKS" = "no" ]; then
    echo "🔴 PROBLEM DETECTED:"
    echo "   • Transcription completed successfully"
    echo "   • But NO text or chunks found"
    echo ""
    echo "🔍 Possible Causes:"
    echo "   1. ❌ Source file has NO AUDIO TRACK (silent file)"
    echo "   2. ❌ Audio file is corrupted or invalid"
    echo "   3. ❌ Faster-Whisper returned empty result (no speech detected)"
    echo "   4. ❌ Audio extraction failed silently"
    echo ""
    echo "💡 Next Steps:"
    echo "   1. Check source file: curl -I \"$FILE_URL\""
    echo "   2. Download and verify audio: ffprobe file.ext"
    echo "   3. Check service logs for errors"
    echo "   4. Try re-transcribing with a different file"
fi

echo ""
echo "✅ Diagnostic complete!"
echo ""

