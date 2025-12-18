#!/bin/bash
# Setup Redis Cloud (redis.io) connection

echo "=================================================================================="
echo "📋 Setup Redis Cloud (redis.io)"
echo "=================================================================================="

echo ""
echo "📝 ขั้นตอนการตั้งค่า:"
echo "   1. ไปที่ https://redis.io/try-free/"
echo "   2. สร้าง account (free tier)"
echo "   3. สร้าง database"
echo "   4. Copy connection details"
echo ""

read -p "Redis Host (e.g., redis-12345.redis.cloud): " REDIS_HOST
read -p "Redis Port (default 12345): " REDIS_PORT
REDIS_PORT=${REDIS_PORT:-12345}
read -p "Redis Password: " -s REDIS_PASSWORD
echo ""

if [ -z "$REDIS_HOST" ] || [ -z "$REDIS_PASSWORD" ]; then
    echo "❌ Redis Host และ Password ต้องไม่ว่าง"
    exit 1
fi

# สร้าง .env.runpod หรืออัปเดต
ENV_FILE=".env.runpod"
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# อัปเดต Redis configuration
if grep -q "REDIS_HOST" "$ENV_FILE"; then
    sed -i "s|REDIS_HOST=.*|REDIS_HOST=$REDIS_HOST|" "$ENV_FILE"
else
    echo "REDIS_HOST=$REDIS_HOST" >> "$ENV_FILE"
fi

if grep -q "REDIS_PORT" "$ENV_FILE"; then
    sed -i "s|REDIS_PORT=.*|REDIS_PORT=$REDIS_PORT|" "$ENV_FILE"
else
    echo "REDIS_PORT=$REDIS_PORT" >> "$ENV_FILE"
fi

if grep -q "REDIS_PASSWORD" "$ENV_FILE"; then
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" "$ENV_FILE"
else
    echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> "$ENV_FILE"
fi

echo ""
echo "✅ Redis configuration saved to $ENV_FILE"
echo ""
echo "📋 Configuration:"
echo "   REDIS_HOST=$REDIS_HOST"
echo "   REDIS_PORT=$REDIS_PORT"
echo "   REDIS_PASSWORD=***"
echo ""

# ทดสอบ connection
echo "🔍 Testing Redis connection..."
python3 << PYTHON_EOF
import os
import sys
from dotenv import load_dotenv

load_dotenv('.env.runpod')

import redis

try:
    r = redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        password=os.getenv('REDIS_PASSWORD'),
        decode_responses=True,
        socket_connect_timeout=5
    )
    result = r.ping()
    if result:
        print("✅ Redis connection successful!")
        print(f"   Host: {os.getenv('REDIS_HOST')}")
        print(f"   Port: {os.getenv('REDIS_PORT', 6379)}")
    else:
        print("❌ Redis connection failed")
        sys.exit(1)
except Exception as e:
    print(f"❌ Redis connection error: {e}")
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================================================="
    echo "✅ Redis Cloud setup complete!"
    echo "=================================================================================="
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Restart worker: python3 -m app.workers.sync.redis_worker"
    echo "   2. Test transcription"
    echo ""
else
    echo ""
    echo "❌ Redis connection test failed"
    echo "   Please check your Redis credentials"
    exit 1
fi

