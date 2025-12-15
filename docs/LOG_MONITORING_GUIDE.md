# Log Monitoring Guide

## 📋 Quick Check Commands

### 1. Check All Logs Status
```bash
# API Service
tail -50 /tmp/transcription-service.log

# Video Worker
tail -50 logs/video-worker.log

# Error Logs
tail -20 logs/api-service-errors.log
tail -20 logs/video-worker-errors.log
```

### 2. Check for Errors
```bash
# All errors
grep -iE "error|exception|traceback|failed|crash" /tmp/transcription-service.log | tail -20
grep -iE "error|exception|traceback|failed|crash" logs/video-worker.log | tail -20

# GPU errors
grep -iE "gpu|cuda|oom|out of memory|nvidia" logs/video-worker-errors.log

# Signal handling
grep -iE "signal|sigterm|sigint|shutdown" logs/video-worker.log | tail -10
```

### 3. Check Service Status
```bash
# Processes
ps aux | grep -E 'uvicorn|video_worker' | grep -v grep

# Health
curl -s http://localhost:8010/health | python3 -m json.tool

# GPU
nvidia-smi
```

### 4. Check Task Activity
```bash
# Recent tasks
tail -100 /tmp/transcription-service.log | grep -E 'transcribe|task' | tail -20

# Worker processing
tail -100 logs/video-worker.log | grep -E 'processing|transcribe' | tail -20
```

## 🔍 Common Issues to Check

### 1. Worker Not Processing
- Check: `grep -i "processing\|transcribe" logs/video-worker.log | tail -10`
- Issue: No processing activity
- Solution: Restart worker

### 2. GPU Not Used
- Check: `nvidia-smi` (utilization = 0%)
- Issue: GPU not being used
- Solution: Check device configuration, restart worker

### 3. Queue Full
- Check: `curl http://localhost:8010/api/queue/info`
- Issue: Queue at max capacity
- Solution: Wait or increase queue size

### 4. Connection Errors
- Check: `grep -i "connection\|rabbitmq" logs/*.log | tail -20`
- Issue: RabbitMQ connection lost
- Solution: Check RabbitMQ service, restart worker

### 5. GPU OOM
- Check: `grep -i "oom\|out of memory" logs/video-worker-errors.log`
- Issue: GPU memory exhausted
- Solution: Reduce GPU_CONCURRENCY, reduce batch_size

## 📊 Monitoring Script

```bash
#!/bin/bash
# Quick log check script

echo "=== Service Status ==="
ps aux | grep -E 'uvicorn|video_worker' | grep -v grep

echo ""
echo "=== Recent Errors ==="
tail -20 logs/api-service-errors.log 2>/dev/null | tail -5
tail -20 logs/video-worker-errors.log 2>/dev/null | tail -5

echo ""
echo "=== GPU Status ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

echo ""
echo "=== Recent Activity ==="
tail -10 logs/video-worker.log 2>/dev/null | tail -5
```

