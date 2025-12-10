#!/bin/bash
# Script สำหรับรัน Dashboard บน macOS Local

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Transcription Service Dashboard (Local macOS)"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Check or create venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Get port from env or default
PORT=${DASHBOARD_PORT:-8020}

echo ""
echo "✅ Starting Dashboard on http://localhost:${PORT}"
echo ""
echo "📊 Dashboard Features:"
echo "   - Monitor 4000-ada and 5080 servers"
echo "   - View transcription tasks"
echo "   - Delete old tasks"
echo "   - Batch transcription testing"
echo ""
echo "💡 Press Ctrl+C to stop"
echo ""

# Run the dashboard
# Use uvicorn directly (better for package imports)
python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload

