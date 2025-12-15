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

# Method 2: Try apt-get (primary method - works even if ping fails)
if [ ! -f "$INSTALL_DIR/ffmpeg" ] || [ ! -x "$INSTALL_DIR/ffmpeg" ]; then
    echo ""
    echo "📥 Method 2: Installing via apt-get (will copy to persistent volume)..."
    if command -v apt-get > /dev/null 2>&1; then
        # Check network (try HTTPS instead of ping - more reliable)
        NETWORK_OK=false
        if timeout 3 curl -I https://github.com > /dev/null 2>&1; then
            NETWORK_OK=true
            echo "   ✅ Network connectivity OK (HTTPS)"
        elif ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
            NETWORK_OK=true
            echo "   ✅ Network connectivity OK (ping)"
        else
            echo "   ⚠️  Ping failed but will try apt-get anyway (may work)"
            NETWORK_OK=true  # Try anyway
        fi
        
        if [ "$NETWORK_OK" = true ]; then
            # Fix dpkg if interrupted
            if dpkg --configure -a 2>&1 | grep -q "dpkg"; then
                echo "   🔧 Fixing interrupted dpkg configuration..."
                DEBIAN_FRONTEND=noninteractive dpkg --configure -a > /dev/null 2>&1 || true
            fi
            
            echo "   Updating package lists..."
            apt-get update -qq 2>&1 | grep -v "^$" | head -5 || echo "   ⚠️  apt-get update had issues (may continue)"
            
            echo "   Installing ffmpeg..."
            if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg 2>&1 | grep -v "^$" | head -10; then
                # Check if installation succeeded
                if command -v ffmpeg > /dev/null 2>&1; then
                    FFMPEG_SYSTEM_PATH=$(which ffmpeg)
                    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}' || echo "unknown")
                    echo "   ✅ FFmpeg installed successfully"
                    echo "   System location: $FFMPEG_SYSTEM_PATH"
                    echo "   Version: $FFMPEG_VERSION"
                    
                    # Copy to persistent volume
                    if [ -f "$FFMPEG_SYSTEM_PATH" ] && [ -w "$INSTALL_DIR" ]; then
                        cp "$FFMPEG_SYSTEM_PATH" "$INSTALL_DIR/ffmpeg"
                        chmod +x "$INSTALL_DIR/ffmpeg"
                        echo "   ✅ Copied ffmpeg to persistent volume: $INSTALL_DIR/ffmpeg"
                    else
                        echo "   ⚠️  Could not copy to persistent volume (using system FFmpeg)"
                    fi
                    
                    # Try to find and copy ffprobe
                    if command -v ffprobe > /dev/null 2>&1; then
                        FFPROBE_SYSTEM_PATH=$(which ffprobe)
                        if [ -f "$FFPROBE_SYSTEM_PATH" ] && [ -w "$INSTALL_DIR" ]; then
                            cp "$FFPROBE_SYSTEM_PATH" "$INSTALL_DIR/ffprobe"
                            chmod +x "$INSTALL_DIR/ffprobe"
                            echo "   ✅ Copied ffprobe to persistent volume"
                        fi
                    fi
                else
                    echo "   ⚠️  apt-get install completed but ffmpeg not found in PATH"
                fi
            else
                echo "   ⚠️  apt-get install failed (check logs above)"
            fi
        else
            echo "   ⚠️  No network connectivity - cannot use apt-get"
        fi
    else
        echo "   ⚠️  apt-get not available"
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
    echo "🔍 Debugging information:"
    echo "   Architecture: $ARCH ($FFMPEG_ARCH)"
    echo "   OS: $OS"
    echo "   Install directory: $INSTALL_DIR"
    echo "   Network check:"
    if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
        echo "      ✅ Internet connectivity OK"
    else
        echo "      ❌ No internet connectivity"
    fi
    echo "   Tools available:"
    command -v curl > /dev/null 2>&1 && echo "      ✅ curl" || echo "      ❌ curl"
    command -v wget > /dev/null 2>&1 && echo "      ✅ wget" || echo "      ❌ wget"
    command -v apt-get > /dev/null 2>&1 && echo "      ✅ apt-get" || echo "      ❌ apt-get"
    echo ""
    echo "💡 Manual installation options:"
    echo "   1. Download static binary manually (if you have network access from another machine):"
    echo "      # On your local machine:"
    echo "      wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-${FFMPEG_ARCH}"
    echo "      # Then upload to Pod:"
    echo "      scp -P <port> ffmpeg-linux-${FFMPEG_ARCH} <user>@<host>:/workspace/.local/bin/ffmpeg"
    echo "      ssh -p <port> <user>@<host> 'chmod +x /workspace/.local/bin/ffmpeg'"
    echo ""
    echo "   2. Use conda/mamba (if available in container):"
    echo "      conda install -c conda-forge ffmpeg -y"
    echo ""
    echo "   3. Check if FFmpeg is already in container but not in PATH:"
    echo "      find /usr -name ffmpeg 2>/dev/null"
    echo "      find /opt -name ffmpeg 2>/dev/null"
    echo ""
    echo "   4. Build from source (if all else fails):"
    echo "      # This requires build tools and takes time"
    echo "      # See: https://trac.ffmpeg.org/wiki/CompilationGuide"
    echo ""
    exit 1
fi

