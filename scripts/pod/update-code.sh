#!/bin/bash
# Script สำหรับอัปเดต code บน RunPod Pod Server
#
# วิธีใช้งาน:
#   bash scripts/pod/update-code.sh [branch-name]
#
# ตัวอย่าง:
#   bash scripts/pod/update-code.sh staging
#   bash scripts/pod/update-code.sh main

set -e

REPO_DIR="/workspace/transcription-service"
BRANCH="${1:-staging}"  # Default: staging

echo "🔄 Updating code on RunPod Pod Server..."
echo "📅 $(date)"
echo ""

# Check if repository exists
if [ ! -d "$REPO_DIR" ]; then
    echo "❌ Repository not found at $REPO_DIR"
    echo "💡 Please clone repository first:"
    echo "   cd /workspace"
    echo "   git clone <repo-url> transcription-service"
    exit 1
fi

cd "$REPO_DIR"

# Stop services
echo "🛑 Stopping services..."
pkill -f "python.*uvicorn.*app.main" || echo "⚠️  No Main API process found"
pkill -f "python.*whisper_api" || echo "⚠️  No Whisper API process found"
pkill -f "python.*video_worker" || echo "⚠️  No Video Worker process found"
pkill -f redis-server || echo "⚠️  No Redis process found"
sleep 2
echo "✅ Services stopped"
echo ""

# Backup and handle .env.runpod (untracked file conflict)
ENV_BACKUP_MOVED=false
if [ -f ".env.runpod" ]; then
    echo "💾 Backing up .env.runpod..."
    cp .env.runpod /tmp/.env.runpod.backup
    cp .env.runpod /workspace/.env.runpod.backup 2>/dev/null || true
    echo "✅ Backup created"
    
    # Check if .env.runpod is untracked (would cause git pull to fail)
    if ! git ls-files --error-unmatch .env.runpod > /dev/null 2>&1; then
        echo "⚠️  .env.runpod is untracked (may conflict with git pull)"
        echo "📦 Temporarily moving .env.runpod to avoid merge conflict..."
        mv .env.runpod .env.runpod.tmp
        ENV_BACKUP_MOVED=true
        echo "✅ Moved to .env.runpod.tmp"
    fi
else
    echo "⚠️  .env.runpod not found (will be created by start script)"
fi
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "📋 Current branch: $CURRENT_BRANCH"
echo "📋 Target branch: $BRANCH"
echo ""

# Switch branch (ถ้าต้องการ)
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "🔄 Switching to branch: $BRANCH"
    git fetch origin "$BRANCH" || {
        echo "⚠️  Failed to fetch branch. Continuing with current branch..."
    }
    git checkout "$BRANCH" || {
        echo "⚠️  Failed to switch branch. Continuing with current branch..."
    }
    echo "✅ Switched to branch: $BRANCH"
else
    echo "✅ Already on branch: $BRANCH"
fi
echo ""

# Pull latest changes
echo "📥 Pulling latest changes from origin/$BRANCH..."
git pull origin "$BRANCH" || {
    echo "❌ Failed to pull changes"
    echo "💡 Try: git fetch origin && git pull origin $BRANCH"
    exit 1
}
echo "✅ Code updated"
echo ""

# Check if requirements.txt changed
if git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -q "requirements.txt"; then
    echo "📦 requirements.txt changed, reinstalling dependencies..."
    pip3 install --no-cache-dir -r requirements.txt || {
        echo "⚠️  Some packages failed to install. Continuing..."
    }
    echo "✅ Dependencies reinstalled"
else
    echo "📦 requirements.txt unchanged, skipping dependency reinstall"
fi
echo ""

# Restore .env.runpod
if [ "$ENV_BACKUP_MOVED" = true ] && [ -f ".env.runpod.tmp" ]; then
    echo "📝 Restoring .env.runpod from temporary backup..."
    mv .env.runpod.tmp .env.runpod
    echo "✅ .env.runpod restored"
elif [ ! -f ".env.runpod" ] && [ -f "/tmp/.env.runpod.backup" ]; then
    echo "📝 Restoring .env.runpod from backup..."
    cp /tmp/.env.runpod.backup .env.runpod
    echo "✅ .env.runpod restored"
fi

# Ensure RabbitMQ config is correct
if [ -f ".env.runpod" ]; then
    if grep -q "RABBITMQ_HOST=localhost" .env.runpod; then
        echo "🔧 Auto-updating RabbitMQ configuration..."
        sed -i 's/RABBITMQ_HOST=localhost/RABBITMQ_HOST=178.128.105.100/g' .env.runpod
        echo "✅ Updated RABBITMQ_HOST to 178.128.105.100"
    fi
fi
echo ""

# Start services
echo "🚀 Starting services..."
bash scripts/pod/start-services-direct.sh

