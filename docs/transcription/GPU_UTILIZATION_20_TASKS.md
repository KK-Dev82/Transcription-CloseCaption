# ตรวจสอบ GPU ทำงานเต็มประสิทธิภาพหรือไม่ (เมื่อมี 20 Tasks พร้อมกัน)

**อัปเดต:** 2026-01-29

---

## 1. การตั้งค่าปัจจุบัน (.env.runpod)

| ตัวแปร | ค่า | ความหมาย |
|--------|-----|----------|
| **NUM_GPUS** | 2 | จำนวน GPU |
| **GPU_WORKERS_PER_GPU** | 10 | จำนวน RQ worker ต่อ 1 GPU (รวม CC + file) |
| **GPU_WORKERS_FOR_CC_PER_GPU** | 2 | ในนั้นกี่ตัวที่ฟัง priority (CC) — ที่เหลือฟังแค่ file |
| **NUM_PREPROCESS_WORKERS** | 8 | จำนวน worker สำหรับ extract + chunk |
| **CHUNK_ENQUEUE_WINDOW_SIZE** | 6 | จำนวน chunk ที่ enqueue ครั้งแรกต่อ task |
| **CHUNK_INFLIGHT_LIMIT_PER_JOB** | 6 | จำนวน chunk สูงสุดที่ “ในคิว/กำลังทำ” ต่อ task (JIT enqueue) |
| **MAX_PREPROCESS_QUEUE_SIZE** | 25 | คิว preprocess เต็มที่ 25 job |
| **MAX_CONCURRENT_REQUESTS** | 25 | API รับพร้อมกันสูงสุด 25 request |

**สรุป:** GPU workers รวม = **2 × 10 = 20 ตัว** (ต่อ GPU: 2 ตัวรับ CC+file, 8 ตัวรับแค่ file)

---

## 2. เมื่อมี 20 Tasks พร้อมกัน — GPU ได้งานเต็มหรือไม่?

### ลำดับการทำงาน

1. **API:** รับ 20 request ได้ (ไม่เกิน MAX_CONCURRENT_REQUESTS=25)
2. **Preprocess:** 20 tasks เข้าคิว `transcription_preprocess` → มี **8 workers** ทำงานพร้อมกัน  
   - ในช่วง steady state มีได้สูงสุด 8 tasks กำลัง preprocess พร้อมกัน  
   - แต่ละ task ที่ preprocess เสร็จจะ enqueue **6 chunks แรก** ไปคิว GPU (round-robin ไป `transcription_gpu0` / `transcription_gpu1`)
3. **GPU:** แต่ละ GPU มี **10 workers** → รวม 20 workers  
   - ช่วงที่ 8 tasks preprocess เสร็จแล้ว จะมีประมาณ 8×6 = **48 chunk jobs** ในคิว GPU (แบ่งระหว่าง gpu0 / gpu1)  
   - 20 workers รับงานได้ทีละ 20 chunks → **ในทางทฤษฎี GPU ควรเต็ม (20/20 workers ทำงาน)**  
   - เมื่อ chunk เสร็จ จะมี JIT enqueue chunk ถัดไปของ task นั้น (ไม่เกิน 6 in-flight ต่อ task)

### สรุปเชิงทฤษฎี

- **จำนวน worker พอ:** 20 tasks × หลาย chunks ต่อ task → จำนวน chunk jobs มากกว่า 20 อย่างชัดเจน ดังนั้น **20 GPU workers ควรมีงานให้ทำเรื่อยๆ**
- **Bottleneck ที่อาจเกิด:**
  1. **Preprocess ช้ากว่า GPU:** ถ้า 8 preprocess workers ทำไม่ทัน → chunk เข้าคิว GPU ช้า → GPU อาจรองานบางช่วง (ไม่เต็มตลอด)
  2. **VRAM ต่อ GPU:** 10 workers ต่อ GPU = 10 process โหลด model (ถ้าไม่ share) → ถ้า VRAM ไม่พออาจมี OOM หรือต้องลด `GPU_WORKERS_PER_GPU`
  3. **สคริปต์ start-rq-workers.sh:** ใช้ `GPU_WORKERS_PER_GPU=${GPU_WORKERS_PER_GPU:-3}` — ถ้า **ไม่ได้โหลด .env.runpod** ก่อนรัน จะได้แค่ 3 ต่อ GPU (รวม 6 workers) → GPU จะไม่เต็ม

