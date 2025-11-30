#!/bin/bash
# Script สำหรับตั้งค่า RabbitMQ Connection ไปยัง Backend Server
#
# วิธีใช้งาน:
# bash scripts/pod/setup-rabbitmq-backend.sh [backend-ip] [backend-port]
#
# ตัวอย่าง:
# bash scripts/pod/setup-rabbitmq-backend.sh 178.128.105.100 5672

set -e

BACKEND_IP="${1:-178.128.105.100}"
BACKEND_PORT="${2:-5672}"
RABBITMQ_USER="${3:-senate}"
RABBITMQ_PASSWORD="${4:-qP2VtHz6fAX4xDksEpMrLT}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔌 Setting up RabbitMQ Connection to Backend Server"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Backend IP: $BACKEND_IP"
echo "   Backend Port: $BACKEND_PORT"
echo "   RabbitMQ User: $RABBITMQ_USER"
echo ""

# Test connection
print_status "Testing RabbitMQ connection..."
if python3 -c "
import pika
import sys
try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host='$BACKEND_IP',
            port=$BACKEND_PORT,
            credentials=pika.PlainCredentials('$RABBITMQ_USER', '$RABBITMQ_PASSWORD'),
            connection_attempts=3,
            retry_delay=2
        )
    )
    print('✅ RabbitMQ connection successful!')
    connection.close()
    sys.exit(0)
except Exception as e:
    print(f'❌ RabbitMQ connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
    print_success "✅ RabbitMQ connection test passed!"
else
    print_error "❌ RabbitMQ connection test failed!"
    echo ""
    print_warning "Possible reasons:"
    echo "   1. Backend Server firewall is blocking port $BACKEND_PORT"
    echo "   2. RabbitMQ is not running on Backend Server"
    echo "   3. IP address or credentials are incorrect"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. Check Backend Server firewall: sudo ufw status"
    echo "   2. Check RabbitMQ is running: docker ps | grep rabbitmq"
    echo "   3. Verify credentials with Backend team"
    exit 1
fi

echo ""

# Create/Update .env.runpod
print_status "Creating/Updating .env.runpod file..."

ENV_FILE=".env.runpod"
if [ -f "$ENV_FILE" ]; then
    print_warning "$ENV_FILE already exists. Backing up..."
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
fi

cat > "$ENV_FILE" << EOF
# RabbitMQ Configuration (Backend Server Dev)
RABBITMQ_HOST=$BACKEND_IP
RABBITMQ_PORT=$BACKEND_PORT
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_API_URL=http://localhost:8002
WHISPER_MODEL_PATH=/workspace/transcription-service/models

# Environment
ENVIRONMENT=runpod

# Storage
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF

print_success "✅ Created/Updated $ENV_FILE"
echo ""

# Display configuration
print_status "📋 Configuration saved to $ENV_FILE:"
cat "$ENV_FILE"
echo ""

# Load environment variables
print_status "Loading environment variables..."
export $(grep -v '^#' "$ENV_FILE" | xargs)
print_success "✅ Environment variables loaded"
echo ""

# Restart services (if running)
if pgrep -f "python.*uvicorn.*app.main" > /dev/null || pgrep -f "python.*video_worker" > /dev/null; then
    print_warning "Services are running. Restart required to apply new configuration."
    echo ""
    read -p "Restart services now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Restarting services..."
        bash scripts/pod/stop-services.sh
        sleep 2
        bash scripts/pod/start-services-direct.sh
    else
        print_status "💡 To apply changes, restart services manually:"
        echo "   bash scripts/pod/stop-services.sh"
        echo "   bash scripts/pod/start-services-direct.sh"
    fi
else
    print_status "💡 Services are not running. Start services with:"
    echo "   bash scripts/pod/start-services-direct.sh"
fi

echo ""
print_success "✅ RabbitMQ setup completed!"
echo ""
print_status "📋 Next steps:"
echo "   1. Verify connection: bash scripts/pod/check-services.sh"
echo "   2. Check logs: tail -f /tmp/video-worker.log"
echo "   3. Test transcription task"

