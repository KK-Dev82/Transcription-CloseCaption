# Queue Priority: วิเคราะห์เวลาและลำดับการแปลงเสร็จ

## ผลการทดสอบ (10 Upload + 1 Record, Record ส่งนาทีที่ 4)

### ผลลัพธ์ที่ได้
| Task | elapsed (นาที) | สรุป |
|------|----------------|------|
| Upload 1 | 7.5 | เสร็จก่อน Record |
| Upload 2-10 | 10.7–11.8 | เสร็จก่อน Record |
| **Record** | **8.2** | **เสร็จเป็นลำดับสุดท้าย** |

### Timeline (จาก elapsed = updated_at - created_at)
- **created_at** = เวลาที่ API รับ request (เวลา submit)
- **updated_at** = เวลาที่ task เสร็จ
- **elapsed** = updated_at - created_at

| Task | ส่ง (นาที) | elapsed | เสร็จที่ (นาที) |
|------|------------|---------|-----------------|
| Upload 1-10 | 0 | 7.5–11.8 | 7.5–11.8 |
| Record | 4 | 8.2 | **12.2** |

Record เสร็จที่ 4 + 8.2 = **12.2 นาที** → เป็นลำดับสุดท้าย

---

## สาเหตุที่ Record เสร็จสุดท้าย

### 1. ลำดับคิวที่ Worker ฟัง (ถูกต้อง)
```
transcription_priority → transcription_gpu_record_$i → transcription_gpu_upload_$i
```
Record queue มาก่อน Upload → ถ้ามี chunk ใน record queue worker จะหยิบก่อน

### 2. ปัญหา: Record chunks เข้า queue ช้ากว่า Upload
- **Upload 1-10**: ส่ง T=0 → preprocess เริ่มทันที → chunks เข้า upload queue ตั้งแต่ ~T=1–3 นาที
- **Record**: ส่ง T=4 นาที → preprocess ต้องรอ (1 worker รับ 10 Upload + 1 Record) → chunks เข้า record queue ช้ากว่า

### 3. Preprocess bottleneck
- Preprocess worker ฟัง: `transcription_preprocess_video_record` ก่อน `transcription_preprocess`
- Record ไป preprocess_video_record → ควรได้ preprocess ก่อน Upload ที่รอใน preprocess ปกติ
- แต่ตอน T=4 นาที มี Upload หลายตัวที่ยังรอ preprocess อยู่ และ Record เพิ่งส่ง
- Record preprocess (~1–2 นาที) → Record chunks เริ่มเข้า record queue ประมาณ T=5–6 นาที

### 4. GPU slots เต็มด้วย Upload chunks
- ตอน T=5–6 นาที Upload 1-10 มี chunks อยู่ใน upload queue แล้ว
- MAX_CONCURRENT_REQUESTS=11 → 10 slots สำหรับ Upload, 1 slot สำหรับ Record
- เมื่อ worker ว่าง จะหยิบ record ก่อน upload
- แต่ Record chunks ยังไม่เข้า queue จนกว่า preprocess จะเสร็จ
- ระหว่างนั้น Upload chunks ถูกประมวลผลไปเรื่อยๆ

### 5. Windowed enqueue
- แต่ละ task enqueue แค่ 4 chunks แรก (CHUNK_ENQUEUE_WINDOW_SIZE=4)
- Chunk ถัดไปจะ enqueue เมื่อ chunk ก่อนหน้าเสร็จ
- Record มี 5 chunks (10 นาที / 120s) → enqueue 4 ก่อน
- Upload 30 นาที มี ~12 chunks → enqueue 4 ก่อน
- Record chunks ที่ enqueue ทีหลังจะต้องรอ slot ว่าง

### 6. สรุป
Record เสร็จสุดท้ายเพราะ:
1. **ส่งช้ากว่า 4 นาที** → preprocess เริ่มช้า
2. **Preprocess ใช้เวลา** → chunks เข้า GPU queue ช้ากว่า Upload ที่เริ่มก่อน
3. แม้ record queue มี priority สูงกว่า แต่ตอน Record chunks เข้า queue Upload หลายตัวกำลังประมวลผลอยู่
4. Record ใช้เวลา 8.2 นาที (รวม preprocess + รอ + GPU) → เสร็จที่ 12.2 นาที

---

## แนวทางปรับปรุง

1. **Reserve slot สำหรับ Record** ✅  
   - Rate Limiter: `MAX_CONCURRENT_REQUESTS=25` + `MAX_CONCURRENT_RECORD_SLOTS=1` → 26 total
   - Preprocess: `MAX_PREPROCESS_QUEUE_SIZE=25` + `MAX_PREPROCESS_QUEUE_VIDEO_RECORD_SLOTS=1` → 26 total
   - Record รับได้แม้ Upload เต็ม 25; เกิน 26 = HTTP 429

2. **เพิ่ม Preprocess workers**  
   ลดเวลารอ preprocess ของ Record

3. **Preempt / Pause Upload chunks**  
   เมื่อมี Record chunk เข้ามา ให้หยุด Upload ชั่วคราว (ซับซ้อน)

4. **ทดสอบ Record ส่งพร้อม Upload**  
   ดูว่าเมื่อส่งพร้อมกัน Record จะแซงได้หรือไม่
