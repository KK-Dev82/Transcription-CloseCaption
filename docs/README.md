# 🎬 Transcription & Close Caption Service

บริการ API สำหรับการแปลงเสียงเป็นข้อความและสร้าง close caption แบบ real-time พร้อมระบบ Video Processing ที่ครบครันด้วย RabbitMQ

## ✨ Features

### 🎵 Transcription & Caption
- **Real-time Transcription**: แปลงเสียงเป็นข้อความแบบ real-time ด้วย Whisper
- **Close Caption Generation**: สร้าง subtitle หลายรูปแบบ (SRT, VTT, ASS)
- **Multi-language Support**: รองรับหลายภาษา
- **Chunk Processing**: ประมวลผลไฟล์ขนาดใหญ่แบบ chunk
- **Search Functionality**: ค้นหาข้อความใน transcription

### 🎬 Video Processing
- **Trim Video**: ตัดวิดีโอตามช่วงเวลา
- **Merge Videos**: รวมวิดีโอหลายไฟล์
- **Convert Format**: แปลงรูปแบบไฟล์ (MP4, AVI, MOV, MKV, etc.)
- **Resize Video**: ปรับขนาดวิดีโอ
- **Batch Processing**: ประมวลผลหลายไฟล์พร้อมกัน
- **Quality Control**: ตั้งค่าคุณภาพ (High, Medium, Low)

### 🔧 Technical Features
- **Async Processing**: ประมวลผลแบบ asynchronous ด้วย RabbitMQ
- **Message Queue**: ใช้ RabbitMQ สำหรับจัดการ video processing tasks
- **Video Worker**: Worker process สำหรับประมวลผลวิดีโอ
- **WebSocket Support**: Real-time status updates
- **File Management**: จัดการไฟล์อัปโหลดและผลลัพธ์
- **JSON Storage**: เก็บข้อมูลในรูปแบบ JSON
- **Docker Support**: รองรับการ deploy ด้วย Docker
- **Health Monitoring**: ตรวจสอบสถานะระบบ

## 🏗️ Architecture

### Development Environment Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   RabbitMQ      │
│   (React/Vue)   │◄──►│   Backend       │◄──►│   Message Queue │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Whisper API   │    │   Video Worker  │
                       │   (Container)   │    │   (FFmpeg)      │
                       │   Port 8002     │    │   (Container)   │
                       └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   JSON Storage  │    │   Processed     │
                       │   (File-based)  │    │   Video Files   │
                       └─────────────────┘    └─────────────────┘
```

### Container Separation
- **API Container**: ทำ video processing (FFmpeg) และ audio extraction
- **Whisper Container**: ทำ transcription เท่านั้น (ไม่มี FFmpeg)
- **Shared Volumes**: temp, uploads, models, storage

### Queue Architecture
```
API Service → RabbitMQ Queues → Video Workers
     │              │              │
     │              ▼              ▼
     │        ┌─────────────┐  ┌─────────────┐
     │        │ Trim Queue  │  │ Worker 1    │
     │        ├─────────────┤  ├─────────────┤
     │        │ Merge Queue │  │ Worker 2    │
     │        ├─────────────┤  ├─────────────┤
     │        │Convert Queue│  │ Worker N    │
     │        ├─────────────┤  └─────────────┘
     │        │Resize Queue │
     │        └─────────────┘
     ▼
JSON Storage ← Task Status Updates
```

## 📦 Installation

### Prerequisites
- Python 3.11+
- FFmpeg
- RabbitMQ
- Redis (optional)

### 1. Clone Repository
```bash
git clone <repository-url>
cd transcription-close-caption-service
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# ดาวน์โหลดจาก https://ffmpeg.org/download.html
```

### 4. Install RabbitMQ
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

### 5. Create Directories
```bash
mkdir -p uploads temp storage models
```

## 🚀 Quick Start

### Development Environment (แนะนำ)

1. **Setup Development Environment:**
   ```bash
   ./dev-setup.sh
   ```

2. **Rebuild และ Start Development Services:**
   ```bash
   ./rebuild-dev.sh
   ```

3. **Start Development Services (ถ้า build แล้ว):**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

4. **View Logs:**
   ```bash
   docker-compose -f docker-compose.dev.yml logs -f api
   docker-compose -f docker-compose.dev.yml logs -f whisper
   ```

### Development Mode (Local)
```bash
# รัน API Service
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# รัน Video Worker (ใน terminal อื่น)
python run_worker.py

# หรือรันหลาย workers
python run_worker.py &
python run_worker.py &
```

### Production Docker Mode
```bash
# รันระบบทั้งหมด (API + RabbitMQ + Workers)
docker-compose up --build

