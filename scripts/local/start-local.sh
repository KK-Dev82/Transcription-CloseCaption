#!/bin/bash
# Script สำหรับ Start Local Docker Testing
# ใช้สำหรับทดสอบ parallel processing บน Mac

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

print_header "🚀 Starting Local Docker Testing"
echo "📅 $(date)"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if container exists
if ! docker ps -a | grep -q transcription-local-base; then
    print_warning "⚠️  Container not found. Running setup first..."
    bash "$SCRIPT_DIR/setup-local-direct.sh"
    echo ""
fi

# Start container if not running
if ! docker ps | grep -q transcription-local-base; then
    print_status "Starting container..."
    docker-compose -f docker-compose.local-direct.yml up -d
    sleep 2
fi

# Check if services are already running
print_status "Checking if services are already running..."
if docker exec transcription-local-base bash -c "pgrep -f 'python.*main.py' > /dev/null" 2>/dev/null; then
    print_warning "⚠️  Services are already running. Use 'restart-local.sh' to restart."
    echo ""
    print_status "To view logs:"
    echo "   bash scripts/local/logs-local.sh"
    echo ""
    print_status "To stop services:"
    echo "   bash scripts/local/stop-local.sh"
    exit 0
fi

# Start services inside container
print_header "Starting services inside container..."
docker exec -it transcription-local-base bash -c "
    cd /workspace/transcription-service && \
    bash scripts/pod/start-pod.sh
" || {
    print_error "❌ Failed to start services"
    print_status "💡 Try running manually:"
    echo "   docker exec -it transcription-local-base bash"
    echo "   cd /workspace/transcription-service"
    echo "   bash scripts/pod/start-pod.sh"
    exit 1
}

echo ""
print_success "🎉 Services started!"
echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "📋 Useful commands:"
echo ""
echo "1. View logs:"
echo "   bash scripts/local/logs-local.sh [service]"
echo "   # service: api, whisper, worker, redis, or all"
echo ""
echo "2. Check status:"
echo "   docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-pod.sh'"
echo ""
echo "3. Test transcription:"
echo "   docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/test-transcription.sh uploads/test.mp4 base'"
echo ""
echo "4. Stop services:"
echo "   bash scripts/local/stop-local.sh"
echo ""
echo "5. Restart services:"
echo "   bash scripts/local/restart-local.sh"
echo ""
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

