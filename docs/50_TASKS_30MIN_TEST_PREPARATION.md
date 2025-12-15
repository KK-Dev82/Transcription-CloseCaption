# 50 Tasks x 30-Minute Video Test Preparation

## 📋 Test Scenario

- **Tasks**: 50 concurrent transcription tasks
- **Video Length**: 30 minutes per video
- **Total Processing Time**: ~8-10 hours (estimated)

## ✅ Pre-Test Checklist

### 1. FFmpeg Installation
```bash
ssh -p 13263 4000-ada-sc
cd /workspace/transcription-service
apt-get update && apt-get install -y ffmpeg
which ffmpeg  # Should show /usr/bin/ffmpeg
```

### 2. System Configuration

#### Queue Limits
- `MAX_QUEUE_REQUEST=51` ✅ (50 video + 1 close caption)
- `MAX_QUEUE_EXTRACTION=80` ✅
- `MAX_QUEUE_TRANSCRIBE=20` ✅

#### GPU & Concurrency
- `GPU_CONCURRENCY=2` ✅ (2 concurrent GPU tasks)
- `TRANSCRIPTION_MAX_WORKERS=5` ✅
- `WHISPER_MODEL=medium` ✅

#### Storage
- `STORAGE_TYPE=sqlite` ✅
- `SAVE_TEMP_FILES=not_save` ✅ (save disk space)

### 3. Service Status

#### Check API Service
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

#### Check Video Worker
```bash
ps aux | grep video_worker
# Should show worker process
```

#### Check RabbitMQ Queues
```bash
# Via API
curl http://localhost:8000/api/queue/status
```

### 4. Resource Monitoring

#### GPU Usage
```bash
nvidia-smi
# Monitor GPU utilization and VRAM
```

#### Disk Space
```bash
df -h /workspace
# Ensure sufficient space for 50 x 30-min videos
```

#### Memory
```bash
free -h
# Monitor available memory
```

## 📊 Expected Performance

### Per Task Processing Time
- **Audio Extraction**: ~2-3 minutes
- **Transcription**: ~15-20 minutes (30-min video)
- **Total**: ~18-23 minutes per task

### Throughput
- **GPU Concurrency**: 2 tasks
- **Throughput**: 2 tasks / 23 minutes = ~5.2 tasks/hour
- **50 Tasks**: ~9.6 hours ✅

### Queue Flow
1. **Request Queue** (max 51): Accepts all 50 tasks
2. **Extraction Queue** (max 80): Processes audio extraction
3. **Transcription Queue** (max 20): Processes transcription with GPU

## 🚀 Test Execution

### 1. Send 50 Tasks
```bash
# Via Dashboard Test Tab
# Or via API script
python scripts/test/send_50_tasks.py
```

### 2. Monitor Progress
```bash
# Dashboard Overview Tab
# Or via API
curl http://localhost:8000/api/queue/status
```

### 3. Check Logs
```bash
# API Service Logs
tail -f logs/api-service.log

# Video Worker Logs
tail -f logs/video-worker.log

# Error Logs
tail -f logs/api-service-errors.log
tail -f logs/video-worker-errors.log
```

## ⚠️ Potential Issues & Solutions

### Issue 1: Queue Full (503 Error)
**Symptom**: API returns 503 Service Unavailable
**Solution**: 
- Check queue status: `curl http://localhost:8000/api/queue/status`
- Wait for queue to process
- Retry with `Retry-After` header

### Issue 2: GPU Out of Memory
**Symptom**: GPU OOM errors in logs
**Solution**:
- Reduce `GPU_CONCURRENCY` to 1
- Check VRAM usage: `nvidia-smi`
- Consider using smaller model

### Issue 3: Disk Space Full
**Symptom**: Storage errors
**Solution**:
- Clean up old files: `bash scripts/pod/cleanup-storage.sh`
- Check disk usage: `df -h /workspace`
- Increase storage if needed

### Issue 4: Tasks Stuck
**Symptom**: Tasks not progressing
**Solution**:
- Check worker status: `ps aux | grep video_worker`
- Check RabbitMQ consumers: `curl http://localhost:8000/api/queue/status`
- Restart worker if needed: `bash scripts/pod/restart-service-daemon.sh`

## 📈 Monitoring Metrics

### Key Metrics to Track
1. **Queue Sizes**: Request, Extraction, Transcription
2. **GPU Utilization**: Should be ~90-100%
3. **GPU VRAM**: Should be < 16GB
4. **Processing Rate**: Tasks completed per hour
5. **Error Rate**: Failed tasks / Total tasks
6. **Average Processing Time**: Per task

### Dashboard Monitoring
- **Overview Tab**: Task status summary
- **Monitoring Tab**: Real-time progress
- **Test Tab**: Batch test results

## ✅ Success Criteria

1. ✅ All 50 tasks accepted (no 503 errors)
2. ✅ All tasks completed successfully
3. ✅ Average processing time < 25 minutes per task
4. ✅ No GPU OOM errors
5. ✅ No disk space issues
6. ✅ System stable for 8-10 hours

## 📝 Post-Test Analysis

### Check Results
```bash
# Count completed tasks
sqlite3 storage/database.db "SELECT COUNT(*) FROM transcriptions WHERE status='completed';"

# Check failed tasks
sqlite3 storage/database.db "SELECT COUNT(*) FROM transcriptions WHERE status='failed';"

# Average processing time
sqlite3 storage/database.db "SELECT AVG(julianday(completed_at) - julianday(created_at)) * 24 * 60 FROM transcriptions WHERE status='completed';"
```

### Review Logs
- Check for errors: `grep -i error logs/*.log`
- Check for warnings: `grep -i warning logs/*.log`
- Check GPU usage: `grep -i gpu logs/*.log`

## 🔧 Troubleshooting Commands

```bash
# Restart services
bash scripts/pod/restart-service-daemon.sh

# Check service health
curl http://localhost:8000/health

# Check queue status
curl http://localhost:8000/api/queue/status

# Purge queues (if needed)
curl -X POST http://localhost:8000/api/queue/purge/transcription_request_queue

# Check FFmpeg
which ffmpeg && ffmpeg -version

# Check GPU
nvidia-smi

# Check disk space
df -h /workspace
```

## 📚 Related Documentation

- `docs/PRODUCTION_CAPACITY_ANALYSIS.md` - Capacity analysis
- `docs/QUEUE_ARCHITECTURE_FINAL.md` - Queue architecture
- `docs/API_QUESTIONS_ANSWERS.md` - Resource management
- `docs/STABILITY_ANALYSIS_50_QUEUES.md` - Stability analysis

