# Configuration Formats

Transcription Service รองรับหลายรูปแบบการตั้งค่า (Configuration) เพื่อความยืดหยุ่นในการใช้งาน

## รูปแบบการตั้งค่าที่รองรับ

### 1. Environment Variables (`.env` file) - Default

**ไฟล์**: `.env.runpod` หรือ `env.runpod`

**รูปแบบ**:
```bash
RABBITMQ_HOST=178.128.105.100
RABBITMQ_PORT=5672
GPU_CONCURRENCY=2
TASK_TIMEOUT_SECONDS=1800
```

**ใช้งาน**:
- โหลดอัตโนมัติผ่าน `python-dotenv`
- ใช้ `os.getenv()` ใน code
- รองรับทุก platform

**ข้อดี**:
- ง่ายต่อการแก้ไข
- มาตรฐานทั่วไป
- รองรับ comments และ blank lines

**ข้อเสีย**:
- ไม่รองรับ type validation
- ต้อง parse string เป็น type เอง

---

### 2. Python Configuration (`.py` file) - Alternative

**ไฟล์**: `config/worker_config.py`

**รูปแบบ**:
```python
RABBITMQ_HOST = '178.128.105.100'
RABBITMQ_PORT = 5672
GPU_CONCURRENCY = 2
TASK_TIMEOUT_SECONDS = 1800
```

**ใช้งาน**:
```python
from config.worker_config import RABBITMQ_HOST, GPU_CONCURRENCY
```

**ข้อดี**:
- Type safety (int, float, bool)
- สามารถใช้ logic, functions, imports ได้
- IDE support (autocomplete, type checking)

**ข้อเสีย**:
- ต้อง import ใน code
- อาจมี security risk ถ้ามี arbitrary code execution

---

### 3. YAML Configuration (`.yaml` file) - Alternative

**ไฟล์**: `config/worker_config.yaml`

**รูปแบบ**:
```yaml
rabbitmq:
  host: 178.128.105.100
  port: 5672

gpu:
  concurrency: 2

transcription:
  task_timeout_seconds: 1800
```

**ใช้งาน**:
```python
import yaml
with open('config/worker_config.yaml') as f:
    config = yaml.safe_load(f)
    host = config['rabbitmq']['host']
```

**ข้อดี**:
- โครงสร้างเป็นลำดับชั้น (hierarchical)
- อ่านง่าย
- รองรับ comments

**ข้อเสีย**:
- ต้องติดตั้ง `pyyaml`
- ไม่มี type checking โดยตรง

---

### 4. JSON Configuration (`.json` file) - Alternative

**ไฟล์**: `config/worker_config.json`

**รูปแบบ**:
```json
{
  "rabbitmq": {
    "host": "178.128.105.100",
    "port": 5672
  },
  "gpu": {
    "concurrency": 2
  }
}
```

**ใช้งาน**:
```python
import json
with open('config/worker_config.json') as f:
    config = json.load(f)
    host = config['rabbitmq']['host']
```

**ข้อดี**:
- มาตรฐาน (JSON)
- ใช้งานง่าย
- รองรับในหลายภาษา

**ข้อเสีย**:
- ไม่รองรับ comments
- ไม่มี type checking

---

### 5. Environment Variables (Direct) - Alternative

**ไม่ใช้ไฟล์** - ตั้งค่าผ่าน environment variables โดยตรง

**รูปแบบ**:
```bash
export RABBITMQ_HOST=178.128.105.100
export RABBITMQ_PORT=5672
export GPU_CONCURRENCY=2
```

**ใช้งาน**:
- ใช้ `os.getenv()` ใน code โดยตรง
- ไม่ต้องมีไฟล์ config

**ข้อดี**:
- ปลอดภัย (ไม่มีไฟล์ config ที่ต้องจัดการ)
- ใช้กับ Docker/Container ได้ดี
- ไม่ต้องจัดการไฟล์

**ข้อเสีย**:
- ยากต่อการจัดการค่าหลายค่า
- ไม่สะดวกในการ development

---

## การเลือกใช้ Configuration Format

### สำหรับ Development
- **แนะนำ**: `.env.runpod` (ง่ายต่อการแก้ไข)
- **Alternative**: Python config (ถ้าต้องการ type safety)

### สำหรับ Production
- **แนะนำ**: Environment Variables (Direct) - ปลอดภัยที่สุด
- **Alternative**: `.env.runpod` หรือ YAML (ถ้าต้องการ centralize config)

### สำหรับ Testing
- **แนะนำ**: Python config (สามารถ override ได้ง่าย)
- **Alternative**: JSON config (ง่ายต่อการ generate programmatically)

---

## Configuration Priority

ถ้าใช้หลายรูปแบบพร้อมกัน ลำดับความสำคัญ:

1. **Environment Variables (Direct)** - สูงสุด
2. **Config File** (`.env`, `.py`, `.yaml`, `.json`) - ถ้าไม่มี env vars
3. **Default Values** ใน code - ต่ำสุด

---

## Environment Variables สำหรับ Stuck Tasks Fix

ตัวแปรที่ต้องเพิ่มใน config:

```bash
# Task Timeout
TASK_TIMEOUT_SECONDS=1800                    # Default timeout (30 min)
TRANSCRIPTION_TASK_TIMEOUT_SECONDS=3600      # Transcription timeout (1 hour)
TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS=1800  # Processing timeout (30 min)

# Stuck Task Detection
STUCK_TASK_THRESHOLD_SECONDS=600             # Stuck threshold (10 min)
STUCK_TASK_CHECK_INTERVAL_SECONDS=60         # Check interval (1 min)
```

---

## ตัวอย่างการใช้งาน

### ใช้ .env file (Current)
```bash
# Load from .env.runpod
source .env.runpod
python -m app.workers.video_worker
```

### ใช้ Python config
```python
from config.worker_config import (
    RABBITMQ_HOST, 
    GPU_CONCURRENCY,
    STUCK_TASK_THRESHOLD_SECONDS
)
```

### ใช้ YAML config
```python
import yaml
with open('config/worker_config.yaml') as f:
    config = yaml.safe_load(f)
```

### ใช้ Environment Variables Direct
```bash
export RABBITMQ_HOST=178.128.105.100
export GPU_CONCURRENCY=2
python -m app.workers.video_worker
```

---

## Migration Guide

### จาก .env ไป Python config

1. สร้าง `config/worker_config.py`
2. Copy values จาก `.env.runpod`
3. แปลงเป็น Python variables
4. Update code ให้ import จาก config module

### จาก .env ไป YAML

1. สร้าง `config/worker_config.yaml`
2. แปลง .env เป็น YAML structure
3. Update code ให้ load YAML file

---

## หมายเหตุ

- **ปัจจุบันระบบใช้ `.env.runpod`** - ไม่ต้องเปลี่ยนถ้าไม่ต้องการ
- **Python config และ YAML config** เป็นทางเลือกเพิ่มเติม
- **Environment Variables (Direct)** ใช้ได้เสมอ และมี priority สูงสุด

