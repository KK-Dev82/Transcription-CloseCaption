#!/usr/bin/env bash
# Script สำหรับ Start Services แบบ Direct Mode (ไม่ใช้ Docker Compose)
# ใช้บน RunPod/HP Z2 ที่ใช้ Custom Base Image

set -euo pipefail

# ป้องกัน CT2 freeze + จำกัด threads
export CT2_USE_CUDA_GRAPH=${CT2_USE_CUDA_GRAPH:-0}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-4}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-4}
export NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-0}

echo "=========================================="
echo "🚀 Starting Services (Direct Mode)"
echo "=========================================="
echo ""

# GPU Info
echo "=== GPU Info ==="
nvidia-smi || echo "⚠️  nvidia-smi not available"
echo ""

# Check CUDA/PyTorch/CTranslate2
echo "=== Environment Check ==="
python3 - <<'PY'
import torch
try:
    import ctranslate2
    print(f"✅ torch: {torch.__version__}")
    print(f"✅ torch cuda: {torch.version.cuda}")
    print(f"✅ CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    print(f"✅ ctranslate2: {ctranslate2.__version__}")
    try:
        ct2_cuda = ctranslate2.get_cuda_version()
        print(f"✅ ctranslate2 CUDA: {ct2_cuda}")
    except:
        print("⚠️  ctranslate2.get_cuda_version() not available")
except ImportError as e:
    print(f"❌ Import error: {e}")
PY
echo ""

# Change to project directory
PROJECT_DIR="/workspace/transcription-service"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PROJECT_DIR"
    echo "   Please clone repository first:"
    echo "   cd /workspace && git clone <repo-url> transcription-service"
    exit 1
fi

cd "$PROJECT_DIR"

# ติดตั้ง dependencies เสริมใน repo (ถ้ามี requirements.txt)
if [ -f "requirements.txt" ]; then
    echo "=== Installing additional dependencies ==="
    pip3 install --no-cache-dir -r requirements.txt || echo "⚠️  Some dependencies failed to install"
    echo ""
fi

# เตรียมโฟลเดอร์
echo "=== Preparing directories ==="
mkdir -p uploads storage temp models test-files
echo "✅ Directories ready"
echo ""

# แปลงไฟล์ตัวอย่าง (ถ้ามี) - กัน codec/stream แปลก
if [ -f "sample.mp4" ] || [ -f "uploads/sample.mp4" ]; then
    SAMPLE_FILE="sample.mp4"
    [ -f "uploads/sample.mp4" ] && SAMPLE_FILE="uploads/sample.mp4"
    echo "=== Converting sample file ==="
    ffmpeg -y -i "$SAMPLE_FILE" -ac 1 -ar 16000 temp/sample_16k.wav 2>&1 | tail -3 || echo "⚠️  Sample conversion failed"
    echo ""
fi

# Start Redis (ถ้ายังไม่รัน)
echo "=== Starting Redis ==="
if pgrep -x "redis-server" > /dev/null; then
    echo "✅ Redis already running"
else
    redis-server --daemonize yes --port 6379 --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru || {
        echo "⚠️  Redis failed to start (may already be running)"
    }
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis started"
    else
        echo "⚠️  Redis not responding"
    fi
fi
echo ""

# Load environment variables
if [ -f ".env.runpod" ]; then
    echo "=== Loading .env.runpod ==="
    set -a
    source .env.runpod
    set +a
    echo "✅ Environment loaded"
    echo ""
fi

# Start Main API
echo "=== Starting Main API ==="
echo "📡 API will be available at: http://0.0.0.0:8001"
echo "📋 Health check: http://0.0.0.0:8001/health"
echo ""
echo "🚀 Starting uvicorn..."
echo ""

# รัน API (foreground)
exec uvicorn app.main:app --host 0.0.0.0 --port 8001

