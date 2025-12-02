# 📌 Port 8002 - จำเป็นหรือไม่?

เอกสารอธิบายความจำเป็นของ Port 8002 สำหรับ Transcription Service

---

## 📋 สรุป

### ✅ Port 8001 (จำเป็น)
- **Service**: Transcription API (Main Service)
- **Provider**: รองรับหลาย providers:
  - ✅ **faster-whisper** (GPU) - **แนะนำ** - ไม่ต้องใช้ port 8002
  - ✅ openai-whisper (CPU/GPU)
  - ❌ builtin (whisper.cpp) - ต้องใช้ port 8002

### ⚠️ Port 8002 (ไม่จำเป็น - ถ้าใช้ faster-whisper)
- **Service**: Whisper API Service (whisper_api.py)
- **ใช้งานเมื่อ**: ใช้ `builtin` provider เท่านั้น
- **ไม่จำเป็นเมื่อ**: ใช้ `faster-whisper` provider

---

## 🎯 Provider ที่ใช้ใน Pod

### ปัจจุบัน Pod ใช้: **faster-whisper**

```bash
WHISPER_PROVIDER=faster-whisper
WHISPER_DEVICE=cuda
```

**ดังนั้น**: **Port 8002 ไม่จำเป็น** ✅

---

## 🔍 ตรวจสอบ Provider ที่ใช้

```bash
# ตรวจสอบ environment variable
echo $WHISPER_PROVIDER

# หรือดูจาก service logs
grep "WhisperService initialized" /tmp/transcription-service.log
```

---

## 📊 Comparison

| Provider | Port 8002 | Port 8001 | Performance |
|----------|-----------|-----------|-------------|
| **faster-whisper** | ❌ ไม่ต้อง | ✅ ใช้ | ⚡ เร็วสุด (GPU) |
| openai-whisper | ❌ ไม่ต้อง | ✅ ใช้ | ⚡ เร็ว (GPU) |
| builtin | ✅ ต้อง | ✅ ใช้ | 🐢 ช้า (CPU) |

---

## 💡 คำแนะนำ

### สำหรับ Pod (GPU)
- ✅ ใช้ **faster-whisper** (default)
- ✅ ไม่ต้องเปิด port 8002
- ✅ ใช้แค่ port 8001

### สำหรับ Local (CPU)
- ใช้ **faster-whisper** (CPU mode)
- ไม่ต้องเปิด port 8002

### สำหรับ Legacy
- ถ้าใช้ **builtin** provider → ต้องเปิด port 8002

---

## ✅ สรุป

**Port 8002 ไม่จำเป็นสำหรับ Pod ที่ใช้ faster-whisper provider**

ใช้แค่ **port 8001** ก็พอ! ✅

---

**Last Updated**: 2025-12-02

