#!/bin/bash
# Script สำหรับ Build และ Push Custom Base Image ไป ACR
#
# วิธีใช้งาน:
# 1. Login ACR: az acr login --name kksenateacr
# 2. รัน: bash scripts/pod/build-and-push-runpod-base.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔨 Building Custom Base Image for RunPod/Z2..."
echo "📁 Project Root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# Build image (use --platform for cross-platform build)
echo "📦 Building image..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "⚠️  Detected ARM64 architecture, using --platform=linux/amd64"
    docker build --platform=linux/amd64 -f Dockerfile.runpod-base -t kksenateacr.azurecr.io/kk-transcription-runpod-base:latest .
else
    docker build -f Dockerfile.runpod-base -t kksenateacr.azurecr.io/kk-transcription-runpod-base:latest .
fi

# Tag as version
VERSION=$(date +%Y%m%d-%H%M%S)
docker tag kksenateacr.azurecr.io/kk-transcription-runpod-base:latest \
    kksenateacr.azurecr.io/kk-transcription-runpod-base:$VERSION

# Login ACR
echo "🔐 Logging in to ACR..."
az acr login --name kksenateacr

# Push images
echo "📤 Pushing images to ACR..."
docker push kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
docker push kksenateacr.azurecr.io/kk-transcription-runpod-base:$VERSION

echo ""
echo "✅ Build and push completed!"
echo ""
echo "📋 Image tags:"
echo "   - kksenateacr.azurecr.io/kk-transcription-runpod-base:latest"
echo "   - kksenateacr.azurecr.io/kk-transcription-runpod-base:$VERSION"
echo ""
echo "💡 Use in RunPod Pod Template Overrides:"
echo "   Container Image: kksenateacr.azurecr.io/kk-transcription-runpod-base:latest"
echo ""

