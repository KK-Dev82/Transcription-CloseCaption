# 📊 ผลการทดสอบด้วย GPU 2 ตัว

## 🔍 สรุปการทดสอบ

**วันที่**: 2026-01-12  
**Configuration**:
- GPU Count: 2 (NVIDIA RTX 4000 Ada Generation)
- Model: `models--Vinxscribe--biodatlab-whisper-th-medium-faster`
- Beam Size: 1
- Device: auto (ใช้ CUDA)

---

## ⚠️ ปัญหาที่พบ

### 1. ไม่ได้รับ Transcription Results

**สถานการณ์**:
- ✅ Chunks ถูกส่งไปยัง `/api/transcription/realtime/live-chunk` สำเร็จ (5/5 chunks)
- ✅ WebSocket เชื่อมต่อสำเร็จ (`ws://localhost:8010/api/ws/captions`)
- ✅ ได้รับ sync, status, heartbeat events
- ❌ **ไม่ได้รับ final events** (transcription results)

**การทดสอบ**:
- รอ 30 วินาที: ไม่ได้รับผลลัพธ์
- รอ 60 วินาที: ไม่ได้รับผลลัพธ์

---

## 🔍 สาเหตุที่เป็นไปได้

### 1. Transcription ใช้เวลานานมาก

**ความเป็นไปได้**: Transcription อาจใช้เวลานานกว่า 60 วินาทีต่อ chunk

**สาเหตุที่เป็นไปได้**:
- Model `medium-faster` อาจใช้เวลานานแม้จะมี GPU 2 ตัว
- faster-whisper ไม่รองรับ multi-GPU โดยตรง (ใช้ GPU แรกเท่านั้น)
- GPU 2 ตัวอาจไม่ได้ช่วยเพิ่มความเร็วถ้า transcription ทำงานแบบ sequential

### 2. Error ในการ Transcription

**ความเป็นไปได้**: มี error ในการ transcription แต่ไม่ได้ log หรือไม่ได้ส่ง error event กลับมา

**การตรวจสอบ**:
- ไม่พบ error logs ใน systemd หรือ uvicorn logs
- Service ทำงานอยู่ (health check ผ่าน)

### 3. WebSocket ไม่ได้ส่ง Final Events

**ความเป็นไปได้**: Code ไม่ได้ส่ง final events ผ่าน WebSocket

**การตรวจสอบ**:
- Code มีการส่ง final events ผ่าน `websocket_manager.send_to_user(meeting_id, final_event)`
- WebSocket endpoint ถูกต้อง (`/api/ws/captions`)

---

## 💡 คำแนะนำ

### 1. ตรวจสอบ Logs โดยตรง

```bash
# ตรวจสอบ uvicorn logs
tail -f /var/log/uvicorn.log  # หรือ log file ที่ตั้งไว้

# ตรวจสอบ transcription service logs
docker logs transcription-service-main-api-1 --tail 100 -f
```

### 2. ทดสอบ Transcription โดยตรง

```bash
# ทดสอบ transcription endpoint โดยตรง
curl -X POST http://localhost:8010/api/transcription/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "http://example.com/audio.wav",
    "language": "th",
    "model_size": "models--Vinxscribe--biodatlab-whisper-th-medium-faster"
  }'
```

### 3. ตรวจสอบ GPU Usage

```bash
# ตรวจสอบว่า GPU ถูกใช้งานหรือไม่
nvidia-smi

# ตรวจสอบว่า faster-whisper ใช้ GPU ตัวไหน
watch -n 1 nvidia-smi
```

### 4. ลด Model Size เพื่อทดสอบ

```bash
# เปลี่ยนเป็น small model เพื่อทดสอบ
CC_MODEL_SIZE=small
CC_BEAM_SIZE=1

# Restart service
bash scripts/pod/restart-main-api.sh
```

---

## 📝 สรุป

### สิ่งที่ทำงานได้:
- ✅ GPU 2 ตัว detect ได้
- ✅ Chunks ถูกส่งไปยัง transcription service สำเร็จ
- ✅ WebSocket เชื่อมต่อสำเร็จ
- ✅ Service ทำงานอยู่ (health check ผ่าน)

### สิ่งที่ไม่ทำงาน:
- ❌ ไม่ได้รับ transcription results ผ่าน WebSocket
- ❌ ไม่ทราบ latency (เพราะไม่ได้รับผลลัพธ์)

### สาเหตุที่เป็นไปได้:
1. Transcription ใช้เวลานานมาก (> 60 วินาที)
2. มี error ในการ transcription แต่ไม่ได้ log
3. WebSocket ไม่ได้ส่ง final events กลับมา

### ขั้นตอนถัดไป:
1. ตรวจสอบ logs ของ transcription service โดยตรง
2. ทดสอบ transcription endpoint โดยตรง (ไม่ผ่าน live-chunk)
3. ตรวจสอบ GPU usage ระหว่าง transcription
4. ลด model size เพื่อทดสอบ (small แทน medium-faster)

---

**หมายเหตุ**: faster-whisper ไม่รองรับ multi-GPU โดยตรง - มันจะใช้ GPU แรกที่เห็นเท่านั้น (ตาม CUDA_VISIBLE_DEVICES) ดังนั้น GPU 2 ตัวอาจไม่ได้ช่วยเพิ่มความเร็วสำหรับ single transcription task

**Last Updated**: 2026-01-12
