#!/bin/bash
# Script สำหรับตรวจสอบ Logs ระหว่างการทดสอบ 50 Concurrency
#
# วิธีใช้งาน:
#   bash scripts/test/check-test-logs.sh [task_id_pattern]
#
# ตัวอย่าง:
#   bash scripts/test/check-test-logs.sh
#   bash scripts/test/check-test-logs.sh 6c7fa156

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

LOG_FILE="/tmp/transcription-service.log"
TASK_PATTERN="${1}"

print_header() { echo -e "${CYAN}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_success() { echo -e "${GREEN}$1${NC}"; }

print_header "╔══════════════════════════════════════════════════════════════╗"
print_header "║  🔍 Check Test Logs                                          ║"
print_header "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    print_error "❌ Log file not found: $LOG_FILE"
    exit 1
fi

LOG_LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)

echo "Log file: $LOG_FILE"
echo "Size: $LOG_SIZE"
echo "Total lines: $LOG_LINES"
echo ""

# 1. Recent POST requests (transcription requests)
print_header "1️⃣  Recent POST /transcribe/ Requests (Last 50)"
echo "──────────────────────────────────────────────────────────────"
echo ""

POST_REQUESTS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -E "POST /transcribe/" | tail -50)
if [ ! -z "$POST_REQUESTS" ]; then
    echo "$POST_REQUESTS" | sed 's/^/   /'
else
    echo "   ⚠️  No POST requests found in recent logs"
fi
echo ""

# 2. Failed requests (4xx, 5xx)
print_header "2️⃣  Failed Requests (4xx, 5xx) (Last 50)"
echo "──────────────────────────────────────────────────────────────"
echo ""

FAILED_REQUESTS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -E "[45][0-9][0-9]" | tail -50)
if [ ! -z "$FAILED_REQUESTS" ]; then
    echo "$FAILED_REQUESTS" | sed 's/^/   /'
else
    echo "   ✅ No failed requests found"
fi
echo ""

# 3. File not found errors
print_header "3️⃣  File Not Found Errors (Last 50)"
echo "──────────────────────────────────────────────────────────────"
echo ""

FILE_ERRORS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "file.*not.*found|file.*not.*exist|file.*does.*not.*exist|no such file|file not accessible" | tail -50)
if [ ! -z "$FILE_ERRORS" ]; then
    print_warning "⚠️  File errors found!"
    echo ""
    echo "$FILE_ERRORS" | sed 's/^/   /'
else
    echo "   ✅ No file errors found"
fi
echo ""

# 4. Errors and Exceptions
print_header "4️⃣  Errors & Exceptions (Last 50)"
echo "──────────────────────────────────────────────────────────────"
echo ""

ERRORS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "error|exception|traceback|failed" | tail -50)
if [ ! -z "$ERRORS" ]; then
    print_warning "⚠️  Errors found!"
    echo ""
    echo "$ERRORS" | sed 's/^/   /'
else
    echo "   ✅ No errors found"
fi
echo ""

# 5. Task-specific logs (if task_id provided)
if [ ! -z "$TASK_PATTERN" ]; then
    print_header "5️⃣  Logs for Task: $TASK_PATTERN"
    echo "──────────────────────────────────────────────────────────────"
    echo ""
    
    TASK_LOGS=$(grep "$TASK_PATTERN" "$LOG_FILE" 2>/dev/null | tail -50)
    if [ ! -z "$TASK_LOGS" ]; then
        echo "$TASK_LOGS" | sed 's/^/   /'
    else
        echo "   ⚠️  No logs found for task: $TASK_PATTERN"
    fi
    echo ""
fi

# 6. Recent GET requests (polling)
print_header "6️⃣  Recent GET /transcribe/{task_id} Requests (Polling) (Last 50)"
echo "──────────────────────────────────────────────────────────────"
echo ""

GET_REQUESTS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -E "GET /transcribe/" | tail -50)
if [ ! -z "$GET_REQUESTS" ]; then
    echo "$GET_REQUESTS" | sed 's/^/   /'
else
    echo "   ⚠️  No GET requests found"
fi
echo ""

# 7. Summary statistics
print_header "7️⃣  Summary Statistics (Last 500 lines)"
echo "──────────────────────────────────────────────────────────────"
echo ""

TOTAL_LINES=$(tail -500 "$LOG_FILE" 2>/dev/null | wc -l)
POST_COUNT=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -c "POST /transcribe/" || echo "0")
GET_COUNT=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -c "GET /transcribe/" || echo "0")
ERROR_COUNT=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -icE "error|exception" || echo "0")
FILE_ERROR_COUNT=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -icE "file.*not.*found|file.*not.*exist" || echo "0")
HTTP_ERROR_COUNT=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -cE "[45][0-9][0-9]" || echo "0")

echo "   Total lines analyzed: $TOTAL_LINES"
echo "   POST /transcribe/ requests: $POST_COUNT"
echo "   GET /transcribe/ requests: $GET_COUNT"
echo "   Errors/Exceptions: $ERROR_COUNT"
echo "   File errors: $FILE_ERROR_COUNT"
echo "   HTTP errors (4xx/5xx): $HTTP_ERROR_COUNT"
echo ""

# 8. Check for specific patterns
print_header "8️⃣  Specific Error Patterns"
echo "──────────────────────────────────────────────────────────────"
echo ""

echo "Connection errors:"
CONN_ERRORS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | wc -l || echo "0")
echo "   Count: $CONN_ERRORS"
if [ "$CONN_ERRORS" -gt 0 ]; then
    tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "disconnect|connection reset|connection refused|connection error|timeout" | tail -10 | sed 's/^/   | /'
fi
echo ""

echo "File path errors:"
FILE_PATH_ERRORS=$(tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "uploads/|file_path|file_path.*not" | wc -l || echo "0")
echo "   Count: $FILE_PATH_ERRORS"
if [ "$FILE_PATH_ERRORS" -gt 0 ]; then
    tail -500 "$LOG_FILE" 2>/dev/null | grep -iE "uploads/|file_path|file_path.*not" | tail -10 | sed 's/^/   | /'
fi
echo ""

# 9. Last 30 lines (most recent)
print_header "9️⃣  Last 30 Lines (Most Recent)"
echo "──────────────────────────────────────────────────────────────"
echo ""

tail -30 "$LOG_FILE" 2>/dev/null | sed 's/^/   | /'
echo ""

# 10. Recommendations
print_header "📊 Recommendations"
echo "──────────────────────────────────────────────────────────────"
echo ""

if [ "$FILE_ERROR_COUNT" -gt 0 ]; then
    print_warning "⚠️  File errors detected!"
    echo "   • Check if file exists: ls -lh uploads/v10-1.mp4"
    echo "   • Check file permissions"
    echo "   • Verify file path in request"
fi

if [ "$CONN_ERRORS" -gt 10 ]; then
    print_warning "⚠️  High number of connection errors!"
    echo "   • Server may be overloaded (50 concurrent requests)"
    echo "   • Try reducing to 20-30 concurrent requests"
    echo "   • Check service status: bash scripts/pod/check-service-status.sh"
fi

if [ "$HTTP_ERROR_COUNT" -gt 0 ]; then
    print_warning "⚠️  HTTP errors detected!"
    echo "   • Check for 4xx (client errors) or 5xx (server errors)"
    echo "   • Review error messages above"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Log analysis complete!"
echo ""
echo "💡 Next steps:"
echo "   • Monitor logs real-time: tail -f $LOG_FILE"
echo "   • Check service status: bash scripts/pod/check-service-status.sh"
echo "   • Check connections: bash scripts/pod/check-connection-issues.sh"
echo ""

