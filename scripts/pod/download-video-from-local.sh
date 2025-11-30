#!/bin/bash
# Script สำหรับ Download Video จาก Local Machine (MacOS) ไปยัง Pod
# ใช้ SCP เพื่อ copy ไฟล์ผ่าน SSH
#
# วิธีใช้งาน:
# bash scripts/pod/download-video-from-local.sh <local-file> <pod-ip> [pod-ssh-port] [destination-dir]
#
# ตัวอย่าง:
# bash scripts/pod/download-video-from-local.sh /path/to/video.mp4 205.196.17.108 13027 uploads/

set -e

LOCAL_FILE="${1}"
POD_IP="${2}"
POD_SSH_PORT="${3:-13027}"
DEST_DIR="${4:-uploads}"

if [ -z "$LOCAL_FILE" ] || [ -z "$POD_IP" ]; then
    echo "❌ Error: Local file and Pod IP are required"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/download-video-from-local.sh <local-file> <pod-ip> [pod-ssh-port] [destination-dir]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/download-video-from-local.sh /path/to/video.mp4 205.196.17.108"
    echo "  bash scripts/pod/download-video-from-local.sh /path/to/video.mp4 205.196.17.108 13027 uploads/"
    echo ""
    exit 1
fi

# Check if file exists
if [ ! -f "$LOCAL_FILE" ]; then
    echo "❌ Error: Local file not found: $LOCAL_FILE"
    exit 1
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "📤 Uploading Video to Pod"
echo "📅 $(date)"
echo ""
echo "📋 Configuration:"
echo "   Local File: $LOCAL_FILE"
echo "   Pod IP: $POD_IP"
echo "   SSH Port: $POD_SSH_PORT"
echo "   Destination: /workspace/transcription-service/$DEST_DIR"
echo ""

# Get file info
FILE_SIZE=$(du -h "$LOCAL_FILE" | cut -f1)
FILENAME=$(basename "$LOCAL_FILE")

print_status "File Information:"
echo "   Name: $FILENAME"
echo "   Size: $FILE_SIZE"
echo ""

# Check SSH connection
print_status "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p "$POD_SSH_PORT" root@"$POD_IP" "echo 'SSH connection OK'" 2>/dev/null; then
    print_error "❌ Cannot connect to Pod via SSH"
    echo ""
    print_status "💡 Please check:"
    echo "   1. Pod is running"
    echo "   2. SSH port is correct: $POD_SSH_PORT"
    echo "   3. SSH key is configured (or use password)"
    exit 1
fi
print_success "✅ SSH connection OK"
echo ""

# Create destination directory on Pod
print_status "Creating destination directory on Pod..."
ssh -p "$POD_SSH_PORT" root@"$POD_IP" "mkdir -p /workspace/transcription-service/$DEST_DIR" || {
    print_error "❌ Failed to create destination directory"
    exit 1
}
print_success "✅ Destination directory created"
echo ""

# Upload file using SCP
print_status "Uploading file..."
DEST_PATH="/workspace/transcription-service/$DEST_DIR/$FILENAME"

scp -P "$POD_SSH_PORT" "$LOCAL_FILE" root@"$POD_IP:$DEST_PATH" || {
    print_error "❌ Upload failed"
    exit 1
}

print_success "✅ File uploaded: $DEST_PATH"
echo ""

# Set permissions on Pod
print_status "Setting permissions..."
ssh -p "$POD_SSH_PORT" root@"$POD_IP" "chmod 644 $DEST_PATH" || {
    print_warning "⚠️  Failed to set permissions (may need manual fix)"
}

# Verify file on Pod
print_status "Verifying file on Pod..."
REMOTE_SIZE=$(ssh -p "$POD_SSH_PORT" root@"$POD_IP" "stat -c%s $DEST_PATH 2>/dev/null || stat -f%z $DEST_PATH 2>/dev/null || echo '0'")
LOCAL_SIZE=$(stat -c%s "$LOCAL_FILE" 2>/dev/null || stat -f%z "$LOCAL_FILE" 2>/dev/null || echo "0")

if [ "$REMOTE_SIZE" = "$LOCAL_SIZE" ] && [ "$REMOTE_SIZE" != "0" ]; then
    print_success "✅ File verified: $REMOTE_SIZE bytes"
else
    print_warning "⚠️  File size mismatch: Local=$LOCAL_SIZE, Remote=$REMOTE_SIZE"
fi

echo ""
print_success "🎉 Upload completed!"
echo ""
print_status "💡 Next steps (on Pod):"
echo "   # SSH to Pod"
echo "   ssh root@$POD_IP -p $POD_SSH_PORT"
echo ""
echo "   # Test transcription"
echo "   cd /workspace/transcription-service"
echo "   bash scripts/pod/test-transcription-performance.sh $DEST_PATH medium"
echo ""

