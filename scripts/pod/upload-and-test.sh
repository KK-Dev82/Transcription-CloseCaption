#!/bin/bash
# Script สำหรับอัปโหลด Video และทดสอบ Transcription จาก Local Machine
#
# วิธีใช้งาน:
# bash scripts/pod/upload-and-test.sh <video-file> <pod-ip> [pod-port] [model-size]
#
# ตัวอย่าง:
# bash scripts/pod/upload-and-test.sh /path/to/video.mp4 205.196.17.108 8001 medium

set -e

VIDEO_FILE="${1}"
POD_IP="${2}"
POD_PORT="${3:-8001}"
MODEL_SIZE="${4:-medium}"

if [ -z "$VIDEO_FILE" ] || [ -z "$POD_IP" ]; then
    echo "❌ Error: Video file and Pod IP are required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/upload-and-test.sh <video-file> <pod-ip> [pod-port] [model-size]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/upload-and-test.sh /path/to/video.mp4 205.196.17.108 8001 medium"
    echo "  bash scripts/pod/upload-and-test.sh /path/to/video.mp4 205.196.17.108 medium"
    echo ""
    echo "Model sizes:"
    echo "  - base: Fastest, lowest accuracy"
    echo "  - small: Balanced"
    echo "  - medium: Better accuracy (แนะนำสำหรับ GPU 4080)"
    echo "  - large-v3: Best accuracy, slowest"
    exit 1
fi

# Check if file exists
if [ ! -f "$VIDEO_FILE" ]; then
    echo "❌ Error: Video file not found: $VIDEO_FILE"
    exit 1
fi

API_URL="http://${POD_IP}:${POD_PORT}"

echo "🧪 Testing Transcription on RunPod..."
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Video File: $VIDEO_FILE"
echo "   Pod IP: $POD_IP"
echo "   Pod Port: $POD_PORT"
echo "   API URL: $API_URL"
echo "   Model Size: $MODEL_SIZE"
echo ""

# Check API health
echo "🏥 Checking API health..."
if ! curl -f "$API_URL/health" > /dev/null 2>&1; then
    echo "❌ API is not responding at $API_URL"
    echo "💡 Please check:"
    echo "   1. Pod is running"
    echo "   2. Services are started: bash scripts/pod/start-services-direct.sh"
    echo "   3. Port $POD_PORT is exposed in RunPod"
    exit 1
fi
echo "✅ API is healthy"
echo ""

# Get file size
FILE_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
echo "📊 File Information:"
echo "   Size: $FILE_SIZE"
echo ""

# Get video duration (if ffprobe is available)
if command -v ffprobe &> /dev/null; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null | cut -d. -f1)
    if [ -n "$DURATION" ]; then
        MINUTES=$((DURATION / 60))
        SECONDS=$((DURATION % 60))
        echo "   Duration: ${MINUTES}m ${SECONDS}s"
    fi
fi
echo ""

# Upload and transcribe
echo "🚀 Uploading video and starting transcription..."
echo "⏳ This may take a while depending on video length and model size..."
echo ""

START_TIME=$(date +%s)

# Step 1: Upload file
echo "📤 Step 1: Uploading video file..."
UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/api/upload/" \
    -F "file=@$VIDEO_FILE")

# Extract file_path from upload response
FILE_PATH=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_path // empty' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
    echo "❌ Upload failed or could not extract file_path:"
    echo "$UPLOAD_RESPONSE" | jq . 2>/dev/null || echo "$UPLOAD_RESPONSE"
    exit 1
fi

echo "✅ File uploaded: $FILE_PATH"
echo ""

# Step 2: Start transcription
echo "🚀 Step 2: Starting transcription..."
RESPONSE=$(curl -s -X POST "$API_URL/api/transcription/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"$FILE_PATH\",
        \"language\": \"th\",
        \"model_size\": \"$MODEL_SIZE\"
    }")

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Check response
if echo "$RESPONSE" | grep -q "error\|Error\|ERROR"; then
    echo "❌ Transcription failed:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Extract task_id from response
TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id // .id // empty' 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    echo "⚠️  Could not extract task_id from response:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    echo ""
    echo "💡 Response received in ${ELAPSED}s"
    exit 1
fi

echo "✅ Transcription job started!"
echo "   Task ID: $TASK_ID"
echo "   Upload time: ${ELAPSED}s"
echo ""

# Poll for result
echo "⏳ Waiting for transcription to complete..."
echo "   (This may take several minutes depending on video length)"
echo ""

MAX_WAIT=1800  # 30 minutes
WAIT_INTERVAL=5
ELAPSED_WAIT=0

while [ $ELAPSED_WAIT -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
    
    if [ -z "$STATUS_RESPONSE" ]; then
        echo "⚠️  Could not get status. Retrying..."
        sleep $WAIT_INTERVAL
        ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
        continue
    fi
    
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // .state // "unknown"' 2>/dev/null || echo "unknown")
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress // 0' 2>/dev/null || echo "0")
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "success" ]; then
        echo ""
        echo "✅ Transcription completed!"
        echo ""
        
        # Get result
        echo "📥 Fetching transcription result..."
        RESULT_RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
        
        if [ -n "$RESULT_RESPONSE" ]; then
            FULL_TEXT=$(echo "$RESULT_RESPONSE" | jq -r '.result.full_text // .full_text // "N/A"' 2>/dev/null || echo "N/A")
            CHUNKS=$(echo "$RESULT_RESPONSE" | jq -r '.result.chunks // .chunks // []' 2>/dev/null || echo "[]")
            
            echo ""
            echo "📝 Transcription Result:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "$FULL_TEXT"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            
            # Save to file
            OUTPUT_FILE="/tmp/transcription-result-$(date +%Y%m%d-%H%M%S).txt"
            echo "$FULL_TEXT" > "$OUTPUT_FILE"
            echo "💾 Result saved to: $OUTPUT_FILE"
            echo ""
            
            # Show statistics
            WORD_COUNT=$(echo "$FULL_TEXT" | wc -w)
            CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c)
            echo "📊 Statistics:"
            echo "   Words: $WORD_COUNT"
            echo "   Characters: $CHAR_COUNT"
            echo ""
        else
            echo "⚠️  Could not fetch result"
        fi
        
        TOTAL_TIME=$((ELAPSED_WAIT + ELAPSED))
        MINUTES=$((TOTAL_TIME / 60))
        SECONDS=$((TOTAL_TIME % 60))
        echo "⏱️  Total time: ${MINUTES}m ${SECONDS}s"
        echo ""
        
        exit 0
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
        echo ""
        echo "❌ Transcription failed!"
        echo "   Status: $STATUS"
        echo "   Response: $STATUS_RESPONSE"
        exit 1
    else
        # Show progress
        PROGRESS_BAR=""
        PROGRESS_INT=${PROGRESS%.*}
        for i in {1..20}; do
            if [ $i -le $((PROGRESS_INT / 5)) ]; then
                PROGRESS_BAR="${PROGRESS_BAR}█"
            else
                PROGRESS_BAR="${PROGRESS_BAR}░"
            fi
        done
        
        MINUTES=$((ELAPSED_WAIT / 60))
        SECONDS=$((ELAPSED_WAIT % 60))
        printf "\r   Status: %-10s Progress: [%s] %3d%% (%dm %ds)" "$STATUS" "$PROGRESS_BAR" "$PROGRESS_INT" "$MINUTES" "$SECONDS"
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
done

echo ""
echo "⏱️  Timeout: Transcription took longer than $((MAX_WAIT / 60)) minutes"
echo "💡 Check status manually:"
echo "   curl $API_URL/api/transcription/$TASK_ID"
echo ""

