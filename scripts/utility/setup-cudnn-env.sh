#!/bin/bash
# Setup cuDNN environment variables

export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/local/lib/python3.10/dist-packages/ctranslate2.libs:${LD_LIBRARY_PATH}

# Update library cache
ldconfig 2>/dev/null || true

echo "✅ cuDNN environment setup complete"
echo "   LD_LIBRARY_PATH includes cuDNN libraries"

