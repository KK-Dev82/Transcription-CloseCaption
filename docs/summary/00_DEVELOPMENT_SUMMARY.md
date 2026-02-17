# สรุปรายงานการพัฒนา: FE CC และ Transcription Service

## ภาพรวม

ระบบ Transcription Service รองรับ 2 โหมดหลัก:

| โหมด | แหล่งข้อมูล | Engine | Use Case |
|------|-------------|--------|----------|
| **FE CC (Live Caption)** | PCM streaming จาก Browser | NeMo/TyPhoon หรือ faster-whisper | Real-time caption แบบ overlay |
| **Transcription** | ไฟล์ Video/Audio | faster-whisper (หรือ NeMo-TyPhoon) | Batch transcription, จดบันทึก |

---

## เอกสารแยกตามหัวข้อ

| เอกสาร | หัวข้อ |
|--------|--------|
| [01_SYSTEM_ARCHITECTURE.md](./01_SYSTEM_ARCHITECTURE.md) | System Architecture, Component, Deployment |
| [02_USE_CASE_ACTIVITY_FLOW.md](./02_USE_CASE_ACTIVITY_FLOW.md) | Use Case, Activity Diagram, Process Flow |
| [03_REQUIREMENTS.md](./03_REQUIREMENTS.md) | Functional และ Non-Functional Requirements |
| [04_SYSTEM_DESIGN.md](./04_SYSTEM_DESIGN.md) | ER Diagram, Class Diagram, Data Dictionary |
| [05_TESTING_UAT_SIT.md](./05_TESTING_UAT_SIT.md) | แนวทางทดสอบ UAT และ SIT |

---

## สรุป Flow (สั้น)

### FE CC

```
Browser (PCM) → WebSocket ingest-audio → ASR (TyPhoon/faster-whisper) → WebSocket captions → Consumer
```

### Transcription

```
API Request → Redis Queue → Preprocess → GPU Workers → Aggregator → SQLite / Callback
```

### Format Resource แนะนำ

- **Input**: PCM16 16kHz mono (FE CC, live-chunk); WAV/Video/Audio (transcription)
- **3 วินาที** = 96,000 bytes (PCM16)
- **Transcription chunks** ≤ 30 วินาที
