# Chunk Group — แผนการ Implement Phase 1–3

**วันที่:** 2026-02-24  
**อ้างอิง:** [CHUNK_GROUP_DESIGN.md](./CHUNK_GROUP_DESIGN.md)

---

## สรุปเป้าหมาย

เพิ่ม API รองรับ `file_paths` + `chunk_group=true` โดย:
- **Validate**: ไฟล์มีอยู่, duration ≤ 35 นาที
- **Preprocess**: ข้าม extract + create_chunks, ใช้แต่ละไฟล์เป็น chunk
- **Aggregator**: รวมผลตามลำดับ (ใช้ logic เดิม)

**เงื่อนไขสำคัญ:** ไม่กระทบ Endpoint เดิม (`file_path` / `file_url` เดี่ยว)

---

## Phase 1: API — รองรับ `file_paths` + `chunk_group`

### 1.1 ขยาย Request Model

**ไฟล์:** `app/api/transcribe.py`

```python
# ขยาย TranscriptionRequest (เพิ่ม optional fields)
class TranscriptionRequest(BaseModel):
    # เดิม
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    language: str = "th"
    model_size: Optional[str] = None
    chunk_duration: Optional[int] = None
    use_chunking: bool = False
    callback_url: Optional[str] = None
    enable_diarization: Optional[bool] = None
    source: Optional[str] = None

    # ใหม่: Chunk Group
    file_paths: Optional[List[str]] = None   # หลายไฟล์
    chunk_group: bool = False               # เปิดโหมด chunk group
```

**ไฟล์:** `app/api/transcription_enhanced.py`

```python
# ขยาย EnhancedTranscriptionRequest
class EnhancedTranscriptionRequest(BaseModel):
    # เดิม
    file_path: str
    language: str = "th"
    ...

    # ใหม่: Chunk Group (ถ้ามี file_paths จะใช้แทน file_path)
    file_paths: Optional[List[str]] = None
    chunk_group: bool = False
```

### 1.2 Logic การรับ Request (ไม่กระทบเดิม)

| Input | การทำงาน |
|-------|----------|
| `file_path` หรือ `file_url` (ไม่มี chunk_group) | Flow เดิมทั้งหมด |
| `file_paths` + `chunk_group=true` | Flow ใหม่ (chunk group) |
| `file_paths` แต่ไม่มี chunk_group | Error 400: "ต้องระบุ chunk_group=true เมื่อใช้ file_paths" |
| `chunk_group=true` แต่ไม่มี file_paths | Error 400: "ต้องระบุ file_paths เมื่อใช้ chunk_group" |

### 1.3 Endpoint ที่ต้องแก้

| Endpoint | ไฟล์ | การเปลี่ยนแปลง |
|----------|------|-----------------|
| `POST /api/transcribe/` | `app/api/transcribe.py` | เพิ่ม branch สำหรับ `file_paths` + `chunk_group` |
| `POST /api/transcribe-enhanced/start` | `app/api/transcription_enhanced.py` | เพิ่ม branch สำหรับ `file_paths` + `chunk_group` |

---

## Phase 2: Validation

### 2.1 ฟังก์ชัน Validation แยก

**ไฟล์ใหม่:** `app/services/chunk_group_validator.py`

```python
"""
Chunk Group Validator
ตรวจสอบ file_paths ก่อนเริ่ม job
"""
import os
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException

from app.services.video_service import VideoService


def validate_chunk_group_request(
    file_paths: List[str],
    max_duration_seconds: int = None,
    max_files: int = None,
    min_files: int = 2
) -> Tuple[List[str], List[float]]:
    """
    Validate file_paths สำหรับ chunk group

    Returns:
        (validated_paths, durations) — paths ที่ผ่าน validation และ duration ของแต่ละไฟล์

    Raises:
        HTTPException 400: ถ้า validation ไม่ผ่าน
    """
    max_duration = max_duration_seconds or int(os.getenv("CHUNK_GROUP_MAX_DURATION_SECONDS", "2100"))
    max_files_limit = max_files or int(os.getenv("CHUNK_GROUP_MAX_FILES", "20"))

    if len(file_paths) < min_files:
        raise HTTPException(
            status_code=400,
            detail=f"chunk_group ต้องมีอย่างน้อย {min_files} ไฟล์ (ได้รับ {len(file_paths)} ไฟล์)"
        )
    if len(file_paths) > max_files_limit:
        raise HTTPException(
            status_code=400,
            detail=f"chunk_group จำกัดไม่เกิน {max_files_limit} ไฟล์ (ได้รับ {len(file_paths)} ไฟล์)"
        )

    video_service = VideoService()
    durations = []

    for fp in file_paths:
        path = Path(fp)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {fp}")

        info = video_service.get_video_info(fp)
        duration = info.get("duration", 0)
        durations.append(duration)

        if duration > max_duration:
            raise HTTPException(
                status_code=400,
                detail=f"ไฟล์ {fp} ยาว {duration/60:.1f} นาที เกินขีดจำกัด {max_duration/60:.0f} นาที"
            )

    return file_paths, durations
```