ดังนั้น **“เต็มประสิทธิภาพ” หรือไม่ ขึ้นกับว่า (1) มี worker 20 ตัวจริง (2) preprocess ส่ง chunk เข้าคิว GPU ทัน (3) ไม่ติด VRAM**

---

## 3. วิธีตรวจสอบบน Server (RunPod/Pod)

### 3.1 ตรวจว่า GPU ถูกใช้และ utilization

```bash
# ดู utilization และ memory แบบต่อเนื่อง
watch -n 1 nvidia-smi
```

- **GPU-Util:** ถ้าอยู่ที่สูง (เช่น 80–100%) ตลอดช่วงที่มี job = ใช้ GPU เต็ม  
- **Memory-Usage:** ดูว่าใช้ไปเท่าไร ถ้าใกล้เต็มและมี OOM อาจต้องลด `GPU_WORKERS_PER_GPU`

### 3.2 ตรวจจำนวน GPU workers จริง

```bash
# จำนวน process ที่เป็น RQ worker ฟังคิว GPU
pgrep -fc "rq worker.*transcription_gpu"
# คาดหวัง: 20 (ถ้า GPU_WORKERS_PER_GPU=10 และ NUM_GPUS=2)
```

ถ้าได้น้อยกว่า 20 แปลว่ามี worker น้อยกว่าที่ตั้งใน .env → GPU มีโอกาสไม่เต็ม

### 3.3 ตรวจความยาวคิว GPU (ว่ามีงานรอหรือไม่)

ใช้สคริปต์ใน repo:

```bash
./scripts/utility/check-gpu-queues.sh
```

หรือใช้ RQ/Redis ดูความยาวคิว `transcription_gpu0`, `transcription_gpu1`  
- ถ้าคิวยาวตลอด + GPU-Util สูง = GPU ทำงานเต็มและมีงานรอ  
- ถ้าคิวว่างบ่อย + GPU-Util ต่ำ = อาจติดที่ preprocess หรือจำนวน worker น้อย

### 3.4 ตรวจ Preprocess (ว่าเป็น bottleneck หรือไม่)

- ดูความยาวคิว `transcription_preprocess`  
- ดู log ว่า preprocess เสร็จและ enqueue chunk บ่อยแค่ไหน  

ถ้าคิว preprocess ยาวตลอด แต่คิว GPU ว่าง = bottleneck อยู่ที่ preprocess → GPU ไม่ได้งานเต็มที่

---

## 4. สรุปคำตอบ: GPU ทำงานเต็มประสิทธิภาพหรือไม่?

| สถานะ | ความหมาย |
|--------|----------|
| **เต็ม (ในทางทฤษฎี)** | ตั้งค่า 20 GPU workers (10×2), preprocess 8 ตัว, window 6 → มี chunk เข้าคิว GPU พอให้ 20 workers ทำงานต่อเนื่องได้ |
| **ต้องตรวจบน server จริง** | 1) `nvidia-smi` ว่า GPU-Util สูงหรือไม่ 2) `pgrep -fc "rq worker.*transcription_gpu"` ว่าได้ 20 หรือไม่ 3) คิว GPU/Preprocess ว่าใครเป็น bottleneck |

**ข้อแนะนำ:**

- ถ้า **GPU-Util ต่ำ** ทั้งที่คิวมีงาน → ลองเพิ่ม `CHUNK_ENQUEUE_WINDOW_SIZE` / `CHUNK_INFLIGHT_LIMIT_PER_JOB` ให้ GPU ได้ chunk มากขึ้นต่อ task  
- ถ้า **คิว GPU ว่างบ่อย** → สงสัย preprocess ช้า หรือ worker น้อย → ตรวจ `NUM_PREPROCESS_WORKERS` และจำนวน GPU workers จริง  
- ถ้า **VRAM เต็ม / OOM** → ลด `GPU_WORKERS_PER_GPU` (เช่น จาก 10 เหลือ 6–8) แล้วดู utilization ใหม่
