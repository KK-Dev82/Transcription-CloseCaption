# FE Live Caption Provider Switch

## สรุป

ระบบ FE Live Caption (WebSocket `/api/ws/ingest-audio`) รองรับการสลับระหว่าง 2 engines:

| Provider | คำอธิบาย | Use Case |
|----------|----------|----------|
| **typhoon** | TyPhoon ASR (NeMo FastConformer) | ภาษาไทยโดยเฉพาะ, streaming, low latency |
| **faster-whisper** | faster-whisper (CTranslate2) | รองรับหลายภาษา, โมเดล large-v3-turbo |

## การตั้งค่า

### .env.runpod (หรือ .env)

```bash
# เลือก provider — typhoon (default สำหรับทดลอง NeMo) หรือ faster-whisper
FE_CC_PROVIDER=typhoon
# FE_CC_PROVIDER=faster-whisper

# TyPhoon (เมื่อ FE_CC_PROVIDER=typhoon)
FE_CC_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime
FE_CC_TYPHOON_DEVICE=auto

# faster-whisper ใช้ CC_MODEL_SIZE จาก CloseCaption config
```

### สลับกลับไปใช้ faster-whisper

```bash
FE_CC_PROVIDER=faster-whisper
```

แล้ว restart Main API

## Fallback

- ถ้า `FE_CC_PROVIDER=typhoon` แต่ `typhoon-asr` ไม่ได้ติดตั้ง → ระบบจะ fallback ไปใช้ **faster-whisper** อัตโนมัติ
- ถ้า `typhoon-asr` ติดตั้งแล้ว → ใช้ TyPhoon ตามที่ตั้งค่า

## Transcription (File) — สลับได้แล้ว

ตั้งแต่เพิ่ม NeMo Typhoon ASR สำหรับ File Transcription:

| Env | ค่าที่เปลี่ยน | ผลลัพธ์ |
|-----|--------------|---------|
| `WHISPER_PROVIDER=faster-whisper` | (default) | ใช้ faster-whisper สำหรับ file transcription |
| `WHISPER_PROVIDER=nemo-typhoon` | เปลี่ยน env | ใช้ NeMo Typhoon ASR สำหรับ file transcription |

```bash
# ใน .env.runpod
WHISPER_PROVIDER=faster-whisper   # หรือ nemo-typhoon
TRANSCRIPTION_TYPHOON_MODEL=typhoon-ai/typhoon-asr-realtime  # เมื่อใช้ nemo-typhoon
```

**สลับได้ตลอดเวลา** — เปลี่ยน env แล้ว restart GPU workers (ไม่กระทบ FE, ไม่ต้องแก้ API/Frontend)

- Fallback: ถ้า `nemo-typhoon` ไม่พร้อม (typhoon-asr ไม่ติดตั้ง) → fallback อัตโนมัติไปใช้ faster-whisper

## หมายเหตุ

- **FE Live Caption** สลับได้ตาม `FE_CC_PROVIDER` (typhoon / faster-whisper)
- **Transcription (file)** สลับได้ตาม `WHISPER_PROVIDER` (faster-whisper / nemo-typhoon)
- สองระบบแยกกัน — ไม่กระทบกัน (ใช้ env คนละตัว)
