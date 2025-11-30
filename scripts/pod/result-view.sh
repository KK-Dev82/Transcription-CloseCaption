#!/bin/bash
# Script สำหรับดูผลลัพธ์ Transcription
#
# วิธีใช้งาน:
#   bash scripts/pod/result-view.sh [task-id]     # ดูผลลัพธ์ของ task-id
#   bash scripts/pod/result-view.sh                # แสดง list ให้เลือก

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

TASK_ID="${1}"
API_URL="${API_URL:-http://localhost:8001}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Function to get transcription list
get_transcription_list() {
    # Try /api/history/transcriptions first
    RESPONSE=$(curl -s "$API_URL/api/history/transcriptions?limit=50" 2>/dev/null || echo "")
    
    # Fallback to /transcribe/ or /api/transcription/
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/transcribe/" 2>/dev/null || echo "")
    fi
    
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/api/transcription/" 2>/dev/null || echo "")
    fi
    
    echo "$RESPONSE"
}

# Function to get transcription details
get_transcription_details() {
    local task_id=$1
    
    # Try /api/history/transcriptions/{task_id} first
    RESPONSE=$(curl -s "$API_URL/api/history/transcriptions/$task_id" 2>/dev/null || echo "")
    
    # Fallback to /transcribe/{task_id}
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
    fi
    
    # Fallback to /api/transcription/{task_id}
    if [ -z "$RESPONSE" ] || echo "$RESPONSE" | grep -q "404\|Not Found" 2>/dev/null; then
        RESPONSE=$(curl -s "$API_URL/api/transcription/$task_id" 2>/dev/null || echo "")
    fi
    
    echo "$RESPONSE"
}

