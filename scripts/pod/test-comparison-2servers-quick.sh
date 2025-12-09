#!/bin/bash
# Script สำหรับทดสอบและเปรียบเทียบ Transcription Performance ระหว่าง 2 Servers (Quick Test)
# ใช้ API /api/control/test เพื่อให้เหมือนกับ concurrency-monitor.html
#
# วิธีใช้งาน:
#   bash scripts/pod/test-comparison-2servers-quick.sh [video_file] [count]
#
# ตัวอย่าง:
#   bash scripts/pod/test-comparison-2servers-quick.sh "v10-1.mp4" 10

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SERVER1="4080s"
SERVER2="4000-ada"
SERVER1_URL="http://80.15.7.37:41314"
SERVER2_URL="http://87.197.119.40:41314"
VIDEO_FILE="${1:-v10-1.mp4}"
TASK_COUNT="${2:-10}"

# Results storage
RESULTS_DIR="/tmp/transcription-comparison-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🧪 Quick Transcription Comparison Test                      ║"
echo "║  ใช้ API /api/control/test เหมือน concurrency-monitor.html    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Server 1: $SERVER1 ($SERVER1_URL)"
echo "  Server 2: $SERVER2 ($SERVER2_URL)"
echo "  Video File: $VIDEO_FILE"
echo "  Task Count: $TASK_COUNT"
echo "  Results Dir: $RESULTS_DIR"
echo ""

