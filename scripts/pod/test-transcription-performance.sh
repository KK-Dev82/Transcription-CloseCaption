#!/bin/bash
# Script สำหรับทดสอบ Transcription Performance และวัดเวลา
#
# วิธีใช้งาน:
# bash scripts/pod/test-transcription-performance.sh <video-file> [model-size] [api-url]
#
# ตัวอย่าง:
# bash scripts/pod/test-transcription-performance.sh /path/to/video.mp4 medium http://localhost:8001

set -e

VIDEO_FILE="${1}"
MODEL_SIZE="${2:-medium}"
API_URL="${3:-http://localhost:8001}"

if [ -z "$VIDEO_FILE" ]; then
    echo "❌ Error: Video file path is required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/test-transcription-performance.sh <video-file> [model-size] [api-url]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/test-transcription-performance.sh /path/to/video.mp4 medium"
    echo "  bash scripts/pod/test-transcription-performance.sh /path/to/video.mp4 medium http://localhost:8001"
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

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_perf() {
    echo -e "${CYAN}[PERF]${NC} $1"
}

echo "🧪 Testing Transcription Performance"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Video File: $VIDEO_FILE"
echo "   Model Size: $MODEL_SIZE"
echo "   API URL: $API_URL"
echo ""

# Get file information
FILE_SIZE=$(du -h "$VIDEO_FILE" | cut -f1)
FILE_SIZE_BYTES=$(stat -c%s "$VIDEO_FILE" 2>/dev/null || stat -f%z "$VIDEO_FILE" 2>/dev/null || echo "0")

print_perf "📊 File Information:"
echo "   Size: $FILE_SIZE ($FILE_SIZE_BYTES bytes)"
echo ""

# Get video duration (if ffprobe is available)
VIDEO_DURATION=0
if command -v ffprobe &> /dev/null; then
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null || echo "0")
    if [ -n "$DURATION" ] && [ "$DURATION" != "0" ]; then
        VIDEO_DURATION=${DURATION%.*}
        MINUTES=$((VIDEO_DURATION / 60))
        SECONDS=$((VIDEO_DURATION % 60))
        print_perf "   Duration: ${MINUTES}m ${SECONDS}s ($VIDEO_DURATION seconds)"
    fi
fi
echo ""

# Check API health
print_status "Checking API health..."
if ! curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
    print_error "❌ API is not responding at $API_URL"
    exit 1
fi
print_success "✅ API is healthy"
echo ""

# Check GPU (if available)
if command -v nvidia-smi &> /dev/null; then
    print_status "GPU Information (Before):"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo "⚠️  nvidia-smi not available"
    echo ""
fi

# Step 1: Upload file
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_perf "Step 1: Uploading Video File"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

UPLOAD_START=$(date +%s)

UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/api/upload/" \
    -F "file=@$VIDEO_FILE")

UPLOAD_END=$(date +%s)
UPLOAD_TIME=$((UPLOAD_END - UPLOAD_START))

# Extract file_path from upload response
FILE_PATH=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_path // empty' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
    print_error "❌ Upload failed or could not extract file_path:"
    echo "$UPLOAD_RESPONSE" | jq . 2>/dev/null || echo "$UPLOAD_RESPONSE"
    exit 1
fi

print_success "✅ File uploaded: $FILE_PATH"
print_perf "⏱️  Upload time: ${UPLOAD_TIME}s"
echo ""

# Step 2: Start transcription
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_perf "Step 2: Starting Transcription"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TRANSCRIBE_START=$(date +%s)

RESPONSE=$(curl -s -X POST "$API_URL/api/transcription/" \
    -H "Content-Type: application/json" \
    -d "{
        \"file_path\": \"$FILE_PATH\",
        \"language\": \"th\",
        \"model_size\": \"$MODEL_SIZE\"
    }")

# Extract task_id from response
TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id // .id // empty' 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
    print_error "❌ Could not extract task_id from response:"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

print_success "✅ Transcription job started!"
print_perf "   Task ID: $TASK_ID"
echo ""

# Monitor GPU during transcription
if command -v nvidia-smi &> /dev/null; then
    (
        while true; do
            sleep 5
            if ! pgrep -f "python.*video_worker\|python.*whisper" > /dev/null; then
                break
            fi
            nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1
        done
    ) > /tmp/gpu-monitor.log 2>&1 &
    GPU_MONITOR_PID=$!
fi

# Poll for result
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_perf "Step 3: Monitoring Transcription Progress"
print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

MAX_WAIT=3600  # 60 minutes
WAIT_INTERVAL=5
ELAPSED_WAIT=0
LAST_PROGRESS=0

