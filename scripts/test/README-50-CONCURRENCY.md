# 🧪 การทดสอบ 50 Concurrency

## 📋 วัตถุประสงค์

ทดสอบการส่ง **50 requests พร้อมกัน** ไปยัง Transcription Service เพื่อดู:

1. **เวลารวมในการแปลงทั้งหมดทุก Task กี่นาที**
2. **เวลาที่ใช้แปลงแต่ละ task เท่าไร**
3. **เวลารอใน Queue** (ถ้ามี)

---

## ⚙️ ระบบที่จำเป็น

### ✅ จำเป็นต้องใช้:
- **RabbitMQ** - ระบบปัจจุบันใช้ RabbitMQ สำหรับ queue อยู่แล้ว

### ❌ ไม่จำเป็นต้องใช้:
- **Redis** - ไม่จำเป็นสำหรับการทดสอบนี้

---

## 🔄 Flow การทำงาน

```
Client (50 requests พร้อมกัน)
    ↓
Transcription Service API (/transcribe/)
    ↓
RabbitMQ Queue (transcription_queue)
    ↓
Video Workers (ประมวลผลตามลำดับ)
    ↓
Results (completed)
```

**หมายเหตุ**: 
- ส่ง 50 HTTP requests พร้อมกันไปยัง API
- แต่ละ request จะเข้า RabbitMQ queue
- Workers จะประมวลผลตามลำดับ (sequential)

---

## 📦 การติดตั้ง Dependencies

```bash
pip install aiohttp python-dateutil
```

---

## 🚀 วิธีใช้งาน

### Option 1: ใช้ file_path (ไฟล์ที่อยู่ใน Server)

```bash
cd transcription-close-caption-service/scripts/test

python test-50-concurrency.py \
  --api-url http://80.15.7.37:8010 \
  --file-path uploads/test-video-10min.mp4 \
  --file-name "test-video-10min.mp4" \
  --num-concurrent 50 \
  --model-size medium
```

### Option 2: ใช้ file_url (URL จาก FileService)

```bash
python test-50-concurrency.py \
  --api-url http://80.15.7.37:8010 \
  --file-url "http://10.200.22.62/fileservice/api/files/abc123" \
  --file-name "test-video-10min.mp4" \
  --num-concurrent 50 \
  --model-size medium
```

### Option 3: ทดสอบบน Pod

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ไปที่ directory
cd /workspace/transcription-service/scripts/test

# รันทดสอบ
python test-50-concurrency.py \
  --api-url http://localhost:8010 \
  --file-path uploads/test-video-10min.mp4 \
  --file-name "test-video-10min.mp4" \
  --num-concurrent 50
```

---

## 📊 Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `--api-url` | Transcription Service API URL | - | ✅ |
| `--num-concurrent` | จำนวน concurrent requests | 50 | ❌ |
| `--file-path` | Path ของไฟล์ใน server | - | ⚠️ (ถ้าไม่มี --file-url) |
| `--file-url` | URL ของไฟล์ | - | ⚠️ (ถ้าไม่มี --file-path) |
| `--file-name` | ชื่อไฟล์ | `test-video-10min.mp4` | ❌ |
| `--language` | ภาษา | `th` | ❌ |
| `--model-size` | ขนาดโมเดล | `medium` | ❌ |
| `--poll-interval` | ช่วงเวลาการตรวจสอบสถานะ (วินาที) | 5 | ❌ |
| `--output` | ไฟล์รายงาน JSON | `concurrency_report_TIMESTAMP.json` | ❌ |

---

## 📈 ผลลัพธ์ที่ได้

### 1. Console Output

```
📊 รายงานผลการทดสอบ 50 Concurrency
================================================================================

📋 สรุปผลการทดสอบ:
  • จำนวน Tasks ทั้งหมด: 50
  • สำเร็จ: 50
  • ล้มเหลว: 0
  • อัตราความสำเร็จ: 100.0%
  • เวลารวมการทดสอบ: 45.23 นาที (2714.1 วินาที)

⏱️  เวลารวมในการแปลงทั้งหมดทุก Task:
  • มากที่สุด: 600.5 วินาที (10.01 นาที)
  • น้อยที่สุด: 315.2 วินาที (5.25 นาที)
  • เฉลี่ย: 450.3 วินาที (7.51 นาที)
  • มัธยฐาน: 445.8 วินาที (7.43 นาที)

