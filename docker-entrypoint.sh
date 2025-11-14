#!/bin/bash
set -e

# จัดการ permission ของ volumes ที่ mount จาก host
# เพื่อให้ container สามารถเขียนไฟล์ได้

echo "🔧 Setting up permissions for mounted volumes..."

# สร้าง directories ถ้ายังไม่มี
mkdir -p /app/uploads /app/temp /app/storage /app/models /app/test-files
mkdir -p /app/storage/transcriptions /app/storage/captions /app/storage/videos /app/storage/metadata

# ตั้งค่า permission ของ directories
chmod -R 777 /app/uploads /app/temp /app/storage /app/models /app/test-files 2>/dev/null || true

# ตั้งค่า permission ของไฟล์ที่มีอยู่แล้ว
find /app/uploads -type f -exec chmod 644 {} \; 2>/dev/null || true
find /app/temp -type f -exec chmod 644 {} \; 2>/dev/null || true
find /app/storage -type f -exec chmod 644 {} \; 2>/dev/null || true
find /app/models -type f -exec chmod 644 {} \; 2>/dev/null || true

echo "✅ Permissions setup completed!"

# รัน command ที่ส่งเข้ามา
exec "$@"

