#!/bin/bash
# Script สำหรับ Build และ Push Custom Base Image ไป ACR
#
# วิธีใช้งาน:
# 1. Login ACR: az acr login --name kksenateacr
# 2. รัน Base Image:     bash scripts/pod/build-and-push-runpod-base.sh base
# 3. รัน Template Image: bash scripts/pod/build-and-push-runpod-base.sh template
# 4. รันทั้งสองแบบ:     bash scripts/pod/build-and-push-runpod-base.sh all
#
# ถ้าไม่ระบุ parameter จะ build base image (เพื่อ backward compatibility)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# รับ parameter (base, template, หรือ all)
BUILD_TYPE="${1:-base}"

# Validate parameter
if [ "$BUILD_TYPE" != "base" ] && [ "$BUILD_TYPE" != "template" ] && [ "$BUILD_TYPE" != "all" ]; then
    echo "❌ Error: Invalid build type '$BUILD_TYPE'"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/build-and-push-runpod-base.sh [base|template|all]"
    echo ""
    echo "Options:"
    echo "  base     - Build PyTorch Official base image (default)"
    echo "  template - Build RunPod Template image (recommended)"
    echo "  all      - Build both images"
    exit 1
fi

cd "$PROJECT_ROOT"

# Function to build and push image
build_and_push() {
    local DOCKERFILE=$1
    local IMAGE_NAME=$2
    local IMAGE_DESC=$3
    
    echo "🔨 Building $IMAGE_DESC..."
echo "📁 Project Root: $PROJECT_ROOT"
    echo "📄 Dockerfile: $DOCKERFILE"
echo ""
echo "⚠️  This is a MINIMAL base image (CUDA + dependencies only)"
echo "   - No services will start automatically"
echo "   - User must clone repo and run scripts/pod/start-services-direct.sh"
echo "   - This prevents duplicate workers"
echo ""

# Build image (use --platform for cross-platform build)
echo "📦 Building image..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "⚠️  Detected ARM64 architecture, using --platform=linux/amd64"
        docker build --platform=linux/amd64 -f "$DOCKERFILE" -t "$IMAGE_NAME:latest" .
else
        docker build -f "$DOCKERFILE" -t "$IMAGE_NAME:latest" .
fi

# Tag as version
VERSION=$(date +%Y%m%d-%H%M%S)
    docker tag "$IMAGE_NAME:latest" "$IMAGE_NAME:$VERSION"

    # Login ACR (only once)
    if [ -z "$ACR_LOGGED_IN" ]; then
echo "🔐 Logging in to ACR..."
az acr login --name kksenateacr
        export ACR_LOGGED_IN=1
    fi

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
}

# Build based on type
if [ "$BUILD_TYPE" = "base" ] || [ "$BUILD_TYPE" = "all" ]; then
    build_and_push \
        "Dockerfile.runpod-base" \
        "kksenateacr.azurecr.io/kk-transcription-runpod-base" \
        "PyTorch Official Base Image"
    
    if [ "$BUILD_TYPE" = "all" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi
fi

if [ "$BUILD_TYPE" = "template" ] || [ "$BUILD_TYPE" = "all" ]; then
    build_and_push \
        "Dockerfile.runpod-template" \
        "kksenateacr.azurecr.io/kk-transcription-runpod-template" \
        "RunPod Template Image (Recommended ⭐)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All builds completed!"
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

