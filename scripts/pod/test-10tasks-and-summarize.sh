#!/bin/bash
# Script สำหรับทดสอบ Transcription 10 Tasks และสรุปผลลัพธ์
# รันบน remote server และสรุปผลลัพธ์เป็น Markdown
#
# วิธีใช้งาน:
#   bash scripts/pod/test-10tasks-and-summarize.sh [video_file] [server_alias]
#
# ตัวอย่าง:
#   bash scripts/pod/test-10tasks-and-summarize.sh v10-1.mp4 4000-ada

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
VIDEO_FILE="${1:-v10-1.mp4}"
SERVER_ALIAS="${2:-4000-ada}"
TASK_COUNT=10
PROJECT_DIR="/workspace/transcription-service"
BENCHMARK_DIR="$PROJECT_DIR/docs/RunPod-Z2/Benchmark"

# Function for floating point calculations
calc() {
    if command -v python3 > /dev/null 2>&1; then
        python3 -c "print(f'{eval($1):.2f}')" 2>/dev/null || echo "0"
    else
        awk "BEGIN {printf \"%.2f\", $1}" 2>/dev/null || echo "0"
    fi
}

# Function to run test on server
run_test() {
    local server=$1
    local video_file=$2
    local count=$3
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🧪 Testing: $server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    local API_URL="http://localhost:8010"
    
    # Pre-flight check
    echo -e "${CYAN}📡 Checking service...${NC}"
    if curl -sf --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Service is running${NC}"
    else
        echo -e "${RED}   ❌ Service is not responding${NC}"
        return 1
    fi
    echo ""
    
    # Create tasks
    echo -e "${CYAN}📤 Creating $count tasks...${NC}"
    local start_time=$(date +%s)
    
    local response=$(curl -s -X POST "$API_URL/api/control/test" \
        -H "Content-Type: application/json" \
        -d "{
            \"video_file\": \"$video_file\",
            \"num_concurrent\": $count,
            \"model_size\": \"medium\",
            \"language\": \"th\"
        }" 2>&1)
    
    if echo "$response" | grep -q '"detail"\|"error"'; then
        echo -e "${RED}   ❌ API Error:${NC}"
        echo "      $(echo "$response" | head -c 300)"
        return 1
    fi
    
    # Extract task IDs
    local task_ids=()
    if command -v jq > /dev/null 2>&1; then
        task_ids=($(echo "$response" | jq -r '.task_ids[]?' 2>/dev/null || echo ""))
    else
        task_ids=($(echo "$response" | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' || echo ""))
    fi
    
    if [ ${#task_ids[@]} -eq 0 ]; then
        echo -e "${RED}   ❌ Failed to get task IDs${NC}"
        return 1
    fi
    
    echo -e "${GREEN}   ✅ Created ${#task_ids[@]} tasks${NC}"
    echo ""
    
    # Wait for completion
    echo -e "${CYAN}⏳ Waiting for completion...${NC}"
    local completed=0
    local success_count=0
    local fail_count=0
    local max_wait=1800  # 30 minutes
    local elapsed=0
    
    declare -A task_start_times
    declare -A task_end_times
    declare -A task_durations
    declare -A task_statuses
    declare -A task_texts
    declare -A task_errors
    
    for task_id in "${task_ids[@]}"; do
        task_start_times["$task_id"]=$start_time
        task_statuses["$task_id"]="pending"
    done
    
    while [ $completed -lt ${#task_ids[@]} ] && [ $elapsed -lt $max_wait ]; do
        sleep 5
        elapsed=$((elapsed + 5))
        completed=0
        
        for task_id in "${task_ids[@]}"; do
            if [ "${task_statuses[$task_id]}" = "completed" ] || [ "${task_statuses[$task_id]}" = "failed" ]; then
                completed=$((completed + 1))
                continue
            fi
            
            # Check status - try multiple endpoints
            local status_response=""
            
            # Try /api/progress/transcription/{task_id} first (preferred)
            status_response=$(curl -s "$API_URL/api/progress/transcription/$task_id" 2>/dev/null || echo "")
            if [ -z "$status_response" ] || echo "$status_response" | grep -q '"detail"\|"Not Found"\|"ไม่พบ"'; then
                # Try /transcribe/{task_id} (loads from storage if not in memory)
                status_response=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
            fi
            if [ -z "$status_response" ] || echo "$status_response" | grep -q '"detail"\|"Not Found"\|"ไม่พบ"'; then
                # Try /api/history/transcription/{task_id} as last resort
                status_response=$(curl -s "$API_URL/api/history/transcription/$task_id" 2>/dev/null || echo "")
            fi
            if [ -z "$status_response" ]; then
                status_response="{}"
            fi
            
            local status=$(echo "$status_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
            
            if [ "$status" = "completed" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - task_start_times["$task_id"]))
                task_statuses["$task_id"]="completed"
                task_end_times["$task_id"]=$end_time
                task_durations["$task_id"]=$duration
                
                # Extract text
                local text=""
                if command -v jq > /dev/null 2>&1; then
                    text=$(echo "$status_response" | jq -r '.corrected_text // .full_text // ""' 2>/dev/null || echo "")
                    if [ -z "$text" ] || [ "$text" = "null" ]; then
                        text=$(echo "$status_response" | jq -r '[.chunks[]?.text // .chunks[]?.original_text] | join(" ")' 2>/dev/null || echo "")
                    fi
                fi
                text=$(echo "$text" | tr '\n' ' ' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
                task_texts["$task_id"]="$text"
                
                success_count=$((success_count + 1))
                completed=$((completed + 1))
                
                echo -e "${GREEN}   ✅ Task completed in ${duration}s${NC}"
                
            elif [ "$status" = "failed" ] || [ "$status" = "error" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - task_start_times["$task_id"]))
                task_statuses["$task_id"]="failed"
                task_end_times["$task_id"]=$end_time
                task_durations["$task_id"]=$duration
                
                local error_msg=$(echo "$status_response" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4 || echo "Unknown error")
                task_errors["$task_id"]="$error_msg"
                
                fail_count=$((fail_count + 1))
                completed=$((completed + 1))
                
                echo -e "${RED}   ❌ Task failed in ${duration}s: $error_msg${NC}"
            fi
        done
        
        if [ $completed -lt ${#task_ids[@]} ]; then
            echo "   Progress: $completed/${#task_ids[@]} completed (${elapsed}s elapsed)"
        fi
    done
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    # Calculate statistics
    local durations_array=()
    for task_id in "${task_ids[@]}"; do
        if [ "${task_statuses[$task_id]}" = "completed" ]; then
            durations_array+=("${task_durations[$task_id]}")
        fi
    done
    
    local min_duration=0
    local max_duration=0
    local avg_duration=0
    if [ ${#durations_array[@]} -gt 0 ]; then
        min_duration=${durations_array[0]}
        max_duration=${durations_array[0]}
        local sum=0
        for d in "${durations_array[@]}"; do
            if [ "$d" -lt "$min_duration" ]; then
                min_duration=$d
            fi
            if [ "$d" -gt "$max_duration" ]; then
                max_duration=$d
            fi
            sum=$((sum + d))
        done
        avg_duration=$(calc "$sum / ${#durations_array[@]}")
    fi
    
    # Generate summary
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local summary_file="$BENCHMARK_DIR/${server}-10tasks-${timestamp}.md"
    mkdir -p "$BENCHMARK_DIR"
    
    cat > "$summary_file" << EOF
# 📊 Transcription Performance Test: 10 Tasks - $server

**Test Date**: $(date)
**Server**: $server
**Video File**: $video_file
**Task Count**: $count tasks
**Model**: medium
**Language**: th

---

## 📈 Summary

| Metric | Value |
|--------|-------|
| **Total Duration** | ${total_duration}s |
| **Success Count** | $success_count/$count |
| **Fail Count** | $fail_count |
| **Success Rate** | $(calc "$success_count * 100 / $count")% |
| **Min Task Duration** | ${min_duration}s |
| **Max Task Duration** | ${max_duration}s |
| **Avg Task Duration** | ${avg_duration}s |

---

## ⏱️ Task Durations

EOF
    
    for i in "${!task_ids[@]}"; do
        local task_id="${task_ids[$i]}"
        local duration="${task_durations[$task_id]:-0}"
        local status="${task_statuses[$task_id]:-unknown}"
        local text="${task_texts[$task_id]:-}"
        
        cat >> "$summary_file" << EOF
### Task $((i+1)): \`${task_id:0:8}...\`

- **Duration**: ${duration}s
- **Status**: $status
- **Text Length**: ${#text} characters

EOF
        
        if [ -n "$text" ] && [ "$text" != "null" ] && [ "$text" != "" ]; then
            # Escape markdown
            text=$(echo "$text" | sed 's/`/\\`/g' | sed 's/\$/\\$/g')
            cat >> "$summary_file" << EOF
**Transcription Text**:
\`\`\`
$text
\`\`\`

EOF
        else
            cat >> "$summary_file" << EOF
**Transcription Text**: _(ไม่มีข้อความ)_

EOF
        fi
        
        if [ -n "${task_errors[$task_id]:-}" ]; then
            cat >> "$summary_file" << EOF
**Error**: ${task_errors[$task_id]}

EOF
        fi
        
        cat >> "$summary_file" << EOF
---

EOF
    done
    
    cat >> "$summary_file" << EOF

## 📋 All Task IDs

EOF
    
    for i in "${!task_ids[@]}"; do
        echo "- Task $((i+1)): \`${task_ids[$i]}\`" >> "$summary_file"
    done
    
    cat >> "$summary_file" << EOF

---

_Report generated at $(date)_
EOF
    
    echo ""
    echo -e "${GREEN}✅ Test completed for $server${NC}"
    echo "  Success: $success_count/$count"
    echo "  Failed: $fail_count/$count"
    echo "  Total time: ${total_duration}s"
    echo "  Summary saved to: $summary_file"
    echo ""
    
    echo "$summary_file"
}

# Main
if [ -z "$SSH_CONNECTION" ]; then
    # Running locally, use SSH
    echo -e "${YELLOW}⚠️  Running test via SSH on $SERVER_ALIAS${NC}"
    ssh "$SERVER_ALIAS" "cd $PROJECT_DIR && bash scripts/pod/test-10tasks-and-summarize.sh '$VIDEO_FILE' '$SERVER_ALIAS'"
else
    # Running on server
    run_test "$SERVER_ALIAS" "$VIDEO_FILE" "$TASK_COUNT"
fi