⚙️  เวลาที่ใช้แปลงแต่ละ Task (Processing Time):
  • มากที่สุด: 311.6 วินาที (5.19 นาที)
  • น้อยที่สุด: 310.5 วินาที (5.18 นาที)
  • เฉลี่ย: 311.1 วินาที (5.19 นาที)
  • มัธยฐาน: 311.0 วินาที (5.18 นาที)

⏳ เวลารอใน Queue:
  • มากที่สุด: 289.0 วินาที (4.82 นาที)
  • น้อยที่สุด: 4.7 วินาที
  • เฉลี่ย: 139.2 วินาที (2.32 นาที)
  • มัธยฐาน: 134.8 วินาที (2.25 นาที)
```

### 2. JSON Report

รายงาน JSON จะบันทึกข้อมูลละเอียดทุก Task ไว้ในไฟล์:

- `concurrency_report_YYYYMMDD_HHMMSS.json`

---

## 💡 คำตอบสำหรับคำถาม

### ❓ จำเป็นต้องใช้ RabbitMQ หรือ Redis ไหม?

**คำตอบ**:
- ✅ **จำเป็นต้องใช้ RabbitMQ** - เพราะระบบปัจจุบันใช้ RabbitMQ สำหรับ queue อยู่แล้ว
- ❌ **ไม่จำเป็นต้องใช้ Redis** - ไม่จำเป็นสำหรับการทดสอบนี้

### ❓ จะส่งแบบ Sequential พร้อมกัน 50 ครั้งได้ไหม?

**คำตอบ**: ได้!
- ส่ง 50 HTTP requests **พร้อมกัน** ไปยัง API
- แต่ละ request จะเข้า **RabbitMQ queue**
- Workers จะประมวลผล**ตามลำดับ (sequential)**

---

## 📝 หมายเหตุ

1. **Video Worker**: ต้องมี Worker รันอยู่เพื่อประมวลผล tasks
2. **Queue Size**: RabbitMQ queue อาจมีขนาดจำกัด ตรวจสอบก่อนรันทดสอบ
3. **GPU Utilization**: การทดสอบนี้จะช่วยดูว่า GPU ใช้งานเต็มที่หรือไม่
4. **Memory**: ตรวจสอบว่า server มี memory เพียงพอสำหรับ 50 tasks

---

## 🔍 ตรวจสอบสถานะ

### ตรวจสอบ RabbitMQ Queue

```bash
ssh pytorch-pod
cd /workspace/transcription-service
bash scripts/pod/check-rabbitmq-queue.sh
```

### ตรวจสอบ Worker Status

```bash
ssh pytorch-pod
cd /workspace/transcription-service
bash scripts/pod/check-service-status.sh
```

---

## 📚 ตัวอย่างผลลัพธ์

### สถานการณ์ที่ 1: 1 Worker, 50 Tasks

- **เวลารวมการทดสอบ**: ~45 นาที
- **เวลารวมแต่ละ Task**: ~5-10 นาที (ขึ้นอยู่กับ queue)
- **เวลาประมวลผลแต่ละ Task**: ~5 นาที (วิดีโอ 10 นาที)
- **เวลารอใน Queue**: 0-40 นาที (ขึ้นอยู่กับลำดับใน queue)

### สถานการณ์ที่ 2: 2 Workers, 50 Tasks

- **เวลารวมการทดสอบ**: ~22-25 นาที
- **เวลารวมแต่ละ Task**: ~5-12 นาที
- **เวลาประมวลผลแต่ละ Task**: ~5 นาที
- **เวลารอใน Queue**: 0-20 นาที

---

## 🐛 Troubleshooting

### ปัญหา: Tasks ล้มเหลว

**สาเหตุที่เป็นไปได้**:
- Worker ไม่รัน
- RabbitMQ ไม่เชื่อมต่อได้
- ไฟล์วิดีโอไม่พบ
- Memory ไม่พอ

**วิธีแก้ไข**:
```bash
# ตรวจสอบ Worker
ssh pytorch-pod "cd /workspace/transcription-service && ps aux | grep video_worker"

# ตรวจสอบ RabbitMQ
ssh pytorch-pod "cd /workspace/transcription-service && bash scripts/pod/check-rabbitmq-queue.sh"
```

### ปัญหา: Tasks ติดค้าง

**สาเหตุที่เป็นไปได้**:
- GPU ไม่ทำงาน
- Model lock
- Timeout

**วิธีแก้ไข**:
```bash
# ตรวจสอบ GPU
ssh pytorch-pod "nvidia-smi"

# ตรวจสอบ Logs
ssh pytorch-pod "cd /workspace/transcription-service && tail -f /tmp/video-worker.log"
```

