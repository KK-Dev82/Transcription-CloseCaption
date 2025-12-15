# API Service Logging Improvements

## 📋 Overview

เอกสารนี้อธิบายการปรับปรุงระบบ logging และ error handling สำหรับ API Service เพื่อช่วยในการวินิจฉัยปัญหาเมื่อ service crash หรือเกิด error

## 🔧 การปรับปรุงที่ทำ

### 1. Global Exception Handler

เพิ่ม global exception handler เพื่อจับ unhandled exceptions ทั้งหมด:

- **Location:** `app/main.py`
- **Features:**
  - จับทุก exception ที่ไม่ถูก handle
  - Log ข้อมูลละเอียด: error type, message, path, method, query params, traceback
  - บันทึกไปยัง error log file แยก (`logs/api-service-errors.log`)
  - Return JSON response ที่เป็นมาตรฐาน

### 2. Signal Handlers

เพิ่ม signal handlers เพื่อ log เมื่อ process ถูก kill:

- **Signals:** `SIGTERM`, `SIGINT`
- **Features:**
  - Log signal ที่ได้รับ
  - Log stack trace เมื่อ process ถูก terminate
  - ช่วยระบุสาเหตุที่ service หยุดทำงาน

### 3. Enhanced Logging Configuration

ปรับปรุง logging configuration:

- **File Handlers:**
  - `logs/api-service.log` - ทุก log messages
  - `logs/api-service-errors.log` - เฉพาะ error และ critical messages
- **Format:**
  - เพิ่ม filename และ line number ใน log format
  - Timestamp สำหรับทุก log entry
- **Uncaught Exception Handler:**
  - จับ exceptions ที่ไม่ถูก catch ใน main thread
  - Log ไปยัง error log file

### 4. Resource Monitoring

เพิ่ม periodic resource monitoring:

- **Interval:** ทุก 5 นาที
- **Metrics:**
  - Memory usage (RSS, percentage)
  - CPU usage
  - Thread count
  - File descriptor count
- **Dependencies:** `psutil` (optional, จะ skip ถ้าไม่มี)

### 5. Startup/Shutdown Logging

เพิ่ม detailed logging ใน startup และ shutdown:

- **Startup:**
  - Process ID
  - Python version
  - Working directory
  - Log file paths
  - Initial resource usage
- **Shutdown:**
  - Final resource usage
  - Graceful cleanup logging

### 6. HTTP Exception Handlers

เพิ่ม exception handlers สำหรับ HTTP errors:

- **HTTPException:** Log warning สำหรับ HTTP errors
- **RequestValidationError:** Log validation errors พร้อม details

## 📁 Log Files

### `logs/api-service.log`
- ทุก log messages (INFO, WARNING, ERROR, CRITICAL)
- Format: `%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s`

### `logs/api-service-errors.log`
- เฉพาะ ERROR และ CRITICAL messages
- รวม unhandled exceptions พร้อม full traceback
- Format เดียวกับ `api-service.log`

## 🔍 วิธีใช้งาน

### 1. ตรวจสอบ Logs

```bash
# ดู logs ทั้งหมด
tail -f logs/api-service.log

# ดู error logs เฉพาะ
tail -f logs/api-service-errors.log

# ดู error logs ล่าสุด
tail -100 logs/api-service-errors.log
```

### 2. ค้นหา Errors

```bash
# ค้นหา CRITICAL errors
grep "CRITICAL" logs/api-service-errors.log

# ค้นหา unhandled exceptions
grep "UNHANDLED EXCEPTION" logs/api-service-errors.log

# ค้นหา errors ในช่วงเวลาหนึ่ง
grep "2024-01-15" logs/api-service-errors.log
```

### 3. Monitor Script

Monitor script (`scripts/pod/monitor-api-service.sh`) จะตรวจสอบ:
- Service process status
- Port listening status
- Health endpoint response
- Log files (รวม error log)

## 🐛 Debugging Tips

### เมื่อ Service Crash

1. **ตรวจสอบ error log:**
   ```bash
   tail -50 logs/api-service-errors.log
   ```

