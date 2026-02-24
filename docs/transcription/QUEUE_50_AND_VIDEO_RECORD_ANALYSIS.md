# วิเคราะห์: Queue 50 + Video Record ลัดคิว — ผลกระทบต่อความช้า

**วันที่:** 2026-02-23

---

## 1. สรุปปัญหา

การขยาย Queue เป็น 50 (25+25) และการแทรกคิว Video Record อาจทำให้เกิดความช้า:

| ปัญหา | สาเหตุ |
|-------|--------|
| **Aggregator backlog** | 50 tasks → 50 aggregator jobs แต่มีแค่ 2 CPU workers |
| **Task ท้ายรอนาน** | Task 50 ต้องรอ preprocess + GPU + aggregator ตามลำดับ |
| **Video Record แทรกคิว** | งานปกติที่รอใน preprocess ถูกเลื่อนเมื่อ video_record เข้ามา |

---

## 2. Pipeline และ Bottleneck

```
Preprocess (4 workers) → GPU chunks (6 workers) → Aggregator (2 workers)
```

### 2.1 เมื่อมี 50 tasks

| ขั้นตอน | จำนวน jobs | Workers | Backlog |
|---------|------------|---------|---------|
| Preprocess | 50 | 4 | 50/4 ≈ 12 waves |
| GPU chunks | 50×8 ≈ 400 | 6 | 400/6 ≈ 67 waves |
| **Aggregator** | **50** | **2** | **50/2 = 25 waves** |

**Aggregator เป็น bottleneck หลัก** — 2 workers กับ 50 jobs = แต่ละ job รอเฉลี่ย 25/2 ≈ 12 jobs ก่อนถึงคิว

### 2.2 เมื่อมี 25 tasks (เดิม)

| ขั้นตอน | จำนวน jobs | Workers | Backlog |
|---------|------------|---------|---------|
| Preprocess | 25 | 4 | 25/4 ≈ 6 waves |
| GPU chunks | 25×8 ≈ 200 | 6 | 200/6 ≈ 33 waves |
| Aggregator | 25 | 2 | 25/2 ≈ 12 waves |

Backlog ลดลงครึ่งหนึ่ง

---

## 3. Video Record ลัดคิว — ผลกระทบ

- Workers ฟัง `preprocess_video_record` ก่อน `preprocess`
- เมื่อ video_record เข้ามา → worker ที่ว่างจะรับ video_record ก่อนงานปกติ
- **ผล:** งานปกติที่ "ควรได้" worker นั้น ต้องรอรอบถัดไป
- ถ้ามี video_record บ่อย → งานปกติถูกเลื่อนต่อเนื่อง

---

## 4. แนวทางแก้ไข

### ตัวเลือก A: Revert กลับ 25 (แนะนำถ้าต้องการความเร็ว)

```env
MAX_PREPROCESS_QUEUE_SIZE=25
MAX_CONCURRENT_REQUESTS=25
```

- งานที่ 26+ ได้ 429 ทันที
- 25 งานแรกเสร็จเร็วขึ้น (aggregator backlog ลด)

### ตัวเลือก B: เก็บ 50 แต่เพิ่ม Aggregator workers

```env
MAX_PREPROCESS_QUEUE_SIZE=50
NUM_CPU_WORKERS=4   # เพิ่มจาก 2 → 4
```

- ลด aggregator backlog (50/4 แทน 50/2)
- ต้องตรวจสอบ CPU headroom

### ตัวเลือก C: ปิด Video Record ลัดคิว

- ส่ง video_record ไปคิวปกติ (ไม่แยก preprocess_video_record)
- หรือใช้ `source=video_record` เฉพาะเมื่อจำเป็นจริง

### ตัวเลือก D: จำกัด Video Record slot

- เก็บ slot พิเศษ 1 ตัว แต่ลดผลกระทบ: video_record ใช้ slot แยก ไม่นับรวมใน 50
- ปัญหา: ยังคงแทรกคิวงานปกติอยู่

---

## 5. สรุปแนะนำ

| Use case | แนะนำ |
|----------|-------|
| ต้องการความเร็ว + เสถียร | **A:** Revert 25, ปิดหรือจำกัด video_record ลัดคิว |
| ต้องการรองรับ 50 งาน | **B:** เพิ่ม NUM_CPU_WORKERS เป็น 4 |
| Video Record สำคัญมาก | เก็บลัดคิว แต่ยอมรับว่างานปกติอาจช้าลง |
