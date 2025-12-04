# แก้ไขปัญหาการเชื่อมต่อ RabbitMQ ใน Video Worker

## ปัญหาที่พบ

Worker พยายามเชื่อมต่อ RabbitMQ ที่ `localhost:5672` แทนที่จะเป็น `178.128.105.100:5672` ทำให้:

1. **Connection Refused** - ไม่สามารถเชื่อมต่อ RabbitMQ ได้
2. **Worker Exit** - Worker จะหยุดทำงานหลังจาก retry 10 ครั้ง
3. **Messages ค้างใน Queue** - มี messages รออยู่ใน queue แต่ไม่มี consumers

## สาเหตุ

Worker ไม่ได้โหลด environment variables จาก `.env.runpod` ทำให้ใช้ค่า default `localhost` แทนค่าที่ถูกต้อง

## วิธีแก้ไข

### 1. แก้ไข Code (ทำแล้ว ✅)

เพิ่มการโหลด `.env.runpod` ใน `app/workers/video_worker.py`:

```python
# Load .env.runpod if exists (ต้องทำก่อน import services ที่ใช้ environment variables)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
        logger_temp = logging.getLogger(__name__)
        logger_temp.info(f"✅ Loaded environment from: {env_file}")
except ImportError:
    pass  # python-dotenv not installed, will use system env vars
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️  Failed to load .env.runpod: {e}")
```

### 2. Sync Code ไปที่ Server

```bash
# บน local machine
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# Commit และ push code
git add app/workers/video_worker.py
git commit -m "Fix: Load .env.runpod in video_worker to use correct RabbitMQ host"
git push origin staging
```

### 3. Pull Code และ Restart Worker บน Server

```bash
# SSH เข้า Pod
ssh pytorch-pod

# Pull code ใหม่
cd /workspace/transcription-service
git pull origin staging

# Stop Worker เก่า
pkill -9 -f "video_worker"

# Restart Worker ด้วย script
bash scripts/pod/start-service-daemon.sh
```

หรือ restart Worker โดยตรง:

```bash
# Load environment variables
set -a
source .env.runpod
set +a

# Start Worker
nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 &
```

### 4. ตรวจสอบว่า Worker เชื่อมต่อสำเร็จ

```bash
# Check Worker logs
tail -f /tmp/video-worker.log

# ควรเห็น:
# ✅ Loaded environment from: /workspace/transcription-service/.env.runpod
# RabbitMQ Configuration: 178.128.105.100:5672
# ✅ Connected to RabbitMQ successfully
```

## ตรวจสอบ Queue Status

```bash
# เชื่อมต่อ RabbitMQ และตรวจสอบ queue
python3 << "PYEOF"
import pika
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path("/workspace/transcription-service/.env.runpod"))

host = os.getenv("RABBITMQ_HOST")
port = int(os.getenv("RABBITMQ_PORT", 5672))
user = os.getenv("RABBITMQ_USER")
password = os.getenv("RABBITMQ_PASSWORD")

credentials = pika.PlainCredentials(user, password)
parameters = pika.ConnectionParameters(host=host, port=port, virtual_host="/", credentials=credentials)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()

queues = ["transcription_request_queue", "audio_extraction_queue", "transcription_queue"]
print("Queue Status:")
for queue_name in queues:
    try:
        method = channel.queue_declare(queue_name, passive=True)
        msg_count = method.method.message_count
        consumer_count = method.method.consumer_count
        print(f"  {queue_name}: {msg_count} messages, {consumer_count} consumers")
    except Exception as e:
        print(f"  {queue_name}: ERROR - {e}")

connection.close()
PYEOF
```

## Quick Fix (Temporary)

หากต้องการแก้ไขชั่วคราวโดยไม่ต้อง sync code:

```bash
# SSH เข้า Pod
ssh pytorch-pod

# Stop Worker
pkill -9 -f "video_worker"

# Start Worker พร้อม environment variables
cd /workspace/transcription-service
export RABBITMQ_HOST=178.128.105.100
export RABBITMQ_PORT=5672
export RABBITMQ_USER=senate
export RABBITMQ_PASSWORD=qP2VtHz6fAX4xDksEpMrLT

nohup python3 -m app.workers.video_worker > /tmp/video-worker.log 2>&1 &

# Check logs
tail -f /tmp/video-worker.log
```

## สรุป

1. ✅ แก้ไข code ให้โหลด `.env.runpod` แล้ว
2. ⏳ ต้อง sync code ไปที่ server
3. ⏳ Restart Worker หลังจาก sync code
4. ✅ Worker จะใช้ RabbitMQ host ที่ถูกต้อง (`178.128.105.100:5672`)

