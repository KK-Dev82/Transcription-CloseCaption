# คำถามและคำตอบเกี่ยวกับ API Service

## 📋 คำถามที่ 1: แต่ละ Task มี Webhook สำหรับติดตาม Progress Tracking ของตัวเองไหม?

### ✅ คำตอบ: **มี แต่มี 2 วิธี**

### 1. **Callback URL (Per-Task)**
แต่ละ Task สามารถมี `callback_url` ของตัวเองได้:

```python
# เมื่อสร้าง transcription task
POST /transcribe/
{
    "file_path": "...",
    "callback_url": "https://your-backend.com/webhook/transcription",
    "job_id": "...",
    "user_id": "..."
}
```

**การทำงาน:**
- เมื่อ task เสร็จ จะส่ง HTTP POST ไปที่ `callback_url`
- Payload ประกอบด้วย task status, results, metadata
- ใช้สำหรับ callback ไปยัง backend (เช่น senate-backend)

**Code Location:**
- `app/services/transcription_service.py:1914-1992` - Callback logic
- `app/models/transcription.py` - TranscriptionRequest model รองรับ `callback_url`

### 2. **Webhook Service (Global Subscriptions)**
มี Webhook Service สำหรับ global subscriptions:

```python
# สมัครรับ webhook
POST /webhook/subscribe
{
    "url": "https://your-app.com/webhook",
    "events": ["transcription.completed", "transcription.progress"],
    "secret": "your-secret-key"
}
```

**Events ที่รองรับ:**
- `transcription.started` - เมื่อเริ่ม transcription
- `transcription.progress` - Progress update (ทุก 10% หรือเปลี่ยน stage)
- `transcription.completed` - เมื่อ transcription เสร็จ
- `transcription.failed` - เมื่อ transcription ล้มเหลว
- `file.uploaded` - เมื่อมีไฟล์ใหม่

**Code Location:**
- `app/services/webhook_service.py` - Webhook service implementation
- `app/api/webhook.py` - Webhook API endpoints

### 📝 สรุป:
- ✅ **Callback URL**: แต่ละ task มี callback_url ของตัวเอง (ส่งไปที่ backend)
- ✅ **Webhook Service**: Global subscriptions สำหรับ events (รองรับหลาย subscribers)
- 💡 **แนะนำ**: ใช้ callback_url สำหรับ backend integration, ใช้ webhook service สำหรับ frontend/monitoring

---

## 📋 คำถามที่ 2: เราจะ handle ไม่ให้ใช้ Resource เกินอย่างไรดี?

### ✅ คำตอบ: **มีหลายชั้นของการป้องกัน**

### 1. **Queue Limits (Admission Control)**

```python
# Queue limits
MAX_QUEUE_REQUEST = 50      # Request queue
MAX_QUEUE_EXTRACTION = 80   # Audio extraction queue
MAX_QUEUE_TRANSCRIBE = 20   # Transcription queue
```

**การทำงาน:**
- API ตรวจสอบ queue sizes ก่อนรับ request
- ถ้า queue เต็ม → Return `503 Service Unavailable` พร้อม `Retry-After` header
- ป้องกัน queue overflow และ back-pressure

**Code Location:**
- `app/services/transcription_service.py:383-435` - Admission control logic
- `app/services/rabbitmq_service.py:77-109` - Queue declarations with max-length

### 2. **GPU Concurrency Control**

```python
# GPU concurrency
GPU_CONCURRENCY = 2  # จำนวน concurrent GPU tasks
```

**การทำงาน:**
- ใช้ `threading.Semaphore` เพื่อจำกัด concurrent GPU tasks
- แต่ละ task ต้อง acquire semaphore ก่อนใช้ GPU
- ป้องกัน GPU memory overflow

**Code Location:**
- `app/services/whisper_providers/faster_whisper_provider.py:240-242` - GPU semaphore
- `app/workers/async/processors.py` - GPU concurrency control

### 3. **Worker Thread Pool**

```python
# Worker threads
TRANSCRIPTION_MAX_WORKERS = 5  # Thread pool size
```

**การทำงาน:**
- จำกัดจำนวน threads ที่ใช้ประมวลผล
- ป้องกัน CPU overload

**Code Location:**
- `app/workers/async/video_worker.py:59` - Thread pool configuration

### 4. **Batch Size Control**

```python
# Batch size
WHISPER_BATCH_SIZE = 32  # Batch size for GPU processing
```

**การทำงาน:**
- จำกัด batch size สำหรับ GPU processing
- ป้องกัน GPU memory spike

