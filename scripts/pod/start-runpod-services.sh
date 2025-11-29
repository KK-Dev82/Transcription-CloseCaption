#!/bin/bash
# Script สำหรับ Start Services ใน Custom Base Image
# ใช้ได้ทั้ง RunPod และ HP Z2 Workstation

set -e

echo "🚀 Starting Transcription Services..."
echo "📅 $(date)"

# Check GPU availability
echo "🔍 Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo "✅ Found $GPU_COUNT GPU(s)"
else
    echo "⚠️  Warning: nvidia-smi not found. GPU may not be available."
fi

# Start Docker daemon (ถ้ายังไม่ทำงาน)
echo "🔍 Checking Docker..."
if ! docker ps &> /dev/null; then
    echo "📦 Starting Docker daemon..."
    dockerd > /tmp/dockerd.log 2>&1 &
    sleep 5
    
    # Wait for Docker to be ready
    for i in {1..30}; do
        if docker ps &> /dev/null; then
            echo "✅ Docker daemon started"
            break
        fi
        sleep 1
    done
else
    echo "✅ Docker daemon already running"
fi

# Check if repository exists
if [ ! -d "/workspace/transcription-service" ]; then
    echo "⚠️  Repository not found at /workspace/transcription-service"
    echo "💡 Please clone repository first:"
    echo "   git clone <repo-url> /workspace/transcription-service"
    echo ""
    echo "⏳ Waiting for repository..."
    # Keep container running
    tail -f /dev/null
    exit 0
fi

cd /workspace/transcription-service

# Check if .env file exists
if [ ! -f ".env.runpod" ]; then
    echo "📝 Creating .env.runpod file..."
    cat > .env.runpod << EOF
# Environment Configuration
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/app/storage

# RabbitMQ Configuration
# สำหรับ Local Testing: ใช้ localhost (ผ่าน SSH Tunnel)
# สำหรับ Staging: ใช้ IP ของ Backend server
RABBITMQ_HOST=\${RABBITMQ_HOST:-localhost}
RABBITMQ_PORT=\${RABBITMQ_PORT:-5672}
RABBITMQ_USER=\${RABBITMQ_USER:-senate}
RABBITMQ_PASSWORD=\${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}

# Redis Configuration
REDIS_URL=\${REDIS_URL:-redis://redis:6379}

# Whisper Configuration
WHISPER_PROVIDER=\${WHISPER_PROVIDER:-builtin}
WHISPER_FALLBACK_ENABLED=\${WHISPER_FALLBACK_ENABLED:-false}
WHISPER_API_URL=http://whisper:8002

# Groq API (optional)
GROQ_API_KEY=\${GROQ_API_KEY:-}

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    echo "✅ Created .env.runpod file"
fi

# Login ACR (ถ้ามี credentials)
if [ -n "$ACR_USERNAME" ] && [ -n "$ACR_PASSWORD" ]; then
    echo "🔐 Logging in to ACR..."
    echo "$ACR_PASSWORD" | docker login kksenateacr.azurecr.io -u "$ACR_USERNAME" --password-stdin || true
fi

# Pull images from ACR
echo "📦 Pulling images from ACR..."
if docker pull kksenateacr.azurecr.io/kk-transcription:alpha-dev 2>/dev/null; then
    echo "✅ Main API image pulled"
else
    echo "⚠️  Failed to pull from ACR. Will try to build locally..."
fi

# Build Whisper GPU image (ถ้ายังไม่มี)
if ! docker images | grep -q "kk-transcription-whisper:runpod-gpu"; then
    echo "📦 Building Whisper GPU image..."
    cd whisper-service
    docker build -f Dockerfile.gpu -t kk-transcription-whisper:runpod-gpu . || {
        echo "⚠️  Failed to build Whisper image. Continuing..."
    }
    cd ..
fi

# Start services with Docker Compose
echo "🚀 Starting services with Docker Compose..."
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
nvidia-smi || echo "⚠️  nvidia-smi not available"

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📋 Useful commands:"
echo "   - Check logs: docker compose -f docker-compose.runpod.yml logs -f"
echo "   - Check status: docker compose -f docker-compose.runpod.yml ps"
echo "   - Stop services: docker compose -f docker-compose.runpod.yml down"
echo ""
echo "🌐 Exposed ports:"
echo "   - API: http://localhost:8001"
echo "   - Whisper: http://localhost:8002"
echo "   - Redis: localhost:6379"
echo ""

# Keep container running
tail -f /dev/null

