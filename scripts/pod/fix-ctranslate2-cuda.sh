#!/bin/bash
# Script สำหรับติดตั้ง CTranslate2 CUDA version แทน CPU-only

set -e

echo "🔧 Fixing CTranslate2 CUDA Support"
echo "=================================="
echo ""

# Detect CUDA version from PyTorch
echo "🔍 Detecting CUDA version..."
PYTORCH_CUDA=$(python3 -c "import torch; print(torch.version.cuda)" 2>/dev/null || echo "unknown")
echo "PyTorch CUDA Version: $PYTORCH_CUDA"

# Check if CUDA 11.8 or 12.x
if [[ "$PYTORCH_CUDA" == "11."* ]] || [[ "$PYTORCH_CUDA" == "11.8"* ]]; then
    CT2_PACKAGE="ctranslate2-cuda11"
    echo "✅ Detected CUDA 11.x - will install ctranslate2-cuda11"
elif [[ "$PYTORCH_CUDA" == "12."* ]]; then
    CT2_PACKAGE="ctranslate2-cuda12"
    echo "✅ Detected CUDA 12.x - will install ctranslate2-cuda12"
else
    echo "⚠️  Unknown CUDA version, trying ctranslate2-cuda12 (default for newer versions)"
    CT2_PACKAGE="ctranslate2-cuda12"
fi

echo ""
echo "📦 Uninstalling CPU-only ctranslate2..."
pip uninstall -y ctranslate2 2>/dev/null || echo "ctranslate2 not installed"

echo ""
echo "📦 Installing $CT2_PACKAGE..."
pip install --no-cache-dir "$CT2_PACKAGE"

echo ""
echo "✅ Installation completed!"
echo ""
echo "🧪 Testing installation..."
python3 << 'PYTHON'
try:
    from faster_whisper import WhisperModel
    print("Testing WhisperModel initialization...")
    model = WhisperModel('tiny', device='cuda', compute_type='float16')
    print("✅ Model initialized successfully!")
    print(f"Model device: {getattr(model, 'device', 'N/A')}")
    if hasattr(model, 'model'):
        print(f"CTranslate2 device: {getattr(model.model, 'device', 'N/A')}")
    print("✅ CTranslate2 CUDA support is working!")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYTHON

echo ""
echo "✅ Fix completed!"