**Code Location:**
- `app/services/whisper_providers/faster_whisper_provider.py:94` - Batch size configuration

### 5. **Rate Limiting**

```python
# API rate limiting
API_RATE_LIMIT_PER_MINUTE = 60  # Requests per minute per IP
```

**การทำงาน:**
- จำกัดจำนวน requests ต่อนาทีต่อ IP
- ป้องกัน DDoS และ API overload

**Code Location:**
- `app/main.py:106-172` - RateLimitMiddleware

### 6. **Resource Monitoring**

```python
# Periodic resource monitoring (ทุก 5 นาที)
- Memory usage (RSS, percentage)
- CPU usage
- Thread count
- File descriptor count
```

**Code Location:**
- `app/main.py:log_resource_usage()` - Resource monitoring function

### 📝 สรุป:
- ✅ **Queue Limits**: ป้องกัน queue overflow (50/80/20)
- ✅ **GPU Concurrency**: จำกัด concurrent GPU tasks (2)
- ✅ **Worker Threads**: จำกัด thread pool (5)
- ✅ **Batch Size**: จำกัด GPU batch size (32)
- ✅ **Rate Limiting**: จำกัด API requests (60/min)
- ✅ **Resource Monitoring**: ติดตาม resource usage

---

## 📋 คำถามที่ 3: เรามีการใช้ PyThaiNLP ช่วยสำหรับการทำ Text Correction หรือยัง?

### ✅ คำตอบ: **ใช้แล้ว!**

### Implementation

**Code Location:**
- `app/services/thai_text_processor.py` - Thai Text Processor
- `app/api/thai_processing.py` - Thai Processing API

### Features ที่ใช้ PyThaiNLP:

1. **Word Tokenization**
   ```python
   from pythainlp.tokenize import word_tokenize as thai_word_tokenize
   ```

2. **Spell Checking**
   ```python
   from pythainlp.spell import correct
   ```

3. **Text Normalization**
   ```python
   from pythainlp.util import normalize
   ```

4. **Thai Words Dictionary**
   ```python
   from pythainlp.corpus import thai_words
   ```

### Processing Pipeline:

```python
def correct_text(self, text: str) -> str:
    # 1. Normalize text
    corrected = normalize(text)
    
    # 2. Fix abnormal repetition
    corrected = self._fix_abnormal_repetition(corrected)
    
    # 3. Common corrections (dictionary-based)
    for wrong, correct_word in self.common_corrections.items():
        corrected = corrected.replace(wrong, correct_word)
    
    # 4. Regex patterns
    for pattern, replacement in self.patterns:
        corrected = re.sub(pattern, replacement, corrected)
    
    # 5. Spell check (PyThaiNLP)
    corrected = self._spell_check(corrected)
    
    # 6. Fix spacing
    corrected = self._fix_spacing(corrected)
    
    # 7. Improve word segmentation (PyThaiNLP)
    corrected = self._improve_word_segmentation(corrected)
    
    return corrected.strip()
```

### Common Corrections:

- คำที่เสียงคล้าย: "ลูก" → "ฟัง", "โงสาก" → "โลก"
- คำผิดทั่วไป: "ครับว่า" → "ครับ ว่า"
- การเว้นวรรค: ปรับ spacing ให้ถูกต้อง
- Word segmentation: ใช้ PyThaiNLP tokenize

### 📝 สรุป:
- ✅ **ใช้ PyThaiNLP แล้ว** สำหรับ:
  - Word tokenization
  - Spell checking
  - Text normalization
  - Word segmentation
- ✅ **Processing Pipeline**: 7 ขั้นตอน
- ✅ **API Endpoint**: `/thai/correct-text` สำหรับทดสอบ

---

## 📋 คำถามที่ 4: Performance - เรารองรับการที่มี Queue เข้ามาที่ RabbitMQ 50 (max) เป็นระยะเวลา 10 ชม ไหวไหม?

### ✅ คำตอบ: **ขึ้นอยู่กับ Processing Time ต่อ Task**

### การคำนวณ Capacity:

#### สมมติฐาน:
- **Queue Max**: 50 tasks
- **Duration**: 10 hours = 600 minutes
- **GPU Concurrency**: 2 (concurrent tasks)
- **Processing Time**: ขึ้นอยู่กับความยาวของวิดีโอ/เสียง

#### สถานการณ์ที่ 1: Tasks สั้น (5-10 นาทีต่อ task)

