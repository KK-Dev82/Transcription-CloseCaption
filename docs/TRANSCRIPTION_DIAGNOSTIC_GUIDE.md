# 🔍 Transcription Diagnostic Guide

คู่มือตรวจสอบปัญหา Transcription เมื่อ status = "completed" แต่ไม่มีข้อความ

---

## 📋 ปัญหาที่พบ

**อาการ:**
- ✅ Transcription status = "completed"
- ✅ Progress = 100%
- ❌ Full Text = "" (ว่างเปล่า)
- ❌ Chunks = [] (ว่างเปล่า)
- ❌ Error Message = null

---

## 🔍 วิธีตรวจสอบ

### 1. ใช้ Diagnostic Script

```bash
# บน Pod
cd /workspace/transcription-service
bash scripts/pod/diagnose-transcription.sh <task_id>

# ตัวอย่าง
bash scripts/pod/diagnose-transcription.sh 6cbcc34f-cd8e-4f9b-b3fb-264c41ab8760
```

**Script จะตรวจสอบ:**
- ✅ Task Status จาก API
- ✅ Metadata ใน Storage
- ✅ Files ใน Storage (full_text.txt, chunks)
- ✅ Recent Logs
- ✅ Source File Accessibility
- ✅ สรุปปัญหาและคำแนะนำ

---

### 2. ตรวจสอบด้วยมือ

#### A. ตรวจสอบ Task Status

```bash
curl http://localhost:8010/transcribe/<task_id> | jq .
```

**ตรวจสอบ:**
- `status` = "completed"?
- `full_text` มีค่าไหม?
- `chunks` มีค่าหรือเปล่า?
- `total_duration` เป็น null หรือไม่?
- `error_message` มีค่าไหม?

#### B. ตรวจสอบ Metadata

```bash
cat storage/transcriptions/<task_id>/metadata.json | jq .
```

**ตรวจสอบ:**
- `full_text` = "" หรือมีค่า?
- `chunks` = [] หรือมีค่า?
- `total_duration` = null หรือมีค่า?

#### C. ตรวจสอบ Source File

```bash
# ดึง file_url จาก metadata
FILE_URL=$(cat storage/transcriptions/<task_id>/metadata.json | jq -r '.file_url')

# ตรวจสอบว่าไฟล์เข้าถึงได้ไหม
curl -I "$FILE_URL"

# Download และตรวจสอบ audio (ถ้ามี ffprobe)
curl -o /tmp/check_file.mp4 "$FILE_URL"
ffprobe -v error -show_entries stream=codec_type,codec_name,duration /tmp/check_file.mp4
```

**ตรวจสอบ:**
- ✅ ไฟล์เข้าถึงได้ไหม?
- ✅ มี audio track หรือไม่?
- ✅ Audio duration เท่าไหร่?
- ✅ Audio codec คืออะไร?

---

## 🎯 สาเหตุที่เป็นไปได้

### 1. ❌ ไฟล์ไม่มี Audio Track

**อาการ:**
- `total_duration` = null
- ไม่มี error message
- Transcription เสร็จแล้วแต่ไม่มีข้อความ

**วิธีตรวจสอบ:**
```bash
ffprobe -v error -show_entries stream=codec_type /path/to/file
```

**ผลลัพธ์ที่ควรเห็น:**
```
[STREAM]
codec_type=video
[/STREAM]
[STREAM]
codec_type=audio    ← ต้องมีบรรทัดนี้!
[/STREAM]
```

**ถ้าไม่มี audio stream:**
- ❌ ไฟล์ไม่มีเสียง
- ต้องแก้ที่ไฟล์ต้นฉบับ

---

### 2. ❌ Audio File เสียหายหรือว่างเปล่า

**อาการ:**
- ไฟล์มี audio track
- แต่ duration = 0 หรือเสียงเป็น silence
- Faster-Whisper ไม่สามารถ transcribe ได้

**วิธีตรวจสอบ:**
```bash
# ตรวจสอบ duration
ffprobe -v error -show_entries format=duration /path/to/file

# ตรวจสอบ audio level (ถ้ามี ffmpeg)
ffmpeg -i /path/to/file -af "volumedetect" -f null - 2>&1 | grep mean_volume
```

**ถ้า duration = 0:**
- ❌ ไฟล์เสียหาย
- ต้องใช้ไฟล์ใหม่

---

### 3. ❌ Faster-Whisper ไม่สามารถ Detect Speech ได้

**อาการ:**
- ไฟล์มีเสียง (audio track exists)
- แต่เป็น silence หรือไม่มี speech
- Faster-Whisper return empty result

**วิธีตรวจสอบ:**
- ดู logs ของ transcription service
- ตรวจสอบว่า faster-whisper process เสร็จแล้วหรือไม่
- ลองใช้ไฟล์ที่มี speech ชัดเจน

**Logs ที่ควรเห็น:**
```
[Faster Whisper] ✅ Transcription complete
[Faster Whisper] 📊 Text length: 0 chars  ← ถ้าเป็น 0 แสดงว่าไม่มี speech
[Faster Whisper] 📊 Segments: 0
```

