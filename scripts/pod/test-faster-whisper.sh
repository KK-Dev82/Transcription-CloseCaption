#!/usr/bin/env bash
# Script สำหรับทดสอบ faster-whisper 1.2.1

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

print_header "🧪 ทดสอบ faster-whisper 1.2.1"

# แก้ไข cuDNN version mismatch สำหรับ faster-whisper
# ตรวจสอบ CTranslate2 version และใช้ cuDNN library ที่เหมาะสม
CT2_VER=$(python3 << 'PYEOF'
try:
    import ctranslate2
    print(ctranslate2.__version__)
except:
    print("NOT_INSTALLED")
PYEOF
)

if [ "$CT2_VER" != "NOT_INSTALLED" ]; then
    if [ "$CT2_VER" == "4.4.0" ]; then
        CUDNN_LIB="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs/libcudnn-463fd6d5.so.8.9.7"
        if [ -f "$CUDNN_LIB" ]; then
            export LD_PRELOAD="$CUDNN_LIB"
            print_success "✅ Using cuDNN 8.9.7 from CTranslate2 4.4.0 (LD_PRELOAD)"
        fi
    elif [[ "$CT2_VER" == "4.6"* ]]; then
        CUDNN_LIB="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs/libcudnn-74a4c495.so.9.1.0"
        if [ -f "$CUDNN_LIB" ]; then
            export LD_PRELOAD="$CUDNN_LIB"
            print_success "✅ Using cuDNN 9.1.0 from CTranslate2 $CT2_VER (LD_PRELOAD)"
        fi
    fi
else
    print_warning "⚠️  CTranslate2 not installed, faster-whisper may have issues"
fi
echo ""

# 1. ตรวจสอบ Python
print_header "1. ตรวจสอบ Python"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_info "Python: $PYTHON_VERSION"
echo ""

# 2. ตรวจสอบ PyTorch และ CUDA
print_header "2. ตรวจสอบ PyTorch และ CUDA"
python3 << 'PYEOF'
import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    if torch.backends.cudnn.is_available():
        print(f"cuDNN Version: {torch.backends.cudnn.version()}")
    else:
        print("⚠️  cuDNN not available")
else:
    print("❌ CUDA not available")
    exit(1)
PYEOF

if [ $? -ne 0 ]; then
    print_error "PyTorch หรือ CUDA มีปัญหา"
    exit 1
fi
echo ""

# 3. ตรวจสอบ NumPy
print_header "3. ตรวจสอบ NumPy"
NUMPY_VERSION=$(python3 << 'PYEOF'
try:
    import numpy
    print(numpy.__version__)
except:
    print("NOT_INSTALLED")
PYEOF
)

if [ "$NUMPY_VERSION" != "NOT_INSTALLED" ]; then
    print_info "NumPy: $NUMPY_VERSION"
    if [[ "$NUMPY_VERSION" == "2."* ]]; then
        print_warning "⚠️  NumPy 2.x พบ - ต้อง downgrade"
    else
        print_success "✅ NumPy version OK"
    fi
else
    print_error "NumPy not installed"
    exit 1
fi
echo ""

# 4. ตรวจสอบ CTranslate2
print_header "4. ตรวจสอบ CTranslate2"
CT2_VERSION=$(python3 << 'PYEOF'
try:
    import ctranslate2
    print(ctranslate2.__version__)
except ImportError:
    print("NOT_INSTALLED")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF
)

if [ "$CT2_VERSION" == "NOT_INSTALLED" ]; then
    print_error "CTranslate2 not installed"
    exit 1
elif [[ "$CT2_VERSION" == "ERROR"* ]]; then
    print_error "CTranslate2 error: $CT2_VERSION"
    exit 1
else
    print_success "CTranslate2: $CT2_VERSION"
fi
echo ""

# 5. ตรวจสอบ faster-whisper
print_header "5. ตรวจสอบ faster-whisper"
FW_VERSION=$(python3 << 'PYEOF'
try:
    import faster_whisper
    print(faster_whisper.__version__)
except ImportError:
    print("NOT_INSTALLED")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF
)

if [ "$FW_VERSION" == "NOT_INSTALLED" ]; then
    print_error "faster-whisper not installed"
    exit 1
elif [[ "$FW_VERSION" == "ERROR"* ]]; then
    print_error "faster-whisper error: $FW_VERSION"
    exit 1
else
    print_success "faster-whisper: $FW_VERSION"
fi
echo ""

# 6. ทดสอบ Import
print_header "6. ทดสอบ Import faster-whisper"
python3 << 'PYEOF'
try:
    from faster_whisper import WhisperModel
    print("✅ Import successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
PYEOF

if [ $? -ne 0 ]; then
    print_error "Import failed"
    exit 1
fi
echo ""

# 7. ทดสอบ Model Loading
print_header "7. ทดสอบ Model Loading (base model)"
print_info "กำลังโหลด model 'base'..."
python3 << 'PYEOF'
import sys
from faster_whisper import WhisperModel
import torch

try:
    print("Initializing WhisperModel...")
    model = WhisperModel("base", device="cuda", compute_type="float16")
    print("✅ Model loaded successfully")
    print(f"✅ Device: cuda")
    print(f"✅ Compute type: float16")
except Exception as e:
    print(f"❌ Model loading failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    print_error "Model loading failed"
    exit 1
fi
echo ""

# 8. ทดสอบ Transcription (ถ้ามีไฟล์ทดสอบ)
print_header "8. ทดสอบ Transcription"
print_info "กำลังทดสอบ transcription..."

# สร้างไฟล์เสียงทดสอบ (sine wave 1 วินาที)
python3 << 'PYEOF'
import numpy as np
import soundfile as sf
import os

# สร้าง sine wave 1 วินาที (16kHz, mono)
sample_rate = 16000
duration = 1.0
frequency = 440  # A4 note
t = np.linspace(0, duration, int(sample_rate * duration))
audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

# บันทึกไฟล์
os.makedirs("test-files", exist_ok=True)
test_file = "test-files/test_audio.wav"
sf.write(test_file, audio, sample_rate)
print(f"✅ Created test audio: {test_file}")
PYEOF

if [ -f "test-files/test_audio.wav" ]; then
    print_info "Testing transcription with test audio..."
    python3 << 'PYEOF'
import sys
from faster_whisper import WhisperModel

try:
    model = WhisperModel("base", device="cuda", compute_type="float16")
    segments, info = model.transcribe("test-files/test_audio.wav", beam_size=5)
    
    print("✅ Transcription successful")
    print(f"Language: {info.language} (probability: {info.language_probability:.2f})")
    
    # อ่าน segments แรก
    first_segment = next(segments, None)
    if first_segment:
        print(f"Text: {first_segment.text}")
        print(f"Start: {first_segment.start:.2f}s, End: {first_segment.end:.2f}s")
    else:
        print("⚠️  No segments found (อาจเป็นเพราะไฟล์เสียงสั้นเกินไป)")
    
except Exception as e:
    print(f"❌ Transcription failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

    if [ $? -eq 0 ]; then
        print_success "✅ Transcription test passed"
    else
        print_error "❌ Transcription test failed"
        exit 1
    fi
else
    print_warning "⚠️  Test audio not created, skipping transcription test"
fi
echo ""

# 9. สรุป
print_header "✅ ทดสอบเสร็จสิ้น"
print_success "faster-whisper 1.2.1 ทำงานได้แล้ว!"
echo ""

