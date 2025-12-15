#!/bin/bash
# Test Script: FFmpeg Installation Testing
# รันบน server เพื่อทดสอบและ debug FFmpeg installation
#
# วิธีใช้งาน:
#   ssh -p 13263 4000-ada-sc "cd /workspace/transcription-service && bash scripts/pod/test-ffmpeg-install.sh"

# Don't exit on error - we want to see all results
set +e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔍 FFmpeg Installation Test & Debug                          ║"
echo "║  เวลา: $(date '+%Y-%m-%d %H:%M:%S')                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/workspace/transcription-service"
cd "$PROJECT_DIR" 2>/dev/null || {
    echo "❌ Cannot find project directory"
    exit 1
}

INSTALL_DIR="/workspace/.local/bin"
mkdir -p "$INSTALL_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Step 1: System Information"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Architecture: $(uname -m)"
echo "OS: $(uname -s)"
echo "Kernel: $(uname -r)"
echo "Current user: $(whoami)"
echo "Current directory: $(pwd)"
echo "Install directory: $INSTALL_DIR"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Step 2: Network Connectivity Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test DNS
echo "Testing DNS resolution..."
if nslookup github.com > /dev/null 2>&1; then
    echo "✅ DNS: OK"
else
    echo "❌ DNS: Failed"
fi

# Test ping
echo "Testing ping to 8.8.8.8..."
if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
    echo "✅ Ping: OK"
else
    echo "❌ Ping: Failed (may be blocked by firewall)"
fi

# Test HTTPS
echo "Testing HTTPS to GitHub..."
if timeout 5 curl -I https://github.com > /dev/null 2>&1; then
    echo "✅ HTTPS to GitHub: OK"
else
    echo "❌ HTTPS to GitHub: Failed"
    echo "   Error details:"
    timeout 5 curl -I https://github.com 2>&1 | head -3
fi

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Step 3: Available Tools"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOOLS=("curl" "wget" "apt-get" "tar" "gzip")
for tool in "${TOOLS[@]}"; do
    if command -v "$tool" > /dev/null 2>&1; then
        VERSION=$($tool --version 2>&1 | head -1 | cut -d' ' -f1-3 || echo "available")
        echo "✅ $tool: $VERSION"
    else
        echo "❌ $tool: Not found"
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Step 4: Check Existing FFmpeg"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check persistent volume
if [ -f "$INSTALL_DIR/ffmpeg" ] && [ -x "$INSTALL_DIR/ffmpeg" ]; then
    VERSION=$("$INSTALL_DIR/ffmpeg" -version 2>&1 | head -1 | awk '{print $3}' || echo "unknown")
    echo "✅ FFmpeg found in persistent volume"
    echo "   Location: $INSTALL_DIR/ffmpeg"
    echo "   Version: $VERSION"
    echo "   Size: $(ls -lh "$INSTALL_DIR/ffmpeg" | awk '{print $5}')"
else
    echo "❌ FFmpeg not found in persistent volume"
fi

# Check system PATH
if command -v ffmpeg > /dev/null 2>&1; then
    FFMPEG_PATH=$(which ffmpeg)
    VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}' || echo "unknown")
    echo "✅ FFmpeg found in system PATH"
    echo "   Location: $FFMPEG_PATH"
    echo "   Version: $VERSION"
else
    echo "❌ FFmpeg not found in system PATH"
fi

# Search common locations
echo ""
echo "Searching common locations..."
FOUND_LOCATIONS=$(find /usr /opt /bin /sbin -name ffmpeg -type f 2>/dev/null | head -5)
if [ -n "$FOUND_LOCATIONS" ]; then
    echo "✅ Found FFmpeg in:"
    echo "$FOUND_LOCATIONS" | while read -r loc; do
        echo "   - $loc ($(ls -lh "$loc" | awk '{print $5}'))"
    done
else
    echo "❌ FFmpeg not found in common locations"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 5: Test Quick Fix Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "scripts/pod/quick-fix-ffmpeg.sh" ]; then
    echo "Running quick-fix-ffmpeg.sh..."
    bash scripts/pod/quick-fix-ffmpeg.sh 2>&1
else
    echo "❌ quick-fix-ffmpeg.sh not found"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📥 Step 6: Test Main Installation Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "scripts/pod/install-ffmpeg-persistent.sh" ]; then
    echo "Running install-ffmpeg-persistent.sh..."
    bash scripts/pod/install-ffmpeg-persistent.sh 2>&1
else
    echo "❌ install-ffmpeg-persistent.sh not found"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Step 7: Final Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "$INSTALL_DIR/ffmpeg" ] && [ -x "$INSTALL_DIR/ffmpeg" ]; then
    echo "✅ FFmpeg installation successful!"
    echo ""
    echo "Location: $INSTALL_DIR/ffmpeg"
    echo "Version:"
    "$INSTALL_DIR/ffmpeg" -version | head -3
    echo ""
    echo "Test command:"
    echo "  $INSTALL_DIR/ffmpeg -f lavfi -i testsrc=duration=1:size=320x240:rate=1 /tmp/test.mp4"
    echo ""
    echo "PATH configuration:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
else
    echo "❌ FFmpeg installation failed"
    echo ""
    echo "💡 Next steps:"
    echo "   1. Check network connectivity"
    echo "   2. Check permissions: ls -ld $INSTALL_DIR"
    echo "   3. Try manual download and upload"
    echo "   4. Check logs above for specific errors"
fi
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Test Complete                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"

