# 📊 Architecture Review: Multi-GPU Transcription Service

## ✅ สรุป: คำแนะนำมีประโยชน์และถูกต้อง

คำแนะนำที่ได้รับ**มีประโยชน์มาก** และ**สอดคล้องกับสิ่งที่เราทำอยู่แล้ว** โดยมีจุดที่ควรปรับปรุงเพิ่มเติม

---

## 🔍 เปรียบเทียบ: คำแนะนำ vs สิ่งที่ทำอยู่

### 1. แบบ A: Worker แยกพอร์ต (Endpoint แยก)

**คำแนะนำ:**
- Worker-0 ฟังที่ `:8010` (GPU0)
- Worker-1 ฟังที่ `:8011` (GPU1)
- Dispatcher รับ request แล้ว "ยิงต่อ" ไปยัง worker

**สิ่งที่ทำอยู่:**
- ✅ Worker GPU 0: Port 8010 (`CUDA_VISIBLE_DEVICES=0`)
- ✅ Worker GPU 1: Port 8011 (`CUDA_VISIBLE_DEVICES=1`)
- ✅ Dispatcher: `TranscriptionService` ส่ง chunks ไปยัง workers
- ✅ Internal endpoint: `/api/internal/transcribe`

**สถานะ:** ✅ **ทำแล้ว**

---

### 2. Dispatch Policy

**คำแนะนำ:**
- Round-robin (เหมาะกับ chunk เวลาใกล้เคียงกัน)
- Least-loaded (ดีกว่าเมื่อ chunk time ไม่เท่ากัน/หลาย user พร้อมกัน)

**สิ่งที่ทำอยู่:**
```python
# ตอนนี้ใช้ round-robin
worker_url = worker_urls[chunk_index % num_workers]
```

**สถานะ:** ⚠️ **ใช้ round-robin อยู่ ควรอัพเกรดเป็น least-loaded**

---

### 3. Parallel Processing

**คำแนะนำ:**
- แยกเป็น 2 process และแต่ละ process เห็น GPU คนละตัว → GPU0 และ GPU1 ทำงานพร้อมกันจริง

**สิ่งที่ทำอยู่:**
- ✅ แต่ละ worker process มี GPU ของตัวเอง
- ✅ Chunks ถูกส่งไปยัง workers พร้อมกัน (async)
- ✅ ผลลัพธ์: GPU 0 และ GPU 1 ทำงานพร้อมกัน (เห็นจาก test results)

**สถานะ:** ✅ **ทำแล้วและทำงานได้จริง**

---

### 4. ไม่สลับ CUDA_VISIBLE_DEVICES ใน Runtime

**คำแนะนำ:**
- ห้ามสลับ `CUDA_VISIBLE_DEVICES` ระหว่าง runtime ใน process เดียว
- ใช้ "1 GPU = 1 Process" แทน

**สิ่งที่ทำอยู่:**
- ✅ ไม่มีการเปลี่ยน `CUDA_VISIBLE_DEVICES` ใน runtime
- ✅ แต่ละ worker process fix GPU ด้วย `CUDA_VISIBLE_DEVICES` ตอนเริ่ม process
- ✅ ลบการเปลี่ยน env ใน `transcribe_chunk()` แล้ว

**สถานะ:** ✅ **ทำแล้ว**

---

## 📈 ผลการทดสอบ

### Test 1: Single Request (v30-1.mp4, 30 นาที)
- **เวลา:** 73.0s (1m 13s)
- **Model:** base
- **GPU Utilization:**
  - GPU 0: 41.9% avg
  - GPU 1: 41.8% avg
- **Text Quality:** ✅ Readable, 352 words, มีภาษาไทย

### Test 2: 5 Concurrent Requests
- **Total Time:** 354.8s (5m 54s)
- **Successful:** 2/5 (3 requests timeout)
- **Avg Task Time:** 348.8s
- **GPU Utilization:**
  - GPU 0: 42.3% avg
  - GPU 1: 41.6% avg

**ปัญหา:** มี 3 requests ที่ timeout (10s) - อาจเป็นเพราะ:
1. Service ยังไม่พร้อมรับ concurrent requests สูง
2. ควรเพิ่ม timeout หรือปรับ connection pool

---

## 🎯 คำแนะนำที่ควรทำเพิ่ม

### 1. ⚠️ **อัพเกรดเป็น Least-Loaded Policy** (สำคัญ)

**เหตุผล:**
- ตอนนี้ใช้ round-robin ซึ่งเหมาะกับ chunk เวลาใกล้เคียงกัน
- แต่เมื่อมี 25 requests พร้อมกัน → chunks อาจมีเวลาต่างกัน
- Least-loaded จะบาลานซ์โหลดได้ดีกว่า

