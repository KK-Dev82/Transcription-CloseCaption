# Dashboard Internal Port Configuration

## ภาพรวม

Dashboard สามารถใช้ **internal port** (localhost:8010) แทน **external port** (เช่น 13264, 15267) เมื่อทำงานบน Pod เดียวกันกับ Transcription Service

## การใช้งาน

### วิธีที่ 1: ใช้ Environment Variable

```bash
export USE_INTERNAL_PORT=true
export INTERNAL_API_PORT=8010  # optional, default: 8010
cd dashboard
python3 -m uvicorn main:app --host 0.0.0.0 --port 8020
```

### วิธีที่ 2: ใช้ใน .env.runpod

เพิ่มใน `.env.runpod`:
```bash
USE_INTERNAL_PORT=true
INTERNAL_API_PORT=8010
```

### วิธีที่ 3: ใช้ใน run.sh

แก้ไข `dashboard/run.sh`:
```bash
export USE_INTERNAL_PORT=true
export INTERNAL_API_PORT=8010
python main.py
```

## ผลลัพธ์

เมื่อ `USE_INTERNAL_PORT=true`:
- Dashboard จะใช้ `http://localhost:8010` สำหรับทุก servers
- ไม่ต้องใช้ external port mapping
- เร็วกว่าและเสถียรกว่า (ไม่ต้องผ่าน network)

## ตรวจสอบ

```bash
# ตรวจสอบว่า Dashboard ใช้ internal port หรือไม่
curl http://localhost:8020/api/server/4000-ada-sc/status

# ดู logs
tail -f /tmp/dashboard.log | grep -i "internal"
```

## หมายเหตุ

- Internal port ใช้ได้เฉพาะเมื่อ Dashboard และ Transcription Service ทำงานบน Pod เดียวกัน
- ถ้า Dashboard ทำงานบนเครื่องอื่น ต้องใช้ external port
- Default: `USE_INTERNAL_PORT=false` (ใช้ external port)

