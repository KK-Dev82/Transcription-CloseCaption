#!/bin/bash
# Restart Pod Container - Stop all services and restart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info "🔄 Restarting Pod Container..."

# 1. Stop all RQ workers
print_info "Stopping RQ workers..."
pkill -f "rq worker" 2>/dev/null || true
sleep 2

# 2. Stop Main API
print_info "Stopping Main API..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2

# 3. Install FFmpeg (if needed)
print_info "Installing FFmpeg..."
apt-get update -qq && apt-get install -y -qq ffmpeg 2>&1 | tail -5 || {
    print_warning "FFmpeg installation failed (may already be installed)"
}

# 4. Load environment variables
print_info "Loading .env.runpod..."
if [ -f ".env.runpod" ]; then
    set -a
    set +u
    source .env.runpod
    set -u
    set +a
    print_success "✅ Environment variables loaded"
else
    print_error "❌ .env.runpod not found!"
    exit 1
fi

# 5. Start RQ workers
print_info "Starting RQ workers..."
bash scripts/pod/start-rq-workers.sh

# 6. Start Main API
print_info "Starting Main API..."
export PYTHONPATH="$PROJECT_ROOT"
export RABBITMQ_HOST=${RABBITMQ_HOST:-178.128.105.100}
export RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
export RABBITMQ_USER=${RABBITMQ_USER:-senate}
export RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-qP2VtHz6fAX4xDksEpMrLT}
export WHISPER_PROVIDER=${WHISPER_PROVIDER:-faster-whisper}
export WHISPER_MODEL=${WHISPER_MODEL:-base}
export WHISPER_DEVICE=${WHISPER_DEVICE:-cuda}
export REDIS_URL=${REDIS_URL:-redis://default:Guls3SwcxCfzYNoigtrlNq7bKZWklCCf@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598}
export WHISPER_USE_BATCHED=${WHISPER_USE_BATCHED:-true}
export WHISPER_BATCH_SIZE=${WHISPER_BATCH_SIZE:-16}
export WHISPER_COMPUTE_TYPE=${WHISPER_COMPUTE_TYPE:-float16}

nohup env RABBITMQ_HOST="${RABBITMQ_HOST}" \
         RABBITMQ_PORT="${RABBITMQ_PORT}" \
         RABBITMQ_USER="${RABBITMQ_USER}" \
         RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD}" \
         WHISPER_PROVIDER="${WHISPER_PROVIDER}" \
         WHISPER_MODEL="${WHISPER_MODEL}" \
         WHISPER_DEVICE="${WHISPER_DEVICE}" \
         REDIS_URL="${REDIS_URL}" \
         WHISPER_USE_BATCHED="${WHISPER_USE_BATCHED}" \
         WHISPER_BATCH_SIZE="${WHISPER_BATCH_SIZE}" \
         WHISPER_COMPUTE_TYPE="${WHISPER_COMPUTE_TYPE}" \
         LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}" \
         python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 > /tmp/main-api.log 2>&1 & disown

sleep 3

# 7. Verify services
print_info "Verifying services..."
if pgrep -f "rq worker.*gpu0" > /dev/null; then
    print_success "✅ GPU workers running"
else
    print_error "❌ GPU workers not running"
fi

if pgrep -f "uvicorn app.main:app" > /dev/null; then
    print_success "✅ Main API running"
else
    print_error "❌ Main API not running"
fi

print_success "✅ Pod Container restarted successfully!"
