#!/bin/bash
# Fix CTranslate2 GPU Support
# ตั้งค่า LD_LIBRARY_PATH และตรวจสอบ CUDA support

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🔧 Fixing CTranslate2 GPU Support..."
echo ""

# 1. ตั้งค่า LD_LIBRARY_PATH
echo "1️⃣ Setting LD_LIBRARY_PATH..."
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
SYSTEM_PATH="/usr/lib/x86_64-linux-gnu"
CUDA_LIB_PATH="/usr/local/cuda-12.1/lib64"
CTRANSLATE2_LIB_PATH="/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

NEW_LD_PATH=""
for path in "$CUDNN_LIB_PATH" "$SYSTEM_PATH" "$CUDA_LIB_PATH" "$CTRANSLATE2_LIB_PATH"; do
    if [ -d "$path" ]; then
        if [ -z "$NEW_LD_PATH" ]; then
            NEW_LD_PATH="$path"
        else
            NEW_LD_PATH="$NEW_LD_PATH:$path"
        fi
        echo "  ✅ Added: $path"
    else
        echo "  ⚠️  Not found: $path"
    fi
done

if [ -n "$NEW_LD_PATH" ]; then
    export LD_LIBRARY_PATH="$NEW_LD_PATH:${LD_LIBRARY_PATH:-}"
    echo "  ✅ LD_LIBRARY_PATH set"
else
    echo "  ❌ No paths found!"
    exit 1
fi

# 2. ตรวจสอบ cuDNN libraries
echo ""
echo "2️⃣ Checking cuDNN libraries..."
CUDNN_FILES=(
    "libcudnn.so.8"
    "libcudnn_ops_infer.so.8"
    "libcudnn_cnn_infer.so.8"
)

for file in "${CUDNN_FILES[@]}"; do
    found=false
    for path in "$CUDNN_LIB_PATH" "$SYSTEM_PATH" "$CUDA_LIB_PATH"; do
        if [ -f "$path/$file" ]; then
            echo "  ✅ Found: $path/$file"
            found=true
            break
        fi
    done
    if [ "$found" = false ]; then
        echo "  ⚠️  Not found: $file"
    fi
done

# 3. ตรวจสอบ ctranslate2 CUDA support
echo ""
echo "3️⃣ Checking ctranslate2 CUDA support..."
python3 << 'PYTHON'
import os
import sys

# ตั้งค่า LD_LIBRARY_PATH
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
os.environ['LD_LIBRARY_PATH'] = new_ld_path

try:
    import ctranslate2
    print(f"  ✅ ctranslate2 version: {ctranslate2.__version__}")
    
    # ตรวจสอบ CUDA compute types
    cuda_types = ctranslate2.get_supported_compute_types("cuda")
    if cuda_types:
        print(f"  ✅ CUDA support: Available")
        print(f"     Compute types: {', '.join(sorted(cuda_types))}")
    else:
        print("  ❌ CUDA support: NOT available")
        sys.exit(1)
    
    # ลองสร้าง model
    from faster_whisper import WhisperModel
    print("  🧪 Testing WhisperModel with CUDA...")
    model = WhisperModel("tiny", device="cuda", compute_type="float16")
    print("  ✅ Model created successfully!")
    
except ImportError as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ CTranslate2 GPU support is working!"
    echo ""
    echo "📋 Next steps:"
    echo "  1. Restart main API: systemctl restart transcription-api (or your restart command)"
    echo "  2. Restart RQ workers: bash scripts/pod/start-rq-workers.sh"
    echo "  3. Verify GPU usage: nvidia-smi"
else
    echo ""
    echo "❌ CTranslate2 GPU support check failed!"
    echo ""
    echo "💡 Try reinstalling ctranslate2:"
    echo "  pip3 uninstall -y ctranslate2"
    echo "  pip3 install ctranslate2==4.4.0 --no-cache-dir"
    exit 1
fi
