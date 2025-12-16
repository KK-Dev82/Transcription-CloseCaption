#!/bin/bash
# Script สำหรับตรวจสอบ Logs และ Webhook ของ Transcription Service
# ตรวจสอบ MainAPI, Video-Worker, Dashboard และ Webhook

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

cd /workspace/transcription-service || exit 1

# Ports
API_PORT=8010
DASHBOARD_PORT=8020

# Log files
# Main API logs (ใช้ logs/ เป็นหลัก, ถ้าไม่มีค่อยใช้ /tmp/)
API_LOG="/workspace/transcription-service/logs/api-service.log"
API_ERROR_LOG="/workspace/transcription-service/logs/api-service-errors.log"
API_LOG_TMP="/tmp/transcription-service.log"  # fallback

# Video Worker logs
WORKER_LOG="/workspace/transcription-service/logs/video-worker.log"
WORKER_ERROR_LOG="/workspace/transcription-service/logs/video-worker-errors.log"
WORKER_LOG_TMP="/tmp/video-worker.log"  # fallback

# Dashboard log
DASHBOARD_LOG="/tmp/dashboard.log"

# ============================================
# Part 1: ตรวจสอบ Logs ของ Services
# ============================================
print_header "📋 Part 1: ตรวจสอบ Logs ของ Services"

# 1.1 ตรวจสอบ MainAPI Logs
print_header "1.1 MainAPI Logs (Port $API_PORT)"

# ใช้ logs/ เป็นหลัก, ถ้าไม่มีค่อยใช้ /tmp/
if [ ! -f "$API_LOG" ] && [ -f "$API_LOG_TMP" ]; then
    API_LOG="$API_LOG_TMP"
fi

