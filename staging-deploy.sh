#!/bin/bash

# Staging Deployment Script - Simplified Version
# สำหรับ deploy ระบบไปยัง staging environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Configuration
MAIN_IMAGE="kksenateacr.azurecr.io/kk-transcription:alpha-dev"
WHISPER_IMAGE="kksenateacr.azurecr.io/kk-transcription-whisper:alpha-dev"
COMPOSE_FILE="docker-compose.yml"

echo "🚀 Starting Staging Deployment..."

# Error handling: Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Error handling: Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed."
    exit 1
fi

# Error handling: Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    print_error "Docker compose file not found: $COMPOSE_FILE"
    exit 1
fi

print_success "Prerequisites check passed"

# Step 1: Pull images from ACR
print_status "📦 Step 1: Pulling images from ACR..."
if ! docker pull $MAIN_IMAGE; then
    print_error "Failed to pull main image: $MAIN_IMAGE"
    exit 1
fi

if ! docker pull $WHISPER_IMAGE; then
    print_error "Failed to pull whisper image: $WHISPER_IMAGE"
    exit 1
fi

print_success "Images pulled successfully"

# Step 2: Create required directories
print_status "📁 Step 2: Creating required directories..."
mkdir -p uploads temp storage models
print_success "Directories created"

# Step 3: Stop existing containers
print_status "🧹 Step 3: Shutting down old containers..."
if ! docker-compose -f $COMPOSE_FILE down --remove-orphans; then
    print_warning "Some containers may not have stopped cleanly"
fi
print_success "Old containers stopped"

# Step 4: Start new containers
print_status "🚀 Step 4: Starting new containers..."
# Set environment variables for staging
export WHISPER_API_URL=http://10.200.22.63:8002
export ENVIRONMENT=staging

if ! docker-compose -f $COMPOSE_FILE up -d; then
    print_error "Failed to start containers"
    exit 1
fi
print_success "Containers started"

# Step 5: Wait for services to be ready
print_status "⏳ Step 5: Waiting for services to start..."
sleep 30

# Step 6: Health checks
print_status "🔍 Step 6: Checking service health..."

# Health check function
check_health() {
    local service_name=$1
    local url=$2
    local expected_code=${3:-200}
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    
    if [ "$response_code" = "$expected_code" ]; then
        print_success "$service_name is healthy (HTTP $response_code)"
        return 0
    else
        print_warning "$service_name health check failed (HTTP $response_code)"
        return 1
    fi
}

# Check all services
HEALTH_FAILED=0

check_health "API" "http://localhost:8001/health" || HEALTH_FAILED=1
check_health "Whisper" "http://localhost:8002/health" || HEALTH_FAILED=1
check_health "Whisper Live" "http://localhost:8003/health" || HEALTH_FAILED=1
check_health "RabbitMQ" "http://localhost:15672/api/overview" || HEALTH_FAILED=1

# Check Redis
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    print_success "Redis is healthy"
else
    print_warning "Redis health check failed"
    HEALTH_FAILED=1
fi

# Step 7: Display service information
echo ""
print_status "🌐 Service URLs:"
echo "  - API Documentation: http://localhost:8001/docs"
echo "  - API Health: http://localhost:8001/health"
echo "  - Whisper API: http://localhost:8002/health"
echo "  - Whisper Live API: http://localhost:8003/health"
echo "  - RabbitMQ Management: http://localhost:15672 (admin/admin123)"
echo "  - Redis: localhost:6379"

# Step 8: Display container status
echo ""
print_status "📊 Container Status:"
docker-compose -f $COMPOSE_FILE ps

# Step 9: Display recent logs
echo ""
print_status "📋 Recent logs (last 20 lines):"
docker-compose -f $COMPOSE_FILE logs --tail=20

# Step 10: Final status
echo ""
if [ $HEALTH_FAILED -eq 0 ]; then
    print_success "🎉 Staging deployment completed successfully!"
    echo ""
    echo "🛠️  Management commands:"
    echo "  - View logs: docker-compose -f $COMPOSE_FILE logs -f [service_name]"
    echo "  - Restart service: docker-compose -f $COMPOSE_FILE restart [service_name]"
    echo "  - Stop all: docker-compose -f $COMPOSE_FILE down"
    echo "  - Update: ./staging-deploy.sh"
else
    print_warning "⚠️  Deployment completed with some health check failures"
    echo "Please check the logs above for more details"
fi

echo ""
