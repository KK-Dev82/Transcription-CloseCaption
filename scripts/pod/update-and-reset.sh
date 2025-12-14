#!/bin/bash
# Update Code and Reset Database Script
# Pull code จาก git และ reset database

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "🔄 Update Code and Reset Database"
echo "=========================================="
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
"$SCRIPT_DIR/reset-database.sh"
echo ""

# Step 3: Restart service
echo "🔄 Step 3: Restarting service..."
if [ -f "$SCRIPT_DIR/start-service-daemon.sh" ]; then
    echo "   ℹ️  Please run the following command to restart service:"
    echo "      ./scripts/pod/start-service-daemon.sh"
else
    echo "   ⚠️  start-service-daemon.sh not found"
fi
echo ""

echo "=========================================="
echo "✅ Update and reset completed!"
echo "=========================================="

