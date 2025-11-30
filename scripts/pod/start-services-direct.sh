#!/bin/bash
# Script สำหรับ Start Services โดยตรงใน Container (ไม่ใช้ Docker Compose)
# ใช้สำหรับ Custom Base Image บน RunPod Pod Container
#
# วิธีใช้งาน:
# - ใช้เป็น CMD ใน Dockerfile.runpod-base
# - หรือรันด้วยตนเอง: bash scripts/pod/start-services-direct.sh

set -e

echo "🚀 Starting Transcription Services (Direct Mode)..."
echo "📅 $(date)"
echo ""

# Check GPU availability
echo "🔍 Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo "✅ Found $GPU_COUNT GPU(s)"
else
    echo "⚠️  Warning: nvidia-smi not found. GPU may not be available."
fi
echo ""

# Check if repository exists
if [ ! -d "/workspace/transcription-service" ]; then
    echo "⚠️  Repository not found at /workspace/transcription-service"
    echo "💡 Please clone repository first:"
    echo "   cd /workspace"
    echo "   git clone <repo-url> transcription-service"
    echo ""
    echo "⏳ Waiting for repository..."
    # Keep container running
    tail -f /dev/null
    exit 0
fi

cd /workspace/transcription-service

# Load environment variables
if [ -f ".env.runpod" ]; then
    echo "📝 Loading .env.runpod..."
    set -a
    source .env.runpod
    set +a
else
    echo "📝 Creating .env.runpod file..."
    cat > .env.runpod << EOF
