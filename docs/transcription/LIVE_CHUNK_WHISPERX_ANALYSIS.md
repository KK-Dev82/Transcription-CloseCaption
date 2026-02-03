# การวิเคราะห์: เพิ่ม Live-Chunk อีก 1 Version ด้วย WhisperX

## สรุปคำถาม
ถ้าเพิ่ม Features สำหรับ **live-chunk อีก 1 version** โดยใช้ **WhisperX** (ที่อาจเหมาะกับ Live Streaming มากกว่า) จะเกิด **Conflict** ใดหรือไม่ เมื่อตอนนี้ใช้ **Faster-Whisper** กับ:
- การแปลงวิดีโอ/เสียง (transcription)
- live-chunk (real-time caption)

---

## สถานะปัจจุบันของระบบ

### 1. Dependencies (`requirements.txt`)

| Package | Version | หมายเหตุ |
|--------|---------|----------|
| **openai-whisper** | 20231117 | ใช้สำหรับ builtin/fallback |
| **faster-whisper** | 1.2.1 | ใช้กับ transcription + live-chunk |
| **ctranslate2** | 4.4.0 | ใช้กับ cuDNN 8.x (PyTorch 2.2.0) |
| **torch / torchaudio** | จาก base image | 2.2.0+cu121 (ไม่ใส่ใน requirements เพื่อหลีกเลี่ยง conflict) |

### 2. การใช้ Provider ในระบบ

- **Video/Audio transcription**  
  ใช้ `WhisperService` → `WhisperProviderFactory.get_with_fallback()` → ปัจจุบันได้ **FasterWhisperProvider** (จาก `WHISPER_PROVIDER=faster-whisper`)

- **Live-chunk**  
  ใช้ **path เดียวกัน**:  
  `realtime_transcription.py` → `whisper_service.transcribe_file()` → **provider เดียวกับ transcription** (FasterWhisperProvider)

- **Singleton**:  
  `WhisperService` โหลด provider ครั้งเดียว (lazy) จาก `WHISPER_PROVIDER` ดังนั้น **transcription กับ live-chunk ใช้ provider ตัวเดียวกัน** ในแต่ละ process

### 3. โครงสร้างที่เกี่ยวข้อง

```
app/api/realtime_transcription.py
  → whisper_service (WhisperService)
  → whisper_service.transcribe_file() → provider.transcribe()

app/services/whisper_service.py
  → WhisperProviderFactory.get_with_fallback()
  → provider = FasterWhisperProvider (จาก WHISPER_PROVIDER)

app/services/whisper_providers/
  → base_provider.py   (interface: transcribe → TranscriptionResult)
  → faster_whisper_provider.py
  → provider_factory.py (สร้าง provider ตาม WHISPER_PROVIDER)
```

---

## WhisperX ใช้ dependencies อะไร (จาก pyproject.toml ล่าสุด)

```toml
dependencies = [
  "ctranslate2>=4.5.0",
  "faster-whisper>=1.1.1",
  "nltk>=3.9.1",
  "numpy>=2.1.0",
  "pandas>=2.2.3",
  "pyannote-audio>=3.3.2,<4.0.0",
  "huggingface-hub<1.0.0",
  "torch~=2.8.0",
  "torchaudio~=2.8.0",
  "transformers>=4.48.0",
  "triton>=3.3.0; ..."
]
```

- WhisperX **ใช้ faster-whisper เป็น backend** อยู่แล้ว (สำหรับ ASR)
- แต่ยังพ่วง **PyTorch 2.8**, **pyannote-audio**, **transformers** (สำหรับ alignment / diarization ฯลฯ)

---

## Conflict ที่จะเกิดถ้าติดตั้ง WhisperX ใน env เดียวกับของเดิม

### 1. PyTorch / torchaudio (ความขัดแย้งหลัก)

| โปรเจกต์ปัจจุบัน | WhisperX |
|------------------|----------|
| torch 2.2.0+cu121 (จาก base image) | torch~=2.8.0 |
| torchaudio 2.2.0+cu121 | torchaudio~=2.8.0 |