---

### 4. ❌ Audio Extraction ล้มเหลว

**อาการ:**
- Video file มี audio track
- แต่การ extract audio ล้มเหลว
- Transcription ไม่สามารถทำงานได้

**วิธีตรวจสอบ:**
- ดู logs ของ video_service
- ตรวจสอบว่า temp audio file ถูกสร้างหรือไม่
- ตรวจสอบ FFmpeg errors

**Logs ที่ควรเห็น:**
```
🎬 ไฟล์เป็น video - กำลัง extract audio...
✅ Extract audio สำเร็จ: /tmp/xxx_audio.wav
```

**ถ้าเห็น error:**
- ❌ Extract audio failed
- ต้องตรวจสอบ FFmpeg installation
- หรือไฟล์ video เสียหาย

---

## 🛠️ วิธีแก้ไข

### 1. ตรวจสอบไฟล์ก่อน Upload

**ใน HTML Upload Page:**
- เพิ่ม validation เพื่อตรวจสอบว่าไฟล์มี audio หรือไม่
- แสดง warning ถ้าไฟล์น่าสงสัย

**Script สำหรับตรวจสอบ:**
```javascript
// ตรวจสอบไฟล์ก่อน upload
async function validateFile(file) {
    // 1. ตรวจสอบขนาดไฟล์
    if (file.size === 0) {
        return { valid: false, error: 'ไฟล์ว่างเปล่า' };
    }
    
    // 2. ตรวจสอบประเภทไฟล์
    const validTypes = ['video/', 'audio/'];
    if (!validTypes.some(type => file.type.startsWith(type))) {
        return { valid: false, error: 'ไฟล์ไม่รองรับ' };
    }
    
    // 3. ลองเล่นไฟล์เพื่อตรวจสอบ audio (ถ้าเป็น video)
    if (file.type.startsWith('video/')) {
        // Create video element and check for audio track
        // (client-side validation)
    }
    
    return { valid: true };
}
```

---

### 2. เพิ่ม Logging ใน Transcription Process

**ใน `transcription_service.py`:**
- Log เมื่อ extract audio สำเร็จ/ล้มเหลว
- Log เมื่อ faster-whisper return empty result
- Log file duration และ audio track info

---

### 3. เพิ่ม Error Handling

**ใน `transcription_service.py`:**
- ตรวจสอบว่า audio extraction สำเร็จหรือไม่
- ตรวจสอบว่า faster-whisper return result หรือไม่
- Set error_message ถ้า transcription ว่างเปล่า

---

## 📊 Diagnostic Checklist

เมื่อเจอปัญหา "completed but no text":

- [ ] ตรวจสอบ Task Status จาก API
- [ ] ตรวจสอบ Metadata ใน Storage
- [ ] ตรวจสอบ Source File (file_url)
- [ ] ตรวจสอบว่าไฟล์มี Audio Track หรือไม่
- [ ] ตรวจสอบ Audio Duration
- [ ] ตรวจสอบ Logs ของ Transcription Service
- [ ] ตรวจสอบ Logs ของ Video Service (ถ้าเป็น video file)
- [ ] ตรวจสอบ Logs ของ Faster-Whisper
- [ ] ลองใช้ไฟล์อื่นที่มี speech ชัดเจน

---

## 🔧 Quick Commands

```bash
# 1. Diagnostic Script
bash scripts/pod/diagnose-transcription.sh <task_id>

# 2. Check Task Status
curl http://localhost:8010/transcribe/<task_id> | jq '{status, progress, full_text: (.full_text | length), chunks: (.chunks | length)}'

# 3. Check Metadata
cat storage/transcriptions/<task_id>/metadata.json | jq '{status, full_text, chunks: (.chunks | length), total_duration, error_message}'

# 4. Check Source File (if accessible)
FILE_URL=$(cat storage/transcriptions/<task_id>/metadata.json | jq -r '.file_url')
curl -I "$FILE_URL"

# 5. Check Audio Track
ffprobe -v error -show_entries stream=codec_type,codec_name,duration <file_path>
```

---

## 💡 Best Practices

1. **ตรวจสอบไฟล์ก่อน Upload**
   - ตรวจสอบว่าไฟล์มี audio track
   - ตรวจสอบ audio duration
   - แสดง warning ถ้าน่าสงสัย

2. **เพิ่ม Validation ใน Service**
   - ตรวจสอบ audio extraction result
   - ตรวจสอบ transcription result
   - Set error_message ถ้าว่างเปล่า

3. **Improve Error Messages**
   - แยก error types (no audio, empty result, etc.)
   - แสดง actionable error messages
   - ให้ข้อมูลที่ช่วยในการ debug

4. **Add Monitoring**
   - Track empty transcription rate
   - Alert เมื่อเจอปัญหา
   - Log diagnostic information

---

**Last Updated:** 2025-12-02  
**Version:** 1.0.0

