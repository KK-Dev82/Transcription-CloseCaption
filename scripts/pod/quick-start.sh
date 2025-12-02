#!/bin/bash
# Quick Start Script - ติดตั้ง dependencies และ start service ในครั้งเดียว
#
# วิธีใช้งาน:
#   bash scripts/pod/quick-start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

echo "🚀 Quick Start: Transcription Service"
echo "======================================"
echo ""

# Check if running on Pod
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Step 1: Check dependencies
echo "📋 Step 1: Checking dependencies..."
if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "⚠️  Dependencies not installed"
    echo ""
    echo "📦 Installing dependencies..."
    bash scripts/pod/install-dependencies.sh || {
        echo "❌ Failed to install dependencies"
        exit 1
    }
else
    echo "✅ Dependencies already installed"
fi
echo ""

# Step 2: Setup GPU environment
echo "📋 Step 2: Setting up GPU environment..."
if [ -f "scripts/pod/setup-gpu-env.sh" ]; then
    source scripts/pod/setup-gpu-env.sh
    echo "✅ GPU environment ready"
else
    echo "⚠️  setup-gpu-env.sh not found"
fi
echo ""

# Step 3: Start service
echo "📋 Step 3: Starting service..."
bash scripts/pod/start-service-daemon.sh

echo ""
echo "✅ Quick Start Complete!"
echo ""

