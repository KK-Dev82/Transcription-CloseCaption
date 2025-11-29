# 🧪 คู่มือการทดสอบ Performance และ Concurrency

## 📋 ภาพรวม

เอกสารนี้อธิบายวิธีการทดสอบ performance และ concurrency ของ Transcription Service สำหรับการรองรับ **80-120 users** พร้อมกัน กับ **วีดิโอความยาว 1 ชั่วโมง**

---

## 🎯 วัตถุประสงค์

1. ทดสอบว่าระบบสามารถรองรับ concurrent requests ได้กี่งานพร้อมกัน
2. วัดเวลาที่ใช้ในการประมวลผล transcription สำหรับวิดีโอ 1 ชั่วโมง
3. ระบุ bottlenecks และข้อจำกัดของระบบ
4. ประเมินความจำเป็นในการ scale up

---

## 📦 Prerequisites

### 1. ติดตั้ง Dependencies

```bash
cd transcription-close-caption-service/scripts
pip install aiohttp aiofiles python-dateutil
```

### 2. เตรียมวีดิโอทดสอบ

- **ขนาด**: วีดิโอความยาว 1 ชั่วโมง (หรือใช้วีดิโอทดสอบที่มีอยู่)
- **รูปแบบ**: MP4 (หรือรูปแบบที่ระบบรองรับ)
- **ขนาดไฟล์**: ประมาณ 500MB - 2GB

**ตัวอย่าง**: ใช้วีดิโอทดสอบที่มีอยู่
```bash
# ตรวจสอบวีดิโอทดสอบที่มีอยู่
ls -lh transcription-close-caption-service/test_video*.mp4
ls -lh transcription-close-caption-service/test-files/*.mp4
```

### 3. เตรียม Authentication Token

```bash
# รับ token จาก Backend API (ถ้ามี)
export AUTH_TOKEN="your-auth-token-here"
```

---

## 🚀 วิธีใช้งาน

### Method 1: Full Performance Test (แนะนำ)

ทดสอบแบบเต็มรูปแบบ - ส่ง requests และรอผลลัพธ์

```bash
python scripts/performance_test.py \
  --backend-url http://localhost:5000 \
  --num-users 100 \
  --video-file path/to/test_video_1hour.mp4 \
  --auth-token $AUTH_TOKEN \
  --language th \
  --model-size base \
  --max-concurrent 10 \
  --output performance_report.json
```

**พารามิเตอร์**:
- `--backend-url`: URL ของ Backend API (ต้องมี trailing slash)
- `--num-users`: จำนวน users ที่ต้องการทดสอบ (default: 100)
- `--video-file`:  path ไปยังไฟล์วีดิโอทดสอบ
- `--auth-token`: Authentication token (optional)
- `--language`: ภาษา (default: th)
- `--model-size`: ขนาด model (default: base)
- `--max-concurrent`: จำนวน concurrent requests สูงสุด (default: 10)
- `--output`: ไฟล์ output สำหรับ report (default: performance_report_TIMESTAMP.json)

**ตัวอย่าง**:
```bash
# ทดสอบ 100 users พร้อมกัน
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 100 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 10

# ทดสอบ 80 users (conservative)
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 80 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 8

# ทดสอบ 120 users (stress test)
python scripts/performance_test.py \
  --backend-url http://10.200.22.61:5000 \
  --num-users 120 \
  --video-file test-files/test_video_1hour.mp4 \
  --max-concurrent 12
```

### Method 2: Quick Load Test (ไม่รอ completion)

ทดสอบแบบเร็ว - ส่ง requests ไปแล้วไม่รอผลลัพธ์ (เหมาะสำหรับทดสอบว่า API รองรับ load ได้หรือไม่)

```bash
python scripts/quick_load_test.py \
  --backend-url http://localhost:5000 \
  --num-users 100 \
  --video-file path/to/test_video_1hour.mp4 \
  --auth-token $AUTH_TOKEN
```

---

## 📊 การตีความผลลัพธ์

### 1. Test Summary

```
Test Summary:
  Total Users: 100
  Successful: 95
  Failed: 5
  Success Rate: 95.00%
  Total Test Time: 425.50 minutes
```