- ถ้า `pip install whisperx` ใน env เดียวกัน pip จะพยายามอัปเกรด torch/torchaudio เป็น ~2.8
- ผลที่ได้:
  - **cuDNN / CUDA** ที่เทสกับ 2.2.0+cu121 อาจไม่ตรงกับ 2.8
  - **ctranslate2** และ **faster-whisper** ถูกเทสกับ PyTorch 2.2 และ cuDNN 8.x ในโปรเจกต์นี้; เปลี่ยนเป็น 2.8 อาจกระทบ stability
  - หมายเหตุใน `requirements.txt` ระบุชัดว่า “torch และ torchaudio ใช้จาก base image” และ “ไม่ต้องติดตั้งใหม่ เพื่อหลีกเลี่ยง conflict”

**สรุป:** การใส่ WhisperX ใน **requirements.txt เดียวกับที่ใช้ torch 2.2 จาก base image** มีโอกาส **Conflict สูง** กับ PyTorch/CUDA/cuDNN และอาจทำให้ transcription + live-chunk (Faster-Whisper) ทำงานผิดปกติ

### 2. ctranslate2

| โปรเจกต์ปัจจุบัน | WhisperX |
|------------------|----------|
| ctranslate2==4.4.0 (ปักเวอร์ชันสำหรับ cuDNN 8.x) | ctranslate2>=4.5.0 |

- อัปเกรดเป็น 4.5+ อาจทำให้ต้องปรับ LD_LIBRARY_PATH / cuDNN อีก
- ไม่รุนแรงเท่า PyTorch แต่ก็เป็นจุดที่ต้องทดสอบถ้าจะใช้ env เดียว

### 3. numpy

- WhisperX ต้องการ `numpy>=2.1.0`
- โปรเจกต์อาจยังใช้ numpy 1.x ในบาง image → อาจถูกอัปเกรดและกระทบ package อื่น

### 4. การอยู่ร่วมกันของโค้ด (ไม่มี conflict แบบ logic)

- **Provider pattern**: มี `WhisperProvider` (base) และ `WhisperProviderFactory` อยู่แล้ว
- **Live-chunk**: เรียก `whisper_service.transcribe_file()` ไม่ได้ผูกกับ implementation ของ Faster-Whisper โดยตรง
- ดังนั้น **ถ้ามี WhisperXProvider ที่ implement interface เดียวกัน** (รับ `audio_path`, คืน `TranscriptionResult`) การเพิ่ม “live-chunk อีก 1 version ที่ใช้ WhisperX” **ไม่ขัดกับ architecture** — จะขัดเฉพาะที่ระดับ **dependency (pip/env)**

---

## ทางเลือกในการเพิ่ม Live-Chunk Version ที่ใช้ WhisperX โดยลด Conflict

### ทางเลือก A: แยก Runtime (แนะนำถ้าต้องใช้ WhisperX จริง)

- **แนวคิด:** ไม่ใส่ WhisperX ใน main app / requirements.txt
- **การทำ:**
  - รัน **worker (หรือ service) แยก** ที่มี env ของตัวเอง:
    - image/conda env ที่ติดตั้ง **WhisperX + torch 2.8** (และ ctranslate2 ที่ WhisperX ต้องการ)
    - ไม่ใช้ torch 2.2+cu121 ของโปรเจกต์หลัก
  - Live-chunk “version WhisperX” ส่งงานไปยัง **queue ของ worker WhisperX** (หรือ HTTP ให้ service นั้น)
  - Worker WhisperX แปลงเสร็จแล้วส่งผลกลับผ่าน Redis/HTTP เหมือนปัจจุบัน (เช่น `send_ws_event_via_http`)
- **ข้อดี:** ไม่กระทบ Faster-Whisper, transcription วิดีโอ/เสียง และ live-chunk version ปัจจุบัน
- **ข้อเสีย:** ต้องจัดการ deployment / queue / config แยก

### ทางเลือก B: Optional dependency + แยก process (ไม่รวมใน process เดียวกับ Faster-Whisper)

- **แนวคิด:** ใส่ WhisperX เป็น optional เช่น `pip install .[whisperx]`
- **ข้อควรระวัง:** ถ้า run **process เดียว** (เช่น worker ตัวเดียว) ที่ทั้งโหลด Faster-Whisper และ WhisperX จะยังเสี่ยงเรื่อง PyTorch/ctranslate2 เวอร์ชันไม่ตรง
- **แนวทางที่ปลอดภัย:** ใช้ optional dependency แต่ **รัน WhisperX ใน process อื่น** (เช่น worker อีกประเภทหนึ่ง ที่ไม่โหลด Faster-Whisper) — เทียบเท่า “แยก runtime” แต่ยังอยู่ใน repo เดียว

