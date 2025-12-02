#!/bin/bash
# Script สำหรับแก้ปัญหา CUDA version mismatch บน Server
# 
# ปัญหา: Base image ใช้ CUDA 12.1 แต่ PyTorch และ CT2 ใช้ CUDA 11.8
# วิธีแก้: อัพเกรด PyTorch และ CT2 เป็นเวอร์ชันที่รองรับ CUDA 12.1
#
# วิธีใช้งาน:
#   bash scripts/pod/fix-cuda-mismatch-on-server.sh
#
# ⚠️ หมายเหตุ: Script นี้ต้องรันใน container ที่มีปัญหา

set -e

echo "🔧 แก้ปัญหา CUDA Version Mismatch บน Server"
echo "============================================"
echo ""

# ตรวจสอบ CUDA version ที่มีอยู่
echo "📋 ตรวจสอบ CUDA Version ปัจจุบัน..."
python3 << 'PYEOF'
import torch
import sys

print(f"PyTorch Version: {torch.__version__}")
print(f"PyTorch CUDA Version: {torch.version.cuda}")
print(f"CUDA Available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ตรวจสอบ CUDA runtime version จาก driver
try:
    import subprocess
    result = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(f"NVIDIA Driver: {result.stdout.strip()}")
except:
    pass

PYEOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Option 1: อัพเกรดเป็น CUDA 12.1 (แนะนำ)
echo "🔧 Option 1: อัพเกรด PyTorch และ CT2 เป็น CUDA 12.1"
echo ""
echo "⚠️  การอัพเกรดจะ:"
echo "   - Uninstall PyTorch และ CT2 ปัจจุบัน (CUDA 11.8)"
echo "   - Install PyTorch 2.1.1+cu121 (รองรับ CUDA 12.1)"
echo "   - Reinstall ctranslate2 สำหรับ CUDA 12.1"
echo ""
read -p "ต้องการดำเนินการต่อ? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "📦 Step 1: Uninstall packages ปัจจุบัน..."
    pip3 uninstall -y torch torchaudio ctranslate2 faster-whisper || true
    
    echo ""
    echo "📦 Step 2: Install PyTorch สำหรับ CUDA 12.1..."
    pip3 install --no-cache-dir \
        torch==2.1.1 \
        torchaudio==2.1.1 \
        --index-url https://download.pytorch.org/whl/cu121
    
    echo ""
    echo "📦 Step 3: Reinstall ctranslate2 (จะ auto-detect CUDA 12.1)..."
    # ctranslate2 จะ build สำหรับ CUDA ที่มีอยู่ใน runtime
    pip3 install --no-cache-dir --upgrade --force-reinstall \
        "ctranslate2>=4.5.0"
    
    echo ""
    echo "📦 Step 4: Reinstall faster-whisper..."
    pip3 install --no-cache-dir \
        "faster-whisper==1.0.2"
    
    echo ""
    echo "✅ การอัพเกรดเสร็จสมบูรณ์!"
    echo ""
    echo "🔍 ตรวจสอบเวอร์ชันใหม่..."
    python3 << 'PYEOF'
import torch
import ctranslate2
import faster_whisper

print(f"PyTorch: {torch.__version__}")
print(f"PyTorch CUDA: {torch.version.cuda}")
print(f"CTranslate2: {ctranslate2.__version__}")
print(f"Faster-Whisper: {faster_whisper.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
PYEOF
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ แก้ไขเสร็จสมบูรณ์!"
    echo ""
    echo "💡 ขั้นตอนต่อไป:"
    echo "   1. ทดสอบ GPU transcription:"
    echo "      export CT2_USE_CUDA_GRAPH=0"
    echo "      python3 -c \"from faster_whisper import WhisperModel; m = WhisperModel('tiny', device='cuda'); print('OK')\""
    echo ""
    echo "   2. Restart services:"
    echo "      bash scripts/pod/restart-pod-services.sh"
    echo ""
else
    echo "❌ ยกเลิกการแก้ไข"
    exit 0
fi

