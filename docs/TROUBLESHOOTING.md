# 🔧 Troubleshooting Guide

## ❌ 502 Bad Gateway

### สาเหตุที่เป็นไปได้

1. **API Server ไม่ได้รัน**
   ```bash
   # ตรวจสอบ
   ps aux | grep uvicorn
   
   # Start API
   bash scripts/start-api-nohup.sh
   ```

2. **Port ถูกใช้อยู่แล้ว**
   ```bash
   # ตรวจสอบ
   lsof -i :8001
   
   # Kill process
   kill $(lsof -t -i:8001)
   ```

3. **Import Errors**
   ```bash
   # ตรวจสอบ
   python3 -c "from app.main import app"
   
   # แก้ไข import errors
   ```

4. **Proxy Configuration**
   - ตรวจสอบว่า RunPod proxy ชี้ไปยัง port ที่ถูกต้อง
   - 8010 → 8001 (API)
   - 8020 → 8002 (Webhook)
   - 8030 → 8003 (Monitoring)

### วิธีแก้ไข

1. **Restart API Server**
   ```bash
   bash scripts/stop-all.sh
   bash scripts/start-api-nohup.sh
   ```

2. **ตรวจสอบ Logs**
   ```bash
   tail -f logs/api.log
   tail -f logs/api-error.log
   ```

3. **ทดสอบ Health Check**
   ```bash
   curl http://localhost:8001/health
   ```

4. **ตรวจสอบ Routes**
   ```bash
   curl http://localhost:8001/docs
   ```

---

## ❌ Upload File Error

### ปัญหา: 502 Bad Gateway เมื่อ Upload

**สาเหตุ:**
- API server crash
- FileService methods ไม่มี
- Import errors

**วิธีแก้ไข:**

1. **ตรวจสอบ FileService**
   ```python
   from app.services.file_service import FileService
   fs = FileService()
   # ตรวจสอบ methods: save_uploaded_file, get_file_info
   ```

2. **ตรวจสอบ Upload Endpoint**
   ```bash
   curl -X POST http://localhost:8001/api/upload/ \
     -F 'file=@test.mp4'
   ```

3. **ตรวจสอบ Logs**
   ```bash
   tail -f logs/api-error.log
   ```

---

## ✅ Checklist

- [ ] API Server รันอยู่ (`ps aux | grep uvicorn`)
- [ ] Port 8001 เปิดอยู่ (`netstat -tuln | grep 8001`)
- [ ] Health check ผ่าน (`curl http://localhost:8001/health`)
- [ ] ไม่มี import errors (`python3 -c "from app.main import app"`)
- [ ] FileService มี methods (`save_uploaded_file`, `get_file_info`)
- [ ] Uploads directory มีอยู่ (`ls -la uploads/`)

---

## 🔍 Debug Commands

```bash
# Check API status
curl http://localhost:8001/health

# Check API docs
curl http://localhost:8001/docs

# Check upload endpoint
curl -X POST http://localhost:8001/api/upload/ -F 'file=@test.mp4'

# Check logs
tail -f logs/api.log
tail -f logs/api-error.log

# Check processes
ps aux | grep -E "(uvicorn|python)"
```

