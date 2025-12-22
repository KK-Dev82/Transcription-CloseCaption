#!/usr/bin/env bash
# Script สำหรับทดสอบ faster-whisper 1.2.1 ใน GPU mode
# ถ้า GPU mode ไม่ทำงาน จะทดสอบ CPU mode

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

print_header "🧪 ทดสอบ faster-whisper 1.2.1 (GPU Mode)"

# สร้างไฟล์เสียงทดสอบ
mkdir -p test-files
python3 << 'PYEOF'
import numpy as np
import soundfile as sf
import os

if not os.path.exists("test-files/test_audio.wav"):
    sample_rate = 16000
    duration = 1.0
    frequency = 440
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    sf.write("test-files/test_audio.wav", audio, sample_rate)
    print("✅ Created test audio")
PYEOF

# ตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN libraries
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
if [ -d "$CUDNN_LIB_PATH" ]; then
    # ตรวจสอบว่า LD_LIBRARY_PATH มีอยู่หรือไม่
    if [ -z "${LD_LIBRARY_PATH:-}" ]; then
        export LD_LIBRARY_PATH="$CUDNN_LIB_PATH"
    else
        export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$LD_LIBRARY_PATH"
    fi
    print_success "✅ Set LD_LIBRARY_PATH for cuDNN libraries"
fi

# ทดสอบ GPU mode
print_header "1. ทดสอบ GPU Mode"
print_info "Testing faster-whisper with GPU (CUDA)..."
GPU_WORKING=false

python3 << 'PYEOF'
import sys
from faster_whisper import WhisperModel
import torch
import ctranslate2

try:
    print(f"✅ CTranslate2: {ctranslate2.__version__}")
    print(f"✅ CUDA available: {torch.cuda.is_available()}")
    
    if not torch.cuda.is_available():
        print("❌ CUDA not available")
        sys.exit(1)
    
    print("Initializing WhisperModel (GPU)...")
    model = WhisperModel("base", device="cuda", compute_type="float16")
    print("✅ Model loaded successfully (GPU)")
    
    # ทดสอบ transcription
    segments, info = model.transcribe("test-files/test_audio.wav", beam_size=5)
    print("✅ Transcription successful (GPU)")
    print(f"Language: {info.language}")
    
    first_segment = next(segments, None)
    if first_segment:
        print(f"Text: {first_segment.text}")
    
    print("GPU_MODE_WORKING")
    sys.exit(0)
except Exception as e:
    print(f"❌ GPU mode failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    GPU_WORKING=true
    print_success "✅ GPU mode ทำงานได้!"
else
    print_error "❌ GPU mode ไม่ทำงาน"
    exit 1
fi

echo ""
print_header "✅ ทดสอบเสร็จสิ้น"
if [ "$GPU_WORKING" = true ]; then
    print_success "faster-whisper 1.2.1 ทำงานได้ใน GPU mode!"
    print_info "💡 หมายเหตุ: GPU mode ใช้ CUDA acceleration (เร็วที่สุด)"
else
    print_warning "faster-whisper 1.2.1 ทำงานได้ใน CPU mode (ช้ากว่า GPU)"
    print_info "💡 ถ้าต้องการ GPU mode: ตรวจสอบ cuDNN libraries และ LD_LIBRARY_PATH"
fi
echo ""

