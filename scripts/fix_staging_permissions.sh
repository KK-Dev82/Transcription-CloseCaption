#!/bin/bash

# Script สำหรับแก้ไข permission ใน staging server

echo "🔧 Fixing file permissions in staging server..."

# ตั้งค่า permission ของ directories ให้ container (root) เข้าถึงได้
echo "�� Setting directory permissions for container access..."
chmod 777 uploads/
chmod 777 temp/
chmod 777 storage/
chmod 777 storage/transcriptions/
chmod 777 storage/captions/
chmod 777 storage/videos/
chmod 777 storage/metadata/
chmod 777 models/          # เพิ่มบรรทัดนี้
chmod 777 test-files/

# แก้ไข permission ของไฟล์ทั้งหมดใน uploads
echo "�� Fixing file permissions in uploads..."
find uploads/ -type f -exec chmod 644 {} \;

# แก้ไข permission ของไฟล์ทั้งหมดใน temp
echo "�� Fixing file permissions in temp..."
find temp/ -type f -exec chmod 644 {} \;

# แก้ไข permission ของไฟล์ทั้งหมดใน storage
echo "�� Fixing file permissions in storage..."
find storage/ -type f -exec chmod 644 {} \;

# แก้ไข permission ของไฟล์ทั้งหมดใน models
echo "�� Fixing file permissions in models..."
find models/ -type f -exec chmod 644 {} \;  # เพิ่มบรรทัดนี้

# เปลี่ยน ownership ของไฟล์ทั้งหมดให้เป็น kscdev:kscdev
echo "👤 Changing file ownership..."
sudo chown -R kscdev:kscdev uploads/
sudo chown -R kscdev:kscdev temp/
sudo chown -R kscdev:kscdev storage/
sudo chown -R kscdev:kscdev models/        # เพิ่มบรรทัดนี้
sudo chown -R kscdev:kscdev test-files/

set -e  # หยุดทำงานเมื่อเกิด error

echo "✅ Permission fix completed!"
echo "📊 Current permissions:"
echo "🔍 Checking current permissions before fix..."
ls -la uploads/ | head -5
ls -la storage/
ls -la models/              # เพิ่มบรรทัดนี้