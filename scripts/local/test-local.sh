#!/bin/bash
# Script สำหรับ Test Transcription บน Local Docker
# Usage: bash scripts/local/test-local.sh [video_file] [model] [chunk_duration]
# Example: bash scripts/local/test-local.sh uploads/test.mp4 base 30

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

VIDEO_FILE=${1:-uploads/test.mp4}
MODEL=${2:-base}
# Note: test-transcription.sh accepts: [video-file] [model-size] [api-url]
# CHUNK_DURATION is not supported in test-transcription.sh yet
API_URL=${3:-http://localhost:8001}

# Check if container exists
if ! docker ps | grep -q transcription-local-base; then
    print_error "❌ Container is not running"
    echo ""
    echo "Start container with:"
    echo "   bash scripts/local/start-local.sh"
    exit 1
fi

# Check if video file exists (on host)
if [ ! -f "$VIDEO_FILE" ]; then
    print_error "❌ Video file not found: $VIDEO_FILE"
    echo ""
    echo "Available files in uploads/:"
    ls -lh uploads/ 2>/dev/null || echo "  (empty)"
    exit 1
fi

print_header "🧪 Testing Transcription on Local Docker"
echo ""
print_status "Video: $VIDEO_FILE"
print_status "Model: $MODEL"
print_status "API URL: $API_URL"
echo ""

# Run test inside container
print_status "Running test inside container..."
docker exec transcription-local-base bash -c "
    cd /workspace/transcription-service && \
    bash scripts/pod/test-transcription.sh $VIDEO_FILE $MODEL $API_URL
"

echo ""
print_success "✅ Test completed!"
echo ""
print_status "💡 View results:"
echo "   docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/result-view.sh -detail 5'"

