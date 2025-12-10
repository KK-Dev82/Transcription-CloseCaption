#!/bin/bash
# Script สำหรับตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN libraries

set -e

echo "🔧 Setting up cuDNN Library Path"
echo "================================="
echo ""

# Get Python site-packages path
PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/usr/local/lib/python3.10/dist-packages")
CUDNN_LIB_PATH="$PYTHON_SITE/nvidia/cudnn/lib"

if [ -d "$CUDNN_LIB_PATH" ]; then
    echo "✅ Found cuDNN libraries at: $CUDNN_LIB_PATH"
    
    # Export LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$LD_LIBRARY_PATH"
    
    # Also add CUDA libs if they exist
    if [ -d "/usr/local/cuda/lib64" ]; then
        export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"
    fi
    if [ -d "/usr/local/cuda-11.8/lib64" ]; then
        export LD_LIBRARY_PATH="/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH"
    fi
    
    echo "✅ LD_LIBRARY_PATH set to: $LD_LIBRARY_PATH"
    
    # Save to file for sourcing
    echo "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH\"" > /tmp/cudnn-env.sh
    chmod +x /tmp/cudnn-env.sh
    
    echo ""
    echo "✅ cuDNN path setup complete!"
    echo "   Source this file: source /tmp/cudnn-env.sh"
else
    echo "❌ cuDNN libraries not found at: $CUDNN_LIB_PATH"
    exit 1
fi
