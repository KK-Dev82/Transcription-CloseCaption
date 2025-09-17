#!/bin/bash

# Test Permission Script for Staging
# ทดสอบ permission ของไฟล์และโฟลเดอร์ใน staging environment

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
    echo -e "${PURPLE}🔍 Staging Permission Test Script${NC}"
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
# ทดสอบผ่าน Nginx proxy (จากภายนอก) - วิธีเดียวที่ใช้งานได้
STAGING_URL="https://staging-ph2.bms.senate.go.th"

print_header

# 1. ตรวจสอบ API
print_step "ตรวจสอบ Staging API..."

print_info "🌐 ทดสอบ health check: ${STAGING_URL}/transcribe/health"
curl -k -f ${STAGING_URL}/transcribe/health || print_warning "API ไม่ตอบสนอง"

print_info "📊 ทดสอบ stats: ${STAGING_URL}/transcribe/stats"
curl -k -f ${STAGING_URL}/transcribe/stats || print_warning "Stats API ไม่ตอบสนอง"

print_info "📋 ทดสอบ transcription list: ${STAGING_URL}/transcribe/transcription/list/stored"
curl -k -f ${STAGING_URL}/transcribe/transcription/list/stored || print_warning "Transcription list API ไม่ตอบสนอง"

print_info "📋 ทดสอบ queue info: ${STAGING_URL}/transcribe/queue/info"
curl -k -f ${STAGING_URL}/transcribe/queue/info || print_warning "Queue info API ไม่ตอบสนอง"

print_info "🎵 ทดสอบ whisper health: ${STAGING_URL}/whisper/health"
curl -k -f ${STAGING_URL}/whisper/health || print_warning "Whisper API ไม่ตอบสนอง"

# 2. ตรวจสอบ test files
print_step "ตรวจสอบ Test Files..."
print_info "🧪 ทดสอบ test-staging.html: ${STAGING_URL}/transcribe/test-files/test-staging.html"
curl -k -f ${STAGING_URL}/transcribe/test-files/test-staging.html > /dev/null || print_warning "Test file ไม่พบ"

print_info "🧪 ทดสอบ test_permission_fix.html: ${STAGING_URL}/transcribe/test-files/test_permission_fix.html"
curl -k -f ${STAGING_URL}/transcribe/test-files/test_permission_fix.html > /dev/null || print_warning "Permission test file ไม่พบ"

# 3. ตรวจสอบ media-uploads directory
print_step "ตรวจสอบ Media Uploads Directory..."
print_info "📁 ตรวจสอบ media-uploads directory: ${STAGING_URL}/media-uploads/"
curl -k -f ${STAGING_URL}/media-uploads/ > /dev/null || print_warning "Media-uploads directory ไม่สามารถเข้าถึงได้ (ไม่มี Nginx endpoint)"

print_info "📁 ทดสอบการเข้าถึงไฟล์ที่อัปโหลดแล้ว: ${STAGING_URL}/transcribe/file/"
print_warning "💡 ต้องเพิ่ม /media-uploads/ endpoint ใน Nginx config หรือใช้ /transcribe/file/{filename} แทน"

# 4. ทดสอบ file upload (simulation)
print_step "ทดสอบ File Upload Simulation..."
print_info "📤 ทดสอบ upload endpoint: ${STAGING_URL}/transcribe/upload/"

# ตรวจสอบว่ามีไฟล์ test หรือไม่
if [ -f "test_video.mp4" ]; then
    print_info "📤 ใช้ไฟล์ test_video.mp4 ที่มีอยู่"
    curl -k -X POST ${STAGING_URL}/transcribe/upload/ \
        -H "Content-Type: multipart/form-data" \
        -F "file=@test_video.mp4" \
        || print_warning "Upload test ล้มเหลว"
else
    print_warning "ไม่พบไฟล์ test_video.mp4 - ข้ามการทดสอบ upload"
    print_info "💡 สร้างไฟล์ test: touch test_video.mp4"
fi

# 5. ตรวจสอบ logs
print_step "ตรวจสอบ Logs..."
print_info "📋 ตรวจสอบ container logs (ถ้าเข้าถึงได้):"
print_info "  docker logs transcription-api-staging"
print_info "  docker logs transcription-whisper-staging"

# 6. สรุปผลลัพธ์
print_success "การทดสอบ Staging Permission เสร็จสิ้น!"
print_info ""
print_info "📋 สรุปผลลัพธ์:"
print_info "  - Main API: ${STAGING_URL}/transcribe"
print_info "  - Whisper API: ${STAGING_URL}/whisper"
print_info "  - Media Files: ${STAGING_URL}/media-uploads"
print_info "  - Test Files: ${STAGING_URL}/transcribe/test-files/"
print_info "  - API Docs: ${STAGING_URL}/transcribe/docs"
print_info ""
print_info "🔧 คำสั่งสำหรับ debug:"
print_info "  # Main API:"
print_info "  curl -k -f ${STAGING_URL}/transcribe/health"
print_info "  curl -k -f ${STAGING_URL}/transcribe/stats"
print_info "  # Whisper API:"
print_info "  curl -k -f ${STAGING_URL}/whisper/health"
print_info "  # Media Files:"
print_info "  curl -k -f ${STAGING_URL}/media-uploads/"
print_info ""
print_info "🧪 ทดสอบผ่าน browser:"
print_info "  ${STAGING_URL}/transcribe/test-files/test-staging.html"
print_info "  ${STAGING_URL}/transcribe/test-files/test_permission_fix.html"
