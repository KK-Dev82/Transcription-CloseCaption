#!/bin/bash
# Script สำหรับทดสอบ GPU Performance บน RunPod
#
# วิธีใช้งาน:
# bash scripts/pod/test-runpod-gpu.sh

set -e

echo "🧪 Testing GPU Performance on RunPod..."
echo ""

# Check GPU
echo "🔍 GPU Information:"
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader || echo "⚠️  nvidia-smi not available"
echo ""

# Check CUDA
echo "🔍 CUDA Information:"
nvcc --version 2>/dev/null || echo "⚠️  nvcc not found (may be normal - using runtime libraries)"
echo ""

# Check Redis
echo "🔴 Testing Redis:"
redis-cli ping 2>/dev/null && echo "✅ Redis is running" || echo "⚠️  Redis not responding"
echo ""

# Test API Health
echo "🏥 Testing API Health:"
if curl -s http://localhost:8001/health > /tmp/api-health.json 2>/dev/null; then
    if command -v jq &> /dev/null; then
        cat /tmp/api-health.json | jq .
    else
        cat /tmp/api-health.json
    fi
    echo "✅ API is healthy"
else
    echo "❌ API not responding"
fi
echo ""

# Test Whisper Health
echo "🏥 Testing Whisper Health:"
if curl -s http://localhost:8002/health > /tmp/whisper-health.json 2>/dev/null; then
    if command -v jq &> /dev/null; then
        cat /tmp/whisper-health.json | jq .
    else
        cat /tmp/whisper-health.json
    fi
    echo "✅ Whisper is healthy"
else
    echo "❌ Whisper not responding"
fi
echo ""

# Check running processes
echo "📊 Running Processes:"
ps aux | grep -E "(python|redis|whisper)" | grep -v grep || echo "⚠️  No processes found"
echo ""

# Monitor GPU during test
echo "📊 Starting GPU Monitor (will run for 10 seconds)..."
timeout 10 nvidia-smi -l 1 || true
echo ""

echo "✅ GPU Test Complete!"
echo ""
echo "💡 To test transcription:"
echo "   curl -X POST http://localhost:8001/api/transcription/upload \\"
echo "     -F 'file=@test_audio.wav' \\"
echo "     -F 'language=th' \\"
echo "     -F 'model_size=small'"
echo ""
echo "📋 Check logs:"
echo "   - Whisper: tail -f /tmp/whisper.log"
echo "   - Video Worker: tail -f /tmp/video-worker.log"

