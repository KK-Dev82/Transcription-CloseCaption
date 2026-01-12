# 📚 การตรวจสอบประวัติการแปลง (Transcription History)

## ✅ สรุปผลการตรวจสอบ

**ผลการตรวจสอบ**: ✅ **มีระบบเก็บประวัติการแปลง**

---

## 🗄️ ระบบเก็บประวัติ

### 1. History API (`app/api/history.py`)

**Endpoints**:
- `GET /api/history/transcriptions` - ดูประวัติการ transcription ทั้งหมด
- `GET /api/history/transcriptions/{task_id}` - ดูรายละเอียด transcription เฉพาะ
- `GET /api/history/stats` - สถิติการ transcription
- `DELETE /api/history/transcriptions/{task_id}` - ลบ transcription
- `WS /api/history/ws/realtime` - WebSocket สำหรับ realtime updates

**การทำงาน**:
- อ่านข้อมูลจาก SQLite Storage เป็นหลัก (`storage/database.db`)
- Fallback ไป JSON Storage ถ้า SQLite ว่างเปล่า
- รองรับการ filter ตาม status, days_ago, limit, offset

---

### 2. Storage Systems

#### A. SQLite Storage (`app/utils/sqlite_storage.py`)

**ที่เก็บ**: `storage/database.db`

**Tables**:
- `transcriptions` - ข้อมูล transcription หลัก
- `segments` - segments ของแต่ละ transcription
- `captions` - caption/subtitle data

**การบันทึก**:
- บันทึกอัตโนมัติเมื่อ transcription เสร็จ
- ใช้ `save_transcription()` method

#### B. JSON Storage (`app/utils/json_storage.py`)

**ที่เก็บ**: `storage/transcriptions/{task_id}/metadata.json`

**โครงสร้าง**:
```
storage/
├── transcriptions/
│   ├── {task_id}/
│   │   └── metadata.json
├── captions/
│   ├── {task_id}/
│   │   └── metadata.json
└── videos/
```

**การบันทึก**:
- บันทึกอัตโนมัติเมื่อ transcription เสร็จ
- ใช้ `save_transcription()` method

---

### 3. RTMP Stream History

**ไฟล์**: `app/services/rtmp/rtmp_stream_service.py`

**การเก็บประวัติ**:

1. **ขณะ Stream ทำงาน**:
   - เก็บใน memory: `self.transcriptions[stream_id]`
   - ไม่บันทึกลง storage จนกว่า stream จะหยุด

2. **เมื่อ Stream หยุด**:
   - เรียก `stop_stream()` → `_save_transcriptions()`
   - บันทึกเป็น caption ใน `storage/captions/{stream_id}/metadata.json`
   - ใช้ `json_storage.save_caption(stream_id, caption_data)`

**⚠️ ปัญหา**:
- ถ้า stream ไม่หยุด (crash, error) ประวัติจะไม่ถูกบันทึก
- ประวัติจะหายไปถ้า service restart (เพราะเก็บใน memory)

---

## 🔍 วิธีตรวจสอบประวัติ

### วิธีที่ 1: ใช้ History API

```bash
# ดูประวัติทั้งหมด (20 รายการล่าสุด)
curl http://localhost:8010/api/history/transcriptions

# ดูประวัติที่เสร็จแล้ว
curl http://localhost:8010/api/history/transcriptions?status=completed

# ดูประวัติ 7 วันที่ผ่านมา
curl http://localhost:8010/api/history/transcriptions?days_ago=7

# ดูรายละเอียด transcription เฉพาะ
curl http://localhost:8010/api/history/transcriptions/{task_id}

# ดูสถิติ
curl http://localhost:8010/api/history/stats
```

### วิธีที่ 2: ตรวจสอบ Storage โดยตรง

```bash
# ตรวจสอบ SQLite
sqlite3 storage/database.db "SELECT task_id, status, created_at FROM transcriptions ORDER BY created_at DESC LIMIT 10;"

# ตรวจสอบ JSON Storage
ls -la storage/transcriptions/
cat storage/transcriptions/{task_id}/metadata.json

# ตรวจสอบ RTMP Stream Captions
ls -la storage/captions/
cat storage/captions/{stream_id}/metadata.json
```

