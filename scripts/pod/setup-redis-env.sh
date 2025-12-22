#!/bin/bash
# Setup Redis Environment Variables
# ใช้สำหรับตั้งค่า REDIS_URL และ environment variables อื่นๆ

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

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Load .env.runpod ถ้ามี
if [ -f ".env.runpod" ]; then
    print_info "Loading .env.runpod..."
    set +u  # Allow unbound variables
    set -a
    source .env.runpod
    set +a
    set -u  # Re-enable unbound variable check
    print_success "✅ Environment variables loaded from .env.runpod"
else
    print_warning "⚠️  .env.runpod not found, using default Redis URL"
    
    # ใช้ Redis Cloud URL จาก start-pod.sh
    export REDIS_URL="redis://default:Guls3SwcxCfzYNoigtrlNq7bKZWklCCf@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598"
    
    print_info "Creating .env.runpod with default values..."
    cat > .env.runpod << EOF
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=$PROJECT_ROOT/storage
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
RABBITMQ_USER=senate
RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT
REDIS_URL=redis://default:Guls3SwcxCfzYNoigtrlNq7bKZWklCCf@redis-12598.c252.ap-southeast-1-1.ec2.cloud.redislabs.com:12598
WHISPER_PROVIDER=faster-whisper
WHISPER_API_URL=http://localhost:8002
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    print_success "✅ Created .env.runpod"
    
    # Load ใหม่
    set -a
    source .env.runpod
    set +a
fi

# ตรวจสอบว่า REDIS_URL ถูกตั้งค่าแล้ว
if [ -z "${REDIS_URL:-}" ]; then
    print_error "REDIS_URL is not set!"
    exit 1
fi

print_success "✅ REDIS_URL: $REDIS_URL"

# ทดสอบ Redis connection
print_info "Testing Redis connection..."
if python3 -c "import redis; r=redis.from_url('$REDIS_URL'); r.ping(); print('OK')" 2>/dev/null; then
    print_success "✅ Redis connection successful"
else
    print_error "❌ Cannot connect to Redis: $REDIS_URL"
    print_info "Please check your Redis URL and network connectivity"
    exit 1
fi

# Export สำหรับ shell session นี้
export REDIS_URL

print_success "✅ Environment setup complete!"
print_info ""
print_info "📝 Note:"
print_info "  - Environment variables are exported for this shell session"
print_info "  - To persist after Pod restart, use .env.runpod file (already created)"
print_info "  - To use in other shells, run: source scripts/pod/setup-redis-env.sh"
print_info ""
print_info "🚀 Next steps:"
print_info "  1. Start RQ workers: bash scripts/pod/start-rq-workers.sh"
print_info "  2. Or use API normally (it will use Redis Queue automatically)"

