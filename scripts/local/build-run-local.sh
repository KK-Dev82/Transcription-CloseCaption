#!/bin/bash

# Build and Run Transcription Docker Service (Local Development)
# Usage: ./scripts/build-run-local.sh

set -e

cd "$(dirname "$0")/.."

echo "=========================================="
echo "Build and Run Transcription Service (Local)"
echo "=========================================="
echo ""

# Step 1: Build Main API Image
echo "Building Main API Image: kk-transcription:local-dev"
docker build \
    -f Dockerfile \
    -t kk-transcription:local-dev \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .

echo ""
echo "✅ Main API Image build completed!"
echo ""

# Step 2: Build Whisper Service Image
echo "Building Whisper Service Image: kk-transcription-whisper:local-dev"
cd whisper-service

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "Detected ARM64 architecture, using Dockerfile.arm64"
    docker build \
        -f Dockerfile.arm64 \
        -t kk-transcription-whisper:local-dev \
        .
else
    echo "Detected x86_64 architecture, using Dockerfile.linux"
    docker build \
        -f Dockerfile.linux \
        -t kk-transcription-whisper:local-dev \
        .
fi

cd ..

echo ""
echo "✅ Whisper Service Image build completed!"
echo ""

# Step 3: Check images
echo "Checking built images..."
docker images | grep -E "(kk-transcription|kk-transcription-whisper)" || echo "  No images found"

echo ""

# Step 4: Start services (docker-compose จะ build image ใหม่ถ้ายังไม่มี)
echo "Starting services..."
docker-compose -f docker-compose.local.yml up -d --build

echo ""
echo "✅ Services started!"
echo ""
echo "Service status:"
docker ps | grep -E "(transcription|whisper|redis)" || echo "  Services not running"
echo ""
echo "Access:"
echo "  API:       http://localhost:8001"
echo "  Health:    http://localhost:8001/health"
echo "  Dashboard: http://localhost:8001/dashboard"
echo ""
echo "View logs:"
echo "  docker-compose -f docker-compose.local.yml logs -f"
echo ""
echo "Stop services:"
echo "  docker-compose -f docker-compose.local.yml down"
echo ""

