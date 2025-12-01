# 📋 Local Docker Testing - Summary

## ✅ สรุป Scripts ที่สร้างใหม่

### 🚀 Main Scripts

1. **`start-local.sh`** - Start services ใน Local Docker
   - ตรวจสอบ Docker และ container
   - Start services (Main API, Whisper API, Video Worker, Redis)
   - แสดงคำสั่งที่มีประโยชน์

2. **`stop-local.sh`** - Stop services ใน Local Docker
   - Stop services ภายใน container
   - ตัวเลือก: Stop container ด้วย (optional)

3. **`restart-local.sh`** - Restart services ใน Local Docker
   - Stop และ start services ใหม่

4. **`logs-local.sh`** - View logs ของ services
   - รองรับ: api, whisper, worker, redis, หรือ all
   - ดู logs จาก host (ไม่ต้องเข้า container)

5. **`test-local.sh`** - Test transcription
   - ทดสอบ transcription ด้วย video file
   - รองรับ parallel processing

## 🎯 Quick Start

```bash
# 1. Setup (ครั้งแรกเท่านั้น)
bash scripts/local/setup-local-direct.sh

# 2. Start services
bash scripts/local/start-local.sh

# 3. Test transcription
bash scripts/local/test-local.sh uploads/test.mp4 base 30

# 4. View logs
bash scripts/local/logs-local.sh worker

# 5. Check status
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-pod.sh'
```

## 📊 Parallel Processing Configuration

### Current Settings (ใน `docker-compose.local-direct.yml`)

```yaml
environment:
  - TRANSCRIPTION_MAX_WORKERS=5      # จำนวน workers
  - TRANSCRIPTION_PREFETCH_COUNT=20  # prefetch count
```

### Expected Behavior

1. **Chunks ถูกส่งไปยัง queue** → 23 chunks (สำหรับ 10-min video)
2. **Workers รับ chunks** → 5 workers ประมวลผล parallel
3. **Model Lock** → Transcription เป็น sequential (1 chunk ต่อครั้ง)
4. **Progress Update** → อัปเดตทุก 1 วินาที

## 🔍 Debugging Tips

### View Real-time Logs

```bash
# Worker logs (real-time)
docker exec -it transcription-local-base bash -c 'tail -f /tmp/video-worker.log'

# All logs (real-time)
docker exec -it transcription-local-base bash -c 'tail -f /tmp/*.log'
```

### Check Queue Status

```bash
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue'
```

### Check Services Status

```bash
docker exec -it transcription-local-base bash -c 'cd /workspace/transcription-service && bash scripts/pod/check-pod.sh'
```

## 📝 Next Steps

1. **ทดสอบ transcription** → `bash scripts/local/test-local.sh uploads/test.mp4 base`
2. **ตรวจสอบ logs** → `bash scripts/local/logs-local.sh worker`
3. **ตรวจสอบ queue** → `bash scripts/pod/check-rabbitmq-queue.sh transcription_chunk_queue`
4. **ดู results** → `bash scripts/pod/result-view.sh -detail 5`

## 🔗 Related Documentation

- `QUICK_START.md` - Quick Start Guide
- `LOCAL_DIRECT_MODE.md` - รายละเอียด Local Direct Mode
- `README.md` - รายละเอียด scripts ทั้งหมด

