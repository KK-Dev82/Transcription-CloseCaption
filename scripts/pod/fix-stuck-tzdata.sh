#!/bin/bash
# Script สำหรับแก้ไขปัญหา tzdata ที่ติดค้างระหว่างการติดตั้ง
# ใช้เมื่อ apt-get install tzdata ติดค้างและไม่สามารถ stop ได้

set -e

echo "🔧 Fixing Stuck tzdata Installation"
echo "===================================="
echo ""

# ตรวจสอบ process ที่เกี่ยวข้อง
echo "📋 Checking for stuck processes..."
STUCK_PROCS=$(ps aux | grep -E "(apt|tzdata|dpkg)" | grep -v grep || true)

if [ -z "$STUCK_PROCS" ]; then
    echo "✅ No stuck processes found"
else
    echo "⚠️  Found stuck processes:"
    echo "$STUCK_PROCS"
    echo ""
    
    # Kill process ที่เกี่ยวข้อง
    echo "🛑 Stopping stuck processes..."
    pkill -f "apt-get.*tzdata" 2>/dev/null || true
    pkill -f "tzdata.config" 2>/dev/null || true
    pkill -f "tzdata.postinst" 2>/dev/null || true
    sleep 2
    
    # Kill dpkg process ที่ติดค้าง
    if pgrep -f "dpkg.*configure" > /dev/null 2>&1; then
        echo "🛑 Stopping dpkg configure process..."
        pkill -f "dpkg.*configure" 2>/dev/null || true
        sleep 1
    fi
fi

# ตรวจสอบ lock files
echo ""
echo "📋 Checking for lock files..."
if [ -f /var/lib/dpkg/lock ]; then
    echo "⚠️  Found dpkg lock file"
    # ตรวจสอบว่ามี process ใช้ lock อยู่หรือไม่
    if ! lsof /var/lib/dpkg/lock > /dev/null 2>&1; then
        echo "   Removing stale lock file..."
        rm -f /var/lib/dpkg/lock
        rm -f /var/lib/dpkg/lock-frontend
        rm -f /var/cache/apt/archives/lock
        rm -f /var/lib/apt/lists/lock
        echo "✅ Lock files removed"
    else
        echo "   ⚠️  Lock file is in use, cannot remove"
    fi
fi

# แก้ไขสถานะ dpkg
echo ""
echo "📋 Fixing dpkg state..."
export DEBIAN_FRONTEND=noninteractive
export TZ=Asia/Bangkok

# Configure tzdata ที่ติดค้าง
if dpkg -l | grep -q "tzdata.*half-configured"; then
    echo "🔧 Configuring stuck tzdata package..."
    echo "tzdata tzdata/Areas select Asia" | debconf-set-selections 2>/dev/null || true
    echo "tzdata tzdata/Zones/Asia select Bangkok" | debconf-set-selections 2>/dev/null || true
    DEBIAN_FRONTEND=noninteractive TZ=Asia/Bangkok dpkg --configure -a || {
        echo "⚠️  dpkg --configure failed, trying force..."
        DEBIAN_FRONTEND=noninteractive dpkg --configure --force-all tzdata || true
    }
fi

# Configure packages ที่ pending ทั้งหมด
echo "🔧 Configuring all pending packages..."
DEBIAN_FRONTEND=noninteractive TZ=Asia/Bangkok dpkg --configure -a 2>&1 | head -20 || {
    echo "⚠️  Some packages may still need configuration"
}

echo ""
echo "✅ Fix attempt complete"
echo ""
echo "💡 Next steps:"
echo "   1. Check if processes are stopped: ps aux | grep -E '(apt|tzdata|dpkg)'"
echo "   2. Try installing again: bash scripts/pod/install-dependencies.sh"
echo ""

