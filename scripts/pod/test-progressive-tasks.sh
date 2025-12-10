#!/bin/bash
# Script สำหรับทดสอบ Progressive Tasks: 1, 2, 5, 10 tasks
# Usage: bash test-progressive-tasks.sh <video_file> <server_alias>

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VIDEO_FILE="${1:-v10-1.mp4}"
SERVER_ALIAS="${2:-4080s}"
PROJECT_DIR="/workspace/transcription-service"
BENCHMARK_DIR="$PROJECT_DIR/docs/RunPod-Z2/Benchmark"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
SUMMARY_FILE="$BENCHMARK_DIR/${SERVER_ALIAS}-progressive-${TIMESTAMP}.md"

# Test counts
TEST_COUNTS=(1 2 5 10)

# API URL - use localhost if running on server, external URL if remote
if [ -z "$SSH_CONNECTION" ] && [ "$(hostname)" != "${SERVER_ALIAS}" ]; then
    case "$SERVER_ALIAS" in
        4080s)
            API_URL="http://80.15.7.37:41314"
            ;;
        4000-ada)
            API_URL="http://87.197.119.40:41314"
            ;;
        *)
            API_URL="http://localhost:8010"
            ;;
    esac
else
    API_URL="http://localhost:8010"
fi

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🧪 Progressive Tasks Test - $SERVER_ALIAS                           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Video File: $VIDEO_FILE"
echo "  Server: $SERVER_ALIAS"
echo "  API URL: $API_URL"
echo "  Test Sequence: ${TEST_COUNTS[@]} tasks"
echo ""

# Function to calculate using Python or awk
calc() {
    if command -v python3 &> /dev/null; then
        python3 -c "print(f'{($1):.2f}')"
    else
        awk "BEGIN {printf \"%.2f\", $1}"
    fi
}

