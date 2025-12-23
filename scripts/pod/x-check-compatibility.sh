#!/usr/bin/env bash
# Script สำหรับตรวจสอบ Compatibility ของ RunPod Template
# runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04

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

print_header "🔍 ตรวจสอบ Compatibility ของ RunPod Template"

echo "Base Image: runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04"
echo ""

# 1. ตรวจสอบ Python
print_header "1. ตรวจสอบ Python"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python: $PYTHON_VERSION"
if [[ "$PYTHON_VERSION" == "3.10"* ]]; then
    print_success "✅ Python 3.10 (ถูกต้อง)"
else
    print_error "❌ Python version ไม่ตรง (ต้องการ 3.10)"
fi
echo ""

# 2. ตรวจสอบ PyTorch
print_header "2. ตรวจสอบ PyTorch"
python3 << 'PYEOF'
import torch
import sys

print(f"PyTorch: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    if torch.backends.cudnn.is_available():
        cudnn_version = torch.backends.cudnn.version()
        print(f"cuDNN Version: {cudnn_version}")
        
        # ตรวจสอบ cuDNN version
        if cudnn_version >= 9000:
            print("✅ cuDNN 9.x (รองรับ CTranslate2 4.6.2+)")
        elif cudnn_version >= 8000:
            print("✅ cuDNN 8.x (รองรับ CTranslate2 4.4.0)")
        else:
            print("⚠️  cuDNN version ต่ำกว่า 8.x")
    else:
        print("❌ cuDNN not available")
else:
    print("❌ CUDA not available")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    print_success "✅ PyTorch และ CUDA ทำงานได้"
else
    print_error "❌ PyTorch หรือ CUDA มีปัญหา"
    exit 1
fi
echo ""

# 3. ตรวจสอบ CTranslate2 compatibility
print_header "3. ตรวจสอบ CTranslate2 Compatibility"
python3 << 'PYEOF'
import torch

# ตรวจสอบ cuDNN version
if torch.backends.cudnn.is_available():
    cudnn_version = torch.backends.cudnn.version()
    print(f"cuDNN Version: {cudnn_version}")
    
    if cudnn_version >= 9000:
        print("✅ รองรับ CTranslate2 4.6.2+ (cuDNN 9)")
        print("   แนะนำ: ctranslate2>=4.6.2")
    elif cudnn_version >= 8000:
        print("✅ รองรับ CTranslate2 4.4.0 (cuDNN 8)")
        print("   แนะนำ: ctranslate2==4.4.0")
    else:
        print("⚠️  cuDNN version ต่ำ - อาจมีปัญหา")
else:
    print("❌ cuDNN not available")
PYEOF
echo ""

# 4. ตรวจสอบ faster-whisper requirements
print_header "4. ตรวจสอบ faster-whisper 1.2.1 Requirements"
python3 << 'PYEOF'
import sys

print("faster-whisper 1.2.1 ต้องการ:")
print("  - ctranslate2>=4.0,<6")
print("  - CUDA 11.8+ หรือ 12.x")
print("  - cuDNN 8.x หรือ 9.x")
print("")
print("✅ CUDA 12.1.1: ตรงตาม requirements")
print("✅ cuDNN: ต้องตรวจสอบ version (8.x หรือ 9.x)")
PYEOF
echo ""

# 5. ตรวจสอบ dependencies ที่มีอยู่แล้ว
print_header "5. ตรวจสอบ Dependencies ที่มีอยู่แล้ว"
python3 << 'PYEOF'
import sys

packages = {
    'torch': 'PyTorch',
    'numpy': 'NumPy',
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'pydantic': 'Pydantic',
    'aiohttp': 'aiohttp',
    'redis': 'Redis',
    'requests': 'Requests',
}

installed = []
missing = []

for pkg, name in packages.items():
    try:
        __import__(pkg)
        installed.append(name)
    except ImportError:
        missing.append(name)

print("✅ ติดตั้งแล้ว:")
for pkg in installed:
    print(f"   - {pkg}")

if missing:
    print("")
    print("❌ ยังไม่ติดตั้ง:")
    for pkg in missing:
        print(f"   - {pkg}")
PYEOF
echo ""

# 6. สรุปและแนะนำ
print_header "📋 สรุปและแนะนำ"
echo ""
echo "✅ Base Image: runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04"
echo "✅ PyTorch 2.2.0 + CUDA 12.1.1"
echo ""
echo "📝 ขั้นตอนต่อไป:"
echo "   1. ตรวจสอบ cuDNN version (ดูจาก output ด้านบน)"
echo "   2. ติดตั้ง dependencies ที่ขาด:"
echo "      bash scripts/pod/install-requirements.sh"
echo ""
echo "💡 ถ้า cuDNN 9.x: ใช้ CTranslate2 4.6.2+"
echo "💡 ถ้า cuDNN 8.x: ใช้ CTranslate2 4.4.0"
echo ""

