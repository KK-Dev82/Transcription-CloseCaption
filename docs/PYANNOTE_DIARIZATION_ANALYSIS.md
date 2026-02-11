# การวิเคราะห์: pyannote.audio 3 vs 4 และผลกระทบต่อภาษาไทย

**สถานะ:** ยังไม่ติดตั้ง — วิเคราะห์ความขัดแย้ง (conflict) และผลกระทบก่อนตัดสินใจ

---

## 1. ความขัดแย้งของ Dependencies (Conflict Analysis)

### 1.1 สรุปเปรียบเทียบ

| รายการ | โปรเจกต์ปัจจุบัน | pyannote 3.3.2 | pyannote 4.0.3 |
|--------|-------------------|----------------|-----------------|
| **torch** | 2.2.0+cu121 (base image) | ต้องการ `torch>=2.0.0` ✅ | ต้องการ **`torch==2.8.0`** ❌ |
| **torchaudio** | 2.2.0+cu121 | ต้องการ `torchaudio>=2.2.0` ✅ | ต้องการ **`torchaudio==2.8.0`** ❌ |
| **soundfile** | 0.12.1 | `>=0.12.1` ✅ | `>=0.13.1` (ต้องอัปเกรด) |
| **Python** | 3.10 | `>=3.9` ✅ | `>=3.10` ✅ |
| **faster-whisper / ctranslate2** | ใช้ torch/cuDNN จาก base | ใช้ torch เดียวกัน ✅ | ถ้าติดตั้ง 4.x จะดึง torch 2.8 → **ขัดกับ ctranslate2/cuDNN** ❌ |

### 1.2 pyannote 3.3.2 — Dependencies ที่จะถูกดึงมา (ไม่มีใน requirements ปัจจุบัน)

- `asteroid-filterbanks>=0.4`
- `einops>=0.6.0`
- `huggingface-hub>=0.13.0` (โปรเจกต์มี requests อยู่แล้ว)
- `lightning>=2.0.1` → รองรับ torch 2.x (lightning 2.x ต้องการ torch>=2.1; โปรเจกต์มี 2.2 ✅)
- `omegaconf<3.0,>=2.1`
- `pyannote.core`, `pyannote.database`, `pyannote.metrics`, `pyannote.pipeline`
- `pytorch-metric-learning>=2.1.0`
- `rich>=12.0.0`
- `semver>=3.0.0`
- `soundfile>=0.12.1` ✅ ตรงกับ 0.12.1
- **`speechbrain>=1.0.0`** → ต้องการ `torch>=1.9`, `torchaudio` (ไม่มี pin แน่นอน) → ใช้ torch 2.2 ได้ ✅
- `tensorboardX>=2.6`
- `torch>=2.0.0`, `torchaudio>=2.2.0` ✅ ใช้จาก base ได้
- `torch-audiomentations>=0.11.0`
- `torchmetrics>=0.11.0`

**ข้อสรุป pyannote 3.3.2:**  
- **ไม่มี conflict กับ torch/faster-whisper/ctranslate2** ถ้าใช้ torch 2.2 จาก base image ตามเดิม  
- การติดตั้งจะเพิ่ม package ใหม่จำนวนหนึ่ง (lightning, speechbrain, omegaconf, rich ฯลฯ) แต่ไม่บังคับให้เปลี่ยนเวอร์ชัน torch

### 1.3 pyannote 4.0.3 — จุดขัดแย้งหลัก

- กำหนด **`torch==2.8.0`**, **`torchaudio==2.8.0`** แบบตายตัว  
- ใช้ **`torchcodec==0.7.0`** (audio decoding)  
- โปรเจกต์ใช้ **torch 2.2 + cuDNN 8.x** กับ **ctranslate2 4.4.0** และ **faster-whisper 1.2.1**

**ผลกระทบถ้าติดตั้ง pyannote 4.x ใน environment เดียว:**

1. pip จะพยายามติดตั้ง/อัปเกรดเป็น **torch 2.8** → อาจทับหรือขัดกับ CUDA/cuDNN ที่ ctranslate2 ใช้  
2. **faster-whisper / ctranslate2** อาจทำงานผิดปกติหรือต้อง rebuild กับ torch 2.8  
3. **ไม่แนะนำ** ให้ใส่ `pyannote.audio==4.x` ลงใน `requirements.txt` เดียวกับ stack ปัจจุบัน  

**ทางเลือกถ้าต้องการใช้ pyannote 4.x:**  
- แยก environment / Docker image อีกตัวที่ใช้ torch 2.8 แล้วรันเฉพาะส่วน diarization หรือ  
- ใช้บริการ diarization แยก (อีก service/container) แล้วส่งผล (ช่วงเวลา + speaker) มาให้ transcription-service ใช้ร่วมกับ faster-whisper  

---

## 2. ผลกระทบต่อภาษาไทย: pyannote 3 vs 4

### 2.1 Diarization ไม่ขึ้นกับภาษา (Language-agnostic)

- **Speaker diarization** ของ pyannote (ทั้ง 3.1 และ community-1) ทำหน้าที่ตอบคำถาม **“ใครพูดเมื่อไหร่”** โดยใช้คุณลักษณะของเสียง (voice characteristics) และการแบ่งช่วงเสียงพูด (segmentation)  
- **ไม่ได้ใช้ข้อความหรือภาษาของคำพูด** เป็น input ของโมเดล diarization  
- เอกสารและโฆษณาของ pyannote ระบุชัดว่าเป็น **language-agnostic** / ใช้ได้กับทุกภาษา รวมถึงภาษาไทย  