if [ -f "$API_LOG" ]; then
    LOG_SIZE=$(du -h "$API_LOG" | cut -f1)
    LOG_LINES=$(wc -l < "$API_LOG" 2>/dev/null || echo "0")
    LAST_MODIFIED=$(stat -c %y "$API_LOG" 2>/dev/null | cut -d'.' -f1 || echo "N/A")
    
    print_success "Log file exists"
    echo "   Path: $API_LOG"
    echo "   Size: $LOG_SIZE"
    echo "   Lines: $LOG_LINES"
    echo "   Last modified: $LAST_MODIFIED"
    echo ""
    
    # Check for recent errors
    ERROR_COUNT=$(tail -100 "$API_LOG" | grep -iE "error|exception|traceback|failed" | wc -l | tr -d ' ' || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "พบ $ERROR_COUNT errors ใน 100 บรรทัดล่าสุด"
        echo "   Last 3 errors:"
        tail -100 "$API_LOG" | grep -iE "error|exception|traceback|failed" | tail -3 | sed 's/^/   | /'
    else
        print_success "ไม่พบ errors ใน 100 บรรทัดล่าสุด"
    fi
    echo ""
    
    # Show last 10 lines
    print_status "Last 10 lines:"
    tail -10 "$API_LOG" | sed 's/^/   | /'
else
    print_warning "Log file not found: $API_LOG"
fi
echo ""

# 1.2 ตรวจสอบ Video-Worker Logs
print_header "1.2 Video-Worker Logs"

# ใช้ logs/ เป็นหลัก, ถ้าไม่มีค่อยใช้ /tmp/
if [ ! -f "$WORKER_LOG" ] && [ -f "$WORKER_LOG_TMP" ]; then
    WORKER_LOG="$WORKER_LOG_TMP"
fi

if [ -f "$WORKER_LOG" ]; then
    LOG_SIZE=$(du -h "$WORKER_LOG" | cut -f1)
    LOG_LINES=$(wc -l < "$WORKER_LOG" 2>/dev/null || echo "0")
    LAST_MODIFIED=$(stat -c %y "$WORKER_LOG" 2>/dev/null | cut -d'.' -f1 || echo "N/A")
    
    print_success "Log file exists"
    echo "   Path: $WORKER_LOG"
    echo "   Size: $LOG_SIZE"
    echo "   Lines: $LOG_LINES"
    echo "   Last modified: $LAST_MODIFIED"
    echo ""
    
    # Check for recent activity
    PROCESSING_COUNT=$(tail -100 "$WORKER_LOG" | grep -iE "processing.*task|received.*message|starting.*transcription" | wc -l | tr -d ' ' || echo "0")
    print_status "Processing activity: $PROCESSING_COUNT (ใน 100 บรรทัดล่าสุด)"
    
    # Check for errors
    ERROR_COUNT=$(tail -100 "$WORKER_LOG" | grep -iE "error|exception|traceback|failed" | wc -l | tr -d ' ' || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "พบ $ERROR_COUNT errors ใน 100 บรรทัดล่าสุด"
        echo "   Last 3 errors:"
        tail -100 "$WORKER_LOG" | grep -iE "error|exception|traceback|failed" | tail -3 | sed 's/^/   | /'
    else
        print_success "ไม่พบ errors ใน 100 บรรทัดล่าสุด"
    fi
    
    # Check for "Channel is closed"
    CHANNEL_CLOSED=$(tail -100 "$WORKER_LOG" | grep -i "channel is closed" | wc -l | tr -d ' ' || echo "0")
    if [ "$CHANNEL_CLOSED" -gt 0 ]; then
        print_warning "พบ 'Channel is closed' $CHANNEL_CLOSED ครั้ง"
    fi
    echo ""
    
    # Show last 10 lines
    print_status "Last 10 lines:"
    if [ -s "$WORKER_LOG" ]; then
        tail -10 "$WORKER_LOG" | sed 's/^/   | /'
    else
        print_warning "Log file is empty (0 bytes)"
    fi
    echo ""
    
    # Check error log
    if [ -f "$WORKER_ERROR_LOG" ]; then
        ERROR_LOG_SIZE=$(du -h "$WORKER_ERROR_LOG" | cut -f1)
        ERROR_LOG_LINES=$(wc -l < "$WORKER_ERROR_LOG" 2>/dev/null || echo "0")
        print_status "Error log: $WORKER_ERROR_LOG ($ERROR_LOG_SIZE, $ERROR_LOG_LINES lines)"
        if [ "$ERROR_LOG_LINES" -gt 0 ]; then
            print_warning "Last 3 errors from error log:"
            tail -3 "$WORKER_ERROR_LOG" | sed 's/^/   | /'
        fi
    fi
else
    print_warning "Log file not found: $WORKER_LOG"
    if [ -f "$WORKER_ERROR_LOG" ]; then
        print_status "But error log exists: $WORKER_ERROR_LOG"
        ERROR_LOG_LINES=$(wc -l < "$WORKER_ERROR_LOG" 2>/dev/null || echo "0")
        if [ "$ERROR_LOG_LINES" -gt 0 ]; then
            print_warning "Last 3 errors:"
            tail -3 "$WORKER_ERROR_LOG" | sed 's/^/   | /'
        fi
    fi
fi
echo ""

# 1.3 ตรวจสอบ Process Status
print_header "1.3 Process Status"

# Check MainAPI process
API_PID=$(pgrep -f "uvicorn.*app.main.*${API_PORT}" | head -1)
if [ -n "$API_PID" ]; then
    print_success "MainAPI is running (PID: $API_PID)"
    ps -p "$API_PID" -o pid,state,etime,pcpu,pmem,command --no-headers 2>/dev/null | awk '{print "   State: "$2", Uptime: "$3", CPU: "$4"%, Memory: "$5"%"}'
else
    print_error "MainAPI is NOT running"
fi

# Check Video-Worker process
WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
if [ -n "$WORKER_PID" ]; then
    print_success "Video-Worker is running (PID: $WORKER_PID)"
    ps -p "$WORKER_PID" -o pid,state,etime,pcpu,pmem,command --no-headers 2>/dev/null | awk '{print "   State: "$2", Uptime: "$3", CPU: "$4"%, Memory: "$5"%"}'
else
    print_error "Video-Worker is NOT running"
fi

# Check Dashboard process
DASHBOARD_PID=$(pgrep -f "uvicorn.*dashboard.*${DASHBOARD_PORT}" | head -1)
if [ -n "$DASHBOARD_PID" ]; then
    print_success "Dashboard is running (PID: $DASHBOARD_PID)"
    ps -p "$DASHBOARD_PID" -o pid,state,etime,pcpu,pmem,command --no-headers 2>/dev/null | awk '{print "   State: "$2", Uptime: "$3", CPU: "$4"%, Memory: "$5"%"}'
else
    print_warning "Dashboard is NOT running"
fi
echo ""

# ============================================
# Part 2: ตรวจสอบ Dashboard
# ============================================
print_header "📊 Part 2: ตรวจสอบ Dashboard (Port $DASHBOARD_PORT)"

# 2.1 ตรวจสอบ Dashboard Health
print_status "Checking dashboard health..."

DASHBOARD_RESPONSE=$(curl -s -m 5 "http://localhost:${DASHBOARD_PORT}/" 2>&1 || echo "ERROR")
if echo "$DASHBOARD_RESPONSE" | grep -q "Transcription\|dashboard\|html"; then
    print_success "Dashboard is responding"
else
    print_error "Dashboard is NOT responding"
    echo "   Response: $(echo "$DASHBOARD_RESPONSE" | head -1 | cut -c1-100)"
fi
echo ""

# 2.2 ตรวจสอบ Dashboard API Endpoints
print_status "Checking dashboard API endpoints..."

# Check server routes
SERVER_ROUTES_RESPONSE=$(curl -s -m 5 "http://localhost:${DASHBOARD_PORT}/api/servers" 2>&1 || echo "ERROR")
if echo "$SERVER_ROUTES_RESPONSE" | grep -q "4000-ada\|servers\|api_url"; then
    print_success "Server routes endpoint is working"
else
    print_warning "Server routes endpoint may not be working"
fi

# Check webhook routes
WEBHOOK_EVENTS_RESPONSE=$(curl -s -m 5 "http://localhost:${DASHBOARD_PORT}/api/webhook/events" 2>&1 || echo "ERROR")
if echo "$WEBHOOK_EVENTS_RESPONSE" | grep -q "tasks\|events\|taskId"; then
    print_success "Webhook events endpoint is working"
    echo "   Response: $(echo "$WEBHOOK_EVENTS_RESPONSE" | head -1 | cut -c1-150)"
else
    print_warning "Webhook events endpoint may not be working"
    echo "   Response: $(echo "$WEBHOOK_EVENTS_RESPONSE" | head -1 | cut -c1-150)"
fi
echo ""

# ============================================
# Part 3: ตรวจสอบ Webhook
# ============================================
print_header "🔔 Part 3: ตรวจสอบ Webhook"

# 3.1 ตรวจสอบ Webhook Endpoint
print_status "Testing webhook endpoint..."

# Create test webhook payload
TEST_TASK_ID="test-$(date +%s)"
TEST_PAYLOAD=$(cat <<EOF
{
  "jobId": "test-job-123",
  "taskId": "$TEST_TASK_ID",
  "status": "processing",
  "progress": 50,
  "text": "Test transcription text",
  "audioDuration": 1800.0,
  "wordCount": 100
}
EOF
)

WEBHOOK_TEST_RESPONSE=$(curl -s -m 5 -X POST \
    -H "Content-Type: application/json" \
    -d "$TEST_PAYLOAD" \
    "http://localhost:${DASHBOARD_PORT}/api/webhook/transcription" 2>&1 || echo "ERROR")

if echo "$WEBHOOK_TEST_RESPONSE" | grep -q "received\|status\|taskId"; then
    print_success "Webhook endpoint is working"
    echo "   Response: $(echo "$WEBHOOK_TEST_RESPONSE" | head -1)"
    
    # Check if event was stored
    sleep 1
    EVENT_CHECK=$(curl -s -m 5 "http://localhost:${DASHBOARD_PORT}/api/webhook/events/$TEST_TASK_ID" 2>&1 || echo "ERROR")
    if echo "$EVENT_CHECK" | grep -q "$TEST_TASK_ID\|events"; then
        print_success "Webhook event was stored correctly"
        echo "   Event data: $(echo "$EVENT_CHECK" | head -1 | cut -c1-150)"
    else
        print_warning "Webhook event may not be stored"
    fi
else
    print_error "Webhook endpoint is NOT working"
    echo "   Response: $(echo "$WEBHOOK_TEST_RESPONSE" | head -1 | cut -c1-150)"
fi
echo ""

# 3.2 ตรวจสอบ Webhook Events ที่มีอยู่
print_status "Checking existing webhook events..."

ALL_EVENTS=$(curl -s -m 5 "http://localhost:${DASHBOARD_PORT}/api/webhook/events" 2>&1 || echo "ERROR")
if echo "$ALL_EVENTS" | grep -q "tasks\|total_events"; then
    TASK_COUNT=$(echo "$ALL_EVENTS" | grep -o '"tasks":\s*\[[^]]*\]' | grep -o '"[^"]*"' | wc -l || echo "0")
    TOTAL_EVENTS=$(echo "$ALL_EVENTS" | grep -o '"total_events":\s*[0-9]*' | grep -o '[0-9]*' || echo "0")
    
    if [ "$TOTAL_EVENTS" -gt 0 ]; then
        print_success "Found $TOTAL_EVENTS webhook events across $TASK_COUNT tasks"
    else
        print_warning "No webhook events found (this is normal if no tasks have been completed)"
    fi
else
    print_warning "Could not retrieve webhook events"
fi
echo ""

# 3.3 ตรวจสอบ MainAPI Webhook Configuration
print_header "3.3 ตรวจสอบ MainAPI Webhook Configuration"

# Check if MainAPI has webhook subscriptions
WEBHOOK_SUBS_RESPONSE=$(curl -s -m 5 "http://localhost:${API_PORT}/webhook/subscriptions" 2>&1 || echo "ERROR")
if echo "$WEBHOOK_SUBS_RESPONSE" | grep -q "subscriptions\|\[\]"; then
    print_success "Webhook subscriptions endpoint is accessible"
    SUBS_COUNT=$(echo "$WEBHOOK_SUBS_RESPONSE" | grep -o '\[.*\]' | grep -o ',' | wc -l || echo "0")
    if [ "$SUBS_COUNT" -eq 0 ]; then
        print_warning "No webhook subscriptions found (this is normal if using per-task callbacks)"
    else
        print_status "Found $SUBS_COUNT webhook subscriptions"
    fi
else
    print_warning "Could not access webhook subscriptions endpoint"
fi
echo ""

# 3.4 ตรวจสอบ Logs สำหรับ Webhook Activity
print_status "Checking logs for webhook activity..."

# Check API logs for webhook sends
WEBHOOK_SEND_COUNT=$(tail -200 "$API_LOG" 2>/dev/null | grep -iE "callback|webhook|_send_callback" | wc -l | tr -d ' ' || echo "0")
if [ "$WEBHOOK_SEND_COUNT" -gt 0 ]; then
    print_success "Found $WEBHOOK_SEND_COUNT webhook/callback activities in API logs"
    echo "   Recent webhook activities:"
    tail -200 "$API_LOG" 2>/dev/null | grep -iE "callback|webhook|_send_callback" | tail -3 | sed 's/^/   | /'
else
    print_warning "No webhook/callback activities found in API logs (อาจยังไม่มี task ที่ส่ง webhook)"
fi
echo ""

# Check Dashboard logs for webhook receives
if [ -f "$DASHBOARD_LOG" ]; then
    WEBHOOK_RECEIVE_COUNT=$(tail -200 "$DASHBOARD_LOG" 2>/dev/null | grep -iE "webhook.*received|transcription.*webhook" | wc -l | tr -d ' ' || echo "0")
    if [ "$WEBHOOK_RECEIVE_COUNT" -gt 0 ]; then
        print_success "Found $WEBHOOK_RECEIVE_COUNT webhook receives in dashboard logs"
        echo "   Recent webhook receives:"
        tail -200 "$DASHBOARD_LOG" 2>/dev/null | grep -iE "webhook.*received|transcription.*webhook" | tail -3 | sed 's/^/   | /'
    else
        print_warning "No webhook receives found in dashboard logs"
    fi
else
    print_warning "Dashboard log file not found: $DASHBOARD_LOG"
fi
echo ""

# ============================================
# Part 4: ตรวจสอบ Task ที่มี Callback URL
# ============================================
print_header "📝 Part 4: ตรวจสอบ Tasks ที่มี Callback URL"

# Check recent tasks for callback_url
print_status "Checking recent tasks for callback_url configuration..."

# Try to get recent tasks from API
RECENT_TASKS_RESPONSE=$(curl -s -m 5 "http://localhost:${API_PORT}/tasks?limit=10" 2>&1 || echo "ERROR")
if echo "$RECENT_TASKS_RESPONSE" | grep -q "taskId\|task_id"; then
    print_success "Can retrieve tasks from API"
    
    # Count tasks with callback_url
    if command -v python3 > /dev/null; then
        TASKS_WITH_CALLBACK=$(echo "$RECENT_TASKS_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tasks = data.get('tasks', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    count = sum(1 for t in tasks if t.get('callback_url') or t.get('callbackUrl'))
    print(count)
except:
    print('0')
" 2>/dev/null || echo "0")
        
        if [ "$TASKS_WITH_CALLBACK" -gt 0 ]; then
            print_success "Found $TASKS_WITH_CALLBACK tasks with callback_url in recent tasks"
        else
            print_warning "No tasks with callback_url found in recent tasks"
            echo "   💡 Tasks need to have 'callback_url' set when creating transcription requests"
        fi
    fi
else
    print_warning "Could not retrieve tasks from API"
    echo "   Response: $(echo "$RECENT_TASKS_RESPONSE" | head -1 | cut -c1-100)"
fi
echo ""

# ============================================
# Summary
# ============================================
print_header "📋 Summary"

echo "Services Status:"
if [ -n "$API_PID" ]; then
    echo -e "   ${GREEN}✅ MainAPI: RUNNING${NC}"
else
    echo -e "   ${RED}❌ MainAPI: NOT RUNNING${NC}"
fi

if [ -n "$WORKER_PID" ]; then
    echo -e "   ${GREEN}✅ Video-Worker: RUNNING${NC}"
else
    echo -e "   ${RED}❌ Video-Worker: NOT RUNNING${NC}"
fi

if [ -n "$DASHBOARD_PID" ]; then
    echo -e "   ${GREEN}✅ Dashboard: RUNNING${NC}"
else
    echo -e "   ${YELLOW}⚠️  Dashboard: NOT RUNNING${NC}"
fi

echo ""
echo "Logs Status:"
# Check API log
if [ -f "$API_LOG" ] || [ -f "$API_LOG_TMP" ]; then
    ACTUAL_API_LOG="$API_LOG"
    [ ! -f "$ACTUAL_API_LOG" ] && ACTUAL_API_LOG="$API_LOG_TMP"
    if [ -s "$ACTUAL_API_LOG" ]; then
        echo -e "   ${GREEN}✅ MainAPI Log: EXISTS${NC} ($ACTUAL_API_LOG)"
    else
        echo -e "   ${YELLOW}⚠️  MainAPI Log: EXISTS BUT EMPTY${NC} ($ACTUAL_API_LOG)"
    fi
    if [ -f "$API_ERROR_LOG" ]; then
        ERROR_SIZE=$(du -h "$API_ERROR_LOG" | cut -f1)
        echo -e "   ${GREEN}✅ MainAPI Error Log: EXISTS${NC} ($API_ERROR_LOG, $ERROR_SIZE)"
    fi
else
    echo -e "   ${YELLOW}⚠️  MainAPI Log: NOT FOUND${NC}"
fi

# Check Worker log
if [ -f "$WORKER_LOG" ] || [ -f "$WORKER_LOG_TMP" ]; then
    ACTUAL_WORKER_LOG="$WORKER_LOG"
    [ ! -f "$ACTUAL_WORKER_LOG" ] && ACTUAL_WORKER_LOG="$WORKER_LOG_TMP"
    if [ -s "$ACTUAL_WORKER_LOG" ]; then
        echo -e "   ${GREEN}✅ Video-Worker Log: EXISTS${NC} ($ACTUAL_WORKER_LOG)"
    else
        echo -e "   ${YELLOW}⚠️  Video-Worker Log: EXISTS BUT EMPTY${NC} ($ACTUAL_WORKER_LOG)"
    fi
    if [ -f "$WORKER_ERROR_LOG" ]; then
        ERROR_SIZE=$(du -h "$WORKER_ERROR_LOG" | cut -f1)
        ERROR_LINES=$(wc -l < "$WORKER_ERROR_LOG" 2>/dev/null || echo "0")
        echo -e "   ${GREEN}✅ Video-Worker Error Log: EXISTS${NC} ($WORKER_ERROR_LOG, $ERROR_SIZE, $ERROR_LINES lines)"
    fi
else
    echo -e "   ${YELLOW}⚠️  Video-Worker Log: NOT FOUND${NC}"
    if [ -f "$WORKER_ERROR_LOG" ]; then
        ERROR_SIZE=$(du -h "$WORKER_ERROR_LOG" | cut -f1)
        echo -e "   ${GREEN}✅ Video-Worker Error Log: EXISTS${NC} ($WORKER_ERROR_LOG, $ERROR_SIZE)"
    fi
fi

echo ""
echo "Webhook Status:"
if echo "$WEBHOOK_TEST_RESPONSE" | grep -q "received\|status"; then
    echo -e "   ${GREEN}✅ Webhook Endpoint: WORKING${NC}"
else
    echo -e "   ${RED}❌ Webhook Endpoint: NOT WORKING${NC}"
fi

echo ""
echo "💡 Useful Commands:"
echo "   View all logs:    bash scripts/pod/tail-all-logs.sh"
echo "   Check API status: bash scripts/pod/check-service-status.sh"
echo "   Check worker:     bash scripts/pod/check-worker-activity.sh"
echo "   Start dashboard: cd dashboard && python3 -m uvicorn main:app --host 0.0.0.0 --port $DASHBOARD_PORT"
echo ""
echo "📁 Log File Locations:"
echo "   Main API:         $API_LOG"
echo "   Main API Errors:  $API_ERROR_LOG"
echo "   Video Worker:     $WORKER_LOG"
echo "   Video Worker Errors: $WORKER_ERROR_LOG"
echo ""
echo "📋 Quick View Commands:"
echo "   tail -50 $API_LOG"
echo "   tail -20 $API_ERROR_LOG"
echo "   tail -50 $WORKER_LOG"
echo "   tail -20 $WORKER_ERROR_LOG"
echo ""

