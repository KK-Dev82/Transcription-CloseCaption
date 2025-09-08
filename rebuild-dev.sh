#!/bin/bash

echo "🔄 เริ่มต้น rebuild development environment..."

# หยุดและลบ containers เดิม
echo "📦 หยุดและลบ containers เดิม..."
docker-compose -f docker-compose.dev.yml down

# ลบ images ที่ไม่ใช้
echo "🧹 ลบ images ที่ไม่ใช้..."
docker image prune -f

# Build containers ใหม่
echo "🔨 Build containers ใหม่..."
docker-compose -f docker-compose.dev.yml build --no-cache

# เริ่มต้น containers
echo "🚀 เริ่มต้น containers..."
docker-compose -f docker-compose.dev.yml up -d

# รอให้ containers พร้อมใช้งาน
echo "⏳ รอให้ containers พร้อมใช้งาน..."
sleep 30

# ตรวจสอบสถานะ containers
echo "📊 ตรวจสอบสถานะ containers..."
docker-compose -f docker-compose.dev.yml ps

# ตรวจสอบ logs ของ API
echo "📋 ตรวจสอบ API logs..."
docker-compose -f docker-compose.dev.yml logs api

# ตรวจสอบ logs ของ Whisper
echo "📋 ตรวจสอบ Whisper logs..."
docker-compose -f docker-compose.dev.yml logs whisper

echo "✅ เสร็จสิ้นการ rebuild development environment!"
echo ""
echo "🌐 Services ที่พร้อมใช้งาน:"
echo "  - API: http://localhost:8001"
echo "  - Whisper API: http://localhost:8002"
echo "  - RabbitMQ Management: http://localhost:15672"
echo "  - Redis: localhost:6379"
echo ""
echo "📝 คำสั่งที่มีประโยชน์:"
echo "  - ดู logs: docker-compose -f docker-compose.dev.yml logs -f [service]"
echo "  - หยุด: docker-compose -f docker-compose.dev.yml down"
echo "  - Restart: docker-compose -f docker-compose.dev.yml restart [service]" 