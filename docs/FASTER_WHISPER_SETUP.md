# 🚀 คู่มือ Setup faster-whisper 1.2.1

## 📋 สรุป

faster-whisper 1.2.1 ทำงานได้บน RunPod Template `runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04` แต่มีข้อจำกัดเกี่ยวกับ cuDNN version mismatch

---

## ✅ สิ่งที่ทำงานได้

- ✅ faster-whisper 1.2.1 ติดตั้งสำเร็จ
- ✅ CTranslate2 4.4.0 ติดตั้งสำเร็จ (รองรับ cuDNN 8.x)
- ✅ CPU mode ทำงานได้ (ช้ากว่า GPU แต่ใช้งานได้)
- ✅ Scripts auto-detect และเลือก CTranslate2 version ที่เหมาะสม

---

## ⚠️ ปัญหาที่พบ

### GPU Mode ไม่ทำงาน

**สาเหตุ**:
- PyTorch 2.2.0 ใช้ cuDNN 8.9.0.2 (8902)
- CTranslate2 4.6.2 ต้องการ cuDNN 9.x
- CTranslate2 4.4.0 รองรับ cuDNN 8.x แต่ต้องการ cuDNN libraries ครบ (`libcudnn_ops_infer.so.8`)

**Error**:
```
Could not load library libcudnn_ops_infer.so.8
```

---

## 💡 วิธีแก้ไข

### 1. ใช้ CPU Mode (แนะนำสำหรับการทดสอบ)

CPU mode ทำงานได้ทันที ไม่ต้องแก้ไขอะไร:

```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.wav")
```

**ข้อดี**:
- ✅ ทำงานได้ทันที
- ✅ ไม่ต้องแก้ไข cuDNN

**ข้อเสีย**:
- ⚠️ ช้ากว่า GPU mode ประมาณ 5-10x

---

### 2. ติดตั้ง cuDNN 9.x ในระบบ (สำหรับ Production)

ถ้าต้องการ GPU mode ต้องติดตั้ง cuDNN 9.x ในระบบ:

```bash
# ติดตั้ง cuDNN 9.x
# (ต้อง download จาก NVIDIA และติดตั้งเอง)
```

**ข้อดี**:
- ✅ GPU mode ทำงานได้
- ✅ Performance สูงสุด

**ข้อเสีย**:
- ⚠️ ซับซ้อน ต้องติดตั้ง cuDNN เอง

---

### 3. ใช้ PyTorch Backend (Fallback)

ถ้า faster-whisper ไม่ทำงาน ใช้ PyTorch backend แทน:

```python
import whisper

model = whisper.load_model("base")
result = model.transcribe("audio.wav")
```

**ข้อดี**:
- ✅ ทำงานได้แน่นอน
- ✅ ไม่มี cuDNN issues

**ข้อเสีย**:
- ⚠️ ช้ากว่า faster-whisper ประมาณ 2-4x

---

## 📝 ขั้นตอนการใช้งาน

### 1. ติดตั้ง Dependencies

```bash
cd /workspace/transcription-service
bash scripts/pod/install-requirements.sh
```

Script จะ:
- ✅ Auto-detect cuDNN version
- ✅ เลือก CTranslate2 version ที่เหมาะสม
- ✅ ติดตั้ง faster-whisper 1.2.1
- ✅ ติดตั้ง dependencies อื่นๆ

### 2. ทดสอบ faster-whisper

```bash
# ทดสอบ GPU mode (ถ้าไม่ทำงานจะ fallback เป็น CPU mode)
bash scripts/pod/test-faster-whisper-gpu.sh

# หรือทดสอบแบบละเอียด
bash scripts/pod/test-faster-whisper.sh
```

### 3. ใช้ใน Code

```python
from faster_whisper import WhisperModel

# ลอง GPU mode ก่อน
try:
    model = WhisperModel("base", device="cuda", compute_type="float16")
except:
    # Fallback เป็น CPU mode
    model = WhisperModel("base", device="cpu", compute_type="int8")

segments, info = model.transcribe("audio.wav")
```

---

## 🔧 Configuration

### Environment Variables

```bash
# ใช้ CPU mode (ถ้า GPU mode ไม่ทำงาน)
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# หรือใช้ GPU mode (ถ้ามี cuDNN ครบ)
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

---

## 📊 Performance

| Mode | เวลา (30 นาที) | หมายเหตุ |
|------|----------------|----------|
| GPU (cuDNN 9.x) | 1-2 นาที | เร็วที่สุด |
| GPU (cuDNN 8.x) | ⚠️ ไม่ทำงาน | ต้องมี cuDNN libraries ครบ |
| CPU | 10-20 นาที | ทำงานได้ แต่ช้า |
| PyTorch Backend | 5-10 นาที | Fallback option |

---

## ✅ Checklist

- [ ] ติดตั้ง dependencies: `bash scripts/pod/install-requirements.sh`
- [ ] ทดสอบ faster-whisper: `bash scripts/pod/test-faster-whisper-gpu.sh`
- [ ] ตรวจสอบว่า GPU mode ทำงานได้หรือไม่
- [ ] ถ้า GPU mode ไม่ทำงาน → ใช้ CPU mode หรือ PyTorch backend

---

## 💡 คำแนะนำ

1. **สำหรับการทดสอบ**: ใช้ CPU mode (ทำงานได้ทันที)
2. **สำหรับ Production**: ติดตั้ง cuDNN 9.x ในระบบเพื่อใช้ GPU mode
3. **Fallback**: ใช้ PyTorch backend ถ้า faster-whisper ไม่ทำงาน

---

## 📚 อ้างอิง

- [faster-whisper GitHub](https://github.com/guillaumekln/faster-whisper)
- [CTranslate2 Documentation](https://opennmt.net/CTranslate2/)
- [cuDNN Installation Guide](https://docs.nvidia.com/deeplearning/cudnn/install-guide/)

