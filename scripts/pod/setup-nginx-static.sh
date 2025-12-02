#!/bin/bash
# Script สำหรับ setup Nginx ให้ serve static HTML files

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔧 Setup Nginx สำหรับ Static HTML Files                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ตรวจสอบว่าเป็น root หรือไม่
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or use sudo"
    exit 1
fi

NGINX_CONFIG="/etc/nginx/sites-available/default"
BACKUP_CONFIG="${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
STATIC_DIR="/workspace/transcription-service/static"

echo "📋 Configuration:"
echo "   Nginx Config: $NGINX_CONFIG"
echo "   Static Directory: $STATIC_DIR"
echo ""

# Backup config เดิม
if [ -f "$NGINX_CONFIG" ]; then
    echo "📦 Backup existing config..."
    cp "$NGINX_CONFIG" "$BACKUP_CONFIG"
    echo "✅ Backup created: $BACKUP_CONFIG"
    echo ""
fi

# ตรวจสอบว่า static directory มีอยู่หรือไม่
if [ ! -d "$STATIC_DIR" ]; then
    echo "❌ Static directory not found: $STATIC_DIR"
    exit 1
fi

# อ่าน config เดิม
if [ -f "$NGINX_CONFIG" ]; then
    CONFIG_CONTENT=$(cat "$NGINX_CONFIG")
else
    echo "❌ Nginx config not found: $NGINX_CONFIG"
    exit 1
fi

# ตรวจสอบว่ามี location /static/ อยู่แล้วหรือไม่
if echo "$CONFIG_CONTENT" | grep -q "location /static/"; then
    echo "⚠️  Location /static/ already exists in config"
    echo "   Skipping..."
else
    echo "📝 Adding location /static/ to nginx config..."
    
    # หา server block และเพิ่ม location
    # ใช้ sed เพื่อเพิ่ม location block ก่อน closing brace ของ server
    sed -i '/location \/ {/,/}/ {
        /}/ {
            i\
\
	# Serve static HTML files\
	location /static/ {\
		alias '"$STATIC_DIR"'/;\
		index transcription-upload.html;\
		try_files $uri $uri/ =404;\
	}
        }
    }' "$NGINX_CONFIG"
    
    echo "✅ Location /static/ added"
fi

# เพิ่ม alias สำหรับ root HTML file
if echo "$CONFIG_CONTENT" | grep -q "location = /transcription-upload.html"; then
    echo "⚠️  Location /transcription-upload.html already exists"
else
    echo "📝 Adding alias for transcription-upload.html..."
    
    sed -i '/location \/ {/,/}/ {
        /}/ {
            i\
\
	# Direct access to transcription upload page\
	location = /transcription-upload.html {\
		alias '"$STATIC_DIR"'/transcription-upload.html;\
	}
        }
    }' "$NGINX_CONFIG"
    
    echo "✅ Alias added"
fi

echo ""
echo "🔍 Testing nginx configuration..."

# ทดสอบ config
if nginx -t 2>&1; then
    echo "✅ Nginx configuration is valid"
    echo ""
    
    echo "🔄 Reloading nginx..."
    if systemctl reload nginx 2>&1; then
        echo "✅ Nginx reloaded successfully"
    else
        echo "⚠️  Failed to reload nginx, trying restart..."
        systemctl restart nginx
        echo "✅ Nginx restarted"
    fi
else
    echo "❌ Nginx configuration test failed!"
    echo ""
    echo "💡 Restoring backup..."
    cp "$BACKUP_CONFIG" "$NGINX_CONFIG"
    echo "✅ Config restored from backup"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup Complete!                                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 URLs ที่ใช้งาน:"
echo "   http://80.15.7.37/transcription-upload.html"
echo "   http://80.15.7.37/static/transcription-upload.html"
echo ""
echo "📋 Backup config saved to: $BACKUP_CONFIG"
echo ""

