#!/bin/bash
# Script สำหรับรัน Transcription Service ที่ local ด้วย whisper.cpp
# เหมาะสำหรับ Local Testing บน Mac Mini M4 (ใช้ CPU)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎤 Starting Transcription Service (whisper.cpp - Local Test)"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Check whisper.cpp
WHISPER_CPP_PATH="${WHISPER_CPP_PATH:-whisper.cpp/main}"
if [ ! -f "$WHISPER_CPP_PATH" ]; then
    echo "⚠️  Warning: whisper.cpp not found at $WHISPER_CPP_PATH"
    echo ""
    echo "📋 To install whisper.cpp:"
    echo "   1. Clone repository:"
    echo "      git clone https://github.com/ggerganov/whisper.cpp.git"
    echo "   2. Build (macOS with Metal):"
    echo "      cd whisper.cpp"
    echo "      make clean"
    echo "      make -j"
    echo "   3. Download model:"
    echo "      ./models/download-ggml-model.sh base"
    echo ""
    echo "   Or set WHISPER_CPP_PATH environment variable to point to whisper.cpp executable"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check or create venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies (minimal - ไม่ต้องติดตั้ง faster-whisper)
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q fastapi uvicorn python-multipart aiofiles pydantic python-dotenv ffmpeg-python websockets

# Set environment variables
export TRANSCRIPTION_MOCK_MODE=false
export WHISPER_PROVIDER=whisper-cpp
export WHISPER_MODEL=${WHISPER_MODEL:-base}
export WHISPER_MODEL_DIR=${WHISPER_MODEL_DIR:-models}

# Auto-detect Metal on macOS Apple Silicon
if [[ "$OSTYPE" == "darwin"* ]] && [[ $(uname -m) == "arm64" ]]; then
    export WHISPER_USE_METAL=${WHISPER_USE_METAL:-true}
    echo "🍎 Detected Apple Silicon - Metal acceleration enabled"
else
    export WHISPER_USE_METAL=false
fi

# Get port from env or default
PORT=${TRANSCRIPTION_PORT:-8012}

echo ""
echo "✅ Starting Transcription Service (whisper.cpp) on http://localhost:${PORT}"
echo ""
echo "📋 Configuration:"
echo "   - Provider: whisper-cpp"
echo "   - Model: ${WHISPER_MODEL}"
echo "   - Model Dir: ${WHISPER_MODEL_DIR}"
echo "   - Use Metal: ${WHISPER_USE_METAL}"
echo "   - Whisper.cpp Path: ${WHISPER_CPP_PATH}"
echo ""
echo "💡 Press Ctrl+C to stop"
echo ""

# Run the service
# ไม่ใช้ --reload เพื่อหลีกเลี่ยงปัญหา multiprocessing ใน macOS
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

