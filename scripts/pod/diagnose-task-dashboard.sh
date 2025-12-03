#!/bin/bash

# Script สำหรับวินิจฉัยปัญหา Task Dashboard ไม่โหลดข้อมูล

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8010}"
STORAGE_DIR="${STORAGE_DIR:-storage}"
PROJECT_DIR="${PROJECT_DIR:-/workspace/transcription-service}"

cd "$PROJECT_DIR" 2>/dev/null || {
    echo -e "${RED}❌ Error: Cannot cd to $PROJECT_DIR${NC}"
    exit 1
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 Task Dashboard Diagnostic                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}┌──────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│ $1${NC}"
    echo -e "${BLUE}└──────────────────────────────────────────────────────────────┘${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 1. Check API Health
print_header "1️⃣  API Health Check"
if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    print_success "API is healthy"
    curl -s "$API_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$API_URL/health"
else
    print_error "API is not accessible at $API_URL"
    echo "   Try: bash scripts/pod/check-service-status.sh"
    exit 1
fi
echo ""

# 2. Check Storage Directory
print_header "2️⃣  Storage Directory Check"
TRANSCRIPTION_DIR="$STORAGE_DIR/transcriptions"
if [ -d "$TRANSCRIPTION_DIR" ]; then
    print_success "Transcription directory exists: $TRANSCRIPTION_DIR"
    
    # Count task folders
    TASK_FOLDERS=$(find "$TRANSCRIPTION_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    echo "   Task folders: $TASK_FOLDERS"
    
    # Count metadata files
    METADATA_FILES=$(find "$TRANSCRIPTION_DIR" -name "metadata.json" 2>/dev/null | wc -l)
    echo "   Metadata files: $METADATA_FILES"
    
    if [ "$TASK_FOLDERS" -eq 0 ] && [ "$METADATA_FILES" -eq 0 ]; then
        print_warning "No tasks found in storage directory"
        echo "   This may be why the dashboard is empty"
    fi
else
    print_error "Transcription directory does not exist: $TRANSCRIPTION_DIR"
fi
echo ""

# 3. Check API Endpoints
print_header "3️⃣  API Endpoints Check"

# Test /api/tasks/available-dates
echo "Testing /api/tasks/available-dates..."
DATES_RESPONSE=$(curl -s "$API_URL/api/tasks/available-dates" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$DATES_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DATES_RESPONSE"
    
    DATE_COUNT=$(echo "$DATES_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('count', 0))" 2>/dev/null || echo "0")
    if [ "$DATE_COUNT" -gt 0 ]; then
        print_success "Available dates endpoint works ($DATE_COUNT dates)"
        LATEST_DATE=$(echo "$DATES_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('dates', [])[0] if d.get('dates') else 'N/A')" 2>/dev/null || echo "N/A")
        echo "   Latest date: $LATEST_DATE"
    else
        print_warning "No dates available"
    fi
else
    print_error "Failed to call /api/tasks/available-dates"
fi
echo ""

# Test /api/tasks/summary
echo "Testing /api/tasks/summary..."
TODAY=$(date +%Y-%m-%d)
SUMMARY_RESPONSE=$(curl -s "$API_URL/api/tasks/summary?date=$TODAY" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$SUMMARY_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SUMMARY_RESPONSE"
    
    ALL_COUNT=$(echo "$SUMMARY_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('summary', {}).get('all_tasks', 0))" 2>/dev/null || echo "0")
    if [ "$ALL_COUNT" -gt 0 ]; then
        print_success "Summary endpoint works ($ALL_COUNT tasks for $TODAY)"
    else
        print_warning "No tasks found for today ($TODAY)"
    fi
else
    print_error "Failed to call /api/tasks/summary"
fi
echo ""

# Test /api/tasks/by-date
echo "Testing /api/tasks/by-date?date=$TODAY..."
BY_DATE_RESPONSE=$(curl -s "$API_URL/api/tasks/by-date?date=$TODAY&limit=10" 2>/dev/null)
if [ $? -eq 0 ]; then
    TASK_COUNT=$(echo "$BY_DATE_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('tasks', [])))" 2>/dev/null || echo "0")
    if [ "$TASK_COUNT" -gt 0 ]; then
        print_success "By-date endpoint works ($TASK_COUNT tasks returned)"
        
        # Show first task
        echo ""
        echo "   First task sample:"
        echo "$BY_DATE_RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tasks = d.get('tasks', [])
if tasks:
    t = tasks[0]
    print(f\"     Task ID: {t.get('task_id', 'N/A')[:16]}...\")
    print(f\"     Status: {t.get('status', 'N/A')}\")
    print(f\"     Video File: {t.get('video_file', 'N/A')}\")
    print(f\"     Progress: {t.get('progress', 0)}%\")
" 2>/dev/null || echo "   (Could not parse response)"
    else
        print_warning "No tasks returned for $TODAY"
        echo "$BY_DATE_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20 || echo "$BY_DATE_RESPONSE" | head -20
    fi
else
    print_error "Failed to call /api/tasks/by-date"
fi
echo ""

# 4. Check Sample Tasks
print_header "4️⃣  Sample Tasks Check"
echo "Checking recent task folders..."
RECENT_TASKS=$(find "$TRANSCRIPTION_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -5 | cut -d' ' -f2-)
if [ ! -z "$RECENT_TASKS" ]; then
    echo "   Recent tasks:"
    for task_dir in $RECENT_TASKS; do
        task_id=$(basename "$task_dir")
        metadata_file="$task_dir/metadata.json"
        
        if [ -f "$metadata_file" ]; then
            status=$(python3 -c "import json; d=json.load(open('$metadata_file')); print(d.get('status', 'N/A'))" 2>/dev/null || echo "N/A")
            created_at=$(python3 -c "import json; d=json.load(open('$metadata_file')); print(d.get('created_at', 'N/A')[:10])" 2>/dev/null || echo "N/A")
            progress=$(python3 -c "import json; d=json.load(open('$metadata_file')); print(d.get('progress', 0))" 2>/dev/null || echo "0")
            
            echo "     • $task_id"
            echo "       Status: $status | Progress: $progress% | Created: $created_at"
        else
            echo "     • $task_id (no metadata.json)"
        fi
    done
else
    print_warning "No task folders found"
fi
echo ""

# 5. Check for Date Parsing Issues
print_header "5️⃣  Date Parsing Check"
echo "Checking task metadata for date format issues..."
PROBLEMATIC_TASKS=0
for metadata_file in $(find "$TRANSCRIPTION_DIR" -name "metadata.json" 2>/dev/null | head -10); do
    created_at=$(python3 -c "import json; d=json.load(open('$metadata_file')); print(d.get('created_at', 'N/A'))" 2>/dev/null || echo "N/A")
    
    if [ "$created_at" != "N/A" ] && [[ ! "$created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
        PROBLEMATIC_TASKS=$((PROBLEMATIC_TASKS + 1))
        task_id=$(dirname "$metadata_file" | xargs basename)
        echo "   ⚠️  Task $task_id: Invalid date format: $created_at"
    fi
done

if [ "$PROBLEMATIC_TASKS" -eq 0 ]; then
    print_success "No date format issues found in sample tasks"
else
    print_warning "$PROBLEMATIC_TASKS tasks have date format issues"
fi
echo ""

# 6. Check JSON Storage Implementation
print_header "6️⃣  JSON Storage Implementation Check"
echo "Checking if json_storage.list_all_transcriptions() works..."

python3 << 'PYTHON_EOF'
import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from app.utils.json_storage import JSONStorage
    
    storage = JSONStorage()
    transcriptions = storage.list_all_transcriptions()
    
    print(f"   Total transcriptions found: {len(transcriptions)}")
    
    if len(transcriptions) > 0:
        print("\n   Sample transcription:")
        sample = transcriptions[0]
        print(f"     Task ID: {sample.get('task_id', 'N/A')[:16]}...")
        print(f"     Status: {sample.get('status', 'N/A')}")
        print(f"     Created At: {sample.get('created_at', 'N/A')}")
        print(f"     Has Full Text: {bool(sample.get('full_text'))}")
        print(f"     Chunks Count: {len(sample.get('chunks', []))}")
    else:
        print("   ⚠️  No transcriptions found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYTHON_EOF

echo ""

# 7. Recommendations
print_header "📊 Recommendations"
echo ""

if [ "$TASK_FOLDERS" -eq 0 ]; then
    print_warning "No tasks found in storage"
    echo "   • Check if transcription service is running"
    echo "   • Check if tasks are being saved: tail -f /tmp/transcription-service.log | grep 'บันทึก transcription'"
    echo "   • Verify storage directory path: $TRANSCRIPTION_DIR"
fi

if [ "$DATE_COUNT" -eq 0 ]; then
    print_warning "No dates available in API"
    echo "   • This means no tasks have been created yet"
    echo "   • Try creating a test transcription first"
fi

echo "   • Test API endpoints manually:"
echo "     curl $API_URL/api/tasks/available-dates"
echo "     curl $API_URL/api/tasks/summary?date=$TODAY"
echo "     curl $API_URL/api/tasks/by-date?date=$TODAY"
echo ""
echo "   • Check Task Dashboard:"
echo "     $API_URL/static/task-dashboard.html"
echo ""
echo "   • Check logs for errors:"
echo "     tail -f /tmp/transcription-service.log | grep -i error"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "✅ Diagnostic complete!"
echo ""

