#!/bin/bash
# Script สำหรับ Build Custom Image สำหรับ Pod Container
# Image นี้มี dependencies ทั้งหมดติดตั้งไว้แล้ว ไม่ต้อง install ใหม่ทุกครั้งที่ restart POD

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

print_header "🐳 Build Custom Image สำหรับ Pod Container"

# Default values
IMAGE_NAME="transcription-service"
IMAGE_TAG="latest"
REGISTRY=""
DOCKERFILE="Dockerfile.base-new"
PUSH_IMAGE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        --dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --name NAME        Image name (default: transcription-service)"
            echo "  --tag TAG          Image tag (default: latest)"
            echo "  --registry REG     Registry URL (e.g., your-registry.io)"
            echo "  --push             Push image to registry after build"
            echo "  --dockerfile FILE  Dockerfile path (default: Dockerfile.runpod-custom)"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --name my-transcription --tag v1.0.0"
            echo "  $0 --registry my-registry.io --name transcription --push"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check Dockerfile exists
if [ ! -f "$PROJECT_DIR/$DOCKERFILE" ]; then
    print_error "Dockerfile not found: $DOCKERFILE"
    exit 1
fi

# Build full image name
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
fi

echo ""
echo "📋 Build Configuration:"
echo "   Dockerfile: $DOCKERFILE"
echo "   Image: $FULL_IMAGE_NAME"
echo "   Push after build: $PUSH_IMAGE"
echo ""

# Build image
print_header "🔨 Building Image"

cd "$PROJECT_DIR"

if docker build -f "$DOCKERFILE" -t "$FULL_IMAGE_NAME" .; then
    print_success "Image built successfully: $FULL_IMAGE_NAME"
else
    print_error "Failed to build image"
    exit 1
fi

# Show image info
echo ""
print_header "📊 Image Information"

IMAGE_SIZE=$(docker images "$FULL_IMAGE_NAME" --format "{{.Size}}" | head -1)
print_success "Image size: $IMAGE_SIZE"

# Push image if requested
if [ "$PUSH_IMAGE" = true ]; then
    echo ""
    print_header "📤 Pushing Image to Registry"
    
    if [ -z "$REGISTRY" ]; then
        print_warning "No registry specified. Skipping push."
        print_warning "Use --registry to specify registry URL"
    else
        if docker push "$FULL_IMAGE_NAME"; then
            print_success "Image pushed successfully: $FULL_IMAGE_NAME"
        else
            print_error "Failed to push image"
            exit 1
        fi
    fi
fi

# Summary
echo ""
print_header "✅ Build Complete"

echo ""
echo "📋 Next Steps:"
echo "   1. Use this image in RunPod:"
echo "      Image: $FULL_IMAGE_NAME"
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

if [ "$PUSH_IMAGE" = false ] && [ -n "$REGISTRY" ]; then
    echo "💡 To push image later:"
    echo "   docker push $FULL_IMAGE_NAME"
    echo ""
fi

