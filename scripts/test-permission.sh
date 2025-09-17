#!/bin/bash

# Test Permission Script
# ทดสอบ permission ของไฟล์และโฟลเดอร์ใน Docker container

set -e

# สีสำหรับ output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ฟังก์ชันสำหรับแสดงข้อความ
print_header() {
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${PURPLE}🔍 Permission Test Script${NC}"
    echo -e "${PURPLE}========================================${NC}"
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Configuration
CONTAINER_NAME="transcription-api-test"

print_header

# 1. ตรวจสอบ container
print_step "ตรวจสอบ Container..."
if ! docker ps | grep -q ${CONTAINER_NAME}; then
    print_error "Container ${CONTAINER_NAME} ไม่ทำงาน!"
    print_info "รันคำสั่ง: docker-compose -f docker-compose.test.yml up -d"
    exit 1
fi
print_success "Container ${CONTAINER_NAME} ทำงานอยู่"

# 2. ตรวจสอบ permission ของ directories
print_step "ตรวจสอบ Permission ของ Directories..."

print_info "📁 uploads directory:"
docker exec ${CONTAINER_NAME} ls -la /app/uploads

print_info "📁 temp directory:"
docker exec ${CONTAINER_NAME} ls -la /app/temp

print_info "📁 storage directory:"
docker exec ${CONTAINER_NAME} ls -la /app/storage

print_info "📁 models directory:"
docker exec ${CONTAINER_NAME} ls -la /app/models

# 3. ตรวจสอบ permission ของไฟล์
print_step "ตรวจสอบ Permission ของไฟล์..."

print_info "🔍 ตรวจสอบ permission ของไฟล์ใน uploads:"
docker exec ${CONTAINER_NAME} find /app/uploads -type f -exec ls -la {} \; 2>/dev/null || print_warning "ไม่มีไฟล์ใน uploads"

print_info "🔍 ตรวจสอบ permission ของไฟล์ใน temp:"
docker exec ${CONTAINER_NAME} find /app/temp -type f -exec ls -la {} \; 2>/dev/null || print_warning "ไม่มีไฟล์ใน temp"

print_info "🔍 ตรวจสอบ permission ของไฟล์ใน storage:"
docker exec ${CONTAINER_NAME} find /app/storage -type f -exec ls -la {} \; 2>/dev/null || print_warning "ไม่มีไฟล์ใน storage"

# 4. ทดสอบการสร้างไฟล์
print_step "ทดสอบการสร้างไฟล์..."

print_info "📝 สร้างไฟล์ทดสอบใน uploads:"
docker exec ${CONTAINER_NAME} touch /app/uploads/test_file.txt
docker exec ${CONTAINER_NAME} ls -la /app/uploads/test_file.txt

print_info "📝 สร้างไฟล์ทดสอบใน temp:"
docker exec ${CONTAINER_NAME} touch /app/temp/test_file.txt
docker exec ${CONTAINER_NAME} ls -la /app/temp/test_file.txt

print_info "📝 สร้างไฟล์ทดสอบใน storage:"
docker exec ${CONTAINER_NAME} touch /app/storage/test_file.txt
docker exec ${CONTAINER_NAME} ls -la /app/storage/test_file.txt

# 5. ทดสอบการเขียนไฟล์
print_step "ทดสอบการเขียนไฟล์..."

print_info "✍️ เขียนข้อมูลลงไฟล์:"
docker exec ${CONTAINER_NAME} sh -c 'echo "Test content" > /app/uploads/test_write.txt'
docker exec ${CONTAINER_NAME} cat /app/uploads/test_write.txt

# 6. ทดสอบการลบไฟล์
print_step "ทดสอบการลบไฟล์..."

print_info "🗑️ ลบไฟล์ทดสอบ:"
docker exec ${CONTAINER_NAME} rm -f /app/uploads/test_file.txt /app/uploads/test_write.txt
docker exec ${CONTAINER_NAME} rm -f /app/temp/test_file.txt
docker exec ${CONTAINER_NAME} rm -f /app/storage/test_file.txt

print_success "ลบไฟล์ทดสอบเสร็จสิ้น"

# 7. ตรวจสอบ API
print_step "ทดสอบ API..."

print_info "🌐 ทดสอบ health check:"
curl -f http://localhost:8001/health || print_warning "API ไม่ตอบสนอง"

print_info "📊 ทดสอบ stats:"
curl -f http://localhost:8001/stats || print_warning "Stats API ไม่ตอบสนอง"

# 8. สรุปผลลัพธ์
print_success "การทดสอบ Permission เสร็จสิ้น!"
print_info ""
print_info "📋 สรุปผลลัพธ์:"
print_info "  - Container: ${CONTAINER_NAME}"
print_info "  - API URL: http://localhost:8001"
print_info "  - Test Files: http://localhost:8001/test-files/"
print_info ""
print_info "🔧 คำสั่งสำหรับ debug:"
print_info "  docker exec ${CONTAINER_NAME} ls -la /app/uploads"
print_info "  docker exec ${CONTAINER_NAME} ls -la /app/temp"
print_info "  docker exec ${CONTAINER_NAME} ls -la /app/storage"
print_info "  docker logs ${CONTAINER_NAME}"
print_info ""
print_info "🛑 หยุด container:"
print_info "  docker-compose -f docker-compose.test.yml down"
