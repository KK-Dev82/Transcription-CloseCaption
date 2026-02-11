# RunPod Container Dependency Analysis

## สรุปการตรวจสอบ

**วันที่วิเคราะห์:** 2025-02-11  
**Container:** `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`  
**วัตถุประสงค์:** รองรับทั้ง **faster-whisper** (Transcription จากไฟล์) และ **TyPhoon ASR + NeMo** (ASR FE Live Caption แบบ Streaming สำหรับภาษาไทย)

---

## 1. RunPod Container Specs

| รายการ | เวอร์ชัน |
|--------|----------|
| CUDA | 12.8.1 |
| PyTorch | 2.8.0 |
| Ubuntu | 24.04 |
| Python | (ตรวจสอบจาก container - มักเป็น 3.10 หรือ 3.11) |

---

## 2. faster-whisper (Transcription จากไฟล์)

### สถานะปัจจุบัน (requirements.txt)
- `faster-whisper==1.2.1`
- `ctranslate2==4.4.0`
- โค้ดเดิมออกแบบสำหรับ PyTorch 2.2.0+cu121, cuDNN 8.x

### ปัญหาที่พบกับ RunPod ใหม่

1. **CTranslate2 + cuDNN**
   - CTranslate2 4.4.0 ออกแบบสำหรับ cuDNN 8.x (PyTorch 2.2)
   - PyTorch 2.8.0 ใช้ **cuDNN 9** ซึ่งอาจทำให้ CTranslate2 4.4.0 มีปัญหา
   - CTranslate2 **>= 4.5.0** รองรับ CUDA 12.3+ และ cuDNN 9

2. **faster-whisper compatibility**
   - faster-whisper 1.2.1 ต้องการ `ctranslate2>=4.0,<6` → **4.5.0 ใช้ได้**

### แนะนำการอัปเกรด

```
faster-whisper>=1.2.1    # ใช้เวอร์ชันล่าสุดที่รองรับ ctranslate2 4.5+
ctranslate2>=4.5.0,<6   # รองรับ PyTorch 2.8 + CUDA 12.8 + cuDNN 9
```

### LD_LIBRARY_PATH (RunPod ใหม่)

- RunPod ใช้ CUDA 12.8.1 → path อาจเป็น `/usr/local/cuda-12.8/lib64` หรือตามที่ container กำหนด
- cuDNN path: ตรวจสอบจาก PyTorch package เช่น `/usr/local/lib/python3.x/dist-packages/nvidia/cudnn/lib`
- ควรอัปเดต `app/main.py` และ `scripts/pod/start-rq-workers.sh` ให้ใช้ path ที่ถูกต้องสำหรับ container ใหม่

---

## 3. TyPhoon ASR + NeMo (ASR FE Live Caption Streaming)

### TyPhoon ASR Real-Time

- **โมเดล:** typhoon-ai/typhoon-asr-realtime (HuggingFace)
- **สถาปัตยกรรม:** FastConformer-Transducer (NVIDIA NeMo)
- **ภาษาครอบคลุม:** ไทย โดยเฉพาะ
- **รูปแบบการใช้งาน:** Streaming real-time, รองรับ CPU และ GPU

### วิธีติดตั้ง TyPhoon ASR

**ทางเลือกที่ 1: ใช้ typhoon-asr package (แนะนำ)**

```bash
pip install typhoon-asr
```

Package นี้จะจัดการ dependencies ให้ รวมถึง NeMo

**ทางเลือกที่ 2: ติดตั้งจาก repository**

```bash
pip install nemo_toolkit[asr]  # หรือ nemo-toolkit[asr]
pip install typhoon-asr
```

### NeMo Framework Version Compatibility

| NeMo Version | PyTorch | CUDA | หมายเหตุ |
|--------------|---------|------|----------|
| 25.07 (NeMo 2.4.0) | 2.8.0a0 | 12.9 | ใกล้เคียง RunPod มากที่สุด |
| 25.04 (NeMo 2.3.0) | 2.7.0a0 | - | ต่ำกว่า |
| 24.09 (NeMo 2.0.0) | 2.4.0a0 | - | ต่ำกว่า |

**RunPod มี PyTorch 2.8.0 (stable)** — NeMo 2.4.0 กำหนด 2.8.0a0 (alpha) แต่โดยทั่วไปมักทำงานร่วมกับ 2.8.0 stable ได้

### typhoon-asr requirements (จาก GitHub)

จาก `typhoon-asr` requirements.txt:
- `nemo-toolkit==2.4.0`
- `torch==2.8.0`, `torchaudio==2.8.0`
- `librosa==0.11.0`
- `soundfile==0.13.1`

---

## 4. ความขัดแย้ง (Conflicts) ที่อาจเกิดขึ้น

