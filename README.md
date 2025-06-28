# 🎬 Transcription & Close Caption Service

บริการ API สำหรับการแปลงเสียงเป็นข้อความและสร้าง close caption แบบ real-time พร้อมระบบ Video Processing ที่ครบครัน

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
- **Async Processing**: ประมวลผลแบบ asynchronous
- **WebSocket Support**: Real-time status updates
- **File Management**: จัดการไฟล์อัปโหลดและผลลัพธ์
- **JSON Storage**: เก็บข้อมูลในรูปแบบ JSON
- **Docker Support**: รองรับการ deploy ด้วย Docker
- **Health Monitoring**: ตรวจสอบสถานะระบบ

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   FFmpeg        │
│   (React/Vue)   │◄──►│   Backend       │◄──►│   Processing    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Whisper.cpp   │
                       │   Transcription │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   JSON Storage  │
                       │   (File-based)  │
                       └─────────────────┘
```

## 📦 Installation

### Prerequisites
- Python 3.11+
- FFmpeg
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

### 4. Create Directories
```bash
mkdir -p uploads temp storage models
```

## 🚀 Quick Start

### Development Mode
```bash
# รันด้วย uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# หรือรันด้วย Python
python main.py
```

### Docker Mode
```bash
# Development
docker-compose -f docker-compose.dev.yml up --build

# Production
docker-compose up --build
```

### Access API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📚 API Usage

### Video Processing

#### 1. อัปโหลดไฟล์วิดีโอ
```python
import requests

# อัปโหลดไฟล์
with open('video.mp4', 'rb') as f:
    files = {'file': ('video.mp4', f, 'video/mp4')}
    response = requests.post('http://localhost:8000/video/upload', files=files)
    
result = response.json()
file_path = result['file_path']
```

#### 2. ตัดวิดีโอ
```python
# ตัดวิดีโอช่วง 10-30 วินาที
data = {
    'input_file': file_path,
    'start_time': 10.0,
    'end_time': 30.0,
    'output_format': 'mp4',
    'quality': 'medium'
}

response = requests.post('http://localhost:8000/video/trim', data=data)
task_id = response.json()['task_id']
```

#### 3. แปลงรูปแบบ
```python
# แปลงเป็น AVI
data = {
    'input_file': file_path,
    'output_format': 'avi',
    'quality': 'high'
}

response = requests.post('http://localhost:8000/video/convert', data=data)
task_id = response.json()['task_id']
```

#### 4. ปรับขนาด
```python
# ปรับเป็น 640x480
data = {
    'input_file': file_path,
    'width': 640,
    'height': 480,
    'output_format': 'mp4',
    'quality': 'medium'
}

response = requests.post('http://localhost:8000/video/resize', data=data)
task_id = response.json()['task_id']
```

#### 5. Batch Processing
```python
operations = [
    {
        "type": "trim",
        "input_file": file_path,
        "start_time": 0.0,
        "end_time": 15.0,
        "output_format": "mp4"
    },
    {
        "type": "convert",
        "input_file": file_path,
        "output_format": "mov"
    }
]

response = requests.post('http://localhost:8000/video/batch', json=operations)
task_id = response.json()['task_id']
```

#### 6. ตรวจสอบสถานะ
```python
# ตรวจสอบสถานะ task
response = requests.get(f'http://localhost:8000/video/status/{task_id}')
status = response.json()
print(f"สถานะ: {status['status']}")
```

#### 7. ดาวน์โหลดผลลัพธ์
```python
# ดาวน์โหลดไฟล์ผลลัพธ์
response = requests.get(f'http://localhost:8000/video/download/{task_id}')
with open('output.mp4', 'wb') as f:
    f.write(response.content)
```

### Transcription & Caption

#### 1. อัปโหลดไฟล์เสียง/วิดีโอ
```python
with open('audio.mp3', 'rb') as f:
    files = {'file': ('audio.mp3', f, 'audio/mpeg')}
    response = requests.post('http://localhost:8000/upload', files=files)
    
result = response.json()
file_path = result['file_path']
```

#### 2. สร้าง Transcription
```python
data = {
    'file_path': file_path,
    'language': 'th',
    'chunk_size': 30
}

response = requests.post('http://localhost:8000/transcription/create', json=data)
task_id = response.json()['task_id']
```

#### 3. สร้าง Caption
```python
data = {
    'file_path': file_path,
    'language': 'th',
    'subtitle_format': 'srt'
}

