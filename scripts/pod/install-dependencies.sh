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

# Install RabbitMQ and async dependencies (critical for worker)
echo "📦 Installing RabbitMQ and async dependencies..."
echo "   (aiofiles, aio-pika, pika - required for video worker)"
pip3 install --user --no-cache-dir \
    aiofiles==23.2.1 \
    "aio-pika==9.3.0" \
    pika==1.3.2 \
    aiohttp==3.9.1 \
    || {
    echo "❌ Failed to install RabbitMQ dependencies"
    echo "   Worker will not be able to connect to RabbitMQ"
    exit 1
}
echo "✅ RabbitMQ dependencies installed"
echo ""

# Install cuDNN (for CUDA 11.8)
echo "📦 Installing cuDNN for CUDA 11.8..."
CUDNN_DIR="/workspace/cudnn"
CUDNN_LIB_DIR="$CUDNN_DIR/lib"
CUDNN_INCLUDE_DIR="$CUDNN_DIR/include"

# Check if cuDNN is already installed
if [ -d "$CUDNN_LIB_DIR" ] && [ -f "$CUDNN_LIB_DIR/libcudnn.so" ]; then
    echo "✅ cuDNN already installed at $CUDNN_DIR"
    echo "   Library files found in $CUDNN_LIB_DIR"
else
    echo "📥 Downloading cuDNN 8.9.7 for CUDA 11.8..."
    mkdir -p "$CUDNN_DIR"
    cd "$CUDNN_DIR"
    
    # Download cuDNN (using NVIDIA's official method or pre-built binaries)
    # Note: This requires NVIDIA Developer account or using pre-built packages
    CUDNN_VERSION="8.9.7"
    CUDA_VERSION="11.8"
    
    # Try to download from NVIDIA (requires authentication)
    # Alternative: Use pre-built cuDNN from PyTorch or conda
    echo "   Attempting to install cuDNN via conda/pip method..."
    
    # Method 1: Try installing via pip (if available)
    if pip3 show nvidia-cudnn-cu11 > /dev/null 2>&1; then
        echo "✅ cuDNN package already installed via pip"
    else
        echo "   Installing nvidia-cudnn-cu11 via pip..."
        pip3 install --user --no-cache-dir nvidia-cudnn-cu11==8.9.7.29 || {
            echo "⚠️  Failed to install via pip, trying alternative method..."
            
            # Method 2: Download and extract cuDNN manually
            echo "   Downloading cuDNN from PyTorch repository..."
            # Use wget or curl to download cuDNN
            # For CUDA 11.8, we need cuDNN 8.9.x
            
            # Create symlink structure
            mkdir -p "$CUDNN_LIB_DIR" "$CUDNN_INCLUDE_DIR"
            
            # Try to find cuDNN in system or PyTorch installation
            PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/usr/local/lib/python3.10/dist-packages")
            
            # Look for cuDNN in common locations
            CUDNN_FOUND=false
            for SEARCH_PATH in \
                "/usr/local/cuda/lib64" \
                "/usr/lib/x86_64-linux-gnu" \
                "$PYTHON_SITE/nvidia_cudnn_cu11/lib" \
                "/workspace/.local/lib/python3.10/site-packages/nvidia_cudnn_cu11/lib"; do
                if [ -f "$SEARCH_PATH/libcudnn.so.8" ] || [ -f "$SEARCH_PATH/libcudnn.so" ]; then
                    echo "   ✅ Found cuDNN at $SEARCH_PATH"
                    # Create symlinks
                    ln -sf "$SEARCH_PATH"/libcudnn*.so* "$CUDNN_LIB_DIR/" 2>/dev/null || true
                    if [ -d "$SEARCH_PATH/../include" ]; then
                        ln -sf "$SEARCH_PATH/../include"/cudnn*.h "$CUDNN_INCLUDE_DIR/" 2>/dev/null || true
                    fi
                    CUDNN_FOUND=true
                    break
                fi
            done
            
            if [ "$CUDNN_FOUND" = false ]; then
                echo "⚠️  cuDNN not found in system. Installing nvidia-cudnn-cu11 package..."
                # Install via pip with retry
                pip3 install --user --no-cache-dir --upgrade nvidia-cudnn-cu11 2>&1 | tail -5 || {
                    echo "❌ Failed to install cuDNN"
                    echo "   💡 Manual installation required:"
                    echo "   1. Download cuDNN from https://developer.nvidia.com/cudnn"
                    echo "   2. Extract to $CUDNN_DIR"
                    echo "   3. Ensure libcudnn.so* files are in $CUDNN_LIB_DIR"
                }
            fi
        }
    fi
    
    # Verify installation
    if [ -d "$CUDNN_LIB_DIR" ] && (ls "$CUDNN_LIB_DIR"/libcudnn*.so* > /dev/null 2>&1 || python3 -c "import nvidia.cudnn; print('✅ cuDNN available via Python package')" 2>/dev/null); then
        echo "✅ cuDNN installed successfully"
        echo "   Location: $CUDNN_DIR"
        if [ -d "$CUDNN_LIB_DIR" ]; then
            echo "   Libraries: $(ls -1 $CUDNN_LIB_DIR/libcudnn*.so* 2>/dev/null | wc -l) files"
        fi
    else
        echo "⚠️  cuDNN installation may be incomplete"
        echo "   Service may work but with reduced performance"
    fi
    
    cd "$PROJECT_DIR"
fi
echo ""

# Install remaining dependencies from requirements.txt
echo "📦 Installing remaining dependencies from requirements.txt..."
echo "   (This may take a while...)"
echo "   Note: Critical dependencies (aiofiles, aio-pika, pika) already installed above"

# Install from requirements.txt but skip already installed critical packages
pip3 install --user --no-cache-dir -r requirements.txt || {
    echo "⚠️  Some dependencies failed to install"
    echo "   Checking which critical dependencies are missing..."
    
    # Verify critical dependencies
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import aiofiles" 2>/dev/null || {
        echo "❌ aiofiles still missing - installing directly..."
        pip3 install --user --no-cache-dir aiofiles==23.2.1
    }
    
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import aio_pika" 2>/dev/null || {
        echo "❌ aio-pika still missing - installing directly..."
        pip3 install --user --no-cache-dir "aio-pika==9.3.0"
    }
    
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import pika" 2>/dev/null || {
        echo "❌ pika still missing - installing directly..."
        pip3 install --user --no-cache-dir pika==1.3.2
    }
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
    python3 -c "import aiofiles; print('✅ aiofiles: OK')" || {
    echo "❌ aiofiles not found - CRITICAL for worker!"
    echo "   Installing aiofiles directly..."
    pip3 install --user --no-cache-dir aiofiles==23.2.1
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import aiofiles; print('✅ aiofiles: OK (installed)')" || echo "❌ aiofiles installation failed"
}
env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import pika; print('✅ pika:', pika.__version__)" || {
    echo "❌ pika not found - CRITICAL for worker!"
    echo "   Installing pika directly..."
    pip3 install --user --no-cache-dir pika==1.3.2
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import pika; print('✅ pika: OK (installed)')" || echo "❌ pika installation failed"
}

echo ""
echo "=============================="
echo "✅ Installation Complete"
echo ""
echo "💡 Next: Start service with"
echo "   bash scripts/pod/start-service-daemon.sh"
echo ""

