#!/bin/bash
# Script สำหรับตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN libraries

set -e

echo "🔧 Setting up cuDNN Library Path"
echo "================================="
echo ""

# Get Python site-packages path
PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/usr/local/lib/python3.10/dist-packages")
CUDNN_LIB_PATH="$PYTHON_SITE/nvidia/cudnn/lib"
TORCH_LIB_PATH="$PYTHON_SITE/torch/lib"

# Initialize LD_LIBRARY_PATH
NEW_LD_LIBRARY_PATH=""

# Add torch/lib first (contains cuDNN so.8 files)
if [ -d "$TORCH_LIB_PATH" ]; then
    echo "✅ Found PyTorch cuDNN libraries at: $TORCH_LIB_PATH"
    NEW_LD_LIBRARY_PATH="$TORCH_LIB_PATH"
fi

# Add nvidia/cudnn/lib (contains cuDNN so.9 files)
if [ -d "$CUDNN_LIB_PATH" ]; then
    echo "✅ Found nvidia cuDNN libraries at: $CUDNN_LIB_PATH"
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$CUDNN_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$CUDNN_LIB_PATH"
    fi
fi

# Also add CUDA libs if they exist
if [ -d "/usr/local/cuda/lib64" ]; then
    NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:/usr/local/cuda/lib64"
fi
if [ -d "/usr/local/cuda-11.8/lib64" ]; then
    NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:/usr/local/cuda-11.8/lib64"
fi

# Export LD_LIBRARY_PATH
if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
    export LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$LD_LIBRARY_PATH"
    
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
