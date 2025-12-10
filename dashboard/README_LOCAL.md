# Dashboard - Local macOS Setup

## การรัน Dashboard บน macOS Local

Dashboard นี้ใช้สำหรับ monitor และควบคุม Transcription Service ที่รันอยู่บน Pod servers (4000-ada และ 5080)

### 🚀 Quick Start

```bash
cd dashboard
bash start-local.sh
```

หรือ

```bash
cd dashboard
bash run.sh
```

### 📋 Requirements

- Python 3.8+
- macOS (หรือ Linux/Windows)

### 📦 Installation

1. **สร้าง virtual environment (ถ้ายังไม่มี)**
   ```bash
   cd dashboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **รัน Dashboard**
   ```bash
   bash start-local.sh
   ```

3. **เปิด Browser**
   ```
   http://localhost:8020
   ```

### 🔧 Configuration

Dashboard จะเชื่อมต่อไปยัง remote servers:
- **4000-ada**: `http://87.197.119.40:40112`
- **5080**: `http://213.144.200.206:15267`

Configuration อยู่ใน `config.py` หรือสามารถ override ด้วย environment variables:
- `SERVER_4000ADA_URL`
- `SERVER_5080_URL`

### 📊 Features

1. **Overview Tab**
   - Monitor tasks จากทั้ง 4000-ada และ 5080
   - Filter tasks by status
   - Clear pending tasks
   - Delete old tasks (with progress tracking)

2. **Test Tab**
   - Send batch transcription tasks
   - Monitor test progress
   - View transcribed results

### 🐛 Troubleshooting

**API 404 Error:**
- ตรวจสอบว่า routes ถูก include แล้ว: `main.py` ต้อง include `cleanup_routes.router`
- ตรวจสอบว่า remote server URLs ถูกต้องใน `config.py`

**Import Error:**
- ใช้ `uvicorn main:app` แทน `python main.py` เพื่อให้ relative imports ทำงาน
- หรือรันผ่าน script: `bash start-local.sh`

**Timeout Errors:**
- ตรวจสอบว่า remote servers (4000-ada, 5080) พร้อมใช้งาน
- เพิ่ม timeout ใน `api-client.js` ถ้าจำเป็น

### 🔍 Verify Routes

ตรวจสอบว่า routes ถูก register แล้ว:
```bash
cd dashboard
source venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '.')
from main import app
routes = [(r.path, list(r.methods)) for r in app.routes if hasattr(r, 'path')]
for path, methods in sorted(routes):
    if 'delete' in path or 'cleanup' in path:
        print(f'{methods} {path}')
"
```

ควรเห็น:
```
['POST'] /api/server/{server_name}/tasks/delete-old
['GET'] /api/cleanup/{cleanup_id}/progress
```

