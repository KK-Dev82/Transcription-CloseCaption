# 📊 การวิเคราะห์ Performance และ Concurrency สำหรับ Transcription Service

## 🎯 วัตถุประสงค์

ทดสอบการรองรับ **80-120 users พร้อมกัน** กับ **วีดิโอความยาว 1 ชั่วโมง** เพื่อประเมิน:
- เวลาที่ใช้ในการประมวลผลทั้งหมด
- ระบบสามารถรองรับ concurrent requests ได้กี่งานพร้อมกัน
- Bottleneck และข้อจำกัดของระบบ

---

## 🔄 Flow การทำงาน (จาก Senate-Backend)

### 1. User Upload & Start Transcription
```
User (Frontend)
  ↓ POST /api/transcription/upload/stream
Senate-Backend (TranscriptionController.UploadStreamAsync)
  ↓ ส่งไฟล์ไปยัง FileService
FileService → return FileId
  ↓ POST /api/transcription/start (fileId, fileName, language, modelSize)
Senate-Backend (TranscriptionController.StartTranscription)
  ↓ สร้าง TranscriptionJob
Hangfire Queue (ProcessTranscriptionAsync) [WorkerCount=2]
```

### 2. Processing Flow
```
Hangfire Background Job (max 2 concurrent)
  ↓ POST {TranscriptionUrl}/transcribe/
Transcription Service API (/transcribe/)
  ↓ ส่ง task ไปยัง RabbitMQ
RabbitMQ Queue (transcription_queue)
  ↓ (2 workers × prefetch_count=3)
Video Workers (video-worker-1, video-worker-2)
  ↓ ดาวน์โหลดไฟล์จาก FileService
  ↓ แบ่งเป็น audio chunks (chunk_duration=30s)
  ↓ POST {WHISPER_API_URL}/transcribe/ (แต่ละ chunk)
Whisper Service API (2.5G RAM, 1.4 CPU)
  ↓ รวมผลลัพธ์ (merge_transcriptions)
  ↓ POST {callback_url}/api/transcription/webhook/completed
Senate-Backend (WebhookCompleted)
  ↓ อัปเดต TranscriptionJob → Status: completed
  ↓ SignalR Notification → User
```

---

## 📐 สถาปัตยกรรมปัจจุบัน

### Resource Allocation (Staging Server: 4 cores, 7.75GB RAM)

| Component | Instances | Memory | CPU | Concurrency |
|-----------|-----------|--------|-----|-------------|
| **API Service** | 1 | 1G | 0.6 | - |
| **Video Worker** | 2 | 3G each | 1.2 each | prefetch_count=3 |
| **Whisper Service** | 1 | 2.5G | 1.4 | - |
| **Redis** | 1 | 0.5G | 0.1 | - |
| **Total** | - | **7.5G** | **3.8** | - |

### Concurrency Settings

1. **Hangfire WorkerCount**: 2
   - จำกัด concurrent transcription jobs เป็น **2 jobs พร้อมกัน**

2. **RabbitMQ Workers**: 2
   - `video-worker-1`, `video-worker-2`
   - `prefetch_count = 3` (จาก video_worker.py line 117)
   - **Total concurrent tasks = 2 workers × 3 prefetch = 6 งานพร้อมกัน**

3. **Whisper Service**:
   - 1 instance, ไม่มี concurrent limit ที่ชัดเจน
   - แต่ละ transcription task จะส่งหลาย requests (1 request ต่อ chunk)

---

## 🧮 การคำนวณสำหรับวิดีโอ 1 ชั่วโมง

### ข้อมูลพื้นฐาน
- **วีดิโอความยาว**: 1 ชั่วโมง = 3600 วินาที
- **Chunk Duration**: 30 วินาที (default)
- **จำนวน Chunks**: 3600 / 30 = **120 chunks**

### เวลาที่ใช้ในการประมวลผล

#### 1. เวลาต่อ Chunk (ประมาณการ)
- **Whisper Processing**: ~2-5 วินาทีต่อ chunk (ขึ้นกับ model_size และ hardware)
- **Overhead**: การดาวน์โหลดไฟล์, แบ่ง chunks, รวมผลลัพธ์ (~10-30 วินาที)

