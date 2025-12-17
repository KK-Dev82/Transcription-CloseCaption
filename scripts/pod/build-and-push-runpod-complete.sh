#!/bin/bash
# Script สำหรับ Build และ Push Complete Image (มี Dependencies ติดตั้งไว้แล้ว) ไป ACR
#
# ⭐ Image นี้มี dependencies ทั้งหมดติดตั้งไว้แล้ว ไม่ต้อง install ใหม่ทุกครั้งที่ restart POD
#
# วิธีใช้งาน:
# 1. Login ACR: az acr login --name kksenateacr
# 2. Build และ Push: bash scripts/pod/build-and-push-runpod-complete.sh
#
# ✅ ข้อดี:
# - ไม่ต้องรัน install-dependencies.sh ทุกครั้งที่ restart POD
# - Start services ได้ทันทีหลัง clone repo
# - ลดเวลา startup และความเสี่ยงจาก network issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

IMAGE_NAME="kksenateacr.azurecr.io/kk-transcription-runpod-complete"
IMAGE_DESC="Complete Image with All Dependencies"

echo "🔨 Building $IMAGE_DESC..."
echo "📁 Project Root: $PROJECT_ROOT"
echo "📄 Dockerfile: Dockerfile.runpod-complete"
echo ""
echo "✅ This is a COMPLETE image with all dependencies pre-installed"
echo "   - All Python packages from requirements.txt are installed"
echo "   - System dependencies (FFmpeg, tzdata) are installed"
echo "   - No need to run install-dependencies.sh after restart POD"
echo "   - Just clone repo and start services!"
echo ""

# Build image (use --platform for cross-platform build)
echo "📦 Building image..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "⚠️  Detected ARM64 architecture, using --platform=linux/amd64"
    docker build --platform=linux/amd64 -f Dockerfile.runpod-complete -t "$IMAGE_NAME:latest" .
else
    docker build -f Dockerfile.runpod-complete -t "$IMAGE_NAME:latest" .
fi

# Tag as version
VERSION=$(date +%Y%m%d-%H%M%S)
docker tag "$IMAGE_NAME:latest" "$IMAGE_NAME:$VERSION"

# Login ACR
echo "🔐 Logging in to ACR..."
az acr login --name kksenateacr

# Push images
echo "📤 Pushing images to ACR..."
docker push "$IMAGE_NAME:latest"
docker push "$IMAGE_NAME:$VERSION"

echo ""
echo "✅ Build and push completed for $IMAGE_DESC!"
echo ""
echo "📋 Image tags:"
echo "   - $IMAGE_NAME:latest"
echo "   - $IMAGE_NAME:$VERSION"
echo ""
echo "💡 Use in RunPod Pod Template Overrides:"
echo "   Container Image: $IMAGE_NAME:latest"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 After Pod starts:"
echo "   1. Clone repository:"
echo "      cd /workspace"
echo "      git clone <repo-url> transcription-service"
echo ""
echo "   2. Start services (Direct mode):"
echo "      cd /workspace/transcription-service"
echo "      bash scripts/pod/start-pod.sh"
echo ""
echo "   3. Check status:"
echo "      bash scripts/pod/check-pod.sh"
echo ""
echo "✅ No need to run install-dependencies.sh!"
echo "   All dependencies are already installed in the image."
echo ""

