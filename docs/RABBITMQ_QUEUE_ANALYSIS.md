# การวิเคราะห์ RabbitMQ Queue และ Connection Issues

## 📊 สรุปผลการตรวจสอบ

### 1️⃣ RabbitMQ Queue Status

- **Queue Name**: `transcription_queue`
- **Messages**: 28 (ลดลงจาก 100 แล้ว - บางส่วนถูก process แล้ว)
- **Consumers**: 0 (ยังไม่มี Worker)

### 2️⃣ Queue Limits

❌ **ไม่มี Queue Limit**
- Queue ไม่มี `x-max-length` (ไม่จำกัดจำนวน messages)
- Queue ไม่มี `x-message-ttl` (messages ไม่ expire)
- Queue สามารถเก็บ messages ได้ไม่จำกัด

⚠️ **ผลกระทบ**: ถ้ามี messages ส่งเข้ามามากๆ อาจทำให้ queue เต็มและใช้ memory มาก

### 3️⃣ Connection Timeout Settings

**Current Settings:**
- Heartbeat: 600 seconds (10 นาที)
- Blocked Connection Timeout: 300 seconds (5 นาที)
- Connection Attempts: 3
- Retry Delay: 2 seconds

**RabbitMQ Connection:**
- Host: 178.128.105.100:5672
- Status: Connected successfully

### 4️⃣ Video Worker Crash Analysis

#### Error ที่พบ:

```
IndexError: pop from an empty deque
StreamLostError: ("Stream connection lost: IndexError('pop from an empty deque')")
AssertionError: ('_AsyncTransportBase._initate_abort() expected _STATE_ABORTED_BY_USER', 2)
```

#### Timeline:

1. **15:15:18** - Video Worker รับ messages ได้หลายตัวพร้อมกัน (10+ messages)
   - Worker ใช้ `prefetch_count=10` เพื่อรับ messages หลายตัวพร้อมกัน
   
2. **15:15:23** - เกิด connection error ขณะกำลัง process messages
   - Pika library internal error: `IndexError: pop from an empty deque`
   - Connection lost: `StreamLostError`
   
3. **15:15:23** - Video Worker crash และ shutdown
   - Worker ไม่สามารถ acknowledge messages ได้
   - Messages ถูก return กลับไปที่ queue

#### สาเหตุ:

1. **Connection Instability**: Connection ระหว่าง Pod และ RabbitMQ server ไม่ stable
2. **Pika Library Bug**: Internal error ใน Pika library (อาจเกิดจาก concurrent access)
3. **High Prefetch Count**: รับ messages มากเกินไปพร้อมกัน (prefetch_count=10)
4. **Network Issues**: Network latency หรือ packet loss ระหว่าง Pod และ RabbitMQ server

### 5️⃣ ปัญหาที่พบ

#### ❌ ปัญหาหลัก:

1. **Video Worker ไม่ Stable**
   - Crash เมื่อมี messages มาก
   - Connection timeout ระหว่าง processing
   - Messages ถูก return กลับไปที่ queue (ต้อง process ซ้ำ)

2. **Connection Timeout Issues**
   - Network instability ระหว่าง Pod และ RabbitMQ server
   - Connection lost ขณะกำลัง process messages

3. **Queue ไม่มี Limit**
   - Messages อาจค้างได้มาก
   - ไม่มี mechanism เพื่อป้องกัน queue เต็ม

#### ⚠️ ปัญหารอง:

1. **Prefetch Count สูง**
   - `prefetch_count=10` อาจทำให้ connection overload
   - อาจทำให้เกิด connection timeout ง่ายขึ้น

2. **ไม่มีการ Retry Mechanism**
   - Failed messages ไม่ถูก retry อัตโนมัติ
   - Messages อาจค้างใน queue ถ้า worker crash

### 6️⃣ วิธีแก้ไขที่แนะนำ

#### ✅ 1. Restart Video Worker

```bash
ssh pytorch-pod
cd /workspace/transcription-service
bash scripts/pod/start-pod.sh
```

#### 💡 2. เพิ่ม Queue Limits (Optional)

เพิ่ม queue limits เพื่อป้องกัน queue เต็ม:

```python
# ใน video_worker.py
self.channel.queue_declare(
    queue=self.transcription_queue,
    durable=True,
    arguments={
        'x-max-length': 1000,  # จำกัดสูงสุด 1000 messages
        'x-message-ttl': 3600000  # Messages expire หลัง 1 ชั่วโมง (milliseconds)
    }
)
```

#### 💡 3. ลด Prefetch Count

ลด prefetch count เพื่อลด load บน connection:

```python
# ใน video_worker.py
self.channel.basic_qos(prefetch_count=5)  # ลดจาก 10 เป็น 5
```

#### 💡 4. เพิ่ม Connection Stability

เพิ่ม connection stability ด้วยการเพิ่ม heartbeat frequency:

```python
# ใน video_worker.py
parameters = pika.ConnectionParameters(
    host=self.rabbitmq_host,
    port=self.rabbitmq_port,
    credentials=credentials,
    heartbeat=300,  # ลดจาก 600 เป็น 300 seconds (5 นาที)
    blocked_connection_timeout=300,
    connection_attempts=5,  # เพิ่มจาก 3 เป็น 5
    retry_delay=2
)
```

#### 💡 5. เพิ่ม Error Handling

เพิ่ม error handling เพื่อป้องกัน worker crash:

```python
# เพิ่ม try-except สำหรับ connection errors
try:
    self.connection.process_data_events(time_limit=1)
except (pika.exceptions.ConnectionClosed, pika.exceptions.StreamLostError) as e:
    logger.error(f"Connection error: {e}")
    # Reconnect logic
    self._reconnect()
```

#### 💡 6. Monitor Queue

ตรวจสอบ queue size เป็นประจำ:

```bash
# Script สำหรับตรวจสอบ queue
python3 -c "
import pika
credentials = pika.PlainCredentials('senate', 'qP2VtHz6fAX4xDksEpMrLT')
parameters = pika.ConnectionParameters(
    host='178.128.105.100',
    port=5672,
    credentials=credentials
)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()
method = channel.queue_declare(queue='transcription_queue', passive=True)
print(f'Messages: {method.method.message_count}')
print(f'Consumers: {method.method.consumer_count}')
"
```

## 📝 สรุป

**ปัญหาหลัก**: Video Worker crash เนื่องจาก connection instability และ Pika library internal error

**วิธีแก้ไขด่วน**: Restart Video Worker และ monitor logs

**วิธีแก้ไขระยะยาว**: 
- ลด prefetch count
- เพิ่ม connection stability
- เพิ่ม error handling
- เพิ่ม queue limits (optional)