#### 2. การประมวลผลแบบ Sequential
```
Total Time = 120 chunks × 5 seconds = 600 seconds = 10 นาที
+ Overhead (30s) = 630 seconds = 10.5 นาที ต่อ 1 วิดีโอ
```

#### 3. การประมวลผลแบบ Concurrent (Ideal)
- ถ้าทำ concurrent 6 chunks พร้อมกัน:
```
Total Time = (120 chunks / 6 concurrent) × 5 seconds = 20 × 5 = 100 seconds = 1.7 นาที
+ Overhead = 130 seconds = 2.2 นาที ต่อ 1 วิดีโอ
```

**⚠️ หมายเหตุ**: การคำนวณนี้เป็นแบบ Ideal แต่ในความเป็นจริง:
- Whisper API อาจไม่รองรับ concurrent requests มาก
- Network latency
- Resource contention
- **คาดหวังจริง: 5-15 นาทีต่อวิดีโอ 1 ชั่วโมง**

---

## 📊 สถานการณ์ทดสอบ: 80-120 Users

### สมมติฐาน
- **80-120 users** ส่ง transcription requests พร้อมกัน
- **วีดิโอ 1 ชั่วโมง** ต่อ user
- **System Capacity**: 
  - Hangfire: 2 concurrent jobs
  - Workers: 6 concurrent tasks (2 workers × 3 prefetch)

### Timeline การประมวลผล

#### Phase 1: Queue Building (0-10 นาที)
```
100 users → 100 jobs in Hangfire queue
Hangfire processes: 2 jobs at a time
Time to process all jobs in queue: 100 / 2 = 50 cycles
If each job takes 5 minutes → 50 × 5 = 250 minutes = 4.2 hours
```

#### Phase 2: RabbitMQ Queue Processing
```
Each Hangfire job creates 1 task in RabbitMQ queue
100 tasks in transcription_queue
Workers process: 6 tasks at a time
Time to process all tasks: 100 / 6 = 16.7 cycles
If each task takes 10 minutes → 16.7 × 10 = 167 minutes = 2.8 hours
```

#### Phase 3: Chunk Processing (ภายในแต่ละ task)
```
Each task processes 120 chunks
If chunks processed sequentially: 120 × 5s = 600s = 10 minutes
If chunks processed concurrently: ~2-5 minutes
```

### ⏱️ เวลารวมที่คาดหวัง

**Scenario 1: Sequential Processing (Pessimistic)**
```
Total Time = Queue Time + Processing Time
           = 250 minutes (Hangfire) + 167 minutes (Workers)
           = 417 minutes = 6.95 hours
```

**Scenario 2: Optimized Processing (Realistic)**
```
Total Time = Max(Queue Time, Processing Time) + Overhead
           = Max(250 min, 167 min) + 10 min per job
           = 250 + (10 × 100 jobs / 6 concurrent) 
           = 250 + 167 = 417 minutes = 6.95 hours
```

**Scenario 3: Best Case (Optimistic)**
```
ถ้า Hangfire และ Workers ทำงาน optimal:
Total Time = 100 jobs / 6 concurrent × 10 minutes
           = 16.7 × 10 = 167 minutes = 2.8 hours
```

**🎯 สรุป: เวลาที่คาดหวังสำหรับ 100 users = 3-7 ชั่วโมง**

---

## 🔍 Bottleneck Analysis

### 1. Hangfire WorkerCount = 2
- **Impact**: จำกัดการส่ง jobs ไปยัง Transcription Service เป็น 2 jobs พร้อมกัน
- **Bottleneck**: ถ้ามี 100 jobs → ต้องรอ ~250 minutes
- **Solution**: 
  - เพิ่ม WorkerCount เป็น 4-6 (ถ้า resources เพียงพอ)
  - หรือใช้ direct API calls แทน Hangfire (bypass queue)

### 2. RabbitMQ Workers = 2 (prefetch=3)
- **Current**: 6 concurrent tasks
- **Bottleneck**: ถ้ามี 100 tasks → ต้องรอ ~167 minutes
- **Solution**: 
  - เพิ่ม workers เป็น 3-4
  - หรือเพิ่ม prefetch_count (แต่ต้องระวัง memory)

