# 🎤 Transcription Close Caption Service

ระบบแปลงเสียงเป็นข้อความและสร้าง Close Caption สำหรับวิดีโอ

## 📁 โครงสร้างโปรเจค

```
transcription-close-caption-service/
├── app/                          # แอปพลิเคชันหลัก
│   ├── api/                      # API endpoints
│   ├── models/                   # Data models
│   ├── services/                 # Business logic
│   ├── utils/                    # Utilities
│   └── workers/                  # Background workers
├── scripts/                      # Scripts สำหรับจัดการระบบ
│   ├── fix_staging_permissions.sh  # แก้ไข permission ใน staging
│   ├── download-models.sh          # ดาวน์โหลด Whisper models
│   └── fix_permissions.py          # แก้ไข permission (Python)
├── test-files/                   # ไฟล์ทดสอบ
│   ├── index.html               ← หน้าแรกสำหรับเลือก test
│   ├── test-staging.html        ← HTML Tests
│   ├── test-frontend.html
│   ├── test-local.html
│   ├── test_permission_fix.html
│   └── python-tests/            ← Python Tests
│       ├── index.html           ← หน้าแรกสำหรับ Python Tests
│       ├── run_all_tests.py     ← รัน tests ทั้งหมด
│       ├── test_api_endpoints.py
│       ├── test_transcription.py
│       └── ...
├── docs/                         # เอกสาร
│   ├── README.md
│   ├── Deployment.md
│   └── *.json
├── whisper-service/              # Whisper service
├── models/                       # Whisper AI models
│   └── ggml-base.bin            ← Whisper base model (148MB)
├── storage/                      # ข้อมูลที่เก็บ
├── uploads/                      # ไฟล์ที่อัปโหลด
├── temp/                         # ไฟล์ชั่วคราว
└── requirements*.txt             # Dependencies
```

## 🚀 การใช้งาน

### 1. **Post-Deployment Setup (หลัง Deploy ขึ้น Server)**

#### **Step 1: เตรียม Whisper Models**
```bash
# ดาวน์โหลด Whisper models
cd scripts/
chmod +x download-models.sh
./download-models.sh

# ตรวจสอบ model file
ls -la models/
# ควรเห็น: ggml-base.bin (ประมาณ 148MB)
```

#### **Step 2: แก้ไข File Permissions**
```bash
# แก้ไข permission สำหรับ Docker containers
chmod +x fix_staging_permissions.sh
./fix_staging_permissions.sh

# ตรวจสอบ permissions
ls -la uploads/ temp/ storage/ models/
```

#### **Step 3: ตั้งค่า Environment Variables**
```bash
# ตรวจสอบ environment variables ใน docker-compose.yml
cat docker-compose.yml | grep -A 5 -B 5 environment

# หรือตรวจสอบใน container
docker exec transcription-api-staging env | grep -E "(API_URL|REDIS|RABBITMQ)"
```

#### **Step 4: ตั้งค่า Proxy/Port (สำหรับ Frontend)**
```nginx
# ตัวอย่าง nginx config สำหรับ WebSocket
location /transcribe/ {
    proxy_pass http://localhost:8001/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

#### **Step 5: เริ่มระบบและตรวจสอบ**
```bash
# เริ่ม services
docker compose up -d

# ตรวจสอบ logs
docker logs transcription-api-staging
docker logs transcription-whisper-staging
docker logs transcription-redis-staging
docker logs transcription-rabbitmq-staging

# ตรวจสอบ health
curl http://localhost:8001/health
```

### 2. **ทดสอบระบบ**
- **Test Index:** `http://localhost:8001/test-files/` หรือ `https://staging-ph2.bms.senate.go.th/transcribe/test-files/`
- **HTML Tests:** `test-staging.html`, `test-local.html`, `test_permission_fix.html`
- **Python Tests:** `test-files/python-tests/` หรือ `python test-files/python-tests/run_all_tests.py`

### 3. **API Endpoints**
- **Health Check:** `GET /health`
- **Upload File:** `POST /upload/`
- **Start Transcription:** `POST /transcribe-enhanced/start`
- **Get Results:** `GET /history/transcriptions/{task_id}`
- **WebSocket:** `WS /ws/transcription` (สำหรับ real-time updates)

## 🔧 การแก้ไขปัญหา

### **Permission Issues**
```bash
# ใช้ script แก้ไข permission
./scripts/fix_staging_permissions.sh

# ตรวจสอบ container user
docker exec transcription-api-staging id
docker exec transcription-whisper-staging id

# ตรวจสอบ file ownership
ls -la uploads/ temp/ storage/ models/
```

### **Model Loading Issues**
```bash
# ตรวจสอบ model file
file models/ggml-base.bin
ls -la models/ggml-base.bin

# Re-download model หากจำเป็น
./scripts/download-models.sh

# ตรวจสอบ Whisper service logs
docker logs transcription-whisper-staging --tail 20
```

### **WebSocket Issues**
```bash
# ตรวจสอบ WebSocket connection
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8001/ws/transcription

# ดู logs ใน browser console
# ตรวจสอบ nginx proxy settings สำหรับ WebSocket
```

### **Transcription Issues**
```bash
# ตรวจสอบ service status
docker ps | grep transcription

# ดู logs ของแต่ละ service
docker logs transcription-api-staging --tail 20
docker logs transcription-whisper-staging --tail 20
docker logs video-worker-1-staging --tail 20

# ตรวจสอบ database
docker exec transcription-api-staging ls -la /app/storage/
```

### **Environment Variables Issues**
```bash
# ตรวจสอบ env ใน container
docker exec transcription-api-staging env | grep -E "(API_URL|REDIS|RABBITMQ|WHISPER)"

# ตรวจสอบ docker-compose environment
cat docker-compose.yml | grep -A 10 -B 2 environment
```

## 📝 หมายเหตุ

### **File Permissions**
- **Directories:** `drwxrwxrwx` (777) - `uploads/`, `temp/`, `storage/`, `models/`
- **Files:** `rw-r--r--` (644) - ไฟล์ที่อัปโหลด
- **Owner:** `kscdev:kscdev` (1001:1001) บน host, `root:root` (0:0) ใน container

### **Performance**
- **ไฟล์ 4 วินาที:** ใช้เวลาประมาณ 1-2 นาที (อัตราส่วน ~20x)
- **Model size:** ggml-base.bin = 148MB
- **Memory usage:** ประมาณ 1-2GB RAM สำหรับ Whisper service

### **Network & Ports**
- **API:** Port 8001 (HTTP/WebSocket)
- **Whisper:** Port 8002 (HTTP)
- **Redis:** Port 6379
- **RabbitMQ:** Port 5672 (AMQP), 15672 (Management UI)
- **WebSocket:** รองรับ `wss://` และ `ws://`

### **Cleanup**
- ไฟล์ใน `temp/` จะถูกลบอัตโนมัติหลัง 24 ชั่วโมง
- ระบบรองรับ WebSocket และ Polling fallback
- Database cleanup ทำได้ผ่าน API endpoints
