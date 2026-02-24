# แผน Implement: ข้าม Convert/Extract เมื่อไฟล์เป็น WAV 16 kHz mono

## วัตถุประสงค์
ลดความซ้ำซ้อนและ CPU overhead โดยข้ามการ extract/convert เมื่อไฟล์ตรงกับ format ที่ต้องการ (WAV 16 kHz mono PCM16) สำหรับ transcription

---

## สถานะปัจจุบัน

| Path | มี logic ข้าม? | หมายเหตุ |
|------|----------------|----------|
| `transcription_service._process_with_chunking` | ✅ มี | probe แล้วข้ามถ้า 16k mono |
| `rq_worker.process_preprocess_job` | ❌ ไม่มี | **Main pipeline** - เรียก extract_audio ทุกครั้ง |
| `video_service.extract_audio` | ❌ ไม่มี | ใช้ FFmpeg ทุกครั้ง |
| `sync/handlers._process_audio_extraction_task` | ❌ ไม่มี | RabbitMQ handler |

---

## แนวทาง Implement

### หลักการ: **Centralize ใน VideoService.extract_audio**

เพิ่ม logic ข้ามใน `extract_audio()` เพื่อให้ **ทุก caller ได้รับประโยชน์** โดยอัตโนมัติ (rq_worker, sync/handlers, transcription_service)

---

## ขั้นตอน Implementation

### Step 1: เพิ่ม helper ใน VideoService

**ไฟล์:** `app/services/video_service.py`

```python
# ค่าคงที่
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.3gp')
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1

def _is_already_wav_16k_mono(self, file_path: str) -> bool:
    """
    ตรวจสอบว่าไฟล์เป็น WAV 16 kHz mono อยู่แล้วหรือไม่ (ใช้ ffprobe)
    Returns True ถ้าข้ามได้
    """
    try:
        probe = ffmpeg.probe(str(file_path))
        audio_stream = next(
            (s for s in probe['streams'] if s.get('codec_type') == 'audio'),
            None
        )
        if not audio_stream:
            return False
        sr = int(audio_stream.get('sample_rate', 0))
        ch = int(audio_stream.get('channels', 0))
        return sr == TARGET_SAMPLE_RATE and ch == TARGET_CHANNELS
    except Exception:
        return False
```

**หมายเหตุ:** 
- ไม่ตรวจ `codec_name == 'pcm_s16le'` เพื่อความยืดหยุ่น (บาง container อาจใช้ชื่ออื่น แต่ compatible)
- ถ้าต้องการเข้มงวดขึ้น สามารถเพิ่ม `codec_name in ('pcm_s16le', 'pcm_s16le_planar')` ได้

---

### Step 2: แก้ไข extract_audio ใน VideoService

**ไฟล์:** `app/services/video_service.py`

**Logic ใหม่:**
```
1. ตรวจสอบว่าเป็นไฟล์วิดีโอ (extension) หรือไม่
   - ถ้าใช่ → ต้อง extract เสมอ (ไม่มีทางข้าม)
   
2. ถ้าเป็นไฟล์ audio:
   - เรียก _is_already_wav_16k_mono(path)
   - ถ้า True → return file_path as-is (ข้าม)
   - ถ้า False → รัน FFmpeg convert เหมือนเดิม
```

**การ return path เมื่อข้าม:**
- คืน `str(video_file)` (path เดิม) — ไม่ต้อง copy ไป uploads/
- `create_chunks` รับ path ใดก็ได้ ไม่จำเป็นต้องอยู่ใน uploads/

**Edge case:** ไฟล์ที่ไม่มี extension ชัดเจน (เช่น `.bin`) → probe ก่อน ถ้ามี audio stream และตรง format ก็ข้ามได้

---

### Step 3: อัปเดต rq_worker (optional - stage description)

**ไฟล์:** `app/workers/rq_worker.py`

- ไม่ต้องเปลี่ยน logic การเรียก — `extract_audio` จะ return เร็วขึ้นเมื่อข้าม
- อาจเพิ่ม log ใน extract_audio: `logger.info("⏭️ Skipped conversion (already WAV 16k mono)")`
- `stage_description` ปัจจุบันคือ "กำลังแยกเสียงจากวิดีโอ" — เมื่อข้ามอาจแสดง "ใช้ไฟล์เสียงเดิม (format ตรง)" ก็ได้ (optional)

---

### Step 4: Refactor transcription_service (ลดความซ้ำซ้อน)

**ไฟล์:** `app/services/transcription_service.py`

**ปัจจุบัน:** มี logic แยก — video → extract_audio, audio → probe + convert เอง

**หลัง refactor:** เรียก `video_service.extract_audio(file_path, task_id)` สำหรับทุกไฟล์
- extract_audio จะจัดการทั้ง video และ audio พร้อม logic ข้าม
- ลบโค้ด probe + convert ที่ซ้ำออกจาก transcription_service

---

### Step 5: sync/handlers (RabbitMQ)

**ไฟล์:** `app/workers/sync/handlers.py`

- ไม่ต้องแก้ — ใช้ `video_service.extract_audio` อยู่แล้ว
- ได้รับ logic ข้ามโดยอัตโนมัติ

---

## โครงสร้าง Code หลังแก้ไข (extract_audio)

```python
def extract_audio(self, video_path: str, task_id: Optional[str] = None) -> str:
    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(...)

    # 1. ถ้าเป็นไฟล์ audio (ไม่ใช่ video) และตรง format → ข้าม
    is_video = video_file.suffix.lower() in VIDEO_EXTENSIONS
    if not is_video and self._is_already_wav_16k_mono(str(video_file)):
        logger.info(f"⏭️ Skipped conversion: already WAV 16kHz mono: {video_path}")
        return str(video_file)

    # 2. Extract/Convert ด้วย FFmpeg (เหมือนเดิม)
    # ... existing FFmpeg logic ...
```

---

## การทดสอบ

1. **Unit test:** ไฟล์ WAV 16k mono → ต้องข้าม (ไม่เรียก FFmpeg)
2. **Unit test:** ไฟล์ WAV 44.1k stereo → ต้อง convert
3. **Unit test:** ไฟล์ MP4 → ต้อง extract (ไม่ข้าม)
4. **Integration:** ส่ง task ด้วย WAV 16k mono → ตรวจ extract_time ≈ 0 และ transcription สำเร็จ

---

## ผลลัพธ์ที่คาดหวัง

- **ไฟล์ WAV 16 kHz mono:** ข้าม FFmpeg → ประหยัด CPU และเวลา
- **ไฟล์ MP3, WAV อื่นๆ, MP4:** ทำงานเหมือนเดิม
- **Backward compatible:** ไม่กระทบ flow ปัจจุบัน

---

## ไฟล์ที่ต้องแก้ไข

| ไฟล์ | การแก้ไข |
|------|----------|
| `app/services/video_service.py` | เพิ่ม `_is_already_wav_16k_mono`, แก้ `extract_audio` |
| `app/services/transcription_service.py` | Refactor ให้ใช้ extract_audio สำหรับทุกไฟล์ (optional) |

---

## ลำดับการทำ

1. ✅ Step 1 + 2: VideoService (core logic)
2. ✅ Step 3: rq_worker — เพิ่ม log (optional)
3. ✅ Step 4: transcription_service refactor (optional แต่แนะนำเพื่อลดซ้ำซ้อน)
4. ✅ Step 5: sync/handlers — ไม่ต้องแก้
5. ✅ Tests