**คำอธิบาย**:
- **Total Users**: จำนวน users ทั้งหมดที่ทดสอบ
- **Successful**: จำนวน jobs ที่สำเร็จ
- **Failed**: จำนวน jobs ที่ล้มเหลว
- **Success Rate**: อัตราส่วนความสำเร็จ (%)
- **Total Test Time**: เวลาทั้งหมดที่ใช้ในการทดสอบ

### 2. Throughput

```
Throughput:
  Jobs per Minute: 0.22
  Jobs per Hour: 13.33
```

**คำอธิบาย**:
- **Jobs per Minute**: จำนวน jobs ที่ประมวลผลได้ต่อนาที
- **Jobs per Hour**: จำนวน jobs ที่ประมวลผลได้ต่อชั่วโมง

**การประเมิน**:
- ถ้า Jobs per Hour = 13.33 → ใช้เวลา ~7.5 ชั่วโมง สำหรับ 100 jobs
- ถ้า Jobs per Hour = 20 → ใช้เวลา ~5 ชั่วโมง สำหรับ 100 jobs

### 3. Metrics

#### Upload Times
```
upload:
  mean: 15.23s
  median: 14.50s
  min: 12.30s
  max: 25.10s
```

**คำอธิบาย**:
- **mean**: เวลาเฉลี่ยในการอัปโหลดไฟล์
- **median**: เวลากลางในการอัปโหลด
- **min/max**: เวลาสั้นที่สุด/ยาวที่สุด

#### Processing Times
```
transcription_processing:
  mean: 635.50s
  median: 620.00s
  min: 580.00s
  max: 720.00s
```

**คำอธิบาย**:
- เวลาเฉลี่ยในการประมวลผล transcription (ประมาณ 10-12 นาทีต่อวิดีโอ 1 ชั่วโมง)
- ถ้า mean > 600s (10 นาที) → ระบบอาจช้าเกินไป

#### Total Processing Times
```
total_processing:
  mean: 650.00s
  median: 635.00s
  min: 600.00s
  max: 750.00s
  p95: 720.00s
  p99: 745.00s
```

**คำอธิบาย**:
- เวลาทั้งหมดจาก upload → completed
- **p95/p99**: Percentile 95/99 (95% หรือ 99% ของ jobs ใช้เวลาไม่เกินค่านี้)

### 4. Errors

```
Errors (5):
  User 12: Upload failed: Connection timeout
  User 34: Start transcription failed: HTTP 429 - Too Many Requests
  ...
```

**การประเมิน**:
- ถ้ามี errors มากกว่า 10% → ระบบอาจ overload
- ถ้ามี HTTP 429 (Too Many Requests) → ต้องลด concurrent requests
- ถ้ามี Connection timeout → ต้องตรวจสอบ network หรือ timeout settings

---

## 🔍 Monitoring ระหว่างทดสอบ

### 1. RabbitMQ Queue

ตรวจสอบ queue length:
```bash
# SSH เข้า RabbitMQ server
rabbitmqctl list_queues name messages consumers

# ดู queue transcription_queue
rabbitmqctl list_queues | grep transcription_queue
```

**การประเมิน**:
- ถ้า queue length > 50 → อาจต้องเพิ่ม workers
- ถ้า queue length = 0 แต่ jobs ยังไม่เสร็จ → workers อาจช้า

### 2. Hangfire Dashboard

ตรวจสอบ Backend Hangfire dashboard:
- URL: `http://backend-url/hangfire`
- ดูจำนวน jobs ที่ pending/processing/completed

### 3. Docker Stats

ตรวจสอบ resource usage:
```bash
# ตรวจสอบ CPU และ Memory
docker stats transcription-api video-worker-1 video-worker-2 transcription-whisper

# ตรวจสอบเฉพาะ transcription services
docker stats $(docker ps --filter "name=transcription" --format "{{.Names}}")
```

### 4. Backend Logs

ตรวจสอบ logs:
```bash
# Transcription Service logs
docker logs -f transcription-api
docker logs -f video-worker-1
docker logs -f video-worker-2

# Backend logs
# (ขึ้นกับ deployment method)
```

