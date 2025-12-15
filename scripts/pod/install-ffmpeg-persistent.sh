#!/bin/bash
# Script สำหรับติดตั้ง FFmpeg Static Binary ไปยัง Persistent Volume (/workspace)
# ใช้ static binary เพื่อให้ทำงานได้ทันทีโดยไม่ต้องติดตั้ง system packages
#
# วิธีใช้งาน:
#   bash scripts/pod/install-ffmpeg-persistent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/workspace/transcription-service"

# Persistent installation location
INSTALL_DIR="/workspace/.local/bin"
mkdir -p "$INSTALL_DIR"

# Add to PATH
export PATH="${INSTALL_DIR}:$PATH"

echo "📦 Installing FFmpeg Static Binary to Persistent Volume"
echo "========================================================"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if already installed
if [ -f "$INSTALL_DIR/ffmpeg" ] && [ -x "$INSTALL_DIR/ffmpeg" ]; then
    FFMPEG_VERSION=$("$INSTALL_DIR/ffmpeg" -version | head -n1 | awk '{print $3}' || echo "unknown")
    echo "✅ FFmpeg already installed in persistent volume"
    echo "   Location: $INSTALL_DIR/ffmpeg"
    echo "   Version: $FFMPEG_VERSION"
    echo ""
    echo "💡 To use it, add to PATH:"
    echo "   export PATH=\"$INSTALL_DIR:\$PATH\""
    echo ""
    exit 0
fi

# Detect architecture
ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

echo "🔍 Detecting system..."
echo "   Architecture: $ARCH"
echo "   OS: $OS"
echo ""

# Map architecture to FFmpeg static binary naming
case "$ARCH" in
    x86_64)
        FFMPEG_ARCH="amd64"
        ;;
    aarch64|arm64)
        FFMPEG_ARCH="arm64"
        ;;
    *)
        echo "❌ Unsupported architecture: $ARCH"
        echo "   Please install FFmpeg manually"
        exit 1
        ;;
esac

# Try multiple methods to get FFmpeg

# Method 1: Download from GitHub releases (johnvansickle/ffmpeg)
echo "📥 Method 1: Downloading FFmpeg static binary from GitHub..."
FFMPEG_URL="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-${FFMPEG_ARCH}"
FFPROBE_URL="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffprobe-linux-${FFMPEG_ARCH}"

if command -v curl > /dev/null 2>&1; then
    echo "   Downloading ffmpeg..."
    if curl -L -f -o "$INSTALL_DIR/ffmpeg" "$FFMPEG_URL" 2>/dev/null; then
        chmod +x "$INSTALL_DIR/ffmpeg"
        echo "   ✅ Downloaded ffmpeg"
        
        # Try to download ffprobe
        if curl -L -f -o "$INSTALL_DIR/ffprobe" "$FFPROBE_URL" 2>/dev/null; then
            chmod +x "$INSTALL_DIR/ffprobe"
            echo "   ✅ Downloaded ffprobe"
        fi
    else
        echo "   ⚠️  Failed to download from GitHub, trying alternative method..."
    fi
elif command -v wget > /dev/null 2>&1; then
    echo "   Downloading ffmpeg..."
    if wget -q -O "$INSTALL_DIR/ffmpeg" "$FFMPEG_URL" 2>/dev/null; then
        chmod +x "$INSTALL_DIR/ffmpeg"
        echo "   ✅ Downloaded ffmpeg"
        
        # Try to download ffprobe
        if wget -q -O "$INSTALL_DIR/ffprobe" "$FFPROBE_URL" 2>/dev/null; then
            chmod +x "$INSTALL_DIR/ffprobe"
            echo "   ✅ Downloaded ffprobe"
        fi
    else
        echo "   ⚠️  Failed to download from GitHub, trying alternative method..."
    fi
else
    echo "   ⚠️  curl/wget not found, trying alternative method..."
fi

# Method 2: Try apt-get (fallback, but won't persist)
if [ ! -f "$INSTALL_DIR/ffmpeg" ] || [ ! -x "$INSTALL_DIR/ffmpeg" ]; then
    echo ""
    echo "📥 Method 2: Trying apt-get (will copy to persistent volume)..."
    if command -v apt-get > /dev/null 2>&1; then
        # Install to system first
        apt-get update -qq > /dev/null 2>&1
        if apt-get install -y -qq ffmpeg > /dev/null 2>&1; then
            # Copy to persistent volume
            if [ -f "/usr/bin/ffmpeg" ]; then
                cp /usr/bin/ffmpeg "$INSTALL_DIR/ffmpeg"
                chmod +x "$INSTALL_DIR/ffmpeg"
                echo "   ✅ Copied ffmpeg to persistent volume"
            fi
            if [ -f "/usr/bin/ffprobe" ]; then
                cp /usr/bin/ffprobe "$INSTALL_DIR/ffprobe"
                chmod +x "$INSTALL_DIR/ffprobe"
                echo "   ✅ Copied ffprobe to persistent volume"
            fi
        fi
    fi
fi

# Verify installation
if [ -f "$INSTALL_DIR/ffmpeg" ] && [ -x "$INSTALL_DIR/ffmpeg" ]; then
    FFMPEG_VERSION=$("$INSTALL_DIR/ffmpeg" -version | head -n1 | awk '{print $3}' || echo "unknown")
    echo ""
    echo "✅ FFmpeg installed successfully!"
    echo "   Location: $INSTALL_DIR/ffmpeg"
    echo "   Version: $FFMPEG_VERSION"
    echo ""
    
    # Test ffmpeg
    if "$INSTALL_DIR/ffmpeg" -version > /dev/null 2>&1; then
        echo "✅ FFmpeg is working correctly"
    else
        echo "⚠️  FFmpeg binary may not be compatible with this system"
    fi
    
    # Check ffprobe
    if [ -f "$INSTALL_DIR/ffprobe" ] && [ -x "$INSTALL_DIR/ffprobe" ]; then
        echo "✅ ffprobe is available"
    else
        echo "⚠️  ffprobe not found (may not be critical)"
    fi
    
    echo ""
    echo "💡 To use FFmpeg, add to PATH:"
    echo "   export PATH=\"$INSTALL_DIR:\$PATH\""
    echo ""
    echo "   Or add to your .bashrc or startup script:"
    echo "   echo 'export PATH=\"$INSTALL_DIR:\$PATH\"' >> ~/.bashrc"
    echo ""
else
    echo ""
    echo "❌ Failed to install FFmpeg"
    echo ""
    echo "💡 Manual installation options:"
    echo "   1. Download static binary manually:"
    echo "      wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-${FFMPEG_ARCH}"
    echo "      mv ffmpeg-linux-${FFMPEG_ARCH} $INSTALL_DIR/ffmpeg"
    echo "      chmod +x $INSTALL_DIR/ffmpeg"
    echo ""
    echo "   2. Use conda/mamba (if available):"
    echo "      conda install -c conda-forge ffmpeg -y"
    echo ""
    exit 1
fi

