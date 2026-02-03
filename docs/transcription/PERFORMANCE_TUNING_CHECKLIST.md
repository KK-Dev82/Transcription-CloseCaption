# ตรวจสอบการแปลง — ดันประสิทธิภาพได้อีกไหม

**อัปเดต:** 2026-01-29

---

## 0. Pipeline ใช้ CPU ตรงไหน / GPU ตรงไหน (ทำไมเหมือน CPU/RAM ทำงานแทน GPU)

| ขั้นตอน | คิว / Worker | ใช้ GPU? | หมายเหตุ |
|--------|----------------|----------|----------|
| **Preprocess** (extract เสียง + แบ่ง chunk) | `transcription_preprocess` | ❌ CPU | ffmpeg + file I/O — ใช้ CPU/RAM เยอะ |
| **Chunk transcription** (transcribe แต่ละ chunk) | `transcription_gpu0`, `transcription_gpu1`, ... | ✅ GPU | ควรใช้ GPU จริง — ถ้า CTranslate2 โหลดไม่เจอ cuDNN จะ fallback เป็น CPU (ช้า + RAM สูง) |
| **Aggregator** (รอ chunks แล้ว merge + Thai processor) | `transcription_cpu` | ❌ CPU | ออกแบบให้รันบน CPU workers — ไม่ใช้ Whisper |

**วิธีตรวจว่า Chunk transcription ใช้ GPU จริงหรือไม่**

1. ดู log ของ **GPU worker** (เช่น `tail -f /tmp/rq-worker-gpu0-w0.log`) ตอนโหลดโมเดลครั้งแรก:
   - ต้องเห็นบรรทัด `ACTUAL model.device=cuda` (ไม่ใช่ `cpu`)
   - ถ้าเห็น `WHISPER_DEVICE=cuda but model is on CPU!` แปลว่า CTranslate2 ใช้ CPU → ตรวจสอบ `LD_LIBRARY_PATH` (cuDNN/CUDA), `CUDA_VISIBLE_DEVICES` และสคริปต์ `start-rq-workers.sh` ว่าส่ง env ไปให้ GPU worker ครบ
2. ตั้ง `WHISPER_FAIL_IF_CPU=1` ใน env ของ GPU workers ถ้าต้องการให้ **หยุดทันที** เมื่อโมเดลโหลดบน CPU (ไม่ให้รันช้าแบบ CPU โดยไม่รู้ตัว)

---

## 1. กรณี Video 30 นาที — CPU > GPU

**สาเหตุ:** ขั้น **extract เสียง** (ffmpeg) ใช้ **CPU** ทั้งหมด; ขั้น **transcribe chunk** ใช้ GPU  
- Video 30 นาที + chunk_duration 150s → มีแค่ ~12 chunks → GPU ทำเสร็จเร็ว แล้วรอ/merge ต่อ  
- จึงเห็น CPU หนักช่วง extract และช่วง merge; GPU หนักแค่ช่วงสั้น

**สิ่งที่ทำแล้วในโค้ด:**
- **จำกัด thread ffmpeg ตอน extract:** ใช้ env `FFMPEG_EXTRACT_THREADS` (default **4**) เพื่อไม่ให้ ffmpeg กิน CPU เต็ม — ปรับได้ใน `.env.runpod` (เช่น `FFMPEG_EXTRACT_THREADS=2` ถ้าต้องการลด CPU ลงอีก)

**ทางเลือกเพิ่ม (ให้ GPU ทำงานนานขึ้น):**
- **ลด chunk_duration** สำหรับวิดีโอ 30 นาที: ส่ง `chunk_duration=90` จาก client → ได้ ~20 chunks แทน 12 → GPU มีงานทำนานขึ้น (ยังคงใช้ CPU เท่าเดิมตอน extract)
- **ลดจำนวน preprocess workers:** ถ้ามีหลายงาน 30 นาทีพร้อมกัน ให้ลด `NUM_PREPROCESS_WORKERS` จาก 8 เป็น 4–6 เพื่อลด peak CPU (แลกกับ throughput ลดลงบ้าง)