# If no task_id provided, show list
if [ -z "$TASK_ID" ]; then
    echo "📋 Transcription Results List"
    echo "📅 $(date)"
    echo ""
    
    print_status "Fetching transcription list..."
    LIST_RESPONSE=$(get_transcription_list)
    
    if [ -z "$LIST_RESPONSE" ]; then
        print_error "❌ Failed to fetch transcription list"
        print_status "💡 Check API: curl $API_URL/health"
        exit 1
    fi
    
    # Parse JSON list
    if command -v jq &> /dev/null; then
        TASK_COUNT=$(echo "$LIST_RESPONSE" | jq 'length' 2>/dev/null || echo "0")
        
        if [ "$TASK_COUNT" -eq 0 ]; then
            print_warning "⚠️  No transcriptions found"
            exit 0
        fi
        
        echo ""
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_header "Available Transcriptions"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Display list with numbers
        INDEX=1
        TASK_IDS=()
        echo "$LIST_RESPONSE" | jq -r '.[] | "\(.task_id // .id // "")|\(.status // "unknown")|\(.file_name // .file_path // "N/A")|\(.created_at // "N/A")"' 2>/dev/null | while IFS='|' read -r task_id status filename created_at; do
            if [ -n "$task_id" ]; then
                TASK_IDS+=("$task_id")
                printf "  %2d. " "$INDEX"
                print_status "Task ID: $task_id"
                echo "      Status: $status"
                echo "      File: $filename"
                echo "      Created: $created_at"
                echo ""
                INDEX=$((INDEX + 1))
            fi
        done
        
        # Store task IDs in a way we can access
        TASK_IDS_ARRAY=($(echo "$LIST_RESPONSE" | jq -r '.[] | .task_id // .id // empty' 2>/dev/null | grep -v '^$'))
        
        if [ ${#TASK_IDS_ARRAY[@]} -eq 0 ]; then
            print_warning "⚠️  No valid task IDs found"
            exit 0
        fi
        
        echo ""
        read -p "Select transcription number (1-${#TASK_IDS_ARRAY[@]}) or enter task ID: " SELECTION
        
        # Check if selection is a number
        if [[ "$SELECTION" =~ ^[0-9]+$ ]]; then
            if [ "$SELECTION" -ge 1 ] && [ "$SELECTION" -le ${#TASK_IDS_ARRAY[@]} ]; then
                TASK_ID="${TASK_IDS_ARRAY[$((SELECTION - 1))]}"
            else
                print_error "❌ Invalid selection"
                exit 1
            fi
        else
            # Assume it's a task ID
            TASK_ID="$SELECTION"
        fi
    else
        print_error "❌ jq not found - cannot parse JSON"
        print_status "💡 Install jq: apt-get install -y jq"
        print_status "💡 Or provide task ID directly: bash scripts/pod/result-view.sh <task-id>"
        exit 1
    fi
fi

# Display transcription details
echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Transcription Result: $TASK_ID"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

print_status "Fetching transcription details..."
DETAILS_RESPONSE=$(get_transcription_details "$TASK_ID")

if [ -z "$DETAILS_RESPONSE" ] || echo "$DETAILS_RESPONSE" | grep -q "404\|Not Found\|ไม่พบ" 2>/dev/null; then
    print_error "❌ Transcription not found: $TASK_ID"
    exit 1
fi

# Check for error in response
if echo "$DETAILS_RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$DETAILS_RESPONSE" | jq -r '.detail' 2>/dev/null)
    print_error "❌ Error: $ERROR_MSG"
    exit 1
fi

# Parse and display details
if command -v jq &> /dev/null; then
    # Basic Info
    STATUS=$(echo "$DETAILS_RESPONSE" | jq -r '.status // .basic_info.status // "unknown"' 2>/dev/null)
    PROGRESS=$(echo "$DETAILS_RESPONSE" | jq -r '.progress // .basic_info.progress // 0' 2>/dev/null)
    FILENAME=$(echo "$DETAILS_RESPONSE" | jq -r '.file_name // .basic_info.filename // .file_path // "N/A"' 2>/dev/null)
    MODEL_SIZE=$(echo "$DETAILS_RESPONSE" | jq -r '.model_size // .basic_info.model_size // "N/A"' 2>/dev/null)
    LANGUAGE=$(echo "$DETAILS_RESPONSE" | jq -r '.language // .basic_info.language // "N/A"' 2>/dev/null)
    
    echo ""
    print_header "📋 Basic Information:"
    echo "   Task ID: $TASK_ID"
    echo "   Status: $STATUS"
    echo "   Progress: ${PROGRESS}%"
    echo "   File: $FILENAME"
    echo "   Model: $MODEL_SIZE"
    echo "   Language: $LANGUAGE"
    echo ""
    
    # Timestamps
    CREATED_AT=$(echo "$DETAILS_RESPONSE" | jq -r '.created_at // .timestamps.created_at // "N/A"' 2>/dev/null)
    COMPLETED_AT=$(echo "$DETAILS_RESPONSE" | jq -r '.completed_at // .timestamps.completed_at // "N/A"' 2>/dev/null)
    
    if [ "$CREATED_AT" != "N/A" ] || [ "$COMPLETED_AT" != "N/A" ]; then
        print_header "⏰ Timestamps:"
        [ "$CREATED_AT" != "N/A" ] && echo "   Created: $CREATED_AT"
        [ "$COMPLETED_AT" != "N/A" ] && echo "   Completed: $COMPLETED_AT"
        echo ""
    fi
    
    # Full Text
    FULL_TEXT=$(echo "$DETAILS_RESPONSE" | jq -r '.result.full_text // .full_text // .results.full_text // ""' 2>/dev/null)
    
    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ]; then
        WORD_COUNT=$(echo "$FULL_TEXT" | wc -w 2>/dev/null || echo "0")
        CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c 2>/dev/null || echo "0")
        
        print_header "📝 Transcription Text:"
        echo "   Words: $WORD_COUNT"
        echo "   Characters: $CHAR_COUNT"
        echo ""
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$FULL_TEXT"
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    else
        print_warning "⚠️  No transcription text available"
        echo ""
    fi
    
    # Chunks
    CHUNKS=$(echo "$DETAILS_RESPONSE" | jq -r '.result.chunks // .chunks // .results.chunks // []' 2>/dev/null)
    CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
    
    if [ "$CHUNK_COUNT" -gt 0 ]; then
        print_header "📦 Chunks: $CHUNK_COUNT chunks"
        echo ""
    fi
    
    # Error Info
    ERROR_MSG=$(echo "$DETAILS_RESPONSE" | jq -r '.error_message // .error_info.error_message // ""' 2>/dev/null)
    if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "null" ]; then
        print_error "❌ Error: $ERROR_MSG"
        echo ""
    fi
    
else
    # Fallback: display raw JSON
    print_warning "⚠️  jq not found - displaying raw JSON"
    echo "$DETAILS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DETAILS_RESPONSE"
fi

echo ""
print_status "💡 To view another transcription:"
echo "   bash scripts/pod/result-view.sh <task-id>"
echo ""

