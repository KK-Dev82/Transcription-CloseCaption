#!/bin/bash
# Tool สำหรับ Download Models และ Videos (Optional)
#
# วิธีใช้งาน:
#   bash scripts/pod/download-tool.sh model <model-size>          # Download model
#   bash scripts/pod/download-tool.sh video <url-or-path> [dest]  # Download video

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

TYPE="${1}"
ARG="${2}"
DEST="${3}"

if [ -z "$TYPE" ] || [ -z "$ARG" ]; then
    echo "❌ Error: Type and argument required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/download-tool.sh model <model-size>"
    echo "  bash scripts/pod/download-tool.sh video <url-or-path> [destination]"
    echo ""
    echo "Examples:"
    echo "  # Download model"
    echo "  bash scripts/pod/download-tool.sh model medium"
    echo "  bash scripts/pod/download-tool.sh model large-v3"
    echo ""
    echo "  # Download video"
    echo "  bash scripts/pod/download-tool.sh video https://example.com/video.mp4"
    echo "  bash scripts/pod/download-tool.sh video /tmp/video.mp4 uploads/"
    echo ""
    echo "Model sizes: base, small, medium, large, large-v2, large-v3"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

case "$TYPE" in
    model)
        print_status "Downloading Whisper model: $ARG"
        if [ -f "scripts/utility/download-models.sh" ]; then
            bash scripts/utility/download-models.sh "$ARG" --skip-restart
        else
            print_error "❌ download-models.sh not found"
            exit 1
        fi
        ;;
    
    video)
        print_status "Downloading/Copying video: $ARG"
        if [ -f "scripts/pod/download-video.sh" ]; then
            if [ -n "$DEST" ]; then
                bash scripts/pod/download-video.sh "$ARG" "$DEST"
            else
                bash scripts/pod/download-video.sh "$ARG" "uploads"
            fi
        else
            print_error "❌ download-video.sh not found"
            exit 1
        fi
        ;;
    
    *)
        print_error "❌ Unknown type: $TYPE"
        echo "   Use 'model' or 'video'"
        exit 1
        ;;
esac

echo ""
print_success "🎉 Download completed!"
echo ""

