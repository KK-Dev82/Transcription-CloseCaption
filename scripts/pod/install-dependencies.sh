#!/bin/bash
# Script สำหรับติดตั้ง Dependencies สำหรับ Transcription Service
#
# วิธีใช้งาน:
#   bash scripts/pod/install-dependencies.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

echo "📦 Installing Dependencies"
echo "=========================="
echo ""

# Check if running on Pod
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Check Python version
echo "🐍 Checking Python..."
python3 --version
echo ""

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found"
    exit 1
fi

# Install system dependencies (FFmpeg, etc.)
echo "🔧 Installing system dependencies..."
if command -v apt-get > /dev/null 2>&1; then
    # Check if ffmpeg is already installed
    if ! command -v ffmpeg > /dev/null 2>&1; then
        echo "📦 Installing FFmpeg..."
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq ffmpeg > /dev/null 2>&1 || {
            echo "⚠️  Failed to install FFmpeg via apt-get"
            echo "   You may need to install it manually"
        }
        
        if command -v ffmpeg > /dev/null 2>&1; then
            echo "✅ FFmpeg installed successfully"
        else
            echo "❌ FFmpeg installation failed"
        fi
    else
        FFMPEG_VERSION=$(ffmpeg -version | head -n1 | awk '{print $3}')
        echo "✅ FFmpeg already installed (version: $FFMPEG_VERSION)"
    fi
    
    # Check if ffprobe is available (usually comes with ffmpeg)
    if ! command -v ffprobe > /dev/null 2>&1; then
        echo "⚠️  ffprobe not found (usually comes with ffmpeg)"
    else
        echo "✅ ffprobe is available"
    fi
else
    echo "⚠️  apt-get not found, skipping system dependencies installation"
    echo "   Please install FFmpeg manually if needed"
fi
echo ""

echo "📋 Installing from requirements.txt..."
echo "   This may take several minutes..."
echo ""

# Setup persistent installation location
# Detect Python version dynamically
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE_PACKAGES="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH"

# Create persistent directories
mkdir -p "$PYTHON_SITE_PACKAGES"
mkdir -p "/workspace/.local/bin"

echo "📁 Installing to persistent location: /workspace/.local"
echo "   Python version: ${PYTHON_VERSION}"
echo "   Installation path: ${PYTHON_SITE_PACKAGES}"
echo "   (Packages will persist after container restart)"
echo ""

# Install dependencies (skip if already installed)
if [ -f ".deps_installed" ]; then
    echo "⚠️  Dependencies may already be installed (.deps_installed exists)"
    echo "   Continuing anyway..."
    echo ""
fi

# Install core dependencies first (fastapi, uvicorn) to persistent location
echo "📦 Installing core dependencies (FastAPI, Uvicorn)..."
pip3 install --user --no-cache-dir \
    fastapi==0.104.1 \
    "uvicorn[standard]==0.24.0" \
    python-multipart==0.0.6 \
    pydantic==2.5.0 \
    || {
    echo "❌ Failed to install core dependencies"
    exit 1
}
echo "✅ Core dependencies installed"
echo ""

# Install PyTorch with CUDA support (if not already installed)
echo "📦 Checking PyTorch..."
if ! env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import torch; print(f'PyTorch: {torch.__version__}')" 2>/dev/null; then
    echo "📦 Installing PyTorch with CUDA 11.8..."
    pip3 install --user --no-cache-dir \
        torch==2.1.0 \
        torchaudio==2.1.0 \
        --index-url https://download.pytorch.org/whl/cu118 \
        || {
        echo "❌ Failed to install PyTorch"
        exit 1
    }
    echo "✅ PyTorch installed"
else
    echo "✅ PyTorch already installed"
fi
echo ""

# Install faster-whisper and dependencies
echo "📦 Installing Whisper dependencies..."
pip3 install --user --no-cache-dir \
    numpy==1.26.4 \
    "ctranslate2==4.4.0" \
    "faster-whisper==1.0.2" \
    || {
    echo "⚠️  Some Whisper dependencies failed (may continue anyway)"
}
echo "✅ Whisper dependencies installed"
echo ""

# Install remaining dependencies from requirements.txt
echo "📦 Installing remaining dependencies..."
echo "   (This may take a while...)"

pip3 install --user --no-cache-dir -r requirements.txt || {
    echo "⚠️  Some dependencies failed to install"
    echo "   Service may still work with core dependencies"
}

echo ""
echo "✅ Dependencies installation completed"
echo ""

# Mark as installed
touch .deps_installed

# Verify installation (ใช้ PYTHONPATH ที่ถูกต้อง)
echo "🔍 Verifying installation..."
env PYTHONUSERBASE="/workspace/.local" \
    PATH="/workspace/.local/bin:$PATH" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import uvicorn; print('✅ uvicorn:', uvicorn.__version__)" || echo "❌ uvicorn not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import fastapi; print('✅ fastapi:', fastapi.__version__)" || echo "❌ fastapi not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import torch; print('✅ torch:', torch.__version__)" || echo "⚠️  torch not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "from faster_whisper import WhisperModel; print('✅ faster-whisper: OK')" || echo "⚠️  faster-whisper not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import aio_pika; print('✅ aio-pika:', aio_pika.__version__)" || echo "⚠️  aio-pika not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import aiofiles; print('✅ aiofiles: OK')" || echo "⚠️  aiofiles not found"
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import pika; print('✅ pika:', pika.__version__)" || echo "⚠️  pika not found"

echo ""
echo "=============================="
echo "✅ Installation Complete"
echo ""
echo "💡 Next: Start service with"
echo "   bash scripts/pod/start-service-daemon.sh"
echo ""

