#!/bin/bash

# Staging Deployment Script
# สำหรับ deploy ระบบไปยัง staging environment

set -e

echo "🚀 Starting Staging Deployment..."

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

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed."
    exit 1
fi

print_status "Docker and Docker Compose are available"

# Create required directories
print_status "Creating required directories..."
mkdir -p uploads temp storage models

# Set environment variables for staging
export ENVIRONMENT=staging
export STORAGE_TYPE=sqlite
export SQLITE_DB_PATH=/app/storage/database.db

print_status "Environment variables set for staging"

# Stop existing containers (if any)
print_status "Stopping existing containers..."
docker-compose -f docker-compose.staging.yml down --remove-orphans || true

# Remove old images (optional - uncomment if you want to force rebuild)
# print_status "Removing old images..."
# docker-compose -f docker-compose.staging.yml down --rmi all || true

# Build and start services
print_status "Building and starting staging services..."
docker-compose -f docker-compose.staging.yml up --build -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Check service health
print_status "Checking service health..."

# Check API health
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health || echo "000")
if [ "$API_HEALTH" = "200" ]; then
    print_success "API service is healthy"
else
    print_warning "API service health check failed (HTTP $API_HEALTH)"
fi

# Check Whisper health
WHISPER_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health || echo "000")
if [ "$WHISPER_HEALTH" = "200" ]; then
    print_success "Whisper service is healthy"
else
    print_warning "Whisper service health check failed (HTTP $WHISPER_HEALTH)"
fi

# Check RabbitMQ
RABBITMQ_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" -u admin:admin123 http://localhost:15672/api/overview || echo "000")
if [ "$RABBITMQ_HEALTH" = "200" ]; then
    print_success "RabbitMQ service is healthy"
else
    print_warning "RabbitMQ service health check failed (HTTP $RABBITMQ_HEALTH)"
fi

# Check Redis
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    print_success "Redis service is healthy"
else
    print_warning "Redis service health check failed"
fi

# Display service URLs
echo ""
echo "🌐 Service URLs:"
echo "  - API Documentation: http://localhost:8001/docs"
echo "  - API Health: http://localhost:8001/health"
echo "  - Whisper API: http://localhost:8002/health"
echo "  - Whisper Live API: http://localhost:8003/health"
echo "  - RabbitMQ Management: http://localhost:15672 (admin/admin123)"
echo "  - Redis: localhost:6379"

# Display container status
echo ""
print_status "Container Status:"
docker-compose -f docker-compose.staging.yml ps

# Display resource usage
echo ""
print_status "Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Run API tests (if test script exists)
if [ -f "test_api_endpoints.py" ]; then
    echo ""
    print_status "Running API tests..."
    python test_api_endpoints.py || print_warning "Some API tests failed"
else
    print_warning "API test script not found, skipping tests"
fi

# Display logs for the last few minutes
echo ""
print_status "Recent logs (last 50 lines):"
docker-compose -f docker-compose.staging.yml logs --tail=50

echo ""
print_success "🎉 Staging deployment completed!"
echo ""
echo "📊 Next steps:"
echo "  1. Test the APIs using: http://localhost:8001/docs"
echo "  2. Monitor logs: docker-compose -f docker-compose.staging.yml logs -f"
echo "  3. Check database: sqlite3 storage/database.db"
echo "  4. Run load tests if needed"
echo ""
echo "🛠️  Management commands:"
echo "  - View logs: docker-compose -f docker-compose.staging.yml logs -f [service_name]"
echo "  - Restart service: docker-compose -f docker-compose.staging.yml restart [service_name]"
echo "  - Stop all: docker-compose -f docker-compose.staging.yml down"
echo "  - Update: ./staging-deploy.sh"
echo ""

# Save deployment info
cat > deployment_info.txt << EOF
Staging Deployment Information
==============================
Deployed at: $(date)
Environment: staging
Storage Type: SQLite
Database Path: storage/database.db
Docker Compose File: docker-compose.staging.yml

Services:
- API: http://localhost:8001
- Whisper: http://localhost:8002
- Whisper Live: http://localhost:8003
- RabbitMQ: http://localhost:15672
- Redis: localhost:6379

Resource Limits:
- API: 6GB RAM, 3 CPU cores
- Whisper: 8GB RAM, 6 CPU cores
- Whisper Live: 6GB RAM, 4 CPU cores
- Video Workers: 4GB RAM, 2-3 CPU cores each
- RabbitMQ: 2GB RAM, 1 CPU core
- Redis: 2GB RAM, 1 CPU core

Total Resources:
- RAM: ~32GB
- CPU: ~16 cores
EOF

print_success "Deployment information saved to deployment_info.txt"
