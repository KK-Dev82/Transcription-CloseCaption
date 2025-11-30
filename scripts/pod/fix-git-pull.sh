#!/bin/bash
# Script สำหรับแก้ไขปัญหา git pull เมื่อมี .env.runpod ที่ untracked
#
# วิธีใช้งาน:
# bash scripts/pod/fix-git-pull.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔧 Fixing Git Pull Issue"
echo "📅 $(date)"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if .env.runpod exists
if [ -f ".env.runpod" ]; then
    print_status "Found .env.runpod file"
    
    # Check if it's tracked by git
    if git ls-files --error-unmatch .env.runpod > /dev/null 2>&1; then
        print_status ".env.runpod is tracked by git"
    else
        print_warning ".env.runpod is untracked (not in git)"
        
        # Backup .env.runpod
        print_status "Backing up .env.runpod..."
        BACKUP_FILE=".env.runpod.backup.$(date +%Y%m%d_%H%M%S)"
        cp .env.runpod "$BACKUP_FILE"
        cp .env.runpod /workspace/.env.runpod.backup 2>/dev/null || true
        print_success "✅ Backed up to: $BACKUP_FILE"
        
        # Temporarily move .env.runpod
        print_status "Temporarily moving .env.runpod..."
        mv .env.runpod .env.runpod.tmp
        print_success "✅ Moved to .env.runpod.tmp"
    fi
else
    print_status "No .env.runpod file found"
fi

# Try git pull
print_status "Attempting git pull..."
if git pull; then
    print_success "✅ Git pull successful!"
    
    # Restore .env.runpod
    if [ -f ".env.runpod.tmp" ]; then
        print_status "Restoring .env.runpod..."
        mv .env.runpod.tmp .env.runpod
        print_success "✅ .env.runpod restored"
        
        # Ensure RabbitMQ config is correct
        if grep -q "RABBITMQ_HOST=localhost" .env.runpod; then
            print_status "🔧 Auto-updating RabbitMQ configuration..."
            sed -i 's/RABBITMQ_HOST=localhost/RABBITMQ_HOST=178.128.105.100/g' .env.runpod
            print_success "✅ Updated RABBITMQ_HOST to 178.128.105.100"
        fi
    fi
else
    print_error "❌ Git pull failed!"
    
    # Restore .env.runpod even if pull failed
    if [ -f ".env.runpod.tmp" ]; then
        print_status "Restoring .env.runpod..."
        mv .env.runpod.tmp .env.runpod
        print_success "✅ .env.runpod restored"
    fi
    
    exit 1
fi

echo ""
print_success "🎉 Git pull completed successfully!"
echo ""
print_status "💡 Next steps:"
echo "   # Restart services if needed:"
echo "   bash scripts/pod/restart-pod-services.sh"

