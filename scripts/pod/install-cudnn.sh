#!/usr/bin/env bash
# Script สำหรับติดตั้ง cuDNN libraries ที่จำเป็นสำหรับ faster-whisper GPU mode

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

print_header "📦 ตรวจสอบและติดตั้ง cuDNN Libraries"

# 1. ตรวจสอบ CUDA version
print_header "1. ตรวจสอบ CUDA Version"
CUDA_VERSION=$(python3 << 'PYEOF'
import torch
if torch.cuda.is_available():
    print(torch.version.cuda)
else:
    print("NOT_AVAILABLE")
PYEOF
)

if [ "$CUDA_VERSION" == "NOT_AVAILABLE" ]; then
    print_error "CUDA not available"
    exit 1
fi

print_info "CUDA Version: $CUDA_VERSION"

# ตรวจสอบ cuDNN version
CUDNN_VERSION=$(python3 << 'PYEOF'
import torch
if torch.backends.cudnn.is_available():
    print(torch.backends.cudnn.version())
else:
    print("NOT_AVAILABLE")
PYEOF
)

if [ "$CUDNN_VERSION" != "NOT_AVAILABLE" ]; then
    print_info "cuDNN Version: $CUDNN_VERSION"
else
    print_error "cuDNN not available"
    exit 1
fi
echo ""

# 2. ตรวจสอบ cuDNN libraries ที่มีอยู่
print_header "2. ตรวจสอบ cuDNN Libraries"
print_info "ตรวจสอบ libcudnn_ops_infer.so.8..."

# ตรวจสอบใน system paths
SYSTEM_PATHS=(
    "/usr/lib/x86_64-linux-gnu"
    "/usr/local/cuda/lib64"
    "/usr/local/cuda-*/lib64"
    "/usr/lib"
)

FOUND_LIB=false
for path in "${SYSTEM_PATHS[@]}"; do
    if [ -d "$path" ]; then
        if find "$path" -name "libcudnn_ops_infer.so.8" 2>/dev/null | grep -q .; then
            LIB_PATH=$(find "$path" -name "libcudnn_ops_infer.so.8" 2>/dev/null | head -1)
            print_success "พบ: $LIB_PATH"
            FOUND_LIB=true
            break
        fi
    fi
done

if [ "$FOUND_LIB" = false ]; then
    print_warning "ไม่พบ libcudnn_ops_infer.so.8 ใน system paths"
    print_info "ตรวจสอบ PyTorch bundled cuDNN libraries..."
    
    # ตรวจสอบ cuDNN libraries จาก PyTorch/nvidia package
    NVIDIA_CUDNN_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
    if [ -d "$NVIDIA_CUDNN_PATH" ]; then
        if [ -f "$NVIDIA_CUDNN_PATH/libcudnn_ops_infer.so.8" ]; then
            print_success "พบ cuDNN libraries ใน: $NVIDIA_CUDNN_PATH"
            print_info "ตั้งค่า LD_LIBRARY_PATH..."
            export LD_LIBRARY_PATH="$NVIDIA_CUDNN_PATH:$LD_LIBRARY_PATH"
            FOUND_LIB=true
        fi
    fi
    
    if [ "$FOUND_LIB" = false ]; then
        print_warning "ยังไม่พบ libcudnn_ops_infer.so.8"
    fi
fi
echo ""

# 3. ตรวจสอบว่าต้องติดตั้ง cuDNN หรือไม่
print_header "3. วิธีติดตั้ง cuDNN"

if [ "$FOUND_LIB" = true ]; then
    print_success "cuDNN libraries พร้อมใช้งานแล้ว!"
else
    print_warning "ต้องติดตั้ง cuDNN libraries เพิ่มเติม"
    echo ""
    print_info "วิธีที่ 1: ติดตั้งจาก NVIDIA (แนะนำ)"
    echo "  1. Download cuDNN จาก: https://developer.nvidia.com/cudnn"
    echo "  2. Extract และ copy libraries:"
    echo "     sudo cp cuda/include/cudnn*.h /usr/local/cuda/include"
    echo "     sudo cp cuda/lib64/libcudnn* /usr/local/cuda/lib64"
    echo "     sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn*"
    echo ""
    print_info "วิธีที่ 2: ใช้ apt (ถ้ามี package)"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install libcudnn8-dev"
    echo ""
    print_info "วิธีที่ 3: ใช้ conda (ถ้าใช้ conda environment)"
    echo "  conda install -c conda-forge cudnn"
    echo ""
fi
echo ""

# 4. ทดสอบ faster-whisper GPU mode
print_header "4. ทดสอบ faster-whisper GPU Mode"
print_info "Testing faster-whisper with GPU..."

python3 << 'PYEOF'
import sys
from faster_whisper import WhisperModel
import torch

try:
    print(f"CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("❌ CUDA not available")
        sys.exit(1)
    
    print("Initializing WhisperModel (GPU)...")
    model = WhisperModel("base", device="cuda", compute_type="float16")
    print("✅ Model loaded successfully (GPU)")
    print("GPU_MODE_WORKING")
    sys.exit(0)
except Exception as e:
    print(f"❌ GPU mode failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    print_success "✅ GPU mode ทำงานได้!"
else
    print_error "❌ GPU mode ไม่ทำงาน"
    print_warning "💡 ต้องติดตั้ง cuDNN libraries เพิ่มเติม"
    exit 1
fi
echo ""

print_header "✅ ตรวจสอบเสร็จสิ้น"