```
Processing Time: 5-10 นาทีต่อ task
GPU Concurrency: 2 tasks พร้อมกัน

Throughput: 2 tasks / 10 นาที = 12 tasks / ชั่วโมง
Capacity (10 ชั่วโมง): 12 × 10 = 120 tasks ✅

สรุป: รองรับได้มากกว่า 50 tasks
```

#### สถานการณ์ที่ 2: Tasks ปานกลาง (15-20 นาทีต่อ task)

```
Processing Time: 15-20 นาทีต่อ task
GPU Concurrency: 2 tasks พร้อมกัน

Throughput: 2 tasks / 20 นาที = 6 tasks / ชั่วโมง
Capacity (10 ชั่วโมง): 6 × 10 = 60 tasks ✅

สรุป: รองรับได้ 50 tasks (พอดี)
```

#### สถานการณ์ที่ 3: Tasks ยาว (30+ นาทีต่อ task)

```
Processing Time: 30+ นาทีต่อ task
GPU Concurrency: 2 tasks พร้อมกัน

Throughput: 2 tasks / 30 นาที = 4 tasks / ชั่วโมง
Capacity (10 ชั่วโมง): 4 × 10 = 40 tasks ⚠️

สรุป: อาจไม่พอสำหรับ 50 tasks
```

### ปัจจัยที่ส่งผลต่อ Performance:

1. **Audio/Video Length**
   - ยาวขึ้น = ใช้เวลานานขึ้น
   - Chunking ช่วยลดเวลา (parallel processing)

2. **GPU Concurrency**
   - ปัจจุบัน: 2 concurrent tasks
   - สามารถเพิ่มได้ถ้า GPU memory พอ

3. **Queue Architecture**
   - 3-Queue: request (50) → extraction (80) → transcription (20)
   - Bottleneck อยู่ที่ transcription queue (20)

4. **Worker Performance**
   - Thread pool: 5 workers
   - Batch size: 32

### แนะนำการปรับปรุง:

#### Option 1: เพิ่ม GPU Concurrency (ถ้า GPU memory พอ)

```bash
# .env.runpod
GPU_CONCURRENCY=3  # เพิ่มจาก 2 เป็น 3

Throughput: 3 tasks / 20 นาที = 9 tasks / ชั่วโมง
Capacity (10 ชั่วโมง): 9 × 10 = 90 tasks ✅
```

#### Option 2: เพิ่ม Transcription Queue Size

```bash
# .env.runpod
MAX_QUEUE_TRANSCRIBE=30  # เพิ่มจาก 20 เป็น 30

# ช่วยให้ buffer มากขึ้น
```

#### Option 3: Optimize Processing Time

- ใช้ chunking เพื่อ parallel processing
- Optimize batch size
- ใช้ faster-whisper (ใช้อยู่แล้ว)

### 📊 Capacity Planning:

| Task Length | GPU Concurrency | Throughput | 10h Capacity | Status |
|------------|----------------|------------|--------------|--------|
| 5-10 min   | 2              | 12/h       | 120          | ✅ OK  |
| 15-20 min  | 2              | 6/h        | 60           | ✅ OK  |
| 30+ min    | 2              | 4/h        | 40           | ⚠️ Risk |
| 15-20 min  | 3              | 9/h        | 90           | ✅ OK  |
| 30+ min    | 3              | 6/h        | 60           | ✅ OK  |

### 📝 สรุป:

**คำตอบ: ขึ้นอยู่กับความยาวของ tasks**

- ✅ **Tasks สั้น (5-15 นาที)**: รองรับได้ 50 tasks ใน 10 ชั่วโมง
- ⚠️ **Tasks ยาว (30+ นาที)**: อาจไม่พอ ต้องเพิ่ม GPU concurrency หรือลด queue size
- 💡 **แนะนำ**: Monitor processing time และปรับ GPU_CONCURRENCY ตามความเหมาะสม

### 🔍 Monitoring:

```bash
# ตรวจสอบ processing time
grep "processing_time\|transcription_time" logs/api-service.log

# ตรวจสอบ queue sizes
curl http://localhost:8010/api/queue/status

# ตรวจสอบ GPU usage
nvidia-smi
```

---

## 📚 สรุปทั้งหมด

1. ✅ **Webhook**: มีทั้ง callback_url (per-task) และ webhook service (global)
2. ✅ **Resource Management**: มีหลายชั้น (queue limits, GPU concurrency, rate limiting, monitoring)
3. ✅ **PyThaiNLP**: ใช้แล้วสำหรับ text correction
4. ⚠️ **Performance**: รองรับ 50 tasks/10h ถ้า tasks ไม่ยาวเกินไป (แนะนำ monitor และปรับ GPU_CONCURRENCY)

