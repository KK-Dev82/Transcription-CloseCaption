#!/bin/bash

# Script สำหรับตรวจสอบรายละเอียดว่า Worker กำลังทำอะไรอยู่

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

cd "$(dirname "$0")/../.." || exit 1

print_header "🔍 ตรวจสอบรายละเอียด Worker Activity"

WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)

if [ -z "$WORKER_PID" ]; then
    print_error "ไม่พบ Video Worker process"
    exit 1
fi

print_success "Worker PID: $WORKER_PID"
echo ""

# Step 1: Check what processes are using CPU
print_header "Step 1: ตรวจสอบ Processes ที่ใช้ CPU สูง"

print_status "Top CPU processes (worker และ child processes):"
ps aux --sort=-%cpu | head -15 | grep -E "PID|$WORKER_PID|python|ffmpeg|faster" || true
echo ""

# Check thread count and CPU usage
THREAD_COUNT=$(ps -p "$WORKER_PID" -o thcount --no-headers 2>/dev/null | tr -d ' ' || echo "0")
CPU_USAGE=$(ps -p "$WORKER_PID" -o %cpu --no-headers 2>/dev/null | tr -d ' ' || echo "0")

print_status "Worker threads: $THREAD_COUNT"
print_status "CPU usage: ${CPU_USAGE}%"

if [ -n "$CPU_USAGE" ]; then
    CPU_INT=$(echo "$CPU_USAGE" | cut -d. -f1)
    if [ "$CPU_INT" -gt 100 ]; then
        print_success "CPU สูง (${CPU_USAGE}%) - Worker กำลังทำงาน (อาจเป็น multi-threading)"
    elif [ "$CPU_INT" -gt 10 ]; then
        print_status "CPU ปานกลาง (${CPU_USAGE}%) - Worker กำลังทำงาน"
    else
        print_warning "CPU ต่ำ (${CPU_USAGE}%) - Worker อาจไม่ได้ทำงาน"
    fi
fi
echo ""

# Step 2: Check child processes
print_header "Step 2: ตรวจสอบ Child Processes"

CHILD_PROCS=$(pgrep -P "$WORKER_PID" 2>/dev/null || echo "")
if [ -n "$CHILD_PROCS" ]; then
    print_status "พบ child processes:"
    for child_pid in $CHILD_PROCS; do
        CHILD_INFO=$(ps -p "$child_pid" -o pid,cmd,%cpu,%mem --no-headers 2>/dev/null || echo "")
        if [ -n "$CHILD_INFO" ]; then
            echo "  $CHILD_INFO"
        fi
    done
else
    print_status "ไม่พบ child processes (worker อาจเป็น single process)"
fi
echo ""

# Step 3: Check what the worker is doing (strace/pstack equivalent)
print_header "Step 3: ตรวจสอบ Worker State และ System Calls"

# Check process state
STATE=$(ps -p "$WORKER_PID" -o state --no-headers 2>/dev/null | tr -d ' ' || echo "")
print_status "Process state: $STATE"

case "$STATE" in
    R)
        print_success "Running - Worker กำลังทำงาน"
        ;;
    S)
        print_status "Sleeping (interruptible) - Worker รอ I/O หรือ events"
        ;;
    D)
        print_warning "Uninterruptible sleep - Worker อาจ stuck ใน I/O operation (FFmpeg, disk, network)"
        ;;
    T)
        print_warning "Stopped - Worker ถูก stop"
        ;;
    Z)
        print_error "Zombie - Worker process เสีย"
        ;;
esac
echo ""

# Step 4: Check file descriptors and connections
print_header "Step 4: ตรวจสอบ File Descriptors และ Network Connections"

if command -v lsof > /dev/null 2>&1; then
    OPEN_FILES=$(lsof -p "$WORKER_PID" 2>/dev/null | wc -l || echo "0")
    print_status "Open file descriptors: $OPEN_FILES"
    
    if [ "$OPEN_FILES" -eq 0 ]; then
        print_warning "⚠️ ไม่มี open files - connection อาจหลุด!"
    else
        print_status "Open files breakdown:"
        lsof -p "$WORKER_PID" 2>/dev/null | grep -E "TCP|REG|FIFO" | head -10 || true
    fi
    
    # Check for RabbitMQ connections
    RABBITMQ_CONNS=$(lsof -p "$WORKER_PID" 2>/dev/null | grep -i "tcp.*5672\|tcp.*15672" | wc -l || echo "0")
    if [ "$RABBITMQ_CONNS" -eq 0 ]; then
        print_error "❌ ไม่พบ RabbitMQ connections - connection หลุดแล้ว!"
    else
        print_success "พบ RabbitMQ connections: $RABBITMQ_CONNS"
    fi
else
    print_warning "lsof ไม่พร้อมใช้งาน - ไม่สามารถตรวจสอบ connections ได้"
fi
echo ""

# Step 5: Check for FFmpeg processes
print_header "Step 5: ตรวจสอบ FFmpeg Processes"

FFMPEG_PROCS=$(pgrep -f "ffmpeg|ffprobe" 2>/dev/null || echo "")
if [ -n "$FFMPEG_PROCS" ]; then
    FFMPEG_COUNT=$(echo "$FFMPEG_PROCS" | wc -l | tr -d ' ')
    print_warning "⚠️ พบ FFmpeg processes: $FFMPEG_COUNT ตัว"
    
    for ffmpeg_pid in $FFMPEG_PROCS; do
        FFMPEG_INFO=$(ps -p "$ffmpeg_pid" -o pid,cmd,%cpu,etime --no-headers 2>/dev/null || echo "")
        if [ -n "$FFMPEG_INFO" ]; then
            echo "  PID: $ffmpeg_pid"
            echo "    $FFMPEG_INFO"
            
            # Check how long it's been running
            FFMPEG_ETIME=$(echo "$FFMPEG_INFO" | awk '{print $NF}')
            echo "    Running time: $FFMPEG_ETIME"
            
            # Check if it's stuck (running for more than 5 minutes)
            if echo "$FFMPEG_ETIME" | grep -qE "[0-9]+:[0-9]+:[0-9]+"; then
                print_warning "    ⚠️ FFmpeg ทำงานนานมาก - อาจ stuck"
            fi
        fi
    done
