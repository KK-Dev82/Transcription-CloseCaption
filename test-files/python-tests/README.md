# 🐍 Python Test Scripts

ไฟล์ทดสอบ Python สำหรับระบบ Transcription Close Caption Service

## 📁 ไฟล์ทดสอบ

### **API Testing**
- **`test_api_endpoints.py`** - ทดสอบ API endpoints ทั้งหมด
- **`test_transcription.py`** - ทดสอบการทำ transcription ผ่าน API
- **`test_transcription_docker.py`** - ทดสอบ transcription ผ่าน Docker

### **Video Processing**
- **`test_video_features.py`** - ทดสอบฟีเจอร์วิดีโอทั้งหมด
- **`test_video_segmentation.py`** - ทดสอบการแบ่งตอนวิดีโอ + transcription
- **`test_video_trim.py`** - ทดสอบการตัดวิดีโอ
- **`test_segmentation_only.py`** - ทดสอบการแบ่งตอนวิดีโออย่างเดียว

### **Text Processing**
- **`test_thai_processing.py`** - ทดสอบการประมวลผลข้อความไทย

## 🚀 วิธีใช้งาน

### **1. ทดสอบ API Endpoints**
```bash
cd test-files/python-tests/
python test_api_endpoints.py
```

### **2. ทดสอบ Transcription**
```bash
# ทดสอบผ่าน API
python test_transcription.py

# ทดสอบผ่าน Docker
python test_transcription_docker.py
```

### **3. ทดสอบ Video Processing**
```bash
# ทดสอบฟีเจอร์วิดีโอทั้งหมด
python test_video_features.py

# ทดสอบการแบ่งตอนวิดีโอ
python test_video_segmentation.py

# ทดสอบการตัดวิดีโอ
python test_video_trim.py
```

### **4. ทดสอบ Text Processing**
```bash
python test_thai_processing.py
```

## 📋 ข้อกำหนด

### **Dependencies**
```bash
pip install requests aiohttp httpx websockets numpy
```

### **ไฟล์ที่จำเป็น**
- `test_video.mp4` - ไฟล์วิดีโอทดสอบ
- `trimmed_short.mp4` - ไฟล์วิดีโอสั้นสำหรับทดสอบ

### **Environment Variables**
- `API_BASE_URL` - URL ของ API (default: http://localhost:8001)
- `DOCKER_COMPOSE_FILE` - ไฟล์ docker-compose (ถ้าใช้ Docker)

## 🔧 การแก้ไขปัญหา

### **API Connection Issues**
- ตรวจสอบว่า API server ทำงานอยู่
- ตรวจสอบ port และ URL
- ดู logs ของ API server

### **Docker Issues**
- ตรวจสอบว่า Docker containers ทำงานอยู่
- ตรวจสอบ docker-compose logs
- ตรวจสอบ volume mounts

### **File Permission Issues**
- ใช้ `scripts/fix_staging_permissions.sh` สำหรับ staging
- ตรวจสอบ file permissions ใน uploads/ และ temp/

## 📊 ผลลัพธ์

### **Test Results**
- ไฟล์ผลลัพธ์จะถูกบันทึกในโฟลเดอร์หลัก
- ดู logs ใน console สำหรับรายละเอียด
- ใช้ `test_results.json` สำหรับผลลัพธ์แบบละเอียด

### **Performance Metrics**
- Response time
- Success rate
- Error messages
- Resource usage

## 🎯 Best Practices

1. **รัน tests ทีละไฟล์** เพื่อ debug ได้ง่าย
2. **ตรวจสอบ logs** เมื่อเกิดข้อผิดพลาด
3. **ใช้ไฟล์ทดสอบขนาดเล็ก** เพื่อประหยัดเวลา
4. **บันทึกผลลัพธ์** สำหรับการเปรียบเทียบ
5. **ทดสอบใน staging** ก่อน production
