#!/bin/bash

# Deploy to Staging Environment
# This script deploys the application to staging using docker-compose.yml

set -e

echo "🚀 Deploying to Staging Environment..."

# 1. Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down || true

# 2. Pull latest images
echo "📥 Pulling latest images..."
docker-compose pull

# 3. Start services
echo "▶️  Starting services..."
docker-compose up -d

# 4. Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 30

# 5. Check service status
echo "🔍 Checking service status..."
docker-compose ps

# 6. Test API health
echo "🏥 Testing API health..."
sleep 10
curl -f http://localhost:8001/health || echo "❌ API health check failed"

echo "✅ Staging deployment completed!"
echo "🌐 API: http://localhost:8001"
echo "📊 RabbitMQ Management: http://localhost:15672 (admin/admin123)"
