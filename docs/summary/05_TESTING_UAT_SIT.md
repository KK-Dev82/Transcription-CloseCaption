# แนวทางทดสอบ UAT และ SIT

## บทนำ

เอกสารนี้อธิบายแนวทางทดสอบ **SIT (System Integration Test)** และ **UAT (User Acceptance Test)** สำหรับ Transcription Service ครอบคลุม FE CC และ Transcription

---

## SIT (System Integration Test)

### วัตถุประสงค์

- ตรวจสอบการทำงานร่วมกันระหว่าง components (API, Workers, Redis, ASR)
- ตรวจสอบ flow end-to-end
- ตรวจสอบข้อผิดพลาดกรณีขอบ (error handling)

### SIT Test Cases: Transcription (File-based)

| ID | Test Case | ขั้นตอน | ผลที่คาดหวัง |
|----|-----------|---------|--------------|
| SIT-TR-01 | ส่ง transcription สำเร็จ | 1. POST /api/transcribe/ ด้วย file_path<br>2. รอจน status=completed | task_id คืนมา, status เปลี่ยนเป็น completed, มี full_text, segments |
| SIT-TR-02 | Poll progress | 1. เริ่ม job<br>2. GET /api/v2/tasks/{id}?format=progress ซ้ำ | progress เพิ่มขึ้น, current_stage เปลี่ยนตามลำดับ |
| SIT-TR-03 | Callback URL | 1. ส่ง job พร้อม callback_url<br>2. รอจนเสร็จ | server ได้รับ POST ที่ callback_url พร้อม payload ครบ |
| SIT-TR-04 | ไฟล์ video | ใช้ไฟล์ .mp4, .webm | extract audio สำเร็จ, ได้ full_text |
| SIT-TR-05 | ไฟล์ audio | ใช้ไฟล์ .mp3, .wav | ได้ full_text โดยไม่ต้อง extract |
| SIT-TR-06 | Job ล้มเหลว | ส่ง file_path ที่ไม่มีอยู่ | status=failed, error_message มีค่า |
| SIT-TR-07 | Concurrent jobs | ส่ง 5–10 jobs พร้อมกัน | ทุก job process ได้ (หรือตาม queue limit) |

### SIT Test Cases: FE Live Caption (WebSocket)

| ID | Test Case | ขั้นตอน | ผลที่คาดหวัง |
|----|-----------|---------|--------------|
| SIT-FE-01 | Producer + Consumer | 1. Connect ingest-audio + captions<br>2. ส่ง PCM frames<br>3. รับ events | ได้ partial แล้วตามด้วย final |
| SIT-FE-02 | Producer Lock | 1. Producer A connect<br>2. Producer B connect ด้วย meeting_id เดียวกัน | B ได้ error PRODUCER_LOCKED |
| SIT-FE-03 | Multi Consumer | 1 Producer, 2 Consumer connect | ทั้ง 2 consumer ได้ events เหมือนกัน |
| SIT-FE-04 | Silence → Final | พูดแล้วหยุดเงียบ ~1s | ได้ final event |
| SIT-FE-05 | Provider Switch | เปลี่ยน FE_CC_PROVIDER แล้ว restart | ระบบใช้ engine ตาม config |

### SIT Test Cases: Live Chunk (POST)

| ID | Test Case | ขั้นตอน | ผลที่คาดหวัง |
|----|-----------|---------|--------------|
| SIT-LC-01 | ส่ง chunk ได้ | 1. Connect WebSocket captions<br>2. POST live-chunk ด้วย PCM 96KB | ได้ final event ทาง WebSocket |
| SIT-LC-02 | Headers ครบ | ส่ง chunk พร้อม X-Meeting-Id, X-Chunk-Index ฯลฯ | job ถูก enqueue, process สำเร็จ |
| SIT-LC-03 | Chunk ตามลำดับ | ส่ง chunk 0, 1, 2 ตามลำดับ | ได้ events ตามลำดับ chunk_index |

### สคริปต์ช่วย SIT

```bash
# Transcription
python scripts/test_transcription_single_file.py
python scripts/test_transcription_with_progress.py
python scripts/test_5_jobs_with_monitoring.py

# Live Chunk
python scripts/test_rtmp_to_live_chunk.py --meeting-id sit-test-001
python scripts/test_redis_live_chunk_end_to_end.py

# Queue / Concurrency
python scripts/test_10_jobs_fairness.py
python scripts/test/test-25-concurrent.py
```

---

## UAT (User Acceptance Test)

### วัตถุประสงค์

