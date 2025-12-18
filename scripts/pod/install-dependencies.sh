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
    # ใช้ persistent volume เพื่อไม่ต้องติดตั้งใหม่ทุกครั้งหลัง restart
    echo ""
    echo "📋 Checking timezone data..."
    PERSISTENT_ZONEINFO="/workspace/.local/share/zoneinfo"
    SYSTEM_ZONEINFO="/usr/share/zoneinfo"
    
    if [ -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
        # ใช้ timezone data จาก persistent volume (เร็วที่สุด - ไม่ต้องติดตั้ง)
        export TZDIR="$PERSISTENT_ZONEINFO"
        echo "✅ Using timezone data from persistent volume: $TZDIR"
        echo "   (Skipping installation - already available)"
    elif [ -d "$SYSTEM_ZONEINFO" ] && [ -f "$SYSTEM_ZONEINFO/Asia/Bangkok" ]; then
        # Fallback: ใช้ system timezone และ copy ไป persistent volume
        echo "📦 Copying timezone data to persistent volume..."
        mkdir -p "$PERSISTENT_ZONEINFO"
        cp -r "$SYSTEM_ZONEINFO"/* "$PERSISTENT_ZONEINFO/" 2>/dev/null || {
            echo "⚠️  Some files may have failed to copy (this is usually OK)"
        }
        if [ -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
            export TZDIR="$PERSISTENT_ZONEINFO"
            echo "✅ Timezone data copied to persistent volume: $TZDIR"
        else
            export TZDIR="$SYSTEM_ZONEINFO"
            echo "⚠️  Using system timezone (persistent copy failed): $TZDIR"
        fi
    else
        # ติดตั้ง tzdata และ copy ไป persistent volume (ใช้เวลานานที่สุด)
        echo "📦 Installing tzdata..."
        echo "   ⚠️  This may take a while (downloading from apt repository)..."
        
        # ตั้งค่า non-interactive mode และ timezone เพื่อหลีกเลี่ยง interactive prompt
        export DEBIAN_FRONTEND=noninteractive
        export TZ=Asia/Bangkok
        ln -sf /usr/share/zoneinfo/Asia/Bangkok /etc/localtime 2>/dev/null || true
        
        # ตรวจสอบว่ามี process tzdata ที่ติดค้างอยู่หรือไม่
        if pgrep -f "tzdata" > /dev/null 2>&1; then
            echo "   ⚠️  Detected stuck tzdata process, attempting to fix..."
            # พยายาม configure tzdata ที่ติดค้าง
            DEBIAN_FRONTEND=noninteractive TZ=Asia/Bangkok dpkg --configure -a 2>/dev/null || true
            sleep 2
        fi
        
        apt-get update -qq > /dev/null 2>&1
        DEBIAN_FRONTEND=noninteractive TZ=Asia/Bangkok apt-get install -y -qq tzdata > /dev/null 2>&1 || {
            echo "⚠️  Failed to install tzdata (may continue anyway)"
            # พยายาม configure ใหม่ถ้าติดค้าง
            DEBIAN_FRONTEND=noninteractive TZ=Asia/Bangkok dpkg --configure -a 2>/dev/null || true
        }
        if [ -d "$SYSTEM_ZONEINFO" ] && [ -f "$SYSTEM_ZONEINFO/Asia/Bangkok" ]; then
            # Copy ไป persistent volume เพื่อใช้ครั้งต่อไป
            echo "📦 Copying timezone data to persistent volume..."
            mkdir -p "$PERSISTENT_ZONEINFO"
            cp -r "$SYSTEM_ZONEINFO"/* "$PERSISTENT_ZONEINFO/" 2>/dev/null || {
                echo "⚠️  Some files may have failed to copy (this is usually OK)"
            }
            if [ -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
                export TZDIR="$PERSISTENT_ZONEINFO"
                echo "✅ tzdata installed and copied to persistent volume: $TZDIR"
            else
                export TZDIR="$SYSTEM_ZONEINFO"
                echo "✅ tzdata installed (using system location): $TZDIR"
            fi
        else
            echo "⚠️  tzdata installation may have failed, but continuing..."
            export TZDIR="${TZDIR:-/usr/share/zoneinfo}"
        fi
    fi
    export TZ=Asia/Bangkok
    echo "   TZ=$TZ"
    echo "   TZDIR=$TZDIR"
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
    "ctranslate2:ctranslate2"
    "torch:torch"
    "pythainlp:pythainlp"
    "ffmpeg-python:ffmpeg"
    "python-dotenv:dotenv"
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
    # Check if faster-whisper or ctranslate2 is missing
    NEED_WHISPER=false
    for dep in "${MISSING_CRITICAL[@]}"; do
        IFS=':' read -r name import_name <<< "$dep"
        if [[ "$name" == "faster-whisper" || "$name" == "ctranslate2" ]]; then
            NEED_WHISPER=true
            break
        fi
    done
    
    if [ "$NEED_WHISPER" = true ]; then
        echo "📦 Installing Whisper dependencies..."
        echo "   ⚠️  Important: Installing CTranslate2 4.4.0 (compatible with cuDNN 8)"
        echo "      CTranslate2 4.5.0+ requires cuDNN 9, but system has cuDNN 8"
        echo "      If you have cuDNN 9, you can upgrade to CTranslate2 4.6.2+ later"
        
        # Check current CTranslate2 version (if installed)
        CURRENT_CT2=$(env PYTHONUSERBASE="/workspace/.local" \
            PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
            python3 -c "import ctranslate2; print(ctranslate2.__version__)" 2>/dev/null || echo "not installed")
        
        if [[ "$CURRENT_CT2" == "4.5."* ]] || [[ "$CURRENT_CT2" == "4.6."* ]]; then
            echo "   ⚠️  Detected CTranslate2 $CURRENT_CT2 (incompatible with cuDNN 8)"
            echo "   📦 Downgrading to CTranslate2 4.4.0..."
            pip3 uninstall -y ctranslate2 2>/dev/null || true
        fi
        
        pip3 install --user --no-cache-dir \
            numpy==1.26.4 \
            "ctranslate2==4.4.0" \
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

# Verify tzdata (check both persistent and system locations)
PERSISTENT_ZONEINFO="/workspace/.local/share/zoneinfo"
SYSTEM_ZONEINFO="/usr/share/zoneinfo"
if [ -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
    echo "✅ tzdata - available (persistent volume: $PERSISTENT_ZONEINFO)"
elif [ -d "$SYSTEM_ZONEINFO" ] && [ -f "$SYSTEM_ZONEINFO/Asia/Bangkok" ]; then
    echo "✅ tzdata - available (system: $SYSTEM_ZONEINFO)"
else
    echo "⚠️  tzdata - not found (may cause issues with pythainlp)"
fi

# Verify CTranslate2 version compatibility
echo ""
echo "🔍 Checking CTranslate2 version compatibility..."
CT2_VERSION=$(env PYTHONUSERBASE="/workspace/.local" \
    PYTHONPATH="${PYTHON_SITE_PACKAGES}:$PYTHONPATH" \
    python3 -c "import ctranslate2; print(ctranslate2.__version__)" 2>/dev/null || echo "not installed")

if [ "$CT2_VERSION" != "not installed" ]; then
    if [[ "$CT2_VERSION" == "4.4."* ]]; then
        echo "✅ CTranslate2 $CT2_VERSION - Compatible with cuDNN 8"
    elif [[ "$CT2_VERSION" == "4.5."* ]] || [[ "$CT2_VERSION" == "4.6."* ]]; then
        echo "⚠️  CTranslate2 $CT2_VERSION - Requires cuDNN 9 (system has cuDNN 8)"
        echo "   💡 Consider downgrading: pip install --user --force-reinstall ctranslate2==4.4.0"
    else
        echo "✅ CTranslate2 $CT2_VERSION - Installed"
    fi
else
    echo "❌ CTranslate2 - NOT INSTALLED"
    VERIFY_FAILED=$((VERIFY_FAILED + 1))
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
