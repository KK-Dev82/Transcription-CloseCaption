#!/bin/bash
# Script สำหรับ Restart Local Docker Services

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_status "🔄 Restarting Local Docker Services"
echo ""

# Stop services (skip prompt)
bash "$SCRIPT_DIR/stop-local.sh" --no-prompt 2>/dev/null || {
    print_status "Services may not be running, continuing..."
}

echo ""

# Start services
bash "$SCRIPT_DIR/start-local.sh"

echo ""
print_success "🎉 Services restarted!"

