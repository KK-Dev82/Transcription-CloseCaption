# 🎯 Model Recommendations สำหรับ GPU 4080

คำแนะนำการเลือก Whisper Model สำหรับ RTX 4080 เพื่อให้เทียบเท่า Groq API

---

## 📊 Model Comparison

| Model | Size | Accuracy | Speed (GPU 4080) | Use Case |
|-------|------|----------|-----------------|----------|
| **base** | 148MB | ⭐⭐ | ⚡⚡⚡⚡⚡ | Fast, low accuracy |
| **small** | 488MB | ⭐⭐⭐ | ⚡⚡⚡⚡ | Balanced |
| **medium** | 1.5GB | ⭐⭐⭐⭐ | ⚡⚡⚡ | **แนะนำสำหรับ GPU 4080** |
| **large-v3** | 3.1GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | Best accuracy |

---

## 🎯 คำแนะนำสำหรับ RTX 4080

### แนะนำ: **medium** model

**เหตุผล:**
- ✅ ความแม่นยำดี (เทียบเท่า Groq API)
- ✅ ความเร็วดี (GPU 4080 รองรับได้)
- ✅ Memory เพียงพอ (16GB VRAM)
- ✅ เหมาะสำหรับ Production

**Performance ประมาณการ:**
- 10 นาที video → ~1-2 นาที transcription
- 30 นาที video → ~3-5 นาที transcription
- 1 ชั่วโมง video → ~6-10 นาที transcription

---

## 🔧 วิธีเปลี่ยน Model

### Option 1: ระบุใน API Request (แนะนำ)

```bash
curl -X POST http://localhost:8001/api/transcription/upload \
  -F 'file=@video.mp4' \
  -F 'language=th' \
  -F 'model_size=medium'
```

### Option 2: ตั้งค่า Environment Variable

```bash
# ใน .env.runpod
WHISPER_MODEL=medium
```

### Option 3: เปลี่ยน Default ใน Code

```python
# app/services/whisper_providers/builtin_provider.py
self.default_model = "medium"  # แทน "base"
```

---

## 📥 Download Medium Model

### บน Pod Server:

```bash
cd /workspace/transcription-service/whisper-service
bash models/download-ggml-model.sh medium
cp models/ggml-medium.bin ../models/
```

### ตรวจสอบ:

```bash
ls -lh /workspace/transcription-service/models/ggml-medium.bin
# ควรเห็น: ~1.5GB
```

---

## 🧪 ทดสอบ Performance

### Test Script:

```bash
# บน Pod Server
bash scripts/pod/test-transcription.sh /path/to/video.mp4 medium

# จาก Local Machine
bash scripts/pod/upload-and-test.sh /path/to/video.mp4 205.196.17.108 8001 medium
```

---

## 🔗 Related Documents

- **Test Transcription:** `scripts/pod/test-transcription.sh`
- **Upload and Test:** `scripts/pod/upload-and-test.sh`

---

**Last Updated:** 2024-12-19