response = requests.post('http://localhost:8000/caption/create', json=data)
task_id = response.json()['task_id']
```

#### 4. ค้นหาข้อความ
```python
# ค้นหาใน transcription
response = requests.get(f'http://localhost:8000/transcription/search/{task_id}?query=คำค้นหา')
results = response.json()

# ค้นหาในทุก transcription
response = requests.get('http://localhost:8000/transcription/search?query=คำค้นหา')
results = response.json()
```

## 🔧 Configuration

### Environment Variables
```bash
# API Configuration
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# File Storage
UPLOAD_DIR=uploads
TEMP_DIR=temp
STORAGE_DIR=storage

# Whisper Configuration
WHISPER_MODEL=base
WHISPER_LANGUAGE=th
CHUNK_SIZE=30

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379
```

### Quality Settings
- **High**: CRF 18, preset slow (คุณภาพสูง, ประมวลผลช้า)
- **Medium**: CRF 23, preset medium (คุณภาพปานกลาง, ประมวลผลปานกลาง)
- **Low**: CRF 28, preset fast (คุณภาพต่ำ, ประมวลผลเร็ว)

## 📁 Project Structure

```
transcription-close-caption-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   ├── transcription.py    # Transcription API
│   │   ├── caption.py          # Caption API
│   │   ├── upload.py           # Upload API
│   │   ├── video.py            # Video Processing API
│   │   └── websocket.py        # WebSocket API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcription_service.py
│   │   ├── caption_service.py
│   │   ├── video_service.py    # Video processing logic
│   │   ├── file_service.py
│   │   └── whisper_service.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── json_storage.py
│   └── models/
├── uploads/                     # อัปโหลดไฟล์
├── temp/                       # ไฟล์ชั่วคราว
├── storage/                    # ข้อมูล JSON
├── models/                     # Whisper models
├── examples/
│   ├── example_usage.py
│   └── video_processing_example.py
├── docker-compose.yml          # Production Docker
├── docker-compose.dev.yml      # Development Docker
├── Dockerfile
├── requirements.txt
└── README.md
```

## 🐳 Docker Deployment

### Development
```bash
# รัน development environment
docker-compose -f docker-compose.dev.yml up --build

# รันพร้อม database
docker-compose -f docker-compose.dev.yml --profile db up --build
```

### Production
```bash
# รัน production environment
docker-compose up --build

# รันพร้อม nginx และ database
docker-compose --profile production up --build
```

### Docker Commands
```bash
# Build image
docker build -t transcription-service .

# Run container
docker run -p 8000:8000 -v $(pwd)/uploads:/app/uploads transcription-service

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 🔍 Monitoring & Health

### Health Check
```bash
curl http://localhost:8000/health
```

### System Stats
```bash
curl http://localhost:8000/stats
```

### WebSocket Monitoring
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Task update:', data);
};

// Subscribe to task updates
ws.send(JSON.stringify({
    type: 'subscribe_task',
    task_id: 'your-task-id',
    task_type: 'video'
}));
```

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with coverage
pytest --cov=app
```

### Example Usage
```bash
# รันตัวอย่าง video processing
python examples/video_processing_example.py

# รันตัวอย่าง transcription
python examples/example_usage.py
```

## 🔧 Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

2. **Permission denied**
   ```bash
   chmod +x main.py
   chmod -R 755 uploads temp storage
   ```

3. **Port already in use**
   ```bash
   # เปลี่ยน port
   uvicorn app.main:app --port 8001
   
   # หรือ kill process
   lsof -ti:8000 | xargs kill -9
   ```

4. **Memory issues**
   ```bash
   # ลด chunk size
   export CHUNK_SIZE=15
   
   # เพิ่ม swap space
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

## 📈 Performance Optimization

### สำหรับไฟล์ขนาดใหญ่
- ใช้ chunk processing
- ตั้งค่า quality เป็น "low" สำหรับการประมวลผลเร็ว
- ใช้ batch processing สำหรับหลายไฟล์

### สำหรับ Real-time
- ใช้ WebSocket สำหรับ status updates
- ตั้งค่า chunk size เล็ก (10-15 วินาที)
- ใช้ async processing

### สำหรับ Production
- ใช้ Redis สำหรับ caching
- ตั้งค่า nginx สำหรับ load balancing
- ใช้ PostgreSQL สำหรับ metadata

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- 📧 Email: support@example.com
- 📖 Documentation: `/docs`
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions

---

**Made with ❤️ for the Thai developer community** 