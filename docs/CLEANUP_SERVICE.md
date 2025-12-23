# Cleanup Service Documentation

## ภาพรวม

ระบบมี cleanup mechanism หลายระดับเพื่อป้องกัน memory leak และ disk space issues:

1. **TTL (Time To Live)** - Redis keys มี TTL อัตโนมัติ
2. **Periodic Cleanup** - Cleanup service รันทุก 1 ชั่วโมง (configurable)
3. **Startup Cleanup** - Cleanup ตอน API startup
4. **Standalone Cleanup Service** - สำหรับ deployment แยก process

## Timestamp ใน Transcription Result

**คำตอบ: ใช่, ระบบเก็บ timestamp ครบถ้วน**

เมื่อ merge chunk แล้ว ข้อมูล timestamp ยังคงอยู่ใน storage:

- `created_at` - เวลาที่สร้าง task
- `start_time` - เวลาเริ่มต้น (alias ของ created_at)
- `completed_at` - เวลาที่เสร็จสิ้น
- `updated_at` - เวลาที่อัปเดตล่าสุด
- `processing_time` / `result_time` - เวลาที่ใช้ในการประมวลผล (วินาที)
- `transcription_time` - เวลาที่ใช้ในการ transcription (วินาที)

สำหรับ chunks แต่ละ chunk มี:
- `start_time` - เวลาเริ่มต้นของ chunk (วินาที)
- `end_time` - เวลาสิ้นสุดของ chunk (วินาที)

ข้อมูลทั้งหมดถูกเก็บใน `storage/transcriptions/{task_id}/metadata.json` และสามารถใช้สำหรับระบบค้นหาได้

## TTL Configuration

### Redis Chunk Keys TTL
- **Default**: 12 hours (43200 seconds)
- **Environment Variable**: `REDIS_CHUNK_TTL_SECONDS`
- **Keys ที่มี TTL**:
  - `task:{task_id}:chunk_jobs`
  - `task:{task_id}:total_chunks`
  - `task:{task_id}:done_chunks`
  - `task:{task_id}:chunk:{index}`
  - `task:{task_id}:aggregator_triggered`

### RQ Job Result TTL
- **Default**: 12 hours (43200 seconds)
- **Environment Variable**: `RQ_DEFAULT_RESULT_TTL`
- **Applied to**: All queues (GPU, CPU, Preprocess, Priority)

### Cleanup Max Age
- **Default**: 12 hours
- **Environment Variable**: `REDIS_CLEANUP_MAX_AGE_HOURS`
- **Applied to**: Finished/Failed jobs cleanup

## Cleanup Mechanisms

### 1. Automatic Cleanup หลัง Aggregator เสร็จ

หลัง aggregator merge chunks เสร็จแล้ว จะลบ Redis keys ทันที:
- `task:{task_id}:chunk:{index}` (ทุก chunk)
- `task:{task_id}:done_chunks`
- `task:{task_id}:total_chunks`
- `task:{task_id}:chunk_jobs`
- `task:{task_id}:aggregator_triggered`

**ผลลัพธ์**: ลด memory usage ทันที แทนรอ TTL 12 ชั่วโมง

### 2. FastAPI Startup Cleanup

เมื่อ FastAPI เริ่มทำงาน:
- Cleanup temp folders เก่า (>24 hours)
- Cleanup Redis finished/failed jobs เก่า (>12 hours)

**ข้อจำกัด**: ถ้า deploy แยก process (API vs RQ worker) และมีแค่ worker รันโดยไม่มี FastAPI, cleanup จะไม่ทำงาน

### 3. Periodic Cleanup (ใน FastAPI)

รันทุก 1 ชั่วโมง (configurable via `CLEANUP_INTERVAL_SECONDS`):
- Cleanup temp folders
- Cleanup Redis finished/failed jobs
- Check disk space

**ข้อจำกัด**: เหมือน startup cleanup - ต้องมี FastAPI process

### 4. Standalone Cleanup Service

