#!/bin/bash
# Quick Fix Script: Manual FFmpeg Installation
# ใช้เมื่อ auto-installation ล้มเหลว
#
# วิธีใช้งาน:
#   bash scripts/pod/quick-fix-ffmpeg.sh

set -e

INSTALL_DIR="/workspace/.local/bin"
mkdir -p "$INSTALL_DIR"

echo "🔧 Quick Fix: FFmpeg Installation"
echo "=================================="
echo ""

# Method 1: Try to find existing FFmpeg in container
echo "🔍 Method 1: Looking for existing FFmpeg in container..."
FFMPEG_FOUND=false

# Common locations
SEARCH_PATHS=(
    "/usr/bin/ffmpeg"
    "/usr/local/bin/ffmpeg"
    "/opt/ffmpeg/bin/ffmpeg"
    "$(which ffmpeg 2>/dev/null || echo '')"
)

for path in "${SEARCH_PATHS[@]}"; do
    if [ -n "$path" ] && [ -f "$path" ] && [ -x "$path" ]; then
        echo "   ✅ Found FFmpeg at: $path"
        cp "$path" "$INSTALL_DIR/ffmpeg"
        chmod +x "$INSTALL_DIR/ffmpeg"
        FFMPEG_FOUND=true
        
        # Try to find ffprobe
        FFPROBE_PATH="${path%ffmpeg}ffprobe"
        if [ -f "$FFPROBE_PATH" ] && [ -x "$FFPROBE_PATH" ]; then
            cp "$FFPROBE_PATH" "$INSTALL_DIR/ffprobe"
            chmod +x "$INSTALL_DIR/ffprobe"
            echo "   ✅ Found and copied ffprobe"
        fi
        break
    fi
done

# Method 2: Try apt-get (primary method - works even if ping fails)
if [ "$FFMPEG_FOUND" = false ] && command -v apt-get > /dev/null 2>&1; then
    echo ""
    echo "📥 Method 2: Installing via apt-get (system package)..."
    
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
        echo "   Updating package lists..."
        if apt-get update -qq 2>&1 | grep -v "^$" | head -10; then
            echo "   ✅ Package lists updated"
        else
            echo "   ⚠️  apt-get update completed (checking for errors above)"
        fi
        
        echo "   Installing ffmpeg..."
        if apt-get install -y -qq ffmpeg 2>&1 | grep -v "^$" | head -20; then
            # Check if installation succeeded
            if command -v ffmpeg > /dev/null 2>&1; then
                FFMPEG_SYSTEM_PATH=$(which ffmpeg)
                FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}' || echo "unknown")
                echo "   ✅ FFmpeg installed successfully"
                echo "   Location: $FFMPEG_SYSTEM_PATH"
                echo "   Version: $FFMPEG_VERSION"
                
                # Try to copy to persistent volume (if writable)
                if [ -w "$INSTALL_DIR" ]; then
                    cp "$FFMPEG_SYSTEM_PATH" "$INSTALL_DIR/ffmpeg" 2>/dev/null && chmod +x "$INSTALL_DIR/ffmpeg" && {
                        echo "   ✅ Copied to persistent volume: $INSTALL_DIR/ffmpeg"
                        FFMPEG_FOUND=true
                    } || echo "   ⚠️  Could not copy to persistent volume (using system FFmpeg)"
                fi
                
                # Copy ffprobe if available
                if command -v ffprobe > /dev/null 2>&1; then
                    FFPROBE_SYSTEM_PATH=$(which ffprobe)
                    if [ -w "$INSTALL_DIR" ]; then
                        cp "$FFPROBE_SYSTEM_PATH" "$INSTALL_DIR/ffprobe" 2>/dev/null && chmod +x "$INSTALL_DIR/ffprobe" && {
                            echo "   ✅ Copied ffprobe to persistent volume"
                        }
                    fi
                fi
                
                # Mark as found (even if not in persistent volume)
                FFMPEG_FOUND=true
            else
                echo "   ❌ apt-get install completed but ffmpeg not found in PATH"
            fi
        else
            echo "   ❌ apt-get install failed"
        fi
    fi
fi

# Verify
if [ -f "$INSTALL_DIR/ffmpeg" ] && [ -x "$INSTALL_DIR/ffmpeg" ]; then
    FFMPEG_VERSION=$("$INSTALL_DIR/ffmpeg" -version | head -n1 | awk '{print $3}' || echo "unknown")
    echo ""
    echo "✅ FFmpeg installed successfully!"
    echo "   Location: $INSTALL_DIR/ffmpeg"
    echo "   Version: $FFMPEG_VERSION"
    echo ""
    echo "💡 Add to PATH:"
    echo "   export PATH=\"$INSTALL_DIR:\$PATH\""
    exit 0
else
    echo ""
    echo "❌ Failed to install FFmpeg"
    echo ""
    echo "💡 Manual installation required:"
    echo "   1. Download FFmpeg on your local machine:"
    echo "      wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-amd64"
    echo ""
    echo "   2. Upload to Pod:"
    echo "      scp -P 13263 ffmpeg-linux-amd64 4000-ada-sc:/workspace/.local/bin/ffmpeg"
    echo ""
    echo "   3. Set permissions:"
    echo "      ssh -p 13263 4000-ada-sc 'chmod +x /workspace/.local/bin/ffmpeg'"
    echo ""
    exit 1
fi

