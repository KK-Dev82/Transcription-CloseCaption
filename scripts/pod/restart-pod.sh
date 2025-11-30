#!/bin/bash
# Script สำหรับ Restart Services ทั้งหมด
#
# วิธีใช้งาน:
#   bash scripts/pod/restart-pod.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

echo "🔄 Restarting Transcription Services"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Stop services
print_status "Stopping services..."
bash stop-pod.sh

echo ""

# Start services
print_status "Starting services..."
bash start-pod.sh

echo ""
print_success "🎉 Services restarted!"
echo ""

