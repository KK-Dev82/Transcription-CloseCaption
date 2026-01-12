# 🔧 Atomic Enqueue Fix - Windowed/JIT Enqueue Improvements

**วันที่:** 2026-01-11  
**ปัญหา:** GPU utilization แกว่ง, jobs รันแบบ sequential แม้มีหลาย workers

---

## 📋 สรุปปัญหา

จากการวิเคราะห์พบว่า **Windowed/JIT Enqueue** มีปัญหาหลายจุด:

1. **Inflight Counter ไม่ใช่ Source of Truth**
   - ใช้การคำนวณ approximate: `inflight_count = enqueued_count - done_count`
   - มีปัญหาเมื่อเกิด race conditions หรือ timing issues

2. **Race Conditions ในการ Claim Next Chunk Index**
   - การอ่าน → check → update `next_chunk_index` ไม่ได้ atomic
   - อาจเกิด enqueue ซ้ำหรือ skip index ได้

3. **ไม่มี Guard กัน Enqueue Chunk ซ้ำ**
   - ไม่มี mechanism ป้องกัน chunk index เดียวกันถูก enqueue หลายครั้ง

---

## ✅ การแก้ไข

### 1. สร้าง Lua Scripts สำหรับ Atomic Operations

สร้างไฟล์ `app/workers/lua_scripts.py`:

#### A) `CLAIM_NEXT_CHUNK_INDEX_SCRIPT`
- **วัตถุประสงค์:** Atomic claim next chunk index + check inflight limit + guard duplicate
- **Returns:** `[claimed_index, inflight_after]` หรือ `[nil, nil]` ถ้าไม่สามารถ claim ได้
- **Features:**
  - ใช้ `SETNX` สำหรับ atomic guard กัน enqueue chunk ซ้ำ
  - Check inflight limit ก่อน claim
  - Update `next_chunk_index` + increment `inflight_chunks` แบบ atomic

#### B) `DECR_INFLIGHT_SCRIPT`
- **วัตถุประสงค์:** Decrement inflight counter เมื่อ chunk เสร็จ
- **Returns:** `new_inflight` count

---

### 2. แก้ไข `process_transcription_job` (Chunk Completion)

**ก่อนแก้:**
```python
# Approximate calculation
enqueued_count = next_chunk_index
inflight_count = enqueued_count - done_count

if next_chunk_index < total_chunks and inflight_count < inflight_limit:
    # Enqueue chunk
    # Update next_chunk_index (not atomic)
    chunks_metadata["next_chunk_index"] = next_chunk_index + 1
    conn.setex(chunks_metadata_key, ttl_seconds, json.dumps(chunks_metadata))
```

**หลังแก้:**
```python
# Atomic claim using Lua script
claim_script = conn.register_script(CLAIM_NEXT_CHUNK_INDEX_SCRIPT)
result = claim_script(
    keys=[chunks_metadata_key, inflight_key, enqueued_guard_prefix],
    args=[inflight_limit, ttl_seconds]
)

claimed_index = result[0]
inflight_after = result[1]

if claimed_index is not None:
    # Enqueue chunk (index already claimed atomically)
    # ...
```

**การ Decrement Inflight:**
```python
# เมื่อ chunk เสร็จ
decr_script = conn.register_script(DECR_INFLIGHT_SCRIPT)
new_inflight = decr_script(keys=[inflight_key, guard_key], args=[ttl_seconds])
```

---

### 3. แก้ไข `process_preprocess_job` (Initial Enqueue)

**ก่อนแก้:**
```python
conn.setex(f"task:{task_id}:inflight_chunks", ttl_seconds, str(enqueued_count))
```

**หลังแก้:**
```python
# ใช้ SET + EXPIRE แทน SETEX เพื่อให้ INCR/DECR ทำงานได้ถูกต้อง
inflight_key = f"task:{task_id}:inflight_chunks"
conn.set(inflight_key, str(enqueued_count))
conn.expire(inflight_key, ttl_seconds)

# ตั้ง guard keys สำหรับ chunks ที่ enqueue แล้ว
enqueued_guard_prefix = f"task:{task_id}:enqueued"
for i in range(enqueued_count):
    guard_key = f"{enqueued_guard_prefix}:{i}"
    conn.setex(guard_key, ttl_seconds, '1')
```

---

## 🔑 Key Improvements

### 1. Inflight Counter เป็น Source of Truth
- ใช้ `INCR`/`DECR` แทนการคำนวณ approximate
- Counter ถูก update atomically ผ่าน Lua script