### 4.1 Package Version Overlap

| Package | โปรเจคปัจจุบัน | TyPhoon/NeMo | แนวทาง |
|---------|-----------------|--------------|--------|
| torch | ใช้จาก base (2.2) | 2.8.0 | **RunPod ใหม่มี 2.8.0 อยู่แล้ว** — ไม่ต้องติดตั้งซ้ำ |
| librosa | 0.10.1 | 0.11.0 | อัปเกรดเป็น 0.11.0 |
| soundfile | 0.12.1 | 0.13.1 | อัปเกรดเป็น 0.13.1 |
| aiohttp | 3.9.1 | 3.12.15 | อัปเกรดเป็น >=3.9.1,<4 (หรือ 3.12 ถ้าไม่มี conflict) |
| requests | 2.31.0 | 2.32.5 | ใช้ >=2.31.0 |
| pydantic | 2.5.0 | (NeMo ใช้內部) | เก็บ 2.5.0 — NeMo 2.4 รองรับ pydantic v2 |

### 4.2 PyTorch / CUDA

- **ไม่ควร `pip install torch`** — ใช้จาก RunPod base image
- NeMo และ typhoon-asr จะใช้ torch ที่มีอยู่แล้ว

### 4.3 CTranslate2 vs NeMo

- **CTranslate2** ใช้โดย faster-whisper เท่านั้น (ไม่มี NeMo)
- **NeMo** ใช้โดย typhoon-asr เท่านั้น
- แยกกันใช้ ไม่มี conflict โดยตรง

---

## 5. แนวทาง requirements.txt ที่รวมกันได้

### หลักการ

1. ใช้ torch/torchaudio จาก RunPod base — **ไม่ต้องระบุใน requirements**
2. อัปเกรด faster-whisper + ctranslate2 สำหรับ PyTorch 2.8 / CUDA 12.8
3. เพิ่ม typhoon-asr (หรือ nemo_toolkit[asr] + typhoon-asr)
4. ปรับ package ร่วมกัน (librosa, soundfile, aiohttp) ให้รองรับทั้งสองฝั่ง

### ตัวอย่างการจัดกลุ่ม

```txt
# ===== Core (ใช้จาก RunPod base) =====
# torch, torchaudio — ไม่ติดตั้ง

# ===== faster-whisper (Transcription จากไฟล์) =====
faster-whisper>=1.2.1
ctranslate2>=4.5.0,<6

# ===== TyPhoon ASR + NeMo (Live Caption Streaming) =====
typhoon-asr>=0.1.0
# typhoon-asr จะ pull nemo_toolkit[asr] โดยอัตโนมัติ

# ===== Audio (ร่วมกัน) =====
librosa>=0.11.0
soundfile>=0.13.1
pydub>=0.25.1
```

---

## 6. สรุปความเหมาะสมของ RunPod Container

| เกณฑ์ | สถานะ | หมายเหตุ |
|-------|--------|----------|
| CUDA 12.8 | ✅ | รองรับทั้ง CTranslate2 4.5+ และ NeMo |
| PyTorch 2.8.0 | ✅ | ตรงกับ NeMo 2.4.0 และ typhoon-asr |
| faster-whisper | ⚠️ | ต้องอัปเกรด ctranslate2 เป็น 4.5+ |
| TyPhoon ASR + NeMo | ✅ | รองรับ streaming ASR ภาษาไทย |
| Conflict ระหว่างทั้งสอง | ✅ | ใช้คนละ stack (CTranslate2 vs NeMo) แยกกันได้ |

---

## 7. แนะนำขั้นตอนถัดไป

1. **สร้าง requirements ใหม่** — รวม faster-whisper (อัปเกรด) + typhoon-asr
2. **ทดสอบใน RunPod container** — `pip install -r requirements.txt` แล้วรัน transcription + live caption
3. **อัปเดต LD_LIBRARY_PATH** — สำหรับ CUDA 12.8 และ cuDNN path ของ RunPod ใหม่
4. **เขียน integration layer** — สำหรับ Live Caption ที่ใช้ TyPhoon ASR แทน faster-whisper (ถ้าต้องการ)

---

## 8. อ้างอิง

- [TyPhoon ASR Real-Time (HuggingFace)](https://huggingface.co/typhoon-ai/typhoon-asr-realtime)
- [TyPhoon ASR GitHub](https://github.com/scb-10x/typhoon-asr)
- [NVIDIA NeMo Software Component Versions](https://docs.nvidia.com/nemo-framework/user-guide/latest/softwarecomponentversions.html)
- [CTranslate2 Installation](https://opennmt.net/CTranslate2/installation.html)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [RunPod PyTorch 2.8 + CUDA 12.8](https://www.runpod.io/articles/guides/pytorch-2-8-cuda-12-8)
