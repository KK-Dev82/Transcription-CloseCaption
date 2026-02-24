# Chunk Group — แผนการ Implement

**วันที่:** 2026-02-24

---

## 1. ภาพรวม

**Chunk Group** = ผู้ใช้อัปโหลดไฟล์เสียง/วิดีโอที่แบ่งเป็นส่วนๆ ไว้แล้ว (pre-chunked) ระบบจะ:
- **ข้าม** extract audio และ create_chunks (ประหยัดเวลา ~22 วินาที)
- ใช้แต่ละไฟล์เป็น "chunk" โดยตรง → ส่งไป GPU transcribe
- Aggregator รวมผลตามลำดับที่กำหนด

---

## 2. การระบุลำดับไฟล์

### วิธีที่ 1: ส่ง `file_paths` เป็น array (แนะนำ)

```json
{
  "file_paths": [
    "uploads/meeting_part1.wav",
    "uploads/meeting_part2.wav",
    "uploads/meeting_part3.wav"
  ],
  "language": "th",
  "chunk_group": true
}
```

- **ข้อดี:** ลำดับชัดเจน 100% — client ส่งลำดับที่ต้องการ
- **ข้อจำกัด:** ต้องส่ง path ทั้งหมด (ไฟล์ต้องอัปโหลดก่อน)

---

### วิธีที่ 2: ตั้งชื่อไฟล์ตาม pattern

| Pattern | ตัวอย่าง | การเรียง |
|---------|----------|----------|
| `{prefix}_part{N}.ext` | `meeting_part1.wav`, `meeting_part2.wav` | เรียงตาม N |
| `{prefix}_{N:04d}.ext` | `meeting_0001.wav`, `meeting_0002.wav` | เรียงตาม N |
| `{prefix}_chunk_{N:04d}.ext` | `meeting_chunk_0000.wav` | เรียงตาม N |
| Natural sort | `part1`, `part2`, `part10` | เรียงตัวเลขถูกต้อง |

**เงื่อนไข:**
- ต้องมีตัวเลขในชื่อไฟล์ (part1, _001, chunk_0000)
- ใช้ regex: `_part(\d+)|_(\d{3,4})|chunk_(\d+)` เพื่อดึง index
- เรียงตาม index ก่อนส่งไป preprocess

**ข้อดี:** อัปโหลดหลายไฟล์แล้วส่งแค่ prefix หรือโฟลเดอร์  
**ข้อเสีย:** ต้องบังคับ naming — ถ้าชื่อไม่ตรง pattern จะไม่รู้ลำดับ

---

### วิธีที่ 3: ไฟล์ manifest (JSON)

โฟลเดอร์มีไฟล์ `manifest.json`:

```json
{
  "group_id": "meeting_20260224",
  "files": [
    {"path": "meeting_part1.wav", "order": 0},
    {"path": "meeting_part2.wav", "order": 1},
    {"path": "meeting_part3.wav", "order": 2}
  ],
  "max_duration_per_file_seconds": 2100
}
```

- API รับ `manifest_path` หรือ `folder_path` + อ่าน manifest
- **ข้อดี:** ยืดหยุ่น มี metadata เพิ่มได้
- **ข้อเสีย:** ต้องมีไฟล์เพิ่ม 1 ไฟล์

---

## 3. แนะนำ: ผสมวิธีที่ 1 + 2

| Input | การทำงาน |
|-------|----------|
| `file_paths: ["a.wav", "b.wav"]` + `chunk_group: true` | ใช้ลำดับจาก array โดยตรง |
| `folder_path: "uploads/meeting/"` + `chunk_group: true` | สแกนโฟลเดอร์ → เรียงตาม naming pattern → ถ้าไม่มี pattern คืน error |
| `file_path: "uploads/meeting_part1.wav"` + `chunk_group: true` + `auto_discover: true` | หาไฟล์ร่วมกลุ่ม (meeting_part2, meeting_part3...) ตาม pattern |

---

## 4. จำกัดขนาดไฟล์ (ไม่เกิน 35 นาที)

**35 นาที = 2100 วินาที**

### 4.1 ตรวจสอบก่อนเริ่ม job

```
สำหรับแต่ละไฟล์ใน chunk group:
  1. ffprobe / video_service.get_video_info() → duration
  2. ถ้า duration > 2100 วินาที → HTTP 400
     "ไฟล์ {path} ยาว {X} นาที เกินขีดจำกัด 35 นาที"
```

### 4.2 Config

```env
# .env.runpod
CHUNK_GROUP_MAX_DURATION_SECONDS=2100   # 35 นาที
CHUNK_GROUP_MAX_FILES=20               # จำกัดจำนวนไฟล์ต่อ group (optional)
```

### 4.3 API validation

