# 📊 สรุปการวิเคราะห์ Performance และ Concurrency Testing

## 🎯 สรุปผลการวิเคราะห์

จากการตรวจสอบ Flow การทำงานจาก **Senate-Backend** และ **Transcription Service** พบว่า:

### Architecture Overview

```
User → Senate-Backend API → Hangfire Queue → Transcription Service API
→ RabbitMQ Queue → Video Workers → Whisper Service → Results
```

### Current System Capacity

| Component | Capacity | Bottleneck |
|-----------|----------|------------|
| **Hangfire Workers** | 2 concurrent jobs | ⚠️ **ใช่** - จำกัดการส่ง jobs |
| **Video Workers** | 6 concurrent tasks (2 workers × prefetch=3) | ❌ ไม่ใช่ |
| **Whisper Service** | 1 instance | ⚠️ **อาจ** - ต้องทดสอบ |

---

## ⏱️ เวลาที่คาดหวังสำหรับ 100 Users (วิดีโอ 1 ชั่วโมง)

### การคำนวณ

**ข้อมูลพื้นฐาน**:
- วิดีโอ 1 ชั่วโมง = 3600 วินาที
- Chunk duration = 30 วินาที
- จำนวน chunks = 120 chunks

**เวลาต่อวิดีโอ**:
- **Sequential processing**: ~10 นาที
- **Concurrent processing (ideal)**: ~2-5 นาที
- **Realistic**: **5-15 นาที**

### เวลารวมสำหรับ 100 Users

| Scenario | Time |
|----------|------|
| **Pessimistic** | 6.95 ชั่วโมง |
| **Realistic** | 3-5 ชั่วโมง |
| **Optimistic** | 2.8 ชั่วโมง |

**🎯 สรุป: คาดหวังประมาณ 3-7 ชั่วโมง สำหรับ 100 users**

---

## 🔍 Bottlenecks ที่พบ

### 1. Hangfire WorkerCount = 2 ⚠️ **Critical**

**ปัญหา**: จำกัดการส่ง jobs เป็น 2 jobs พร้อมกัน

**ผลกระทบ**:
- ถ้ามี 100 jobs → ต้องรอ ~250 นาที (4.2 ชั่วโมง) แค่ใน Hangfire queue

**แนวทางแก้ไข**:
- เพิ่ม Hangfire WorkerCount เป็น 4-6
- หรือ bypass Hangfire ใช้ direct API calls

### 2. Whisper Service (1 instance) ⚠️ **Potential**

**ปัญหา**: อาจไม่รองรับ concurrent requests มาก

**ผลกระทบ**:
- ถ้าแต่ละ task ส่ง 120 requests → อาจ overload

**แนวทางแก้ไข**:
- เพิ่ม Whisper instances
- Optimize batch processing

### 3. Queue Processing ⚠️ **Minor**

**Current**: 6 concurrent tasks (2 workers × prefetch=3)

**ผลกระทบ**:
- ถ้ามี 100 tasks → ต้องรอ ~167 นาที (2.8 ชั่วโมง)

**แนวทางแก้ไข**:
- เพิ่ม workers เป็น 3-4
- เพิ่ม prefetch_count (ระวัง memory)

---

## 🧪 วิธีทดสอบ Performance

### วิธีที่ 1: Full Performance Test (แนะนำ)

ทดสอบแบบเต็มรูปแบบ - ส่ง requests และรอผลลัพธ์

**ใช้สคริปต์**: `scripts/performance_test.py`

```bash
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 100 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 10 \
  --output performance_report.json
```

**ข้อดี**:
- ✅ วัดเวลาได้ครบถ้วน
- ✅ ได้ metrics ทั้งหมด
- ✅ วิเคราะห์ bottlenecks ได้

**ข้อเสีย**:
- ⏱️ ใช้เวลานาน (3-7 ชั่วโมง)

### วิธีที่ 2: Quick Load Test

ทดสอบแบบเร็ว - ส่ง requests ไปแล้วไม่รอผลลัพธ์

**ใช้สคริปต์**: `scripts/quick_load_test.py`

```bash
python scripts/quick_load_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 100 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 10
```

**ข้อดี**:
- ✅ เร็ว (5-10 นาที)
- ✅ ทดสอบว่า API รองรับ load ได้หรือไม่

**ข้อเสีย**:
- ❌ ไม่ได้วัด processing time
- ❌ ไม่ได้วิเคราะห์ bottlenecks

### วิธีที่ 3: Monitoring Tools

ใช้ tools เช่น:
- **RabbitMQ Management UI**: ตรวจสอบ queue length
- **Hangfire Dashboard**: ตรวจสอบ jobs status
- **Docker Stats**: ตรวจสอบ resource usage
- **Grafana/Prometheus**: Monitoring dashboard

---

## 📈 Metrics ที่ควรวัด

### 1. Time Metrics
- ✅ **Total Processing Time**: เวลาจาก request → completed
- ✅ **Queue Waiting Time**: เวลารอใน Hangfire/RabbitMQ queue
- ✅ **Processing Time**: เวลาที่ใช้ในการประมวลผลจริง
- ✅ **Chunk Processing Time**: เวลาต่อ chunk