# Function to test server using /api/control/test endpoint
test_server_with_control_api() {
    local server=$1
    local server_url=$2
    local video_file=$3
    local count=$4
    local results_file="$RESULTS_DIR/${server}-results.json"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🧪 Testing: $server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Pre-flight check
    echo -e "${CYAN}📡 Checking service...${NC}"
    if curl -sf "$server_url/health" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Service is running${NC}"
    else
        echo -e "${RED}   ❌ Service is not responding${NC}"
        return 1
    fi
    echo ""
    
    # Use /api/control/test endpoint (same as concurrency-monitor.html)
    echo -e "${CYAN}📤 Sending $count tasks via /api/control/test...${NC}"
    local start_time=$(date +%s)
    
    local response=$(curl -s -X POST "$server_url/api/control/test" \
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
    
    # Extract task IDs from response
    local task_ids=()
    if echo "$response" | grep -q "task_ids"; then
        # Parse JSON response
        if command -v jq > /dev/null 2>&1; then
            task_ids=($(echo "$response" | jq -r '.task_ids[]?' 2>/dev/null || echo ""))
        else
            # Fallback: extract manually using grep
            task_ids=($(echo "$response" | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' || echo ""))
        fi
        
        if [ ${#task_ids[@]} -eq 0 ]; then
            # Try alternative parsing - extract from task_ids array
            task_ids=($(echo "$response" | grep -o '"task_ids":\s*\[[^]]*\]' | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' || echo ""))
        fi
    else
        # Try to extract UUIDs directly
        task_ids=($(echo "$response" | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' || echo ""))
    fi
    
    if [ ${#task_ids[@]} -eq 0 ]; then
        echo -e "${RED}   ❌ Failed to get task IDs from response${NC}"
        echo "      Response: $(echo "$response" | head -c 500)"
        return 1
    fi
    
    echo -e "${GREEN}   ✅ Created ${#task_ids[@]} tasks${NC}"
    for i in "${!task_ids[@]}"; do
        echo "      Task $((i+1)): ${task_ids[$i]}"
    done
    echo ""
    
    # Wait for completion
    echo -e "${CYAN}⏳ Waiting for completion...${NC}"
    local completed=0
    local success_count=0
    local fail_count=0
    local max_wait=1800  # 30 minutes
    local elapsed=0
    local task_statuses=()
    local task_results=()
    
    # Initialize task statuses
    for i in "${!task_ids[@]}"; do
        task_statuses[$i]="pending"
    done
    
    while [ $completed -lt ${#task_ids[@]} ] && [ $elapsed -lt $max_wait ]; do
        sleep 5
        elapsed=$((elapsed + 5))
        completed=0
        
        for i in "${!task_ids[@]}"; do
            local task_id="${task_ids[$i]}"
            
            # Skip if already completed
            if [ "${task_statuses[$i]}" = "completed" ] || [ "${task_statuses[$i]}" = "failed" ]; then
                completed=$((completed + 1))
                continue
            fi
            
            # Check status
            local status_response=$(curl -s "$server_url/transcribe/$task_id" 2>/dev/null || echo "{}")
            local status=$(echo "$status_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
            
            if [ "$status" = "completed" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                task_statuses[$i]="completed"
                task_results[$i]="$status_response"
                success_count=$((success_count + 1))
                completed=$((completed + 1))
                
                # Check if has text
                local has_text=$(echo "$status_response" | grep -o '"full_text"[^,}]*' | grep -v '""' | grep -v 'null' || echo "")
                if [ -n "$has_text" ]; then
                    echo -e "${GREEN}   ✅ Task $((i+1)) completed with text in ${duration}s${NC}"
                else
                    echo -e "${YELLOW}   ⚠️  Task $((i+1)) completed but no text in ${duration}s${NC}"
                fi
            elif [ "$status" = "failed" ] || [ "$status" = "error" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                task_statuses[$i]="failed"
                task_results[$i]="$status_response"
                fail_count=$((fail_count + 1))
                completed=$((completed + 1))
                
                local error_msg=$(echo "$status_response" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4 || echo "Unknown error")
                echo -e "${RED}   ❌ Task $((i+1)) failed: $error_msg${NC}"
            fi
        done
        
        if [ $completed -lt ${#task_ids[@]} ]; then
            echo "   Progress: $completed/${#task_ids[@]} completed (${elapsed}s elapsed)"
        fi
    done
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    # Save results
    echo "{" > "$results_file"
    echo "  \"server\": \"$server\"," >> "$results_file"
    echo "  \"server_url\": \"$server_url\"," >> "$results_file"
    echo "  \"video_file\": \"$video_file\"," >> "$results_file"
    echo "  \"test_start\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"test_end\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"task_count\": ${#task_ids[@]}," >> "$results_file"
    echo "  \"total_duration\": $total_duration," >> "$results_file"
    echo "  \"task_ids\": [" >> "$results_file"
    for i in "${!task_ids[@]}"; do
        if [ $i -gt 0 ]; then
            echo "," >> "$results_file"
        fi
        echo -n "    \"${task_ids[$i]}\"" >> "$results_file"
    done
    echo "" >> "$results_file"
    echo "  ]," >> "$results_file"
    echo "  \"summary\": {" >> "$results_file"
    echo "    \"total_tasks\": ${#task_ids[@]}," >> "$results_file"
    echo "    \"success_count\": $success_count," >> "$results_file"
    echo "    \"fail_count\": $fail_count," >> "$results_file"
    if [ ${#task_ids[@]} -gt 0 ]; then
        echo "    \"success_rate\": $(echo "scale=2; $success_count * 100 / ${#task_ids[@]}" | bc)," >> "$results_file"
    else
        echo "    \"success_rate\": 0," >> "$results_file"
    fi
    echo "    \"total_duration\": $total_duration" >> "$results_file"
    if [ $success_count -gt 0 ]; then
        echo "    ,\"avg_time\": $(echo "scale=2; $total_duration / $success_count" | bc)" >> "$results_file"
    else
        echo "    ,\"avg_time\": 0" >> "$results_file"
    fi
    if [ $total_duration -gt 0 ]; then
        echo "    ,\"throughput\": $(echo "scale=2; $success_count * 3600 / $total_duration" | bc)" >> "$results_file"
    else
        echo "    ,\"throughput\": 0" >> "$results_file"
    fi
    echo "  }," >> "$results_file"
    echo "  \"tasks\": [" >> "$results_file"
    for i in "${!task_ids[@]}"; do
        if [ $i -gt 0 ]; then
            echo "," >> "$results_file"
        fi
        echo "    {" >> "$results_file"
        echo "      \"task_id\": \"${task_ids[$i]}\"," >> "$results_file"
        echo "      \"status\": \"${task_statuses[$i]}\"," >> "$results_file"
        echo "      \"result\": ${task_results[$i]:-{}}" >> "$results_file"
        echo -n "    }" >> "$results_file"
    done
    echo "" >> "$results_file"
    echo "  ]" >> "$results_file"
    echo "}" >> "$results_file"
    
    echo ""
    echo -e "${GREEN}✅ Test completed for $server${NC}"
    echo "  Success: $success_count/${#task_ids[@]}"
    echo "  Failed: $fail_count/${#task_ids[@]}"
    echo "  Total time: ${total_duration}s"
    if [ $success_count -gt 0 ]; then
        echo "  Avg time: $(echo "scale=2; $total_duration / $success_count" | bc)s"
    fi
    echo ""
}

# Compare results
compare_results() {
    local file1="$RESULTS_DIR/${SERVER1}-results.json"
    local file2="$RESULTS_DIR/${SERVER2}-results.json"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📊 Comparison Results${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [ ! -f "$file1" ] || [ ! -f "$file2" ]; then
        echo -e "${RED}❌ Results files not found${NC}"
        return 1
    fi
    
    # Extract summary (use jq if available, otherwise use grep)
    if command -v jq > /dev/null 2>&1; then
        local s1_success=$(jq -r '.summary.success_count' "$file1")
        local s1_fail=$(jq -r '.summary.fail_count' "$file1")
        local s1_avg=$(jq -r '.summary.avg_time' "$file1")
        local s1_throughput=$(jq -r '.summary.throughput' "$file1")
        
        local s2_success=$(jq -r '.summary.success_count' "$file2")
        local s2_fail=$(jq -r '.summary.fail_count' "$file2")
        local s2_avg=$(jq -r '.summary.avg_time' "$file2")
        local s2_throughput=$(jq -r '.summary.throughput' "$file2")
    else
        # Fallback: use grep
        local s1_success=$(grep -o '"success_count": [0-9]*' "$file1" | grep -o '[0-9]*' || echo "0")
        local s1_fail=$(grep -o '"fail_count": [0-9]*' "$file1" | grep -o '[0-9]*' || echo "0")
        local s1_avg=$(grep -o '"avg_time": [0-9.]*' "$file1" | grep -o '[0-9.]*' || echo "0")
        local s1_throughput=$(grep -o '"throughput": [0-9.]*' "$file1" | grep -o '[0-9.]*' || echo "0")
        
        local s2_success=$(grep -o '"success_count": [0-9]*' "$file2" | grep -o '[0-9]*' || echo "0")
        local s2_fail=$(grep -o '"fail_count": [0-9]*' "$file2" | grep -o '[0-9]*' || echo "0")
        local s2_avg=$(grep -o '"avg_time": [0-9.]*' "$file2" | grep -o '[0-9.]*' || echo "0")
        local s2_throughput=$(grep -o '"throughput": [0-9.]*' "$file2" | grep -o '[0-9.]*' || echo "0")
    fi
    
    # Print comparison table
    printf "%-25s %20s %20s\n" "Metric" "$SERVER1" "$SERVER2"
    echo "────────────────────────────────────────────────────────────────────────────────────"
    printf "%-25s %20s %20s\n" "Success Count" "$s1_success" "$s2_success"
    printf "%-25s %20s %20s\n" "Fail Count" "$s1_fail" "$s2_fail"
    printf "%-25s %20.2fs %20.2fs\n" "Avg Time" "$s1_avg" "$s2_avg"
    printf "%-25s %20.2f/hr %20.2f/hr\n" "Throughput" "$s1_throughput" "$s2_throughput"
    
    echo ""
    echo -e "${CYAN}📁 Results saved to: $RESULTS_DIR${NC}"
    echo ""
    
    # Determine winner
    if [ "$s1_fail" = "0" ] && [ "$s2_fail" = "0" ]; then
        if (( $(echo "$s1_avg < $s2_avg" | bc -l) )); then
            echo -e "${GREEN}🏆 Winner: $SERVER1 (Faster avg time, No failures)${NC}"
        elif (( $(echo "$s2_avg < $s1_avg" | bc -l) )); then
            echo -e "${GREEN}🏆 Winner: $SERVER2 (Faster avg time, No failures)${NC}"
        else
            echo -e "${GREEN}🤝 Perfect Tie: Both servers completed all tasks with similar performance!${NC}"
        fi
    elif [ "$s1_fail" = "0" ] && [ "$s2_fail" -gt 0 ]; then
        echo -e "${GREEN}🏆 Winner: $SERVER1 (No failures vs $s2_fail failures)${NC}"
    elif [ "$s2_fail" = "0" ] && [ "$s1_fail" -gt 0 ]; then
        echo -e "${GREEN}🏆 Winner: $SERVER2 (No failures vs $s1_fail failures)${NC}"
    else
        if [ "$s1_success" -gt "$s2_success" ]; then
            echo -e "${GREEN}🏆 Winner: $SERVER1 (More successful tasks)${NC}"
        elif [ "$s2_success" -gt "$s1_success" ]; then
            echo -e "${GREEN}🏆 Winner: $SERVER2 (More successful tasks)${NC}"
        else
            echo -e "${YELLOW}🤝 Tie: Both servers had similar results${NC}"
        fi
    fi
}

# Main execution
main() {
    # Check dependencies
    if ! command -v bc > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  bc not found. Installing...${NC}"
        apt-get update -qq > /dev/null 2>&1 && apt-get install -y -qq bc > /dev/null 2>&1 || {
            echo -e "${RED}❌ Cannot install bc. Please install manually${NC}"
            exit 1
        }
    fi
    
    echo -e "${YELLOW}⚠️  This will test transcription on both servers${NC}"
    echo -e "${YELLOW}   Using /api/control/test endpoint (same as concurrency-monitor.html)${NC}"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    # Run tests
    test_server_with_control_api "$SERVER1" "$SERVER1_URL" "$VIDEO_FILE" "$TASK_COUNT"
    sleep 10  # Cooldown between tests
    test_server_with_control_api "$SERVER2" "$SERVER2_URL" "$VIDEO_FILE" "$TASK_COUNT"
    
    # Compare results
    compare_results
    
    echo ""
    echo -e "${CYAN}💡 Tip: View detailed results in: $RESULTS_DIR${NC}"
}

# Run main
main

