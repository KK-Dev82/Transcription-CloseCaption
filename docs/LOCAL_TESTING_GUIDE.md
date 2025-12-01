# 🧪 คู่มือการทดสอบ Faster-Whisper ที่ Local

## 📋 ภาพรวม

คู่มือนี้จะช่วยให้คุณทดสอบ faster-whisper ที่ local machine ก่อน deploy ไปยัง server

## ⚠️ เรื่อง Git Sync

### ถ้าแก้ไข Code บน Server แล้ว Code ที่ Local จะล้าหลังไหม?

**คำตอบ: ใช่** - Code ที่แก้บน server จะไม่ sync กับ local อัตโนมัติ

### วิธี Sync Code

#### 1. **Pull จาก Server** (ถ้าแก้บน server แล้วต้องการมา local)
```bash
# บน server
cd /workspace/transcription-service
git add .
git commit -m "Fix: faster-whisper transcription issue"
git push origin staging

# บน local
cd transcription-close-caption-service
git pull origin staging
```

#### 2. **Push จาก Local** (แนะนำ - แก้ที่ local แล้ว push ไป server)
```bash
# บน local
cd transcription-close-caption-service
git add .
git commit -m "Fix: faster-whisper transcription issue"
git push origin staging

# บน server
cd /workspace/transcription-service
git pull origin staging
```

### ⚠️ ข้อควรระวัง

- **อย่าแก้ code บน server โดยตรง** - จะทำให้ local และ server ไม่ sync
- **ใช้ Git workflow** - แก้ที่ local → commit → push → pull บน server
- **ตรวจสอบ git status** ก่อนแก้ไข

## 🚀 การทดสอบที่ Local

### ขั้นตอนที่ 1: ตรวจสอบ Virtual Environment

```bash
cd transcription-close-caption-service

# เปิดใช้งาน venv
source venv/bin/activate  # macOS/Linux
# หรือ
venv\Scripts\activate  # Windows
```

### ขั้นตอนที่ 2: ติดตั้ง Dependencies

```bash
# ติดตั้ง faster-whisper และ dependencies
pip install faster-whisper==1.0.3
pip install torch==2.1.1 torchaudio==2.1.1

# หรือติดตั้งทั้งหมด
pip install -r requirements.txt
```

### ขั้นตอนที่ 3: ทดสอบด้วย Script

```bash
# ใช้ script ที่สร้างไว้
python3 scripts/local/test-faster-whisper-local.py uploads/test_video.mp4 th base
```

### ขั้นตอนที่ 4: ทดสอบด้วย Python โดยตรง

```python
import asyncio
import os
from app.services.whisper_service import WhisperService

# Set environment variables
os.environ['WHISPER_PROVIDER'] = 'faster-whisper'
os.environ['WHISPER_DEVICE'] = 'cpu'  # ใช้ CPU สำหรับ local
os.environ['WHISPER_MODEL'] = 'base'

async def test():
    service = WhisperService()
    result = await service.transcribe_file(
        'uploads/test_audio.wav',
        language='th',
        model_size='base'
    )
    print(result['text'])

asyncio.run(test())
```

## 🔧 Configuration สำหรับ Local

### CPU Mode (แนะนำสำหรับ Local)

```bash
export WHISPER_PROVIDER=faster-whisper
export WHISPER_DEVICE=cpu
export WHISPER_MODEL=base  # ใช้ base (เล็กกว่า medium)
export WHISPER_COMPUTE_TYPE=float32
```

### GPU Mode (ถ้ามี GPU)

```bash
export WHISPER_PROVIDER=faster-whisper
export WHISPER_DEVICE=cuda
export WHISPER_MODEL=medium
export WHISPER_COMPUTE_TYPE=float16
```

## 📊 เปรียบเทียบ Performance

| Mode | Model | Speed (1 min audio) | Memory |
|------|-------|-------------------|--------|
| CPU | base | ~2-5 min | ~500MB |
| CPU | medium | ~10-20 min | ~2GB |
| GPU | base | ~5-10s | ~1GB |
| GPU | medium | ~30-60s | ~2GB |

## ✅ Checklist ก่อน Deploy

- [ ] ทดสอบที่ local สำเร็จ
- [ ] Commit code ไปยัง Git
- [ ] Push ไปยัง remote repository
- [ ] Pull บน server
- [ ] ทดสอบบน server อีกครั้ง

## 🐛 Troubleshooting

### ปัญหา: ModuleNotFoundError: No module named 'faster_whisper'

**แก้ไข:**
```bash
pip install faster-whisper==1.0.3
```

### ปัญหา: Transcription ช้ามาก (CPU mode)

**แก้ไข:**
- ใช้ model `base` แทน `medium` หรือ `large`
- หรือใช้ GPU ถ้ามี

### ปัญหา: CUDA out of memory

**แก้ไข:**
- ใช้ model ที่เล็กกว่า (base แทน medium)
- ลด batch_size
- ใช้ float16 แทน float32

## 📝 สรุป

1. **ทดสอบที่ local ก่อน** - ง่ายต่อการ debug
2. **ใช้ Git workflow** - แก้ที่ local → commit → push → pull บน server
3. **ใช้ CPU mode สำหรับ local** - ไม่ต้องมี GPU
4. **ใช้ base model สำหรับ local** - เร็วกว่า medium

