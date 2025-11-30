# 🎯 Large Model Setup Guide

คู่มือการตั้งค่าและใช้ Large Model สำหรับ RTX 4080

---

## 📋 Overview

สำหรับ RTX 4080 (16GB VRAM) สามารถใช้ `large` model ได้ ซึ่งให้ความแม่นยำสูงสุด

**เปรียบเทียบ:**
- **`large` model:** ใช้ ~10GB VRAM, ความแม่นยำสูงสุด (⭐⭐⭐⭐⭐⭐)
- **`medium` model:** ใช้ ~5GB VRAM, ความแม่นยำสูง (⭐⭐⭐⭐⭐)

**คำแนะนำ:**
- **ถ้า VRAM ≥12GB:** ใช้ `large` model เพื่อความแม่นยำสูงสุด
- **ถ้า VRAM <12GB:** ใช้ `medium` model

---

## 🚀 Setup Large Model

### Option 1: ตั้งค่าใน .env.runpod (แนะนำ)

**บน Pod:**

```bash
# SSH เข้า Pod
ssh root@<pod-ip> -p <port>

# ไปที่ project directory
cd /workspace/transcription-service

# แก้ไข .env.runpod
nano .env.runpod

# เพิ่ม/แก้ไข:
WHISPER_MODEL=large
```

**หรือใช้ script:**
```bash
# อัปเดต .env.runpod
echo "WHISPER_MODEL=large" >> .env.runpod
```

---

### Option 2: Download Model โดยตรง

**บน Pod:**

```bash
# ไปที่ project directory
cd /workspace/transcription-service

# Download large model
bash scripts/utility/download-models.sh large

# หรือใช้ whisper.cpp script
cd whisper-service
bash models/download-ggml-model.sh large
cp models/ggml-large.bin ../models/
cd ..
```

---

### Option 3: ระบุใน API Request

**ไม่ต้องตั้งค่า default model, ระบุใน API request:**

```bash
# ใช้ large model
curl -X POST http://localhost:8001/api/transcription/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/video.mp4",
    "language": "th",
    "model_size": "large"
  }'
```

---

## 🔍 ตรวจสอบ Model

**บน Pod:**

```bash
# ตรวจสอบว่า model ถูก download แล้ว
ls -lh /workspace/transcription-service/models/ggml-large.bin

# ควรเห็น: ~3GB
```

---

## ⚠️ VRAM Check

**ตรวจสอบ VRAM ก่อนใช้ large model:**

```bash
# ตรวจสอบ GPU VRAM
nvidia-smi --query-gpu=memory.total,memory.free --format=csv,noheader

# ควรมี Free VRAM ≥12GB สำหรับ large model
```

**ถ้า VRAM ไม่เพียงพอ:**
- ใช้ `medium` model แทน
- หรือลด batch size (ถ้ามี)

---

## 🧪 ทดสอบ Performance

**ทดสอบด้วย large model:**

```bash
# บน Pod
cd /workspace/transcription-service

# ทดสอบ transcription
bash scripts/pod/test-transcription-performance.sh \
  uploads/video.mp4 \
  large
```

**Expected Performance (RTX 4080 + Large Model):**

| Video Duration | Expected Transcription Time | Ratio |
|----------------|----------------------------|-------|
| 10 minutes | 1.5-2.5 minutes | 0.15-0.25x |
| 30 minutes | 4-7 minutes | 0.13-0.23x |
| 1 hour | 8-14 minutes | 0.13-0.23x |

---

## 🔄 Fallback Mechanism

**Script `start-services-direct.sh` มี fallback mechanism:**

- ถ้า download `large` model ไม่สำเร็จ → จะลอง `medium` model
- ถ้า `large` model ไม่มี → จะใช้ `medium` model

**ตรวจสอบ logs:**
```bash
# ดู logs ว่าใช้ model อะไร
tail -f /tmp/whisper.log | grep -i model
```

---

## 📊 Model Comparison

| Model | Size | VRAM | Speed | Accuracy | Use Case |
|-------|------|------|-------|----------|----------|
| `medium` | ~1.5GB | ~5GB | ⚡ | ⭐⭐⭐⭐⭐ | Default, สมดุล |
| `large` | ~3GB | ~10GB | 🐌 | ⭐⭐⭐⭐⭐⭐ | ความแม่นยำสูงสุด |

**สำหรับ RTX 4080:**
- **แนะนำ:** ใช้ `large` model (ถ้า VRAM ≥12GB)
- **Alternative:** ใช้ `medium` model (ถ้า VRAM <12GB หรือต้องการความเร็ว)

---

## 🔗 Related Documents

- **Model Recommendations:** `docs/RunPod-Z2/MODEL_RECOMMENDATIONS.md`
- **Performance Testing:** `docs/RunPod-Z2/PERFORMANCE_TESTING.md`
- **Download Models:** `scripts/utility/download-models.sh`

---

**Last Updated:** 2024-12-19

