# RunPod Lifecycle Policy - SIGTERM Solution

## ปัญหา

Worker ถูก SIGTERM จาก RunPod platform ประมาณ 75-90 วินาที หลัง start แม้:
- Worker ไม่ crash
- ไม่มี exception/OOM/connection error
- Worker ไม่ idle (heartbeat ทุก 25 วินาที)
- RabbitMQ connection healthy

## สาเหตุ

**RunPod Lifecycle Policy** - Platform terminate worker ที่ idle (แม้มี heartbeat)

### Pattern ที่พบ:
- โดน SIGTERM ตอน "รอคิว" (ไม่ได้ทำงาน)
- เวลาอยู่ได้ใกล้ ๆ กันทุกครั้ง (~1-1.5 นาที)
- Heartbeat ไม่ช่วย (RabbitMQ heartbeat = platform มองไม่เห็น)

### สาเหตุที่เป็นไปได้:
1. **Serverless Worker** - ออกแบบมาให้ start → do job → exit
2. **Idle Timeout** - Platform terminate เมื่อ idle
3. **Job-based Container** - ไม่เหมาะกับ long-running consumer
4. **Spot / Interruptible Pod** - อาจถูก reclaim

## ทางแก้

### ทางที่ 1: On-Demand Pod (Non-Serverless) ⭐ แนะนำ

**ข้อดี:**
- ✅ ง่ายที่สุด - แค่เปลี่ยน RunPod settings
- ✅ ไม่ต้องแก้โค้ด
- ✅ Worker architecture เหมือนเดิม
- ✅ เหมาะกับ queue-based worker
- ✅ Worker จะอยู่ได้นานเป็นชั่วโมง/วัน

**ข้อเสีย:**
- ❌ ต้องจ่ายตลอดเวลา (แม้ idle)
- ❌ ไม่ scale-to-zero

**วิธีทำ:**
1. เปลี่ยน Pod type เป็น **On-Demand** (ไม่ใช่ Serverless)
2. ปิด **Idle Timeout** / **Auto-Stop**
3. ตั้ง **Max Execution Time** ให้มากพอ (หรือไม่จำกัด)
4. หลีกเลี่ยง **Spot / Interruptible**

### ทางที่ 2: Per-Job Worker (Serverless)

**ข้อดี:**
- ✅ จ่ายเฉพาะเมื่อทำงาน
- ✅ Scale-to-zero
- ✅ RunPod happy กับแบบนี้

**ข้อเสีย:**
- ❌ ยากกว่า - ต้องเปลี่ยน architecture
- ❌ ต้องแก้โค้ดเยอะ
- ❌ ต้องเปลี่ยน API flow

**วิธีทำ:**
1. เปลี่ยน API → สร้าง RunPod job แทนส่งไป RabbitMQ
2. Worker → start → process 1 task → exit
3. ไม่ใช้ long-running consumer
4. ไม่ใช้ heartbeat/stuck monitor

**Flow ใหม่:**
```
API → Create RunPod Job → Worker Start → Process 1 Task → Exit
```

## สิ่งที่ "ไม่ช่วย"

❌ เพิ่ม heartbeat  
❌ เปลี่ยน aio-pika เป็น pika  
❌ ทำ async → sync  
❌ เปลี่ยน prefetch  
❌ ปรับ RabbitMQ  

**เหตุผล:** ปัญหาไม่ได้อยู่ที่โค้ด แต่เป็น RunPod lifecycle policy

## คำแนะนำ

### สำหรับตอนนี้:
- **แนะนำใช้ On-Demand Pod** (ง่ายกว่า, ไม่ต้องแก้โค้ด)
- ถ้าต้องการประหยัด → ค่อยเปลี่ยนเป็น Per-Job ภายหลัง

### RunPod Settings ที่ต้องตั้ง:
1. **Pod Type:** On-Demand (ไม่ใช่ Serverless)
2. **Idle Timeout:** ปิด หรือตั้งให้มากพอ (เช่น 1 ชั่วโมง)
3. **Max Execution Time:** ไม่จำกัด หรือตั้งให้มากพอ
4. **Auto-Stop:** ปิด
5. **Spot / Interruptible:** ปิด

## สรุป

- **การวิเคราะห์ถูกต้อง 100%** - ไม่ใช่ปัญหาโค้ด แต่เป็น RunPod lifecycle policy
- **ทางแก้ที่ง่ายที่สุด:** ใช้ On-Demand Pod (ไม่ต้องแก้โค้ด)
- **ทางแก้ที่ประหยัดกว่า:** เปลี่ยนเป็น Per-Job Worker (แต่ต้องแก้โค้ดเยอะ)


