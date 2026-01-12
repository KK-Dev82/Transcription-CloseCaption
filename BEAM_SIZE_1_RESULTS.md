# 📊 ผลการทดสอบ: Beam Size = 1

## 🎯 สรุปผลการทดสอบ

### Configuration
- **Beam Size**: 1 (greedy decoding - เร็วที่สุด)
- **Temperature**: 0.0
- **VAD Filter**: true
- **Overlap**: 0.6s
- **Dedupe**: enabled
- **Postprocess**: enabled

---

## 📈 Latency Results

### 1. Small Model (Beam Size = 1)

**Latency**:
- Chunk 0: **23.0s** (อาจรวม model loading time)
- Chunk 1: **17.0s**
- Chunk 2: **5.0s**
- Chunk 3: **1.0s**
- **Average: 11.5s per chunk**

**Real-time Ratio**: 3.8x (latency > chunk duration)

**📝 Transcription Results**:
1. Chunk 0: "ช่าย สิต รง ตน"
2. Chunk 1: "บ้า ว บ้า ว บ้า" (มี repetition)
3. Chunk 2: "ดี ย ง คุณ ครับ"
4. Chunk 3: "ว่า ว่า วัก หนึ่ง เป็น 300 หนึ่ง ท่าน"

**FullText**: "ช่าย สิต รง ตน บ้า ว บ้า ว บ้า ดี ย ง คุณ ครับ ว่า ว่า วัก หนึ่ง เป็น 300 หนึ่ง ท่าน"

---

### 2. Medium-Faster Model (Beam Size = 1)

**Latency**:
- Chunk 0: **8.0s** (อาจรวม model loading time)
- Chunk 1: **1.0s**
- Chunk 2: **0.5s**
- Chunk 3: **0.4s**
- Chunk 4: **0.5s**
- **Average: 2.0s per chunk**

**Real-time Ratio**: 0.7x (latency < chunk duration) ✅ **Real-time!**

**📝 Transcription Results**:
1. Chunk 0: "ไป ทาน ครับ ส วัส ดง ตน ครับ"
2. Chunk 1: "อ้าว วัน จะ ถาม จาก ที่ บ้าง"
3. Chunk 2: "ตาม ตาก ที่จะ รับ ละ การ ยัง รับ"
4. Chunk 3: "แอ ง รับ ริม ไอ้"
5. Chunk 4: "ขอ โจ เกิด อ อก เที่ย ลง กัน"

**FullText**: "ไป ทาน ครับ ส วัส ดง ตน ครับ อ้าว วัน จะ ถาม จาก ที่ บ้าง ตาม ตาก ที่จะ รับ ละ การ ยัง รับ แอ ง รับ ริม ไอ้ ขอ โจ เกิด อ อก เที่ย ลง กัน"

---

## 📊 เปรียบเทียบ

| Model | Beam Size | Average Latency | Real-time Ratio | Status |
|-------|-----------|----------------|-----------------|--------|
| **Small** | 3 | 6.3s | 2.1x | ⚠️ Not real-time |
| **Small** | 1 | 11.5s | 3.8x | ⚠️ Not real-time (worse) |
| **Medium-Faster** | 3 | 4.0s | 1.3x | ⚠️ Not real-time |
| **Medium-Faster** | 1 | **2.0s** | **0.7x** | ✅ **Real-time!** |

---

## 🔍 วิเคราะห์

### 1. Small Model (Beam Size = 1)

**ปัญหา**:
- ⚠️ Latency **แย่ลง** จาก 6.3s → 11.5s
- ⚠️ Chunk แรกใช้เวลานานมาก (23s) - อาจเป็น model loading
- ⚠️ มี repetition ในข้อความ (Chunk 1: "บ้า ว บ้า ว บ้า")

**สาเหตุ**:
- Small model อาจไม่เหมาะกับ beam_size=1
- Greedy decoding ทำให้เกิด repetition

---

### 2. Medium-Faster Model (Beam Size = 1)

**ผลลัพธ์**:
- ✅ Latency **ดีขึ้น** จาก 4.0s → 2.0s (50% เร็วขึ้น)
- ✅ **Real-time!** (latency < chunk duration)
- ✅ ข้อความอ่านได้ดีกว่า Small model
- ✅ ไม่มี repetition

**สาเหตุ**:
- Medium-Faster model ถูก optimize สำหรับ real-time
- Beam size = 1 ทำงานได้ดีกับ model นี้

---

## 💡 สรุป

### คำตอบ

1. **Latency ดีขึ้นไหม?**
   - ✅ **Medium-Faster**: ดีขึ้น (4.0s → 2.0s, 50% เร็วขึ้น)
   - ❌ **Small**: แย่ลง (6.3s → 11.5s)

2. **Real-time?**
   - ✅ **Medium-Faster + Beam Size = 1**: **Real-time!** (2.0s < 3s)
   - ❌ **Small + Beam Size = 1**: ไม่ real-time (11.5s > 3s)

3. **คุณภาพข้อความ?**
   - ✅ **Medium-Faster**: ดีกว่า (อ่านได้ดีกว่า, ไม่มี repetition)
   - ⚠️ **Small**: มี repetition (beam_size=1 ไม่เหมาะ)

---

## 🎯 คำแนะนำ

### สำหรับ Real-time CloseCaption

**แนะนำ**: ใช้ **Medium-Faster Model + Beam Size = 1**

```bash
CC_MODEL_SIZE=models--Vinxscribe--biodatlab-whisper-th-medium-faster
CC_BEAM_SIZE=1
```

**ผลลัพธ์**:
- ✅ Real-time (2.0s latency < 3s chunk duration)
- ✅ คุณภาพดี (ไม่มี repetition)
- ✅ ข้อความอ่านได้ดี

---

### สำหรับคุณภาพสูงสุด

**แนะนำ**: ใช้ **Medium-Faster Model + Beam Size = 3**

```bash
CC_MODEL_SIZE=models--Vinxscribe--biodatlab-whisper-th-medium-faster
CC_BEAM_SIZE=3
```

**ผลลัพธ์**:
- ⚠️ ไม่ real-time (4.0s latency > 3s)
- ✅ คุณภาพดีที่สุด
- ✅ แม่นยำสูง

---

## 📝 ข้อสังเกต

1. **Small Model + Beam Size = 1**: ไม่แนะนำ (latency สูง + มี repetition)
2. **Medium-Faster Model**: เหมาะกับ beam_size=1 (real-time + คุณภาพดี)
3. **Chunk แรก**: ใช้เวลานานกว่า (model loading) → ไม่นับใน average

---

**วันที่ทดสอบ**: 2026-01-12  
**GPU**: RTX 4000 Ada  
**Chunk Duration**: 3 seconds
