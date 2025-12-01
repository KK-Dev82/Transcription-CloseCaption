#!/bin/bash
# Script สำหรับ Deploy และ Setup บน RunPod GPU Server
# Usage: bash scripts/pod/deploy-to-runpod.sh

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

# SSH Host (จาก ~/.ssh/config)
# ใช้ calm-pink-turtle หรือ runpod หรือ runpod-gpu
SSH_HOST="${RUNPOD_HOST:-calm-pink-turtle}"
PROJECT_DIR="/workspace/transcription-service"
POD_NAME="calm_pink_turtle"

print_status "🚀 Deploying to RunPod GPU Server"
print_status "Pod Name: $POD_NAME"
print_status "SSH Host: $SSH_HOST"
print_status "Project Directory: $PROJECT_DIR"
echo ""

# ตรวจสอบ SSH connection
print_status "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SSH_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    print_error "Cannot connect to $SSH_HOST"
    print_info "Please check:"
    print_info "  1. SSH config: ~/.ssh/config"
    print_info "  2. SSH key: ~/.ssh/id_ed25519"
    print_info "  3. RunPod Pod status"
    exit 1
fi
print_success "SSH connection OK"
echo ""

# ตรวจสอบว่า directory มีอยู่หรือไม่
print_status "Checking project directory..."
if ssh "$SSH_HOST" "[ -d '$PROJECT_DIR' ]"; then
    print_success "Project directory exists"
    print_status "Pulling latest changes..."
    ssh "$SSH_HOST" "cd $PROJECT_DIR && git pull"
else
    print_warning "Project directory not found"
    read -p "Clone repository? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Repository URL: " REPO_URL
        ssh "$SSH_HOST" "cd /workspace && git clone $REPO_URL transcription-service"
    else
        print_error "Cannot proceed without repository"
        exit 1
    fi
fi
echo ""

# Run setup script
print_status "Running setup script..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/setup-pod.sh"
echo ""

# ตรวจสอบ configuration
print_status "Checking configuration..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && cat .env.runpod | grep -E 'RABBITMQ_HOST|WHISPER_PROVIDER|WHISPER_USE_THREAD_LOCAL|TRANSCRIPTION_MAX_WORKERS'"
echo ""

# Restart services
print_status "Restarting services..."
read -p "Restart services? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/restart-pod.sh"
    print_success "Services restarted"
else
    print_info "Skipping service restart"
fi
echo ""

# ตรวจสอบ status
print_status "Checking service status..."
ssh "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/check-pod.sh"
echo ""

print_success "✅ Deployment completed!"
print_info "SSH to server: ssh $SSH_HOST"
print_info "View logs: ssh $SSH_HOST 'cd $PROJECT_DIR && tail -f /tmp/video-worker.log'"