# Environment Configuration
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# RabbitMQ Configuration
# สำหรับ Local Testing: ใช้ localhost (ผ่าน SSH Tunnel)
# สำหรับ Staging: ใช้ IP ของ Backend server
RABBITMQ_HOST=\${RABBITMQ_HOST:-localhost}
RABBITMQ_PORT=\${RABBITMQ_PORT:-5672}
RABBITMQ_USER=\${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=\${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

# Redis Configuration (local)
REDIS_URL=\${REDIS_URL:-redis://localhost:6379}

# Whisper Configuration
WHISPER_PROVIDER=\${WHISPER_PROVIDER:-builtin}
WHISPER_FALLBACK_ENABLED=\${WHISPER_FALLBACK_ENABLED:-false}
WHISPER_API_URL=http://localhost:8002

# Groq API (optional)
GROQ_API_KEY=\${GROQ_API_KEY:-}

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    set -a
    source .env.runpod
    set +a
    echo "✅ Created .env.runpod file"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    echo "📦 Installing from requirements.txt..."
    pip3 install --no-cache-dir -r requirements.txt || {
        echo "⚠️  Some packages failed to install, trying essential packages..."
        pip3 install --no-cache-dir \
            fastapi==0.104.1 \
            uvicorn[standard]==0.24.0 \
            pydantic==2.5.0 \
            requests==2.31.0 \
            aiohttp==3.9.1 \
            aiofiles==23.2.1 \
            redis==5.0.1 \
            pika==1.3.2 \
            python-dotenv==1.0.0 \
            pythainlp==4.0.2 \
            psutil==5.9.6 \
            python-multipart==0.0.6 \
            websockets==12.0 \
            tzdata
    }
else
    echo "⚠️  requirements.txt not found, installing basic dependencies..."
    pip3 install --no-cache-dir \
        fastapi==0.104.1 \
        uvicorn[standard]==0.24.0 \
        pydantic==2.5.0 \
        requests==2.31.0 \
        aiohttp==3.9.1 \
        aiofiles==23.2.1 \
        redis==5.0.1 \
        pika==1.3.2 \
        python-dotenv==1.0.0 \
        pythainlp==4.0.2 \
        psutil==5.9.6 \
        python-multipart==0.0.6 \
        websockets==12.0 \
        tzdata
fi

# Install tzdata (required for pythainlp timezone support)
echo "📦 Installing tzdata (required for pythainlp)..."
pip3 install --no-cache-dir tzdata || {
    echo "⚠️  Failed to install tzdata. Trying system package..."
    apt-get update && apt-get install -y tzdata || echo "⚠️  Failed to install tzdata"
}

echo "✅ Python dependencies installed"

# Install Whisper dependencies
echo "📦 Checking Whisper dependencies..."
if [ -d "whisper-service" ]; then
    cd whisper-service
    if [ -f "requirements.txt" ]; then
        pip3 install --no-cache-dir -r requirements.txt || true
    fi
    cd ..
fi

# Download Whisper models (ถ้ายังไม่มี)
echo "📦 Checking Whisper models..."
if [ ! -f "models/ggml-base.bin" ]; then
    echo "📥 Downloading Whisper models..."
    mkdir -p models
    
    # Download base model
    if [ -d "whisper-service" ] && [ -f "whisper-service/models/download-ggml-model.sh" ]; then
        cd whisper-service
        bash models/download-ggml-model.sh base || echo "⚠️  Failed to download base model"
        cp models/ggml-base.bin ../models/ 2>/dev/null || true
        cd ..
    else
        echo "⚠️  Whisper models download script not found"
    fi
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p uploads storage/transcriptions storage/metadata storage/captions temp models test-files
echo "✅ Directories created"
echo ""

# Start Redis (background)
echo "🔴 Starting Redis..."
if command -v redis-server &> /dev/null; then
    redis-server --daemonize yes --port 6379 --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru || {
        echo "⚠️  Redis already running or failed to start"
    }
    sleep 2
    echo "✅ Redis started"
else
    echo "⚠️  redis-server not found. Skipping Redis..."
fi
echo ""

# Start Whisper API (background)
echo "🎤 Starting Whisper API..."
cd whisper-service
if [ -f "whisper_api.py" ]; then
    # Set environment for Whisper
    export WHISPER_MODEL_PATH=/workspace/transcription-service/models
    export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
    export WHISPER_CUBLAS=1
    
    # Start Whisper API in background
    nohup python3 whisper_api.py > /tmp/whisper.log 2>&1 &
    WHISPER_PID=$!
    echo "✅ Whisper API started (PID: $WHISPER_PID)"
    
    # Wait for Whisper API to be ready
    echo "⏳ Waiting for Whisper API to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:8002/health > /dev/null 2>&1; then
            echo "✅ Whisper API is ready"
            break
        fi
        sleep 1
    done
    
    if ! curl -f http://localhost:8002/health > /dev/null 2>&1; then
        echo "⚠️  Whisper API health check failed. Check logs: tail -f /tmp/whisper.log"
    fi
else
    echo "⚠️  whisper_api.py not found"
    WHISPER_PID=""
fi
cd ..
echo ""

# Start Video Worker (background)
echo "🎬 Starting Video Worker..."
if [ -f "app/workers/video_worker.py" ]; then
    export PYTHONPATH=/workspace/transcription-service
    nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 &
    VIDEO_WORKER_PID=$!
    echo "✅ Video Worker started (PID: $VIDEO_WORKER_PID)"
    sleep 2
else
    echo "⚠️  video_worker.py not found"
    VIDEO_WORKER_PID=""
fi
echo ""

# Start Main API (background - ใช้ nohup เพื่อไม่ให้ปิดเมื่อออกจาก terminal)
echo "🚀 Starting Main API..."
if [ -f "app/main.py" ]; then
    export PYTHONPATH=/workspace/transcription-service
    
    # Start Main API in background with nohup
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/main-api.log 2>&1 &
    MAIN_API_PID=$!
    echo "✅ Main API started (PID: $MAIN_API_PID)"
    
    # Wait for Main API to be ready
    echo "⏳ Waiting for Main API to be ready..."
    sleep 3
    for i in {1..30}; do
        if curl -f http://localhost:8001/health > /dev/null 2>&1; then
            echo "✅ Main API is ready"
            break
        fi
        sleep 1
    done
    
    if ! curl -f http://localhost:8001/health > /dev/null 2>&1; then
        echo "⚠️  Main API health check failed. Check logs: tail -f /tmp/main-api.log"
    fi
    
    echo ""
    echo "📋 Service Status:"
    echo "   - Redis: Running on port 6379"
    if [ -n "$WHISPER_PID" ]; then
        echo "   - Whisper API: Running on port 8002 (PID: $WHISPER_PID)"
    else
        echo "   - Whisper API: Not started"
    fi
    if [ -n "$VIDEO_WORKER_PID" ]; then
        echo "   - Video Worker: Running (PID: $VIDEO_WORKER_PID)"
    else
        echo "   - Video Worker: Not started"
    fi
    if [ -n "$MAIN_API_PID" ]; then
        echo "   - Main API: Running on port 8001 (PID: $MAIN_API_PID)"
    else
        echo "   - Main API: Not started"
    fi
    echo ""
    echo "🌐 Exposed ports:"
    echo "   - API: http://localhost:8001"
    echo "   - Whisper: http://localhost:8002"
    echo "   - Redis: localhost:6379"
    echo ""
    echo "📋 Useful commands:"
    echo "   - Check logs: tail -f /tmp/main-api.log /tmp/whisper.log /tmp/video-worker.log"
    echo "   - Check API: curl http://localhost:8001/health"
    echo "   - Check Whisper: curl http://localhost:8002/health"
    echo "   - Monitor GPU: watch -n 1 nvidia-smi"
    echo "   - Stop services: pkill -f 'python.*uvicorn.*app.main' && pkill -f 'python.*whisper_api' && pkill -f 'python.*video_worker' && pkill -f redis-server"
    echo ""
    echo "✅ All services started in background!"
    echo "💡 Services will continue running even if you exit the terminal"
    echo ""
    
    # Setup signal handler to prevent Ctrl+C from killing services
    trap 'echo ""; echo "⚠️  Received interrupt signal. Services will continue running in background."; echo "💡 To stop services, run: bash scripts/pod/stop-services.sh"; exit 0' INT TERM
    
    # Keep container running (wait for processes) - non-blocking
    echo "⏳ Monitoring services... (Press Ctrl+C to exit - services will continue running)"
    echo ""
    
    # Background monitoring (non-blocking)
    (
        while true; do
            sleep 30
            # Check if processes are still running
            if [ -n "$MAIN_API_PID" ] && ! kill -0 $MAIN_API_PID 2>/dev/null; then
                echo "⚠️  Main API process died. Check logs: tail -f /tmp/main-api.log"
            fi
            if [ -n "$WHISPER_PID" ] && ! kill -0 $WHISPER_PID 2>/dev/null; then
                echo "⚠️  Whisper API process died. Check logs: tail -f /tmp/whisper.log"
            fi
            if [ -n "$VIDEO_WORKER_PID" ] && ! kill -0 $VIDEO_WORKER_PID 2>/dev/null; then
                echo "⚠️  Video Worker process died. Check logs: tail -f /tmp/video-worker.log"
            fi
        done
    ) &
    MONITOR_PID=$!
    
    # Keep main process alive (but allow Ctrl+C to exit gracefully)
    tail -f /dev/null
else
    echo "❌ app/main.py not found"
    echo "⏳ Keeping container running..."
    tail -f /dev/null
fi

