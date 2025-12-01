#!/bin/bash
# Script สำหรับ Stop Local Docker Services

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_status "🛑 Stopping Local Docker Services"
echo ""

# Check if container exists
if ! docker ps -a | grep -q transcription-local-base; then
    print_warning "⚠️  Container not found"
    exit 0
fi

# Stop services inside container
if docker ps | grep -q transcription-local-base; then
    print_status "Stopping services inside container..."
    docker exec transcription-local-base bash -c "
        cd /workspace/transcription-service && \
        bash scripts/pod/stop-pod.sh 2>/dev/null || true
    " || print_warning "⚠️  Services may not be running"
fi

# Option to stop container (skip if --no-prompt flag)
if [ "$1" != "--no-prompt" ]; then
    read -p "Stop container as well? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Stopping container..."
        docker-compose -f docker-compose.local-direct.yml down
        print_success "✅ Container stopped"
    else
        print_status "Container is still running. Services stopped."
    fi
else
    print_status "Container is still running. Services stopped."
fi

echo ""
print_success "✅ Done!"

