# OpenAI Whisper Provider with CUDA Setup

## ภาพรวม

ระบบใช้ `openai-whisper` Python library พร้อม PyTorch CUDA สำหรับ transcription บน RunPod GPU Server และ HP Z2 Workstation

## คำตอบคำถาม

### 1. จำเป็นต้องใช้ PyTorch + CUDA เพื่อประสิทธิภาพที่ดีไหม?

**คำตอบ: จำเป็นมาก** ✅

- `openai-whisper` ใช้ PyTorch เป็น backend
- **GPU acceleration**: เร็วกว่า CPU มาก (10-50x ขึ้นอยู่กับ model)
- **Model large-v3**: ต้องการ GPU เพื่อให้ได้ประสิทธิภาพตามเป้าหมาย (10 นาที video < 1.5 นาที)
- **CPU only**: ใช้ได้แต่ช้ามาก (10 นาที video อาจใช้เวลา 10-30 นาที)

**เปรียบเทียบ Performance:**
- **CPU (base model)**: ~1x real-time (10 นาที video = 10 นาที processing)
- **GPU (base model)**: ~10-20x real-time (10 นาที video = 30-60 วินาที)
- **GPU (large-v3 model)**: ~5-10x real-time (10 นาที video = 60-120 วินาที)

### 2. Ubuntu 22 LTS, 24 LTS ใช้ได้รึเปล่า?

**คำตอบ: ใช้ได้ทั้งสอง** ✅

- **Ubuntu 22.04 LTS**: รองรับเต็มที่ (ใช้ใน Dockerfile.runpod-base)
- **Ubuntu 24.04 LTS**: รองรับเต็มที่ (CUDA 12.1 และ PyTorch 2.1.1 รองรับ)

**CUDA Compatibility:**
- CUDA 12.1 รองรับ Ubuntu 20.04, 22.04, 24.04
- PyTorch 2.1.1 รองรับ CUDA 11.8 และ 12.1

### 3. Transcription Service มี FFmpeg ในตัวไหม?

**คำตอบ: มีอยู่แล้ว** ✅

**FFmpeg ใน Transcription Service:**
- ✅ `Dockerfile.runpod-base` ติดตั้ง `ffmpeg` system package
- ✅ `requirements.txt` มี `ffmpeg-python==0.2.0` library
- ✅ `video_service.py` ใช้ FFmpeg สำหรับ:
  - Extract audio from video
  - Create audio chunks
  - Video trimming/merging
- ✅ `file_service.py` ใช้ FFmpeg สำหรับ extract audio

**ถ้าไม่มี FFmpeg จะเป็นปัญหาอะไร?**
- ❌ ไม่สามารถ extract audio จาก video ได้
- ❌ ไม่สามารถสร้าง audio chunks ได้
- ❌ Transcription service จะไม่ทำงาน

**ถ้าเพิ่ม FFmpeg จะช่วยให้อะไรดีขึ้นบ้าง?**
- ✅ **Performance**: FFmpeg native (C++) เร็วกว่า Python library
- ✅ **Format Support**: รองรับ video formats มากกว่า
- ✅ **Optimization**: สามารถ optimize audio extraction สำหรับ Whisper (16kHz mono)
- ✅ **Production Ready**: เหมาะสำหรับ production ที่ต้องการ performance สูง

**หมายเหตุ**: Production มี FFmpeg service แยกอยู่แล้ว แต่ Transcription Service ยังต้องใช้ FFmpeg สำหรับ:
- Extract audio chunks จาก video (ต้องทำใน transcription service)
- Pre-process audio สำหรับ Whisper (sample rate, channels)

## การ Setup

### 1. Build Base Image

```bash
cd transcription-close-caption-service
docker build -f Dockerfile.runpod-base -t kksenateacr.azurecr.io/kk-transcription-runpod-base:latest --platform linux/amd64 .
```

### 2. Push to ACR

```bash
az acr login --name kksenateacr
docker push kksenateacr.azurecr.io/kk-transcription-runpod-base:latest
```

### 3. RunPod Setup

1. **Create Pod**:
   - Template: Custom Image
   - Image: `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest`
   - GPU: RTX 4080 หรือสูงกว่า
   - Container: Ubuntu 22.04

2. **Clone Repository**:
   ```bash
   cd /workspace
   git clone <repo-url> transcription-service
   cd transcription-service
   ```

3. **Setup**:
   ```bash
   bash scripts/pod/setup-pod.sh
   ```

4. **Start Services**:
   ```bash
   bash scripts/pod/start-pod.sh
   ```

### 4. Configuration

**Environment Variables** (ใน `.env.runpod`):
```bash
WHISPER_PROVIDER=openai-whisper
WHISPER_MODEL=large-v3
WHISPER_DEVICE=auto  # auto-detect CUDA
CUDA_VISIBLE_DEVICES=0
```

**Model Selection**:
- `tiny`: เร็วสุด, ความแม่นยำต่ำ
- `base`: เร็ว, ความแม่นยำปานกลาง
- `small`: ปานกลาง, ความแม่นยำดี
- `medium`: ช้า, ความแม่นยำดีมาก
- `large`: ช้าสุด, ความแม่นยำสูงสุด
- `large-v3`: **แนะนำสำหรับ production** (ความแม่นยำสูงสุด)

## Performance Targets

### เป้าหมาย: 10 นาที video < 1.5 นาที processing

**Model large-v3 + RTX 4080:**
- Expected: ~5-10x real-time
- 10 นาที video = 60-120 วินาที processing ✅

**Model large-v3 + RTX 4070:**
- Expected: ~3-5x real-time
- 10 นาที video = 120-200 วินาที processing ⚠️ (อาจไม่บรรลุเป้าหมาย)

**Model large-v3 + CPU:**
- Expected: ~0.3-0.5x real-time
- 10 นาที video = 20-30 นาที processing ❌ (ไม่บรรลุเป้าหมาย)

## Troubleshooting

### CUDA ไม่ทำงาน

```bash
# ตรวจสอบ CUDA
nvidia-smi

# ตรวจสอบ PyTorch CUDA
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

### Model ไม่ download

```bash
# Download model manually
python3 -c "import whisper; whisper.load_model('large-v3')"
```

### FFmpeg ไม่ทำงาน

```bash
# ตรวจสอบ FFmpeg
ffmpeg -version

# Test audio extraction
ffmpeg -i test.mp4 -acodec pcm_s16le -ar 16000 -ac 1 test.wav
```

## เปรียบเทียบ Providers

| Provider | Performance | Accuracy | GPU Required | On-Premise |
|----------|-------------|----------|--------------|------------|
| **openai-whisper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Recommended | ✅ |
| whisper.cpp | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Recommended | ✅ |
| Groq API | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ (Cloud) | ❌ |

**แนะนำ**: ใช้ `openai-whisper` สำหรับ RunPod และ Z2 เพราะ:
- ประสิทธิภาพดีที่สุด
- รองรับ CUDA เต็มรูปแบบ
- Model large-v3 มีความแม่นยำสูงสุด

