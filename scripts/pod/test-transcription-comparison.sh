#!/bin/bash
# Script สำหรับทดสอบและเปรียบเทียบ Transcription Performance ระหว่าง 2 Servers
#
# วิธีใช้งาน:
#   bash scripts/pod/test-transcription-comparison.sh [server1] [server2] [video_count]
#
# ตัวอย่าง:
#   bash scripts/pod/test-transcription-comparison.sh 4080s 4000-ada 10

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SERVER1="${1:-4080s}"
SERVER2="${2:-4000-ada}"
VIDEO_COUNT="${3:-10}"
VIDEO_URL="${4:-http://localhost:5182/api/files/test-video}"

# Test video URLs (ตัวอย่าง - ปรับตามจริง)
TEST_VIDEOS=(
    "http://localhost:5182/api/files/video1.mp4"
    "http://localhost:5182/api/files/video2.mp4"
    "http://localhost:5182/api/files/video3.mp4"
    "http://localhost:5182/api/files/video4.mp4"
    "http://localhost:5182/api/files/video5.mp4"
    "http://localhost:5182/api/files/video6.mp4"
    "http://localhost:5182/api/files/video7.mp4"
    "http://localhost:5182/api/files/video8.mp4"
    "http://localhost:5182/api/files/video9.mp4"
    "http://localhost:5182/api/files/video10.mp4"
)

# Results storage
RESULTS_DIR="/tmp/transcription-comparison-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🧪 Transcription Performance Comparison Test                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Server 1: $SERVER1"
echo "  Server 2: $SERVER2"
echo "  Video Count: $VIDEO_COUNT"
echo "  Results Dir: $RESULTS_DIR"
echo ""

# Function to get transcription service URL
get_transcription_url() {
    local server=$1
    case $server in
        "4080s")
            echo "http://80.15.7.37:41314"
            ;;
        "4000-ada")
            echo "http://87.197.119.40:41314"
            ;;
        *)
            echo "http://localhost:8001"
            ;;
    esac
}

# Function to check SSH connection
check_ssh_connection() {
    local server=$1
    echo -e "${CYAN}📡 Checking SSH connection to $server...${NC}"
    
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$server" "echo 'Connected'" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ SSH connection to $server: OK${NC}"
        return 0
    else
        echo -e "${RED}❌ SSH connection to $server: FAILED${NC}"
        return 1
    fi
}

# Function to check service status
check_service_status() {
    local server=$1
    local url=$(get_transcription_url "$server")
    
    echo -e "${CYAN}🔍 Checking service status on $server...${NC}"
    
    # Check via SSH
    if ssh "$server" "curl -sf $url/health > /dev/null 2>&1" 2>/dev/null; then
        echo -e "${GREEN}✅ Service on $server: Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Service on $server: Not responding${NC}"
        return 1
    fi
}

# Function to check RabbitMQ connection
check_rabbitmq_connection() {
    local server=$1
    
    echo -e "${CYAN}🐰 Checking RabbitMQ connection on $server...${NC}"
    
    # Check RabbitMQ connection via SSH
    if ssh "$server" "python3 -c \"
import os
import sys
sys.path.insert(0, '/workspace/transcription-service')
from app.workers.async.connection import AsyncRabbitMQConnection
import asyncio

async def test():
    try:
        conn = AsyncRabbitMQConnection()
        await conn.connect()
        await conn.close()
        print('OK')
    except Exception as e:
        print(f'ERROR: {e}')
        sys.exit(1)

asyncio.run(test())
\"" 2>/dev/null | grep -q "OK"; then
        echo -e "${GREEN}✅ RabbitMQ connection on $server: OK${NC}"
        return 0
    else
        echo -e "${RED}❌ RabbitMQ connection on $server: FAILED${NC}"
        return 1
    fi
}

# Function to send transcription task
send_transcription_task() {
    local server=$1
    local video_url=$2
    local task_id=$3
    local url=$(get_transcription_url "$server")
    
    local response=$(curl -s -X POST "$url/transcribe/" \
        -H "Content-Type: application/json" \
        -d "{
            \"file_url\": \"$video_url\",
            \"file_name\": \"test-video-$task_id.mp4\",
            \"language\": \"th\",
            \"model_size\": \"medium\",
            \"chunk_duration\": 30,
            \"callback_url\": \"http://localhost:5173/api/transcription/webhook/completed\",
            \"job_id\": $task_id,
            \"user_id\": \"test-user\"
        }")
    
    echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 || echo ""
}

