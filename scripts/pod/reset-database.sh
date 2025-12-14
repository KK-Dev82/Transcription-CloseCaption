#!/bin/bash
# Reset SQLite Database Script
# ลบ database เก่าและเริ่มใหม่ (ไม่เก็บข้อมูลเก่า)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Database path
DB_PATH="${SQLITE_DB_PATH:-$PROJECT_ROOT/storage/database.db}"
STORAGE_DIR="${JSON_STORAGE_DIR:-$PROJECT_ROOT/storage}"

echo "=========================================="
echo "🗑️  Reset SQLite Database"
echo "=========================================="
echo ""

# Check if database exists
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "📊 Database found: $DB_PATH"
    echo "   Size: $DB_SIZE"
    echo ""
    
    read -p "⚠️  คุณแน่ใจหรือไม่ว่าต้องการลบ database นี้? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ ยกเลิกการลบ database"
        exit 1
    fi
    
    # Backup database (optional)
    BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 Creating backup: $BACKUP_PATH"
    cp "$DB_PATH" "$BACKUP_PATH"
    echo "   ✅ Backup created"
    echo ""
    
    # Remove database
    echo "🗑️  Removing database..."
    rm -f "$DB_PATH"
    echo "   ✅ Database removed"
    echo ""
else
    echo "ℹ️  Database does not exist: $DB_PATH"
    echo "   Will be created automatically when service starts"
    echo ""
fi

# Remove database journal files
echo "🧹 Cleaning up database journal files..."
rm -f "${DB_PATH}-journal"
rm -f "${DB_PATH}-wal"
rm -f "${DB_PATH}-shm"
echo "   ✅ Journal files cleaned"
echo ""

# Optionally remove old JSON storage (if exists)
if [ -d "$STORAGE_DIR/transcriptions" ]; then
    JSON_COUNT=$(find "$STORAGE_DIR/transcriptions" -type f -name "*.json" 2>/dev/null | wc -l)
    if [ "$JSON_COUNT" -gt 0 ]; then
        echo "📁 Found $JSON_COUNT JSON files in old storage"
        read -p "⚠️  ลบ JSON storage เก่าด้วยหรือไม่? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Removing old JSON storage..."
            rm -rf "$STORAGE_DIR/transcriptions"
            echo "   ✅ JSON storage removed"
        else
            echo "   ℹ️  Keeping JSON storage"
        fi
        echo ""
    fi
fi

echo "=========================================="
echo "✅ Database reset completed!"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo "   1. Restart the service:"
echo "      ./scripts/pod/start-service-daemon.sh"
echo ""
echo "   2. The service will create a new database automatically"
echo "      with the correct schema"
echo ""

