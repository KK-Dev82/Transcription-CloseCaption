# Worker Monitor - Auto-restart Video Worker

## 📋 Overview

Worker Monitor เป็น service ที่ตรวจสอบและ auto-restart Video Worker เมื่อไม่ทำงาน เพื่อแก้ปัญหาที่ Video Worker หยุดทำงาน (ซึ่งเป็นสาเหตุหลัก 90% ของปัญหา)

## 🎯 เป้าหมาย

- **Auto-restart**: Restart Video Worker อัตโนมัติเมื่อไม่ทำงาน
- **Health Check**: ตรวจสอบ worker status และ queue consumers
- **Rate Limiting**: จำกัดจำนวนครั้งที่ restart ต่อชั่วโมง
- **No SSH Required**: ไม่ต้อง SSH เข้าไป restart เอง

## ⚙️ Configuration

```bash
# Enable/Disable Worker Monitor (default: true)
ENABLE_WORKER_MONITOR=true

# Check interval in seconds (default: 60)
WORKER_MONITOR_INTERVAL=60

# Max restart attempts per hour (default: 5)
WORKER_MONITOR_MAX_RESTARTS=5
```

## 🚀 Usage

Worker Monitor จะเริ่มทำงานอัตโนมัติเมื่อ API service start (ถ้า `ENABLE_WORKER_MONITOR=true`)

## 🔍 Troubleshooting

ตรวจสอบ logs:
```bash
tail -f logs/service.log | grep "Worker Monitor"
```