```python
MAX_DURATION = int(os.getenv("CHUNK_GROUP_MAX_DURATION_SECONDS", "2100"))  # 35 min
for fp in file_paths:
    duration = get_audio_duration(fp)  # ffprobe
    if duration > MAX_DURATION:
        raise HTTPException(400, f"ไฟล์ {fp} ยาว {duration/60:.1f} นาที เกินขีดจำกัด {MAX_DURATION/60:.0f} นาที")
```

---

## 5. Flow การทำงาน (Chunk Group)

```
1. API รับ request (file_paths + chunk_group=true)
2. Validate:
   - ไฟล์มีอยู่ครบ
   - แต่ละไฟล์ duration ≤ 35 นาที
   - จำนวนไฟล์ ≤ CHUNK_GROUP_MAX_FILES (ถ้ามี)
3. สร้าง task_id (เหมือนเดิม)
4. Enqueue preprocess_job_chunk_group (แทน preprocess ปกติ)
5. Preprocess (chunk group mode):
   - ข้าม extract_audio
   - ข้าม create_chunks
   - ใช้ file_paths เป็น chunks โดยตรง
   - Convert เป็น 16k mono ถ้าจำเป็น (หรือข้ามถ้าเป็น WAV 16k แล้ว)
   - Enqueue chunk jobs ไป GPU (เหมือนเดิม)
6. Aggregator: รวมผลตามลำดับ (เหมือนเดิม — ใช้ chunk index 0,1,2,...)
```

---

## 6. โครงสร้าง API

### 6.1 Request (ขยายจากเดิม)

```python
class ChunkGroupTranscriptionRequest(BaseModel):
    # วิธีที่ 1: ส่ง paths โดยตรง
    file_paths: Optional[List[str]] = None
    
    # วิธีที่ 2: โฟลเดอร์ (ต้องมี naming pattern)
    folder_path: Optional[str] = None
    
    # วิธีที่ 3: ไฟล์เดียว + auto discover
    file_path: Optional[str] = None  # existing
    auto_discover_siblings: Optional[bool] = None  # หา part2, part3...
    
    chunk_group: bool = False
    language: str = "th"
    model_size: Optional[str] = None
    chunk_duration: Optional[int] = None  # ไม่ใช้ใน chunk_group (แต่ละไฟล์ = 1 chunk)
```

### 6.2 Validation rules

| กรณี | เงื่อนไข |
|------|----------|
| `chunk_group=true` + `file_paths` | ต้องมี file_paths อย่างน้อย 2 ไฟล์ |
| `chunk_group=true` + `folder_path` | โฟลเดอร์ต้องมีไฟล์เสียง ≥ 2 และชื่อตรง pattern |
| `chunk_group=true` + `file_path` + `auto_discover_siblings` | ต้องมี part2, part3... ในโฟลเดอร์เดียวกัน |
| ทุกไฟล์ | duration ≤ CHUNK_GROUP_MAX_DURATION_SECONDS |

---

## 7. Naming Pattern สำหรับ Auto-discover

รองรับรูปแบบ:

```
{prefix}_part{N}.{ext}     → meeting_part1.wav, meeting_part2.wav
{prefix}_part{N:02d}.{ext} → meeting_part01.wav
{prefix}_{N:04d}.{ext}     → meeting_0001.wav
{prefix}_chunk_{N:04d}.{ext} → meeting_chunk_0000.wav
```

Regex ตัวอย่าง:
```python
import re
def extract_chunk_index(filename: str) -> Optional[int]:
    # part1, part01, _001, chunk_0000
    m = re.search(r'_part(\d+)|_(\d{3,4})(?:\.|$)|chunk_(\d+)', filename, re.I)
    if m:
        for g in m.groups():
            if g is not None:
                return int(g)
    return None
```

---

## 8. สรุปเงื่อนไข

| หัวข้อ | รายละเอียด |
|--------|-------------|
| **เรียงลำดับ** | ใช้ `file_paths` array (แนะนำ) หรือ naming pattern |
| **จำกัดขนาด** | แต่ละไฟล์ ≤ 35 นาที (2100s) ตรวจด้วย ffprobe |
| **ไฟล์ที่ต้องมี** | อย่างน้อย 2 ไฟล์ขึ้นไป (ถึงจะใช้ chunk_group) |
| **Format** | WAV 16k mono ได้เลย หรือให้ระบบ convert (เหมือน extract) |

---

## 9. ขั้นตอน Implement (Phase)

| Phase | งาน |
|-------|-----|
| **1** | API: รองรับ `file_paths` + `chunk_group` ใน transcribe/ และ transcribe-enhanced |
| **2** | Validation: duration ≤ 35 นาที, ไฟล์มีอยู่ |
| **3** | Preprocess: โหมด chunk_group — ข้าม extract/create_chunks, ใช้ file_paths เป็น chunks |
| **4** | (Optional) folder_path + auto_discover |
| **5** | (Optional) manifest.json |
