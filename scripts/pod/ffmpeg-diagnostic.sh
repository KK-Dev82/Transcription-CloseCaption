#!/bin/bash
# FFmpeg Diagnostic Script - Minimal, fast output
# Run on server to diagnose FFmpeg installation issues

cd /workspace/transcription-service 2>/dev/null || cd /workspace/transcription-close-caption-service 2>/dev/null || exit 1

OUTPUT_FILE="logs/ffmpeg-diagnostic-$(date +%Y%m%d-%H%M%S).log"
mkdir -p logs

{
    echo "=== FFmpeg Diagnostic ==="
    echo "Time: $(date)"
    echo ""
    
    # System
    echo "=== System ==="
    echo "Arch: $(uname -m)"
    echo "OS: $(uname -s)"
    echo "User: $(whoami)"
    echo "PWD: $(pwd)"
    echo ""
    
    # Network
    echo "=== Network ==="
    (ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1 && echo "Ping: OK") || echo "Ping: FAIL"
    (timeout 3 curl -I https://github.com > /dev/null 2>&1 && echo "GitHub: OK") || echo "GitHub: FAIL"
    echo ""
    
    # Tools
    echo "=== Tools ==="
    for tool in curl wget apt-get tar; do
        if command -v "$tool" > /dev/null 2>&1; then
            echo "$tool: OK"
        else
            echo "$tool: MISSING"
        fi
    done
    echo ""
    
    # FFmpeg locations
    echo "=== FFmpeg Search ==="
    if [ -f "/workspace/.local/bin/ffmpeg" ]; then
        echo "Persistent: EXISTS"
        /workspace/.local/bin/ffmpeg -version 2>&1 | head -1
    else
        echo "Persistent: NOT FOUND"
    fi
    
    if command -v ffmpeg > /dev/null 2>&1; then
        echo "PATH: EXISTS at $(which ffmpeg)"
        ffmpeg -version 2>&1 | head -1
    else
        echo "PATH: NOT FOUND"
    fi
    
    SYSTEM_FFMPEG=$(find /usr /opt -name ffmpeg -type f 2>/dev/null | head -1)
    if [ -n "$SYSTEM_FFMPEG" ]; then
        echo "System: FOUND at $SYSTEM_FFMPEG"
    else
        echo "System: NOT FOUND"
    fi
    echo ""
    
    # Permissions
    echo "=== Permissions ==="
    echo "Install dir: $(ls -ld /workspace/.local/bin 2>/dev/null || echo 'NOT ACCESSIBLE')"
    echo "Can write: $([ -w /workspace/.local/bin ] && echo 'YES' || echo 'NO')"
    echo ""
    
    # Try installation
    echo "=== Installation Test ==="
    if [ -f "scripts/pod/quick-fix-ffmpeg.sh" ]; then
        echo "Running quick-fix..."
        bash scripts/pod/quick-fix-ffmpeg.sh 2>&1 | tail -10
    fi
    
    echo ""
    echo "=== Final Status ==="
    if [ -f "/workspace/.local/bin/ffmpeg" ] && [ -x "/workspace/.local/bin/ffmpeg" ]; then
        echo "✅ FFmpeg INSTALLED"
        /workspace/.local/bin/ffmpeg -version 2>&1 | head -3
    else
        echo "❌ FFmpeg NOT INSTALLED"
    fi
    
} | tee "$OUTPUT_FILE"

echo ""
echo "Results saved to: $OUTPUT_FILE"
echo ""
echo "=== Summary ==="
tail -20 "$OUTPUT_FILE"