### 2.2 Config (.env)

```env
# .env.runpod (หรือ .env.runpod-1GPU)
CHUNK_GROUP_MAX_DURATION_SECONDS=2100   # 35 นาที
CHUNK_GROUP_MAX_FILES=20               # จำกัดจำนวนไฟล์ต่อ group
```

---

## Phase 3: Preprocess โหมด Chunk Group

### 3.1 Worker Function ใหม่

**ไฟล์:** `app/workers/rq_worker.py`

เพิ่มฟังก์ชัน `process_preprocess_job_chunk_group`:

```python
def process_preprocess_job_chunk_group(
    task_id: str,
    file_paths: List[str],
    language: str,
    model_size: str,
) -> Dict:
    """
    Preprocess โหมด chunk group:
    - ข้าม extract_audio
    - ข้าม create_chunks
    - ใช้ file_paths เป็น chunks โดยตรง
    - Convert เป็น 16k mono ถ้าจำเป็น (หรือข้ามถ้าเป็น WAV 16k แล้ว)
    - Enqueue chunk jobs ไป GPU
    - Enqueue aggregator
    """
    # 1. โหลด task_data จาก storage
    # 2. อัปเดต stage: preprocessing_chunk_group
    # 3. สำหรับแต่ละ file_path:
    #    - ถ้าไม่ใช่ WAV 16k mono → convert (ใช้ video_service.extract_audio logic)
    #    - ถ้าเป็น WAV 16k mono อยู่แล้ว → ใช้ path เดิม
    # 4. chunks = list of (converted or original) paths
    # 5. เก็บ chunks_metadata ใน Redis (เหมือน process_preprocess_job)
    # 6. Enqueue chunk jobs (เหมือนเดิม)
    # 7. Enqueue aggregator (เหมือนเดิม)
```

### 3.2 Redis Queue Service — เพิ่ม enqueue_preprocess_chunk_group

**ไฟล์:** `app/services/redis_queue_service.py`

```python
def enqueue_preprocess_chunk_group(
    self,
    task_id: str,
    file_paths: List[str],
    language: str = "th",
    model_size: Optional[str] = None,
    source: Optional[str] = None
) -> str:
    """
    Enqueue preprocessing job โหมด chunk group
    ใช้ process_preprocess_job_chunk_group แทน process_preprocess_job
    """
    # ตรวจสอบ queue limit
    # Enqueue ไป preprocess_queue (หรือ preprocess_video_record_queue ถ้า source=video_record)
    # job = queue.enqueue('app.workers.rq_worker.process_preprocess_job_chunk_group', ...)
```

### 3.3 Flow เปรียบเทียบ

| ขั้นตอน | Flow ปกติ | Flow Chunk Group |
|---------|-----------|------------------|
| 1 | extract_audio | **ข้าม** |
| 2 | (optional) diarization | **ข้าม** (หรือทำทีหลังถ้าต้องการ) |
| 3 | create_chunks | **ข้าม** — ใช้ file_paths เป็น chunks |
| 4 | Convert 16k mono | ทำเฉพาะไฟล์ที่ยังไม่ตรง format |
| 5 | Enqueue chunk jobs | เหมือนเดิม |
| 6 | Enqueue aggregator | เหมือนเดิม |

### 3.4 การ Convert ไฟล์ (ถ้าจำเป็น)

ใน `process_preprocess_job_chunk_group`:
- ใช้ `video_service._is_already_wav_16k_mono(path)` เพื่อตรวจสอบ
- ถ้าไม่ตรง → ใช้ `video_service.extract_audio(path, task_id)` (รองรับทั้ง video และ audio)
- ถ้าตรง → ใช้ path เดิม

---

## โครงสร้างไฟล์ที่แก้/เพิ่ม

