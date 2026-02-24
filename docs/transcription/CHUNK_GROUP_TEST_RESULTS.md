# Chunk Group — ผลการทดสอบ

**วันที่:** 2026-02-24

---

## 1. การเตรียมไฟล์

### 1.1 แบ่งไฟล์ WAV เป็น chunks 240s

ใช้สคริปต์ `scripts/split_wav_to_chunks.py`:

```bash
python scripts/split_wav_to_chunks.py "uploads/0e692d52-364e-424a-8f1a-4903c30cdaeb_3fe4b1ff-26e2-4883-a278-7ecad8b1fd5b_chapter_video_b41379a4-6100-4b29-8d60-87e97ee3da8c.wav" -d 240
```

**ผลลัพธ์:**
- ไฟล์ต้นฉบับ: 1992s (~33 นาที)
- สร้าง 9 chunks ที่ `uploads/0e692d52-.../chunk_0000.wav` ... `chunk_0008.wav`
- แต่ละ chunk ~240s (chunk สุดท้ายสั้นกว่า)

---

## 2. วิธีทดสอบ

### 2.1 ทดสอบ Chunk Group (Direct API)

```bash
python scripts/test_chunk_group_direct.py
```

### 2.2 เปรียบเทียบ Chunk Group vs Normal

```bash
python scripts/compare_chunk_group_vs_normal.py
```

จะส่ง 2 requests:
1. **Chunk Group**: 9 ไฟล์ pre-chunked
2. **Normal**: ไฟล์ต้นฉบับ 1 ไฟล์

### 2.3 ต้องมี RQ Workers

```bash
# ดู scripts/pod/start-rq-workers.sh
# หรือรัน worker ตาม env ที่ config ไว้
```

---

## 3. ผลการทดสอบเบื้องต้น

### API Response Time

| Flow | เวลา enqueue | หมายเหตุ |
|------|----------|----------|
| Chunk Group | ~8.87s | Validation 9 ไฟล์ (ffprobe) |
| Normal | ~2.17s | Validation 1 ไฟล์ |

**หมายเหตุ:** Chunk Group ใช้เวลานานกว่าในขั้นตอน API เพราะต้อง validate duration ของทุกไฟล์ (ffprobe 9 ครั้ง) แต่เมื่อ job เริ่มทำงาน:

- **Chunk Group**: ข้าม extract ~10-15s + create_chunks ~5-10s → ประหยัด CPU ~15-25s
- **Normal**: ต้อง extract + create_chunks ก่อน

### ข้อดีของ Chunk Group

1. **CPU**: ข้าม extract_audio และ create_chunks
2. **เวลา**: เริ่ม transcribe เร็วขึ้น (ไม่ต้องรอ preprocess)
3. **ไฟล์ WAV 16k mono**: ถ้า chunks เป็น WAV 16k อยู่แล้ว จะข้าม conversion ด้วย

---

## 4. ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | หน้าที่ |
|------|--------|
| `scripts/split_wav_to_chunks.py` | แบ่ง wav เป็น chunks |
| `scripts/test_chunk_group_direct.py` | ทดสอบ chunk group โดยตรง |
| `scripts/compare_chunk_group_vs_normal.py` | เปรียบเทียบ 2 วิธี |

---

## 5. การวัด CPU และเวลา

เมื่อมี workers รัน:

```bash
# Terminal 1: ดู CPU
vmstat 2

# Terminal 2: ส่ง compare
python scripts/compare_chunk_group_vs_normal.py

# ดูสถานะ tasks
GET /api/v2/tasks/{task_id}
```

หรือใช้ Dashboard เพื่อดู progress และ phase_timings
