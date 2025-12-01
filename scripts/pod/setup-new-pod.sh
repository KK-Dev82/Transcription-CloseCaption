#!/bin/bash
# Script สำหรับ Setup Pod ใหม่ - Clone repo และ Setup ทุกอย่าง
#
# วิธีใช้งาน:
#   bash scripts/pod/setup-new-pod.sh

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
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
GIT_REPO="https://github.com/KK-Dev82/Transcription-CloseCaption.git"

echo "🚀 Setting Up New Pod"
echo "📅 $(date)"
echo ""

# ตรวจสอบ SSH connection
print_status "Checking SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    print_status "Please check SSH connection"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# Clone repo
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Step 1: Cloning Repository"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ssh "$SSH_HOST" "[ -d '$PROJECT_DIR' ]"; then
    print_warning "⚠️  Directory $PROJECT_DIR already exists"
    read -p "Remove and re-clone? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ssh "$SSH_HOST" "rm -rf $PROJECT_DIR"
        print_success "✅ Removed existing directory"
    else
        print_status "💡 Updating existing repository..."
        ssh "$SSH_HOST" "cd $PROJECT_DIR && git pull" || {
            print_error "❌ Failed to update repository"
            exit 1
        }
        print_success "✅ Repository updated"
    fi
fi

if ! ssh "$SSH_HOST" "[ -d '$PROJECT_DIR' ]"; then
    print_status "Cloning repository: $GIT_REPO"
    ssh "$SSH_HOST" "mkdir -p /workspace && cd /workspace && git clone $GIT_REPO transcription-service" || {
        print_error "❌ Failed to clone repository"
        exit 1
    }
    print_success "✅ Repository cloned"
else
    print_success "✅ Repository exists"
fi
echo ""

# Setup
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Step 2: Running Setup"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_status "Running setup-pod.sh..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/setup-pod.sh" || {
    print_error "❌ Setup failed"
    exit 1
}
print_success "✅ Setup completed"
echo ""

# Download Whisper model
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_status "Step 3: Downloading Whisper Model (medium)"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_status "Downloading medium model (this may take a while)..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && python3 -c 'import whisper; whisper.load_model(\"medium\")'" || {
    print_error "❌ Failed to download model"
    exit 1
}
print_success "✅ Model downloaded"
echo ""

# Summary
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_header "Setup Summary"
print_header "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

print_success "✅ Setup completed!"
echo ""
print_status "💡 Next steps:"
echo "   1. Download videos: bash scripts/pod/download-test-videos.sh"
echo "   2. Start services: bash scripts/pod/start-pod.sh"
echo "   3. Test transcription: bash scripts/pod/test-all-videos.sh"
echo ""

