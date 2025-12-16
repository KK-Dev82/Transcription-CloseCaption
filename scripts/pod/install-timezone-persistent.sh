#!/bin/bash
# Script สำหรับติดตั้ง timezone data ไปยัง persistent volume
# เพื่อไม่ต้องติดตั้งใหม่ทุกครั้งหลัง restart Pod

set -e

PERSISTENT_ZONEINFO="/workspace/.local/share/zoneinfo"
SYSTEM_ZONEINFO="/usr/share/zoneinfo"

echo "📋 Installing timezone data to persistent volume..."
echo ""

# สร้าง directory
mkdir -p "$PERSISTENT_ZONEINFO"

# ตรวจสอบว่ามี timezone data ที่ system หรือไม่
if [ -d "$SYSTEM_ZONEINFO" ] && [ -f "$SYSTEM_ZONEINFO/Asia/Bangkok" ]; then
    echo "✅ Found timezone data at $SYSTEM_ZONEINFO"
    
    # Copy ไปยัง persistent volume
    if [ ! -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
        echo "📦 Copying timezone data to persistent volume..."
        cp -r "$SYSTEM_ZONEINFO"/* "$PERSISTENT_ZONEINFO/" 2>/dev/null || {
            echo "⚠️  Some files may have failed to copy (this is usually OK)"
        }
        echo "✅ Timezone data copied to $PERSISTENT_ZONEINFO"
    else
        echo "✅ Timezone data already exists at persistent volume"
    fi
    
    # ตรวจสอบว่า copy สำเร็จ
    if [ -f "$PERSISTENT_ZONEINFO/Asia/Bangkok" ]; then
        echo "✅ Timezone data ready at persistent volume"
        echo "   Location: $PERSISTENT_ZONEINFO"
        echo "   Bangkok timezone: $(ls -lh "$PERSISTENT_ZONEINFO/Asia/Bangkok" | awk '{print $5}')"
    else
        echo "⚠️  Timezone data copy may have failed"
    fi
else
    echo "⚠️  No timezone data found at $SYSTEM_ZONEINFO"
    echo "📦 Installing tzdata..."
    
    # ติดตั้ง tzdata
    apt-get update -qq && apt-get install -y -qq tzdata > /dev/null 2>&1 || {
        echo "❌ Failed to install tzdata"
        exit 1
    }
    
    # Copy ไปยัง persistent volume
    if [ -d "$SYSTEM_ZONEINFO" ] && [ -f "$SYSTEM_ZONEINFO/Asia/Bangkok" ]; then
        echo "📦 Copying timezone data to persistent volume..."
        cp -r "$SYSTEM_ZONEINFO"/* "$PERSISTENT_ZONEINFO/" 2>/dev/null || {
            echo "⚠️  Some files may have failed to copy (this is usually OK)"
        }
        echo "✅ Timezone data copied to $PERSISTENT_ZONEINFO"
    fi
fi

echo ""
echo "✅ Timezone data installation complete!"
echo "   Use TZDIR=$PERSISTENT_ZONEINFO in your environment variables"

