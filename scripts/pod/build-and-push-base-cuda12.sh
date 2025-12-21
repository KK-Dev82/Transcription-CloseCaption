#!/bin/bash
# Script สำหรับ Build และ Push Base Image CUDA 12.1 (Dockerfile.base-new-cuda12) ไป ACR
# ⭐ Image นี้มี dependencies ทั้งหมดติดตั้งไว้แล้ว + faster-whisper 1.2.1
#
# วิธีใช้งาน:
#   1. Login ACR: az acr login --name kksenateacr
#   2. Run script: bash scripts/pod/build-and-push-base-cuda12.sh
#
# Image จะถูก push ไป:
#   - kksenateacr.azurecr.io/kk-transcription-base-cuda12:latest
#   - kksenateacr.azurecr.io/kk-transcription-base-cuda12:v{version}

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "🐳 Build และ Push Base Image CUDA 12.1 ไป ACR"

cd "$PROJECT_DIR"

# Configuration
ACR_NAME="kksenateacr"
IMAGE_NAME="kksenateacr.azurecr.io/kk-transcription-base-cuda12"
DOCKERFILE="Dockerfile.base-new-cuda12"
VERSION=$(date +"%Y%m%d-%H%M%S")

# Build Configuration
print_header "📋 Build Configuration"
echo "ACR: $ACR_NAME"
echo "Image: $IMAGE_NAME"
echo "Dockerfile: $DOCKERFILE"
echo "Version: $VERSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    print_error "Dockerfile not found: $DOCKERFILE"
    exit 1
fi

# Detect platform
PLATFORM="linux/amd64"
if [[ "$(uname -m)" == "arm64" ]] || [[ "$(uname -m)" == "aarch64" ]]; then
    print_warning "Building on ARM64 - using --platform=$PLATFORM"
    PLATFORM_FLAG="--platform=$PLATFORM"
else
    PLATFORM_FLAG=""
fi

# Login to ACR
print_header "🔐 Logging in to ACR"
if az acr login --name "$ACR_NAME" 2>/dev/null; then
    print_success "Logged in to ACR: $ACR_NAME"
else
    print_error "Failed to login to ACR. Please run: az acr login --name $ACR_NAME"
    exit 1
fi

# Build image
print_header "🔨 Building Image"
echo "Building: $IMAGE_NAME:latest"
echo ""

if docker build $PLATFORM_FLAG \
    -f "$DOCKERFILE" \
    -t "$IMAGE_NAME:latest" \
    -t "$IMAGE_NAME:$VERSION" \
    .; then
    print_success "Image built successfully"
else
    print_error "Failed to build image"
    exit 1
fi

# Push image
print_header "📤 Pushing Image to ACR"
echo "Pushing: $IMAGE_NAME:latest"
echo "Pushing: $IMAGE_NAME:$VERSION"
echo ""

if docker push "$IMAGE_NAME:latest" && docker push "$IMAGE_NAME:$VERSION"; then
    print_success "Image pushed successfully"
else
    print_error "Failed to push image"
    exit 1
fi

# Summary
print_header "✅ Build และ Push เสร็จสิ้น"
echo "Image: $IMAGE_NAME:latest"
echo "Version: $IMAGE_NAME:$VERSION"
echo ""
echo "📋 วิธีใช้งานใน RunPod:"
echo "   1. ไปที่ RunPod Dashboard → Pod Settings"
echo "   2. เปลี่ยน Container Image เป็น: $IMAGE_NAME:latest"
echo "   3. Restart Pod"
echo ""
echo "📋 Features:"
echo "   ✅ CUDA 12.1 + cuDNN 9"
echo "   ✅ faster-whisper 1.2.1"
echo "   ✅ CTranslate2 4.6.2+"
echo "   ✅ PyTorch 2.1.0+cu121"
echo "   ✅ Performance: 30 นาที → 1-2 นาที"
echo ""

