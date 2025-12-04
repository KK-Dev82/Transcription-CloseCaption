# 🔍 Worker และ Consumer อธิบาย

## 📋 คำถาม: Worker กับ Consumer คืออะไร?

---

## 🎯 Worker คืออะไร?

**Worker** = **Process/โปรแกรมที่ทำงานอยู่** (Video Worker process)

- **Worker** เป็นโปรแกรมที่ทำงานอยู่บน server (process)
- **Worker** ใช้ RabbitMQ ในการรับงาน (messages) จาก queues
- **Worker** ประมวลผลงานและส่งผลลัพธ์กลับ

### ตัวอย่าง:
```
Worker Process (PID: 4610)
├── RabbitMQ Connection
├── Thread Pool (สำหรับ parallel processing)
├── Services (VideoService, TranscriptionService)
└── Consumers (ฟัง queues)
```

---

## 🔌 Consumer คืออะไร?

**Consumer** = **ส่วนของ Worker ที่ฟังและรับ messages จาก RabbitMQ queue**

- **Consumer** ไม่ใช่ process แยก แต่เป็นส่วนหนึ่งของ Worker
- **Consumer** = Handler function ที่รับ messages จาก queue
- **Worker ตัวเดียวสามารถมี Consumers หลายตัวได้** (สำหรับหลาย queues)

### ตัวอย่าง:
```python
class VideoWorker:
    def setup_consumers(self):
        # Consumer สำหรับ transcription_queue
        self.channel.basic_consume(
            queue='transcription_queue',
            on_message_callback=self._process_transcription_task
        )
        
        # Consumer สำหรับ transcription_request_queue (ใหม่)
        self.channel.basic_consume(
            queue='transcription_request_queue',
            on_message_callback=self._process_request_task
        )
        
        # Consumer สำหรับ audio_extraction_queue (ใหม่)
        self.channel.basic_consume(
            queue='audio_extraction_queue',
            on_message_callback=self._process_extraction_task
        )
```

---

## 🔄 Worker vs Consumer

### Worker (Process)
- ✅ ทำงานอยู่บน server (1 process)
- ✅ เชื่อมต่อกับ RabbitMQ
- ✅ มี Thread Pool, Services, Resources
- ✅ ทำงานต่อเนื่อง (long-running process)

### Consumer (Handler)
- ✅ เป็นส่วนหนึ่งของ Worker
- ✅ ฟัง queue เฉพาะ
- ✅ เรียก handler function เมื่อมี message
- ✅ Worker ตัวเดียวมีหลาย consumers ได้

---

## 📊 ตัวอย่างการทำงาน

### สถานการณ์ปัจจุบัน:
```
Worker Process (PID: 4610)
├── ✅ Consumer: transcription_queue
├── ✅ Consumer: transcription_chunk_queue
├── ✅ Consumer: video_trim_queue
└── ❌ Consumer: transcription_request_queue (ยังไม่มี)
    ❌ Consumer: audio_extraction_queue (ยังไม่มี)
```

**ปัญหาคือ:**
- มี Worker อยู่แล้ว ✅
- แต่ Worker ไม่ได้ฟัง (consume) จาก queues ใหม่ ❌
- Messages รออยู่ใน queue แต่ไม่มีใครรับ ✅

---

## 🎯 ทำไมต้องมี Consumers หลายตัว?

### เพราะแต่ละ Queue ต้องการ Handler ที่ต่างกัน:

1. **transcription_request_queue** → ต้อง:
   - Download file
   - Check file type
   - Route ไปยัง queue ถัดไป

2. **audio_extraction_queue** → ต้อง:
   - Extract audio จาก video
   - ส่ง audio ไปยัง transcription_queue

3. **transcription_queue** → ต้อง:
   - Transcribe audio ด้วย Whisper
   - Save results

### แต่ละ Queue = แต่ละ Stage ของ Pipeline

```
transcription_request_queue (Stage 1: Download & Route)
    ↓
audio_extraction_queue (Stage 2: Extract Audio)
    ↓
transcription_queue (Stage 3: Transcribe)
```

---

## 💡 สรุป

### Worker = โปรแกรมที่ทำงานอยู่
- 1 Worker Process
- มี Services, Thread Pool, Resources
- เชื่อมต่อ RabbitMQ

### Consumer = Handler สำหรับแต่ละ Queue
- Worker ตัวเดียวมีหลาย Consumers ได้
- แต่ละ Consumer ฟัง queue เฉพาะ
- แต่ละ Consumer มี Handler function เฉพาะ

### ปัญหาปัจจุบัน:
- ✅ มี Worker อยู่แล้ว
- ❌ แต่ Worker ไม่มี Consumers สำหรับ queues ใหม่
- ❌ Messages รออยู่ใน queue แต่ไม่มีใครรับ

### วิธีแก้:
- เพิ่ม Consumers สำหรับ queues ใหม่เข้าไปใน Worker เดิม
- ไม่ต้องสร้าง Worker ใหม่
- เพิ่ม Handler functions เท่านั้น

---

## 🔧 Implementation

**ตอนนี้จะทำ:**
1. เพิ่ม Consumer สำหรับ `transcription_request_queue`
   - Handler: `_process_transcription_request_task()`
   - Logic: Download file → Check type → Route

2. เพิ่ม Consumer สำหรับ `audio_extraction_queue`
   - Handler: `_process_audio_extraction_task()`
   - Logic: Extract audio → Send to transcription_queue

**Worker เดิมยังทำงานอยู่ เพียงแต่เพิ่ม Consumers เข้าไป**

---

## 📝 Flow หลัง Implementation

```
Worker Process (PID: 4610)
├── Consumer 1: transcription_request_queue
│   └── Handler: Download & Route
│
├── Consumer 2: audio_extraction_queue
│   └── Handler: Extract Audio
│
└── Consumer 3: transcription_queue
    └── Handler: Transcribe
```

**Worker ตัวเดียวรับผิดชอบทุก stage!**

