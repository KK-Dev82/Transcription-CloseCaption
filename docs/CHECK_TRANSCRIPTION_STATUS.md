# 🔍 ตรวจสอบสถานะ Transcription Service

## คำสั่งตรวจสอบหลัง Restart

### 1. ตรวจสอบ Tasks ที่ค้างอยู่ (Processing)

```bash
# นับจำนวน tasks ที่ status = "processing"
docker exec -it video-worker-1 grep -r '"status":"processing"' /app/storage/transcriptions/ 2>/dev/null | wc -l

# แสดงรายละเอียด tasks ที่ processing
docker exec -it video-worker-1 grep -r '"status":"processing"' /app/storage/transcriptions/ 2>/dev/null
```

**ผลลัพธ์ที่คาดหวัง:**
- `0` = ไม่มี tasks ค้างอยู่ (ปกติ)
- `> 0` = มี tasks ค้างอยู่ (อาจต้องตรวจสอบเพิ่มเติม)

### 2. ตรวจสอบ Tasks ที่เสร็จสิ้น (Completed)

```bash
# นับจำนวน tasks ที่ status = "completed"
docker exec -it video-worker-1 grep -r '"status":"completed"' /app/storage/transcriptions/ 2>/dev/null | wc -l
```

**ผลลัพธ์ที่คาดหวัง:**
- จำนวน tasks ที่เสร็จสิ้นแล้ว (ปกติ)

### 3. ตรวจสอบ RabbitMQ Queue

```bash
# ตรวจสอบ messages ใน queue
docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep -E 'transcription|audio'
```

**ผลลัพธ์ที่คาดหวัง:**
- `transcription_queue 0` = ไม่มี messages ค้างอยู่ (ปกติ)
- `transcription_queue > 0` = มี messages ค้างอยู่ (อาจต้อง purge)

### 4. ตรวจสอบ Logs ล่าสุด

```bash
# ดู logs ล่าสุด 100 บรรทัด
docker logs video-worker-1 --tail 100 | grep -E 'chunk|transcription' | tail -20
```

**สิ่งที่ต้องระวัง:**
- ถ้าเห็น `สร้าง audio chunk 236`, `237`, `238`, ... ไปเรื่อยๆ → **ยังมีปัญหา infinite loop**
- ถ้าเห็น chunk numbers หยุดที่จำนวนที่เหมาะสม → **ปกติ**

### 5. ตรวจสอบ Infinite Loop

```bash
# ตรวจสอบ chunk numbers ใน logs
docker logs video-worker-1 --tail 200 | grep "สร้าง audio chunk" | tail -30

# ตรวจสอบว่า chunk numbers เพิ่มขึ้นเรื่อยๆ หรือไม่
docker logs video-worker-1 --tail 500 | grep "สร้าง audio chunk" | grep -oE 'chunk [0-9]+' | tail -20
```

**ผลลัพธ์ที่คาดหวัง:**
- Chunk numbers หยุดที่จำนวนที่เหมาะสม (เช่น 1-50 สำหรับวิดีโอ 25 นาที)
- **ไม่ควรเห็น** chunk numbers เพิ่มขึ้นเรื่อยๆ (236, 237, 238, ...)

### 6. ตรวจสอบ Tasks ใหม่หลัง Restart

```bash
# ดู tasks ที่สร้างล่าสุด
docker exec -it video-worker-1 ls -lt /app/storage/transcriptions/ | head -10

# ตรวจสอบ timestamp ของ task ใหม่
docker exec -it video-worker-1 stat /app/storage/transcriptions/*/task.json 2>/dev/null | grep Modify | sort -k2,3 | tail -5
```

**ผลลัพธ์ที่คาดหวัง:**
- Tasks ใหม่ถูกสร้างหลัง restart (ปกติ ถ้ามี transcription jobs ใหม่)
- **ไม่ควรเห็น** tasks เก่าถูกอัปเดตซ้ำๆ

## 🚨 สัญญาณเตือน

### ❌ ยังมีปัญหา Infinite Loop ถ้า:

1. **Chunk numbers เพิ่มขึ้นเรื่อยๆ:**
   ```
   สร้าง audio chunk 236: 5875s - 5905s
   สร้าง audio chunk 237: 5900s - 5930s
   สร้าง audio chunk 238: 5925s - 5955s
   ...
   ```

2. **Tasks มี status = "processing" ค้างอยู่หลายชั่วโมง:**
   ```bash
   docker exec -it video-worker-1 grep -r '"status":"processing"' /app/storage/transcriptions/ | grep -E '01:|02:|03:'
   ```

3. **RabbitMQ queue มี messages ค้างอยู่:**
   ```bash
   docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
   # ผลลัพธ์: transcription_queue 10 (มี messages ค้างอยู่)
   ```

### ✅ ปกติ ถ้า:

1. **Chunk numbers หยุดที่จำนวนที่เหมาะสม:**
   ```
   สร้าง audio chunk 1: 0s - 30s
   สร้าง audio chunk 2: 25s - 55s
   ...
   สร้าง audio chunks สำเร็จ: 50 chunks
   ```

2. **Tasks มี status = "completed" หรือ "failed":**
   ```bash
   docker exec -it video-worker-1 grep -r '"status":"completed"' /app/storage/transcriptions/ | wc -l
   # ผลลัพธ์: จำนวน tasks ที่เสร็จสิ้น
   ```

3. **RabbitMQ queue ว่างเปล่า:**
   ```bash
   docker exec -it rabbitmq rabbitmqctl list_queues name messages | grep transcription
   # ผลลัพธ์: transcription_queue 0
   ```

## 🔧 วิธีแก้ไขถ้ายังมีปัญหา

### 1. Purge RabbitMQ Queue

```bash
docker exec -it rabbitmq rabbitmqctl purge_queue transcription_queue
```

### 2. ลบ Tasks ที่ค้างอยู่

```bash
# ระวัง: ลบเฉพาะ tasks ที่ค้างอยู่จริงๆ
docker exec -it video-worker-1 find /app/storage/transcriptions/ -name "task.json" -exec grep -l '"status":"processing"' {} \; | xargs rm -f
```

### 3. Restart Workers อีกครั้ง

```bash
docker-compose -f docker-compose.staging.yml restart video-worker-1 video-worker-2
```

### 4. ตรวจสอบ Logs อีกครั้ง

```bash
docker logs video-worker-1 --tail 50 -f
```





