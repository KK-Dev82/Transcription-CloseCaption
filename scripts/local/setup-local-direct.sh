#!/bin/bash
# Script สำหรับ Setup Local Direct Mode Testing
# ใช้แนวทางเดียวกับ RunPod: Build Container → Clone Git → Start services แบบ Direct mode

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_header "🚀 Local Direct Mode Setup"
echo "📅 $(date)"
echo ""

# Step 1: Stop existing containers
print_header "Step 1: Stopping existing transcription containers..."
bash "$SCRIPT_DIR/stop-transcription-containers.sh"
echo ""

# Step 2: Build base image
print_header "Step 2: Building local base image..."
if docker build -f Dockerfile.local-base -t kk-transcription-local-base:latest .; then
    print_success "✅ Base image built successfully"
else
    print_error "❌ Failed to build base image"
    exit 1
fi
echo ""

# Step 3: Start container
print_header "Step 3: Starting container..."
if docker-compose -f docker-compose.local-direct.yml up -d; then
    print_success "✅ Container started"
else
    print_error "❌ Failed to start container"
    exit 1
fi
echo ""

# Step 4: Wait for container to be ready
print_status "Waiting for container to be ready..."
sleep 3

# Step 5: Setup inside container
print_header "Step 4: Setting up inside container..."
print_status "Running setup inside container..."

docker exec -it transcription-local-base bash -c "
    cd /workspace/transcription-service && \
    bash scripts/pod/setup-pod.sh
" || {
    print_warning "⚠️  Setup script may have interactive prompts"
    print_status "💡 You can run setup manually:"
    echo "   docker exec -it transcription-local-base bash"
    echo "   cd /workspace/transcription-service"
    echo "   bash scripts/pod/setup-pod.sh"
}

echo ""
print_success "🎉 Setup completed!"
echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "📋 Next steps:"
echo ""
echo "1. Enter container:"
echo "   docker exec -it transcription-local-base bash"
echo ""
echo "2. Inside container, start services:"
echo "   cd /workspace/transcription-service"
echo "   bash scripts/pod/start-pod.sh"
echo ""
echo "3. Check status:"
echo "   bash scripts/pod/check-pod.sh"
echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

