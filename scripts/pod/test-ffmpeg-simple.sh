#!/bin/bash
# Simple FFmpeg Test - Minimal output for SSH
# Output will be saved to file for analysis

cd /workspace/transcription-service || exit 1
mkdir -p logs

{
    echo "=== FFmpeg Installation Test ==="
    echo "Time: $(date)"
    echo ""
    
    echo "=== System Info ==="
    echo "Arch: $(uname -m)"
    echo "OS: $(uname -s)"
    echo "User: $(whoami)"
    echo ""
    
    echo "=== Network Test ==="
    ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1 && echo "Ping: OK" || echo "Ping: FAILED"
    timeout 5 curl -I https://github.com > /dev/null 2>&1 && echo "GitHub HTTPS: OK" || echo "GitHub HTTPS: FAILED"
    echo ""
    
    echo "=== Tools Check ==="
    command -v curl > /dev/null && echo "curl: OK" || echo "curl: MISSING"
    command -v wget > /dev/null && echo "wget: OK" || echo "wget: MISSING"
    command -v apt-get > /dev/null && echo "apt-get: OK" || echo "apt-get: MISSING"
    echo ""
    
    echo "=== Existing FFmpeg ==="
    if [ -f "/workspace/.local/bin/ffmpeg" ]; then
        echo "Persistent: FOUND"
        /workspace/.local/bin/ffmpeg -version 2>&1 | head -1
    else
        echo "Persistent: NOT FOUND"
    fi
    
    if command -v ffmpeg > /dev/null; then
        echo "System PATH: FOUND"
        ffmpeg -version 2>&1 | head -1
    else
        echo "System PATH: NOT FOUND"
    fi
    
    FOUND=$(find /usr /opt -name ffmpeg 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        echo "System locations: FOUND at $FOUND"
    else
        echo "System locations: NOT FOUND"
    fi
    echo ""
    
    echo "=== Running Quick Fix ==="
    bash scripts/pod/quick-fix-ffmpeg.sh 2>&1
    echo ""
    
    echo "=== Running Main Install ==="
    bash scripts/pod/install-ffmpeg-persistent.sh 2>&1
    echo ""
    
    echo "=== Final Check ==="
    if [ -f "/workspace/.local/bin/ffmpeg" ] && [ -x "/workspace/.local/bin/ffmpeg" ]; then
        echo "✅ SUCCESS: FFmpeg installed"
        /workspace/.local/bin/ffmpeg -version 2>&1 | head -3
    else
        echo "❌ FAILED: FFmpeg not installed"
    fi
    
} | tee logs/ffmpeg-test-simple.log

echo ""
echo "Results saved to: logs/ffmpeg-test-simple.log"
cat logs/ffmpeg-test-simple.log

