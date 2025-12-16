#!/bin/bash
# Script สำหรับแก้ไข CTranslate2 cuDNN compatibility issue
# Downgrade CTranslate2 จาก 4.6.2 เป็น 4.4.0 เพื่อรองรับ cuDNN 8

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "🔧 Fixing CTranslate2 cuDNN 8 Compatibility"

# Check current versions
echo "🔍 Checking current versions..."
CURRENT_CT2=$(python3 -c "import ctranslate2; print(ctranslate2.__version__)" 2>/dev/null || echo "not installed")
CURRENT_CUDA=$(python3 -c "import torch; print(torch.version.cuda)" 2>/dev/null || echo "unknown")
CURRENT_CUDNN=$(python3 -c "import torch; print(torch.backends.cudnn.version())" 2>/dev/null || echo "unknown")

echo "   Current CTranslate2: $CURRENT_CT2"
echo "   Current CUDA (PyTorch): $CURRENT_CUDA"
echo "   Current cuDNN: $CURRENT_CUDNN"
echo ""

# Check if downgrade is needed
if [[ "$CURRENT_CT2" == "4.6."* ]] || [[ "$CURRENT_CT2" == "4.5."* ]]; then
    print_warning "CTranslate2 $CURRENT_CT2 requires cuDNN 9, but system has cuDNN 8"
    print_warning "Downgrading to CTranslate2 4.4.0 (supports cuDNN 8)..."
    echo ""
    
    # Uninstall current version
    print_warning "Uninstalling CTranslate2 $CURRENT_CT2..."
    pip uninstall -y ctranslate2 2>/dev/null || true
    
    # Install compatible version
    print_warning "Installing CTranslate2 4.4.0 (cuDNN 8 compatible)..."
    pip install --no-cache-dir "ctranslate2==4.4.0" || {
        print_error "Failed to install CTranslate2 4.4.0"
        exit 1
    }
    
    print_success "CTranslate2 downgraded to 4.4.0"
else
    print_success "CTranslate2 version is compatible (current: $CURRENT_CT2)"
fi

echo ""
print_header "🧪 Testing CTranslate2 Compatibility"

# Test installation
python3 << 'PYTHON'
try:
    import ctranslate2
    print(f"✅ CTranslate2 version: {ctranslate2.__version__}")
    print(f"   CUDA available: {ctranslate2.get_cuda_device_count() > 0}")
    if ctranslate2.get_cuda_device_count() > 0:
        print(f"   CUDA device count: {ctranslate2.get_cuda_device_count()}")
    
    # Test model initialization
    from faster_whisper import WhisperModel
    print("\n🔍 Testing WhisperModel initialization...")
    model = WhisperModel('tiny', device='cuda', compute_type='float16')
    print("✅ Model initialized successfully!")
    print(f"   Model device: {getattr(model, 'device', 'N/A')}")
    if hasattr(model, 'model'):
        print(f"   CTranslate2 device: {getattr(model.model, 'device', 'N/A')}")
    print("✅ CTranslate2 cuDNN 8 compatibility test passed!")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON

echo ""
print_success "Fix completed! CTranslate2 is now compatible with cuDNN 8"
print_warning "Please restart Video Worker to apply changes"