**สำหรับ deployment แยก process**

รัน cleanup service แยกจาก API:

```bash
# วิธีที่ 1: ใช้ Python module
python -m scripts.cleanup_service_standalone

# วิธีที่ 2: ใช้ script โดยตรง
python scripts/cleanup_service_standalone.py

# วิธีที่ 3: ใช้ systemd service (แนะนำ)
# สร้างไฟล์ /etc/systemd/system/transcription-cleanup.service
```

**Systemd Service Example**:

```ini
[Unit]
Description=Transcription Service Cleanup
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/workspace/transcription-service
Environment="PYTHONPATH=/workspace/transcription-service"
ExecStart=/usr/bin/python3 -m scripts.cleanup_service_standalone
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable service**:
```bash
sudo systemctl enable transcription-cleanup
sudo systemctl start transcription-cleanup
sudo systemctl status transcription-cleanup
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_CHUNK_TTL_SECONDS` | 43200 (12h) | TTL สำหรับ Redis chunk keys |
| `RQ_DEFAULT_RESULT_TTL` | 43200 (12h) | TTL สำหรับ RQ job results |
| `REDIS_CLEANUP_MAX_AGE_HOURS` | 12 | อายุสูงสุดของ jobs ก่อน cleanup |
| `CLEANUP_INTERVAL_SECONDS` | 3600 (1h) | Interval สำหรับ periodic cleanup |
| `TEMP_FOLDER_MAX_AGE_HOURS` | 24 | อายุสูงสุดของ temp folders |

## Monitoring

ใช้ `/api/monitoring/` endpoint เพื่อตรวจสอบ:
- Redis memory และ key count
- Queue depth (queued, started, finished, failed)
- System resources (CPU, RAM, GPU)

**Alert Thresholds** (แนะนำ):
- Redis memory > 100 MB
- Keys without TTL > 500
- Finished jobs > 1000
- Failed jobs > 100

## Best Practices

1. **สำหรับ Production**:
   - ใช้ standalone cleanup service (systemd)
   - ตั้ง alert บน Redis memory/key count
   - Monitor queue depth

2. **สำหรับ Development**:
   - ใช้ FastAPI startup cleanup (ง่ายกว่า)
   - Monitor logs สำหรับ cleanup errors

3. **สำหรับ High Load (50+ jobs/day)**:
   - ลด TTL เป็น 6-8 hours (ถ้าไม่ต้อง retry นาน)
   - เพิ่ม cleanup frequency (ทุก 30 นาที)
   - ตั้ง alert ที่ aggressive กว่า

## Troubleshooting

### Problem: Redis memory เพิ่มขึ้นเรื่อยๆ

**สาเหตุ**:
- Cleanup service ไม่ทำงาน
- Keys ไม่มี TTL
- Jobs เก่าไม่ถูกลบ

**แก้ไข**:
1. ตรวจสอบว่า cleanup service ทำงาน: `ps aux | grep cleanup`
2. ตรวจสอบ Redis keys: `/api/monitoring/redis`
3. เริ่ม standalone cleanup service

### Problem: Temp folders ค้าง

**สาเหตุ**:
- Cleanup service ไม่ทำงาน
- Disk space ไม่พอ

**แก้ไข**:
1. รัน manual cleanup: `python -c "from app.services.cleanup_service import cleanup_service; import asyncio; asyncio.run(cleanup_service.cleanup_on_startup())"`
2. ตรวจสอบ disk space: `/api/monitoring/system`

## Summary

- ✅ **Timestamp ถูกเก็บครบถ้วน** - ใช้สำหรับระบบค้นหาได้
- ✅ **TTL ลดเหลือ 12 hours** - เหมาะกับ use-case 50 งาน/วัน
- ✅ **Cleanup หลัง aggregator** - ลด memory ทันที
- ✅ **Standalone cleanup service** - ทำงานได้แม้ไม่มี FastAPI
- ✅ **Monitoring endpoint** - ตรวจสอบสถานะได้ง่าย


