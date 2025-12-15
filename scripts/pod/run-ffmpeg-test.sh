#!/bin/bash
# Script สำหรับรัน FFmpeg test และบันทึกผลลัพธ์
# รันบน server แล้วดูผลลัพธ์จากไฟล์

cd /workspace/transcription-service || exit 1

# Create logs directory
mkdir -p logs

# Run test and save output
bash scripts/pod/test-ffmpeg-install.sh > logs/ffmpeg-test-output.log 2>&1

# Also try quick fix
bash scripts/pod/quick-fix-ffmpeg.sh >> logs/ffmpeg-test-output.log 2>&1

# Show summary
echo "=== Test Complete ==="
echo "Results saved to: logs/ffmpeg-test-output.log"
echo ""
echo "=== Last 50 lines ==="
tail -50 logs/ffmpeg-test-output.log

