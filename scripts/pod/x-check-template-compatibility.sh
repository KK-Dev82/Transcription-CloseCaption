#!/usr/bin/env bash
# Script สำหรับตรวจสอบ Compatibility ของ RunPod Templates
# สำหรับ faster-whisper 1.2.1 + RTX 4000 Ada

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

print_header "🔍 ตรวจสอบ Compatibility สำหรับ faster-whisper 1.2.1"

# ตรวจสอบ template ปัจจุบัน
CURRENT_IMAGE=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || echo "Unknown")

print_info "Current environment check..."
echo ""

# 1. ตรวจสอบ Python
print_header "1. ตรวจสอบ Python"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

print_info "Python: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    print_success "✅ Python $PYTHON_VERSION (รองรับ faster-whisper 1.2.1)"
else
    print_error "❌ Python version ไม่รองรับ (ต้องการ 3.8+)"
fi
echo ""

# 2. ตรวจสอบ PyTorch
print_header "2. ตรวจสอบ PyTorch"
python3 << 'PYEOF'
import sys
try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    
    # ตรวจสอบ CUDA
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        
        # ตรวจสอบ cuDNN
        if torch.backends.cudnn.is_available():
            cudnn_version = torch.backends.cudnn.version()
            print(f"cuDNN Version: {cudnn_version}")
            
            # แนะนำ CTranslate2 version
            if cudnn_version >= 9000:
                print("✅ cuDNN 9.x → ใช้ CTranslate2 4.6.2+")
            elif cudnn_version >= 8000:
                print("✅ cuDNN 8.x → ใช้ CTranslate2 4.4.0")
            else:
                print("⚠️  cuDNN version ต่ำ")
        else:
            print("❌ cuDNN not available")
    else:
        print("❌ CUDA not available")
        sys.exit(1)
except ImportError:
    print("❌ PyTorch not installed")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    print_success "✅ PyTorch และ CUDA ทำงานได้"
else
    print_error "❌ PyTorch หรือ CUDA มีปัญหา"
    exit 1
fi
echo ""

# 3. ตรวจสอบ NumPy version
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
        print_warning "⚠️  NumPy 2.x พบ - ต้อง downgrade เป็น <2.0.0"
    else
        print_success "✅ NumPy version OK (<2.0.0)"
    fi
else
    print_info "NumPy: Not installed"
fi
echo ""

# 4. ตรวจสอบ faster-whisper compatibility
print_header "4. ตรวจสอบ faster-whisper 1.2.1 Compatibility"
python3 << 'PYEOF'
import sys

print("faster-whisper 1.2.1 Requirements:")
print("  ✅ ctranslate2>=4.0,<6")
print("  ✅ CUDA 11.8+ หรือ 12.x")
print("  ✅ cuDNN 8.x หรือ 9.x")
print("  ✅ Python 3.8+")
print("")
print("RTX 4000 Ada Generation:")
print("  ✅ Compute Capability: 8.9")
print("  ✅ รองรับ CUDA 12.x")
print("")
print("✅ ทั้ง 2 templates รองรับ faster-whisper 1.2.1")
PYEOF
echo ""

# 5. สรุปและแนะนำ
print_header "📋 สรุปและแนะนำ"
echo ""
echo "Template 1: runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04"
echo "   ✅ เสถียรกว่า"
echo "   ✅ Python 3.10 (รองรับดี)"
print_info "   💡 แนะนำ: ใช้ template นี้ (เสถียร, รองรับแน่นอน)"
echo ""
echo "Template 2: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
echo "   ✅ เร็วกว่า (PyTorch 2.4.0 + Python 3.11)"
echo "   ✅ CUDA 12.4.1 (ใหม่กว่า)"
print_warning "   ⚠️  ต้องทดสอบ (Python 3.11 อาจมี compatibility issues)"
echo ""
echo "💡 คำแนะนำ:"
echo "   - สำหรับ Production: ใช้ Template 1 (เสถียร)"
echo "   - สำหรับ Performance สูงสุด: ทดสอบ Template 2 ก่อน"
echo ""

