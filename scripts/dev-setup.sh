#!/bin/bash

echo "🚀 Setting up Development Environment"
echo "====================================="

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.dev.yml down

# Build Whisper image first
echo "🔨 Building Whisper image..."
docker-compose -f docker-compose.dev.yml build whisper

# Build other services
echo "🔨 Building other services..."
docker-compose -f docker-compose.dev.yml build

# Start all services
echo "🚀 Starting all services..."
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check status
echo "📊 Checking service status..."
docker-compose -f docker-compose.dev.yml ps

echo "✅ Development environment is ready!"
echo "🌐 API: http://localhost:8001"
echo "🐰 RabbitMQ Management: http://localhost:15672 (admin/admin123)"
echo "🔴 Redis: localhost:6379" 