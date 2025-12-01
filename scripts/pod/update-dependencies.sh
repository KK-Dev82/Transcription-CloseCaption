#!/bin/bash
# Script สำหรับอัปเดต dependencies บน Pod GPU
# Usage: bash scripts/pod/update-dependencies.sh

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_status "📦 Updating Dependencies"
print_status "📅 $(date)"
echo ""

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    print_error "❌ requirements.txt not found"
    exit 1
fi

# Install/Update faster-whisper
print_status "Installing faster-whisper..."
pip3 install --no-cache-dir faster-whisper==1.0.3 || {
    print_warning "⚠️  Failed to install faster-whisper, trying without version..."
    pip3 install --no-cache-dir faster-whisper || {
        print_error "❌ Cannot install faster-whisper"
        exit 1
    }
}
print_success "✅ faster-whisper installed"
echo ""

# Install all dependencies from requirements.txt
print_status "Installing all dependencies from requirements.txt..."
pip3 install --no-cache-dir -r requirements.txt || {
    print_warning "⚠️  Some packages failed, but continuing..."
}
print_success "✅ Dependencies updated"
echo ""

# Verify critical dependencies
print_status "Verifying critical dependencies..."
CRITICAL_DEPS=("fastapi" "uvicorn" "pydantic" "aiofiles" "redis" "pika" "faster_whisper" "openai_whisper" "torch")
ALL_OK=true

for dep in "${CRITICAL_DEPS[@]}"; do
    if python3 -c "import ${dep//-/_}" 2>/dev/null; then
        print_success "   ✅ $dep"
    else
        print_error "   ❌ $dep (missing)"
        ALL_OK=false
    fi
done

# Check python-dotenv separately
if python3 -c "import dotenv" 2>/dev/null; then
    print_success "   ✅ python-dotenv"
else
    print_error "   ❌ python-dotenv (missing)"
    ALL_OK=false
fi

echo ""

if [ "$ALL_OK" = true ]; then
    print_success "✅ All critical dependencies are installed"
else
    print_warning "⚠️  Some dependencies are missing"
fi

# Check faster-whisper version
print_status "Checking faster-whisper version..."
python3 -c "import faster_whisper; print(f'faster-whisper version: {faster_whisper.__version__}')" 2>/dev/null || {
    print_warning "⚠️  Cannot get faster-whisper version"
}

echo ""
print_success "✅ Dependency update completed!"