# Function to wait for transcription completion
wait_for_completion() {
    local server=$1
    local task_id=$2
    local url=$(get_transcription_url "$server")
    local max_wait=1800  # 30 minutes
    local elapsed=0
    local interval=5
    
    while [ $elapsed -lt $max_wait ]; do
        local status=$(curl -s "$url/progress/$task_id" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        
        if [ "$status" = "completed" ]; then
            return 0
        elif [ "$status" = "failed" ]; then
            return 1
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
        echo -n "."
    done
    
    return 2  # Timeout
}

# Function to get transcription result
get_transcription_result() {
    local server=$1
    local task_id=$2
    local url=$(get_transcription_url "$server")
    
    curl -s "$url/result/$task_id" || echo "{}"
}

# Function to run test on server
run_test_on_server() {
    local server=$1
    local video_count=$2
    local results_file="$RESULTS_DIR/${server}-results.json"
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}🧪 Testing Server: $server${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Pre-flight checks
    if ! check_ssh_connection "$server"; then
        echo -e "${RED}❌ Cannot connect to $server. Skipping...${NC}"
        return 1
    fi
    
    if ! check_service_status "$server"; then
        echo -e "${YELLOW}⚠️  Service not running on $server. Attempting to start...${NC}"
        ssh "$server" "bash /workspace/transcription-service/scripts/pod/restart-service-daemon.sh" || {
            echo -e "${RED}❌ Failed to start service on $server${NC}"
            return 1
        }
        sleep 10
    fi
    
    if ! check_rabbitmq_connection "$server"; then
        echo -e "${YELLOW}⚠️  RabbitMQ connection issue on $server${NC}"
        echo -e "${YELLOW}   Checking logs...${NC}"
        ssh "$server" "tail -50 /workspace/transcription-service/logs/video_worker.log | grep -i rabbitmq" || true
    fi
    
    # Initialize results
    echo "{" > "$results_file"
    echo "  \"server\": \"$server\"," >> "$results_file"
    echo "  \"test_start\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"video_count\": $video_count," >> "$results_file"
    echo "  \"tasks\": [" >> "$results_file"
    
    local success_count=0
    local fail_count=0
    local total_time=0
    local task_ids=()
    
    # Send tasks
    echo -e "${CYAN}📤 Sending $video_count transcription tasks...${NC}"
    for i in $(seq 1 $video_count); do
        local video_url="${TEST_VIDEOS[$((i-1))]:-$VIDEO_URL}"
        local task_id=$(send_transcription_task "$server" "$video_url" "$i")
        
        if [ -n "$task_id" ]; then
            task_ids+=("$task_id")
            echo -e "${GREEN}✅ Task $i: $task_id${NC}"
        else
            echo -e "${RED}❌ Task $i: Failed to send${NC}"
            fail_count=$((fail_count + 1))
        fi
        
        sleep 1  # Rate limiting
    done
    
    echo ""
    echo -e "${CYAN}⏳ Waiting for completion...${NC}"
    
    # Wait for completion
    for i in "${!task_ids[@]}"; do
        local task_id="${task_ids[$i]}"
        local task_num=$((i + 1))
        
        echo -n "  Task $task_num ($task_id): "
        local start_time=$(date +%s)
        
        if wait_for_completion "$server" "$task_id"; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            total_time=$((total_time + duration))
            success_count=$((success_count + 1))
            
            echo -e "${GREEN}✅ Completed in ${duration}s${NC}"
            
            # Get result
            local result=$(get_transcription_result "$server" "$task_id")
            
            # Append to results
            if [ $task_num -gt 1 ]; then
                echo "," >> "$results_file"
            fi
            echo "    {" >> "$results_file"
            echo "      \"task_id\": \"$task_id\"," >> "$results_file"
            echo "      \"duration\": $duration," >> "$results_file"
            echo "      \"status\": \"completed\"," >> "$results_file"
            echo "      \"result\": $result" >> "$results_file"
            echo -n "    }" >> "$results_file"
        else
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            fail_count=$((fail_count + 1))
            
            echo -e "${RED}❌ Failed${NC}"
            
            # Append to results
            if [ $task_num -gt 1 ]; then
                echo "," >> "$results_file"
            fi
            echo "    {" >> "$results_file"
            echo "      \"task_id\": \"$task_id\"," >> "$results_file"
            echo "      \"duration\": $duration," >> "$results_file"
            echo "      \"status\": \"failed\"," >> "$results_file"
            echo "      \"result\": {}" >> "$results_file"
            echo -n "    }" >> "$results_file"
        fi
    done
    
    # Finalize results
    echo "" >> "$results_file"
    echo "  ]," >> "$results_file"
    echo "  \"test_end\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$results_file"
    echo "  \"summary\": {" >> "$results_file"
    echo "    \"total_tasks\": $video_count," >> "$results_file"
    echo "    \"success_count\": $success_count," >> "$results_file"
    echo "    \"fail_count\": $fail_count," >> "$results_file"
    echo "    \"success_rate\": $(echo "scale=2; $success_count * 100 / $video_count" | bc)," >> "$results_file"
    echo "    \"total_time\": $total_time," >> "$results_file"
    if [ $success_count -gt 0 ]; then
        echo "    \"avg_time\": $(echo "scale=2; $total_time / $success_count" | bc)," >> "$results_file"
    else
        echo "    \"avg_time\": 0," >> "$results_file"
    fi
    echo "    \"throughput\": $(echo "scale=2; $success_count * 3600 / $total_time" | bc)" >> "$results_file"
    echo "  }" >> "$results_file"
    echo "}" >> "$results_file"
    
    echo ""
    echo -e "${GREEN}✅ Test completed for $server${NC}"
    echo "  Success: $success_count/$video_count"
    echo "  Total time: ${total_time}s"
    if [ $success_count -gt 0 ]; then
        echo "  Avg time: $(echo "scale=2; $total_time / $success_count" | bc)s"
    fi
}

# Function to compare results
compare_results() {
    local file1="$RESULTS_DIR/${SERVER1}-results.json"
    local file2="$RESULTS_DIR/${SERVER2}-results.json"
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📊 Comparison Results${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [ ! -f "$file1" ] || [ ! -f "$file2" ]; then
        echo -e "${RED}❌ Results files not found${NC}"
        return 1
    fi
    
    # Extract summary data
    local s1_success=$(jq -r '.summary.success_count' "$file1")
    local s1_fail=$(jq -r '.summary.fail_count' "$file1")
    local s1_avg=$(jq -r '.summary.avg_time' "$file1")
    local s1_throughput=$(jq -r '.summary.throughput' "$file1")
    
    local s2_success=$(jq -r '.summary.success_count' "$file2")
    local s2_fail=$(jq -r '.summary.fail_count' "$file2")
    local s2_avg=$(jq -r '.summary.avg_time' "$file2")
    local s2_throughput=$(jq -r '.summary.throughput' "$file2")
    
    # Print comparison table
    printf "%-20s %15s %15s\n" "Metric" "$SERVER1" "$SERVER2"
    echo "────────────────────────────────────────────────────────────"
    printf "%-20s %15s %15s\n" "Success Count" "$s1_success" "$s2_success"
    printf "%-20s %15s %15s\n" "Fail Count" "$s1_fail" "$s2_fail"
    printf "%-20s %15.2fs %15.2fs\n" "Avg Time" "$s1_avg" "$s2_avg"
    printf "%-20s %15.2f/hr %15.2f/hr\n" "Throughput" "$s1_throughput" "$s2_throughput"
    
    echo ""
    echo -e "${CYAN}📁 Results saved to: $RESULTS_DIR${NC}"
}

# Main execution
main() {
    echo -e "${YELLOW}⚠️  This script will test transcription on both servers${NC}"
    echo -e "${YELLOW}   Make sure both servers are accessible and services are running${NC}"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    
    # Run tests
    run_test_on_server "$SERVER1" "$VIDEO_COUNT"
    sleep 5  # Cooldown between tests
    run_test_on_server "$SERVER2" "$VIDEO_COUNT"
    
    # Compare results
    compare_results
}

# Run main
main