while [ $ELAPSED_WAIT -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
    
    if [ -z "$STATUS_RESPONSE" ]; then
        sleep $WAIT_INTERVAL
        ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
        continue
    fi
    
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // .state // "unknown"' 2>/dev/null || echo "unknown")
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress // 0' 2>/dev/null || echo "0")
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "success" ]; then
        TRANSCRIBE_END=$(date +%s)
        TRANSCRIBE_TIME=$((TRANSCRIBE_END - TRANSCRIBE_START))
        TOTAL_TIME=$((TRANSCRIBE_END - UPLOAD_START))
        
        echo ""
        print_success "✅ Transcription completed!"
        echo ""
        
        # Stop GPU monitor
        if [ -n "$GPU_MONITOR_PID" ]; then
            kill $GPU_MONITOR_PID 2>/dev/null || true
        fi
        
        # Get result
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_perf "Step 4: Fetching Transcription Result"
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        RESULT_RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
        
        if [ -n "$RESULT_RESPONSE" ]; then
            FULL_TEXT=$(echo "$RESULT_RESPONSE" | jq -r '.result.full_text // .full_text // "N/A"' 2>/dev/null || echo "N/A")
            CHUNKS=$(echo "$RESULT_RESPONSE" | jq -r '.result.chunks // .chunks // []' 2>/dev/null || echo "[]")
            CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
            
            echo ""
            print_perf "📝 Transcription Result:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "$FULL_TEXT" | head -c 500
            if [ ${#FULL_TEXT} -gt 500 ]; then
                echo "..."
                echo "(แสดง 500 ตัวอักษรแรก - ดูผลลัพธ์เต็มในไฟล์)"
            fi
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            
            # Save to file
            OUTPUT_FILE="/tmp/transcription-result-$(date +%Y%m%d-%H%M%S).txt"
            echo "$FULL_TEXT" > "$OUTPUT_FILE"
            print_success "💾 Result saved to: $OUTPUT_FILE"
            echo ""
            
            # Statistics
            WORD_COUNT=$(echo "$FULL_TEXT" | wc -w 2>/dev/null || echo "0")
            CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c 2>/dev/null || echo "0")
            
            print_perf "📊 Statistics:"
            echo "   Words: $WORD_COUNT"
            echo "   Characters: $CHAR_COUNT"
            echo "   Chunks: $CHUNK_COUNT"
            echo ""
        fi
        
        # Performance Summary
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_perf "Performance Summary"
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        print_perf "⏱️  Timing:"
        echo "   Upload time: ${UPLOAD_TIME}s"
        echo "   Transcription time: ${TRANSCRIBE_TIME}s"
        echo "   Total time: ${TOTAL_TIME}s"
        echo ""
        
        if [ $VIDEO_DURATION -gt 0 ]; then
            # Calculate ratio using awk (more portable than bc)
            RATIO=$(awk "BEGIN {printf \"%.2f\", $TRANSCRIBE_TIME / $VIDEO_DURATION}" 2>/dev/null || echo "N/A")
            SPEEDUP=$(awk "BEGIN {printf \"%.2f\", $VIDEO_DURATION / $TRANSCRIBE_TIME}" 2>/dev/null || echo "N/A")
            
            print_perf "📈 Performance Metrics:"
            echo "   Video duration: ${VIDEO_DURATION}s"
            echo "   Transcription time: ${TRANSCRIBE_TIME}s"
            echo "   Ratio (transcribe/video): ${RATIO}x"
            echo "   Speedup (video/transcribe): ${SPEEDUP}x"
            echo ""
            
            # Performance rating
            if [ "$RATIO" != "N/A" ]; then
                RATIO_NUM=$(echo "$RATIO" | cut -d. -f1)
                if [ -n "$RATIO_NUM" ] && [ "$RATIO_NUM" -ge 0 ] 2>/dev/null; then
                    if [ "$RATIO_NUM" -le 1 ]; then
                    print_success "✅ Excellent! Transcription is faster than video duration"
                elif [ "$RATIO_NUM" -le 2 ]; then
                    print_success "✅ Good! Transcription is 2x video duration"
                elif [ "$RATIO_NUM" -le 5 ]; then
                    print_warning "⚠️  Acceptable. Transcription is 5x video duration"
                else
                    print_warning "⚠️  Slow. Transcription is more than 5x video duration"
                fi
            fi
        fi
        
        # GPU Usage Summary
        if [ -f "/tmp/gpu-monitor.log" ] && [ -s "/tmp/gpu-monitor.log" ]; then
            echo ""
            print_perf "🎮 GPU Usage (during transcription):"
            echo "   (showing sample)"
            head -5 /tmp/gpu-monitor.log | while read line; do
                echo "   $line"
            done
            echo "   (see full log: cat /tmp/gpu-monitor.log)"
        fi
        
        echo ""
        exit 0
        
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
        echo ""
        print_error "❌ Transcription failed!"
        echo "   Status: $STATUS"
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.error_message // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")
        echo "   Error: $ERROR_MSG"
        exit 1
    else
        # Show progress
        PROGRESS_BAR=""
        PROGRESS_INT=${PROGRESS%.*}
        
        # Update progress bar only if changed
        if [ "$PROGRESS_INT" != "$LAST_PROGRESS" ]; then
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
            LAST_PROGRESS=$PROGRESS_INT
        fi
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED_WAIT=$((ELAPSED_WAIT + WAIT_INTERVAL))
done

echo ""
print_error "⏱️  Timeout: Transcription took longer than $((MAX_WAIT / 60)) minutes"
print_status "💡 Check status manually:"
echo "   curl $API_URL/api/transcription/$TASK_ID"
echo ""

