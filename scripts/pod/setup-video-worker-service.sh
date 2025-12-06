#!/bin/bash

# Script สำหรับติดตั้ง Video Worker เป็น systemd service
# ใช้สำหรับ auto-restart worker เมื่อ crash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVICE_NAME="video-worker"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔧 Setup Video Worker Systemd Service                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ตรวจสอบว่าอยู่ใน root หรือไม่
if [ "$EUID" -ne 0 ]; then
    echo "❌ ต้องใช้สิทธิ์ root เพื่อติดตั้ง systemd service"
    echo "   รัน: sudo bash $0"
    exit 1
fi

echo "📋 Steps:"
echo "  1. สร้าง systemd service file"
echo "  2. Reload systemd daemon"
echo "  3. Enable service (auto-start on boot)"
echo "  4. Start service"
echo ""

# Step 1: Copy service file
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Step 1: สร้าง systemd service file..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$SERVICE_FILE" ]; then
    echo "⚠️  Service file มีอยู่แล้ว: $SERVICE_FILE"
    read -p "ต้องการ overwrite หรือไม่? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ ข้ามการสร้าง service file"
        exit 1
    fi
fi

# สร้าง service file จาก template
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Transcription Video Worker
After=network.target rabbitmq-server.service
Requires=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/transcription-service
ExecStart=/usr/bin/python3 -m app.workers.video_worker
Restart=always
RestartSec=10
StartLimitInterval=0
StartLimitBurst=0
StandardOutput=append:/tmp/video-worker.log
StandardError=append:/tmp/video-worker.log
Environment="PYTHONPATH=/workspace/transcription-service"
Environment="PYTHONUSERBASE=/workspace/.local"
EnvironmentFile=/workspace/transcription-service/.env.runpod

# Resource limits
TimeoutStartSec=300
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

echo "✅ สร้าง service file สำเร็จ: $SERVICE_FILE"

# Step 2: Reload systemd
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Step 2: Reload systemd daemon..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

systemctl daemon-reload
echo "✅ Reload systemd daemon สำเร็จ"

# Step 3: Enable service
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  Step 3: Enable service (auto-start on boot)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

systemctl enable "$SERVICE_NAME"
echo "✅ Enable service สำเร็จ"

# Step 4: Start service
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 4: Start service..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

systemctl start "$SERVICE_NAME"
echo "✅ Start service สำเร็จ"

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup Complete                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Service Status:"
systemctl status "$SERVICE_NAME" --no-pager -l || true
echo ""
echo "💡 Useful Commands:"
echo "   Check status:  systemctl status $SERVICE_NAME"
echo "   View logs:     journalctl -u $SERVICE_NAME -f"
echo "   Stop service:  systemctl stop $SERVICE_NAME"
echo "   Start service: systemctl start $SERVICE_NAME"
echo "   Restart:       systemctl restart $SERVICE_NAME"
echo "   Disable:       systemctl disable $SERVICE_NAME"
echo ""