ดังนั้น **สำหรับภาษาไทยโดยตรง:**  
- **การเลือก pyannote 3.3.2 vs 4.0.3 ไม่ได้ทำให้ “รองรับไทย” หรือ “ไม่รองรับไทย” ต่างกัน**  
- ทั้งสองเวอร์ชันใช้ได้กับเสียงภาษาไทยในลักษณะเดียวกัน (แยกผู้พูดตามเสียง ไม่ได้ตามภาษา)

### 2.2 ความแตกต่างที่กระทบ “คุณภาพ” การแยกผู้พูด (ไม่เฉพาะไทย)

| ด้าน | pyannote 3.1 (ใช้กับ 3.x) | pyannote 4 community-1 |
|------|----------------------------|--------------------------|
| **Pipeline** | `pyannote/speaker-diarization-3.1` | `pyannote/speaker-diarization-community-1` |
| **ความแม่นยำ (DER โดยรวม)** | ดี (benchmark หลายชุด) | ดีกว่า 3.1 ชัดเจน ( speaker assignment ดีขึ้น) |
| **โหมด exclusive speaker** | ไม่มี | มี (หนึ่งช่วงเวลามีผู้พูดคนเดียว → ง่ายต่อการจับคู่กับ STT) |
| **ความเร็ว (self-hosted)** | ช้ากว่า community-1 | เร็วกว่า (ประมาณ 2–2.6x ในบาง benchmark) |
| **การ reconcile กับ STT** | ทำได้ | ง่ายกว่าเพราะ exclusive mode + ปรับปรุง timestamp |

**สรุปผลกระทบต่อ “การใช้งานกับภาษาไทย”:**  
- **ฟังก์ชันการแยกผู้พูดสำหรับเสียงไทย:** ใช้ได้ทั้ง 3.x และ 4.x แบบไม่ต่างกันในแง่ “รองรับภาษา”  
- **ผลที่ได้อาจต่างกันที่:** ความแม่นยำการแยกผู้พูด (DER), ความเร็ว, และความสะดวกในการจับคู่กับผลจาก faster-whisper  
- ถ้าใช้ **pyannote 3.3.2 + pipeline 3.1** คุณยังได้ diarization ที่ใช้ได้กับภาษาไทยได้ดี แค่ความละเอียด/ความสะดวกอาจไม่เท่า 4.x + community-1  

---

## 3. แนวทางที่แนะนำ (ก่อนติดตั้ง)

1. **ถ้าต้องการอยู่ environment เดียวกับ faster-whisper (และไม่ยอมเปลี่ยน torch):**  
   - ใช้ **pyannote.audio==3.3.2**  
   - ใช้ pipeline **`pyannote/speaker-diarization-3.1`**  
   - ต้อง Accept conditions และใช้ Hugging Face token ตามที่เอกสาร pyannote กำหนด  

2. **ถ้าต้องการความแม่นยำ/ความเร็วของ community-1 (4.x):**  
   - ใช้ **pyannote 4.x ใน environment แยก** (torch 2.8)  
   - หรือใช้บริการ diarization แยก (API / container อื่น) แล้วส่งผลมา merge กับผลจาก faster-whisper  

3. **ไม่แนะนำ:**  
   - ใส่ `pyannote.audio==4.x` ลงใน `requirements.txt` เดียวกับ stack ปัจจุบัน (torch 2.2 + ctranslate2 + faster-whisper) เพื่อหลีกเลี่ยง conflict และความเสี่ยงต่อการทำงานของ transcription  

---

## 4. สรุปสั้นๆ

| คำถาม | คำตอบ |
|--------|--------|
| **มี conflict ไหมถ้าใช้ pyannote 3.3.2?** | **ไม่มี** กับ torch 2.2 / faster-whisper / ctranslate2 ในโปรเจกต์ปัจจุบัน |
| **มี conflict ไหมถ้าใช้ pyannote 4.x?** | **มี** — ต้องการ torch==2.8.0 จะขัดกับ torch 2.2 และอาจกระทบ ctranslate2/faster-whisper |
| **pyannote 3 vs 4 มีผลกับภาษาไทยโดยตรงไหม?** | **ไม่มี** — diarization เป็น language-agnostic ใช้กับไทยได้ทั้งสองเวอร์ชัน |
| **ความต่าง 3 vs 4 ที่สำคัญคืออะไร?** | 4 (community-1) แม่นและเร็วกว่า 3.1 แต่ต้องใช้ torch 2.8 จึงไม่เหมาะกับ requirements ปัจจุบัน |
| **ควรเริ่มจากอะไร?** | เริ่มจาก **pyannote.audio==3.3.2** ใน requirements เดิม แล้วออกแบบ flow diarization + faster-whisper; ถ้าอยากได้ community-1 ค่อยแยก environment/บริการภายหลัง |

ไฟล์นี้เขียนเพื่อใช้อ้างอิงก่อนตัดสินใจติดตั้งหรือปรับเปลี่ยน requirements
