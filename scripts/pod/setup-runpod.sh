#!/bin/bash
# Script สำหรับ Setup Transcription Service บน RunPod GPU Instance
#
# วิธีใช้งาน:
# 1. สร้าง RunPod Pod (GPU Template: PyTorch, CUDA 12.1)
# 2. SSH เข้าไปที่ Pod
# 3. Clone repository: git clone <repo-url> /workspace/transcription-service
# 4. รัน: bash /workspace/transcription-service/scripts/pod/setup-runpod.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Starting RunPod Setup for Transcription Service..."
echo "📁 Project Root: $PROJECT_ROOT"

# Check if running on RunPod
if [ -z "$RUNPOD_POD_ID" ]; then
    echo "⚠️  Warning: RUNPOD_POD_ID not set. Continuing anyway..."
fi

# Check GPU availability
echo "🔍 Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo "✅ Found $GPU_COUNT GPU(s)"
else
    echo "❌ nvidia-smi not found. GPU may not be available."
    exit 1
fi

# Check Docker and nvidia-docker
echo "🔍 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# Check if nvidia-docker runtime is available
if ! docker info | grep -q "nvidia"; then
    echo "⚠️  Warning: nvidia-docker runtime may not be configured."
    echo "   RunPod should have this pre-configured, but checking anyway..."
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p "$PROJECT_ROOT/uploads"
mkdir -p "$PROJECT_ROOT/storage/transcriptions"
mkdir -p "$PROJECT_ROOT/storage/metadata"
mkdir -p "$PROJECT_ROOT/storage/captions"
mkdir -p "$PROJECT_ROOT/temp"
mkdir -p "$PROJECT_ROOT/models"

# Set permissions
chmod -R 755 "$PROJECT_ROOT/uploads"
chmod -R 755 "$PROJECT_ROOT/storage"
chmod -R 755 "$PROJECT_ROOT/temp"

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env.runpod" ]; then
    echo "📝 Creating .env.runpod file..."
    cat > "$PROJECT_ROOT/.env.runpod" << EOF
# RunPod Environment Configuration
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/app/storage

# RabbitMQ Configuration
# สำหรับ Local Testing: ใช้ localhost (ผ่าน SSH Tunnel จาก MacOS)
# ⚠️ ต้องตั้งค่า SSH Tunnel ก่อน: ssh -L 5672:localhost:5672 root@<runpod-ip> -p <port> -N
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

# Redis Configuration
# ใช้ local container (เหมือน staging/local) - ไม่ต้องใช้ SSH Tunnel
REDIS_URL=redis://redis:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_FALLBACK_ENABLED=false
WHISPER_API_URL=http://whisper:8002

# Groq API (optional - for fallback)
GROQ_API_KEY=

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    echo "✅ Created .env.runpod file"
else
    echo "✅ .env.runpod file already exists"
fi

# Build Docker images
echo "🔨 Building Docker images..."
cd "$PROJECT_ROOT"

# Pull main API image จาก ACR (เหมือน staging)
echo "📦 Pulling main API image from ACR..."
if docker pull kksenateacr.azurecr.io/kk-transcription:alpha-dev 2>/dev/null; then
    echo "✅ Main API image pulled from ACR"
else
    echo "⚠️  Failed to pull from ACR, will build locally"
    echo "💡 Tip: Login to ACR first: az acr login --name kksenateacr"
    docker build -t kksenateacr.azurecr.io/kk-transcription:alpha-dev .
fi

# Build Whisper GPU image (ACR ไม่มี GPU image - ต้อง build)
echo "📦 Building Whisper GPU image (with CUDA support)..."
cd "$PROJECT_ROOT/whisper-service"
docker build -f Dockerfile.gpu -t kk-transcription-whisper:runpod-gpu .

cd "$PROJECT_ROOT"

# Start services
echo "🚀 Starting services with Docker Compose..."
echo "💡 Make sure SSH Tunnel is running: ssh -L 5672:localhost:5672 ..."
docker compose -f docker-compose.runpod.yml --env-file .env.runpod up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker compose -f docker-compose.runpod.yml ps

# Test API health
echo "🏥 Testing API health..."
sleep 5
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ API is healthy"
else
    echo "⚠️  API health check failed. Check logs: docker compose -f docker-compose.runpod.yml logs api"
fi

# Test Whisper health
echo "🏥 Testing Whisper health..."
if curl -f http://localhost:8002/health > /dev/null 2>&1; then
    echo "✅ Whisper service is healthy"
else
    echo "⚠️  Whisper health check failed. Check logs: docker compose -f docker-compose.runpod.yml logs whisper"
fi

# Display GPU usage
echo "🎮 GPU Usage:"
nvidia-smi

echo ""
echo "✅ RunPod setup completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Check logs: docker compose -f docker-compose.runpod.yml logs -f"
echo "   2. Test transcription: curl -X POST http://localhost:8001/api/transcription/upload"
echo "   3. Monitor GPU: watch -n 1 nvidia-smi"
echo ""
echo "🌐 Exposed ports:"
echo "   - API: http://localhost:8001"
echo "   - Whisper: http://localhost:8002"
echo ""
echo "💡 To stop services: docker compose -f docker-compose.runpod.yml down"
echo "💡 To restart: docker compose -f docker-compose.runpod.yml restart"

