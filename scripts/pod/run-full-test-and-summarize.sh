#!/bin/bash
# Script สำหรับทดสอบ Transcription 10 Concurrency และสรุปผลลัพธ์โดยอัตโนมัติ
# รันบน remote servers ผ่าน SSH และสรุปผลลัพธ์ทั้งหมด
#
# วิธีใช้งาน:
#   bash scripts/pod/run-full-test-and-summarize.sh [video_file] [task_count]
#
# ตัวอย่าง:
#   bash scripts/pod/run-full-test-and-summarize.sh v10-1.mp4 2
#   bash scripts/pod/run-full-test-and-summarize.sh v10-1.mp4 10

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
SERVER1="4080s"
SERVER2="4000-ada"
SERVER1_URL="http://80.15.7.37:41314"
SERVER2_URL="http://87.197.119.40:41314"
VIDEO_FILE="${1:-v10-1.mp4}"
TASK_COUNT="${2:-10}"  # Default to 10 tasks, can be overridden
PROJECT_DIR="/workspace/transcription-service"

# Results storage
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="/tmp/transcription-full-test-${TIMESTAMP}"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🧪 Full Transcription Test: $TASK_COUNT Concurrency                    ║"
echo "║  Testing both 4080s and 4000-ada servers                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Server 1: $SERVER1 ($SERVER1_URL)"
echo "  Server 2: $SERVER2 ($SERVER2_URL)"
echo "  Video File: $VIDEO_FILE"
echo "  Concurrency: $TASK_COUNT"
echo "  Results Dir: $RESULTS_DIR"
echo ""

