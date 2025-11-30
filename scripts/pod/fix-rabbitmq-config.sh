#!/bin/bash
# Script สำหรับแก้ไข RabbitMQ Configuration ใน .env.runpod
#
# วิธีใช้งาน:
# bash scripts/pod/fix-rabbitmq-config.sh [rabbitmq-host] [rabbitmq-port]
#
# ตัวอย่าง:
# bash scripts/pod/fix-rabbitmq-config.sh 178.128.105.100 5672

set -e

RABBITMQ_HOST="${1:-178.128.105.100}"
RABBITMQ_PORT="${2:-5672}"
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

echo "🔧 Fixing RabbitMQ Configuration"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Host: $RABBITMQ_HOST"
echo "   Port: $RABBITMQ_PORT"
echo "   User: $RABBITMQ_USER"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE=".env.runpod"

# Check if .env.runpod exists
if [ ! -f "$ENV_FILE" ]; then
    print_warning "⚠️  .env.runpod not found. Creating new file..."
    
    cat > "$ENV_FILE" << EOF
# Environment Configuration
ENVIRONMENT=runpod
STORAGE_TYPE=json
JSON_STORAGE_DIR=/workspace/transcription-service/storage

# RabbitMQ Configuration (Backend Server Dev)
RABBITMQ_HOST=$RABBITMQ_HOST
RABBITMQ_PORT=$RABBITMQ_PORT
RABBITMQ_USER=$RABBITMQ_USER
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Whisper Configuration
WHISPER_PROVIDER=builtin
WHISPER_API_URL=http://localhost:8002
WHISPER_MODEL_PATH=/workspace/transcription-service/models

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
WHISPER_CUBLAS=1
EOF
    
    print_success "✅ Created $ENV_FILE"
else
    print_status "Updating existing $ENV_FILE..."
    
    # Backup
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Update RABBITMQ_HOST
    if grep -q "^RABBITMQ_HOST=" "$ENV_FILE"; then
        sed -i "s|^RABBITMQ_HOST=.*|RABBITMQ_HOST=$RABBITMQ_HOST|" "$ENV_FILE"
        print_success "✅ Updated RABBITMQ_HOST to $RABBITMQ_HOST"
    else
        echo "RABBITMQ_HOST=$RABBITMQ_HOST" >> "$ENV_FILE"
        print_success "✅ Added RABBITMQ_HOST=$RABBITMQ_HOST"
    fi
    
    # Update RABBITMQ_PORT
    if grep -q "^RABBITMQ_PORT=" "$ENV_FILE"; then
        sed -i "s|^RABBITMQ_PORT=.*|RABBITMQ_PORT=$RABBITMQ_PORT|" "$ENV_FILE"
        print_success "✅ Updated RABBITMQ_PORT to $RABBITMQ_PORT"
    else
        echo "RABBITMQ_PORT=$RABBITMQ_PORT" >> "$ENV_FILE"
        print_success "✅ Added RABBITMQ_PORT=$RABBITMQ_PORT"
    fi
    
    # Update RABBITMQ_USER
    if grep -q "^RABBITMQ_USER=" "$ENV_FILE"; then
        sed -i "s|^RABBITMQ_USER=.*|RABBITMQ_USER=$RABBITMQ_USER|" "$ENV_FILE"
        print_success "✅ Updated RABBITMQ_USER to $RABBITMQ_USER"
    else
        echo "RABBITMQ_USER=$RABBITMQ_USER" >> "$ENV_FILE"
        print_success "✅ Added RABBITMQ_USER=$RABBITMQ_USER"
    fi
    
    # Update RABBITMQ_PASSWORD
    if grep -q "^RABBITMQ_PASSWORD=" "$ENV_FILE"; then
        sed -i "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD|" "$ENV_FILE"
        print_success "✅ Updated RABBITMQ_PASSWORD"
    else
        echo "RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD" >> "$ENV_FILE"
        print_success "✅ Added RABBITMQ_PASSWORD"
    fi
fi

echo ""
print_status "📋 Updated $ENV_FILE:"
grep "^RABBITMQ_" "$ENV_FILE" || echo "No RABBITMQ configuration found"
echo ""

# Test connection
print_status "Testing RabbitMQ connection..."
if bash scripts/pod/test-rabbitmq-connection.sh "$RABBITMQ_HOST" "$RABBITMQ_PORT" "$RABBITMQ_USER" "$RABBITMQ_PASSWORD" 2>/dev/null; then
    print_success "✅ RabbitMQ connection test passed!"
    echo ""
    print_status "💡 Next steps:"
    echo "   1. Restart services:"
    echo "      bash scripts/pod/stop-services.sh"
    echo "      bash scripts/pod/start-services-direct.sh"
    echo ""
    echo "   2. Check Video Worker logs:"
    echo "      tail -f /tmp/video-worker.log"
else
    print_warning "⚠️  RabbitMQ connection test failed"
    echo ""
    print_status "💡 Possible reasons:"
    echo "   1. Firewall is blocking port $RABBITMQ_PORT"
    echo "   2. RabbitMQ is not running on Backend Server"
    echo "   3. Network connectivity issues"
    echo ""
    print_status "💡 Solutions:"
    echo "   1. Check Backend Server firewall: sudo ufw status"
    echo "   2. Check RabbitMQ: docker ps | grep rabbitmq (on Backend Server)"
    echo "   3. Verify IP address: 178.128.105.100"
    echo ""
    print_warning "⚠️  Services will start, but Video Worker may not connect to RabbitMQ"
fi