# ดู logs
docker-compose logs -f video-worker
docker-compose logs -f rabbitmq
```

### Access Services
- API Documentation: http://localhost:8001/docs
- Whisper API: http://localhost:8002/health
- RabbitMQ Management: http://localhost:15672 (admin/admin123)

## 📚 API Usage

### Video Processing with RabbitMQ

#### 1. อัปโหลดไฟล์วิดีโอ
```python
import requests

# อัปโหลดไฟล์
with open('video.mp4', 'rb') as f:
    files = {'file': ('video.mp4', f, 'video/mp4')}
    response = requests.post('http://localhost:8001/upload', files=files)
    
result = response.json()
file_path = result['file_path']
```

#### 2. ตัดวิดีโอ (ส่งไปยัง RabbitMQ)
```python
# ตัดวิดีโอช่วง 10-30 วินาที
data = {
    'input_file': file_path,
    'start_time': 10.0,
    'end_time': 30.0,
    'output_format': 'mp4',
    'quality': 'medium'
}

response = requests.post('http://localhost:8001/video/trim', data=data)
task_id = response.json()['task_id']
print(f"Task ID: {task_id}")  # ส่งไปยัง RabbitMQ queue
```

#### 3. ตรวจสอบสถานะ
```python
# ตรวจสอบสถานะ task
response = requests.get(f'http://localhost:8001/video/status/{task_id}')
status = response.json()
print(f"สถานะ: {status['status']}")

# รอให้เสร็จสิ้น
while status['status'] == 'pending':
    time.sleep(5)
    response = requests.get(f'http://localhost:8001/video/status/{task_id}')
    status = response.json()
    print(f"สถานะ: {status['status']}")
```

#### 4. Queue Management
```python
# ตรวจสอบสถานะ queue
response = requests.get('http://localhost:8001/queue/info')
queues = response.json()
print("Queue Status:", queues)

# ตรวจสอบสุขภาพ RabbitMQ
response = requests.get('http://localhost:8001/queue/health')
health = response.json()
print("RabbitMQ Health:", health)
```

### Queue Operations

#### ตรวจสอบ Queue Status
```bash
# ผ่าน API
curl http://localhost:8001/queue/info

# ผ่าน RabbitMQ Management UI
# เข้าไปที่ http://localhost:15672
```

#### ลบ Messages ใน Queue
```bash
curl -X POST http://localhost:8001/queue/purge/video_trim_queue
```

## 🔧 Configuration

### Environment Variables
```bash
# RabbitMQ Configuration
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=admin123

# API Configuration
ENVIRONMENT=production
PYTHONPATH=/app
```

### Docker Configuration
```yaml
# docker-compose.yml
services:
  api:
    ports:
      - "8001:8001"
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
  
  video-worker:
    deploy:
      replicas: 2  # รัน 2 workers
  
  rabbitmq:
    ports:
      - "5672:5672"
      - "15672:15672"
```

## 📊 Monitoring

### Queue Monitoring
```python
# ตรวจสอบสถิติ queue
response = requests.get('http://localhost:8001/queue/stats')
stats = response.json()
print("Queue Statistics:", stats)
```

### Worker Monitoring
```bash
# ดู worker logs
docker-compose logs -f video-worker

# ตรวจสอบ worker processes
ps aux | grep video_worker
```

### Health Checks
```bash
# API Health
curl http://localhost:8001/health

# Queue Health
curl http://localhost:8001/queue/health
```

## 🚀 Scaling

### เพิ่ม Workers
```bash
# ใน docker-compose.yml
video-worker:
  deploy:
    replicas: 5  # เพิ่มเป็น 5 workers

# หรือรัน workers แยก
python run_worker.py &
python run_worker.py &
python run_worker.py &
```

### Load Balancing
```yaml
# ใช้ nginx สำหรับ load balancing
nginx:
  ports:
    - "80:80"
  depends_on:
    - api
```

## 🔍 Troubleshooting

### RabbitMQ Issues
```bash
# ตรวจสอบสถานะ RabbitMQ
sudo systemctl status rabbitmq-server

# เริ่มต้นใหม่
sudo systemctl restart rabbitmq-server

# ตรวจสอบ queue
rabbitmqctl list_queues
```

### Worker Issues
```bash
# ตรวจสอบ worker logs
docker-compose logs video-worker

# ตรวจสอบ queue messages
curl http://localhost:8001/queue/info
```

### Performance Issues
```bash
# ตรวจสอบ CPU/Memory usage
docker stats

# ตรวจสอบ queue backlog
curl http://localhost:8001/queue/stats
```

## 📖 Documentation

- [RabbitMQ Setup Guide](RABBITMQ_SETUP.md)
- [API Documentation](http://localhost:8001/docs)
- [Video Processing Examples](examples/video_processing_example.py)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 