### วิธีที่ 3: ใช้ V2 API (แนะนำ)

```bash
# ดูรายการ tasks
curl http://localhost:8010/api/v2/tasks/?limit=20&status=completed

# ดูรายละเอียด task
curl http://localhost:8010/api/v2/tasks/{task_id}?format=full

# ดูสถิติ
curl http://localhost:8010/api/v2/tasks/stats/summary
```

---

## 📊 สรุปการเก็บประวัติ

| ประเภท | ที่เก็บ | เมื่อไหร่บันทึก | วิธีดู |
|--------|---------|----------------|--------|
| **Transcription ปกติ** | SQLite + JSON | เมื่อ transcription เสร็จ | `GET /api/history/transcriptions` |
| **RTMP Stream** | Memory → JSON (Caption) | เมื่อ stream หยุด | `GET /api/rtmp/stream/{stream_id}/transcriptions` |
| **Live Chunk** | Memory (Metadata) | ไม่บันทึก (เก็บแค่ metadata) | `GET /api/transcription/realtime/chunk-metadata` |

---

## ⚠️ ข้อจำกัด

### 1. RTMP Stream History

**ปัญหา**:
- เก็บใน memory จนกว่า stream จะหยุด
- ถ้า stream ไม่หยุด (crash, error) ประวัติจะไม่ถูกบันทึก
- ประวัติจะหายไปถ้า service restart

**แนวทางแก้ไข**:
- เพิ่ม periodic save (บันทึกทุก N transcriptions)
- บันทึกทันทีเมื่อมี transcription ใหม่ (ไม่รอ stream หยุด)

### 2. Live Chunk History

**ปัญหา**:
- เก็บแค่ metadata ใน memory (`_chunk_metadata_store`)
- ไม่บันทึกลง storage
- จำกัดไว้ 100 chunks ต่อ meeting

**แนวทางแก้ไข**:
- เพิ่มการบันทึกลง storage
- เก็บ full transcription results

---

## 📝 คำแนะนำ

### สำหรับ RTMP Stream

1. **เพิ่ม Periodic Save**:
   ```python
   # บันทึกทุก 100 transcriptions
   if len(self.transcriptions[stream_id]) % 100 == 0:
       await self._save_transcriptions(stream_id)
   ```

2. **บันทึกทันที**:
   ```python
   # บันทึกทุก transcription ทันที
   self.transcriptions[stream_id].append(result)
   await self._save_single_transcription(stream_id, result)
   ```

3. **เพิ่ม Endpoint สำหรับดู RTMP History**:
   ```python
   @router.get("/rtmp/history")
   async def get_rtmp_history():
       # ดึงจาก storage/captions/
       pass
   ```

---

## 🎯 สรุป

### ✅ มีประวัติการแปลง

**หลักฐาน**:
1. ✅ มี History API (`/api/history/transcriptions`)
2. ✅ มี SQLite Storage (`storage/database.db`)
3. ✅ มี JSON Storage (`storage/transcriptions/`)
4. ✅ RTMP Stream บันทึกเมื่อ stream หยุด

**การใช้งาน**:
- Transcription ปกติ: ✅ บันทึกอัตโนมัติ
- RTMP Stream: ⚠️ บันทึกเมื่อ stream หยุดเท่านั้น
- Live Chunk: ❌ ไม่บันทึก (เก็บแค่ metadata)

**คำแนะนำ**:
- ใช้ `GET /api/history/transcriptions` เพื่อดูประวัติ
- ใช้ `GET /api/v2/tasks/` (แนะนำ - API ใหม่)
- ตรวจสอบ RTMP Stream history ผ่าน `/api/rtmp/stream/{stream_id}/transcriptions`

---

**วันที่ตรวจสอบ**: 2024-12-19
**สถานะ**: ✅ มีประวัติ แต่ RTMP Stream มีข้อจำกัด
