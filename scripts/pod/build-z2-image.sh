#!/bin/bash
# Script สำหรับ Build Docker Image สำหรับ HP Z2 Workstation
#
# ใช้ข้อมูลจาก Environment ที่ทำงานได้บน RunPod
# ไปสร้าง Image สำหรับ Z2
#
# วิธีใช้งาน:
#   bash scripts/pod/build-z2-image.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔨 Building Docker Image สำหรับ HP Z2 Workstation"
echo "📁 Project Root: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

# ตรวจสอบว่ามี Dockerfile.z2-base หรือไม่
if [ ! -f "Dockerfile.z2-base" ]; then
    echo "❌ Error: ไม่พบ Dockerfile.z2-base"
    echo "   ต้องสร้าง Dockerfile.z2-base ก่อน"
    exit 1
fi

# Build image
echo "📦 Building image..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "⚠️  Detected ARM64 architecture, using --platform=linux/amd64"
    docker build --platform=linux/amd64 -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .
else
    docker build -f Dockerfile.z2-base -t kk-transcription-z2-base:latest .
fi

# Tag as version
VERSION=$(date +%Y%m%d-%H%M%S)
docker tag kk-transcription-z2-base:latest kk-transcription-z2-base:$VERSION

echo ""
echo "✅ Build completed!"
echo ""
echo "📋 Image tags:"
echo "   - kk-transcription-z2-base:latest"
echo "   - kk-transcription-z2-base:$VERSION"
echo ""
echo "🚀 วิธีใช้งานบน Z2:"
echo ""
echo "   1. Load image (ถ้า build ที่อื่น):"
echo "      docker load < kk-transcription-z2-base.tar"
echo ""
echo "   2. Run container:"
echo "      docker run --gpus all -it \\"
echo "          -v /path/to/workspace:/workspace \\"
echo "          kk-transcription-z2-base:latest"
echo ""
echo "   3. Clone repository:"
echo "      cd /workspace"
echo "      git clone <repo-url> transcription-service"
echo ""
echo "   4. Setup GPU environment:"
echo "      cd transcription-service"
echo "      source scripts/pod/setup-gpu-env.sh"
echo ""
echo "   5. Test GPU transcription:"
echo "      python3 scripts/pod/test-faster-whisper-gpu.py"
echo ""