### ทางเลือก C: ใช้เฉพาะ Faster-Whisper ใน live-chunk แต่ปรับพารามิเตอร์/โมเดล

- **แนวคิด:** ไม่เพิ่ม WhisperX; ปรับ **Faster-Whisper** ให้เหมาะกับ live streaming มากขึ้น (chunk size, VAD, beam_size, batch สำหรับ short chunk ฯลฯ)
- **ข้อดี:** ไม่มี dependency conflict เลย
- **ข้อเสีย:** ไม่ได้ฟีเจอร์เฉพาะของ WhisperX (เช่น alignment, diarization ที่อาจมีใน roadmap)

---

## สรุปคำตอบ: จะเกิด Conflict หรือไม่

| หัวข้อ | คำตอบ |
|--------|--------|
| **Conflict ระดับ dependency (pip/env)** | **ใช่** — ถ้าติดตั้ง WhisperX ใน **environment เดียว** กับที่ใช้อยู่ตอนนี้ (torch 2.2+cu121, ctranslate2==4.4.0, faster-whisper 1.2.1) จะมีความเสี่ยง **PyTorch/torchaudio เวอร์ชันข้าม**, และอาจกระทบ **Faster-Whisper + transcription วิดีโอ/เสียง + live-chunk ปัจจุบัน** |
| **Conflict ระดับ architecture/โค้ด** | **ไม่** — การเพิ่ม “live-chunk อีก 1 version” ที่ใช้ WhisperX ผ่าน provider pattern (เช่น endpoint แยก หรือ queue แยกไปยัง WhisperX worker) **ไม่ทำให้โครงสร้างเดิมขัดกัน** |
| **แนวทางที่ปลอดภัย** | **แยก runtime** สำหรับ WhisperX (worker/service อีกตัว, env อื่น ที่มี torch 2.8 + WhisperX) และให้ live-chunk “version WhisperX” ใช้ runtime นั้นเท่านั้น ไม่ใส่ WhisperX ใน requirements.txt หลัก |

---

## ใช้ requirements เดียวกันได้ไหม (faster-whisper + WhisperX)

**ตอบ: ได้** โดยอัปเกรดไปใช้ **ชุด dependency ที่ WhisperX ใช้** แล้วให้ faster-whisper ใช้ชุดเดียวกัน

### เหตุผลที่ทำได้

1. **faster-whisper ไม่ได้ depend บน PyTorch โดยตรง**  
   ใช้แค่ **CTranslate2** สำหรับ inference ดังนั้น:
   - ถ้าใช้ **ctranslate2>=4.5.0** กับ **CUDA 12.4+ / cuDNN 9** (ที่มากับ PyTorch 2.8+cu124/cu128) แล้ว faster-whisper จะทำงานได้ปกติ
2. **ความสัมพันธ์ CTranslate2 กับ PyTorch/CUDA** (จากชุมชน):
   - **PyTorch 2.\*+cu121** → ใช้ **CTranslate2 ≤4.4.0** (cuDNN 8)
   - **PyTorch 2.\*+cu124 หรือ ≥2.4** → ใช้ **CTranslate2 ≥4.5.0** (cuDNN 9, CUDA ≥12.3)
3. **WhisperX** กำหนด: `torch~=2.8.0`, `torchaudio~=2.8.0`, `ctranslate2>=4.5.0`, `faster-whisper>=1.1.1`  
   → ถ้าใช้ชุดนี้เป็นหลัก **ทั้ง faster-whisper และ WhisperX ใช้ dependency ชุดเดียวกันได้**

### แนวทาง: ชุด dependency เดียวกัน

| Package | เวอร์ชันที่ใช้ร่วมกัน | หมายเหตุ |
|--------|------------------------|----------|
| **torch** | ~2.8.0 (หรือ 2.8.x+cu124/cu128) | ต้องเปลี่ยนจาก base image 2.2.0+cu121 |
| **torchaudio** | ~2.8.0 | คู่กับ torch |
| **ctranslate2** | ≥4.5.0 | ใช้กับ cuDNN 9 / CUDA 12.4+ |
| **faster-whisper** | ≥1.1.1 (เช่น 1.2.1) | ใช้ ctranslate2 ตัวนี้ได้ |
| **whisperx** | ล่าสุดที่รองรับ (เช่น 3.7.x) | จะดึง pyannote, transformers ฯลฯ มา |