- ตรวจสอบว่าระบบตรงตามความต้องการของ User
- ตรวจสอบ UX และ flow การใช้งานจริง
- ตรวจสอบคุณภาพผลลัพธ์ (transcription accuracy)

### UAT Test Cases: Transcription

| ID | Test Case | สถานการณ์ | เกณฑ์ผ่าน |
|----|-----------|-----------|-----------|
| UAT-TR-01 | ไฟล์สั้น (< 1 นาที) | ส่งไฟล์เสียงสั้น | ได้ข้อความอ่านรู้เรื่องภายในเวลาเหมาะสม |
| UAT-TR-02 | ไฟล์ยาว (> 10 นาที) | ส่งไฟล์ยาว | progress อัปเดต, เสร็จสมบูรณ์ ไม่ timeout |
| UAT-TR-03 | ภาษาไทย | ไฟล์พูดภาษาไทย | คำถูกต้อง ไม่อ่านเพี้ยนมาก |
| UAT-TR-04 | Webhook integration | User ตั้ง callback_url | ได้รับผลลัพธ์ที่ server ปลายทาง |
| UAT-TR-05 | ดึงผลจาก API | User poll /api/v2/tasks/{id} | ได้ full_text, segments ครบ |

### UAT Test Cases: FE Live Caption

| ID | Test Case | สถานการณ์ | เกณฑ์ผ่าน |
|----|-----------|-----------|-----------|
| UAT-FE-01 | Real-time caption | พูดผ่าน mic → ดู overlay | ข้อความปรากฏภายใน ~2 วินาที |
| UAT-FE-02 | Partial → Final | พูดแล้วหยุด | เห็น partial ก่อน แล้วเป็น final หลัง silence |
| UAT-FE-03 | Meeting หลายคน | หลาย consumer ใน meeting เดียว | ทุกคนเห็น caption แบบ real-time |
| UAT-FE-04 | Producer เดียว | พยายามเปิด 2 producer | มีแค่คนแรกที่ใช้ได้ |
| UAT-FE-05 | คุณภาพภาษาไทย | พูดประโยคยาว | คำถูกต้องพอใช้ overlay ได้ |

### UAT Checklist (Frontend Integration)

จาก `docs/LIVE_CHUNK_FRONTEND_INTEGRATION.md`:

- [ ] Connect WebSocket (`/api/ws/captions?meeting_id={id}`)
- [ ] Handle `sync`, `status`, `final`, `partial` events
- [ ] ส่ง audio chunks เป็น PCM16 16kHz mono
- [ ] Headers ครบ (X-Meeting-Id, X-Chunk-Index, X-Start-Time, X-Duration)
- [ ] แสดง caption บน overlay ได้ถูกต้อง
- [ ] จัดการ reconnection เมื่อ WebSocket ขาด

### สถานการณ์ UAT จำลอง

| สถานการณ์ | ขั้นตอน | เกณฑ์ |
|-----------|---------|-------|
| การประชุมออนไลน์ | 1. เปิด meeting 2. พูด 3. ดู caption | Caption ตรงกับคำพูดพอใช้ |
| บันทึกการประชุม | 1. ส่งไฟล์อัดเสียง 2. รอ transcription 3. ดึงผล | ได้เอกสารสรุปใช้ได้ |
| Live streaming | 1. FFmpeg stream → live-chunk 2. รับ WebSocket | Caption แสดงแบบ near real-time |

---

## สิ่งที่ต้องเตรียม

### สำหรับ SIT

- Redis ทำงาน
- RQ Workers รัน (preprocess, GPU, aggregator)
- Main API รัน
- ไฟล์ทดสอบ (video/audio)
- (ถ้าต้องการ) ngrok หรือ public URL สำหรับ callback

### สำหรับ UAT

- Frontend ที่ integrate WebSocket + live-chunk
- หรือใช้ `scripts/test_rtmp_to_live_chunk_with_websocket.py` จำลอง
- Mic สำหรับ FE CC (หรือใช้ไฟล์เสียงแทน)

### ตรวจสอบระบบก่อนทดสอบ

```bash
# Health
curl http://localhost:8010/health

# Queue status
curl http://localhost:8010/api/transcribe/debug/queue

# Worker health
bash scripts/pod/check-worker-health.sh
```

---

## สรุป Test Matrix

| โหมด | SIT | UAT |
|------|-----|-----|
| Transcription | API flow, queue, callback, error | Accuracy, progress, webhook integration |
| FE CC | WebSocket, producer lock, provider | Latency, UX, คำถูกต้อง |
| Live Chunk | POST + WebSocket flow | Near real-time, integration |