### 2. Throughput Metrics
- ✅ **Jobs per Minute**: จำนวน jobs ที่ประมวลผลได้ต่อนาที
- ✅ **Tasks per Minute**: จำนวน tasks ที่ workers ประมวลผลได้ต่อนาที
- ✅ **Chunks per Minute**: จำนวน chunks ที่ Whisper ประมวลผลได้ต่อนาที

### 3. Resource Metrics
- ✅ **CPU Usage**: แต่ละ component
- ✅ **Memory Usage**: แต่ละ component
- ✅ **Queue Length**: Hangfire, RabbitMQ
- ✅ **Error Rate**: จำนวน errors ต่อจำนวน requests

---

## 🔧 Recommendations

### Short-term (สำหรับ 80-120 Users)

1. **เพิ่ม Hangfire WorkerCount**: 2 → 4-6
   - ต้องเพิ่ม resources ให้ Backend

2. **เพิ่ม Video Workers**: 2 → 3-4
   - ต้องเพิ่ม resources ให้ Transcription Service

3. **Optimize Whisper Processing**:
   - เพิ่ม batch processing
   - Parallel chunk processing

### Long-term (Scale Up)

1. **Horizontal Scaling**:
   - เพิ่ม Transcription Service instances
   - Load balancing

2. **Separate Whisper Service**:
   - แยก Whisper service เป็น cluster
   - Auto-scaling based on queue length

3. **Queue Optimization**:
   - Priority queues (สำหรับ urgent jobs)
   - Job scheduling (distribute load)

---

## 📚 เอกสารที่เกี่ยวข้อง

### เอกสารหลัก

1. **[Performance Testing Analysis](./PERFORMANCE_TESTING_ANALYSIS.md)**
   - วิเคราะห์ Flow การทำงาน
   - การคำนวณเวลา
   - Bottleneck analysis

2. **[Performance Testing Guide](../scripts/PERFORMANCE_TESTING_GUIDE.md)**
   - วิธีใช้งานสคริปต์ทดสอบ
   - การตีความผลลัพธ์
   - Troubleshooting

3. **[Transcription Performance Optimization](./TRANSCRIPTION_PERFORMANCE_OPTIMIZATION.md)**
   - การ optimize ที่ทำไปแล้ว
   - Architecture flow

### สคริปต์ทดสอบ

1. **`scripts/performance_test.py`**
   - Full performance test
   - วัดเวลาและ metrics ครบถ้วน

2. **`scripts/quick_load_test.py`**
   - Quick load test
   - ทดสอบว่าระบบรองรับ load ได้หรือไม่

---

## 🚀 Quick Start

### ขั้นตอนที่ 1: เตรียมการ

```bash
# 1. ติดตั้ง dependencies
cd transcription-close-caption-service/scripts
pip install aiohttp aiofiles python-dateutil

# 2. เตรียมวีดิโอทดสอบ (1 ชั่วโมง)
# หรือใช้วีดิโอทดสอบที่มีอยู่

# 3. เตรียม authentication token (ถ้ามี)
export AUTH_TOKEN="your-token-here"
```

### ขั้นตอนที่ 2: ทดสอบเบื้องต้น (10 users)

```bash
# ทดสอบ 10 users ก่อน
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 10 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 5
```

### ขั้นตอนที่ 3: ทดสอบเต็มรูปแบบ (80-120 users)

```bash
# ทดสอบ 100 users
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 100 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 10 \
  --output performance_report_$(date +%Y%m%d_%H%M%S).json
```

### ขั้นตอนที่ 4: วิเคราะห์ผลลัพธ์

1. ดู Success Rate (ควร ≥ 95%)
2. ดู Processing Time (ควร ≤ 15 นาทีต่อวิดีโอ)
3. ดู Throughput (ควร ≥ 10 jobs ต่อชั่วโมง)
4. วิเคราะห์ Errors และ Bottlenecks

---

## ✅ Checklist

### ก่อนทดสอบ
- [ ] ติดตั้ง dependencies
- [ ] เตรียมวีดิโอทดสอบ
- [ ] เตรียม authentication token
- [ ] ตรวจสอบ backend URL
- [ ] แจ้งทีมก่อนทดสอบ

### ระหว่างทดสอบ
- [ ] Monitor RabbitMQ queue
- [ ] Monitor Hangfire dashboard
- [ ] Monitor Docker stats
- [ ] ตรวจสอบ logs

### หลังทดสอบ
- [ ] วิเคราะห์ผลลัพธ์
- [ ] ระบุ bottlenecks
- [ ] แนวทางแก้ไข
- [ ] บันทึกผลลัพธ์

---

## 📞 Support

หากพบปัญหาหรือต้องการความช่วยเหลือ:

1. ตรวจสอบ logs
2. ตรวจสอบเอกสาร
3. ติดต่อทีมพัฒนา

---

**📅 สร้างเมื่อ**: {{ datetime.now().strftime('%Y-%m-%d %H:%M:%S') }}
**🔖 Version**: 1.0

