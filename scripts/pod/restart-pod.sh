#!/bin/bash
# Script สำหรับ Restart Services ทั้งหมด
# หยุด services ทั้งหมด แล้ว start ใหม่

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

echo "🔄 Restarting Transcription Services"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 1. หยุด RQ Workers
print_status "Stopping RQ Workers..."
bash "$SCRIPT_DIR/stop-rq-workers.sh" 2>/dev/null || {
    pkill -f "rq worker.*transcription" 2>/dev/null || true
    sleep 2
}
print_success "✅ RQ Workers stopped"

# 2. หยุด Main API
print_status "Stopping Main API..."
pkill -f "python.*uvicorn.*app.main" 2>/dev/null || true
sleep 2
print_success "✅ Main API stopped"

# 3. หยุด Video Worker
print_status "Stopping Video Worker..."
pkill -f "python.*video_worker" 2>/dev/null || true
sleep 2
print_success "✅ Video Worker stopped"

# 4. หยุด Whisper API
print_status "Stopping Whisper API..."
pkill -f "python.*whisper_api" 2>/dev/null || true
sleep 2
print_success "✅ Whisper API stopped"

echo ""

# 5. Start Services ใหม่
print_status "Starting services..."
bash "$SCRIPT_DIR/start-pod.sh"

echo ""
print_success "🎉 Services restarted!"
