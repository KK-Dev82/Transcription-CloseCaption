#!/bin/bash
# Script สำหรับรัน Dashboard

cd "$(dirname "$(readlink -f "$0")")"

echo "🚀 Starting Transcription Service Dashboard..."
echo "================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Load environment variables from parent .env.runpod if exists
if [ -f "../.env.runpod" ]; then
    echo "📋 Loading environment from ../.env.runpod..."
    set -a  # Automatically export all variables
    source ../.env.runpod 2>/dev/null || true
    set +a  # Stop automatically exporting
fi

# Set default port if not set
export DASHBOARD_PORT=${DASHBOARD_PORT:-8020}

echo ""
echo "✅ Starting dashboard on http://localhost:${DASHBOARD_PORT}"
echo ""

# Run dashboard
python main.py

