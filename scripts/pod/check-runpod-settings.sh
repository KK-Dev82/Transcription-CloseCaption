#!/bin/bash
# Script สำหรับตรวจสอบ RunPod Settings และ Process Tree
# ใช้สำหรับหาต้นเหตุ SIGTERM

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 RunPod Settings & Process Tree Checker                   ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: ตรวจสอบ PID 1 และ Process Tree"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check PID 1
if [ -f /proc/1/cmdline ]; then
    PID1_CMD=$(cat /proc/1/cmdline | tr '\0' ' ')
    print_info "PID 1 Command: $PID1_CMD"
    
    # Check if worker is PID 1
    if echo "$PID1_CMD" | grep -qE "video_worker|app.workers"; then
        print_success "Worker is PID 1 (no wrapper)"
    else
        print_warning "Worker is NOT PID 1 (has wrapper)"
        echo "   → Wrapper: $PID1_CMD"
        echo "   → อาจมี idle timeout logic ใน wrapper"
    fi
else
    print_error "Cannot read /proc/1/cmdline"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: ตรวจสอบ Worker Process"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WORKER_PID=$(pgrep -f "app.workers.*video_worker" | head -1)
if [ -n "$WORKER_PID" ]; then
    print_success "Worker Process: RUNNING (PID: $WORKER_PID)"
    
    # Get parent PID
    PPID=$(ps -o ppid= -p "$WORKER_PID" 2>/dev/null | tr -d ' ' || echo "unknown")
    print_info "Parent PID: $PPID"
    
    # Get parent command
    if [ "$PPID" != "unknown" ] && [ -f "/proc/$PPID/cmdline" ]; then
        PARENT_CMD=$(cat "/proc/$PPID/cmdline" 2>/dev/null | tr '\0' ' ' || echo "unknown")
        print_info "Parent Command: $PARENT_CMD"
        
        if echo "$PARENT_CMD" | grep -qE "bash|sh|start|entrypoint"; then
            print_warning "Worker started by wrapper script"
            echo "   → Wrapper may have idle timeout logic"
        fi
    fi
    
    # Get worker command
    WORKER_CMD=$(ps -o cmd= -p "$WORKER_PID" 2>/dev/null || echo "unknown")
    print_info "Worker Command: $WORKER_CMD"
else
    print_error "Worker Process: NOT RUNNING"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: ตรวจสอบ Startup Scripts"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check /start.sh
if [ -f /start.sh ]; then
    print_info "Found /start.sh"
    echo "   First 20 lines:"
    head -20 /start.sh | sed 's/^/   /'
    
    # Check for idle timeout or auto-stop logic
    if grep -qE "timeout|idle|auto.stop|SIGTERM|kill" /start.sh; then
        print_warning "⚠️  /start.sh may have idle timeout/auto-stop logic"
        echo "   Lines containing timeout/idle/auto-stop:"
        grep -nE "timeout|idle|auto.stop|SIGTERM|kill" /start.sh | head -5 | sed 's/^/   /'
    else
        print_success "/start.sh ไม่มี idle timeout logic"
    fi
else
    print_info "/start.sh not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: ตรวจสอบ RunPod Environment Variables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check RunPod environment variables
if [ -n "$RUNPOD_POD_ID" ]; then
    print_info "RunPod Pod ID: $RUNPOD_POD_ID"
else
    print_warning "RUNPOD_POD_ID not set"
fi

if [ -n "$RUNPOD_CPU_COUNT" ]; then
    print_info "RunPod CPU Count: $RUNPOD_CPU_COUNT"
fi

# Check for auto-stop or idle timeout settings
if [ -n "$RUNPOD_AUTO_STOP" ]; then
    print_warning "RUNPOD_AUTO_STOP: $RUNPOD_AUTO_STOP"
fi

if [ -n "$RUNPOD_IDLE_TIMEOUT" ]; then
    print_warning "RUNPOD_IDLE_TIMEOUT: $RUNPOD_IDLE_TIMEOUT"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: คำแนะนำ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
print_info "📋 สิ่งที่ต้องตรวจสอบใน RunPod Dashboard:"
echo ""
echo "1. Pod Settings:"
echo "   - Auto stop / Stop after inactivity: ปิด หรือตั้งให้มากพอ"
echo "   - Idle timeout: ปิด หรือตั้งให้มากพอ (เช่น 1 ชั่วโมง)"
echo "   - Max execution time: ไม่จำกัด หรือตั้งให้มากพอ"
echo ""
echo "2. Billing/Funding:"
echo "   - ตรวจสอบยอดคงเหลือ (ต้องมากกว่า 1 ชั่วโมง)"
echo ""
echo "3. Pod Events:"
echo "   - ดูเหตุผล stop ใน Pod events"
echo "   - ตรวจสอบว่ามี 'stopped due to low balance' หรือไม่"
echo ""
echo "4. Pod Type:"
echo "   - ตรวจสอบว่าเป็น On-Demand Pod (ไม่ใช่ Serverless)"
echo "   - หลีกเลี่ยง Spot / Interruptible"
echo ""

print_warning "💡 ถ้า Worker ไม่ใช่ PID 1:"
echo "   - Wrapper script อาจมี idle timeout logic"
echo "   - ควรแก้ให้ worker เป็น PID 1 หรือแก้ wrapper script"
echo ""

print_success "✅ Check completed"


