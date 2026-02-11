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

## หมายเหตุ

- **Transcription (file)** ยังใช้ faster-whisper เสมอ (ไม่เปลี่ยนแปลง)
- **RQ Workers** (Transcription Queue) ยังใช้ faster-whisper
- เฉพาะ **FE Live Caption** (WebSocket ingest) เท่านั้นที่สลับได้ตาม FE_CC_PROVIDER