**วิธีทำ:**
```python
# เพิ่ม worker load tracking
worker_loads = {url: 0 for url in worker_urls}  # Track inflight tasks

async def get_least_loaded_worker():
    """เลือก worker ที่มี load น้อยที่สุด"""
    return min(worker_loads.items(), key=lambda x: x[1])[0]

async def transcribe_with_semaphore(chunk_path, chunk_index):
    async with task_semaphore:
        worker_url = await get_least_loaded_worker()
        worker_loads[worker_url] += 1  # เพิ่ม load
        try:
            result = await transcribe_chunk(chunk_path, chunk_index, worker_url=worker_url)
            return result
        finally:
            worker_loads[worker_url] -= 1  # ลด load
```

---

### 2. ⚠️ **เพิ่ม Connection Pool และ Timeout**

**ปัญหา:** 3/5 requests timeout

**วิธีแก้:**
```python
# ใช้ connection pool แบบ persistent
connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
timeout = aiohttp.ClientTimeout(total=1800, connect=30)
session = aiohttp.ClientSession(connector=connector, timeout=timeout)
```

---

### 3. ✅ **เพิ่ม Health Check และ Retry Logic**

**วิธีทำ:**
```python
async def get_healthy_worker():
    """เลือก worker ที่ healthy"""
    for url in worker_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=2) as resp:
                    if resp.status == 200:
                        return url
        except:
            continue
    raise Exception("No healthy workers available")
```

---

### 4. 📊 **เพิ่ม Metrics/Monitoring**

- Track worker response time
- Track worker error rate
- Track queue depth per worker

---

## 🚀 แนวทางสำหรับ 25 Requests

### การวิเคราะห์

จากผลการทดสอบ:
- Single request: 73.0s
- Avg concurrent (5 requests): 348.8s
- Estimated (25 requests, linear): 1743.9s (29m)
- Estimated (25 requests, 2 GPUs): 1046.3s (17m)

**คำตอบ:** ✅ **ทำได้** แต่ควร:
1. อัพเกรดเป็น least-loaded policy
2. เพิ่ม connection pool
3. เพิ่ม retry logic
4. Monitor worker health

---

## 🎬 Live Streaming Transcription (RTMP Close Caption)

### คำแนะนำ: เพิ่ม GPU 1 ตัวสำหรับ Priority Tasks

**Architecture:**
```
GPU 0, 1: Batch transcription (VOD) - Port 8010, 8011
GPU 2: Live streaming (priority, low latency) - Port 8012
```

**ข้อดี:**
- ✅ Isolated resources สำหรับ real-time processing
- ✅ ไม่รบกวน batch jobs
- ✅ Latency ต่ำสำหรับ live streams

**Implementation:**
1. เพิ่ม worker GPU 2 (port 8012) ด้วย `CUDA_VISIBLE_DEVICES=2`
2. สร้าง priority queue หรือ routing logic
3. Route live streaming requests ไปยัง GPU 2
4. ใช้ `chunk_duration` เล็กกว่า (15-30s) สำหรับ live streams

**โค้ดตัวอย่าง:**
```python
# ใน TranscriptionService
if request.get("priority") == "live_stream":
    worker_urls = ["http://127.0.0.1:8012"]  # GPU 2 สำหรับ live
    chunk_duration = 15  # เล็กกว่า VOD
else:
    worker_urls = os.getenv('WHISPER_WORKER_URLS', '...').split(',')
    chunk_duration = 90
```

---

## 📝 สรุป

### ✅ สิ่งที่ทำดีแล้ว
1. Multi-GPU architecture แบบ "1 GPU = 1 Process"
2. Internal endpoint สำหรับ worker communication
3. Round-robin dispatch (พื้นฐาน)
4. ไม่สลับ CUDA_VISIBLE_DEVICES ใน runtime

### ⚠️ สิ่งที่ควรปรับปรุง
1. **อัพเกรดเป็น least-loaded policy** (สำคัญที่สุด)
2. เพิ่ม connection pool และ timeout
3. เพิ่ม health check และ retry logic
4. เพิ่ม metrics/monitoring

### 🎯 คำแนะนำสำหรับ Production
1. ใช้ least-loaded policy สำหรับ 25+ concurrent requests
2. เพิ่ม GPU 3 สำหรับ live streaming (ถ้าต้องการ)
3. Monitor worker health และ auto-restart
4. เพิ่ม queue system (Redis/RabbitMQ) ถ้าต้องการ scale มากกว่า

---

## 🔗 References

- [Multi-GPU Test Results](./MULTI_GPU_TEST_RESULTS.md)
- [Start Multi-GPU Workers Script](../scripts/pod/start-multi-gpu-workers.sh)

