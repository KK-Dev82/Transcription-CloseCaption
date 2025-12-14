#!/bin/bash
# Script สำหรับติดตั้ง Dependencies สำหรับ Transcription Service
# ปรับปรุง: ตรวจสอบ dependencies ที่มีอยู่แล้วก่อนติดตั้ง (ไม่ติดตั้งซ้ำ)
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

# Setup persistent installation location
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE_PACKAGES="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

export PYTHONUSERBASE="/workspace/.local"
export PATH="/workspace/.local/bin:$PATH"
export PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH"

# Create persistent directories
mkdir -p "$PYTHON_SITE_PACKAGES"
mkdir -p "/workspace/.local/bin"

echo "📁 Installation location: /workspace/.local"
echo "   Python version: ${PYTHON_VERSION}"
echo "   Installation path: ${PYTHON_SITE_PACKAGES}"
echo ""

# ============================================================
# Step 1: Install System Dependencies (FFmpeg, tzdata)
# ============================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Step 1: System Dependencies (FFmpeg, tzdata)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v apt-get > /dev/null 2>&1; then
    # Install FFmpeg
    if ! command -v ffmpeg > /dev/null 2>&1; then
        echo "📦 Installing FFmpeg..."
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq ffmpeg > /dev/null 2>&1 || {
            echo "⚠️  Failed to install FFmpeg via apt-get"
            echo "   You may need to install it manually"
        }
        
        if command -v ffmpeg > /dev/null 2>&1; then
            FFMPEG_PATH=$(which ffmpeg)
            FFMPEG_VERSION=$(ffmpeg -version | head -n1 | awk '{print $3}')
            echo "✅ FFmpeg installed successfully"
            echo "   Location: $FFMPEG_PATH"
            echo "   Version: $FFMPEG_VERSION"
        else
            echo "❌ FFmpeg installation failed"
        fi
    else
        FFMPEG_PATH=$(which ffmpeg)
        FFMPEG_VERSION=$(ffmpeg -version | head -n1 | awk '{print $3}')
        echo "✅ FFmpeg already installed"
        echo "   Location: $FFMPEG_PATH"
        echo "   Version: $FFMPEG_VERSION"
    fi
    
    # Verify ffmpeg is accessible
    if command -v ffmpeg > /dev/null 2>&1; then
        if ffmpeg -version > /dev/null 2>&1; then
            echo "✅ FFmpeg is accessible from PATH"
        else
            echo "⚠️  FFmpeg found but not working properly"
        fi
    fi
    
    # Check ffprobe
    if ! command -v ffprobe > /dev/null 2>&1; then
        echo "⚠️  ffprobe not found (usually comes with ffmpeg)"
    else
        echo "✅ ffprobe is available"
    fi
    
    # Install/check timezone data (required for pythainlp)
    echo ""
    echo "📋 Checking timezone data..."
    if [ ! -d "/usr/share/zoneinfo" ] || [ ! -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
        echo "📦 Installing tzdata..."
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq tzdata > /dev/null 2>&1 || {
            echo "⚠️  Failed to install tzdata (may continue anyway)"
        }
        if [ -d "/usr/share/zoneinfo" ] && [ -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
            echo "✅ tzdata installed successfully"
        else
            echo "⚠️  tzdata installation may have failed, but continuing..."
        fi
    else
        echo "✅ Timezone data already available (skipping installation)"
    fi
    if [ -d "/usr/share/zoneinfo" ]; then
        export TZDIR=/usr/share/zoneinfo
        echo "✅ Timezone data ready"
    fi
    export TZ=Asia/Bangkok
else
    echo "⚠️  apt-get not found, skipping system dependencies installation"
    echo "   Please install FFmpeg and tzdata manually if needed"
fi
echo ""

# ============================================================
# Step 2: Check Existing Python Dependencies
# ============================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Step 2: Checking Existing Python Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to check if package is installed
check_package() {
    local package_name=$1
    local import_name=$2
    env PYTHONUSERBASE="/workspace/.local" \
        PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
        python3 -c "import ${import_name}" > /dev/null 2>&1
}

# Critical dependencies to check
CRITICAL_DEPS=(
    "uvicorn:uvicorn"
    "fastapi:fastapi"
    "aiofiles:aiofiles"
    "aio-pika:aio_pika"
    "pika:pika"
    "faster-whisper:faster_whisper"
    "torch:torch"
    "pythainlp:pythainlp"
    "ffmpeg-python:ffmpeg"
)

MISSING_CRITICAL=()
INSTALLED_CRITICAL=()

for dep in "${CRITICAL_DEPS[@]}"; do
    IFS=':' read -r name import_name <<< "$dep"
    if check_package "$name" "$import_name"; then
        version=$(env PYTHONUSERBASE="/workspace/.local" \
            PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
            python3 -c "import ${import_name}; print(getattr(${import_name}, '__version__', 'installed'))" 2>/dev/null || echo "installed")
        echo "✅ $name - $version (already installed)"
        INSTALLED_CRITICAL+=("$name")
    else
        echo "❌ $name - NOT INSTALLED"
        MISSING_CRITICAL+=("$name:$import_name")
    fi
done

echo ""
if [ ${#MISSING_CRITICAL[@]} -eq 0 ]; then
    echo "✅ All critical dependencies are already installed!"
    echo "   Skipping Python package installation"
    echo ""
else
    echo "📦 Need to install ${#MISSING_CRITICAL[@]} missing critical dependencies"
    echo ""
fi

# ============================================================
# Step 3: Install Missing Dependencies Only
# ============================================================
if [ ${#MISSING_CRITICAL[@]} -gt 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 Step 3: Installing Missing Dependencies"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Install core dependencies first (if missing)
    NEED_CORE=false
    for dep in "${MISSING_CRITICAL[@]}"; do
        IFS=':' read -r name import_name <<< "$dep"
        if [[ "$name" == "uvicorn" || "$name" == "fastapi" || "$name" == "pydantic" ]]; then
            NEED_CORE=true
            break
        fi
    done
    
    if [ "$NEED_CORE" = true ]; then
        echo "📦 Installing core dependencies (FastAPI, Uvicorn, Pydantic)..."
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
    fi
    
    # Install PyTorch (if missing)
    if [[ " ${MISSING_CRITICAL[@]} " =~ " torch " ]]; then
        echo "📦 Installing PyTorch with CUDA support..."
        pip3 install --user --no-cache-dir \
            torch==2.1.1 \
            torchaudio==2.1.1 \
            || {
            echo "❌ Failed to install PyTorch"
            exit 1
        }
        echo "✅ PyTorch installed"
        echo ""
    fi
    
    # Install RabbitMQ dependencies (if missing)
    NEED_RABBITMQ=false
    for dep in "${MISSING_CRITICAL[@]}"; do
        IFS=':' read -r name import_name <<< "$dep"
        if [[ "$name" == "aiofiles" || "$name" == "aio-pika" || "$name" == "pika" ]]; then
            NEED_RABBITMQ=true
            break
        fi
    done
    
    if [ "$NEED_RABBITMQ" = true ]; then
        echo "📦 Installing RabbitMQ and async dependencies..."
        pip3 install --user --no-cache-dir \
            aiofiles==23.2.1 \
            "aio-pika==9.3.0" \
            pika==1.3.2 \
            aiohttp==3.9.1 \
            || {
            echo "❌ Failed to install RabbitMQ dependencies"
            exit 1
        }
        echo "✅ RabbitMQ dependencies installed"
        echo ""
    fi
    
    # Install Whisper dependencies (if missing)
    if [[ " ${MISSING_CRITICAL[@]} " =~ " faster-whisper " ]]; then
        echo "📦 Installing Whisper dependencies..."
        pip3 install --user --no-cache-dir \
            numpy==1.26.4 \
            "faster-whisper==1.0.3" \
            || {
            echo "⚠️  Some Whisper dependencies failed (may continue anyway)"
        }
        echo "✅ Whisper dependencies installed"
        echo ""
    fi
    
    # Install remaining from requirements.txt (only if needed)
    echo "📦 Installing remaining dependencies from requirements.txt..."
    echo "   (Only missing packages will be installed)"
    pip3 install --user --no-cache-dir -r requirements.txt || {
        echo "⚠️  Some dependencies failed to install"
    }
    echo ""
fi

# ============================================================
# Step 4: Verify Installation
# ============================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Step 4: Verifying Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

VERIFY_FAILED=0

for dep in "${CRITICAL_DEPS[@]}"; do
    IFS=':' read -r name import_name <<< "$dep"
    if check_package "$name" "$import_name"; then
        version=$(env PYTHONUSERBASE="/workspace/.local" \
            PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
            python3 -c "import ${import_name}; print(getattr(${import_name}, '__version__', 'installed'))" 2>/dev/null || echo "installed")
        echo "✅ $name - $version"
    else
        echo "❌ $name - NOT FOUND"
        VERIFY_FAILED=$((VERIFY_FAILED + 1))
    fi
done

echo ""

# Verify FFmpeg
if command -v ffmpeg > /dev/null 2>&1; then
    echo "✅ FFmpeg - $(ffmpeg -version | head -n1 | awk '{print $3}')"
else
    echo "❌ FFmpeg - NOT FOUND"
    VERIFY_FAILED=$((VERIFY_FAILED + 1))
fi

# Verify tzdata
if [ -d "/usr/share/zoneinfo" ] && [ -f "/usr/share/zoneinfo/Asia/Bangkok" ]; then
    echo "✅ tzdata - available"
else
    echo "⚠️  tzdata - not found (may cause issues with pythainlp)"
fi

echo ""

# ============================================================
# Summary
# ============================================================
if [ $VERIFY_FAILED -eq 0 ]; then
    echo "=============================="
    echo "✅ Installation Complete"
    echo ""
    echo "💡 Next: Start service with"
    echo "   bash scripts/pod/start-service-daemon.sh"
    echo ""
    
    # Mark as installed
    touch .deps_installed
else
    echo "=============================="
    echo "⚠️  Installation completed with $VERIFY_FAILED missing dependencies"
    echo "   Please check the errors above"
    echo ""
    exit 1
fi
