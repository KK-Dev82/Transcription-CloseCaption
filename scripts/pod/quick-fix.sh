#!/bin/bash
# Quick Fix Script - Pull code, reset database, restart service
# ใช้เมื่อต้องการ fix ปัญหา HTTP 500 หรือ database issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "🔧 Quick Fix: Pull, Reset, Restart"
echo "=========================================="
echo ""

# Step 1: Pull code
echo "📥 Step 1: Pulling code..."
if git pull; then
    echo "   ✅ Code updated"
else
    echo "   ⚠️  Git pull failed (continuing anyway...)"
fi
echo ""

# Step 2: Reset database (no backup, fresh start)
echo "🗑️  Step 2: Resetting database..."
DB_PATH="${SQLITE_DB_PATH:-$PROJECT_ROOT/storage/database.db}"

if [ -f "$DB_PATH" ]; then
    echo "   Removing database: $DB_PATH"
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
if [ -f "$PROJECT_ROOT/logs/service.pid" ]; then
    PID=$(cat "$PROJECT_ROOT/logs/service.pid" 2>/dev/null || echo "")
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "   Stopping service (PID: $PID)..."
        kill "$PID" 2>/dev/null || true
        sleep 2
        echo "   ✅ Service stopped"
    else
        echo "   ℹ️  Service not running"
    fi
else
    echo "   ℹ️  No PID file found"
fi
echo ""

# Step 4: Restart service
echo "🚀 Step 4: Restarting service..."
"$SCRIPT_DIR/start-service-daemon.sh"
echo ""

echo "=========================================="
echo "✅ Quick fix completed!"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo "   1. Check service status:"
echo "      curl http://localhost:8010/health"
echo ""
echo "   2. Check logs:"
echo "      tail -f logs/app.log"
echo ""

