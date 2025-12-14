#!/bin/bash
# Remote Fix Script - Execute fix commands on Pod via SSH
# Usage: 
#   bash scripts/pod/remote-fix.sh [ssh-host]
#   bash scripts/pod/remote-fix.sh pytorch-pod
#   bash scripts/pod/remote-fix.sh root@80.15.7.37:41475

set -e

# Get SSH host from argument or environment
SSH_HOST="${1:-${RUNPOD_HOST:-pytorch-pod}}"

echo "=========================================="
echo "🔧 Remote Fix: Pull, Reset, Restart"
echo "=========================================="
echo "SSH Host: $SSH_HOST"
echo ""

# Check if SSH host is provided
if [ -z "$SSH_HOST" ]; then
    echo "❌ Error: SSH host not specified"
    echo ""
    echo "Usage:"
    echo "  bash scripts/pod/remote-fix.sh [ssh-host]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/pod/remote-fix.sh pytorch-pod"
    echo "  bash scripts/pod/remote-fix.sh root@80.15.7.37 -p 41475"
    echo ""
    exit 1
fi

echo "📡 Connecting to $SSH_HOST..."
echo ""

# Execute commands on remote server
ssh "$SSH_HOST" << 'REMOTE_SCRIPT'
set -e

PROJECT_ROOT="/workspace/transcription-service"

echo "📁 Changing to project directory..."
cd "$PROJECT_ROOT" || { echo "❌ Project directory not found"; exit 1; }
echo "   ✅ Current directory: $(pwd)"
echo ""

# Step 1: Pull code
echo "📥 Step 1: Pulling code from git..."
if git pull; then
    echo "   ✅ Code updated successfully"
else
    echo "   ⚠️  Git pull failed or no changes"
fi
echo ""

# Step 2: Reset database
echo "🗑️  Step 2: Resetting database..."
DB_PATH="${SQLITE_DB_PATH:-$PROJECT_ROOT/storage/database.db}"

if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "   📊 Database found: $DB_PATH (Size: $DB_SIZE)"
    echo "   🗑️  Removing database..."
    rm -f "$DB_PATH"
    rm -f "${DB_PATH}-journal"
    rm -f "${DB_PATH}-wal"
    rm -f "${DB_PATH}-shm"
    echo "   ✅ Database removed"
else
    echo "   ℹ️  Database does not exist (will be created on start)"
fi
echo ""

# Step 3: Stop existing service
echo "🛑 Step 3: Stopping existing service..."
PID_FILE="$PROJECT_ROOT/logs/service.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "   Stopping service (PID: $PID)..."
        kill "$PID" 2>/dev/null || true
        sleep 2
        echo "   ✅ Service stopped"
    else
        echo "   ℹ️  Service not running (PID file exists but process not found)"
    fi
else
    echo "   ℹ️  No PID file found"
    # Try to find and kill uvicorn process
    if pgrep -f "uvicorn.*app.main:app" > /dev/null; then
        echo "   Found uvicorn process, stopping..."
        pkill -f "uvicorn.*app.main:app" || true
        sleep 2
        echo "   ✅ Uvicorn processes stopped"
    fi
fi
echo ""

# Step 4: Restart service
echo "🚀 Step 4: Restarting service..."
if [ -f "$PROJECT_ROOT/scripts/pod/start-service-daemon.sh" ]; then
    bash "$PROJECT_ROOT/scripts/pod/start-service-daemon.sh"
    echo "   ✅ Service restart command executed"
else
    echo "   ❌ start-service-daemon.sh not found"
    echo "   💡 Please run manually:"
    echo "      cd $PROJECT_ROOT"
    echo "      bash scripts/pod/start-service-daemon.sh"
fi
echo ""

echo "=========================================="
echo "✅ Remote fix completed!"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo "   1. Check service status:"
echo "      ssh $SSH_HOST 'curl http://localhost:8010/health'"
echo ""
echo "   2. Check logs:"
echo "      ssh $SSH_HOST 'tail -f $PROJECT_ROOT/logs/app.log'"
echo ""

REMOTE_SCRIPT

echo ""
echo "✅ All commands executed successfully!"