---

## 📈 การวิเคราะห์ผลลัพธ์

### สถานการณ์ที่ 1: Success Rate ต่ำ (< 90%)

**สาเหตุที่เป็นไปได้**:
1. API overload (HTTP 429)
2. Resource exhaustion (memory/CPU)
3. Network issues
4. Timeout settings

**แนวทางแก้ไข**:
- ลด `--max-concurrent` (เช่น 10 → 5)
- เพิ่ม timeout settings
- เพิ่ม resources (CPU/Memory)
- Scale up services

### สถานการณ์ที่ 2: Processing Time นาน (> 15 นาทีต่อวิดีโอ)

**สาเหตุที่เป็นไปได้**:
1. Queue congestion
2. Whisper service bottleneck
3. Workers ไม่เพียงพอ
4. Resource contention

**แนวทางแก้ไข**:
- เพิ่ม Video Workers (2 → 3-4)
- เพิ่ม Hangfire WorkerCount (2 → 4-6)
- เพิ่ม Whisper instances
- Optimize chunk processing

### สถานการณ์ที่ 3: Queue Length สูง (> 50)

**สาเหตุที่เป็นไปได้**:
1. Workers ไม่เพียงพอ
2. Processing time ต่อ job นานเกินไป
3. Prefetch count ต่ำเกินไป

**แนวทางแก้ไข**:
- เพิ่ม Video Workers
- เพิ่ม prefetch_count
- Optimize processing logic

---

## 🎯 เป้าหมายการทดสอบ

### Baseline (Current System)
- **Success Rate**: ≥ 95%
- **Processing Time**: ≤ 15 นาทีต่อวิดีโอ 1 ชั่วโมง
- **Throughput**: ≥ 10 jobs ต่อชั่วโมง

### Target (Optimized System)
- **Success Rate**: ≥ 99%
- **Processing Time**: ≤ 10 นาทีต่อวิดีโอ 1 ชั่วโมง
- **Throughput**: ≥ 20 jobs ต่อชั่วโมง

---

## 🔧 Troubleshooting

### ปัญหา: Connection Timeout

**แก้ไข**:
```python
# เพิ่ม timeout ใน aiohttp.ClientSession
timeout = aiohttp.ClientTimeout(total=7200)  # 2 hours
```

### ปัญหา: Too Many Requests (HTTP 429)

**แก้ไข**:
1. ลด `--max-concurrent` จาก 10 → 5
2. เพิ่ม delay ระหว่าง requests
3. ใช้ rate limiting

### ปัญหา: Memory Exhaustion

**แก้ไข**:
1. ลด `--max-concurrent`
2. เพิ่ม memory limits ใน docker-compose
3. Scale horizontally

---

## 📝 Best Practices

1. **เริ่มจากการทดสอบจำนวนน้อยก่อน**:
   ```bash
   # ทดสอบ 10 users ก่อน
   python scripts/performance_test.py --num-users 10 ...
   ```

2. **ใช้วีดิโอทดสอบที่มีขนาดเหมาะสม**:
   - ไม่ใหญ่เกินไป (≤ 2GB)
   - ไม่เล็กเกินไป (≥ 100MB)

3. **Monitor resources ระหว่างทดสอบ**:
   - CPU/Memory usage
   - Queue length
   - Error rates

4. **บันทึกผลลัพธ์ทุกครั้ง**:
   ```bash
   --output performance_report_$(date +%Y%m%d_%H%M%S).json
   ```

5. **ทดสอบในช่วงเวลาที่เหมาะสม**:
   - ไม่ใช่เวลา peak hours
   - แจ้งทีมก่อนทดสอบ

---

## 📚 เอกสารที่เกี่ยวข้อง

- [Performance Testing Analysis](./PERFORMANCE_TESTING_ANALYSIS.md)
- [Transcription Performance Optimization](../docs/TRANSCRIPTION_PERFORMANCE_OPTIMIZATION.md)

---

## 🆘 Support

หากพบปัญหาหรือต้องการความช่วยเหลือ:
1. ตรวจสอบ logs
2. ตรวจสอบเอกสาร
3. ติดต่อทีมพัฒนา

