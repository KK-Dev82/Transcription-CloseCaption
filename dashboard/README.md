# Transcription Service Dashboard

Mini dashboard สำหรับ monitor และ control transcription service

## Features

- 📊 **Task Summary**: แสดงสถิติ tasks ทั้งหมด (completed, processing, pending, failed, stuck)
- ⚙️ **Worker Status**: แสดงสถานะ worker process (running/stopped, PID, uptime)
- 📋 **Queue Status**: แสดงสถานะ RabbitMQ queues (messages ready, unacked, consumers)
- 📝 **Tasks List**: แสดงรายการ tasks พร้อม filter และ actions
- 🔄 **Auto Refresh**: Auto refresh ทุก 5 วินาที
- 🎨 **Modern UI**: สวยงาม responsive design

## Installation

```bash
cd dashboard
pip install -r requirements.txt
```

## Usage

### Start Dashboard

```bash
python main.py
```

หรือ

```bash
uvicorn main:app --host 0.0.0.0 --port 8020 --reload
```

### Access Dashboard

เปิด browser ไปที่: `http://localhost:8020`

## Configuration

Dashboard จะอ่าน configuration จาก environment variables หรือ parent `.env.runpod`:

- `JSON_STORAGE_DIR`: Path to transcription storage (default: `../storage`)
- `SERVICE_URL`: Transcription service URL (default: `http://localhost:8010`)
- `RABBITMQ_HOST`: RabbitMQ host (for queue status)
- `RABBITMQ_USER`: RabbitMQ username
- `RABBITMQ_PASSWORD`: RabbitMQ password
- `DASHBOARD_PORT`: Dashboard port (default: `8020`)

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/tasks/summary` - Get tasks summary
- `GET /api/tasks` - Get tasks list (with optional `status` filter)
- `GET /api/tasks/{task_id}` - Get task details
- `GET /api/worker/status` - Get worker status
- `GET /api/queues/status` - Get RabbitMQ queues status
- `GET /api/logs/recent` - Get recent worker logs
- `POST /api/worker/restart` - Restart worker (placeholder)
- `POST /api/tasks/{task_id}/retry` - Retry failed task (placeholder)
- `DELETE /api/tasks/{task_id}` - Delete task

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --port 8020

# Or run directly
python main.py
```

## Notes

- Dashboard อ่านข้อมูลจาก `storage/transcriptions/` directory
- Worker logs อ่านจาก `/tmp/video-worker.log`
- RabbitMQ queue status ต้องมี RabbitMQ Management API enabled (port 15672)

