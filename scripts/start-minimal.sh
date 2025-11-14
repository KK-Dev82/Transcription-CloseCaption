#!/bin/bash

# Script สำหรับเริ่มระบบบน Minimal Server (2 CPU, 2GB RAM)
# ใช้ memory และ CPU น้อยที่สุดที่ยังทำงานได้

echo "🚀 Starting Transcription Service on Minimal Server (2 CPU, 2GB RAM)..."

# ตรวจสอบ Docker และ Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ไม่ได้ติดตั้ง"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose ไม่ได้ติดตั้ง"
    exit 1
fi

# ตรวจสอบไฟล์ docker-compose.minimal.yml
if [ ! -f "docker-compose.minimal.yml" ]; then
    echo "❌ ไม่พบไฟล์ docker-compose.minimal.yml"
    exit 1
fi

# ตรวจสอบ system resources
echo "🔍 Checking system resources..."
TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
TOTAL_CPU=$(nproc)

echo "   Total Memory: ${TOTAL_MEM}MB"
echo "   Total CPU: ${TOTAL_CPU} cores"

if [ "$TOTAL_MEM" -lt 1800 ]; then
    echo "⚠️  Warning: Memory อาจไม่เพียงพอ (แนะนำอย่างน้อย 2GB)"
fi

if [ "$TOTAL_CPU" -lt 2 ]; then
    echo "⚠️  Warning: CPU อาจไม่เพียงพอ (แนะนำอย่างน้อย 2 cores)"
fi

# สร้าง directories ที่จำเป็น
echo "📁 Creating necessary directories..."
mkdir -p uploads storage temp models
mkdir -p storage/transcriptions storage/captions storage/videos storage/metadata

# ตั้งค่า permissions
echo "🔧 Setting up permissions..."
chmod 755 uploads/ storage/ temp/ models/
chmod 644 uploads/* storage/* temp/* models/* 2>/dev/null || true

# ตรวจสอบ Whisper model
if [ ! -f "models/ggml-base.bin" ]; then
    echo "⚠️  ไม่พบ Whisper model"
    echo "📥 Downloading Whisper model..."
    if [ -f "scripts/download-models.sh" ]; then
        chmod +x scripts/download-models.sh
        ./scripts/download-models.sh
    else
        echo "❌ ไม่พบ script download-models.sh"
        echo "กรุณาดาวน์โหลด model ด้วยตนเอง:"
        echo "wget -O models/ggml-base.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
        exit 1
    fi
fi

# ตรวจสอบขนาด model
if [ -f "models/ggml-base.bin" ]; then
    MODEL_SIZE=$(stat -c%s "models/ggml-base.bin" 2>/dev/null || echo "0")
    if [ "$MODEL_SIZE" -lt 100000000 ]; then
        echo "❌ Model file ผิดปกติ (ขนาด: $MODEL_SIZE bytes)"
        echo "กรุณาดาวน์โหลด model ใหม่"
        exit 1
    fi
    echo "✅ Whisper model พร้อมใช้งาน (ขนาด: $(($MODEL_SIZE / 1024 / 1024))MB)"
fi

# เริ่มระบบ
echo "🐳 Starting Docker containers..."
docker compose -f docker-compose.minimal.yml down
docker compose -f docker-compose.minimal.yml up -d

# รอให้ containers เริ่มต้น
echo "⏳ Waiting for services to start..."
sleep 15

# ตรวจสอบสถานะ
echo "🔍 Checking service status..."
docker compose -f docker-compose.minimal.yml ps

# ตรวจสอบ resource usage
echo "📊 Checking resource usage..."
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# ตรวจสอบ health
echo "🏥 Checking service health..."
sleep 10

# ตรวจสอบ API
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ API Service: Ready"
else
    echo "❌ API Service: Not ready"
fi

# ตรวจสอบ Whisper
if curl -s http://localhost:8002/health > /dev/null; then
    echo "✅ Whisper Service: Ready"
else
    echo "❌ Whisper Service: Not ready"
fi

# ตรวจสอบ Redis
if docker exec transcription-redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Ready"
else
    echo "❌ Redis: Not ready"
fi

# ตรวจสอบ RabbitMQ
if docker exec transcription-rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
    echo "✅ RabbitMQ: Ready"
else
    echo "❌ RabbitMQ: Not ready"
fi

echo ""
echo "🎉 Transcription Service started successfully!"
echo ""
echo "📊 Service URLs:"
echo "   API: http://localhost:8001"
echo "   Whisper: http://localhost:8002"
echo "   RabbitMQ Management: http://localhost:15672 (admin/admin123)"
echo ""
echo "📝 Useful commands:"
echo "   View logs: docker compose -f docker-compose.minimal.yml logs -f"
echo "   Stop services: docker compose -f docker-compose.minimal.yml down"
echo "   Restart: docker compose -f docker-compose.minimal.yml restart"
echo "   Check resources: docker stats"
echo ""
echo "💡 Resource Usage:"
echo "   Total Memory: ~1.8GB (จาก 2GB)"
echo "   Total CPU: ~1.7 cores (จาก 2 cores)"
echo "   Free Memory: ~200MB"
echo ""
echo "⚠️  Performance Notes:"
echo "   - Transcription จะช้ากว่าปกติ (1-3 นาทีสำหรับไฟล์ 1 นาที)"
echo "   - ระบบจะทำงานได้แต่ไม่แนะนำสำหรับ production"
echo "   - แนะนำใช้เฉพาะการทดสอบหรือ development"
