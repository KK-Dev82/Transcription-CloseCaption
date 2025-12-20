#!/bin/bash
# Script สำหรับ Build และ Push Base Image ใหม่ (Dockerfile.base-new) ไป ACR
# ⭐ Image นี้มี dependencies ทั้งหมดติดตั้งไว้แล้ว ไม่ต้อง install ใหม่ทุกครั้งที่ restart POD
#
# วิธีใช้งาน:
#   1. Login ACR: az acr login --name kksenateacr
#   2. Run script: bash scripts/pod/build-and-push-base-new.sh
#
# Image จะถูก push ไป:
#   - kksenateacr.azurecr.io/kk-transcription-base:latest
#   - kksenateacr.azurecr.io/kk-transcription-base:v1.0.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

print_header "🐳 Build และ Push Base Image ใหม่ไป ACR"

cd "$PROJECT_DIR"

# Configuration
ACR_NAME="kksenateacr"
IMAGE_NAME="kksenateacr.azurecr.io/kk-transcription-base"
DOCKERFILE="Dockerfile.base-new"
VERSION=$(date +%Y%m%d-%H%M%S)  # Version based on timestamp

# Check Dockerfile exists
if [ ! -f "$PROJECT_DIR/$DOCKERFILE" ]; then
    print_error "Dockerfile not found: $DOCKERFILE"
    exit 1
fi

echo ""
echo "📋 Build Configuration:"
echo "   ACR: $ACR_NAME"
echo "   Image: $IMAGE_NAME"
echo "   Dockerfile: $DOCKERFILE"
echo "   Version: $VERSION"
echo ""

# Check if docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not available in this environment"
    print_warning "Please run this script on a machine with Docker installed"
    print_warning "Or use Azure Cloud Shell or GitHub Actions"
    exit 1
fi

# Check if az CLI is available
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not available"
    print_warning "Please install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login ACR
print_header "🔐 Logging in to ACR"
if az acr login --name "$ACR_NAME" 2>/dev/null; then
    print_success "Logged in to ACR: $ACR_NAME"
else
    print_error "Failed to login to ACR: $ACR_NAME"
    print_warning "Please check your Azure credentials: az login"
    exit 1
fi

# Build image
print_header "🔨 Building Image"

echo "Building: $IMAGE_NAME:latest"
if docker build -f "$DOCKERFILE" -t "$IMAGE_NAME:latest" .; then
    print_success "Image built successfully: $IMAGE_NAME:latest"
else
    print_error "Failed to build image"
    exit 1
fi

# Tag with version
echo ""
echo "Tagging: $IMAGE_NAME:$VERSION"
if docker tag "$IMAGE_NAME:latest" "$IMAGE_NAME:$VERSION"; then
    print_success "Image tagged: $IMAGE_NAME:$VERSION"
else
    print_error "Failed to tag image"
    exit 1
fi

# Show image info
echo ""
print_header "📊 Image Information"

IMAGE_SIZE=$(docker images "$IMAGE_NAME:latest" --format "{{.Size}}" | head -1)
print_success "Image size: $IMAGE_SIZE"

# Push images
print_header "📤 Pushing Images to ACR"

echo "Pushing: $IMAGE_NAME:latest"
if docker push "$IMAGE_NAME:latest"; then
    print_success "Image pushed: $IMAGE_NAME:latest"
else
    print_error "Failed to push image: $IMAGE_NAME:latest"
    exit 1
fi

echo ""
echo "Pushing: $IMAGE_NAME:$VERSION"
if docker push "$IMAGE_NAME:$VERSION"; then
    print_success "Image pushed: $IMAGE_NAME:$VERSION"
else
    print_error "Failed to push image: $IMAGE_NAME:$VERSION"
    exit 1
fi

# Summary
echo ""
print_header "✅ Build and Push Complete"

echo ""
echo "📋 Images pushed to ACR:"
echo "   - $IMAGE_NAME:latest"
echo "   - $IMAGE_NAME:$VERSION"
echo ""
echo "📋 Next Steps:"
echo "   1. Use in RunPod:"
echo "      Image: $IMAGE_NAME:latest"
echo ""
echo "   2. After starting Pod, clone repository:"
echo "      git clone <repo> /workspace/transcription-service"
echo ""
echo "   3. Start services:"
echo "      cd /workspace/transcription-service"
echo "      bash scripts/pod/start-pod.sh"
echo ""
echo "   ✅ No need to run install-dependencies.sh!"
echo ""
echo "📋 Verify images:"
echo "   az acr repository show-tags --name $ACR_NAME --repository kk-transcription-base"
echo ""

