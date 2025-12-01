# 🔄 อัปเดต Custom Base Image สำหรับ RunPod

## 📋 สรุปการเปลี่ยนแปลง

Custom Image `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest` **ไม่ได้** build จาก `Dockerfile.local-faster-whisper-gpu`

### ✅ Dockerfile ที่ใช้จริง

- **Dockerfile**: `Dockerfile.runpod-base`
- **Script Build**: `scripts/pod/build-and-push-runpod-base.sh`

### 🔧 การเปลี่ยนแปลง

อัปเดต `Dockerfile.runpod-base` ให้ติดตั้ง:

1. **faster-whisper** พร้อมเวอร์ชันที่เข้ากันได้:
   - `numpy==1.26.4`
   - `ctranslate2==4.5.0`
   - `faster-whisper==1.0.2`

2. **Environment Variables** เพื่อป้องกัน freeze:
   - `CT2_USE_CUDA_GRAPH=0` (ปิด CUDA Graph)
   - `OMP_NUM_THREADS=4`
   - `MKL_NUM_THREADS=4`

3. **Default Provider**: เปลี่ยนจาก `openai-whisper` เป็น `faster-whisper`

## 🚀 วิธี Build และ Push Image ใหม่

```bash
# 1. Login ACR
az acr login --name kksenateacr

# 2. Build และ Push
bash scripts/pod/build-and-push-runpod-base.sh
```

## 📝 หลังจาก Pod Pull Image ใหม่

Image ใหม่จะมี faster-whisper ติดตั้งอยู่แล้ว ไม่ต้องติดตั้งใหม่บน Pod

### ตรวจสอบบน Pod:

```bash
# ตรวจสอบ faster-whisper
python3 -c "from faster_whisper import WhisperModel; print('OK')"

# ตรวจสอบ versions
pip3 list | grep -E 'faster-whisper|ctranslate2|numpy|torch'
```

### ทดสอบ GPU:

```bash
export CT2_USE_CUDA_GRAPH=0
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=0

python3 -c "
from faster_whisper import WhisperModel
m = WhisperModel('tiny', device='cuda', compute_type='float16', num_workers=1, cpu_threads=4)
segs, info = m.transcribe('uploads/v05-1_16k.wav', language='th', vad_filter=False, without_timestamps=True, beam_size=1, temperature=0.0)
print('Type:', type(segs))
if isinstance(segs, list):
    print('✓ LIST! First:', segs[0].text[:50])
else:
    first = next(iter(segs))
    print('Generator, first:', first.text[:50])
"
```

## ⚠️ หมายเหตุ

- `Dockerfile.local-faster-whisper-gpu` ใช้สำหรับ **Local Development** เท่านั้น
- RunPod ใช้ `Dockerfile.runpod-base` (Direct Mode - ไม่ใช้ Docker Compose)
- Image ใหม่จะใช้ CUDA 11.8 compatible wheels (PyTorch 2.1.1+cu118)

