# 📝 Close Caption Profile: TH-CC-RT v1

## ภาพรวม

Profile สำหรับ Close Caption แบบ Real-time ที่ออกแบบมาเพื่อ:
- ✅ ส่ง caption ทุก **3 วินาที** (realtime)
- ✅ ลดคำเพี้ยน/ประโยคขาดตอนจากการตัด chunk
- ✅ รวมเป็น **FullText** ได้เนียน (ไม่ซ้ำ ไม่หาย)

---

## 🎯 Profile Configuration

### Model: Small + Overlap + Dedupe + Postprocess

- **Model Size**: `small` (เร็วกว่า medium แต่ยังแม่น)
- **Overlap**: `0.6s` (แก้รอยต่อ)
- **Dedupe**: ตัดข้อความซ้ำ
- **Postprocess**: ปรับปรุงข้อความภาษาไทย

---

## ⚙️ Environment Variables

### เปิดใช้งาน CloseCaption

```bash
CC_ENABLED=true
```

### Model Configuration

```bash
# Model size (small สำหรับ realtime)
CC_MODEL_SIZE=small

# Device (auto, cuda, cpu)
CC_DEVICE=auto

# Compute type (float16 สำหรับ GPU)
CC_COMPUTE_TYPE=float16
```

### Chunking Configuration

```bash
# Chunk hop (ความถี่ที่ emit caption)
CC_CHUNK_HOP=3.0

# Overlap (ระยะเวลา overlap)
CC_CHUNK_OVERLAP=0.6
```

### faster-whisper Parameters

```bash
# Beam size (3 สำหรับความแม่น)
CC_BEAM_SIZE=3

# Temperature (0.0 สำหรับความนิ่ง)
CC_TEMPERATURE=0.0

# VAD Filter (เปิดเพื่อตัดช่วงเงียบ)
CC_VAD_FILTER=true

# Condition on previous text (ปิดสำหรับ chunk-based)
CC_CONDITION_ON_PREVIOUS_TEXT=false

# No speech threshold
CC_NO_SPEECH_THRESHOLD=0.6

# Log probability threshold
CC_LOG_PROB_THRESHOLD=-1.0
```

### Dedupe Configuration

```bash
# เปิดใช้งาน dedupe
CC_DEDUPE_ENABLED=true

# ความยาวสูงสุดที่ match (ตัวอักษร)
CC_DEDUPE_MAX_MATCH=80
```

### Postprocess Configuration

```bash
# เปิดใช้งาน postprocess
CC_POSTPROCESS_ENABLED=true

# Normalize (ลบช่องว่างซ้ำ, etc.)
CC_POSTPROCESS_NORMALIZE=true

# Word segmentation (ต้องมี PyThaiNLP)
CC_POSTPROCESS_WORD_SEG=true
```

### Language

```bash
CC_LANGUAGE=th
```

---

## 📋 ตัวอย่าง Configuration (Full)

```bash
# Enable CloseCaption
CC_ENABLED=true

# Model
CC_MODEL_SIZE=small
CC_DEVICE=auto
CC_COMPUTE_TYPE=float16

# Chunking
CC_CHUNK_HOP=3.0
CC_CHUNK_OVERLAP=0.6

# Whisper Parameters
CC_BEAM_SIZE=3
CC_TEMPERATURE=0.0
CC_VAD_FILTER=true
CC_CONDITION_ON_PREVIOUS_TEXT=false
CC_NO_SPEECH_THRESHOLD=0.6
CC_LOG_PROB_THRESHOLD=-1.0

# Dedupe
CC_DEDUPE_ENABLED=true
CC_DEDUPE_MAX_MATCH=80

# Postprocess
CC_POSTPROCESS_ENABLED=true
CC_POSTPROCESS_NORMALIZE=true
CC_POSTPROCESS_WORD_SEG=true

# Language
CC_LANGUAGE=th
```

---

## 🔄 วิธีการทำงาน

### 1. Overlap Buffer

- เก็บ **tail 0.6s** ของ chunk ก่อนหน้า
- เอามา prepend ให้ chunk ใหม่ → ได้ buffer 3.6s
- ส่งเข้า ASR

### 2. Dedupe

- เก็บ `last_emitted_text` (ข้อความที่ส่งออกล่าสุด)
- หา "ส่วนที่ซ้ำกัน" ระหว่างท้ายของ `last_emitted_text` กับต้นของ `new_text`
- ตัดส่วนซ้ำนั้นออกจาก `new_text`
- Emit เฉพาะส่วนใหม่

### 3. Postprocess

- **Normalize**: ลบช่องว่างซ้ำ, normalize วรรณยุกต์/สระ
- **Fix Words**: แก้คำเพี้ยนยอดฮิตด้วย mapping table
- **Word Segmentation**: ตัดคำภาษาไทยด้วย PyThaiNLP (optional)

---

## 📊 Output

### Caption Event (WebSocket)

```json
{
    "type": "final",
    "meeting_id": "meeting-001",
    "chunk_index": 0,
    "chunk_start_ms": 0,
    "chunk_duration_ms": 3000,
    "text": "ข้อความที่แปลงได้...",
    "segments": [
        {
            "id": "seg-0-0",
            "t0_ms": 0,
            "t1_ms": 3000,
            "text": "ข้อความที่แปลงได้...",
            "confidence": 0.95,
            "is_final": true
        }
    ]
}
```

### FullText Record

- ต่อข้อความจาก caption events เข้าด้วยกัน
- เก็บ metadata: meeting_id, chunk_index, start_time, end_time, latency_ms

---

## 🚀 การใช้งาน

### 1. ตั้งค่า Environment Variables

```bash
export CC_ENABLED=true
export CC_MODEL_SIZE=small
export CC_BEAM_SIZE=3
export CC_CHUNK_OVERLAP=0.6
# ... (ดูตัวอย่างข้างบน)
```

### 2. Restart Service

```bash
bash scripts/pod/restart-main-api.sh
```

### 3. ส่ง Audio Chunks

ส่ง audio chunks ไปยัง `/api/transcription/realtime/live-chunk` ตามปกติ

ระบบจะ:
- ✅ ใช้ overlap buffer อัตโนมัติ
- ✅ Dedupe ข้อความซ้ำ
- ✅ Postprocess ข้อความภาษาไทย
- ✅ ส่งผลลัพธ์ผ่าน WebSocket

---

## 📝 หมายเหตุ

- **Overlap**: ช่วยแก้รอยต่อระหว่าง chunks → ลดคำเพี้ยน/ประโยคขาดตอน
- **Dedupe**: ตัดข้อความซ้ำจาก overlap → FullText ต่อเนียน ไม่ซ้ำซ้อน
- **Postprocess**: ปรับปรุงข้อความภาษาไทย → อ่านรู้เรื่องขึ้น

---

## 🔧 Troubleshooting

### ไม่เห็น overlap

- ตรวจสอบว่า `CC_ENABLED=true`
- ตรวจสอบว่า `CC_CHUNK_OVERLAP=0.6` (หรือค่าที่ต้องการ)

### ข้อความยังซ้ำ

- ตรวจสอบว่า `CC_DEDUPE_ENABLED=true`
- เพิ่ม `CC_DEDUPE_MAX_MATCH` ถ้าจำเป็น

### ข้อความยังเพี้ยน

- ตรวจสอบว่า `CC_POSTPROCESS_ENABLED=true`
- เพิ่มคำใน mapping table (`app/utils/thai_postprocess.py`)

---

**Profile Version**: TH-CC-RT v1  
**Last Updated**: 2026-01-12
