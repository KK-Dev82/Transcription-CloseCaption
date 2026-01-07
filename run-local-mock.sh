#!/bin/bash
# Script สำหรับรัน Transcription Service ที่ local ใน MOCK MODE
# (ไม่ต้องทำ transcription ด้วย faster-whisper - สำหรับทดสอบ stream connectivity)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧪 Starting Transcription Service (MOCK MODE - Local)"
echo "=================================================="
echo ""
echo "⚠️  MOCK MODE: Transcription disabled - only testing stream connectivity"
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

# Install dependencies (minimal - ไม่ต้องติดตั้ง faster-whisper)
echo "📥 Installing dependencies (minimal for MOCK MODE)..."
pip install -q --upgrade pip
pip install -q fastapi uvicorn python-multipart aiofiles pydantic python-dotenv ffmpeg-python websockets

# Set MOCK MODE
export TRANSCRIPTION_MOCK_MODE=true

# Get port from env or default (ใช้ 8012 เพื่อหลีกเลี่ยง conflict กับ Cursor port forwarding)
PORT=${TRANSCRIPTION_PORT:-8012}

echo ""
echo "✅ Starting Transcription Service (MOCK MODE) on http://localhost:${PORT}"
echo ""
echo "📋 Features:"
echo "   - ✅ Receive audio stream from Audio Tap"
echo "   - ✅ Process stream chunks"
echo "   - ✅ Send NDJSON responses"
echo "   - 🧪 MOCK: Skip transcription (no faster-whisper required)"
echo ""
echo "💡 Press Ctrl+C to stop"
echo ""

# Run the service
# ไม่ใช้ --reload เพื่อหลีกเลี่ยงปัญหา multiprocessing ใน macOS
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

