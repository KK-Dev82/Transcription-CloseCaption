# 🐛 Debug Guide

คู่มือการ debug สำหรับ Transcription Service

## วิธีที่ 1: ใช้ VS Code Debugger (แนะนำ)

### Setup
1. เปิด VS Code
2. กด `F5` หรือไปที่ Run and Debug (Ctrl+Shift+D)
3. เลือก "Python: FastAPI (Port 8010)"
4. ตั้ง breakpoint ในโค้ดที่ต้องการ debug

### ข้อดี
- ✅ ใช้งานง่าย ไม่ต้องแก้โค้ด
- ✅ รองรับ breakpoint, step through, watch variables
- ✅ Auto-reload เมื่อแก้โค้ด

---

## วิธีที่ 2: ใช้ Debugpy (Remote Debugging)

เหมาะสำหรับกรณีที่รันใน Docker หรือ remote server

### Setup
1. ติดตั้ง debugpy:
```bash
pip install debugpy
```

2. รันด้วย debugpy:
```bash
DEBUG=true USE_DEBUGPY=true DEBUGPY_PORT=5678 python main.py
```

3. ใน VS Code:
   - เลือก "Python: FastAPI (Port 8010) - Debugpy Remote"
   - กด F5 เพื่อ attach

### Environment Variables
- `USE_DEBUGPY=true` - เปิดใช้งาน debugpy
- `DEBUGPY_PORT=5678` - Port สำหรับ debugpy (default: 5678)
- `DEBUGPY_WAIT=true` - รอให้ debugger attach ก่อนเริ่มรัน (optional)

---

## วิธีที่ 3: ใช้ Logging (Debug Mode)

### เปิด Debug Logging
```bash
DEBUG=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

หรือ
```bash
DEBUG=true python main.py
```

### ข้อดี
- ✅ เห็น log ทุกอย่างแบบละเอียด
- ✅ ไม่ต้อง setup อะไรเพิ่ม
- ✅ เหมาะสำหรับดู flow ของ request

---

## วิธีที่ 4: ใช้ pdb/ipdb (Breakpoint ในโค้ด)

### วิธีใช้
เพิ่ม breakpoint ในโค้ด:
```python
import pdb; pdb.set_trace()  # หรือ
import ipdb; ipdb.set_trace()  # ถ้าติดตั้ง ipdb แล้ว
```

### ติดตั้ง ipdb (แนะนำ - UI ดีกว่า pdb)
```bash
pip install ipdb
```

### ตัวอย่าง
```python
@app.post("/api/upload")
async def upload_file(file: UploadFile):
    import ipdb; ipdb.set_trace()  # Breakpoint ที่นี่
    # ... rest of code
```

---

## วิธีที่ 5: ใช้ uvicorn --log-level debug

### วิธีใช้
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010 --log-level debug
```

### ข้อดี
- ✅ เห็น HTTP request/response แบบละเอียด
- ✅ เห็น middleware processing
- ✅ เห็น ASGI events

---

## วิธีที่ 6: ใช้ Python Debugger ใน Terminal

### วิธีใช้
```bash
python -m pdb main.py
```

หรือ
```bash
python -m ipdb main.py
```

---

## 📝 Tips

### 1. ดู Logs แบบ Real-time
```bash
tail -f logs/*.log
```

### 2. Filter Logs
```bash
grep "ERROR" logs/*.log
```

### 3. ดู API Logs ผ่าน API
```bash
curl http://localhost:8010/api/logs
```

### 4. ใช้ Postman/Insomnia สำหรับ Test API
- Import collection จาก `examples/` folder
- Test endpoints พร้อมดู logs

---

## ⚠️ แก้ปัญหา Startup ค้าง

### อาการ: แอปค้างที่ "Waiting for application startup"

**สาเหตุ:** WebSocket initialization รอ Redis connection ที่ timeout หรือไม่พร้อม

### วิธีแก้

#### วิธีที่ 1: Skip WebSocket Initialization (เร็วที่สุด)
```bash
SKIP_WEBSOCKET=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

หรือ
```bash
SKIP_WEBSOCKET=true python main.py
```

#### วิธีที่ 2: ใช้ Mock Mode
```bash
TRANSCRIPTION_MOCK_MODE=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

#### วิธีที่ 3: ตรวจสอบ Redis Connection
```bash
# ตรวจสอบว่า Redis URL ถูกต้อง
echo $REDIS_URL

# หรือตรวจสอบใน .env.runpod
cat .env.runpod | grep REDIS_URL
```

#### วิธีที่ 4: ใช้ Debug Logging เพื่อดูว่าเกิดอะไรขึ้น
```bash
DEBUG=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

จะเห็น log แบบละเอียดว่า startup ค้างที่ไหน

### การปรับปรุงที่ทำไปแล้ว
- ✅ เพิ่ม timeout สั้นลง (10 วินาที แทน 30 วินาที)
- ✅ จำกัดจำนวน retry (3 ครั้ง)
- ✅ ถ้า timeout จะ skip websocket แต่ยังรันแอปได้
- ✅ เพิ่ม option `SKIP_WEBSOCKET` เพื่อข้าม websocket initialization

---

## 🔧 Environment Variables สำหรับ Debug

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | เปิด debug logging | `false` |
| `USE_DEBUGPY` | เปิด debugpy remote debugging | `false` |
| `DEBUGPY_PORT` | Port สำหรับ debugpy | `5678` |
| `DEBUGPY_WAIT` | รอ debugger attach | `false` |
| `SKIP_WEBSOCKET` | ข้าม WebSocket initialization | `false` |
| `TRANSCRIPTION_MOCK_MODE` | ใช้ Mock Mode (ข้าม websocket และ services) | `false` |

---

## 🚀 Quick Start

### Debug แบบง่ายที่สุด (VS Code)
1. เปิด VS Code
2. กด `F5`
3. ตั้ง breakpoint
4. Test API

### Debug แบบ Command Line
```bash
DEBUG=true python main.py
```

### Debug แบบ Remote (Docker)
```bash
DEBUG=true USE_DEBUGPY=true DEBUGPY_PORT=5678 python main.py
# แล้ว attach จาก VS Code
```

### แก้ปัญหา Startup ค้าง
```bash
# วิธีที่ 1: Skip WebSocket (เร็วที่สุด)
SKIP_WEBSOCKET=true python main.py

# วิธีที่ 2: ใช้ Mock Mode
TRANSCRIPTION_MOCK_MODE=true python main.py

# วิธีที่ 3: Debug เพื่อดูว่าเกิดอะไรขึ้น
DEBUG=true python main.py
```
