# 📁 Utility Scripts

Scripts สำหรับการจัดการ Models และ Utilities อื่นๆ

## 📋 Scripts

### `download-models.sh` ⭐
**Download Whisper Models**
- ดาวน์โหลด Whisper models จาก Hugging Face
- รองรับ: tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo
- รองรับทั้ง Docker Compose และ Direct Mode
- ตรวจสอบและ validate ไฟล์อัตโนมัติ
- เก็บ models ใน `models/` directory

**Usage:**
```bash
# ดาวน์โหลด base model (default)
bash scripts/utility/download-models.sh

# ดาวน์โหลดหลาย models
bash scripts/utility/download-models.sh base small medium

# ดาวน์โหลด base, small, medium (recommended)
bash scripts/utility/download-models.sh --all

# ใช้ whisper.cpp download script (ถ้ามี)
bash scripts/utility/download-models.sh medium --docker-script

# ไม่ restart services หลัง download
bash scripts/utility/download-models.sh base --skip-restart
```

**Options:**
- `--all` - Download base, small, medium models
- `--docker-script` - Use whisper.cpp download script (if available)
- `--skip-restart` - Skip restarting containers/services

**Examples:**
```bash
# Download base model (สำหรับ CPU หรือ testing)
bash scripts/utility/download-models.sh base

# Download medium model (สำหรับ GPU 4080) ⭐ แนะนำ
bash scripts/utility/download-models.sh medium

# Download multiple models
bash scripts/utility/download-models.sh base small medium

# Download all recommended models
bash scripts/utility/download-models.sh --all
```

---

### `fix-models.sh`
**Fix Missing App Models**
- สร้างไฟล์ models ที่ขาดหายไป
- Copy models จาก whisper-service/models
- ตรวจสอบและแก้ไข permission

**Usage:**
```bash
bash scripts/utility/fix-models.sh
```

**Use Case:**
- เมื่อ models หายไปหรือ permission ผิด
- หลังจาก clone repository ใหม่

---

## 🔗 Related Files

- `models/` - Directory สำหรับเก็บ Whisper models
- `whisper-service/models/` - Models ใน Whisper service

---

## 📝 Model Information

| Model | Size | VRAM | Speed (GPU 4080) | Accuracy | Use Case |
|-------|------|------|-----------------|----------|----------|
| tiny | ~75MB | ~500MB | ⚡⚡⚡⚡⚡ | ⭐⭐ | Fast testing |
| base | ~148MB | ~1GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | CPU, Fast |
| small | ~488MB | ~2GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Balanced |
| medium | ~1.5GB | ~5GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | **GPU 4080** ⭐ |
| large | ~3.1GB | ~10GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Best accuracy |
| large-v3 | ~3.1GB | ~10GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Latest model |

**แนะนำ:**
- **CPU:** ใช้ `base` หรือ `small`
- **GPU 4080:** ใช้ `medium` (เทียบเท่า Groq API) ⭐
- **Best Accuracy:** ใช้ `large-v3`