สิ่งที่ต้องเปลี่ยนในโปรเจกต์:

1. **Base image / การติดตั้ง PyTorch**  
   - ไม่พึ่ง torch จาก base image 2.2.0+cu121  
   - ใช้ base image ที่มี **Python 3.10+** แล้วติดตั้ง **torch 2.8+cu124 หรือ cu128** (จาก [PyTorch wheel](https://download.pytorch.org/whl/torch_stable.html)) หรือใช้ image ที่มี PyTorch 2.8 อยู่แล้ว

2. **requirements.txt**  
   - ใส่ **torch** และ **torchaudio** เวอร์ชันที่เลือก (เช่น 2.8.x สำหรับ CUDA 12.8)  
   - ใส่ **ctranslate2>=4.5.0** แทน 4.4.0  
   - คง **faster-whisper==1.2.1** (หรือ ≥1.1.1)  
   - เพิ่ม **whisperx** (และถ้าต้องการ pin ก็ระบุเวอร์ชัน)

3. **LD_LIBRARY_PATH / cuDNN**  
   - CTranslate2 4.5+ ใช้ **cuDNN 9**  
   - ปรับ path ให้ชี้ไปที่ cuDNN ที่มากับ PyTorch 2.8 (หรือที่ติดตั้งในระบบ) ใน `app/main.py` และ `scripts/pod/start-rq-workers.sh`

4. **ทดสอบ**  
   - รัน transcription (faster-whisper) และ live-chunk หลังอัปเกรด  
   - รัน WhisperX (ถ้ามี script/endpoint) ให้แน่ใจว่าไม่มี import error หรือ CUDA/cuDNN error

### ทางเลือกอีกทาง (อยู่กับ PyTorch 2.2)

ถ้าต้อง **คง PyTorch 2.2.0+cu121 และ ctranslate2==4.4.0** ไว้:

- WhisperX เวอร์ชันใหม่ (3.7.x) กำหนด `torch~=2.8.0` ใน pyproject โดยตรง จึง **ไม่สามารถใช้ requirements เดียวกับ WhisperX 3.7 ใน env เดียวกับ torch 2.2 ได้โดยไม่ override**
- อาจลอง **WhisperX เวอร์ชันเก่า** ที่อาจรองรับ torch>=2.0 หรือ 2.2 (เช่น 3.2 / 3.3) แล้วติดตั้งด้วย `--no-deps` และใส่ torch/ctranslate2 เอง — วิธีนี้เสี่ยงกับความไม่ตรงของ pyannote/lightning และไม่แนะนำสำหรับระยะยาว

**สรุป:** ทางที่เสถียรคือ **อัปเกรดทั้งโปรเจกต์ไปใช้ชุดเดียวกับ WhisperX (torch 2.8, ctranslate2≥4.5)** แล้วใช้ requirements เดียวกันได้ทั้ง faster-whisper และ WhisperX

### ตัวอย่างบล็อกสำหรับ requirements (ชุดรวม)

ใช้ร่วมกับ requirements.txt อื่นที่มีอยู่ — แทนที่ส่วน Whisper/torch เดิม:

```text
# Whisper stack (รวม faster-whisper + WhisperX) — ใช้ PyTorch 2.8 + CTranslate2 4.5+
# ติดตั้ง torch/torchaudio ก่อนจาก PyTorch index ที่ตรง CUDA (เช่น cu124/cu128)
# pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
torch>=2.8.0
torchaudio>=2.8.0

ctranslate2>=4.5.0
faster-whisper>=1.1.1
whisperx>=3.7.0

openai-whisper==20231117
```

หมายเหตุ: ถ้าใช้ GPU ควรติดตั้ง torch จาก index ที่มี CUDA (เช่น `cu124` หรือ `cu128`) แทนการ pip ติดตั้งจาก PyPI ธรรมดา เพื่อให้ได้ binary ที่ตรงกับ driver ในเครื่อง

---

## GPU ตระกูล Ada (เช่น RTX 4000 Ada / L40) จะมีปัญหาหรือไม่

**สรุป: โดยทั่วไปไม่มีปัญหา** — GPU Ada Lovelace (RTX 4000 Ada, L40, L4 ฯลฯ) รองรับ CUDA 11.8 ขึ้นไป รวมถึง **CUDA 12.4 / 12.8** ที่ใช้กับ PyTorch 2.8 และ CTranslate2 4.5+

### สิ่งที่ต้องมี

| รายการ | หมายเหตุ |
|--------|----------|
| **Driver** | CUDA 12.4 ต้องการ **NVIDIA driver ≥ 525** (CUDA 12.x) — ตรวจด้วย `nvidia-smi` |
| **PyTorch 2.8+cu124/cu128** | รองรับ Ada (compute capability 8.9) |
| **CTranslate2 / cuDNN 9** | ใช้ CUDA 12.x ได้ ไม่มีข้อยกเว้นเฉพาะ Ada |

### ข้อควรระวัง (จากรายงานในชุมชน)

- มีรายงาน **faster-whisper / CTranslate2** บางเคสว่า GPU utilization บน **RTX 4000 Ada** ไม่สูง (เช่น [faster-whisper #844](https://github.com/SYSTRAN/faster-whisper/issues/844) บน Windows + CUDA 12.3) — มักเป็นเรื่องการตั้งค่า/โหลดมากกว่าความไม่รองรับฮาร์ดแวร์
- แนะนำ: หลังอัปเกรดให้ทดสอบบนเครื่องจริง (รัน transcription + ดู `nvidia-smi` / GPU utilization) ถ้า utilization ต่ำอาจลองปรับ batch size หรือ worker count

### สรุปสำหรับ GPU 4000 Ada

- **ใช้ชุด requirements เดียวกัน (PyTorch 2.8, CTranslate2 4.5+, faster-whisper, WhisperX) บน GPU 4000 Ada ได้**
- ตรวจสอบ driver ≥ 525 และติดตั้ง torch จาก index ที่ตรง CUDA (เช่น cu124/cu128) ให้ตรงกับ driver ในเครื่อง

---

## RunPod Pod Template ที่แนะนำ (PyTorch 2.8 + CUDA 12.8)

สำหรับชุด requirements เดียวกัน (faster-whisper + WhisperX) แนะนำใช้ **RunPod PyTorch 2.8.0**:

| รายการ | ค่า |
|--------|-----|
| **Template** | Runpod Pytorch 2.8.0 |
| **Docker Image** | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |

**หมายเหตุ:** ถ้าในรายการ Pod มีเขียน `cu1281` อาจเป็น typo ของ **cu128** (CUDA 12.8) — ตรวจจากรายละเอียด template ว่าเป็น CUDA 12.8 หรือ 12.4

**เหตุผลที่เหมาะกับโปรเจกต์นี้:**
- มี **PyTorch 2.8.0** ตรงกับที่ WhisperX และชุดรวมต้องการ
- **CUDA 12.8** (cu128) รองรับ CTranslate2 4.5+ และ GPU Ada
- Ubuntu 24.04 — Python 3.10+ พอสำหรับ WhisperX (requires-python >=3.10, <3.14)

**หลังสร้าง Pod แล้ว:** ติดตั้งจาก requirements.txt ที่อัปเดตแล้ว (ctranslate2>=4.5.0, faster-whisper, whisperx; ไม่ต้องติดตั้ง torch/torchaudio ซ้ำถ้า image มีอยู่แล้ว) และปรับ LD_LIBRARY_PATH สำหรับ cuDNN 9 ตามที่ CTranslate2 ต้องการ (มักมากับ PyTorch 2.8 image อยู่แล้ว)

---

## อ้างอิง

- โปรเจกต์: `requirements.txt`, `app/services/whisper_providers/`, `app/api/realtime_transcription.py`, `app/services/whisper_service.py`
- WhisperX: [pyproject.toml](https://github.com/m-bain/whisperX/blob/main/pyproject.toml) (dependencies)
- ปัญหา PyTorch/lightning ของ WhisperX: [GitHub Issues](https://github.com/m-bain/whisperX/issues) (torch>=2.1 จาก pyannote/lightning chain)
