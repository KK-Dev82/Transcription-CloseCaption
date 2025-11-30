#!/bin/bash
# Script สำหรับ Stop Services ทั้งหมด
#
# วิธีใช้งาน:
#   bash scripts/pod/stop-pod.sh

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

echo "🛑 Stopping Transcription Services"
echo "📅 $(date)"
echo ""

# Stop Main API
print_status "Stopping Main API..."
pkill -f "python.*uvicorn.*app.main" && print_success "✅ Main API stopped" || print_warning "⚠️  Main API not running"

# Stop Whisper API
print_status "Stopping Whisper API..."
pkill -f "python.*whisper_api" && print_success "✅ Whisper API stopped" || print_warning "⚠️  Whisper API not running"

# Stop Video Worker
print_status "Stopping Video Worker..."
pkill -f "python.*video_worker" && print_success "✅ Video Worker stopped" || print_warning "⚠️  Video Worker not running"

# Stop Redis
print_status "Stopping Redis..."
pkill -f redis-server && print_success "✅ Redis stopped" || print_warning "⚠️  Redis not running"

sleep 2

# Check remaining processes
REMAINING=$(pgrep -f "python.*uvicorn|python.*whisper|python.*video_worker|redis-server" || true)
if [ -n "$REMAINING" ]; then
    print_warning "⚠️  Some processes still running, force killing..."
    pkill -9 -f "python.*uvicorn" 2>/dev/null || true
    pkill -9 -f "python.*whisper" 2>/dev/null || true
    pkill -9 -f "python.*video_worker" 2>/dev/null || true
    pkill -9 -f redis-server 2>/dev/null || true
    sleep 1
fi

print_success "🎉 All services stopped!"
echo ""

