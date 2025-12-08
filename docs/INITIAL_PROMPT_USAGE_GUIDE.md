# 📝 คู่มือการใช้งาน Initial Prompt + Dictionary + SpellChecker

**วันที่สร้าง**: 2024-12-05  
**Version**: 1.0  
**Status**: Production Ready

---

## 📋 สารบัญ

1. [ภาพรวม](#ภาพรวม)
2. [การทำงาน](#การทำงาน)
3. [วิธีเปิดใช้งาน](#วิธีเปิดใช้งาน)
4. [API Parameters](#api-parameters)
5. [ตัวอย่างการใช้งาน](#ตัวอย่างการใช้งาน)
6. [Configuration](#configuration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 ภาพรวม

Initial Prompt เป็น feature ที่ช่วยเพิ่มความแม่นยำของการ transcription โดยการส่งคำศัพท์เฉพาะหรือ context ให้กับ Whisper model ก่อนเริ่ม transcription

### ✅ Features

- **Dictionary Integration**: ดึงคำศัพท์จาก Backend Dictionary API (Global/Personal scope)
- **Custom Prompt**: ส่ง initial_prompt โดยตรง (ไม่ผ่าน Dictionary)
- **Optional Mode**: เปิด/ปิดได้ (default: ปิด เพื่อป้องกันความช้า)
- **SpellChecker Integration**: ทำงานร่วมกับ Thai Text Processor
- **Chunking Support**: ส่ง initial_prompt ไปยังทุก chunks

### 🔄 3-Phase Workflow

```
Phase 1: Preparation
  ↓
Backend Dictionary API → คำศัพท์เฉพาะ
  ↓
สร้าง initial_prompt

Phase 2: Transcription
  ↓
Whisper Model (ใช้ initial_prompt) → ผลลัพธ์

Phase 3: Post-Processing
  ↓
Thai Text Processor (SpellChecker) → แก้ไขคำผิด
```

---

## 🔧 การทำงาน

### 1. Dictionary Service

ดึงคำศัพท์จาก Backend Dictionary API:

```python
# Backend API Endpoint
GET /api/word-management/dictionary
```

**Parameters:**
- `language`: "thai" (default)
- `scope`: "Global" หรือ "Personal"
- `ownerUserId`: User ID (สำหรับ Personal scope)
- `limit`: จำนวนคำสูงสุด (default: 500)
- `includeGlobal`: รวม Global words ด้วย (default: true)

### 2. Prompt Builder

สร้าง initial_prompt จาก Dictionary words:

```python
prompt_builder.build_initial_prompt(
    dictionary_words=["วุฒิสภา", "สมาชิก", "ร่างกฎหมาย"],
    context="การประชุม",
    max_words=50,
    include_common_phrases=True
)
```

**Output:**
```
"การประชุม สมาชิกวุฒิสภา ประเด็น การพิจารณาร่างกฎหมาย..."
```

### 3. Whisper Transcription

ส่ง initial_prompt ไปยัง Whisper:

```python
whisper_model.transcribe(
    audio_path="audio.wav",
    language="th",
    initial_prompt="การประชุม สมาชิกวุฒิสภา..."
)
```

### 4. Post-Processing

ใช้ Thai Text Processor แก้ไขคำผิด:

```python
thai_processor.correct_text(
    text=whisper_result,
    # Spell checking, word segmentation, repetition fixing
)
```

---

## ⚙️ วิธีเปิดใช้งาน

### Option 1: ใช้ Backend Dictionary (แนะนำ)

```json
POST /transcribe/
{
  "file_url": "http://example.com/video.mp4",
  "language": "th",
  "model_size": "medium",
  "enable_initial_prompt": true,
  "use_backend_dictionary": true,
  "dictionary_scope": "Global",
  "dictionary_max_words": 50,
  "user_id": "123"  // Optional: สำหรับ Personal scope
}
```

### Option 2: ส่ง initial_prompt โดยตรง

```json
POST /transcribe/
{
  "file_url": "http://example.com/video.mp4",
  "language": "th",
  "model_size": "medium",
  "enable_initial_prompt": true,
  "initial_prompt": "การประชุม สมาชิกวุฒิสภา ประเด็น การพิจารณาร่างกฎหมาย",
  "use_backend_dictionary": false
}
```

### Option 3: ปิดใช้งาน (Default)

```json
POST /transcribe/
{
  "file_url": "http://example.com/video.mp4",
  "language": "th",
  "model_size": "medium",
  "enable_initial_prompt": false  // หรือไม่ส่ง parameter นี้
}
```

---

## 📊 API Parameters

### TranscriptionRequest Model

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_initial_prompt` | `bool` | `false` | เปิดใช้ initial_prompt (⚠️ ปิดไว้เพื่อป้องกันความช้า) |
| `initial_prompt` | `string` | `null` | initial_prompt โดยตรง (ถ้ามีจะใช้แทน Dictionary) |
| `use_backend_dictionary` | `bool` | `true` | ใช้ Dictionary จาก Backend API |
| `dictionary_scope` | `string` | `"Global"` | "Global" หรือ "Personal" |
| `dictionary_max_words` | `int` | `50` | จำนวนคำสูงสุดจาก Dictionary |

### ⚠️ หมายเหตุ

- **Default: `enable_initial_prompt=false`** - ปิดไว้เพื่อป้องกันความช้า
- ถ้า `initial_prompt` มีค่า จะใช้แทน Dictionary
- ถ้า `enable_initial_prompt=true` แต่ไม่มี `initial_prompt` และ `use_backend_dictionary=false` จะไม่ใช้ initial_prompt

---

## 💡 ตัวอย่างการใช้งาน

### Example 1: ใช้ Global Dictionary

```bash
curl -X POST "http://localhost:8010/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/video.mp4",
    "language": "th",
    "model_size": "medium",
    "enable_initial_prompt": true,
    "use_backend_dictionary": true,
    "dictionary_scope": "Global",
    "dictionary_max_words": 50
  }'
```

**Response:**
```json
{
  "task_id": "abc-123-def",
  "status": "pending",
  "progress": 0,
  ...
}
```

### Example 2: ใช้ Personal Dictionary

```bash
curl -X POST "http://localhost:8010/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/video.mp4",
    "language": "th",
    "model_size": "medium",
    "enable_initial_prompt": true,
    "use_backend_dictionary": true,
    "dictionary_scope": "Personal",
    "dictionary_max_words": 50,
    "user_id": "123"
  }'
```

### Example 3: Custom Prompt

```bash
curl -X POST "http://localhost:8010/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/video.mp4",
    "language": "th",
    "model_size": "medium",
    "enable_initial_prompt": true,
    "initial_prompt": "การประชุม สมาชิกวุฒิสภา ประเด็น การพิจารณาร่างกฎหมาย",
    "use_backend_dictionary": false
  }'
```

### Example 4: CloseCaption (Priority + Initial Prompt)

```bash
curl -X POST "http://localhost:8010/transcribe/" \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "http://example.com/video.mp4",
    "language": "th",
    "model_size": "medium",
    "display_mode": "realtime_chunks",
    "enable_initial_prompt": true,
    "use_backend_dictionary": true,
    "dictionary_scope": "Global"
  }'
```

**หมายเหตุ:**
- `display_mode="realtime_chunks"` → Priority 10 (สูงสุด)
- CloseCaption จะได้รับการประมวลผลก่อน normal transcription

---

## ⚙️ Configuration

### Environment Variables

```bash
# Backend API Base URL (สำหรับ Dictionary Service)
BACKEND_API_BASE_URL=http://localhost:5173
# หรือ
BACKEND_URL=http://localhost:5173

# Redis (optional - สำหรับ WebSocket scaling)
REDIS_URL=redis://localhost:6379
```

### Backend Dictionary API

**Endpoint:**
```
GET /api/word-management/dictionary
```

**Query Parameters:**
- `language`: "thai" (default)
- `limit`: 500 (default)
- `includeGlobal`: true (default)
- `ownerUserId`: User ID (optional, สำหรับ Personal scope)

**Response Format:**
```json
{
  "data": [
    {
      "word": "วุฒิสภา",
      "language": "thai",
      "scope": "Global",
      ...
    },
    ...
  ]
}
```

---

## 📚 Best Practices

### 1. เมื่อไหร่ควรใช้ initial_prompt?

✅ **ควรใช้:**
- มีคำศัพท์เฉพาะ (ชื่อบุคคล, สถานที่, องค์กร)
- มีคำศัพท์เทคนิค (กฎหมาย, การแพทย์, วิทยาศาสตร์)
- ต้องการความแม่นยำสูงสำหรับคำศัพท์เฉพาะ

❌ **ไม่ควรใช้:**
- Audio สั้นมาก (< 5 วินาที) - อาจทำให้ช้าเกินไป
- Audio คุณภาพต่ำ - initial_prompt อาจไม่ช่วยมาก
- ต้องการความเร็วสูงสุด - initial_prompt เพิ่ม overhead

### 2. จำนวนคำที่เหมาะสม

| Audio Duration | Recommended Max Words |
|----------------|----------------------|
| < 30 วินาที    | 20-30 คำ            |
| 30-60 วินาที   | 30-50 คำ            |
| 1-5 นาที       | 50-100 คำ           |
| > 5 นาที       | 50-100 คำ (คงเดิม)   |

**⚠️ หมายเหตุ:**
- Whisper ต้องการ prompt สั้นๆ (ประมาณ 50-100 คำ)
- Prompt ยาวเกินไปอาจทำให้ transcription ช้าลง

### 3. Dictionary Scope

**Global Dictionary:**
- คำศัพท์ที่ใช้ร่วมกันทั้งระบบ
- เหมาะสำหรับคำศัพท์ทั่วไป (เช่น "วุฒิสภา", "สมาชิก")

**Personal Dictionary:**
- คำศัพท์เฉพาะของแต่ละ user
- เหมาะสำหรับชื่อเฉพาะ, คำศัพท์เฉพาะ domain

**แนะนำ:** ใช้ทั้ง 2 scope ร่วมกัน (Global + Personal)

### 4. Performance Considerations

⚠️ **ข้อควรระวัง:**

1. **Backend API Call**: การดึง Dictionary จะใช้เวลา 1-5 วินาที (ขึ้นอยู่กับ network)
   - **Solution**: ใช้ timeout 5 วินาที (default)
   - ถ้า Backend API ไม่พร้อม จะข้าม initial_prompt และทำงานปกติ

2. **Prompt Processing**: initial_prompt อาจเพิ่มเวลา transcription 5-10%
   - **Solution**: ใช้เฉพาะเมื่อจำเป็น

3. **Dictionary Size**: Dictionary ใหญ่เกินไปอาจทำให้ prompt ยาวเกินไป
   - **Solution**: จำกัดด้วย `dictionary_max_words` (default: 50)

---

## 🔍 Troubleshooting

### Problem 1: Backend Dictionary API ไม่ทำงาน

**อาการ:**
- Log: `⚠️ Failed to fetch dictionary from Backend API`
- initial_prompt เป็น `None`

**แก้ไข:**
1. ตรวจสอบ Backend API URL:
   ```bash
   # ตรวจสอบ environment variable
   echo $BACKEND_API_BASE_URL
   ```

2. ทดสอบ Backend API:
   ```bash
   curl "http://localhost:5173/api/word-management/dictionary?language=thai&limit=10"
   ```

3. ถ้า Backend API ไม่พร้อม:
   - ระบบจะข้าม initial_prompt และทำงานปกติ
   - หรือใช้ `initial_prompt` โดยตรงแทน

### Problem 2: Transcription ช้าลง

**อาการ:**
- เปิดใช้ `enable_initial_prompt=true` แล้ว transcription ช้าลง

**สาเหตุ:**
1. Backend API Call ใช้เวลานาน (> 5 วินาที)
2. initial_prompt ยาวเกินไป (> 100 คำ)
3. Dictionary มีคำศัพท์เยอะเกินไป

**แก้ไข:**
1. ลด `dictionary_max_words`:
   ```json
   {
     "enable_initial_prompt": true,
     "dictionary_max_words": 30  // ลดจาก 50 เป็น 30
   }
   ```

2. ใช้ `initial_prompt` โดยตรง (ไม่ผ่าน Dictionary):
   ```json
   {
     "enable_initial_prompt": true,
     "initial_prompt": "คำศัพท์เฉพาะที่ต้องการ",
     "use_backend_dictionary": false
   }
   ```

3. ปิดใช้งานถ้าไม่จำเป็น:
   ```json
   {
     "enable_initial_prompt": false
   }
   ```

### Problem 3: initial_prompt ไม่มีผล

**อาการ:**
- เปิดใช้ `enable_initial_prompt=true` แล้วแต่ไม่เห็นผล

**ตรวจสอบ:**
1. ตรวจสอบ Logs:
   ```bash
   # ดู logs ของ video_worker
   tail -f /tmp/video-worker.log | grep "initial_prompt"
   ```

2. ตรวจสอบว่า Backend Dictionary มีคำศัพท์หรือไม่:
   ```bash
   curl "http://localhost:5173/api/word-management/dictionary?language=thai&limit=10"
   ```

3. ตรวจสอบว่า initial_prompt ถูกส่งไปยัง Whisper หรือไม่:
   - ดู logs: `📝 Built initial_prompt from Dictionary`
   - ดู logs: `Using initial_prompt: ...`

### Problem 4: Dictionary timeout

**อาการ:**
- Log: `⚠️ Backend Dictionary API timeout (>5s)`

**แก้ไข:**
1. ตรวจสอบ Backend API performance
2. เพิ่ม timeout (ถ้าจำเป็น):
   ```python
   # ใน dictionary_service.py
   self.timeout = aiohttp.ClientTimeout(total=10.0)  # เพิ่มจาก 5 เป็น 10
   ```

---

## 📊 Performance Impact

### Expected Overhead

| Component | Time Overhead | Notes |
|-----------|---------------|-------|
| Backend API Call | 1-5 วินาที | ขึ้นอยู่กับ network และ Backend performance |
| Prompt Building | < 0.1 วินาที | Negligible |
| Whisper Processing | 5-10% ช้าลง | ขึ้นอยู่กับ prompt length |
| **Total** | **1-6 วินาที + 5-10%** | สำหรับ audio สั้นๆ |

### When to Use

✅ **ควรใช้:**
- Audio > 1 นาที → Overhead เล็กน้อยเมื่อเทียบกับ total time
- ต้องการความแม่นยำสูง → เพิ่มความแม่นยำ 5-10%
- มีคำศัพท์เฉพาะ → ช่วยให้ Whisper รู้ context

❌ **ไม่ควรใช้:**
- Audio < 30 วินาที → Overhead สูงเมื่อเทียบกับ total time
- ต้องการความเร็วสูงสุด → initial_prompt เพิ่ม overhead
- Audio คุณภาพต่ำ → initial_prompt อาจไม่ช่วยมาก

---

## 🔗 Related Documentation

- [Queue Architecture](./QUEUE_ARCHITECTURE_FINAL.md) - ระบบ Queue และ Priority
- [Worker Architecture](./WORKER_ARCHITECTURE_EXPLANATION.md) - Worker implementation
- [Thai Text Processor](./TRANSCRIPTION_PERFORMANCE_OPTIMIZATION.md) - Post-processing

---

## 📝 Summary

### ✅ Features

- ✅ Initial Prompt จาก Backend Dictionary
- ✅ Initial Prompt โดยตรง (custom)
- ✅ Optional Mode (เปิด/ปิดได้)
- ✅ รองรับทั้ง Global และ Personal Dictionary
- ✅ ทำงานร่วมกับ SpellChecker
- ✅ รองรับ Chunking

### 🎯 Workflow

```
Backend Dictionary → initial_prompt → Whisper → SpellChecker → Result
```

### ⚙️ Configuration

```json
{
  "enable_initial_prompt": true,
  "use_backend_dictionary": true,
  "dictionary_scope": "Global",
  "dictionary_max_words": 50
}
```

### 📊 Performance

- **Overhead**: 1-6 วินาที + 5-10% ช้าลง
- **Accuracy Improvement**: +5-10% สำหรับคำศัพท์เฉพาะ
- **Recommendation**: ใช้เฉพาะเมื่อจำเป็น

---

**Last Updated**: 2024-12-05  
**Status**: Production Ready ✅

