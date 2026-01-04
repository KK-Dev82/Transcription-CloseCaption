#!/bin/bash
# Script สำหรับ Restart RQ Workers
# ใช้เมื่อต้องการ restart workers ใหม่ (เช่น หลังแก้ไขโค้ด)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

print_header() {
    echo ""
    echo "================================================================================"
    echo -e "${BLUE}$1${NC}"
    echo "================================================================================"
}

# Load environment variables
if [ -f ".env.runpod" ]; then
    print_info "Loading environment variables from .env.runpod..."
    set -a
    source .env.runpod
    set +a
    print_success "Environment variables loaded from .env.runpod"
else
    print_warning ".env.runpod not found, using system environment variables"
fi

# Stop existing workers
print_header "Stopping existing RQ workers..."

# Kill all RQ worker processes
pkill -f "rq worker" || true
sleep 2

# Remove PID files
rm -f /tmp/rq-worker-*.pid

print_success "Stopped all existing workers"

# Wait a bit for processes to fully terminate
sleep 2

# Start workers using the start script
print_header "Starting RQ workers..."
bash "$SCRIPT_DIR/start-rq-workers.sh"

print_header "Restart Complete!"
print_info "Workers should be running now. Check logs if needed:"
print_info "  - GPU 0: tail -f /tmp/rq-worker-gpu0.log"
print_info "  - GPU 1: tail -f /tmp/rq-worker-gpu1.log"
print_info "  - Preprocess: tail -f /tmp/rq-worker-preprocess-0.log"
print_info "  - CPU: tail -f /tmp/rq-worker-cpu-0.log"

