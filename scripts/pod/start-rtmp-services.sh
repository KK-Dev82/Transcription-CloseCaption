#!/bin/bash
# Script สำหรับ Start RTMP Services (nginx-rtmp, transcription, burn-in)
# ใช้สำหรับทดสอบระบบ RTMP → HLS → Transcription → Close Caption

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🚀 Starting RTMP Services"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if nginx-rtmp is installed
print_status "Checking nginx-rtmp..."
if ! command -v nginx &> /dev/null; then
    print_warning "⚠️  nginx not found. Installing nginx with rtmp module..."
    
    # Install nginx with rtmp module (Ubuntu/Debian)
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y nginx libnginx-mod-rtmp ffmpeg
    else
        print_error "❌ Please install nginx with rtmp module manually"
        exit 1
    fi
fi

# Create HLS directories
print_status "Creating HLS directories..."
mkdir -p /tmp/hls/clean
mkdir -p /tmp/hls/cc
print_success "✅ HLS directories created"

# Copy nginx-rtmp config
print_status "Setting up nginx-rtmp config..."
if [ -f "config/nginx-rtmp.conf" ]; then
    # Backup existing config
    if [ -f "/etc/nginx/nginx.conf" ]; then
        sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # Copy config
    sudo cp config/nginx-rtmp.conf /etc/nginx/nginx.conf
    
    # Test nginx config
    if sudo nginx -t; then
        print_success "✅ Nginx config is valid"
    else
        print_error "❌ Nginx config is invalid"
        exit 1
    fi
else
    print_error "❌ nginx-rtmp.conf not found at config/nginx-rtmp.conf"
    exit 1
fi

# Start nginx
print_status "Starting nginx..."
if pgrep -x nginx > /dev/null; then
    print_warning "⚠️  nginx already running, reloading..."
    sudo nginx -s reload
else
    sudo nginx
fi

# Wait for nginx to start
sleep 2

# Check nginx status
if pgrep -x nginx > /dev/null; then
    print_success "✅ nginx started"
else
    print_error "❌ nginx failed to start"
    exit 1
fi

# Check RTMP port
print_status "Checking RTMP port (1935)..."
if netstat -tuln | grep -q ":1935"; then
    print_success "✅ RTMP server is listening on port 1935"
else
    print_warning "⚠️  RTMP port 1935 not listening"
fi

# Check HTTP port
print_status "Checking HTTP port (8080)..."
if netstat -tuln | grep -q ":8080"; then
    print_success "✅ HTTP server is listening on port 8080"
else
    print_warning "⚠️  HTTP port 8080 not listening"
fi

echo ""
print_success "🎉 RTMP Services started!"
echo ""
print_status "💡 RTMP Push URL: rtmp://localhost:1935/live/stream_key"
print_status "💡 HLS Clean URL: http://localhost:8080/hls/clean/stream_key.m3u8"
print_status "💡 HLS CC URL: http://localhost:8080/hls/cc/stream_key.m3u8"
print_status "💡 RTMP Stats: http://localhost:8080/stat"
print_status "💡 Frontend: http://localhost:8010/static/rtmp-streaming.html"
echo ""