---

## 2. สถานะปัจจุบัน vs คำแนะนำ (PERFORMANCE_RECORDS / bottleneck)

| ตัวแปร | ค่าปัจจุบัน | คำแนะนำเดิม | สถานะ |
|--------|-------------|-------------|--------|
| **GPU_WORKERS_PER_GPU** | 10 | 10 | ✅ ครบแล้ว |
| **CHUNK_INFLIGHT_LIMIT_PER_JOB** | 6 | 6 | ✅ ครบแล้ว |
| **CHUNK_ENQUEUE_WINDOW_SIZE** | 6 | 8 | ⬆️ ปรับเป็น 8 ได้ (ให้ GPU ได้ chunk มากขึ้นตั้งแต่แรก) |
| **NUM_PREPROCESS_WORKERS** | 8 | 8 | ✅ ครบแล้ว |
| **NUM_CPU_WORKERS** | 8 | 8 | ✅ ครบแล้ว |
| **WHISPER_BEAM_SIZE** | 1 | 1 | ✅ เร็วสุดแล้ว |
| **WHISPER_MODEL** | Systran/faster-whisper-small | - | ✅ เร็วกว่า Vinxscribe medium แล้ว |

**Bottleneck หลักจาก phase_timings:** **Wait chunks** (~75–88% ของ total) → การดันต้องให้ GPU ได้งานต่อเนื่อง (window/inflight พอ)

---

## 3. จุดที่ยังดันได้ (ไม่เสี่ยง OOM/คุณภาพ)

| การปรับ | ผลที่คาด | ความเสี่ยง |
|---------|-----------|------------|
| **CHUNK_ENQUEUE_WINDOW_SIZE=8** | ส่ง chunk เข้าคิว GPU มากขึ้นตั้งแต่แรก → GPU ไม่รองาน | ต่ำ |
| **WHISPER_CONDITION_ON_PREVIOUS_TEXT=false** | ไม่ใช้ context จาก chunk ก่อน (chunked file ไม่จำเป็น) → ลด latency/compute เล็กน้อย | ต่ำ (คุณภาพ chunk ต่อ chunk แทบไม่เปลี่ยน) |
| **WHISPER_BATCH_SIZE** | ปัจจุบัน 16 — ถ้า VRAM เหลือ (Systran small เล็ก) อาจลอง **24** ได้; เกินแล้วค่อยลดกลับ | ปานกลาง (เสี่ยง OOM ถ้า workers เยอะ) |

---

## 4. สิ่งที่ทำไปแล้วในรอบนี้

- ตั้ง **CHUNK_ENQUEUE_WINDOW_SIZE=8** ใน `.env.runpod` (จาก 6)
- ตั้ง **WHISPER_CONDITION_ON_PREVIOUS_TEXT=false** ใน `.env.runpod` (comment บอกว่า “chunked ไม่จำเป็น”)

**หลังแก้:** Restart RQ workers (และ API ถ้าโหลด env ตอนเริ่ม) เพื่อให้ค่ามีผล

---

## 5. สรุป: ยังดันได้อีกไหม?

- **ได้อีกนิด:** ปรับ window=8 และ condition_on_previous=false ตามด้านบน (ทำแล้วใน repo)
- **ส่วนใหญ่ดันแล้ว:** workers 10/GPU, inflight 6, preprocess 8, model เป็น Systran small, beam=1
- **ต่อไป:** หลัง deploy ให้ดู **phase_timings** อีกครั้ง (wait_chunks ลดหรือไม่) และ **nvidia-smi** ว่า GPU-Util สูงขึ้นหรือไม่; ถ้ายังรอ chunk อยู่ อาจลอง **CHUNK_INFLIGHT_LIMIT_PER_JOB=8** (ต้องทดสอบ VRAM/คิว)