### 3. Whisper Service (1 instance)
- **Bottleneck**: ถ้าแต่ละ task ส่ง 120 requests → อาจ overload
- **Solution**: 
  - เพิ่ม Whisper instances
  - หรือใช้ batch processing
  - หรือเพิ่ม concurrent processing ใน Whisper API

### 4. Network & File Download
- **Bottleneck**: การดาวน์โหลดไฟล์จาก FileService
- **Solution**: 
  - Caching
  - Parallel downloads
  - CDN หรือ local storage

---

## 🧪 วิธีทดสอบ Performance

### Method 1: Load Testing Script (แนะนำ)

สร้างสคริปต์ Python ที่:
1. ส่ง transcription requests 80-120 requests พร้อมกัน
2. ใช้วีดิโอทดสอบความยาว 1 ชั่วโมง
3. วัดเวลาและ monitor progress

**ไฟล์**: `scripts/performance_test.py`

### Method 2: Stress Testing ด้วย Artillery/Locust

ใช้ load testing tools เช่น:
- **Artillery**: HTTP load testing
- **Locust**: Python-based load testing
- **k6**: Modern load testing tool

### Method 3: Real-world Simulation

1. สร้าง 100 test users
2. ส่ง transcription requests ตามเวลาจริง
3. Monitor queue length, processing time, errors

---

## 📈 Metrics ที่ควรวัด

### 1. Time Metrics
- **Total Processing Time**: เวลาจาก request → completed
- **Queue Waiting Time**: เวลารอใน Hangfire queue
- **Processing Time**: เวลาที่ใช้ในการประมวลผลจริง
- **Chunk Processing Time**: เวลาต่อ chunk

### 2. Throughput Metrics
- **Jobs per Minute**: จำนวน jobs ที่ประมวลผลได้ต่อนาที
- **Tasks per Minute**: จำนวน tasks ที่ workers ประมวลผลได้ต่อนาที
- **Chunks per Minute**: จำนวน chunks ที่ Whisper ประมวลผลได้ต่อนาที

### 3. Resource Metrics
- **CPU Usage**: แต่ละ component
- **Memory Usage**: แต่ละ component
- **Queue Length**: Hangfire, RabbitMQ
- **Error Rate**: จำนวน errors ต่อจำนวน requests

### 4. User Experience Metrics
- **Time to First Result**: เวลาที่ user เห็นผลลัพธ์แรก
- **Progress Updates**: ความถี่ของ progress updates
- **Completion Rate**: % ของ jobs ที่สำเร็จ

---

## 🔧 Recommendations

### สำหรับ 80-120 Users (Short-term)

1. **เพิ่ม Hangfire WorkerCount**: 2 → 4-6
   - ต้องเพิ่ม resources ให้ Backend

2. **เพิ่ม Video Workers**: 2 → 3-4
   - ต้องเพิ่ม resources ให้ Transcription Service

3. **Optimize Whisper Processing**:
   - เพิ่ม batch processing
   - Parallel chunk processing

### สำหรับ Scale Up (Long-term)

1. **Horizontal Scaling**:
   - เพิ่ม Transcription Service instances
   - Load balancing

2. **Separate Whisper Service**:
   - แยก Whisper service เป็น cluster
   - Auto-scaling based on queue length

3. **Queue Optimization**:
   - Priority queues (สำหรับ urgent jobs)
   - Job scheduling (distribute load)

4. **Caching & Optimization**:
   - Cache audio chunks
   - Reuse transcription results

---

## 📝 สรุป

### การรองรับ 80-120 Users

**Current Capacity**:
- Hangfire: 2 concurrent jobs → **Bottleneck**
- Workers: 6 concurrent tasks → **Adequate**
- Whisper: 1 instance → **Potential Bottleneck**

**Expected Time**:
- **3-7 ชั่วโมง** สำหรับ 100 jobs (วีดิโอ 1 ชั่วโมง)

**Recommendations**:
1. เพิ่ม Hangfire WorkerCount เป็น 4-6
2. เพิ่ม Video Workers เป็น 3-4
3. Monitor และ optimize Whisper processing
4. ใช้ load testing script เพื่อทดสอบจริง

### Next Steps

1. ✅ สร้าง load testing script
2. ✅ ทดสอบกับ 10-20 users ก่อน
3. ✅ Monitor metrics และ identify bottlenecks
4. ✅ Scale up ตามผลลัพธ์

