# เปรียบเทียบ 25 Tasks: Chunk Group vs Normal

**วันที่:** 2026-02-24  
**Setup:** 2 GPU ADA, vCPU 10, 6 GPU workers, 2 CPU workers, 4 preprocess workers

---

## 1. Chunk Group (25 tasks)

| รายการ | ค่า |
|--------|-----|
| จำนวน tasks | 25 |
| เสร็จ | 25/25 |
| เวลารวม | **23.1 นาที** |
| Task แรก created | 12:04:13 |
| Task สุดท้าย completed | 12:27:19 |
| เวลาส่ง (enqueue) | ~118 วินาที |

**Flow:** ข้าม extract + create_chunks, ใช้ 9 ไฟล์ pre-chunked โดยตรง

---

## 2. Normal (25 tasks)

ใช้ไฟล์ต้นฉบับเดียวกัน (~33 นาที) 25 ครั้ง

```bash
python scripts/test_25_normal_tasks.py --wait
```

**Flow:** extract + create_chunks + transcribe (แต่ละ task)

---

## 3. GPU/CPU Usage

**หมายเหตุ:** ไม่มี resource log จากระหว่างทดสอบ

วิธีวัดในรอบถัดไป:
```bash
# Terminal 1: บันทึก CPU/GPU
mkdir -p logs
./scripts/watch_resources.sh 5 --log logs/resources.csv

# Terminal 2: รันทดสอบ
python scripts/test_25_chunk_group.py --wait
# หรือ
python scripts/test_25_normal_tasks.py --wait
```

---

## 4. สรุปเปรียบเทียบ

| รายการ | Chunk Group | Normal | ผลต่าง |
|--------|-------------|--------|--------|
| เวลา | **23.1 นาที** | 28.3 นาที | Chunk Group เร็วกว่า **5.2 นาที (22%)** |
| เสร็จ | 25/25 | 25/25 | - |

**สรุป:** Chunk Group เร็วกว่า Normal ประมาณ 22% เพราะข้าม extract + create_chunks
