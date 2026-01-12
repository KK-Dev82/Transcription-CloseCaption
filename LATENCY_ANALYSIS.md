# 📊 Latency Analysis: CloseCaption Profile

## 🎯 สรุปผลการทดสอบ

### 1. Small Model (CloseCaption Profile - Default)

**Configuration**:
- Model: `small`
- Beam Size: 3
- Temperature: 0.0
- VAD Filter: true
- Overlap: 0.6s
- Dedupe: enabled
- Postprocess: enabled

**Latency Results**:
- Chunk 0: **7.0s**
- Chunk 1: **7.0s**
- Chunk 2: **5.0s**
- **Average: ~6.3s per chunk**

**Real-time Ratio**: 2.1x (latency > chunk duration)

---

### 2. Medium-Faster Model (biodatlab-whisper-th-medium-faster)

**Configuration**:
- Model: `models--Vinxscribe--biodatlab-whisper-th-medium-faster`
- Beam Size: 3
- Temperature: 0.0
- VAD Filter: true
- Overlap: 0.6s
- Dedupe: enabled
- Postprocess: enabled

**Latency Results**:
- Chunk 0: **2.0s**
- Chunk 1: **4.0s**
- Chunk 2: **6.0s**
- **Average: ~4.0s per chunk**

**Real-time Ratio**: 1.3x (latency > chunk duration)

---

## 📈 เปรียบเทียบ

| Model | Average Latency | Real-time Ratio | Status |
|-------|----------------|-----------------|--------|
| **Small** | 6.3s | 2.1x | ⚠️ Not real-time |
| **Medium-Faster** | 4.0s | 1.3x | ⚠️ Not real-time |

**ผลลัพธ์**: 
- ✅ **Medium-Faster เร็วกว่า Small ประมาณ 2.3 วินาที** (36% เร็วขึ้น)
- ⚠️ **ทั้งสอง model ยังไม่ real-time** (latency > 3s chunk duration)

---

## 🔍 สาเหตุที่ Latency สูง

### 1. CloseCaption Profile Features

- **Overlap Processing**: เพิ่ม buffer 0.6s → ประมวลผล 3.6s แทน 3s
- **Beam Size = 3**: ใช้เวลามากกว่า beam_size=1 (แต่แม่นกว่า)
- **Postprocess**: Normalize + Word Segmentation เพิ่มเวลาเล็กน้อย

### 2. Model Size

- **Small**: เร็วกว่า medium แต่แม่นน้อยกว่า
- **Medium-Faster**: ใหญ่กว่า small → ใช้เวลามากกว่าเล็กน้อย แต่แม่นกว่า

### 3. GPU Performance

- Latency ขึ้นอยู่กับ GPU performance
- RTX 4000 Ada อาจไม่เร็วพอสำหรับ real-time processing

---

## 💡 แนวทางลด Latency

### 1. ลด Beam Size

```bash
CC_BEAM_SIZE=1  # จาก 3 → 1 (เร็วกว่าแต่แม่นน้อยกว่า)
```

### 2. ปิด Postprocess (ถ้าไม่จำเป็น)

```bash
CC_POSTPROCESS_ENABLED=false
CC_POSTPROCESS_WORD_SEG=false
```

### 3. ลด Overlap

```bash
CC_CHUNK_OVERLAP=0.3  # จาก 0.6s → 0.3s
```

### 4. ใช้ Model ที่เล็กลง

```bash
CC_MODEL_SIZE=base  # หรือ tiny (เร็วที่สุด)
```

---

## ✅ สรุป

1. **Latency สูงขึ้น**: ใช่ (6.3s สำหรับ small, 4.0s สำหรับ medium-faster)
2. **Medium-Faster เร็วกว่า Small**: ใช่ (ประมาณ 2.3s เร็วขึ้น)
3. **Real-time**: ยังไม่ถึง (latency > chunk duration)

**คำแนะนำ**:
- ถ้าต้องการ **real-time** → ลด beam_size, ปิด postprocess, ลด overlap
- ถ้าต้องการ **คุณภาพ** → ใช้ medium-faster + beam_size=3 + postprocess

---

**วันที่ทดสอบ**: 2026-01-12  
**GPU**: RTX 4000 Ada  
**Chunk Duration**: 3 seconds