# Function to run test on a server and collect results
run_test_on_server() {
    local server=$1
    local server_url=$2
    local video_file=$3
    local count=$4
    local results_file="$RESULTS_DIR/${server}-results.json"
    local texts_file="$RESULTS_DIR/${server}-texts.txt"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🧪 Testing: $server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Determine API URL - if running on the server itself, use localhost
    # Otherwise use the public URL
    if [ "$server" = "4080s" ] && [ "$(hostname 2>/dev/null || echo '')" != "" ]; then
        # We're on 4080s server, use localhost
        API_URL="http://localhost:8010"
        echo -e "${CYAN}📡 Using localhost API (running on 4080s)${NC}"
    elif [ "$server" = "4000-ada" ] && [ "$(hostname 2>/dev/null || echo '')" != "" ]; then
        # We're on 4000-ada server, use localhost
        API_URL="http://localhost:8010"
        echo -e "${CYAN}📡 Using localhost API (running on 4000-ada)${NC}"
    else
        # Use public URL
        API_URL="$server_url"
        echo -e "${CYAN}📡 Using API URL: $API_URL${NC}"
    fi
    
    # Pre-flight check
    echo -e "${CYAN}📡 Checking service...${NC}"
    if curl -sf --max-time 5 "$API_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Service is running${NC}"
    else
        echo -e "${RED}   ❌ Service is not responding${NC}"
        return 1
    fi
    echo ""
    
    # Use /api/control/test endpoint
    echo -e "${CYAN}📤 Sending $count tasks via /api/control/test...${NC}"
    local start_time=$(date +%s)
    
    local response=$(curl -s -X POST "$API_URL/api/control/test" \
        -H "Content-Type: application/json" \
        -d "{
            \"video_file\": \"$video_file\",
            \"num_concurrent\": $count,
            \"model_size\": \"medium\",
            \"language\": \"th\"
        }" 2>&1)
    
    # Check for errors
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
    
    # Wait for completion and collect detailed results
    echo -e "${CYAN}⏳ Waiting for completion and collecting results...${NC}"
    local completed=0
    local success_count=0
    local fail_count=0
    local max_wait=1800  # 30 minutes
    local elapsed=0
    local task_data=()
    
    # Initialize tracking
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
            
            # Check status (use correct endpoint)
            # Try /api/progress/transcription/{task_id} first (preferred endpoint)
            local status_response=$(curl -s "$API_URL/api/progress/transcription/$task_id" 2>/dev/null || echo "{}")
            # Try alternative endpoints if main one fails
            if [ "$status_response" = "{}" ] || [ -z "$status_response" ] || echo "$status_response" | grep -q '"detail"\|"Not Found"'; then
                status_response=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "{}")
            fi
            # Final fallback
            if [ "$status_response" = "{}" ] || [ -z "$status_response" ] || echo "$status_response" | grep -q '"detail"\|"Not Found"'; then
                status_response=$(curl -s "$API_URL/api/progress/$task_id" 2>/dev/null || echo "{}")
            fi
            local status=$(echo "$status_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
            
            if [ "$status" = "completed" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - task_start_times["$task_id"]))
                task_statuses["$task_id"]="completed"
                task_end_times["$task_id"]=$end_time
                task_durations["$task_id"]=$duration
                
                # Extract text (try corrected_text first, then full_text, then chunks)
                # Use jq if available for better JSON parsing
                local text=""
                if command -v jq > /dev/null 2>&1; then
                    text=$(echo "$status_response" | jq -r '.corrected_text // .full_text // ""' 2>/dev/null || echo "")
                    # If still empty, try getting from chunks
                    if [ -z "$text" ] || [ "$text" = "null" ]; then
                        text=$(echo "$status_response" | jq -r '[.chunks[]?.text // .chunks[]?.original_text] | join(" ")' 2>/dev/null || echo "")
                    fi
                else
                    # Fallback: use grep with better pattern (handle multiline JSON)
                    text=$(echo "$status_response" | grep -oE '"corrected_text"\s*:\s*"[^"]*"' | head -1 | sed -E 's/.*"corrected_text"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/' || echo "")
                    if [ -z "$text" ]; then
                        text=$(echo "$status_response" | grep -oE '"full_text"\s*:\s*"[^"]*"' | head -1 | sed -E 's/.*"full_text"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/' || echo "")
                    fi
                fi
                # Clean text (remove newlines for storage, but keep in texts file)
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
    
    # Save detailed results to JSON
    echo "{" > "$results_file"
    echo "  \"server\": \"$server\"," >> "$results_file"
    echo "  \"server_url\": \"$API_URL\"," >> "$results_file"
    echo "  \"video_file\": \"$video_file\"," >> "$results_file"
    echo "  \"test_start\": \"$(date -u -d @$start_time +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -r $start_time +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")\"," >> "$results_file"
    echo "  \"test_end\": \"$(date -u -d @$end_time +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -r $end_time +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")\"," >> "$results_file"
    echo "  \"total_duration\": $total_duration," >> "$results_file"
    echo "  \"task_count\": ${#task_ids[@]}," >> "$results_file"
    echo "  \"success_count\": $success_count," >> "$results_file"
    echo "  \"fail_count\": $fail_count," >> "$results_file"
    echo "  \"tasks\": [" >> "$results_file"
    
    # Save texts to separate file
    echo "=== Transcription Texts from $server ===" > "$texts_file"
    echo "" >> "$texts_file"
    
    for i in "${!task_ids[@]}"; do
        local task_id="${task_ids[$i]}"
        if [ $i -gt 0 ]; then
            echo "," >> "$results_file"
        fi
        echo "    {" >> "$results_file"
        echo "      \"task_id\": \"$task_id\"," >> "$results_file"
        echo "      \"status\": \"${task_statuses[$task_id]}\"," >> "$results_file"
        echo "      \"duration\": ${task_durations[$task_id]:-0}," >> "$results_file"
        echo "      \"text\": \"${task_texts[$task_id]:-}\"," >> "$results_file"
        if [ -n "${task_errors[$task_id]:-}" ]; then
            echo "      \"error\": \"${task_errors[$task_id]}\"," >> "$results_file"
        fi
        echo "      \"start_time\": ${task_start_times[$task_id]:-0}," >> "$results_file"
        echo "      \"end_time\": ${task_end_times[$task_id]:-0}" >> "$results_file"
        echo -n "    }" >> "$results_file"
        
        # Add to texts file
        echo "Task $((i+1)): $task_id" >> "$texts_file"
        echo "Status: ${task_statuses[$task_id]}" >> "$texts_file"
        echo "Duration: ${task_durations[$task_id]:-0}s" >> "$texts_file"
        if [ -n "${task_texts[$task_id]:-}" ]; then
            echo "Text: ${task_texts[$task_id]}" >> "$texts_file"
        else
            echo "Text: (ไม่มีข้อความ)" >> "$texts_file"
        fi
        if [ -n "${task_errors[$task_id]:-}" ]; then
            echo "Error: ${task_errors[$task_id]}" >> "$texts_file"
        fi
        echo "" >> "$texts_file"
        echo "────────────────────────────────────" >> "$texts_file"
        echo "" >> "$texts_file"
    done
    
    echo "" >> "$results_file"
    echo "  ]" >> "$results_file"
    echo "}" >> "$results_file"
    
    echo ""
    echo -e "${GREEN}✅ Test completed for $server${NC}"
    echo "  Success: $success_count/${#task_ids[@]}"
    echo "  Failed: $fail_count/${#task_ids[@]}"
    echo "  Total time: ${total_duration}s"
    echo ""
    
    # Return task data for summary
    echo "${task_ids[@]}|${task_durations[*]}|${task_statuses[*]}|${task_texts[*]}"
}

