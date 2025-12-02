#!/bin/bash
# Script สำหรับ Export Environment ทั้งหมดจาก Container
# ใช้สำหรับสร้าง Dockerfile หรือตั้งค่าใหม่

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/ENVIRONMENT_EXPORT.txt"

echo "📋 Exporting Environment จาก Container..."
echo ""

# สร้าง output file
{
    echo "============================================================"
    echo "Environment Export - $(date)"
    echo "============================================================"
    echo ""
    
    echo "1. PYTHON PACKAGES (สำคัญ)"
    echo "------------------------------------------------------------"
    pip3 list --format=freeze | grep -E "(torch|ctranslate|whisper|numpy|fastapi|uvicorn|pydantic)" || true
    echo ""
    
    echo "2. PYTHON PACKAGES (ทั้งหมด)"
    echo "------------------------------------------------------------"
    pip3 list --format=freeze
    echo ""
    
    echo "3. SYSTEM PACKAGES"
    echo "------------------------------------------------------------"
    dpkg -l | grep -E "(ffmpeg|git|wget|curl|build-essential|cmake)" || true
    echo ""
    
    echo "4. CUDA INFO"
    echo "------------------------------------------------------------"
    python3 << 'PYEOF'
import torch
print(f"PyTorch: {torch.__version__}")
print(f"PyTorch CUDA: {torch.version.cuda}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"cuDNN: {torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else 'N/A'}")
PYEOF
    echo ""
    
    echo "5. ENVIRONMENT VARIABLES"
    echo "------------------------------------------------------------"
    env | grep -E "(CUDA|CT2|OMP|MKL|PYTHON|HF_)" | sort
    echo ""
    
    echo "6. LIBRARY PATHS"
    echo "------------------------------------------------------------"
    echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
    echo ""
    
    echo "7. SYMLINKS"
    echo "------------------------------------------------------------"
    if [ -L /usr/local/cuda-11.8/targets/x86_64-linux/lib/libcublas.so.12 ]; then
        ls -la /usr/local/cuda-11.8/targets/x86_64-linux/lib/libcublas.so.12
    fi
    echo ""
    
    echo "8. DIRECTORY STRUCTURE"
    echo "------------------------------------------------------------"
    find /workspace -maxdepth 2 -type d 2>/dev/null | head -10
    echo ""
    
    echo "9. MODELS CACHE"
    echo "------------------------------------------------------------"
    ls -d /root/.cache/huggingface/hub/models--*/*/ 2>/dev/null | head -5 || echo "No models cached"
    echo ""
    
} > "$OUTPUT_FILE"

echo "✅ Export เสร็จสมบูรณ์!"
echo "📄 ไฟล์: $OUTPUT_FILE"
echo ""
echo "💡 ใช้ข้อมูลนี้ในการสร้าง Dockerfile สำหรับ Z2"
echo ""

