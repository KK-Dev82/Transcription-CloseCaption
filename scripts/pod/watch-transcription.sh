#!/bin/bash
# Script สำหรับ Watch Transcription Progress แบบ Real-time
#
# วิธีใช้งาน:
#   bash scripts/pod/watch-transcription.sh [task-id]

set -e

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

TASK_ID="${1}"

if [ -z "$TASK_ID" ]; then
    print_warning "⚠️  Task ID not provided"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/watch-transcription.sh <task-id>"
    echo ""
    echo "Example:"
    echo "  bash scripts/pod/watch-transcription.sh b4544c2d-82b3-4a41-a340-18834e345a76"
    exit 1
fi

API_URL="${2:-http://localhost:8001}"

echo "👀 Watching Transcription Progress"
echo "📅 $(date)"
echo ""
print_status "Task ID: $TASK_ID"
print_status "API URL: $API_URL"
echo ""
print_status "💡 Press Ctrl+C to stop"
echo ""

LAST_PROGRESS=-1
LAST_STATUS=""

while true; do
    # Get task status
    RESPONSE=$(curl -s "$API_URL/transcribe/$TASK_ID" 2>/dev/null || echo "")
    
    if [ -z "$RESPONSE" ]; then
        RESPONSE=$(curl -s "$API_URL/api/transcription/$TASK_ID" 2>/dev/null || echo "")
    fi
    
    if [ -n "$RESPONSE" ]; then
        STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        PROGRESS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('progress', 0))" 2>/dev/null || echo "0")
        
        # Only print if changed
        if [ "$PROGRESS" != "$LAST_PROGRESS" ] || [ "$STATUS" != "$LAST_STATUS" ]; then
            TIMESTAMP=$(date '+%H:%M:%S')
            
            # Progress bar
            PROGRESS_BAR=""
            PROGRESS_INT=${PROGRESS%.*}
            for i in {1..20}; do
                if [ $i -le $((PROGRESS_INT / 5)) ]; then
                    PROGRESS_BAR="${PROGRESS_BAR}█"
                else
                    PROGRESS_BAR="${PROGRESS_BAR}░"
                fi
            done
            
            case "$STATUS" in
                completed|success)
                    print_success "[$TIMESTAMP] ✅ Status: $STATUS | Progress: [$PROGRESS_BAR] $PROGRESS%"
                    echo ""
                    print_success "🎉 Transcription completed!"
                    break
                    ;;
                failed|error)
                    ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('error_message', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
                    print_warning "[$TIMESTAMP] ❌ Status: $STATUS | Error: $ERROR_MSG"
                    break
                    ;;
                processing|processing_*)
                    print_status "[$TIMESTAMP] ⏳ Status: $STATUS | Progress: [$PROGRESS_BAR] $PROGRESS%"
                    ;;
                *)
                    print_status "[$TIMESTAMP] 📋 Status: $STATUS | Progress: [$PROGRESS_BAR] $PROGRESS%"
                    ;;
            esac
            
            LAST_PROGRESS=$PROGRESS
            LAST_STATUS=$STATUS
        fi
    fi
    
    sleep 3
done

echo ""