# Function to generate comprehensive summary
generate_summary() {
    local summary_file="$RESULTS_DIR/SUMMARY.md"
    
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  📊 Generating Summary Report                                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Read results
    local file1="$RESULTS_DIR/${SERVER1}-results.json"
    local file2="$RESULTS_DIR/${SERVER2}-results.json"
    
    if [ ! -f "$file1" ] || [ ! -f "$file2" ]; then
        echo -e "${RED}❌ Results files not found${NC}"
        return 1
    fi
    
    # Extract data using jq or grep
    if command -v jq > /dev/null 2>&1; then
        local s1_total=$(jq -r '.total_duration' "$file1")
        local s1_success=$(jq -r '.success_count' "$file1")
        local s1_fail=$(jq -r '.fail_count' "$file1")
        local s1_tasks=$(jq -r '.tasks[] | "\(.task_id)|\(.duration)|\(.status)|\(.text // "")"' "$file1")
        
        local s2_total=$(jq -r '.total_duration' "$file2")
        local s2_success=$(jq -r '.success_count' "$file2")
        local s2_fail=$(jq -r '.fail_count' "$file2")
        local s2_tasks=$(jq -r '.tasks[] | "\(.task_id)|\(.duration)|\(.status)|\(.text // "")"' "$file2")
    else
        # Fallback using grep
        local s1_total=$(grep -o '"total_duration": [0-9]*' "$file1" | grep -o '[0-9]*' || echo "0")
        local s1_success=$(grep -o '"success_count": [0-9]*' "$file1" | grep -o '[0-9]*' || echo "0")
        local s1_fail=$(grep -o '"fail_count": [0-9]*' "$file1" | grep -o '[0-9]*' || echo "0")
        
        local s2_total=$(grep -o '"total_duration": [0-9]*' "$file2" | grep -o '[0-9]*' || echo "0")
        local s2_success=$(grep -o '"success_count": [0-9]*' "$file2" | grep -o '[0-9]*' || echo "0")
        local s2_fail=$(grep -o '"fail_count": [0-9]*' "$file2" | grep -o '[0-9]*' || echo "0")
    fi
    
    # Helper function for calculation (defined here for use in generate_summary)
    if command -v python3 > /dev/null 2>&1; then
        calc() { python3 -c "print('%.2f' % ($1))" 2>/dev/null || echo "0"; }
    elif command -v bc > /dev/null 2>&1; then
        calc() { echo "scale=2; $1" | bc -l 2>/dev/null || echo "0"; }
    else
        calc() { awk "BEGIN {printf \"%.2f\", $1}" 2>/dev/null || echo "0"; }
    fi
    
    # Calculate averages
    local s1_avg=0
    local s2_avg=0
    if [ "$s1_success" -gt 0 ]; then
        local s1_durations=($(echo "$s1_tasks" | cut -d'|' -f2 | grep -E '^[0-9]+$' || echo ""))
        if [ ${#s1_durations[@]} -gt 0 ]; then
            local s1_sum=0
            for d in "${s1_durations[@]}"; do
                s1_sum=$((s1_sum + d))
            done
            s1_avg=$(calc "$s1_sum / ${#s1_durations[@]}")
        fi
    fi
    
    if [ "$s2_success" -gt 0 ]; then
        local s2_durations=($(echo "$s2_tasks" | cut -d'|' -f2 | grep -E '^[0-9]+$' || echo ""))
        if [ ${#s2_durations[@]} -gt 0 ]; then
            local s2_sum=0
            for d in "${s2_durations[@]}"; do
                s2_sum=$((s2_sum + d))
            done
            s2_avg=$(calc "$s2_sum / ${#s2_durations[@]}")
        fi
    fi
    
    # Generate Markdown summary
    cat > "$summary_file" << EOF
# 📊 Transcription Test Summary Report

**Test Date**: $(date)
**Video File**: $VIDEO_FILE
**Concurrency**: $TASK_COUNT tasks

---

## 🖥️ Server Comparison

| Metric | $SERVER1 | $SERVER2 |
|--------|----------|----------|
| **Total Duration** | ${s1_total}s | ${s2_total}s |
| **Success Count** | $s1_success/$TASK_COUNT | $s2_success/$TASK_COUNT |
| **Fail Count** | $s1_fail | $s2_fail |
| **Average Time per Task** | ${s1_avg}s | ${s2_avg}s |
| **Success Rate** | $(calc "$s1_success * 100 / $TASK_COUNT")% | $(calc "$s2_success * 100 / $TASK_COUNT")% |

---

## ⏱️ Detailed Task Durations

### $SERVER1

EOF
    
    # Add task details for SERVER1
    local task_num=1
    if [ -n "$s1_tasks" ]; then
        while IFS='|' read -r task_id duration status text; do
            echo "**Task $task_num** ($task_id)" >> "$summary_file"
            echo "- Duration: ${duration}s" >> "$summary_file"
            echo "- Status: $status" >> "$summary_file"
            if [ -n "$text" ] && [ "$text" != "null" ] && [ "$text" != "" ]; then
                # Escape text for markdown
                text=$(echo "$text" | sed 's/`/\\`/g' | sed 's/\$/\\$/g')
                echo "- Text: \`$text\`" >> "$summary_file"
            else
                echo "- Text: _(ไม่มีข้อความ)_" >> "$summary_file"
            fi
            echo "" >> "$summary_file"
            task_num=$((task_num + 1))
        done <<< "$s1_tasks"
    else
        echo "_(ไม่มีข้อมูล tasks)_" >> "$summary_file"
    fi
    
    cat >> "$summary_file" << EOF

### $SERVER2

EOF
    
    # Add task details for SERVER2
    task_num=1
    if [ -n "$s2_tasks" ]; then
        while IFS='|' read -r task_id duration status text; do
            echo "**Task $task_num** ($task_id)" >> "$summary_file"
            echo "- Duration: ${duration}s" >> "$summary_file"
            echo "- Status: $status" >> "$summary_file"
            if [ -n "$text" ] && [ "$text" != "null" ] && [ "$text" != "" ]; then
                # Escape text for markdown
                text=$(echo "$text" | sed 's/`/\\`/g' | sed 's/\$/\\$/g')
                echo "- Text: \`$text\`" >> "$summary_file"
            else
                echo "- Text: _(ไม่มีข้อความ)_" >> "$summary_file"
            fi
            echo "" >> "$summary_file"
            task_num=$((task_num + 1))
        done <<< "$s2_tasks"
    else
        echo "_(ไม่มีข้อมูล tasks)_" >> "$summary_file"
    fi
    
    cat >> "$summary_file" << EOF

---

## 📝 All Transcription Texts

### $SERVER1 Texts

EOF
    cat "$RESULTS_DIR/${SERVER1}-texts.txt" >> "$summary_file"
    
    cat >> "$summary_file" << EOF

### $SERVER2 Texts

EOF
    cat "$RESULTS_DIR/${SERVER2}-texts.txt" >> "$summary_file"
    
    cat >> "$summary_file" << EOF

---

## 🏆 Winner

EOF
    
    # Determine winner (use calc-compatible comparison)
    if [ "$s1_fail" = "0" ] && [ "$s2_fail" = "0" ]; then
        # Use Python or awk for comparison
        if command -v python3 > /dev/null 2>&1; then
            local s1_lt_s2=$(python3 -c "print(1 if float('$s1_avg') < float('$s2_avg') else 0)" 2>/dev/null || echo "0")
            local s2_lt_s1=$(python3 -c "print(1 if float('$s2_avg') < float('$s1_avg') else 0)" 2>/dev/null || echo "0")
        else
            local s1_lt_s2=$(awk "BEGIN {print ($s1_avg < $s2_avg) ? 1 : 0}")
            local s2_lt_s1=$(awk "BEGIN {print ($s2_avg < $s1_avg) ? 1 : 0}")
        fi
        
        if [ "$s1_lt_s2" = "1" ]; then
            echo "**🏆 Winner: $SERVER1** (Faster average time: ${s1_avg}s vs ${s2_avg}s)" >> "$summary_file"
        elif [ "$s2_lt_s1" = "1" ]; then
            echo "**🏆 Winner: $SERVER2** (Faster average time: ${s2_avg}s vs ${s1_avg}s)" >> "$summary_file"
        else
            echo "**🤝 Perfect Tie!** Both servers completed all tasks with similar performance." >> "$summary_file"
        fi
    elif [ "$s1_fail" = "0" ] && [ "$s2_fail" -gt 0 ]; then
        echo "**🏆 Winner: $SERVER1** (No failures vs $s2_fail failures)" >> "$summary_file"
    elif [ "$s2_fail" = "0" ] && [ "$s1_fail" -gt 0 ]; then
        echo "**🏆 Winner: $SERVER2** (No failures vs $s1_fail failures)" >> "$summary_file"
    else
        if [ "$s1_success" -gt "$s2_success" ]; then
            echo "**🏆 Winner: $SERVER1** (More successful tasks: $s1_success vs $s2_success)" >> "$summary_file"
        elif [ "$s2_success" -gt "$s1_success" ]; then
            echo "**🏆 Winner: $SERVER2** (More successful tasks: $s2_success vs $s1_success)" >> "$summary_file"
        else
            echo "**🤝 Tie** Both servers had similar results" >> "$summary_file"
        fi
    fi
    
    echo "" >> "$summary_file"
    echo "---" >> "$summary_file"
    echo "" >> "$summary_file"
    echo "_Report generated at $(date)_" >> "$summary_file"
    
    # Display summary
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}📊 SUMMARY REPORT${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Server Comparison                                           ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    printf "║  %-20s %20s %20s ║\n" "Metric" "$SERVER1" "$SERVER2"
    echo "╠══════════════════════════════════════════════════════════════╣"
    printf "║  %-20s %20s %20s ║\n" "Total Duration" "${s1_total}s" "${s2_total}s"
    printf "║  %-20s %20s %20s ║\n" "Success" "$s1_success/$TASK_COUNT" "$s2_success/$TASK_COUNT"
    printf "║  %-20s %20s %20s ║\n" "Failed" "$s1_fail" "$s2_fail"
    printf "║  %-20s %20s %20s ║\n" "Avg Time/Task" "${s1_avg}s" "${s2_avg}s"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Show winner (use calc-compatible comparison)
    if [ "$s1_fail" = "0" ] && [ "$s2_fail" = "0" ]; then
        # Use Python or awk for comparison
        if command -v python3 > /dev/null 2>&1; then
            local s1_lt_s2=$(python3 -c "print(1 if float('$s1_avg') < float('$s2_avg') else 0)" 2>/dev/null || echo "0")
            local s2_lt_s1=$(python3 -c "print(1 if float('$s2_avg') < float('$s1_avg') else 0)" 2>/dev/null || echo "0")
        else
            local s1_lt_s2=$(awk "BEGIN {print ($s1_avg < $s2_avg) ? 1 : 0}")
            local s2_lt_s1=$(awk "BEGIN {print ($s2_avg < $s1_avg) ? 1 : 0}")
        fi
        
        if [ "$s1_lt_s2" = "1" ]; then
            echo -e "${GREEN}🏆 Winner: $SERVER1 (Faster: ${s1_avg}s vs ${s2_avg}s)${NC}"
        elif [ "$s2_lt_s1" = "1" ]; then
            echo -e "${GREEN}🏆 Winner: $SERVER2 (Faster: ${s2_avg}s vs ${s1_avg}s)${NC}"
        else
            echo -e "${GREEN}🤝 Perfect Tie! Both servers completed all tasks.${NC}"
        fi
    elif [ "$s1_fail" = "0" ] && [ "$s2_fail" -gt 0 ]; then
        echo -e "${GREEN}🏆 Winner: $SERVER1 (No failures vs $s2_fail failures)${NC}"
    elif [ "$s2_fail" = "0" ] && [ "$s1_fail" -gt 0 ]; then
        echo -e "${GREEN}🏆 Winner: $SERVER2 (No failures vs $s1_fail failures)${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}📁 Full report saved to: $summary_file${NC}"
    echo -e "${CYAN}📁 Texts saved to: $RESULTS_DIR/${SERVER1}-texts.txt and $RESULTS_DIR/${SERVER2}-texts.txt${NC}"
    echo ""
}

# Main execution
main() {
    # Check dependencies - use Python for calculations if bc is not available
    if ! command -v bc > /dev/null 2>&1; then
        if command -v python3 > /dev/null 2>&1; then
            echo -e "${CYAN}📊 Using Python for calculations (bc not found)${NC}"
            # Define a simple calc function using Python
            calc() {
                python3 -c "print($1)" 2>/dev/null || echo "0"
            }
        else
            echo -e "${YELLOW}⚠️  bc not found, calculations may be limited${NC}"
            # Fallback: simple shell arithmetic (limited)
            calc() {
                echo "$1" | awk '{print $1}'
            }
        fi
    else
        calc() {
            echo "$1" | bc -l 2>/dev/null || echo "0"
        }
    fi
    
    echo -e "${YELLOW}⚠️  Running transcription tests on both servers${NC}"
    echo -e "${YELLOW}   Video: $VIDEO_FILE, Concurrency: $TASK_COUNT${NC}"
    echo ""
    echo -e "${CYAN}Starting tests in 3 seconds...${NC}"
    sleep 3
    
    # Run tests sequentially (not parallel) to avoid overwhelming
    # First server
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}Starting test on $SERVER1...${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    run_test_on_server "$SERVER1" "$SERVER1_URL" "$VIDEO_FILE" "$TASK_COUNT" | tee "$RESULTS_DIR/${SERVER1}-output.log"
    local result1=$?
    
    echo ""
    echo -e "${CYAN}⏸️  Waiting 10 seconds before starting next server...${NC}"
    sleep 10
    
    # Second server
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}Starting test on $SERVER2...${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    run_test_on_server "$SERVER2" "$SERVER2_URL" "$VIDEO_FILE" "$TASK_COUNT" | tee "$RESULTS_DIR/${SERVER2}-output.log"
    local result2=$?
    
    if [ $result1 -ne 0 ] || [ $result2 -ne 0 ]; then
        echo -e "${YELLOW}⚠️  One or both tests had errors, but continuing to generate summary...${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Both tests completed!${NC}"
    echo ""
    
    # Generate summary
    generate_summary
    
    echo ""
    echo -e "${GREEN}✅ Full test completed!${NC}"
    echo -e "${CYAN}📁 All results in: $RESULTS_DIR${NC}"
    echo ""
}

# Run main
main

