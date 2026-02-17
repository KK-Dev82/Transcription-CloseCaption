# Functional และ Non-Functional Requirements

## Functional Requirements

### FE Live Caption (FE CC)

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| FR-FE-01 | รับ PCM streaming | ระบบต้องรับ PCM16 (16kHz mono) ผ่าน WebSocket `/api/ws/ingest-audio` |
| FR-FE-02 | Producer Lock | จำกัด meeting หนึ่งมีได้ 1 producer เท่านั้น |
| FR-FE-03 | Rolling Window Transcription | แปลงเสียงเป็นข้อความทุก step seconds (rolling window) |
| FR-FE-04 | Broadcast Caption | ส่ง caption events (partial, final) ไปยัง consumers ที่ subscribe meeting_id |
| FR-FE-05 | Provider Switch | รองรับ TyPhoon (NeMo) หรือ faster-whisper ตาม config |
| FR-FE-06 | Dedupe | ตัดข้อความซ้ำจาก overlap ระหว่าง chunks |
| FR-FE-07 | VAD + Silence | รอ silence ก่อนส่ง final เพื่อประโยคสมบูรณ์ |
| FR-FE-08 | Postprocess Thai | ปรับข้อความภาษาไทย (normalize, fix words) — ข้ามได้เมื่อ low-latency mode |

### Transcription (File-based)

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| FR-TR-01 | รับ Request | รับ file_path หรือ file_url เพื่อเริ่ม transcription |
| FR-TR-02 | Extract Audio | แยกเสียงจาก video (FFmpeg) |
| FR-TR-03 | Chunk + Overlap | แบ่ง audio เป็น chunks พร้อม overlap เพื่อลดการขาดตอน |
| FR-TR-04 | Multi-GPU | รองรับหลาย GPU (1 worker ต่อ GPU) |
| FR-TR-05 | Merge Segments | รวม segments จาก chunks เป็น full_text |
| FR-TR-06 | บันทึก Result | บันทึกผลลัพธ์ลง SQLite และ/หรือส่ง callback |
| FR-TR-07 | Status/Progress | ให้สอบถามสถานะและความคืบหน้าได้ |
| FR-TR-08 | Provider Switch | รองรับ faster-whisper หรือ nemo-typhoon ตาม config |
| FR-TR-09 | Diarization | รองรับ speaker diarization (pyannote) เมื่อเปิดใช้งาน |

### Live Chunk (POST-based Realtime)

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| FR-LC-01 | รับ Chunk | รับ audio chunk ผ่าน POST `/api/transcription/realtime/live-chunk` |
| FR-LC-02 | Overlap Buffer | ใช้ overlap buffer เมื่อ CC_ENABLED |
| FR-LC-03 | Priority Queue | ประมวลผลผ่าน priority queue |
| FR-LC-04 | WebSocket Broadcast | ส่งผลลัพธ์ผ่าน WebSocket captions |

---

## Non-Functional Requirements

### Performance

| ID | Requirement | เป้าหมาย |
|----|-------------|----------|
| NFR-P01 | FE CC Latency | partial ใน ~1–2s หลังมีเสียง; final หลัง silence ~0.8s |
| NFR-P02 | Transcription Throughput | รองรับ concurrent jobs ตามจำนวน GPU |
| NFR-P03 | Live-chunk Latency | ~1–2s ต่อ chunk (ขึ้นกับ model) |
| NFR-P04 | Chunk Length | Transcription chunk แนะนำ ≤ 30s (Whisper limit) |

### Scalability

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| NFR-S01 | Multi-GPU | รองรับ 1–N GPU โดยเพิ่ม worker ต่อ GPU |
| NFR-S02 | Queue Separation | แยก queue ตามหน้าที่ (preprocess, GPU, priority, cpu) |
| NFR-S03 | Horizontal Scale | Main API stateless; scale ได้โดยเพิ่ม instance (ต้อง share WebSocket state ถ้า multi-instance) |

### Reliability

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| NFR-R01 | Fallback | TyPhoon ไม่พร้อม → fallback faster-whisper |
| NFR-R02 | Producer TTL | Producer lock หมดอายุเมื่อไม่ได้รับ heartbeat |
| NFR-R03 | Job Persistence | Job ใน Redis queue อยู่จนกว่าจะ process เสร็จ |

### Maintainability

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| NFR-M01 | Provider Swappable | สลับ ASR provider ได้ผ่าน env |
| NFR-M02 | Logging | มี log สำหรับ debug (WS ingest, transcription, queue) |
| NFR-M03 | Health Check | มี /health สำหรับ monitoring |

### Security (พื้นฐาน)

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| NFR-SEC01 | Input Validation | ตรวจสอบ meeting_id, task_id, file_path |
| NFR-SEC02 | Rate Limit | รองรับ rate limiting สำหรับ API |
| NFR-SEC03 | CORS | ตั้งค่า CORS ตาม deployment |

### Resource Format

| ID | Requirement | รายละเอียด |
|----|-------------|-------------|
| NFR-F01 | PCM Input | PCM16, 16kHz, mono สำหรับ FE CC และ live-chunk |
| NFR-F02 | Audio Output | WAV 16k mono สำหรับ internal ASR |
| NFR-F03 | Video Input | mp4, webm, avi, mov, mkv, flv สำหรับ transcription |
| NFR-F04 | Audio Input | wav, mp3, m4a, aac, ogg, flac — แปลงเป็น 16k mono หากจำเป็น |
