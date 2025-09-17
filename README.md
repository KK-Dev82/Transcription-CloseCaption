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
│   ├── fix_staging_permissions.sh
│   └── fix_permissions.py
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
├── storage/                      # ข้อมูลที่เก็บ
├── uploads/                      # ไฟล์ที่อัปโหลด
├── temp/                         # ไฟล์ชั่วคราว
└── requirements*.txt             # Dependencies
```

## 🚀 การใช้งาน

### 1. **Staging Environment**
```bash
# แก้ไข permission ใน staging server
cd scripts/
chmod +x fix_staging_permissions.sh
./fix_staging_permissions.sh
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

## 🔧 การแก้ไขปัญหา

### **Permission Issues**
```bash
# ใช้ script แก้ไข permission
./scripts/fix_staging_permissions.sh
```

### **WebSocket Issues**
- ตรวจสอบ `app/api/websocket.py` สำหรับ pong message handling
- ดู logs ใน browser console

### **Transcription Issues**
- ตรวจสอบ Whisper service status
- ดู logs ใน `app/services/transcription_service.py`

## 📝 หมายเหตุ

- ไฟล์ใน `uploads/` จะมี permission `644` (rw-r--r--)
- ไฟล์ใน `temp/` จะถูกลบอัตโนมัติหลัง 24 ชั่วโมง
- ระบบรองรับ WebSocket และ Polling fallback
