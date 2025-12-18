# ทำไม Main API และ Dashboard ไม่ถูก SIGKILL แต่ Video Worker ถูก?

## คำถาม

1. ทำไม Main API (nohup) ถึงไม่ถูก SIGKILL?
2. ทำไม Dashboard (nohup) ถึงไม่ถูก SIGKILL?
3. Consumer RabbitMQ จะหายถ้า video_worker ถูก KILL ใช่ไหม?

## คำตอบ

### 1. ทำไม Main API ไม่ถูก SIGKILL?

**Main API (PID 17214):**
- รันด้วย: `python3 -m uvicorn app.main:app --port 8010`
- PPID = 1 (child ของ docker-init)
- ใช้ nohup (จาก `start-service-daemon.sh`)

**ทำไมไม่ถูก SIGKILL:**
- ✅ **Main API มี activity (HTTP requests)**
- ✅ **มี health check endpoint (`/health`) ที่ถูกเรียกบ่อย**
- ✅ **RunPod เห็นว่า service ยัง active → ไม่ idle**
- ✅ **ไม่ใช่ idle waiting → ไม่ถูก SIGTERM**

**ความแตกต่างจาก Video Worker:**
- Main API: มี external activity (HTTP requests) → RunPod เห็นว่า active
- Video Worker: รอคิว (idle waiting) → RunPod เห็นว่า idle → ถูก SIGTERM

### 2. ทำไม Dashboard ไม่ถูก SIGKILL?

**Dashboard (PID 8315):**
- รันด้วย: `python3 -m uvicorn main:app --port 8020`
- PPID = 1 (child ของ docker-init)
- ใช้ nohup (จาก `start-all-services.sh`)

**ทำไมไม่ถูก SIGKILL:**
- ✅ **Dashboard มี activity (HTTP requests)**
- ✅ **มี user เข้าใช้งาน → มี activity**
- ✅ **RunPod เห็นว่า service ยัง active → ไม่ idle**
- ✅ **ไม่ใช่ idle waiting → ไม่ถูก SIGTERM**

**ความแตกต่างจาก Video Worker:**
- Dashboard: มี external activity (HTTP requests) → RunPod เห็นว่า active
- Video Worker: รอคิว (idle waiting) → RunPod เห็นว่า idle → ถูก SIGTERM

### 3. Consumer RabbitMQ จะหายถ้า video_worker ถูก KILL ใช่ไหม?

**คำตอบ: ใช่! Consumer RabbitMQ จะหายเมื่อ video_worker ถูก KILL**

**เหตุผล:**
1. **Consumers ถูก register ผ่าน connection/channel ของ worker**
   - Consumers ถูก register ผ่าน `queue.consume(handler)`
   - Connection และ channel เป็นของ worker process

2. **เมื่อ process ถูก kill → connection ปิด**
   - Process ถูก kill → connection ถูกปิด
   - Connection ปิด → channel ปิด
   - Channel ปิด → consumers หาย

3. **RabbitMQ จะ requeue messages ที่ยังไม่ ack**
   - Messages ที่ยังไม่ ack จะถูก requeue
   - Messages ที่กำลัง process จะถูก requeue (ถ้า connection ปิดเร็วเกินไป)

**วิธีแก้ไข:**
1. **Worker restart อัตโนมัติ (main() loop)**
   - Worker มี infinite retry loop
   - Restart อัตโนมัติเมื่อถูก SIGTERM/SIGKILL

2. **Re-register consumers หลัง restart**
   - Worker จะ re-register consumers หลัง restart
   - แต่ถ้า restart ช้า → messages อาจค้างใน queue

3. **ใช้ On-Demand Pod (ไม่ใช่ Serverless)**
   - ป้องกัน SIGTERM/SIGKILL
   - Worker จะอยู่ได้นานเป็นชั่วโมง/วัน

## สรุป

| Service | Activity | Idle? | SIGKILL? |
|---------|----------|-------|----------|
| Main API | HTTP requests | ❌ | ❌ |
| Dashboard | HTTP requests | ❌ | ❌ |
| Video Worker | รอคิว (idle) | ✅ | ✅ |

**Key Point:**
- **RunPod lifecycle policy** จะ kill processes ที่ idle
- **Main API และ Dashboard** มี activity → ไม่ idle → ไม่ถูก kill
- **Video Worker** รอคิว (idle) → idle → ถูก kill

**Consumer RabbitMQ:**
- ✅ **จะหายเมื่อ video_worker ถูก KILL**
- ✅ **Worker restart อัตโนมัติ → re-register consumers**
- ✅ **Messages จะถูก requeue ถ้ายังไม่ ack**


