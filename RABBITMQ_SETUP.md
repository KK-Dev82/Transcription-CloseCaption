# การตั้งค่า RabbitMQ และ Video Worker

## ภาพรวม

ระบบนี้ใช้ RabbitMQ เป็น message queue เพื่อจัดการ video processing tasks แบบ asynchronous โดยมี Video Worker ที่จะประมวลผลงานที่ส่งมาจาก API

## สถาปัตยกรรม

```
API Service → RabbitMQ Queue → Video Worker → Processed Files
```

### Components

1. **API Service** - รับคำขอและส่ง tasks ไปยัง RabbitMQ
2. **RabbitMQ** - Message queue สำหรับจัดเก็บ tasks
3. **Video Worker** - ประมวลผล video tasks จาก queue
4. **JSON Storage** - เก็บสถานะและผลลัพธ์ของ tasks

## การติดตั้ง

### 1. ใช้ Docker Compose (แนะนำ)

```bash
# รันระบบทั้งหมด
docker-compose up -d

# ดู logs
docker-compose logs -f video-worker
docker-compose logs -f rabbitmq
```

### 2. ติดตั้งแบบ Manual

#### ติดตั้ง RabbitMQ

```bash
# Ubuntu/Debian
sudo apt-get install rabbitmq-server

# macOS
brew install rabbitmq

# เริ่มต้น RabbitMQ
sudo systemctl start rabbitmq-server
# หรือ
brew services start rabbitmq
```

#### ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

#### รัน Video Worker

```bash
# รัน worker
python run_worker.py

# หรือรันหลาย worker instances
python -m app.workers.video_worker &
python -m app.workers.video_worker &
```

## การใช้งาน

### 1. ส่ง Video Processing Task

```python
from app.services.video_service import VideoService

video_service = VideoService()

# ตัดวิดีโอ
task_id = await video_service.trim_video(
    input_file="uploads/video.mp4",
    start_time=10.0,
    end_time=30.0,
    output_format="mp4",
    quality="medium"
)

# รวมวิดีโอ
task_id = await video_service.merge_videos(
    input_files=["uploads/video1.mp4", "uploads/video2.mp4"],
    output_format="mp4",
    quality="high"
)

# แปลงรูปแบบ
task_id = await video_service.convert_format(
    input_file="uploads/video.avi",
    output_format="mp4",
    quality="medium"
)

# ปรับขนาดวิดีโอ
task_id = await video_service.resize_video(
    input_file="uploads/video.mp4",
    width=1920,
    height=1080,
    output_format="mp4",
    quality="high"
)
```

### 2. ตรวจสอบสถานะ Task

```python
from app.utils.json_storage import JSONStorage

json_storage = JSONStorage()

# ดึงสถานะ task
task = json_storage.load_video_task(task_id)
print(f"Status: {task['status']}")
print(f"Output: {task.get('output_file')}")
```

### 3. API Endpoints

#### Video Processing
- `POST /video/trim` - ตัดวิดีโอ
- `POST /video/merge` - รวมวิดีโอ
- `POST /video/convert` - แปลงรูปแบบ
- `POST /video/resize` - ปรับขนาดวิดีโอ
- `GET /video/status/{task_id}` - ตรวจสอบสถานะ

#### Queue Management
- `GET /queue/info` - ข้อมูล queue ทั้งหมด
- `GET /queue/health` - ตรวจสอบสถานะ RabbitMQ
- `GET /queue/stats` - สถิติ queue
- `POST /queue/purge/{queue_name}` - ลบ messages ใน queue

## Queue Configuration

### Queue Names
- `video_trim_queue` - สำหรับ trim video tasks
- `video_merge_queue` - สำหรับ merge video tasks
- `video_convert_queue` - สำหรับ convert format tasks
- `video_resize_queue` - สำหรับ resize video tasks

### Message Format

```json
{
  "task_id": "uuid-string",
  "type": "trim|merge|convert|resize",
  "status": "pending|processing|completed|failed",
  "input_file": "path/to/input/file",
  "output_format": "mp4",
  "quality": "low|medium|high",
  "created_at": "2024-01-01T00:00:00",
  "completed_at": "2024-01-01T00:05:00",
  "output_file": "path/to/output/file",
  "error_message": "error description"
}
```

## การ Monitor และ Debug

### 1. RabbitMQ Management UI

เข้าถึงได้ที่: http://localhost:15672
- Username: admin
- Password: admin123

### 2. ดู Logs

```bash
# API Service logs
docker-compose logs -f api

# Video Worker logs
docker-compose logs -f video-worker

# RabbitMQ logs
docker-compose logs -f rabbitmq
```

### 3. ตรวจสอบ Queue Status

```bash
# ผ่าน API
curl http://localhost:8001/queue/info

# ผ่าน RabbitMQ CLI
rabbitmqctl list_queues
```

## การ Scale

### เพิ่ม Video Workers

```bash
# ใน docker-compose.yml
video-worker:
  deploy:
    replicas: 5  # เพิ่มจำนวน workers
```

### หรือรัน workers แยก

```bash
# รันหลาย worker instances
python run_worker.py &
python run_worker.py &
python run_worker.py &
```

## Troubleshooting

### 1. RabbitMQ ไม่สามารถเชื่อมต่อได้

```bash
# ตรวจสอบสถานะ RabbitMQ
sudo systemctl status rabbitmq-server

# เริ่มต้นใหม่
sudo systemctl restart rabbitmq-server
```

### 2. Worker ไม่ประมวลผล tasks

```bash
# ตรวจสอบ queue
curl http://localhost:8001/queue/info

# ตรวจสอบ worker logs
docker-compose logs video-worker
```

### 3. Tasks ค้างใน queue

```bash
# ลบ messages ใน queue
curl -X POST http://localhost:8001/queue/purge/video_trim_queue
```

## Performance Tuning

### 1. Worker Configuration

```python
# ใน video_worker.py
self.channel.basic_qos(prefetch_count=1)  # รับงานทีละ 1 task
```

### 2. Queue Configuration

```python
# สร้าง queue แบบ durable
self.channel.queue_declare(queue=queue_name, durable=True)
```

### 3. Message Persistence

```python
# ส่ง message แบบ persistent
properties=pika.BasicProperties(delivery_mode=2)
```

## Security

### 1. RabbitMQ Authentication

```yaml
# ใน docker-compose.yml
environment:
  - RABBITMQ_DEFAULT_USER=admin
  - RABBITMQ_DEFAULT_PASS=admin123
```

### 2. Network Security

```yaml
# จำกัดการเข้าถึง RabbitMQ
ports:
  - "127.0.0.1:5672:5672"  # เฉพาะ localhost
```

## การ Backup และ Recovery

### 1. Backup RabbitMQ Data

```bash
# Backup queue data
docker exec transcription-rabbitmq rabbitmqctl export_definitions > backup.json
```

### 2. Restore RabbitMQ Data

```bash
# Restore queue data
docker exec -i transcription-rabbitmq rabbitmqctl import_definitions < backup.json
``` 