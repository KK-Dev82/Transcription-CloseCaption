# 🧪 ทดสอบ Transcription บน RunPod

คู่มือการทดสอบ Transcription ด้วย Video File จาก Local Machine

---

## 📋 คำถาม

### 1. ตอนนี้ใช้ Model แบบไหน?

**คำตอบ:** ใช้ `base` (default)

**แนะนำ:** เปลี่ยนเป็น `medium` สำหรับ RTX 4080 เพื่อให้เทียบเท่า Groq API

### 2. ทดลองแปลงได้ไหม?

**คำตอบ:** ✅ ได้ - ใช้ curl ได้ (ไม่ต้อง SSH)

**หมายเหตุ:**
- Port `13027` = SSH port (ไม่จำเป็น)
- Port `8001` = API port (ใช้สำหรับ curl)

### 3. ใช้ Video 10 นาทีได้ไหม?

**คำตอบ:** ✅ ได้

---

## 🚀 วิธีทดสอบ

### Option 1: ใช้ Script (แนะนำ)

**จาก Local Machine (MacOS):**

```bash
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# ทดสอบด้วย video 10 นาที
bash scripts/pod/upload-and-test.sh \
  "/Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Resources/video/trimmed_short.mp4" \
  205.196.17.108 \
  8001 \
  medium
```

**Script จะทำ:**
1. ✅ ตรวจสอบ API health
2. ✅ อัปโหลด video file
3. ✅ เริ่ม transcription (ใช้ medium model)
4. ✅ รอผลลัพธ์และแสดง progress
5. ✅ แสดง transcription result

---

### Option 2: Manual (2 ขั้นตอน)

#### Step 1: Upload Video

```bash
curl -X POST http://205.196.17.108:8001/api/upload/ \
  -F "file=@/Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Resources/video/trimmed_short.mp4"
```

**Response:**
```json
{
  "file_id": "...",
  "filename": "trimmed_short.mp4",
  "file_path": "uploads/...",
  "file_size": ...,
  "status": "uploaded"
}
```

#### Step 2: Start Transcription

```bash
curl -X POST http://205.196.17.108:8001/api/transcription/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/...",
    "language": "th",
    "model_size": "medium"
  }'
```

**Response:**
```json
{
  "task_id": "...",
  "status": "pending",
  "file_path": "uploads/...",
  "progress": 0
}
```

#### Step 3: Check Status

```bash
curl http://205.196.17.108:8001/api/transcription/{task_id}
```

---

## 📥 Download Medium Model (ถ้ายังไม่มี)

**บน Pod Server:**

```bash
# SSH เข้า Pod
ssh root@205.196.17.108 -p 13027

# Download medium model
cd /workspace/transcription-service/whisper-service
bash models/download-ggml-model.sh medium
cp models/ggml-medium.bin ../models/

# ตรวจสอบ
ls -lh /workspace/transcription-service/models/ggml-medium.bin
# ควรเห็น: ~1.5GB
```

---

## 🎯 Model Recommendations

| Model | Accuracy | Speed (GPU 4080) | Use Case |
|-------|----------|-----------------|----------|
| **base** | ⭐⭐ | ⚡⚡⚡⚡⚡ | Fast, low accuracy |
| **small** | ⭐⭐⭐ | ⚡⚡⚡⚡ | Balanced |
| **medium** | ⭐⭐⭐⭐ | ⚡⚡⚡ | **แนะนำสำหรับ GPU 4080** |
| **large-v3** | ⭐⭐⭐⭐⭐ | ⚡⚡ | Best accuracy |

---

## 📊 Performance ประมาณการ (Medium Model + GPU 4080)

- **10 นาที video** → ~1-2 นาที transcription
- **30 นาที video** → ~3-5 นาที transcription
- **1 ชั่วโมง video** → ~6-10 นาที transcription

---

## 🔍 ตรวจสอบ Services

**ก่อนทดสอบ ตรวจสอบว่า services ทำงาน:**

```bash
# จาก Local Machine
curl http://205.196.17.108:8001/health
curl http://205.196.17.108:8002/health
```

**หรือ SSH เข้า Pod:**

```bash
ssh root@205.196.17.108 -p 13027
bash scripts/pod/test-runpod-gpu.sh
```

---

## 🔗 Related Documents

- **Model Recommendations:** [MODEL_RECOMMENDATIONS.md](./MODEL_RECOMMENDATIONS.md)
- **Scripts:** `scripts/pod/upload-and-test.sh`

---

**Last Updated:** 2024-12-19

