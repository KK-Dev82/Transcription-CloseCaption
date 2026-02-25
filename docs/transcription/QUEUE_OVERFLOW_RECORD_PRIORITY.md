# Queue Overflow: Record Priority เมื่อระบบเต็ม

## สถานการณ์

1. Upload เต็ม 25 + Record 1 = 26 tasks
2. 10 นาทีผ่านไป งานยังไม่เสร็จ (ไฟล์ยาว)
3. มี Upload และ Record ใหม่เข้ามา
4. **Record ต้องมี priority สูงกว่า** — ควรรับ Record ก่อน Upload

---

## แนวทางจัดการ

### 1. เพิ่ม Record Slots (แนะนำ)

**แนวคิด:** เปลี่ยนจาก 1 slot เป็น 5–10 slots — ให้ Record หลายตัวรอในคิวได้

| ค่า | ความหมาย |
|-----|----------|
| `MAX_CONCURRENT_RECORD_SLOTS=5` | Record รับได้สูงสุด 5 ตัว (รวมกับ Upload 25 = 30 total) |
| `MAX_PREPROCESS_QUEUE_VIDEO_RECORD_SLOTS=5` | Preprocess queue รับ Record ได้ 5 ตัว |

**พฤติกรรม:**
- 25 Upload + 1 Record → ยังรับ Record ได้อีก 4 ตัว
- 25 Upload + 5 Record → เต็ม, Record ใหม่ได้ 429
- Upload ใหม่ → 429 (เต็ม 25)

**ข้อดี:** ง่าย, ปรับ env ได้ ไม่ต้องแก้ logic  
**ข้อเสีย:** Record ต้องมีขีดจำกัด (เช่น 5) — ถ้าเกินยังได้ 429

---

### 2. Record Waiting Queue (ซับซ้อน)

**แนวคิด:** Record ไม่เคยได้ 429 — รับเสมอแล้วใส่ใน queue รอ

- Upload: 429 เมื่อเต็ม 25
- Record: รับเสมอ (ไม่มี limit) แต่รอใน queue

**ข้อเสีย:** ต้องมี queue แยกและ logic สำหรับจัดการเมื่อ slot ว่าง — ซับซ้อนมาก

---

### 3. ค่าที่ใช้แล้ว (อัปเดต env)

| ตัวแปร | ค่า | หมายเหตุ |
|--------|-----|----------|
| `MAX_CONCURRENT_RECORD_SLOTS` | 5 | Record รับได้ 5 ตัว |
| `MAX_PREPROCESS_QUEUE_VIDEO_RECORD_SLOTS` | 5 | Preprocess queue |

**รวม:** 25 Upload + 5 Record = 30 total (1GPU/2GPU) หรือ 50 + 5 = 55 (production)

**พฤติกรรมเมื่อเต็ม:**
- 25 Upload + 5 Record → เต็ม
- Upload ใหม่ → 429
- Record ใหม่ → 429
- Record ในคิวจะถูกประมวลผลก่อน (Worker ฟัง `preprocess_video_record` ก่อน `preprocess`)