# Function to run a single test
run_single_test() {
    local task_count=$1
    local test_num=$2
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}📊 Test #$test_num: $task_count Task(s)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check service health
    if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
        echo -e "${RED}❌ Service is not healthy at $API_URL${NC}"
        return 1
    fi
    echo -e "${GREEN}✅ Service is healthy${NC}"
    
    # Create tasks
    echo -e "${YELLOW}📤 Creating $task_count task(s)...${NC}"
    local start_time=$(date +%s)
    local response=$(curl -s -X POST "$API_URL/api/control/test" \
        -H "Content-Type: application/json" \
        -d "{\"video_file\": \"$VIDEO_FILE\", \"count\": $task_count}" 2>/dev/null || echo "{}")
    
    if [ "$response" = "{}" ] || [ -z "$response" ]; then
        echo -e "${RED}❌ Failed to create tasks${NC}"
        return 1
    fi
    
    # Extract task IDs
    local task_ids=()
    if command -v jq &> /dev/null; then
        task_ids=($(echo "$response" | jq -r '.task_ids[]?' 2>/dev/null || echo ""))
    else
        # Fallback: extract from JSON manually
        task_ids=($(echo "$response" | grep -oE '"task_ids"\s*:\s*\[[^]]*\]' | grep -oE '[a-f0-9-]{36}' || echo ""))
    fi
    
    if [ ${#task_ids[@]} -eq 0 ]; then
        echo -e "${RED}❌ Failed to get task IDs${NC}"
        echo "Response: $response"
        return 1
    fi
    
    echo -e "${GREEN}✅ Created ${#task_ids[@]} task(s):${NC}"
    for i in "${!task_ids[@]}"; do
        echo "  $((i+1)). ${task_ids[$i]}"
    done
    
    # Wait for tasks to complete
    echo -e "${YELLOW}⏳ Waiting for tasks to complete...${NC}"
    local completed=0
    local failed=0
    local max_wait_time=3600  # 1 hour max
    local check_interval=2
    local elapsed=0
    
    declare -A task_start_times
    declare -A task_end_times
    declare -A task_durations
    declare -A task_statuses
    declare -A task_texts
    declare -A task_errors
    
    # Initialize task start times
    for task_id in "${task_ids[@]}"; do
        task_start_times["$task_id"]=$start_time
        task_statuses["$task_id"]="pending"
    done
    
    while [ $elapsed -lt $max_wait_time ] && [ $((completed + failed)) -lt ${#task_ids[@]} ]; do
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        
        for task_id in "${task_ids[@]}"; do
            if [ "${task_statuses[$task_id]}" != "completed" ] && [ "${task_statuses[$task_id]}" != "failed" ]; then
                # Try multiple endpoints
                local status_response=$(curl -s "$API_URL/api/progress/transcription/$task_id" 2>/dev/null || echo "")
                if [ -z "$status_response" ] || [ "$status_response" = "{}" ]; then
                    status_response=$(curl -s "$API_URL/transcribe/$task_id" 2>/dev/null || echo "")
                fi
                if [ -z "$status_response" ] || [ "$status_response" = "{}" ]; then
                    status_response=$(curl -s "$API_URL/api/history/transcription/$task_id" 2>/dev/null || echo "")
                fi
                
                if [ -n "$status_response" ] && [ "$status_response" != "{}" ]; then
                    local status="unknown"
                    if command -v jq &> /dev/null; then
                        status=$(echo "$status_response" | jq -r '.status // .task_status // "unknown"' 2>/dev/null || echo "unknown")
                    else
                        status=$(echo "$status_response" | grep -oE '"status"\s*:\s*"[^"]*"' | head -1 | grep -oE '"[^"]*"' | tr -d '"' || echo "unknown")
                    fi
                    
                    if [ "$status" = "completed" ] || [ "$status" = "success" ]; then
                        task_statuses["$task_id"]="completed"
                        task_end_times["$task_id"]=$(date +%s)
                        local start=${task_start_times[$task_id]}
                        local end=${task_end_times[$task_id]}
                        task_durations["$task_id"]=$((end - start))
                        completed=$((completed + 1))
                        
                        # Extract text
                        if command -v jq &> /dev/null; then
                            task_texts["$task_id"]=$(echo "$status_response" | jq -r '.corrected_text // .full_text // (.chunks[]?.text // empty) | join(" ")' 2>/dev/null || echo "")
                        fi
                    elif [ "$status" = "failed" ] || [ "$status" = "error" ]; then
                        task_statuses["$task_id"]="failed"
                        task_end_times["$task_id"]=$(date +%s)
                        local start=${task_start_times[$task_id]}
                        local end=${task_end_times[$task_id]}
                        task_durations["$task_id"]=$((end - start))
                        failed=$((failed + 1))
                        
                        # Extract error
                        if command -v jq &> /dev/null; then
                            task_errors["$task_id"]=$(echo "$status_response" | jq -r '.error_message // .error // "Unknown error"' 2>/dev/null || echo "Unknown error")
                        fi
                    fi
                fi
            fi
        done
        
        # Show progress
        if [ $((elapsed % 10)) -eq 0 ]; then
            echo -e "${YELLOW}  Progress: ${completed}/${#task_ids[@]} completed, ${failed} failed (${elapsed}s elapsed)${NC}"
        fi
    done
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    echo ""
    echo -e "${GREEN}✅ Test completed:${NC}"
    echo "  Total Duration: ${total_duration}s"
    echo "  Completed: $completed/${#task_ids[@]}"
    echo "  Failed: $failed/${#task_ids[@]}"
    
    # Calculate statistics
    local total_duration_sum=0
    local completed_count=0
    local min_duration=999999
    local max_duration=0
    
    for task_id in "${task_ids[@]}"; do
        if [ -n "${task_durations[$task_id]}" ] && [ "${task_statuses[$task_id]}" = "completed" ]; then
            local dur=${task_durations[$task_id]}
            total_duration_sum=$((total_duration_sum + dur))
            completed_count=$((completed_count + 1))
            if [ $dur -lt $min_duration ]; then
                min_duration=$dur
            fi
            if [ $dur -gt $max_duration ]; then
                max_duration=$dur
            fi
        fi
    done
    
    local avg_duration=0
    if [ $completed_count -gt 0 ]; then
        avg_duration=$((total_duration_sum / completed_count))
    fi
    
    # Return results as JSON-like output
    echo "RESULTS_START"
    echo "{\"task_count\": $task_count, \"total_duration\": $total_duration, \"completed\": $completed, \"failed\": $failed, \"min_duration\": $min_duration, \"max_duration\": $max_duration, \"avg_duration\": $avg_duration, \"task_ids\": [$(printf '"%s",' "${task_ids[@]}" | sed 's/,$//')]}"
    echo "RESULTS_END"
    
    # Add a small delay between tests
    if [ $test_num -lt ${#TEST_COUNTS[@]} ]; then
        echo -e "${YELLOW}⏸️  Waiting 5 seconds before next test...${NC}"
        sleep 5
    fi
}

# Main execution
mkdir -p "$BENCHMARK_DIR"

echo -e "${BLUE}Starting progressive tests...${NC}"
echo ""

# Store all results
declare -a all_results

for i in "${!TEST_COUNTS[@]}"; do
    test_count=${TEST_COUNTS[$i]}
    test_num=$((i + 1))
    
    result=$(run_single_test $test_count $test_num 2>&1)
    echo "$result"
    
    # Extract results if available
    if echo "$result" | grep -q "RESULTS_START"; then
        result_json=$(echo "$result" | sed -n '/RESULTS_START/,/RESULTS_END/p' | sed '1d;$d')
        all_results+=("$result_json")
    fi
done

# Generate summary markdown
echo ""
echo -e "${GREEN}📝 Generating summary report...${NC}"

cat > "$SUMMARY_FILE" << EOF
# Progressive Tasks Test Report - $SERVER_ALIAS

**Date**: $(date '+%Y-%m-%d %H:%M:%S')  
**Video File**: \`$VIDEO_FILE\`  
**Server**: $SERVER_ALIAS

---

## 📊 Summary

| Task Count | Total Duration (s) | Completed | Failed | Min Duration (s) | Max Duration (s) | Avg Duration (s) |
|------------|-------------------|-----------|--------|------------------|------------------|------------------|
EOF

for result_json in "${all_results[@]}"; do
    if command -v jq &> /dev/null; then
        task_count=$(echo "$result_json" | jq -r '.task_count')
        total_duration=$(echo "$result_json" | jq -r '.total_duration')
        completed=$(echo "$result_json" | jq -r '.completed')
        failed=$(echo "$result_json" | jq -r '.failed')
        min_duration=$(echo "$result_json" | jq -r '.min_duration')
        max_duration=$(echo "$result_json" | jq -r '.max_duration')
        avg_duration=$(echo "$result_json" | jq -r '.avg_duration')
        
        echo "| $task_count | $total_duration | $completed | $failed | $min_duration | $max_duration | $avg_duration |" >> "$SUMMARY_FILE"
    fi
done

cat >> "$SUMMARY_FILE" << EOF

---

## 📈 Performance Analysis

### Throughput (Tasks per Second)
EOF

for result_json in "${all_results[@]}"; do
    if command -v jq &> /dev/null; then
        task_count=$(echo "$result_json" | jq -r '.task_count')
        total_duration=$(echo "$result_json" | jq -r '.total_duration')
        completed=$(echo "$result_json" | jq -r '.completed')
        
        if [ "$total_duration" != "0" ] && [ "$completed" != "0" ]; then
            throughput=$(echo "scale=4; $completed / $total_duration" | bc 2>/dev/null || echo "$completed / $total_duration")
            echo "- **${task_count} tasks**: $throughput tasks/sec (${completed} completed in ${total_duration}s)" >> "$SUMMARY_FILE"
        fi
    fi
done

cat >> "$SUMMARY_FILE" << EOF

---

## 🔍 Detailed Results

EOF

for result_json in "${all_results[@]}"; do
    if command -v jq &> /dev/null; then
        task_count=$(echo "$result_json" | jq -r '.task_count')
        echo "### $task_count Task(s)" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
        echo "\`\`\`json" >> "$SUMMARY_FILE"
        echo "$result_json" | jq . >> "$SUMMARY_FILE" 2>/dev/null || echo "$result_json" >> "$SUMMARY_FILE"
        echo "\`\`\`" >> "$SUMMARY_FILE"
        echo "" >> "$SUMMARY_FILE"
    fi
done

echo -e "${GREEN}✅ Summary report saved to: $SUMMARY_FILE${NC}"
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ✅ All Tests Completed                                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

