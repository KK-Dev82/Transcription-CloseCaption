#!/bin/bash
# ตรวจสอบว่า CTranslate2 และ faster-whisper เห็น GPU และทำงานได้
#
# วิธีใช้:
#   ./scripts/utility/verify-ctranslate2-gpu.sh
#
# หรือโหลด LD_LIBRARY_PATH ก่อน (ถ้า setup-cudnn-env.sh รันแล้ว):
#   source scripts/utility/.cudnn-ldpath.sh
#   ./scripts/utility/verify-ctranslate2-gpu.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# โหลด LD_LIBRARY_PATH (ถ้ามี)
if [ -f "$PROJECT_ROOT/scripts/utility/.cudnn-ldpath.sh" ]; then
    set -a
    source "$PROJECT_ROOT/scripts/utility/.cudnn-ldpath.sh"
    set +a
    echo "✅ Loaded LD_LIBRARY_PATH"
fi

# ปิด hf_transfer เพื่อหลีกเลี่ยง ModuleNotFoundError
export HF_HUB_ENABLE_HF_TRANSFER=0

echo ""
echo "🔍 Verifying CTranslate2 + faster-whisper GPU support"
echo "=================================================="

python3 << 'PYTHON'
import os
import sys

print("1️⃣  LD_LIBRARY_PATH:", os.environ.get("LD_LIBRARY_PATH", "(not set)")[:100] + "..." if len(os.environ.get("LD_LIBRARY_PATH", "")) > 100 else os.environ.get("LD_LIBRARY_PATH", "(not set)"))
print()

# CTranslate2
try:
    import ctranslate2
    print("2️⃣  ctranslate2 version:", ctranslate2.__version__)
    cuda_types = ctranslate2.get_supported_compute_types("cuda")
    if cuda_types:
        print("    ✅ CUDA support:", ", ".join(sorted(cuda_types)))
    else:
        print("    ❌ CUDA support: NOT available")
        sys.exit(1)
except Exception as e:
    print("    ❌ ctranslate2 error:", e)
    sys.exit(1)

# faster-whisper + WhisperModel
try:
    from faster_whisper import WhisperModel
    print("3️⃣  Loading WhisperModel (tiny, cuda, float16)...")
    model = WhisperModel("tiny", device="cuda", compute_type="float16")
    print("    ✅ Model loaded successfully!")
except Exception as e:
    print("    ❌ WhisperModel error:", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("4️⃣  Model ready for inference")
print()
print("✅ CTranslate2 + GPU verification passed!")
PYTHON

echo ""
echo "=================================================="
echo "✅ Verification complete"
