#!/bin/bash
# Script สำหรับทดสอบและเปรียบเทียบ Transcription Performance ระหว่าง 2 Servers
# รองรับการทดสอบ 10 วิดีโอ และเปรียบเทียบ performance, stability
#
# วิธีใช้งาน:
#   bash scripts/pod/test-comparison-2servers.sh [video_url] [count]
#
# ตัวอย่าง:
#   bash scripts/pod/test-comparison-2servers.sh "http://localhost:5182/api/files/video1.mp4" 10

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
VIDEO_URL="${1:-http://localhost:5182/api/files/test-video.mp4}"
VIDEO_COUNT="${2:-10}"

# Results storage
RESULTS_DIR="/tmp/transcription-comparison-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🧪 Transcription Performance Comparison Test                ║"
echo "║  Server 1: $SERVER1 ($SERVER1_URL)                          ║"
echo "║  Server 2: $SERVER2 ($SERVER2_URL)                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Video URL: $VIDEO_URL"
echo "  Video Count: $VIDEO_COUNT"
echo "  Results Dir: $RESULTS_DIR"
echo ""

# Function to send transcription task
send_task() {
    local url=$1
    local video_url=$2
    local task_num=$3
    
    # Try file_path first (more reliable for local files)
    # If video_url is a local path, use file_path, otherwise use file_url
    local use_file_path=false
    if [[ "$video_url" == /* ]] || [[ "$video_url" == .* ]] || [[ ! "$video_url" == http* ]]; then
        use_file_path=true
    fi
    
    local request_body=""
    if [ "$use_file_path" = true ]; then
        request_body="{
            \"file_path\": \"$video_url\",
            \"file_name\": \"test-video-$task_num.mp4\",
            \"language\": \"th\",
            \"model_size\": \"medium\",
            \"use_chunking\": false,
            \"callback_url\": \"http://localhost:5173/api/transcription/webhook/completed\",
            \"job_id\": $task_num,
            \"user_id\": \"test-user\"
        }"
    else
        request_body="{
            \"file_url\": \"$video_url\",
            \"file_name\": \"test-video-$task_num.mp4\",
            \"language\": \"th\",
            \"model_size\": \"medium\",
            \"use_chunking\": false,
            \"callback_url\": \"http://localhost:5173/api/transcription/webhook/completed\",
            \"job_id\": $task_num,
            \"user_id\": \"test-user\"
        }"
    fi
    
    local response=$(curl -s -X POST "$url/transcribe/" \
        -H "Content-Type: application/json" \
        -d "$request_body" 2>&1)
    
    # Check for errors in response
    if echo "$response" | grep -q '"detail"\|"error"\|"message"'; then
        echo "ERROR: $response" >&2
        echo ""
    else
        echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo ""
    fi
}

# Function to check task status
check_status() {
    local url=$1
    local task_id=$2
    
    local response=$(curl -s "$url/progress/$task_id" 2>/dev/null || echo "")
    echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown"
}

# Function to get result
get_result() {
    local url=$1
    local task_id=$2
    
    curl -s "$url/result/$task_id" 2>/dev/null || echo "{}"
}

# Function to run test on server
run_test() {
    local server=$1
    local server_url=$2
    local video_url=$3
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
        echo "      Please check: ssh $server 'bash /workspace/transcription-service/scripts/pod/check-service-status.sh'"
        return 1
    fi
    echo ""
    
    # Initialize results
    echo "{" > "$results_file"
    echo "  \"server\": \"$server\"," >> "$results_file"
    echo "  \"server_url\": \"$server_url\"," >> "$results_file"
    echo "  \"test_start\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"video_count\": $count," >> "$results_file"
    echo "  \"tasks\": [" >> "$results_file"
    
    local task_ids=()
    local start_times=()
    local success_count=0
    local fail_count=0
    local total_time=0
    
    # Send tasks
    echo -e "${CYAN}📤 Sending $count tasks...${NC}"
    for i in $(seq 1 $count); do
        local task_id=$(send_task "$server_url" "$video_url" "$i")
        local start_time=$(date +%s)
        
        if [ -n "$task_id" ]; then
            task_ids+=("$task_id")
            start_times+=("$start_time")
            echo -e "${GREEN}   ✅ Task $i: $task_id${NC}"
        else
            echo -e "${RED}   ❌ Task $i: Failed to send${NC}"
            fail_count=$((fail_count + 1))
        fi
        
        sleep 0.5
    done
    
    echo ""
    echo -e "${CYAN}⏳ Waiting for completion...${NC}"
    
    # Wait for completion
    local completed=0
    local max_wait=1800  # 30 minutes
    local elapsed=0
    
    while [ $completed -lt ${#task_ids[@]} ] && [ $elapsed -lt $max_wait ]; do
        sleep 5
        elapsed=$((elapsed + 5))
        completed=0
        
        for i in "${!task_ids[@]}"; do
            local task_id="${task_ids[$i]}"
            
            # Skip if already processed
            if echo "${task_ids[@]:0:$i}" | grep -q "$task_id"; then
                continue
            fi
            
            local status=$(check_status "$server_url" "$task_id")
            
            if [ "$status" = "completed" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_times[$i]))
                total_time=$((total_time + duration))
                success_count=$((success_count + 1))
                completed=$((completed + 1))
                
                # Get full result with error details if any
                local result=$(get_result "$server_url" "$task_id")
                local has_text=$(echo "$result" | grep -o '"full_text"[^,}]*' | grep -v '""' | grep -v 'null' || echo "")
                
                # Append to results
                if [ $success_count -gt 1 ]; then
                    echo "," >> "$results_file"
                fi
                echo "    {" >> "$results_file"
                echo "      \"task_id\": \"$task_id\"," >> "$results_file"
                echo "      \"duration\": $duration," >> "$results_file"
                echo "      \"status\": \"completed\"," >> "$results_file"
                if [ -n "$has_text" ]; then
                    echo "      \"has_text\": true," >> "$results_file"
                else
                    echo "      \"has_text\": false," >> "$results_file"
                    echo "      \"warning\": \"No text found in result\"," >> "$results_file"
                fi
                echo "      \"result\": $result" >> "$results_file"
                echo -n "    }" >> "$results_file"
                
                if [ -n "$has_text" ]; then
                    echo -e "${GREEN}   ✅ Task $((i+1)) completed in ${duration}s${NC}"
                else
                    echo -e "${YELLOW}   ⚠️  Task $((i+1)) completed but no text in ${duration}s${NC}"
                fi
                
                # Mark as processed
                task_ids[$i]=""
            elif [ "$status" = "failed" ] || [ "$status" = "error" ]; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_times[$i]))
                fail_count=$((fail_count + 1))
                completed=$((completed + 1))
                
                # Get error details
                local error_result=$(get_result "$server_url" "$task_id")
                local error_msg=$(echo "$error_result" | grep -o '"error_message":"[^"]*"' | cut -d'"' -f4 || echo "Unknown error")
                
                # Append to results
                if [ $((success_count + fail_count)) -gt 1 ]; then
                    echo "," >> "$results_file"
                fi
                echo "    {" >> "$results_file"
                echo "      \"task_id\": \"$task_id\"," >> "$results_file"
                echo "      \"duration\": $duration," >> "$results_file"
                echo "      \"status\": \"failed\"," >> "$results_file"
                echo "      \"error_message\": \"$error_msg\"," >> "$results_file"
                echo "      \"result\": $error_result" >> "$results_file"
                echo -n "    }" >> "$results_file"
                
                echo -e "${RED}   ❌ Task $((i+1)) failed: $error_msg${NC}"
                
                # Mark as processed
                task_ids[$i]=""
            fi
        done
        
        if [ $completed -lt ${#task_ids[@]} ]; then
            echo "   Progress: $completed/${#task_ids[@]} completed (${elapsed}s elapsed)"
        fi
    done
    
    # Finalize results
    echo "" >> "$results_file"
    echo "  ]," >> "$results_file"
    echo "  \"test_end\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"summary\": {" >> "$results_file"
    echo "    \"total_tasks\": ${#task_ids[@]}," >> "$results_file"
    echo "    \"success_count\": $success_count," >> "$results_file"
    echo "    \"fail_count\": $fail_count," >> "$results_file"
    if [ ${#task_ids[@]} -gt 0 ]; then
        echo "    \"success_rate\": $(echo "scale=2; $success_count * 100 / ${#task_ids[@]}" | bc)," >> "$results_file"
    else
        echo "    \"success_rate\": 0," >> "$results_file"
    fi
    echo "    \"total_time\": $total_time" >> "$results_file"
    if [ $success_count -gt 0 ]; then
        echo "    ,\"avg_time\": $(echo "scale=2; $total_time / $success_count" | bc)" >> "$results_file"
    else
        echo "    ,\"avg_time\": 0" >> "$results_file"
    fi
    if [ $total_time -gt 0 ]; then
        echo "    ,\"throughput\": $(echo "scale=2; $success_count * 3600 / $total_time" | bc)" >> "$results_file"
    else
        echo "    ,\"throughput\": 0" >> "$results_file"
    fi
    echo "  }" >> "$results_file"
    echo "}" >> "$results_file"
    
    echo ""
    echo -e "${GREEN}✅ Test completed for $server${NC}"
    echo "  Success: $success_count/${#task_ids[@]}"
    echo "  Total time: ${total_time}s"
    if [ $success_count -gt 0 ]; then
        echo "  Avg time: $(echo "scale=2; $total_time / $success_count" | bc)s"
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
        # Fallback: use grep and basic parsing
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
    if (( $(echo "$s1_success > $s2_success" | bc -l) )); then
        echo -e "${GREEN}🏆 Winner: $SERVER1 (More successful tasks)${NC}"
    elif (( $(echo "$s2_success > $s1_success" | bc -l) )); then
        echo -e "${GREEN}🏆 Winner: $SERVER2 (More successful tasks)${NC}"
    elif (( $(echo "$s1_avg < $s2_avg" | bc -l) )); then
        echo -e "${GREEN}🏆 Winner: $SERVER1 (Faster avg time)${NC}"
    elif (( $(echo "$s2_avg < $s1_avg" | bc -l) )); then
        echo -e "${GREEN}🏆 Winner: $SERVER2 (Faster avg time)${NC}"
    else
        echo -e "${YELLOW}🤝 Tie: Both servers performed similarly${NC}"
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
    echo -e "${YELLOW}   Make sure both services are accessible${NC}"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    # Run tests
    run_test "$SERVER1" "$SERVER1_URL" "$VIDEO_URL" "$VIDEO_COUNT"
    sleep 10  # Cooldown between tests
    run_test "$SERVER2" "$SERVER2_URL" "$VIDEO_URL" "$VIDEO_COUNT"
    
    # Compare results
    compare_results
}

# Run main
main

