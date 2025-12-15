#!/bin/bash
# Remote Test Script - Run this from local machine
# This script will SSH to server and run FFmpeg tests

SSH_HOST="4000-ada-sc"
SSH_PORT="13263"
PROJECT_DIR="/workspace/transcription-service"

echo "🔍 Testing FFmpeg Installation on Remote Server"
echo "================================================"
echo ""

# Test SSH connection
echo "Testing SSH connection..."
if ssh -p "$SSH_PORT" -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" "echo 'SSH OK'" > /dev/null 2>&1; then
    echo "✅ SSH connection OK"
else
    echo "❌ SSH connection failed"
    exit 1
fi

# Pull latest changes
echo ""
echo "Pulling latest changes..."
ssh -p "$SSH_PORT" "$SSH_HOST" "cd $PROJECT_DIR && git pull origin staging" 2>&1 | tail -3

# Run simple test
echo ""
echo "Running FFmpeg test..."
ssh -p "$SSH_PORT" "$SSH_HOST" "cd $PROJECT_DIR && bash scripts/pod/test-ffmpeg-simple.sh" 2>&1

# Get results from log file
echo ""
echo "=== Test Results from Log File ==="
ssh -p "$SSH_PORT" "$SSH_HOST" "cat $PROJECT_DIR/logs/ffmpeg-test-simple.log 2>/dev/null || echo 'Log file not found'"

