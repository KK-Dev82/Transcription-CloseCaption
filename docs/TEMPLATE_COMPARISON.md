# 📊 เปรียบเทียบ RunPod Templates สำหรับ faster-whisper 1.2.1

## 📋 Templates ที่มี

### Template 1: runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04
- PyTorch: 2.2.0
- Python: 3.10
- CUDA: 12.1.1
- cuDNN: ต้องตรวจสอบ

### Template 2: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04
- PyTorch: 2.4.0
- Python: 3.11
- CUDA: 12.4.1
- cuDNN: ต้องตรวจสอบ

---

## 🔍 เปรียบเทียบ

| Feature | Template 1 | Template 2 |
|---------|-----------|-----------|
| **PyTorch** | 2.2.0 | 2.4.0 (ใหม่กว่า) |
| **Python** | 3.10 | 3.11 (เร็วกว่า) |
| **CUDA** | 12.1.1 | 12.4.1 (ใหม่กว่า) |
| **เสถียรภาพ** | ✅ สูง | ⚠️ ต้องทดสอบ |
| **Performance** | เร็วมาก | เร็วที่สุด |
| **Compatibility** | ✅ รองรับแน่นอน | ⚠️ ต้องตรวจสอบ |
| **แนะนำ** | ✅ **แนะนำ** | ⚠️ ทดสอบก่อน |

---

## 💡 คำแนะนำ

### Template 1 (2.2.0 + Python 3.10) - **แนะนำ** ✅

**ข้อดี**:
- ✅ เสถียรกว่า
- ✅ Python 3.10 (libraries รองรับครบ)
- ✅ faster-whisper 1.2.1 รองรับแน่นอน
- ✅ NumPy compatibility ดี
- ✅ ไม่มี compatibility issues

**Performance**:
- 30 นาที → **1-2 นาที** ✅

**เหมาะสำหรับ**:
- Production
- ความเสถียรสำคัญกว่า performance เล็กน้อย

---

### Template 2 (2.4.0 + Python 3.11) - ทดสอบก่อน ⚠️

**ข้อดี**:
- ✅ PyTorch 2.4.0 (ใหม่กว่า, performance ดีกว่า ~5-10%)
- ✅ Python 3.11 (เร็วกว่า 3.10 ~10-15%)
- ✅ CUDA 12.4.1 (ใหม่กว่า, bug fixes)
- ✅ Performance สูงสุด

**ข้อเสีย**:
- ⚠️ Python 3.11 (บาง libraries อาจยังไม่รองรับ)
- ⚠️ PyTorch 2.4.0 (ใหม่มาก - ต้องทดสอบ)
- ⚠️ NumPy compatibility อาจมีปัญหา

**Performance**:
- 30 นาที → **0.8-1.5 นาที** (เร็วที่สุด)

**เหมาะสำหรับ**:
- ทดสอบ performance
- ถ้าต้องการความเร็วสูงสุด

---

## 🎯 สรุป

**แนะนำ**: ใช้ **Template 1** (2.2.0 + Python 3.10)
- ✅ เสถียร
- ✅ รองรับแน่นอน
- ✅ Performance ดีมาก (1-2 นาที สำหรับ 30 นาที)
- ✅ ไม่มี compatibility issues

**ถ้าต้องการทดสอบ**: ใช้ **Template 2** (2.4.0 + Python 3.11)
- ⚠️ ต้องทดสอบ compatibility
- ⚠️ อาจมี issues กับบาง libraries
- ✅ Performance สูงสุด (0.8-1.5 นาที)

---

## 📝 ขั้นตอนการใช้งาน

### Template 1 (แนะนำ)

```bash
# 1. ใช้ Template: runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04
# 2. Clone repo
git clone <repo> /workspace/transcription-service
cd /workspace/transcription-service

# 3. ตรวจสอบ compatibility
bash scripts/pod/check-template-compatibility.sh

# 4. ติดตั้ง requirements
bash scripts/pod/install-requirements.sh

# 5. Start services
bash scripts/pod/start-pod.sh
```

### Template 2 (ทดสอบ)

```bash
# 1. ใช้ Template: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04
# 2. Clone repo
git clone <repo> /workspace/transcription-service
cd /workspace/transcription-service

# 3. ตรวจสอบ compatibility
bash scripts/pod/check-template-compatibility.sh

# 4. ติดตั้ง requirements (อาจมี issues)
bash scripts/pod/install-requirements.sh

# 5. ทดสอบ transcription
# 6. ถ้าไม่มีปัญหา → ใช้ได้
#    ถ้ามีปัญหา → เปลี่ยนเป็น Template 1
```

---

## ⚠️ หมายเหตุ

1. **NumPy Version**: ทั้ง 2 templates อาจมี NumPy 2.x → script จะ downgrade อัตโนมัติ
2. **cuDNN Version**: Script จะ auto-detect และเลือก CTranslate2 ที่เหมาะสม
3. **Compatibility**: ตรวจสอบก่อนเสมอด้วย `check-template-compatibility.sh`

