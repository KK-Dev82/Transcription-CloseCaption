# การ Optimize: 10 Tasks จาก 10 นาที → 8 นาที

**เป้า:** ลด 120 วินาที รวม (เฉลี่ย 12 วินาที/ไฟล์)  
**ไฟล์ทดสอบ:** WAV 16kHz mono, 30 นาที

---

## 1. ตรวจสอบว่าใช้เวลาไปกับอะไร

รันสคริปต์วิเคราะห์ bottleneck:

```bash
python scripts/analyze_bottleneck.py --limit 10
```

จะแสดง:
- **Phase breakdown:** Extract, Chunk, GPU Transcribe (wait), Fetch, Merge, Thai, Fuzzy
- **% ของแต่ละ phase**
- **คำแนะนำ** ตาม phase ที่ใช้เวลามาก

---

## 2. จุดที่มักใช้เวลามาก และวิธีลด

| Phase | สาเหตุ | วิธีลด |
|-------|--------|--------|
| **GPU Transcribe (wait_chunks)** | รอ GPU ทำ chunks — มัก 70–90% | เพิ่ม GPU workers (ถ้า CPU พอ), ลด chunk_duration |
| **Preprocess** | Extract + Chunk | ใช้ WAV แทน M4A, เพิ่ม preprocess workers |
| **Thai processing** | PyThaiNLP + Attacut | ปิด `enable_thai_processing` ถ้าไม่จำเป็น |
| **Fuzzy match** | แก้ชื่อคน/คำศัพท์ | ตั้ง `FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION=false` |
| **Fetch/Merge** | Redis GET + merge loop | ลดได้จำกัด |

---

## 3. การตั้งค่าที่ช่วยลดเวลา

### 3.1 ปิด Fuzzy Match (ถ้าไม่ใช้)
```bash
FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION=false
```
ประหยัด ~2–10 วินาที/ไฟล์ (ขึ้นกับความยาวข้อความ)

### 3.2 ลด chunk_duration (เพิ่ม parallel GPU)
```bash
TRANSCRIPTION_CHUNK_DURATION=150  # จาก 240
```
- Chunks เยอะขึ้น → GPU ได้งาน parallel มากขึ้น
- แต่ aggregator ใช้เวลานานขึ้น (fetch loop)
- ทดสอบดูว่า total ลดหรือไม่

### 3.3 เพิ่ม GPU workers (ถ้า CPU พอ)
```bash
GPU_WORKERS_PER_GPU=4  # จาก 3 (vCPU 10 จำกัด)
```
- ใช้ CPU เพิ่ม → ต้อง monitor ว่าไม่ overload

### 3.4 ปิด Thai processing (ถ้าไม่จำเป็น)
ส่ง `enable_thai_processing: false` ใน request  
หรือปรับใน aggregator ให้ข้ามขั้นตอนนี้

---

## 4. ลำดับการตรวจสอบ

1. รัน `analyze_bottleneck.py` หลังทดสอบ 10 tasks
2. ดู phase ที่ใช้เวลา % สูงสุด
3. ลองปรับตามตารางด้านบน
4. ทดสอบซ้ำ แล้วรัน analyze อีกครั้ง

---

## 5. ข้อจำกัด (vCPU 10)

- ไม่สามารถเพิ่ม workers ได้มาก — CPU จะ overload
- GPU Transcribe เป็นตัวหลัก — การเร่งต้องเพิ่ม GPU workers หรือใช้โมเดลเล็กกว่า
- Trade-off: ความแม่นยำ vs ความเร็ว (โมเดล small เร็วกว่า large)
