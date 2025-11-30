#!/bin/bash
# Script สำหรับดูผลลัพธ์ Transcription
#
# วิธีใช้งาน:
#   bash scripts/pod/result-view.sh [task-id]              # ดูผลลัพธ์ของ task-id
#   bash scripts/pod/result-view.sh                        # แสดง list ให้เลือก
#   bash scripts/pod/result-view.sh -detail [number]       # แสดงรายละเอียดข้อความที่แปลงได้ทันที (เรียงจากล่าสุด)
#   bash scripts/pod/result-view.sh --detail [number]       # เหมือน -detail

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

# Parse arguments
DETAIL_MODE=false
DETAIL_COUNT=5
TASK_ID=""
API_URL="${API_URL:-http://localhost:8001}"

while [[ $# -gt 0 ]]; do
    case $1 in
        -detail|--detail)
            DETAIL_MODE=true
            if [[ $# -gt 1 ]] && [[ "$2" =~ ^[0-9]+$ ]]; then
                DETAIL_COUNT="$2"
                shift
            fi
            shift
            ;;
        *)
            if [ -z "$TASK_ID" ]; then
                TASK_ID="$1"
            fi
            shift
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Function to check API health
check_api_health() {
    if ! curl -f -s --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
        print_error "❌ API is not responding at $API_URL"
        print_status "💡 Check if services are running: bash scripts/pod/check-pod.sh"
        exit 1
    fi
}

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

# Function to get transcription from storage file directly
get_transcription_from_storage() {
    local task_id=$1
    
    # Try folder structure first: storage/transcriptions/{task_id}/metadata.json
    METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id/metadata.json"
    if [ -f "$METADATA_FILE" ]; then
        # Read and merge with full_text.json if available
        METADATA_DATA=$(cat "$METADATA_FILE" 2>/dev/null || echo "{}")
        FULL_TEXT_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id/full_text.json"
        
        if [ -f "$FULL_TEXT_FILE" ] && command -v jq &> /dev/null; then
            # Merge full_text from full_text.json into metadata
            FULL_TEXT=$(jq -r '.full_text // ""' "$FULL_TEXT_FILE" 2>/dev/null || echo "")
            SEGMENTS=$(jq -r '.segments // []' "$FULL_TEXT_FILE" 2>/dev/null || echo "[]")
            
            if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ]; then
                # Merge using jq
                echo "$METADATA_DATA" | jq --arg full_text "$FULL_TEXT" --argjson segments "$SEGMENTS" \
                    '.full_text = $full_text | .chunks = $segments' 2>/dev/null || echo "$METADATA_DATA"
                return 0
            fi
        fi
        
        echo "$METADATA_DATA"
        return 0
    fi
    
    # Try old structure: storage/transcriptions/{task_id}.json
    OLD_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id.json"
    if [ -f "$OLD_FILE" ]; then
        cat "$OLD_FILE"
        return 0
    fi
    
    return 1
}

# Function to get transcription details
get_transcription_details() {
    local task_id=$1
    
    # Try storage file first (more reliable)
    STORAGE_DATA=$(get_transcription_from_storage "$task_id" 2>/dev/null || echo "")
    if [ -n "$STORAGE_DATA" ]; then
        echo "$STORAGE_DATA"
        return 0
    fi
    
    # Fallback to API
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

# Function to calculate processing time
calculate_processing_time() {
    local created_at="$1"
    local completed_at="$2"
    
    if [ "$created_at" = "N/A" ] || [ "$completed_at" = "N/A" ]; then
        echo "N/A"
        return
    fi
    
    # Try to parse ISO format dates
    if command -v date &> /dev/null; then
        # Convert ISO format to epoch seconds
        # Try GNU date format first (Linux)
        CREATED_EPOCH=$(date -d "$created_at" +%s 2>/dev/null || echo "")
        COMPLETED_EPOCH=$(date -d "$completed_at" +%s 2>/dev/null || echo "")
        
        # Fallback: Try Python if date command fails (works on both Linux and macOS)
        if [ -z "$CREATED_EPOCH" ] || [ -z "$COMPLETED_EPOCH" ]; then
            if command -v python3 &> /dev/null; then
                CREATED_EPOCH=$(python3 -c "from datetime import datetime; print(int(datetime.fromisoformat('${created_at%+*}'.replace('Z', '+00:00')).timestamp()))" 2>/dev/null || echo "")
                COMPLETED_EPOCH=$(python3 -c "from datetime import datetime; print(int(datetime.fromisoformat('${completed_at%+*}'.replace('Z', '+00:00')).timestamp()))" 2>/dev/null || echo "")
            fi
        fi
        
        if [ -n "$CREATED_EPOCH" ] && [ -n "$COMPLETED_EPOCH" ] && [ "$CREATED_EPOCH" != "" ] && [ "$COMPLETED_EPOCH" != "" ]; then
            DIFF=$((COMPLETED_EPOCH - CREATED_EPOCH))
            
            if [ $DIFF -lt 0 ]; then
                echo "N/A"
                return
            fi
            
            if [ $DIFF -lt 60 ]; then
                echo "${DIFF}s"
            elif [ $DIFF -lt 3600 ]; then
                MIN=$((DIFF / 60))
                SEC=$((DIFF % 60))
                echo "${MIN}m ${SEC}s"
            else
                HOUR=$((DIFF / 3600))
                MIN=$(((DIFF % 3600) / 60))
                SEC=$((DIFF % 60))
                echo "${HOUR}h ${MIN}m ${SEC}s"
            fi
            return
        fi
    fi
    
    echo "N/A"
}

# Function to display transcription detail
display_transcription_detail() {
    local task_id=$1
    local show_full_text=${2:-true}
    
    DETAILS_RESPONSE=$(get_transcription_details "$task_id" 2>/dev/null || echo "")
    
    if [ -z "$DETAILS_RESPONSE" ] || echo "$DETAILS_RESPONSE" | grep -q "404\|Not Found\|ไม่พบ" 2>/dev/null; then
        return 1
    fi
    
    if command -v jq &> /dev/null; then
        STATUS=$(echo "$DETAILS_RESPONSE" | jq -r '.status // .basic_info.status // "unknown"' 2>/dev/null)
        PROGRESS=$(echo "$DETAILS_RESPONSE" | jq -r '.progress // .basic_info.progress // 0' 2>/dev/null)
        FILENAME=$(echo "$DETAILS_RESPONSE" | jq -r '.file_name // .filename // .basic_info.filename // .file_path // "N/A"' 2>/dev/null)
        CREATED_AT=$(echo "$DETAILS_RESPONSE" | jq -r '.created_at // .timestamps.created_at // "N/A"' 2>/dev/null)
        COMPLETED_AT=$(echo "$DETAILS_RESPONSE" | jq -r '.completed_at // .timestamps.completed_at // "N/A"' 2>/dev/null)
        
        # Calculate processing time
        PROCESSING_TIME=$(calculate_processing_time "$CREATED_AT" "$COMPLETED_AT")
        
        # Status color
        if [ "$STATUS" = "completed" ]; then
            STATUS_COLOR="${GREEN}"
        elif [ "$STATUS" = "processing" ] || [ "$STATUS" = "pending" ]; then
            STATUS_COLOR="${YELLOW}"
        elif [ "$STATUS" = "failed" ]; then
            STATUS_COLOR="${RED}"
        elif [ "$STATUS" = "cancelled" ]; then
            STATUS_COLOR="${CYAN}"
        else
            STATUS_COLOR="${NC}"
        fi
        
        echo -e "  ${STATUS_COLOR}${STATUS}${NC} | ${PROGRESS}% | $task_id"
        echo "      File: $FILENAME"
        if [ "$PROCESSING_TIME" != "N/A" ] && [ "$STATUS" = "completed" ]; then
            echo "      Processing Time: $PROCESSING_TIME"
        fi
        echo "      Created: $CREATED_AT"
        if [ "$COMPLETED_AT" != "N/A" ]; then
            echo "      Completed: $COMPLETED_AT"
        fi
        
        # Show full text if requested and available
        if [ "$show_full_text" = "true" ] && [ "$STATUS" = "completed" ]; then
            FULL_TEXT=$(echo "$DETAILS_RESPONSE" | jq -r '.result.full_text // .full_text // .results.full_text // ""' 2>/dev/null)
            
            # Try reading from storage file if not in API response
            if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
                FULL_TEXT_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id/full_text.json"
                if [ -f "$FULL_TEXT_FILE" ]; then
                    FULL_TEXT=$(jq -r '.full_text // ""' "$FULL_TEXT_FILE" 2>/dev/null || echo "")
                fi
                
                if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ]; then
                    METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$task_id/metadata.json"
                    if [ -f "$METADATA_FILE" ]; then
                        FULL_TEXT=$(jq -r '.full_text // ""' "$METADATA_FILE" 2>/dev/null || echo "")
                        
                        # If still empty, try to build from chunks
                        if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
                            CHUNKS=$(jq -r '.chunks // []' "$METADATA_FILE" 2>/dev/null || echo "[]")
                            if [ -n "$CHUNKS" ] && [ "$CHUNKS" != "[]" ] && [ "$CHUNKS" != "null" ]; then
                                CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
                                if [ "$CHUNK_COUNT" -gt 0 ]; then
                                    FULL_TEXT=$(echo "$CHUNKS" | jq -r '[.[] | .text // ""] | join(" ")' 2>/dev/null || echo "")
                                fi
                            fi
                        fi
                    fi
                fi
            fi
            
            if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                WORD_COUNT=$(echo "$FULL_TEXT" | wc -w 2>/dev/null || echo "0")
                CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c 2>/dev/null || echo "0")
                echo "      Text: ${WORD_COUNT} words, ${CHAR_COUNT} characters"
                echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                # Show first 500 characters (increased from 200)
                TEXT_PREVIEW=$(echo "$FULL_TEXT" | head -c 500)
                echo "      $TEXT_PREVIEW"
                if [ ${#FULL_TEXT} -gt 500 ]; then
                    echo "..."
                    echo "      (Full text truncated. Use 'bash scripts/pod/result-view.sh $task_id' to see complete text)"
                fi
                echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            else
                # If no text found, show warning
                print_warning "      ⚠️  No transcription text available"
                print_status "      💡 Checking storage files..."
                
                # Debug: Check what files exist
                TASK_DIR="$PROJECT_ROOT/storage/transcriptions/$task_id"
                if [ -d "$TASK_DIR" ]; then
                    print_status "      📁 Storage directory exists: $TASK_DIR"
                    ls -lh "$TASK_DIR" 2>/dev/null | head -10 || true
                    
                    # Try to read chunks directly
                    METADATA_FILE="$TASK_DIR/metadata.json"
                    if [ -f "$METADATA_FILE" ]; then
                        # Show metadata.json content summary
                        print_status "      📄 Checking metadata.json content..."
                        METADATA_KEYS=$(jq -r 'keys | join(", ")' "$METADATA_FILE" 2>/dev/null || echo "unknown")
                        print_status "      📋 Keys in metadata.json: $METADATA_KEYS"
                        
                        # Check for chunks - show actual value
                        CHUNKS_VALUE=$(jq -r '.chunks' "$METADATA_FILE" 2>/dev/null || echo "null")
                        CHUNKS_COUNT=$(jq -r '.chunks // [] | length' "$METADATA_FILE" 2>/dev/null || echo "0")
                        FULL_TEXT_IN_METADATA=$(jq -r '.full_text // ""' "$METADATA_FILE" 2>/dev/null || echo "")
                        
                        # Debug: Show actual values
                        if [ "$CHUNKS_VALUE" = "null" ] || [ "$CHUNKS_VALUE" = "[]" ] || [ -z "$CHUNKS_VALUE" ]; then
                            print_warning "      ⚠️  chunks field is null or empty: $CHUNKS_VALUE"
                        else
                            print_status "      📦 chunks field exists: $CHUNKS_VALUE (type: $(echo "$CHUNKS_VALUE" | jq -r 'type' 2>/dev/null || echo "unknown"))"
                        fi
                        
                        if [ -z "$FULL_TEXT_IN_METADATA" ] || [ "$FULL_TEXT_IN_METADATA" = "null" ] || [ "$FULL_TEXT_IN_METADATA" = "" ]; then
                            print_warning "      ⚠️  full_text field is null or empty"
                        else
                            FULL_TEXT_LEN=${#FULL_TEXT_IN_METADATA}
                            print_status "      📝 full_text field exists: ${FULL_TEXT_LEN} characters"
                        fi
                        
                        if [ "$CHUNKS_COUNT" -gt 0 ]; then
                            print_status "      📦 Found $CHUNKS_COUNT chunks in metadata.json"
                            print_status "      💡 Attempting to build full_text from chunks..."
                            CHUNKS=$(jq -r '.chunks // []' "$METADATA_FILE" 2>/dev/null || echo "[]")
                            FULL_TEXT=$(echo "$CHUNKS" | jq -r '[.[] | .text // ""] | join(" ")' 2>/dev/null || echo "")
                            if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                                WORD_COUNT=$(echo "$FULL_TEXT" | wc -w 2>/dev/null || echo "0")
                                CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c 2>/dev/null || echo "0")
                                echo "      ✅ Built text from chunks: ${WORD_COUNT} words, ${CHAR_COUNT} characters"
                                echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                TEXT_PREVIEW=$(echo "$FULL_TEXT" | head -c 500)
                                echo "      $TEXT_PREVIEW"
                                if [ ${#FULL_TEXT} -gt 500 ]; then
                                    echo "..."
                                    echo "      (Full text truncated. Use 'bash scripts/pod/result-view.sh $task_id' to see complete text)"
                                fi
                                echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                            else
                                print_warning "      ⚠️  Chunks exist but could not build full_text (chunks may be empty)"
                            fi
                        elif [ -n "$FULL_TEXT_IN_METADATA" ] && [ "$FULL_TEXT_IN_METADATA" != "null" ] && [ "$FULL_TEXT_IN_METADATA" != "" ]; then
                            # If full_text exists directly in metadata.json
                            WORD_COUNT=$(echo "$FULL_TEXT_IN_METADATA" | wc -w 2>/dev/null || echo "0")
                            CHAR_COUNT=$(echo "$FULL_TEXT_IN_METADATA" | wc -c 2>/dev/null || echo "0")
                            echo "      ✅ Found full_text in metadata.json: ${WORD_COUNT} words, ${CHAR_COUNT} characters"
                            echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                            TEXT_PREVIEW=$(echo "$FULL_TEXT_IN_METADATA" | head -c 500)
                            echo "      $TEXT_PREVIEW"
                            if [ ${#FULL_TEXT_IN_METADATA} -gt 500 ]; then
                                echo "..."
                                echo "      (Full text truncated. Use 'bash scripts/pod/result-view.sh $task_id' to see complete text)"
                            fi
                            echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        else
                            # Check for full_text.json
                            FULL_TEXT_JSON="$TASK_DIR/full_text.json"
                            if [ -f "$FULL_TEXT_JSON" ]; then
                                print_status "      📄 Found full_text.json, checking content..."
                                FULL_TEXT_FROM_JSON=$(jq -r '.full_text // ""' "$FULL_TEXT_JSON" 2>/dev/null || echo "")
                                SEGMENTS_FROM_JSON=$(jq -r '.segments // []' "$FULL_TEXT_JSON" 2>/dev/null || echo "[]")
                                
                                if [ -n "$FULL_TEXT_FROM_JSON" ] && [ "$FULL_TEXT_FROM_JSON" != "null" ] && [ "$FULL_TEXT_FROM_JSON" != "" ]; then
                                    WORD_COUNT=$(echo "$FULL_TEXT_FROM_JSON" | wc -w 2>/dev/null || echo "0")
                                    CHAR_COUNT=$(echo "$FULL_TEXT_FROM_JSON" | wc -c 2>/dev/null || echo "0")
                                    echo "      ✅ Found full_text in full_text.json: ${WORD_COUNT} words, ${CHAR_COUNT} characters"
                                    echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                    TEXT_PREVIEW=$(echo "$FULL_TEXT_FROM_JSON" | head -c 500)
                                    echo "      $TEXT_PREVIEW"
                                    if [ ${#FULL_TEXT_FROM_JSON} -gt 500 ]; then
                                        echo "..."
                                        echo "      (Full text truncated. Use 'bash scripts/pod/result-view.sh $task_id' to see complete text)"
                                    fi
                                    echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                elif [ -n "$SEGMENTS_FROM_JSON" ] && [ "$SEGMENTS_FROM_JSON" != "[]" ] && [ "$SEGMENTS_FROM_JSON" != "null" ]; then
                                    SEGMENTS_COUNT=$(echo "$SEGMENTS_FROM_JSON" | jq 'length' 2>/dev/null || echo "0")
                                    if [ "$SEGMENTS_COUNT" -gt 0 ]; then
                                        print_status "      📦 Found $SEGMENTS_COUNT segments in full_text.json"
                                        FULL_TEXT=$(echo "$SEGMENTS_FROM_JSON" | jq -r '[.[] | .text // ""] | join(" ")' 2>/dev/null || echo "")
                                        if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                                            WORD_COUNT=$(echo "$FULL_TEXT" | wc -w 2>/dev/null || echo "0")
                                            CHAR_COUNT=$(echo "$FULL_TEXT" | wc -c 2>/dev/null || echo "0")
                                            echo "      ✅ Built text from segments: ${WORD_COUNT} words, ${CHAR_COUNT} characters"
                                            echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                            TEXT_PREVIEW=$(echo "$FULL_TEXT" | head -c 500)
                                            echo "      $TEXT_PREVIEW"
                                            if [ ${#FULL_TEXT} -gt 500 ]; then
                                                echo "..."
                                                echo "      (Full text truncated. Use 'bash scripts/pod/result-view.sh $task_id' to see complete text)"
                                            fi
                                            echo "      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                        fi
                                    fi
                                else
                                    print_warning "      ⚠️  full_text.json exists but contains no text or segments"
                                fi
                            else
                                print_warning "      ⚠️  No chunks, full_text, or full_text.json found"
                                print_status "      💡 This may indicate the transcription was not completed properly"
                                print_status "      💡 Check video worker logs: bash scripts/pod/logs-pod.sh worker | grep $task_id"
                            fi
                        fi
                    else
                        print_warning "      ⚠️  metadata.json not found"
                    fi
                else
                    print_warning "      ⚠️  Storage directory not found: $TASK_DIR"
                fi
            fi
        fi
        echo ""
        return 0
    fi
    
    return 1
}

# If detail mode, show details directly
if [ "$DETAIL_MODE" = "true" ]; then
    print_header "📋 Transcription Details (Latest $DETAIL_COUNT)"
    echo "📅 $(date)"
    echo ""
    
    check_api_health
    
    print_status "Fetching latest transcriptions..."
    LIST_RESPONSE=$(get_transcription_list)
    
    if [ -z "$LIST_RESPONSE" ]; then
        print_error "❌ Failed to fetch transcription list"
        exit 1
    fi
    
    if command -v jq &> /dev/null; then
        # Sort by created_at descending (latest first) and take first N
        TASK_IDS_ARRAY=($(echo "$LIST_RESPONSE" | jq -r 'sort_by(.created_at // "") | reverse | .[] | .task_id // .id // empty' 2>/dev/null | grep -v '^$' | head -n "$DETAIL_COUNT"))
        
        if [ ${#TASK_IDS_ARRAY[@]} -eq 0 ]; then
            print_warning "⚠️  No transcriptions found"
            exit 0
        fi
        
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        for task_id in "${TASK_IDS_ARRAY[@]}"; do
            display_transcription_detail "$task_id" true
        done
        
        print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    else
        print_error "❌ jq not found - cannot parse JSON"
        exit 1
    fi
    
    exit 0
fi

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
        echo "$LIST_RESPONSE" | jq -r '.[] | "\(.task_id // .id // "")|\(.status // "unknown")|\(.file_name // .file_path // "N/A")|\(.progress // 0)|\(.created_at // "N/A")"' 2>/dev/null | while IFS='|' read -r task_id status filename progress created_at; do
            if [ -n "$task_id" ]; then
                TASK_IDS+=("$task_id")
                
                # Status color
                if [ "$status" = "completed" ]; then
                    STATUS_COLOR="${GREEN}"
                elif [ "$status" = "processing" ] || [ "$status" = "pending" ]; then
                    STATUS_COLOR="${YELLOW}"
                elif [ "$status" = "failed" ]; then
                    STATUS_COLOR="${RED}"
                elif [ "$status" = "cancelled" ]; then
                    STATUS_COLOR="${CYAN}"
                else
                    STATUS_COLOR="${NC}"
                fi
                
                printf "  %2d. " "$INDEX"
                echo -e "${STATUS_COLOR}${status}${NC} | ${progress}% | $task_id"
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
    
    # Check storage files directly
    print_status "💡 Checking storage files..."
    TASK_DIR="$PROJECT_ROOT/storage/transcriptions/$TASK_ID"
    if [ -d "$TASK_DIR" ]; then
        print_status "   Found storage directory: $TASK_DIR"
        ls -lh "$TASK_DIR" 2>/dev/null || true
    else
        OLD_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID.json"
        if [ -f "$OLD_FILE" ]; then
            print_status "   Found old format file: $OLD_FILE"
        else
            print_warning "   No storage files found"
        fi
    fi
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
    FILENAME=$(echo "$DETAILS_RESPONSE" | jq -r '.file_name // .filename // .basic_info.filename // .file_path // "N/A"' 2>/dev/null)
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
        
        # Calculate and display processing time if completed
        if [ "$STATUS" = "completed" ] && [ "$CREATED_AT" != "N/A" ] && [ "$COMPLETED_AT" != "N/A" ]; then
            PROCESSING_TIME=$(calculate_processing_time "$CREATED_AT" "$COMPLETED_AT")
            if [ "$PROCESSING_TIME" != "N/A" ]; then
                echo "   Processing Time: $PROCESSING_TIME"
            fi
        fi
        echo ""
    fi
    
    # Full Text - only show if completed
    FULL_TEXT=""
    if [ "$STATUS" = "completed" ]; then
        FULL_TEXT=$(echo "$DETAILS_RESPONSE" | jq -r '.result.full_text // .full_text // .results.full_text // ""' 2>/dev/null)
        
        # If not found in API response, try reading from storage file directly
        if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
            # Try reading from full_text.json (new structure)
            FULL_TEXT_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/full_text.json"
            if [ -f "$FULL_TEXT_FILE" ]; then
                FULL_TEXT=$(jq -r '.full_text // ""' "$FULL_TEXT_FILE" 2>/dev/null || echo "")
                if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                    print_status "   ✅ Found full_text in storage file (full_text.json)"
                fi
            fi
            
            # If still not found, try from metadata.json
            if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
                METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/metadata.json"
                if [ -f "$METADATA_FILE" ]; then
                    FULL_TEXT=$(jq -r '.full_text // ""' "$METADATA_FILE" 2>/dev/null || echo "")
                    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                        print_status "   ✅ Found full_text in metadata.json"
                    fi
                fi
            fi
            
            # Try old format: {task_id}.json
            if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
                OLD_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID.json"
                if [ -f "$OLD_FILE" ]; then
                    FULL_TEXT=$(jq -r '.full_text // ""' "$OLD_FILE" 2>/dev/null || echo "")
                    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                        print_status "   ✅ Found full_text in old format file"
                    fi
                fi
            fi
            
            # If still no full_text, try to build it from chunks
            if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
                CHUNKS=$(echo "$DETAILS_RESPONSE" | jq -r '.result.chunks // .chunks // .results.chunks // []' 2>/dev/null)
                
                # Try reading chunks from storage if not in API response
                if [ -z "$CHUNKS" ] || [ "$CHUNKS" = "[]" ] || [ "$CHUNKS" = "null" ]; then
                    METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/metadata.json"
                    if [ -f "$METADATA_FILE" ]; then
                        CHUNKS=$(jq -r '.chunks // []' "$METADATA_FILE" 2>/dev/null || echo "[]")
                    fi
                fi
                
                # Build full_text from chunks
                if [ -n "$CHUNKS" ] && [ "$CHUNKS" != "[]" ] && [ "$CHUNKS" != "null" ]; then
                    CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
                    if [ "$CHUNK_COUNT" -gt 0 ]; then
                        FULL_TEXT=$(echo "$CHUNKS" | jq -r '[.[] | .text // ""] | join(" ")' 2>/dev/null || echo "")
                        if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                            print_status "   ✅ Built full_text from $CHUNK_COUNT chunks"
                        fi
                    fi
                fi
            fi
        fi
    fi
    
    # Show status-specific information
    if [ "$STATUS" = "pending" ] || [ "$STATUS" = "processing" ]; then
        print_header "⏳ Task Status: $STATUS"
        echo "   Progress: ${PROGRESS}%"
        if [ "$STATUS" = "processing" ]; then
            print_status "   💡 Task is currently being processed"
            print_status "   💡 Check logs: bash scripts/pod/logs-pod.sh worker"
        else
            print_status "   💡 Task is waiting to be processed"
        fi
        echo ""
    elif [ "$STATUS" = "cancelled" ]; then
        print_header "🚫 Task Status: Cancelled"
        echo "   This task was cancelled before completion"
        echo ""
    elif [ "$STATUS" = "failed" ]; then
        ERROR_MSG=$(echo "$DETAILS_RESPONSE" | jq -r '.error_message // .error_info.error_message // ""' 2>/dev/null)
        print_header "❌ Task Status: Failed"
        if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "null" ]; then
            echo "   Error: $ERROR_MSG"
        fi
        echo ""
    elif [ "$STATUS" = "completed" ]; then
        # Check if transcription actually has content
        CHUNKS_COUNT=$(echo "$DETAILS_RESPONSE" | jq -r '.result.chunks // .chunks // .results.chunks // [] | length' 2>/dev/null || echo "0")
        
        # Try reading from storage
        if [ "$CHUNKS_COUNT" -eq 0 ]; then
            METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/metadata.json"
            if [ -f "$METADATA_FILE" ]; then
                CHUNKS_COUNT=$(jq -r '.chunks // [] | length' "$METADATA_FILE" 2>/dev/null || echo "0")
            fi
        fi
        
        if [ "$CHUNKS_COUNT" -gt 0 ]; then
            print_success "✅ Transcription completed successfully"
            echo "   Chunks: $CHUNKS_COUNT"
        else
            print_warning "⚠️  Task marked as completed but no transcription content found"
        fi
        echo ""
    fi
    
    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
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
    fi
    
    # If still no text and status is completed, try one more time to build from chunks
    if [ "$STATUS" = "completed" ] && ([ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]); then
        # Try one more time to build from chunks if we haven't already
        METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/metadata.json"
        if [ -f "$METADATA_FILE" ]; then
            CHUNKS=$(jq -r '.chunks // []' "$METADATA_FILE" 2>/dev/null || echo "[]")
            if [ -n "$CHUNKS" ] && [ "$CHUNKS" != "[]" ] && [ "$CHUNKS" != "null" ]; then
                CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
                if [ "$CHUNK_COUNT" -gt 0 ]; then
                    FULL_TEXT=$(echo "$CHUNKS" | jq -r '[.[] | .text // ""] | join(" ")' 2>/dev/null || echo "")
                    if [ -n "$FULL_TEXT" ] && [ "$FULL_TEXT" != "null" ] && [ "$FULL_TEXT" != "" ]; then
                        print_success "✅ Built full_text from $CHUNK_COUNT chunks"
                        # Display the text
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
                    fi
                fi
            fi
        fi
        
        # If still no text, show warning
        if [ -z "$FULL_TEXT" ] || [ "$FULL_TEXT" = "null" ] || [ "$FULL_TEXT" = "" ]; then
            print_warning "⚠️  No transcription text available (task is completed but text is missing)"
            print_status "💡 Check storage files: ls -lh storage/transcriptions/$TASK_ID/"
            echo ""
        fi
    fi
    
    # Chunks - try multiple sources
    CHUNKS=$(echo "$DETAILS_RESPONSE" | jq -r '.result.chunks // .chunks // .results.chunks // []' 2>/dev/null)
    
    # If not found in API response, try reading from storage file
    if [ -z "$CHUNKS" ] || [ "$CHUNKS" = "[]" ] || [ "$CHUNKS" = "null" ]; then
        # Try reading from full_text.json (segments field)
        FULL_TEXT_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/full_text.json"
        if [ -f "$FULL_TEXT_FILE" ]; then
            CHUNKS=$(jq -r '.segments // []' "$FULL_TEXT_FILE" 2>/dev/null || echo "[]")
        fi
        
        # If still not found, try from metadata.json
        if [ -z "$CHUNKS" ] || [ "$CHUNKS" = "[]" ] || [ "$CHUNKS" = "null" ]; then
            METADATA_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID/metadata.json"
            if [ -f "$METADATA_FILE" ]; then
                CHUNKS=$(jq -r '.chunks // []' "$METADATA_FILE" 2>/dev/null || echo "[]")
            fi
        fi
        
        # Try old format
        if [ -z "$CHUNKS" ] || [ "$CHUNKS" = "[]" ] || [ "$CHUNKS" = "null" ]; then
            OLD_FILE="$PROJECT_ROOT/storage/transcriptions/$TASK_ID.json"
            if [ -f "$OLD_FILE" ]; then
                CHUNKS=$(jq -r '.chunks // []' "$OLD_FILE" 2>/dev/null || echo "[]")
            fi
        fi
    fi
    
    CHUNK_COUNT=$(echo "$CHUNKS" | jq 'length' 2>/dev/null || echo "0")
    
    if [ "$CHUNK_COUNT" -gt 0 ]; then
        print_header "📦 Chunks: $CHUNK_COUNT chunks"
        echo ""
        
        # Show first few chunks as preview
        if [ "$CHUNK_COUNT" -le 5 ]; then
            echo "$CHUNKS" | jq -r '.[] | "   [\(.start_time // .start // "N/A")s - \(.end_time // .end // "N/A")s] \(.text // "")"' 2>/dev/null | head -5
        else
            echo "$CHUNKS" | jq -r '.[] | "   [\(.start_time // .start // "N/A")s - \(.end_time // .end // "N/A")s] \(.text // "")"' 2>/dev/null | head -3
            print_status "   ... and $((CHUNK_COUNT - 3)) more chunks"
        fi
        echo ""
    fi
    
    # Error Info (only show if failed)
    if [ "$STATUS" = "failed" ]; then
        ERROR_MSG=$(echo "$DETAILS_RESPONSE" | jq -r '.error_message // .error_info.error_message // ""' 2>/dev/null)
        if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "null" ]; then
            print_error "❌ Error: $ERROR_MSG"
            echo ""
        fi
    fi
    
else
    # Fallback: display raw JSON
    print_warning "⚠️  jq not found - displaying raw JSON"
    echo "$DETAILS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DETAILS_RESPONSE"
fi

echo ""
print_status "💡 Useful commands:"
echo "   bash scripts/pod/result-view.sh <task-id>              # View specific task"
echo "   bash scripts/pod/result-view.sh -detail [number]       # View latest N completed tasks"
echo "   bash scripts/pod/task-service.sh list                  # List all tasks"
echo "   bash scripts/pod/task-service.sh stop <task-id>        # Stop a task"
echo ""