```
app/
├── api/
│   ├── transcribe.py              # แก้: เพิ่ม file_paths, chunk_group branch
│   └── transcription_enhanced.py  # แก้: เพิ่ม file_paths, chunk_group branch
├── services/
│   ├── chunk_group_validator.py   # ใหม่: validation logic
│   └── redis_queue_service.py     # แก้: เพิ่ม enqueue_preprocess_chunk_group
└── workers/
    └── rq_worker.py               # แก้: เพิ่ม process_preprocess_job_chunk_group
```

---

## ลำดับการ Implement (Checklist)

### Phase 1: API
- [ ] 1.1 ขยาย `TranscriptionRequest` ใน `transcribe.py` (เพิ่ม `file_paths`, `chunk_group`)
- [ ] 1.2 ขยาย `EnhancedTranscriptionRequest` ใน `transcription_enhanced.py`
- [ ] 1.3 เพิ่ม validation logic ใน `start_transcription`: ถ้า `chunk_group` ต้องมี `file_paths`
- [ ] 1.4 เพิ่ม branch ใน `start_transcription`: เมื่อ `file_paths` + `chunk_group` → เรียก flow ใหม่
- [ ] 1.5 ทำเหมือนกันใน `start_enhanced_transcription`

### Phase 2: Validation
- [ ] 2.1 สร้าง `app/services/chunk_group_validator.py`
- [ ] 2.2 เพิ่ม `CHUNK_GROUP_MAX_DURATION_SECONDS`, `CHUNK_GROUP_MAX_FILES` ใน `.env.runpod`
- [ ] 2.3 เรียก `validate_chunk_group_request()` ก่อน enqueue ใน API

### Phase 3: Preprocess
- [ ] 3.1 เพิ่ม `enqueue_preprocess_chunk_group()` ใน `redis_queue_service.py`
- [ ] 3.2 เพิ่ม `process_preprocess_job_chunk_group()` ใน `rq_worker.py`
- [ ] 3.3 ใน API: เมื่อ chunk_group → เรียก `enqueue_preprocess_chunk_group` แทน `enqueue_preprocess`
- [ ] 3.4 บันทึก `file_paths` ลง task_dict (ใช้ `file_path` เป็น path แรก หรือเก็บเป็น JSON)
- [ ] 3.5 บันทึก `chunk_group: true` ใน task_dict เพื่อให้ aggregator รู้ว่าเป็น chunk group

---

## การไม่กระทบ Endpoint เดิม

| สถานการณ์ | การทำงาน |
|-----------|----------|
| Request มีแค่ `file_path` | Flow เดิม 100% — ไม่เข้า branch ใหม่ |
| Request มีแค่ `file_url` | Flow เดิม 100% |
| Request มี `file_paths` แต่ไม่มี `chunk_group` | Error 400 ทันที |
| Request มี `chunk_group` แต่ไม่มี `file_paths` | Error 400 ทันที |
| Request มีทั้ง `file_path` และ `file_paths` | Error 400: ระบุได้อย่างใดอย่างหนึ่ง |

**การตรวจสอบใน API:**
```python
# ใน start_transcription
if request.chunk_group:
    if not request.file_paths:
        raise HTTPException(400, "ต้องระบุ file_paths เมื่อใช้ chunk_group")
    if request.file_path or request.file_url:
        raise HTTPException(400, "เมื่อใช้ chunk_group ให้ระบุเฉพาะ file_paths")
    # → flow chunk group
elif request.file_paths:
    raise HTTPException(400, "ต้องระบุ chunk_group=true เมื่อใช้ file_paths")
# else → flow เดิม (file_path หรือ file_url)
```

---

## หมายเหตุ Aggregator

Aggregator (`process_transcription_job` เมื่อ `is_aggregator_job`) ใช้ logic เดิม:
- อ่าน chunk results จาก Redis `task:{task_id}:chunk:{i}`
- รวมตามลำดับ index 0, 1, 2, ...
- Chunk group ใช้ index เดียวกัน (0=file_paths[0], 1=file_paths[1], ...) จึงไม่ต้องแก้ aggregator

---

## การทดสอบ

1. **Unit test**: `validate_chunk_group_request` — ไฟล์ไม่มี, duration เกิน, จำนวนไฟล์ไม่พอ
2. **Integration test**: ส่ง `file_paths` + `chunk_group=true` → ตรวจสอบว่า job ทำงานครบและได้ผลลัพธ์ถูกต้อง
3. **Regression**: ส่ง `file_path` เดี่ยว → ต้องทำงานเหมือนเดิม
