#!/bin/bash

# Build Local Docker Images with Layer Caching
# สคริปต์สำหรับ build และทดสอบ permission ใน local environment

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
    echo -e "${PURPLE}🐳 Docker Build Local${NC}"
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
IMAGE_TAG="local-dev"
MAIN_IMAGE="kk-transcription:${IMAGE_TAG}"
WHISPER_IMAGE="kk-transcription-whisper:${IMAGE_TAG}"

print_header

# 1. ตรวจสอบ Docker
print_step "ตรวจสอบ Docker..."
if ! command -v docker &> /dev/null; then
    print_error "ไม่พบ Docker! กรุณาติดตั้ง Docker ก่อน"
    exit 1
fi
print_success "Docker พร้อมใช้งาน"

# 2. Build Main API Image (ใช้ cache)
print_step "Build Main API Image (ใช้ layer caching)..."
docker build \
    -f Dockerfile \
    -t ${MAIN_IMAGE} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .

print_success "Build Main API Image เสร็จสิ้น"

# 3. Build Whisper Service Image (ใช้ cache)
print_step "Build Whisper Service Image (ใช้ layer caching)..."
cd whisper-service
docker build \
    -f Dockerfile.arm64 \
    -t ${WHISPER_IMAGE} \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .
cd ..

print_success "Build Whisper Service Image เสร็จสิ้น"

# 4. ตรวจสอบ images
print_step "ตรวจสอบ Images..."
docker images | grep -E "(kk-transcription|kk-transcription-whisper)"

# 5. ทดสอบ Permission
print_step "ทดสอบ Permission..."

# สร้าง test container
print_info "สร้าง test container..."
docker run -d --name test-permission \
    -p 8001:8001 \
    -v $(pwd)/uploads:/app/uploads \
    -v $(pwd)/temp:/app/temp \
    -v $(pwd)/storage:/app/storage \
    ${MAIN_IMAGE}

# รอให้ container เริ่มต้น
print_info "รอให้ container เริ่มต้น..."
sleep 10

# ตรวจสอบ permission
print_info "ตรวจสอบ permission ของ uploads directory..."
docker exec test-permission ls -la /app/uploads

# ตรวจสอบ permission ของ temp directory
print_info "ตรวจสอบ permission ของ temp directory..."
docker exec test-permission ls -la /app/temp

# ตรวจสอบ permission ของ storage directory
print_info "ตรวจสอบ permission ของ storage directory..."
docker exec test-permission ls -la /app/storage

# 6. ทดสอบ API
print_step "ทดสอบ API..."
print_info "ทดสอบ health check..."
curl -f http://localhost:8001/health || print_warning "API ยังไม่พร้อม"

# 7. แสดงข้อมูล
print_success "Build และทดสอบเสร็จสิ้น!"
print_info "Images:"
print_info "  - ${MAIN_IMAGE}"
print_info "  - ${WHISPER_IMAGE}"
print_info ""
print_info "Test Container: test-permission"
print_info "API URL: http://localhost:8001"
print_info "Test Files: http://localhost:8001/test-files/"
print_info ""
print_info "คำสั่งสำหรับทดสอบ:"
print_info "  docker exec test-permission ls -la /app/uploads"
print_info "  docker exec test-permission ls -la /app/temp"
print_info "  docker exec test-permission ls -la /app/storage"
print_info ""
print_info "หยุด test container:"
print_info "  docker stop test-permission"
print_info "  docker rm test-permission"
