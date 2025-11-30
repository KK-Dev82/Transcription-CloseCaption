#!/bin/bash
# Script สำหรับ Build และ Push Custom Base Image ไป ACR
#
# วิธีใช้งาน:
# 1. Login ACR: az acr login --name kksenateacr
# 2. รัน: bash scripts/pod/build-and-push-runpod-base.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔨 Building Minimal Base Image for RunPod/Z2..."
echo "📁 Project Root: $PROJECT_ROOT"
echo ""
echo "⚠️  This is a MINIMAL base image (CUDA + dependencies only)"
echo "   - No services will start automatically"
echo "   - User must clone repo and run scripts/pod/start-services-direct.sh"
echo "   - This prevents duplicate workers"
echo ""

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
echo "📋 After Pod starts:"
echo "   1. Clone repository:"
echo "      cd /workspace"
echo "      git clone <repo-url> transcription-service"
echo ""
echo "   2. Setup Pod (first time):"
echo "      cd /workspace/transcription-service"
echo "      bash scripts/pod/setup-pod.sh"
echo ""
echo "   3. Start services (Direct mode):"
echo "      bash scripts/pod/start-pod.sh"
echo ""
echo "   4. Check status:"
echo "      bash scripts/pod/check-pod.sh"
echo ""
echo "⚠️  Important: Services are NOT started automatically"
echo "   This prevents duplicate workers from Docker Compose + Direct mode"
echo ""

