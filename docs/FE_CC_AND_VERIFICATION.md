# FE Live Caption: NeMo vs faster-whisper และการตรวจสอบ CTranslate2/GPU

## 1. NeMo ใช้ Endpoint เดียวกับ FE CC faster-whisper ไหม?

**ใช่ — ใช้ endpoint เดียวกัน**

| Endpoint | รายละเอียด |
|----------|-------------|
| `ws://host/api/ws/ingest-audio` | Producer uplink — รับ PCM16 จาก browser |
| `ws://host/api/ws/captions` | Consumer — ส่ง caption events ไปยัง frontend |

ทั้ง **TyPhoon (NeMo)** และ **faster-whisper** ใช้ flow เดียวกัน:

1. Frontend ส่ง audio ผ่าน `/api/ws/ingest-audio`
2. Main API ทำ transcription (เลือก engine ตาม `FE_CC_PROVIDER`)
3. ส่ง caption events ไปยัง `/api/ws/captions`

**ข้อแตกต่าง:** แค่ engine ที่ใช้แปลงเสียงเท่านั้น (typhoon vs faster-whisper)

---

## 2. ต้องตรวจสอบ CTranslate2 และ GPU ไหม?

**ควรตรวจสอบ** เพื่อให้แน่ใจว่า:

- CTranslate2 รองรับ CUDA
- faster-whisper เห็น GPU และโหลดโมเดลได้
- RQ workers ใช้ GPU จริง (ไม่ fallback เป็น CPU)

### วิธีตรวจสอบ

```bash
# หลัง setup-cudnn-env.sh
./scripts/utility/verify-ctranslate2-gpu.sh
```

หรือถ้าโหลด LD_LIBRARY_PATH ก่อน:

```bash
source scripts/utility/.cudnn-ldpath.sh
./scripts/utility/verify-ctranslate2-gpu.sh
```

### ผลลัพธ์ที่ควรได้

- ctranslate2 มี CUDA support
- WhisperModel โหลดได้บน cuda
- ไม่มี error เกี่ยวกับ `hf_transfer` หรือ `libcudnn`

---

## 3. สรุปปัญหาที่แก้ไข (จาก terminal output)

| ปัญหา | สาเหตุ | การแก้ไข |
|-------|--------|----------|
| `hf_transfer` not available | `HF_HUB_ENABLE_HF_TRANSFER=1` แต่ไม่มี package | เพิ่ม `HF_HUB_ENABLE_HF_TRANSFER=0` ใน .env.runpod และ setup-cudnn-env.sh |
| `GPU_WORKERS_FOR_CC_PER_GPU มากเกินไป → ตั้งเป็น 0` | สูตร MAX_CC ให้ 0 เมื่อมี 2 workers | ปรับ MAX_CC ให้มีอย่างน้อย 1 CC worker เมื่อมี 2+ workers |
| No CUDA/cuDNN libraries found | path ใช้ Python 3.10, CUDA 12.1 | ใช้ path ที่รองรับ Python 3.12 และ CUDA 12.8 |
| cuDNN verification failed | ตรวจเฉพาะ libcudnn_ops_infer.so.8 | รองรับทั้ง .so.8 และ .so.9 |
| `bash: ---: command not found` | มี `---` ใน command | ตรวจสอบ command ก่อนรัน — ไม่ควรมี `---` |

---

## 4. หมายเหตุ

- **FE Live Caption (WebSocket ingest)** รันใน Main API — ไม่ใช้ RQ workers
- **RQ workers** ใช้สำหรับ **file transcription** และ **realtime_chunks** (display_mode จาก upload)
- **TyPhoon** ใช้เฉพาะเมื่อ `FE_CC_PROVIDER=typhoon` และเรียกจาก Main API ผ่าน WebSocket ingest
