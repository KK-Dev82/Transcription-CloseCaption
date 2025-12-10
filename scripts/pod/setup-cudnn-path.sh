#!/bin/bash
# Script สำหรับตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN libraries

set -e

echo "🔧 Setting up cuDNN Library Path"
echo "================================="
echo ""

# Get Python site-packages path (both system and /workspace/.local)
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.10")
PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "/usr/local/lib/python3.10/dist-packages")
WORKSPACE_LOCAL="/workspace/.local/lib/python${PYTHON_VERSION}/site-packages"

CUDNN_LIB_PATH="$PYTHON_SITE/nvidia/cudnn/lib"
TORCH_LIB_PATH="$PYTHON_SITE/torch/lib"
WORKSPACE_CUDNN_LIB_PATH="$WORKSPACE_LOCAL/nvidia/cudnn/lib"
WORKSPACE_TORCH_LIB_PATH="$WORKSPACE_LOCAL/torch/lib"

# Initialize LD_LIBRARY_PATH
NEW_LD_LIBRARY_PATH=""

# Priority 1: Add /workspace/.local/torch/lib first (persistent, contains cuDNN so.8 files)
if [ -d "$WORKSPACE_TORCH_LIB_PATH" ]; then
    echo "✅ Found PyTorch cuDNN libraries (persistent) at: $WORKSPACE_TORCH_LIB_PATH"
    NEW_LD_LIBRARY_PATH="$WORKSPACE_TORCH_LIB_PATH"
fi

# Priority 2: Add system torch/lib (contains cuDNN so.8 files)
if [ -d "$TORCH_LIB_PATH" ]; then
    echo "✅ Found PyTorch cuDNN libraries (system) at: $TORCH_LIB_PATH"
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$TORCH_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$TORCH_LIB_PATH"
    fi
fi

# Priority 3: Add /workspace/.local/nvidia/cudnn/lib (persistent, contains cuDNN so.9 files)
if [ -d "$WORKSPACE_CUDNN_LIB_PATH" ]; then
    echo "✅ Found nvidia cuDNN libraries (persistent) at: $WORKSPACE_CUDNN_LIB_PATH"
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$WORKSPACE_CUDNN_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$WORKSPACE_CUDNN_LIB_PATH"
    fi
fi

# Priority 4: Add system nvidia/cudnn/lib (contains cuDNN so.9 files)
if [ -d "$CUDNN_LIB_PATH" ]; then
    echo "✅ Found nvidia cuDNN libraries (system) at: $CUDNN_LIB_PATH"
    if [ -n "$NEW_LD_LIBRARY_PATH" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$CUDNN_LIB_PATH"
    else
        NEW_LD_LIBRARY_PATH="$CUDNN_LIB_PATH"
    fi
fi

# Also add CUDA libs if they exist (check both system and common locations)
for CUDA_DIR in "/usr/local/cuda-12.4/lib64" "/usr/local/cuda-12/lib64" "/usr/local/cuda/lib64" "/usr/local/cuda-11.8/lib64"; do
    if [ -d "$CUDA_DIR" ]; then
        NEW_LD_LIBRARY_PATH="$NEW_LD_LIBRARY_PATH:$CUDA_DIR"
        echo "✅ Added CUDA libraries: $CUDA_DIR"
    fi
done

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
