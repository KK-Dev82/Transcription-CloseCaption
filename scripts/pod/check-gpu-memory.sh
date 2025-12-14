#!/bin/bash
# Script สำหรับตรวจสอบ GPU และ Memory Usage

PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || exit 1

echo "🔍 Checking GPU and Memory Status..."
echo "================================================"
echo ""

# 1. Check GPU
echo "1️⃣ GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader,nounits | while IFS=',' read -r name total used free util temp; do
        echo "   GPU: $name"
        echo "   Memory: ${used}MB / ${total}MB (Free: ${free}MB)"
        echo "   Utilization: ${util}%"
        echo "   Temperature: ${temp}°C"
    done
else
    echo "   ⚠️  nvidia-smi not found - GPU may not be available"
fi
echo ""

# 2. Check RAM
echo "2️⃣ RAM Status:"
free -h | grep -E "^Mem|^Swap"
echo ""

# 3. Check Top Memory Processes
echo "3️⃣ Top Memory Processes:"
ps aux --sort=-%mem | head -6 | awk 'NR==1 || $4>1.0 {printf "   %6s %6s %s\n", $4"%", $2, $11" "$12" "$13" "$14" "$15" "$16" "$17" "$18" "$19" "$20}'
echo ""

# 4. Check Video Worker
echo "4️⃣ Video Worker Status:"
if pgrep -f "python.*video_worker" > /dev/null; then
    WORKER_PID=$(pgrep -f "python.*video_worker" | head -1)
    echo "   ✅ Video Worker running (PID: $WORKER_PID)"
    WORKER_MEM=$(ps -p $WORKER_PID -o %mem,rss --no-headers 2>/dev/null | awk '{print $1"% ("$2/1024"MB)"}')
    echo "   Memory: $WORKER_MEM"
    
    # Check if worker is using GPU
    if command -v nvidia-smi &> /dev/null; then
        GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | grep "$WORKER_PID" || echo "")
        if [ -n "$GPU_PROCESSES" ]; then
            echo "   GPU Usage: $GPU_PROCESSES"
        else
            echo "   ⚠️  Worker not using GPU (may be using CPU instead)"
        fi
    fi
else
    echo "   ❌ Video Worker NOT running"
fi
echo ""

# 5. Check Environment Variables
echo "5️⃣ GPU Configuration:"
if [ -f ".env.runpod" ] || [ -f "env.runpod" ]; then
    ENV_FILE=".env.runpod"
    [ -f "env.runpod" ] && ENV_FILE="env.runpod"
    echo "   WHISPER_DEVICE: $(grep '^WHISPER_DEVICE=' $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo 'not set')"
    echo "   WHISPER_MODEL: $(grep '^WHISPER_MODEL=' $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo 'not set')"
    echo "   WHISPER_PROVIDER: $(grep '^WHISPER_PROVIDER=' $ENV_FILE 2>/dev/null | cut -d'=' -f2 || echo 'not set')"
else
    echo "   ⚠️  Environment file not found"
fi
echo ""

# 6. Check Recent Logs for GPU errors
echo "6️⃣ Recent GPU-related Logs:"
if [ -f "/tmp/video-worker.log" ]; then
    tail -30 /tmp/video-worker.log | grep -iE "(gpu|cuda|device|error|warning)" | tail -5 || echo "   No GPU-related messages found"
else
    echo "   ⚠️  Video Worker log not found"
fi
echo ""

echo "================================================"
echo "💡 Recommendations:"
if ! command -v nvidia-smi &> /dev/null; then
    echo "   ⚠️  GPU not detected - check if NVIDIA drivers are installed"
elif ! pgrep -f "python.*video_worker" > /dev/null; then
    echo "   ⚠️  Video Worker not running - restart it"
fi
echo ""