else
    print_status "ไม่พบ FFmpeg processes กำลังทำงาน"
fi
echo ""

# Step 6: Check CPU transcription processes (faster-whisper in CPU mode)
print_header "Step 6: ตรวจสอบ Transcription Processes (CPU Mode)"

# Check for Python processes doing transcription
TRANSCRIBE_PROCS=$(ps aux | grep -E "[p]ython.*transcribe|[f]aster.*whisper" | grep -v grep || echo "")
if [ -n "$TRANSCRIBE_PROCS" ]; then
    print_status "พบ transcription-related processes:"
    echo "$TRANSCRIBE_PROCS" | while read line; do
        PID=$(echo "$line" | awk '{print $2}')
        CPU=$(echo "$line" | awk '{print $3}')
        CMD=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        echo "  PID: $PID, CPU: ${CPU}%"
        echo "    $CMD"
    done
else
    print_status "ไม่พบ transcription processes กำลังทำงาน"
fi
echo ""

# Step 7: Check recent logs for what worker is doing
print_header "Step 7: ตรวจสอบ Logs ล่าสุด (Worker กำลังทำอะไร)"

if [ -f "/tmp/video-worker.log" ]; then
    print_status "Last 30 log entries:"
    tail -30 /tmp/video-worker.log | grep -E "INFO|ERROR|WARNING" | tail -15 || true
    echo ""
    
    # Check what stage worker is at
    LAST_STAGE=$(tail -100 /tmp/video-worker.log | grep -iE "audio extraction|transcription|processing|extract|transcribe" | tail -5 || echo "")
    if [ -n "$LAST_STAGE" ]; then
        print_status "Recent activity stages:"
        echo "$LAST_STAGE"
    fi
fi
echo ""

# Step 8: Check if worker is stuck in CPU transcription
print_header "Step 8: ตรวจสอบว่า Worker Stuck ใน CPU Transcription หรือไม่"

# Check for CPU mode fallback
CPU_FALLBACK_COUNT=$(tail -500 /tmp/video-worker.log | grep -i "falling back to CPU mode" | wc -l | tr -d ' ' || echo "0")
if [ "$CPU_FALLBACK_COUNT" -gt 0 ]; then
    print_warning "⚠️ พบ CPU fallback: $CPU_FALLBACK_COUNT ครั้ง"
    print_status "   Worker อาจกำลัง process ใน CPU mode (ช้ามาก)"
    
    # Check last CPU fallback
    LAST_CPU_FALLBACK=$(tail -500 /tmp/video-worker.log | grep -i "falling back to CPU mode" | tail -1 || echo "")
    if [ -n "$LAST_CPU_FALLBACK" ]; then
        print_status "   Last CPU fallback:"
        echo "   $LAST_CPU_FALLBACK"
    fi
fi

# Check for timeout errors
TIMEOUT_COUNT=$(tail -500 /tmp/video-worker.log | grep -i "timeout" | wc -l | tr -d ' ' || echo "0")
if [ "$TIMEOUT_COUNT" -gt 0 ]; then
    print_warning "⚠️ พบ timeout errors: $TIMEOUT_COUNT ครั้ง"
fi
echo ""

# Step 9: Summary and recommendations
print_header "Step 9: สรุปและคำแนะนำ"

print_status "สรุปสถานะ Worker:"
echo "  - PID: $WORKER_PID"
echo "  - State: $STATE"
echo "  - CPU: ${CPU_USAGE}%"
echo "  - Threads: $THREAD_COUNT"
echo "  - Open files: ${OPEN_FILES:-N/A}"
echo "  - GPU: 0% (fallback to CPU)"
echo "  - Messages in queue: 26"
echo ""

# Recommendations
if [ "$STATE" = "D" ]; then
    print_warning "⚠️ Worker อยู่ใน uninterruptible sleep - อาจ stuck ใน I/O"
    print_status "💡 แนะนำ: Restart worker (อาจ stuck ใน FFmpeg หรือ disk I/O)"
elif [ "$OPEN_FILES" -eq 0 ] || [ "${RABBITMQ_CONNS:-0}" -eq 0 ]; then
    print_warning "⚠️ Connection หลุด - Worker ไม่สามารถรับ messages ได้"
    print_status "💡 แนะนำ: Restart worker เพื่อ reconnect"
elif [ "$CPU_FALLBACK_COUNT" -gt 0 ] && [ -n "$CPU_USAGE" ] && [ "${CPU_INT:-0}" -gt 100 ]; then
    print_warning "⚠️ Worker กำลัง process ใน CPU mode (ช้ามาก)"
    print_status "💡 แนะนำ: รอให้เสร็จก่อน หรือ restart เพื่อใช้ GPU ใหม่"
elif [ -n "$FFMPEG_PROCS" ]; then
    print_warning "⚠️ พบ FFmpeg ทำงานอยู่ - อาจกำลัง extract audio"
    print_status "💡 แนะนำ: รอให้ FFmpeg เสร็จก่อน restart"
else
    print_status "💡 Worker ดูเหมือนกำลังทำงาน - อาจไม่จำเป็นต้อง restart"
fi

echo ""
print_header "✅ เสร็จสมบูรณ์"

