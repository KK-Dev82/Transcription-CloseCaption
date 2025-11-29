# 📁 Utility Scripts

Scripts สำหรับการจัดการ Models และ Utilities อื่นๆ

## 📋 Scripts

### `download-models.sh`
**Download Whisper Models**
- Download models จาก Hugging Face
- รองรับ base, small, medium models
- ตรวจสอบ checksum
- เก็บ models ใน `models/` directory

**Usage:**
```bash
bash scripts/utility/download-models.sh
```

**Options:**
- `--model <size>` - Download specific model (base, small, medium)
- `--all` - Download all models
- `--force` - Force re-download

**Example:**
```bash
# Download base model
bash scripts/utility/download-models.sh --model base

# Download all models
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

| Model | Size | VRAM | Speed | Accuracy |
|-------|------|------|-------|----------|
| base | ~150MB | ~1GB | ⚡⚡⚡ | ⭐⭐⭐ |
| small | ~500MB | ~2GB | ⚡⚡ | ⭐⭐⭐⭐ |
| medium | ~1.5GB | ~5GB | ⚡ | ⭐⭐⭐⭐⭐ |

**แนะนำ:** ใช้ `small` สำหรับ production (สมดุลระหว่าง speed/accuracy)

