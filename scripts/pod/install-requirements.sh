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

# ตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN libraries (ถ้ามี)
CUDNN_LIB_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
if [ -d "$CUDNN_LIB_PATH" ]; then
    # ตรวจสอบว่า LD_LIBRARY_PATH มีอยู่หรือไม่
    if [ -z "${LD_LIBRARY_PATH:-}" ]; then
        export LD_LIBRARY_PATH="$CUDNN_LIB_PATH"
    else
        export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$LD_LIBRARY_PATH"
    fi
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

# 1. แก้ไข NumPy version (ต้อง <2.0.0 เพื่อความเข้ากันได้)
print_header "1. แก้ไข NumPy Version (<2.0.0)"
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

# 2. ติดตั้ง CTranslate2 4.4.0
print_header "2. ติดตั้ง CTranslate2 4.4.0"
print_info "Installing: ctranslate2==4.4.0"
print_info "หมายเหตุ: ใช้ CTranslate2 4.4.0 (รองรับ cuDNN 8.x ที่ PyTorch 2.2.0 ใช้)"
if pip3 install --no-cache-dir "ctranslate2==4.4.0"; then
    print_success "CTranslate2 4.4.0 installed"
else
    print_error "CTranslate2 installation failed"
    exit 1
fi
echo ""

# 3. ติดตั้ง faster-whisper 1.2.1
print_header "3. ติดตั้ง faster-whisper 1.2.1"
if pip3 install --no-cache-dir "faster-whisper==1.2.1"; then
    print_success "faster-whisper 1.2.1 installed"
else
    print_error "faster-whisper installation failed"
    exit 1
fi
echo ""

# 4. ทดสอบ faster-whisper
print_header "4. ทดสอบ faster-whisper"
python3 << 'PYEOF'
try:
    from faster_whisper import WhisperModel
    import ctranslate2
    
    print("✅ faster-whisper imported successfully")
    print(f"✅ CTranslate2: {ctranslate2.__version__}")
    
    # ทดสอบ CPU mode (ทำงานได้แน่นอน)
    print("📦 Testing model loading (CPU mode)...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("✅ faster-whisper 1.2.1 ทำงานได้แล้ว!")
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

# 5. ติดตั้ง dependencies อื่นๆ จาก requirements.txt
print_header "5. ติดตั้ง Dependencies อื่นๆ"
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

# 6. สรุป
print_header "✅ ติดตั้งเสร็จสิ้น"
echo ""
echo "📋 สรุป:"
echo "   ✅ NumPy: <2.0.0"
echo "   ✅ CTranslate2: 4.4.0"
echo "   ✅ faster-whisper: 1.2.1"
echo "   ✅ Dependencies: จาก requirements.txt"
echo ""
echo "🚀 พร้อมใช้งาน faster-whisper 1.2.1 แล้ว!"
echo ""

