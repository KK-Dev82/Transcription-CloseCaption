# Dashboard Quick Start Guide

## การใช้งาน Dashboard

### 1. ติดตั้ง Dependencies

```bash
cd dashboard
pip install -r requirements.txt
```

หรือใช้ virtual environment:

```bash
cd dashboard
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. รัน Dashboard

**วิธีที่ 1: ใช้ script (แนะนำ)**

```bash
cd dashboard
bash run.sh
```

**วิธีที่ 2: รันด้วย Python โดยตรง**

```bash
cd dashboard
python main.py
```

**วิธีที่ 3: ใช้ uvicorn (development mode)**

```bash
cd dashboard
uvicorn main:app --host 0.0.0.0 --port 8020 --reload
```

### 3. เข้าถึง Dashboard

เปิด browser ไปที่: **http://localhost:8020**

## Features

### 📊 Task Summary
- แสดงจำนวน tasks ทั้งหมด (Total, Completed, Processing, Pending, Failed, Stuck)
- Auto refresh ทุก 5 วินาที

### ⚙️ Worker Status
- แสดงสถานะ worker process (Running/Stopped)
- แสดง PID, Uptime, Last Activity

### 📋 RabbitMQ Queues
- แสดงสถานะ queues (messages ready, unacked, consumers)
- ต้องมี RabbitMQ Management API enabled (port 15672)

### 📝 Tasks List
- แสดงรายการ tasks พร้อม filter ตาม status
- แสดง progress bar, text length, updated time
- Actions: Retry (สำหรับ failed tasks), Delete

## Configuration

Dashboard จะอ่าน configuration จาก:

1. **Environment Variables**:
   - `JSON_STORAGE_DIR`: Path to storage (default: `../storage`)
   - `SERVICE_URL`: Service URL (default: `http://localhost:8010`)
   - `DASHBOARD_PORT`: Dashboard port (default: `8020`)

2. **Parent `.env.runpod`** (ถ้ามี):
   - `RABBITMQ_HOST`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` สำหรับ queue status

## Troubleshooting

### Dashboard ไม่แสดงข้อมูล

1. ตรวจสอบว่า transcription service ทำงานอยู่:
   ```bash
   curl http://localhost:8010/health
   ```

2. ตรวจสอบว่า storage directory มีอยู่:
   ```bash
   ls -la ../storage/transcriptions/
   ```

3. ตรวจสอบ worker logs:
   ```bash
   tail -f /tmp/video-worker.log
   ```

### RabbitMQ Queue Status ไม่แสดง

- ต้องมี RabbitMQ Management API enabled
- ตรวจสอบว่า port 15672 เปิดอยู่
- ตรวจสอบ credentials ใน `.env.runpod`

## Development

```bash
# Install in development mode
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --port 8020
```

## Notes

- Dashboard อ่านข้อมูลจาก `storage/transcriptions/` directory โดยตรง
- Worker logs อ่านจาก `/tmp/video-worker.log`
- สำหรับ remote servers (4000-ada, 5080) อาจต้องใช้ SSH tunnel หรือ VPN

