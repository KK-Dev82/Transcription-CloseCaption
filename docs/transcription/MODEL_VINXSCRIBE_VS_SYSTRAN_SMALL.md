# เปรียบเทียบ: เปลี่ยนมาใช้ Systran/faster-whisper-small ทั้ง Transcription และ CC ดีไหม

**อัปเดต:** 2026-01-29

---

## สถานะปัจจุบัน

| ใช้กับ | Model ปัจจุบัน |
|--------|-----------------|
| **Transcription (file)** | `Vinxscribe/biodatlab-whisper-th-medium-faster` (WHISPER_MODEL) |
| **CC (Close Caption)** | เดียวกัน (CC_MODEL_SIZE หรือ fallback WHISPER_MODEL) |

- **Vinxscribe:** โมเดล **medium** ที่ **ปรับสำหรับภาษาไทย** (biodatlab-whisper-th-medium-faster)
- **Systran/faster-whisper-small:** โมเดล **small** ของ faster-whisper แบบ **multilingual** (ไม่เน้นไทยโดยเฉพาะ)

---

## ข้อดีของการเปลี่ยนเป็น Systran/faster-whisper-small ทั้งคู่

| ข้อดี | รายละเอียด |
|--------|-------------|
| **ความเร็ว** | small เร็วกว่า medium → เวลาแปลงต่อ chunk สั้นลง, throughput สูงขึ้น |
| **VRAM น้อยลง** | small ใช้ VRAM น้อยกว่า medium → รัน workers ต่อ GPU ได้มากขึ้น หรือลดโอกาส OOM |
| **โมเดลเดียวทั้งระบบ** | ใช้ model เดียวทั้ง Transcription และ CC → cache เดียว, deploy/maintain ง่าย |
| **ความสม่ำเสมอ** | ผลลัพธ์ CC กับผล file transcription มาจาก model เดียว → “เสียง” เหมือนกัน |

---

## ข้อเสีย / ความเสี่ยง

| ข้อเสีย | รายละเอียด |
|--------|-------------|
| **คุณภาพภาษาไทยอาจลด** | Vinxscribe ถูกออกแบบ/เทรนเน้น **ภาษาไทย**; Systran small เป็น multilingual ทั่วไป → โดยเฉพาะคำศัพท์เฉพาะทาง/ชื่อไทย อาจแม่นน้อยลง |
| **ต้องทดสอบก่อนใช้จริง** | ควร A/B กับคลิปเสียงไทยจริง (ทั้งพูดชัด, มีศัพท์เฉพาะ, มีเสียงรบกวน) ก่อนตัดสินใจเปลี่ยนทั้งระบบ |

---

## คำแนะนำ

### ถ้าต้องการ **ความแม่นยำภาษาไทยเป็นหลัก** (เช่น สภา, บันทึกทางการ)

- **ไม่แนะนำ** ให้เปลี่ยนทั้งคู่เป็น Systran small  
- **แนะนำ:** คง **Vinxscribe** ไว้ทั้ง Transcription และ CC  
- ถ้าต้องการเร่งความเร็ว: พิจารณา **ลด chunk_duration** หรือเพิ่ม workers แทนการเปลี่ยน model

### ถ้าต้องการ **ความเร็ว / throughput / ลด VRAM** และยอมลดความแม่นยำไทยได้บ้าง

- **พิจารณา** ใช้ **Systran/faster-whisper-small** ทั้ง Transcription และ CC ได้  
- **ควรทำก่อนเปลี่ยนจริง:**
  1. **A/B test บนคลิปไทยจริง:** รันงานเดียวกันด้วย Vinxscribe กับ Systran small แล้วเปรียบเทียบข้อความ (คำผิด, การตัดคำ, ชื่อ)  
  2. ถ้าผล Systran small **ยอมรับได้** สำหรับ use case ของคุณ ค่อยเปลี่ยน default ใน env  

### ทางเลือกแบบผสม (Transcription เน้นคุณภาพ, CC เน้นความเร็ว)

- **Transcription (file):** คง **Vinxscribe** (คุณภาพไทยดี)
- **CC:** ใช้ **Systran small** (CC_MODEL_SIZE=Systran/faster-whisper-small) เพื่อความเร็วและ latency ต่ำ  
- ข้อเสีย: ต้องโหลด/cache 2 โมเดล และผล CC กับผล file อาจไม่เหมือนกันทุกคำ

---

## วิธีเปลี่ยน (ถ้าตัดสินใจใช้ Systran small ทั้งคู่)

ตั้งค่าใน `.env.runpod` (หรือ env ที่ใช้รัน worker):

```bash
# ใช้ Systran small ทั้ง Transcription และ CC
WHISPER_MODEL=Systran/faster-whisper-small
CC_MODEL_SIZE=Systran/faster-whisper-small
```

จากนั้น **restart API และ RQ workers** (และ clear cache model เก่าถ้าต้องการบังคับโหลดใหม่)

---

## สรุปสั้นๆ

| คำถาม | คำตอบ |
|--------|--------|
| **เปลี่ยนมาใช้ Systran/faster-whisper-small ทั้ง Transcription และ CC ดีไหม?** | **ดีในแง่ความเร็วและความง่าย** แต่ **ไม่ดีในแง่คุณภาพภาษาไทย** เมื่อเทียบกับ Vinxscribe |
| **ควรเปลี่ยนไหม?** | ขึ้นกับว่า **ให้ความสำคัญกับความแม่นยำไทยหรือความเร็วมากกว่า** — ถ้าเน้นไทย แนะนำคง Vinxscribe; ถ้าเน้น throughput/VRAM แนะนำทดสอบ Systran small บนคลิปจริงก่อน แล้วค่อยเปลี่ยน |
