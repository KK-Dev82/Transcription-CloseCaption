#!/bin/bash
# Script สำหรับติดตั้ง SQLite Admin (phpLiteAdmin) บน PodContainer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"
ADMIN_DIR="$DASHBOARD_DIR/sqlite_admin"

echo "🔧 Installing SQLite Admin (phpLiteAdmin) for PodContainer"
echo "=================================================="
echo ""

# Check PHP
if ! command -v php &> /dev/null; then
    echo "📦 Installing PHP..."
    
    # Check if we're root or need sudo
    if [ "$EUID" -eq 0 ]; then
        # We're root, no need for sudo
        USE_SUDO=""
    elif command -v sudo &> /dev/null; then
        # sudo is available
        USE_SUDO="sudo"
    else
        # No sudo and not root - try without sudo (might work if user has permissions)
        USE_SUDO=""
        echo "⚠️  Warning: No sudo available and not root. Trying without sudo..."
    fi
    
    if command -v apt-get &> /dev/null; then
        $USE_SUDO apt-get update
        $USE_SUDO apt-get install -y php php-cli php-sqlite3
    elif command -v yum &> /dev/null; then
        $USE_SUDO yum install -y php php-cli php-pdo php-sqlite3
    else
        echo "❌ Error: Cannot install PHP automatically. Please install PHP manually."
        echo ""
        echo "💡 Manual installation options:"
        echo "   - Ubuntu/Debian: apt-get install -y php php-cli php-sqlite3"
        echo "   - CentOS/RHEL: yum install -y php php-cli php-pdo php-sqlite3"
        echo "   - Or use a container image that already has PHP installed"
        exit 1
    fi
fi

echo "✅ PHP found: $(php --version | head -1)"

# Create admin directory
mkdir -p "$ADMIN_DIR"
cd "$ADMIN_DIR"

# Download phpLiteAdmin
echo ""
echo "📥 Downloading phpLiteAdmin..."
if [ ! -f "phpliteadmin.php" ]; then
    wget -q https://raw.githubusercontent.com/webshell/phpLiteAdmin/master/phpliteadmin.php -O phpliteadmin.php
    echo "✅ Downloaded phpliteadmin.php"
else
    echo "✅ phpliteadmin.php already exists"
fi

# Create configuration
echo ""
echo "🔧 Creating configuration..."

# Get storage path
STORAGE_DIR="$PROJECT_ROOT/storage"
DB_PATH="$STORAGE_DIR/database.db"

cat > "$ADMIN_DIR/config.php" << 'EOF'
<?php
/**
 * phpLiteAdmin Configuration
 * สำหรับ Transcription Service
 */

// Database directory (parent directory of database.db)
$directory = '/workspace/transcription-service/storage';

// Password protection (optional - แนะนำให้ตั้ง password)
$password = ''; // ใส่ password ตรงนี้ถ้าต้องการ (เช่น 'your_password_here')

// Allowed extensions
$allowed_extensions = array('db','db3','sqlite','sqlite3');

// Theme
$theme = 'phpliteadmin.css';

// Language
$language = 'en';

// Rows per page
$rowsNum = 30;

// Max rows for export
$maxrows = 1000;

// Max upload size (MB)
$max_upload_size = 10;
EOF

# Update directory path in config
sed -i "s|/workspace/transcription-service/storage|$STORAGE_DIR|g" "$ADMIN_DIR/config.php"

# Create simple index.php to redirect to phpliteadmin
cat > "$ADMIN_DIR/index.php" << 'EOF'
<?php
// Redirect to phpliteadmin.php
header('Location: phpliteadmin.php');
exit;
EOF

# Set permissions
chmod 644 "$ADMIN_DIR/phpliteadmin.php"
chmod 644 "$ADMIN_DIR/config.php"
chmod 644 "$ADMIN_DIR/index.php"

echo ""
echo "✅ SQLite Admin installed successfully!"
echo ""
echo "📋 Configuration:"
echo "   - Admin directory: $ADMIN_DIR"
echo "   - Database path: $DB_PATH"
echo "   - Config file: $ADMIN_DIR/config.php"
echo ""
echo "🌐 Access SQLite Admin:"
echo "   - Via Dashboard: http://YOUR_SERVER:8020/sqlite-admin/"
echo "   - Direct: http://YOUR_SERVER:8020/sqlite-admin/phpliteadmin.php"
echo ""
echo "💡 Security Note:"
echo "   - แนะนำให้ตั้ง password ใน config.php"
echo "   - หรือใช้ Dashboard authentication"
echo ""