### 2. Atomic Claim Next Chunk Index
- ทุกขั้นตอน (check limit → claim index → update metadata → increment inflight) ทำงานใน Lua script เดียว
- ไม่มี race conditions

### 3. Guard กัน Enqueue ซ้ำ
- ใช้ `SETNX` สำหรับ atomic guard
- Key pattern: `task:{task_id}:enqueued:{chunk_index}`

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_INFLIGHT_LIMIT_PER_JOB` | `2` | จำนวน chunks ที่กำลังประมวลผลต่อ job (สำหรับ fairness) |
| `CHUNK_ENQUEUE_WINDOW_SIZE` | `4` | จำนวน chunks ที่ enqueue ครั้งแรก (windowed enqueue) |
| `GPU_WORKERS_PER_GPU` | `1` | **⚠️ ควรเป็น 1-3** เพื่อหลีกเลี่ยง model duplication ใน VRAM |

---

## 🎯 Expected Results

### 1. GPU Utilization เสถียรขึ้น
- ไม่มีช่วงที่ GPU idle นาน (queue ว่าง)
- JIT enqueue ทำให้มี chunks ในคิวตลอดเวลา

### 2. Fairness ดีขึ้น
- แต่ละ job ไม่สามารถ "กิน" GPU queue ทั้งหมด
- `inflight_limit` ทำให้ jobs รันแบบ round-robin

### 3. ไม่มี Race Conditions
- ไม่มี chunk index ซ้ำ
- ไม่มี chunk index ข้าม

---

## 📊 Monitoring Checklist

### A) ตรวจว่า JIT Enqueue เดินต่อเนื่องไหม

```bash
# ตรวจ Redis keys
redis-cli GET "task:{task_id}:chunks_metadata" | jq '.next_chunk_index'
redis-cli GET "task:{task_id}:done_chunks"
redis-cli GET "task:{task_id}:inflight_chunks"
```

**Expected:**
- `next_chunk_index` เพิ่มเรื่อย ๆ
- `done_chunks` เพิ่มเรื่อย ๆ
- `inflight_chunks` อยู่ในช่วง `0` - `inflight_limit`

### B) ตรวจว่าคิว GPU "มีงานตลอด" ไหม

```bash
# RQ queue info
rq info --url $REDIS_URL
```

**Expected:**
- GPU queue length ไม่เป็น 0 เป็นเวลานาน
- มี chunks ในคิวตลอดเวลา

### C) ตรวจว่าไม่มี Enqueue ซ้ำ

```bash
# ตรวจ guard keys
redis-cli KEYS "task:{task_id}:enqueued:*" | wc -l
```

**Expected:**
- จำนวน guard keys = จำนวน chunks ที่ enqueue แล้ว
- ไม่มี guard key ซ้ำ

---

## 🔧 Testing

### Test Script

```bash
# ทดสอบ 10 jobs พร้อมกัน
python3 scripts/test_10_jobs_fairness.py

# ตรวจสอบ GPU utilization
watch -n 1 nvidia-smi

# ตรวจสอบ Redis keys
redis-cli MONITOR | grep "task:"
```

---

## 📝 Notes

### เกี่ยวกับ `GPU_WORKERS_PER_GPU`

⚠️ **สำคัญ:** RQ workers เป็น **process-based** ไม่ใช่ thread-based

ถ้าแต่ละ process เรียก `get_transcription_service()` แล้ว provider โหลด model เข้า GPU:
- **VRAM จะถูกใช้ซ้ำต่อ process** (duplicate weights)
- ถ้า `GPU_WORKERS_PER_GPU=12` → อาจโหลดโมเดล 12 ก้อน → **VRAM เต็ม → OOM**

**คำแนะนำ:**
- **medium/large model:** `GPU_WORKERS_PER_GPU=1-2` (มากสุด 3)
- **base/small model:** `GPU_WORKERS_PER_GPU=2-4`

แทนที่จะเพิ่มจำนวน process ให้เพิ่ม **batching/throughput ใน process เดียว** (เช่น `batch_size`, `num_workers`, `compute_type`)

---

## ✅ Summary

การแก้ไขนี้ทำให้:
1. ✅ Inflight counter เป็น source of truth (ใช้ INCR/DECR)
2. ✅ Atomic claim next chunk index (ไม่มี race conditions)
3. ✅ Guard กัน enqueue chunk ซ้ำ (ใช้ SETNX)

**ผลลัพธ์ที่คาดหวัง:**
- GPU utilization เสถียรขึ้น
- Fairness ดีขึ้น
- ไม่มี chunk index ซ้ำ/ข้าม
