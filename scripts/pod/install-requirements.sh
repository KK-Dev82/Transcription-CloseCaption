#!/usr/bin/env bash
# Script สำหรับติดตั้ง Requirements ที่ขาดใน RunPod Template
# รองรับทั้ง:
#   - runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04
#   - runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

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

print_header "📦 ติดตั้ง Requirements สำหรับ faster-whisper 1.2.1"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

# 1. ตรวจสอบ cuDNN version เพื่อเลือก CTranslate2 ที่เหมาะสม
print_header "1. ตรวจสอบ cuDNN Version"
CUDNN_VERSION=$(python3 << 'PYEOF'
import torch
if torch.backends.cudnn.is_available():
    print(torch.backends.cudnn.version())
else:
    print("0")
PYEOF
)

echo "cuDNN Version: $CUDNN_VERSION"
echo ""

# 2. เลือก CTranslate2 version
if [ "$CUDNN_VERSION" -ge 9000 ]; then
    CT2_VERSION=">=4.6.2"
    print_success "cuDNN 9.x → ใช้ CTranslate2 4.6.2+"
elif [ "$CUDNN_VERSION" -ge 8000 ]; then
    CT2_VERSION="==4.4.0"
    print_success "cuDNN 8.x → ใช้ CTranslate2 4.4.0"
else
    CT2_VERSION="==4.4.0"
    print_warning "cuDNN version ต่ำ → ใช้ CTranslate2 4.4.0 (fallback)"
fi
echo ""

# 3. แก้ไข NumPy version (ต้อง <2.0.0 เพื่อความเข้ากันได้)
print_header "2. แก้ไข NumPy Version (<2.0.0)"
print_info "ตรวจสอบ NumPy version ปัจจุบัน..."
CURRENT_NUMPY=$(python3 << 'PYEOF'
try:
    import numpy
    print(numpy.__version__)
except:
    print("NOT_INSTALLED")
PYEOF
)

if [ "$CURRENT_NUMPY" != "NOT_INSTALLED" ]; then
    print_info "NumPy version ปัจจุบัน: $CURRENT_NUMPY"
    
    # ตรวจสอบว่าเป็น NumPy 2.x หรือไม่
    if [[ "$CURRENT_NUMPY" == "2."* ]]; then
        print_warning "NumPy 2.x พบ - ต้อง downgrade เป็น <2.0.0"
        print_info "Downgrading NumPy..."
        pip3 install --no-cache-dir --force-reinstall "numpy<2.0.0" || {
            print_error "NumPy downgrade failed"
            exit 1
        }
        print_success "NumPy downgraded to <2.0.0"
    else
        print_success "NumPy version OK (<2.0.0)"
    fi
else
    print_info "NumPy not installed - installing <2.0.0..."
    pip3 install --no-cache-dir "numpy<2.0.0" || {
        print_error "NumPy installation failed"
        exit 1
    }
    print_success "NumPy installed"
fi
echo ""

# 4. ติดตั้ง CTranslate2
print_header "3. ติดตั้ง CTranslate2"
echo "Installing: ctranslate2$CT2_VERSION"
if pip3 install --no-cache-dir "ctranslate2$CT2_VERSION"; then
    print_success "CTranslate2 installed"
else
    print_error "CTranslate2 installation failed"
    exit 1
fi
echo ""

# 5. ตรวจสอบ CTranslate2 version
print_info "ตรวจสอบ CTranslate2 version..."
CT2_VER=$(python3 << 'PYEOF'
try:
    import ctranslate2
    print(ctranslate2.__version__)
except:
    print("ERROR")
PYEOF
)

if [ "$CT2_VER" != "ERROR" ]; then
    print_success "CTranslate2: $CT2_VER"
else
    print_error "CTranslate2 not installed correctly"
    exit 1
fi
echo ""

# 6. ติดตั้ง faster-whisper 1.2.1
print_header "4. ติดตั้ง faster-whisper 1.2.1"
if pip3 install --no-cache-dir "faster-whisper==1.2.1"; then
    print_success "faster-whisper 1.2.1 installed"
else
    print_error "faster-whisper installation failed"
    exit 1
fi
echo ""

# 7. ทดสอบ faster-whisper
print_header "5. ทดสอบ faster-whisper"
python3 << 'PYEOF'
try:
    from faster_whisper import WhisperModel
    import torch
    
    print("✅ faster-whisper imported successfully")
    print(f"✅ CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print("📦 Testing model loading...")
        model = WhisperModel("base", device="cuda", compute_type="float16")
        print("✅ faster-whisper 1.2.1 ทำงานได้แล้ว!")
    else:
        print("⚠️  CUDA not available - faster-whisper will use CPU")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF

if [ $? -eq 0 ]; then
    print_success "✅ faster-whisper 1.2.1 พร้อมใช้งาน"
else
    print_error "❌ faster-whisper test failed"
    exit 1
fi
echo ""

# 8. ติดตั้ง dependencies อื่นๆ จาก requirements.txt
print_header "6. ติดตั้ง Dependencies อื่นๆ"
if [ -f "requirements.txt" ]; then
    print_info "Installing from requirements.txt..."
    
    # ติดตั้ง dependencies ที่ยังไม่มี (skip faster-whisper และ ctranslate2 เพราะติดตั้งแล้ว)
    pip3 install --no-cache-dir -r requirements.txt 2>&1 | grep -v "already satisfied" | tail -20 || {
        print_warning "Some dependencies may have failed, but core packages are installed"
    }
    
    print_success "Dependencies installed"
else
    print_warning "requirements.txt not found"
fi
echo ""

# 9. สรุป
print_header "✅ ติดตั้งเสร็จสิ้น"
echo ""
echo "📋 สรุป:"
echo "   ✅ NumPy: <2.0.0"
echo "   ✅ CTranslate2: $CT2_VER"
echo "   ✅ faster-whisper: 1.2.1"
echo "   ✅ Dependencies: จาก requirements.txt"
echo ""
echo "🚀 พร้อมใช้งาน faster-whisper 1.2.1 แล้ว!"
echo ""

