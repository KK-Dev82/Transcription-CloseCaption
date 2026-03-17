# ทำไม Task ค้างที่ 90%?

## ความหมายของ 90%

- **90%** = Chunks เสร็จหมดแล้ว กำลังรอ **Aggregator** (รวมผล → Thai processing → save)
- Progress: 0-40% = preprocess, 40-90% = chunks, 90-100% = aggregator

## สาเหตุที่ค้าง 90%

| สาเหตุ | อธิบาย |
|--------|--------|
| **Aggregator job fail** | Worker ถูก kill กลางคัน (restart) → aggregator job fail |
| **CPU queue เต็ม** | NUM_CPU_WORKERS=4 แต่มี 25+ aggregator jobs รอ |
| **Chunks ไม่ครบ** | บาง chunk fail → done_chunks < total_chunks → aggregator รอไม่จบ (timeout 1 ชม.) |

## วิธีแก้

### 1. Re-enqueue Aggregator (chunks เสร็จหมดแล้ว)

```bash
python scripts/fix_stuck_90_percent.py --apply
```

### 2. Re-enqueue Chunks (chunks ยังไม่ครบ)

```bash
python scripts/recover_after_restart.py --apply
```

### 3. ตรวจสอบ CPU workers

```bash
# ดูจำนวน CPU workers
ps aux | grep "rq worker.*transcription_cpu"

# เพิ่ม NUM_CPU_WORKERS ใน .env.runpod (default 4)
```
