#!/bin/bash

# Script สำหรับแก้ไข permission ใน staging server

echo "🔧 Fixing file permissions in staging server..."

# ตั้งค่า permission ของ directories
echo "📁 Setting directory permissions..."
chmod 755 uploads/
chmod 755 temp/
chmod 755 storage/
chmod 755 storage/transcriptions/
chmod 755 storage/captions/
chmod 755 storage/videos/
chmod 755 storage/metadata/
chmod 755 test-files/

# แก้ไข permission ของไฟล์ทั้งหมดใน uploads
echo "📄 Fixing file permissions in uploads..."
find uploads/ -type f -exec chmod 644 {} \;

# แก้ไข permission ของไฟล์ทั้งหมดใน temp
echo "📄 Fixing file permissions in temp..."
find temp/ -type f -exec chmod 644 {} \;

# แก้ไข permission ของไฟล์ทั้งหมดใน storage
echo "📄 Fixing file permissions in storage..."
find storage/ -type f -exec chmod 644 {} \;

# เปลี่ยน ownership ของไฟล์ทั้งหมดให้เป็น kscdev:kscdev
echo "👤 Changing file ownership..."
chown -R kscdev:kscdev uploads/
chown -R kscdev:kscdev temp/
chown -R kscdev:kscdev storage/
chown -R kscdev:kscdev test-files/

set -e  # หยุดทำงานเมื่อเกิด error

echo "✅ Permission fix completed!"
echo "📊 Current permissions:"
echo "🔍 Checking current permissions before fix..."
ls -la uploads/ | head -5
# ls -la uploads/
ls -la storage/
