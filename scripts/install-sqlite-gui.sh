#!/bin/bash
# Script สำหรับติดตั้ง SQLite GUI (phpLiteAdmin)
# ใช้งานผ่าน Web Browser

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
SQLITE_ADMIN_DIR="$DASHBOARD_DIR/sqlite_admin"
PHPLITEADMIN_URL="https://raw.githubusercontent.com/phpLiteAdmin/pla/master/phpliteadmin.php"

echo "🚀 Installing SQLite GUI (phpLiteAdmin)..."
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs root privileges to install PHP"
    echo "   Run with: sudo bash scripts/install-sqlite-gui.sh"
    exit 1
fi

# 1. Install PHP and SQLite extension
echo "📦 Installing PHP and SQLite extension..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y php php-cli php-sqlite3
elif command -v yum &> /dev/null; then
    yum install -y php php-cli php-sqlite3
else
    echo "❌ Package manager not found. Please install PHP manually:"
    echo "   - Debian/Ubuntu: apt-get install php php-cli php-sqlite3"
    echo "   - CentOS/RHEL: yum install php php-cli php-sqlite3"
    exit 1
fi

# Verify PHP installation
if ! command -v php &> /dev/null; then
    echo "❌ PHP installation failed"
    exit 1
fi

PHP_VERSION=$(php --version | head -1)
echo "✅ PHP installed: $PHP_VERSION"
echo ""

# 2. Create sqlite_admin directory
echo "📁 Creating sqlite_admin directory..."
mkdir -p "$SQLITE_ADMIN_DIR"
echo "✅ Directory created: $SQLITE_ADMIN_DIR"
echo ""

# 3. Download phpLiteAdmin
echo "📥 Downloading phpLiteAdmin..."
if [ -f "$SQLITE_ADMIN_DIR/phpliteadmin.php" ] && [ -s "$SQLITE_ADMIN_DIR/phpliteadmin.php" ]; then
    echo "⚠️  phpLiteAdmin already exists, skipping download"
else
    if command -v curl &> /dev/null; then
        curl -L -o "$SQLITE_ADMIN_DIR/phpliteadmin.php" "$PHPLITEADMIN_URL"
    elif command -v wget &> /dev/null; then
        wget -O "$SQLITE_ADMIN_DIR/phpliteadmin.php" "$PHPLITEADMIN_URL"
    else
        echo "❌ curl or wget not found. Please install one of them."
        exit 1
    fi
    
    if [ -f "$SQLITE_ADMIN_DIR/phpliteadmin.php" ] && [ -s "$SQLITE_ADMIN_DIR/phpliteadmin.php" ]; then
        echo "✅ phpLiteAdmin downloaded successfully"
    else
        echo "❌ Failed to download phpLiteAdmin"
        exit 1
    fi
fi
echo ""

# 4. Update config.php
echo "⚙️  Updating config.php..."
CONFIG_FILE="$SQLITE_ADMIN_DIR/config.php"

# Determine database path
if [ -f "$PROJECT_ROOT/.env.runpod" ]; then
    # Try to get path from .env.runpod
    DB_PATH=$(grep -E "^SQLITE_DB_PATH=" "$PROJECT_ROOT/.env.runpod" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "")
    if [ -z "$DB_PATH" ]; then
        DB_DIR="$PROJECT_ROOT/storage"
    else
        DB_DIR=$(dirname "$DB_PATH")
    fi
else
    DB_DIR="$PROJECT_ROOT/storage"
fi

cat > "$CONFIG_FILE" << EOF
<?php
/**
 * phpLiteAdmin Configuration
 * สำหรับ Transcription Service
 */

// Database directory (parent directory of database.db)
\$directory = '$DB_DIR';

// Password protection (optional - แนะนำให้ตั้ง password)
\$password = ''; // ใส่ password ตรงนี้ถ้าต้องการ (เช่น 'your_password_here')

// Allowed extensions
\$allowed_extensions = array('db','db3','sqlite','sqlite3');

// Theme
\$theme = 'phpliteadmin.css';

// Language
\$language = 'en';

// Rows per page
\$rowsNum = 30;

// Max rows for export
\$maxrows = 1000;

// Max upload size (MB)
\$max_upload_size = 10;
EOF

echo "✅ Config updated: $CONFIG_FILE"
echo "   Database directory: $DB_DIR"
echo ""

# 5. Set permissions
echo "🔐 Setting permissions..."
chmod 644 "$SQLITE_ADMIN_DIR/phpliteadmin.php"
chmod 644 "$CONFIG_FILE"
echo "✅ Permissions set"
echo ""

# 6. Verify installation
echo "🔍 Verifying installation..."
if [ -f "$SQLITE_ADMIN_DIR/phpliteadmin.php" ] && [ -s "$SQLITE_ADMIN_DIR/phpliteadmin.php" ]; then
    echo "✅ phpLiteAdmin file exists and is not empty"
else
    echo "❌ phpLiteAdmin file is missing or empty"
    exit 1
fi

if [ -f "$CONFIG_FILE" ]; then
    echo "✅ Config file exists"
else
    echo "❌ Config file is missing"
    exit 1
fi

if command -v php &> /dev/null; then
    echo "✅ PHP is available"
else
    echo "❌ PHP is not available"
    exit 1
fi
echo ""

# 7. Test PHP execution
echo "🧪 Testing PHP execution..."
if php -r "echo 'PHP works!';" &> /dev/null; then
    echo "✅ PHP execution test passed"
else
    echo "⚠️  PHP execution test failed (may still work)"
fi
echo ""

echo "=========================================="
echo "✅ SQLite GUI (phpLiteAdmin) installed successfully!"
echo ""
echo "📊 Usage:"
echo "   1. Make sure Dashboard is running:"
echo "      cd dashboard && bash start-daemon.sh"
echo ""
echo "   2. Open browser and go to:"
echo "      http://localhost:8020/sqlite-admin/"
echo ""
echo "   3. Select database:"
echo "      database.db (in $DB_DIR)"
echo ""
echo "💡 Note: If Dashboard is not running, start it first:"
echo "   cd dashboard && bash start-daemon.sh"
echo ""
