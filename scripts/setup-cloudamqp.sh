#!/bin/bash
# Setup CloudAMQP connection

echo "=================================================================================="
echo "📋 Setup CloudAMQP"
echo "=================================================================================="

echo ""
echo "📝 ขั้นตอนการตั้งค่า:"
echo "   1. ไปที่ https://www.cloudamqp.com/"
echo "   2. สร้าง account (free tier available)"
echo "   3. สร้าง instance"
echo "   4. เลือก region ที่ใกล้ที่สุด"
echo "   5. Copy connection details"
echo ""

read -p "RabbitMQ Host (e.g., your-instance.cloudamqp.com): " RABBITMQ_HOST
read -p "RabbitMQ Port (default 5672, SSL: 5671): " RABBITMQ_PORT
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
read -p "RabbitMQ User: " RABBITMQ_USER
read -p "RabbitMQ Password: " -s RABBITMQ_PASSWORD
echo ""
read -p "RabbitMQ VHost (default /): " RABBITMQ_VHOST
RABBITMQ_VHOST=${RABBITMQ_VHOST:-/}
read -p "Use SSL/TLS? (y/n, default y): " USE_SSL
USE_SSL=${USE_SSL:-y}

if [ -z "$RABBITMQ_HOST" ] || [ -z "$RABBITMQ_USER" ] || [ -z "$RABBITMQ_PASSWORD" ]; then
    echo "❌ RabbitMQ Host, User และ Password ต้องไม่ว่าง"
    exit 1
fi

# สร้าง .env.runpod หรืออัปเดต
ENV_FILE=".env.runpod"
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# อัปเดต RabbitMQ configuration
if grep -q "RABBITMQ_HOST" "$ENV_FILE"; then
    sed -i "s|RABBITMQ_HOST=.*|RABBITMQ_HOST=$RABBITMQ_HOST|" "$ENV_FILE"
else
    echo "RABBITMQ_HOST=$RABBITMQ_HOST" >> "$ENV_FILE"
fi

if grep -q "RABBITMQ_PORT" "$ENV_FILE"; then
    sed -i "s|RABBITMQ_PORT=.*|RABBITMQ_PORT=$RABBITMQ_PORT|" "$ENV_FILE"
else
    echo "RABBITMQ_PORT=$RABBITMQ_PORT" >> "$ENV_FILE"
fi

if grep -q "RABBITMQ_USER" "$ENV_FILE"; then
    sed -q "s|RABBITMQ_USER=.*|RABBITMQ_USER=$RABBITMQ_USER|" "$ENV_FILE"
else
    echo "RABBITMQ_USER=$RABBITMQ_USER" >> "$ENV_FILE"
fi

if grep -q "RABBITMQ_PASSWORD" "$ENV_FILE"; then
    sed -i "s|RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD|" "$ENV_FILE"
else
    echo "RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD" >> "$ENV_FILE"
fi

if grep -q "RABBITMQ_VHOST" "$ENV_FILE"; then
    sed -i "s|RABBITMQ_VHOST=.*|RABBITMQ_VHOST=$RABBITMQ_VHOST|" "$ENV_FILE"
else
    echo "RABBITMQ_VHOST=$RABBITMQ_VHOST" >> "$ENV_FILE"
fi

if [ "$USE_SSL" = "y" ] || [ "$USE_SSL" = "Y" ]; then
    if grep -q "RABBITMQ_USE_SSL" "$ENV_FILE"; then
        sed -i "s|RABBITMQ_USE_SSL=.*|RABBITMQ_USE_SSL=true|" "$ENV_FILE"
    else
        echo "RABBITMQ_USE_SSL=true" >> "$ENV_FILE"
    fi
    echo "✅ SSL/TLS enabled"
else
    if grep -q "RABBITMQ_USE_SSL" "$ENV_FILE"; then
        sed -i "s|RABBITMQ_USE_SSL=.*|RABBITMQ_USE_SSL=false|" "$ENV_FILE"
    else
        echo "RABBITMQ_USE_SSL=false" >> "$ENV_FILE"
    fi
fi

echo ""
echo "✅ CloudAMQP configuration saved to $ENV_FILE"
echo ""
echo "📋 Configuration:"
echo "   RABBITMQ_HOST=$RABBITMQ_HOST"
echo "   RABBITMQ_PORT=$RABBITMQ_PORT"
echo "   RABBITMQ_USER=$RABBITMQ_USER"
echo "   RABBITMQ_PASSWORD=***"
echo "   RABBITMQ_VHOST=$RABBITMQ_VHOST"
echo "   RABBITMQ_USE_SSL=$USE_SSL"
echo ""

# ทดสอบ connection
echo "🔍 Testing CloudAMQP connection..."
python3 << PYTHON_EOF
import os
import sys
from dotenv import load_dotenv

load_dotenv('.env.runpod')

import pika

try:
    credentials = pika.PlainCredentials(
        os.getenv('RABBITMQ_USER'),
        os.getenv('RABBITMQ_PASSWORD')
    )
    
    parameters = pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST'),
        port=int(os.getenv('RABBITMQ_PORT', 5672)),
        virtual_host=os.getenv('RABBITMQ_VHOST', '/'),
        credentials=credentials,
        connection_attempts=3,
        retry_delay=2
    )
    
    # Add SSL if enabled
    if os.getenv('RABBITMQ_USE_SSL', 'false').lower() == 'true':
        import ssl
        ssl_context = ssl.create_default_context()
        parameters.ssl_options = pika.SSLOptions(ssl_context, server_hostname=os.getenv('RABBITMQ_HOST'))
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    print("✅ CloudAMQP connection successful!")
    print(f"   Host: {os.getenv('RABBITMQ_HOST')}")
    print(f"   Port: {os.getenv('RABBITMQ_PORT', 5672)}")
    print(f"   VHost: {os.getenv('RABBITMQ_VHOST', '/')}")
    print(f"   SSL: {os.getenv('RABBITMQ_USE_SSL', 'false')}")
    
    connection.close()
    
except Exception as e:
    print(f"❌ CloudAMQP connection error: {e}")
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================================================="
    echo "✅ CloudAMQP setup complete!"
    echo "=================================================================================="
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Restart worker: python3 -m app.workers.sync.video_worker"
    echo "   2. Test transcription"
    echo ""
else
    echo ""
    echo "❌ CloudAMQP connection test failed"
    echo "   Please check your CloudAMQP credentials"
    exit 1
fi