2. **ตรวจสอบ signal handlers:**
   - ดู log สำหรับ `SIGTERM` หรือ `SIGINT`
   - ตรวจสอบว่า process ถูก kill โดยใคร

3. **ตรวจสอบ resource usage:**
   - ดู resource monitoring logs ใน `api-service.log`
   - ตรวจสอบ memory leaks หรือ resource exhaustion

4. **ตรวจสอบ unhandled exceptions:**
   - ดู `UNHANDLED EXCEPTION` ใน error log
   - ตรวจสอบ full traceback เพื่อหาสาเหตุ

### เมื่อ Service ไม่ตอบสนอง

1. **ตรวจสอบ health endpoint:**
   ```bash
   curl http://localhost:8010/health
   ```

2. **ตรวจสอบ process status:**
   ```bash
   ps aux | grep uvicorn
   ```

3. **ตรวจสอบ logs:**
   ```bash
   tail -f logs/api-service.log
   ```

## 📊 Resource Monitoring

Resource monitoring จะ log ทุก 5 นาที:

```
📊 Resource Usage - Memory: 512.34 MB (25.5%), CPU: 15.2%, Threads: 8, FDs: 42
```

### Metrics ที่ติดตาม:
- **Memory (RSS):** Physical memory ที่ใช้
- **Memory (%):** เปอร์เซ็นต์ของ total memory
- **CPU (%):** CPU usage percentage
- **Threads:** จำนวน active threads
- **FDs:** จำนวน file descriptors (ถ้า available)

## ⚠️ ข้อควรระวัง

1. **Log File Size:**
   - Log files อาจเติบโตขึ้นเรื่อยๆ
   - ควรตั้งค่า log rotation (ใช้ `logrotate` หรือ similar)
   - Monitor disk space

2. **Performance Impact:**
   - Resource monitoring ใช้ CPU เล็กน้อย
   - Exception handling เพิ่ม overhead เล็กน้อย
   - ควร monitor performance impact

3. **Dependencies:**
   - `psutil` เป็น optional dependency
   - Service จะทำงานได้แม้ไม่มี `psutil` (แต่จะไม่มี resource monitoring)

## 🔄 Next Steps

1. **Log Rotation:**
   - ตั้งค่า log rotation เพื่อป้องกัน disk space issues
   - เก็บ logs เก่าไว้สำหรับ analysis

2. **Alerting:**
   - ตั้งค่า alerting เมื่อมี CRITICAL errors
   - Monitor error rate และ response time

3. **Metrics Collection:**
   - ส่ง metrics ไปยัง monitoring system (Prometheus, etc.)
   - Track error rates, response times, resource usage

## 📝 Example Log Output

### Normal Operation
```
2024-01-15 10:30:00 - app.main - INFO - [main.py:600] - ✅ API Server พร้อมใช้งาน
2024-01-15 10:35:00 - app.main - INFO - [main.py:XXX] - 📊 Resource Usage - Memory: 512.34 MB (25.5%), CPU: 15.2%, Threads: 8, FDs: 42
```

### Error
```
2024-01-15 10:40:00 - app.main - ERROR - [transcription.py:87] - Error getting task abc123 status: Traceback...
```

### Critical/Unhandled Exception
```
2024-01-15 10:45:00 - app.main - CRITICAL - [main.py:XXX] - 💥 UNHANDLED EXCEPTION: ValueError: Invalid task_id
Path: GET /transcribe/abc123
Traceback:
  File "app/api/transcription.py", line 70, in get_transcription_status
    ...
```

## 🎯 Summary

การปรับปรุงเหล่านี้จะช่วยให้:
- ✅ จับและ log ทุก error ที่เกิดขึ้น
- ✅ ระบุสาเหตุที่ service crash ได้ง่ายขึ้น
- ✅ Monitor resource usage เพื่อป้องกัน resource exhaustion
- ✅ Track errors และ exceptions อย่างละเอียด
- ✅ Debug ปัญหาได้เร็วขึ้น

