# 🚀 คู่มือ Setup RunPod Template

## 📋 Base Image

**RunPod Template**: `runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04`

### Components
- ✅ PyTorch: 2.2.0
- ✅ Python: 3.10
- ✅ CUDA: 12.1.1
- ✅ cuDNN: ต้องตรวจสอบ (8.x หรือ 9.x)
- ✅ Ubuntu: 22.04

---

## 🔍 ขั้นตอนที่ 1: ตรวจสอบ Compatibility

```bash
cd /workspace/transcription-service
bash scripts/pod/check-compatibility.sh
```

Script นี้จะตรวจสอบ:
- ✅ Python version
- ✅ PyTorch และ CUDA
- ✅ cuDNN version
- ✅ CTranslate2 compatibility
- ✅ Dependencies ที่มีอยู่แล้ว

---

## 📦 ขั้นตอนที่ 2: ติดตั้ง Requirements

```bash
cd /workspace/transcription-service
bash scripts/pod/install-requirements.sh
```

Script นี้จะ:
1. ตรวจสอบ cuDNN version
2. เลือก CTranslate2 version ที่เหมาะสม:
   - cuDNN 9.x → CTranslate2 4.6.2+
   - cuDNN 8.x → CTranslate2 4.4.0
3. ติดตั้ง NumPy (<2.0.0)
4. ติดตั้ง CTranslate2
5. ติดตั้ง faster-whisper 1.2.1
6. ทดสอบ faster-whisper
7. ติดตั้ง dependencies อื่นๆ จาก requirements.txt

---

## 🚀 ขั้นตอนที่ 3: Start Services

```bash
cd /workspace/transcription-service
bash scripts/pod/start-pod.sh
```

หรือ

```bash
bash scripts/pod/start-services-direct.sh
```

---

## ⚙️ Environment Variables

ตั้งค่าใน RunPod Pod Settings หรือ `.env.runpod`:

```bash
WHISPER_PROVIDER=faster-whisper
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
CT2_USE_CUDA_GRAPH=0
```

---

## 📊 Performance

| Configuration | เวลา (30 นาที) |
|--------------|----------------|
| faster-whisper 1.2.1 + CUDA 12.1.1 + cuDNN 9 | **1-2 นาที** ✅ |
| faster-whisper 1.2.1 + CUDA 12.1.1 + cuDNN 8 | 1.5-2.5 นาที |

---

## ⚠️ Troubleshooting

### ปัญหา: cuDNN version mismatch

**แก้ไข**: Script จะเลือก CTranslate2 version อัตโนมัติ:
- cuDNN 9.x → CTranslate2 4.6.2+
- cuDNN 8.x → CTranslate2 4.4.0

### ปัญหา: NumPy version conflict

**แก้ไข**: Script จะติดตั้ง NumPy <2.0.0 อัตโนมัติ

### ปัญหา: faster-whisper ไม่ทำงาน

**ตรวจสอบ**:
```bash
python3 -c "from faster_whisper import WhisperModel; model = WhisperModel('base', device='cuda'); print('OK')"
```

---

## ✅ Checklist

- [ ] Clone repository: `git clone <repo> /workspace/transcription-service`
- [ ] ตรวจสอบ compatibility: `bash scripts/pod/check-compatibility.sh`
- [ ] ติดตั้ง requirements: `bash scripts/pod/install-requirements.sh`
- [ ] Start services: `bash scripts/pod/start-pod.sh`
- [ ] ทดสอบ API: `curl http://localhost:8010/health`

---

## 📝 หมายเหตุ

1. **ไม่ต้อง build image ใหม่** - ใช้ RunPod Template โดยตรง
2. **ติดตั้ง dependencies ใน Pod** - ใช้ script `install-requirements.sh`
3. **Auto-detect cuDNN version** - Script จะเลือก CTranslate2 version ที่เหมาะสม
4. **Performance สูงสุด** - faster-whisper 1.2.1 + CUDA 12.1.1

