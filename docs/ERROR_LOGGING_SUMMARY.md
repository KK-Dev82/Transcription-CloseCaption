# Error Logging Summary

## ✅ Implementation Complete

### 1. Main API Error Logging
- **Location**: `app/main.py`
- **Error Log**: `logs/api-service-errors.log` (ERROR level only)
- **Main Log**: `logs/api-service.log` (INFO+)
- **Features**:
  - Global exception handler
  - Signal handlers (SIGTERM, SIGINT)
  - Resource monitoring
  - Full traceback logging

### 2. Video Worker Error Logging
- **Location**: `app/workers/async/video_worker.py`
- **Error Log**: `logs/video-worker-errors.log` (ERROR level only)
- **Main Log**: `logs/video-worker.log` (INFO+)
- **Features**:
  - Enhanced signal handler
  - Resource usage logging before shutdown
  - GPU error detection
  - Full traceback logging

### 3. Transcription GPU Error Detection
- **Location**: `app/services/whisper_providers/faster_whisper_provider.py`
- **Features**:
  - CUDA/OOM error detection
  - GPU-related error logging
  - Automatic error classification

## 📁 Log File Structure

```
logs/
├── api-service.log              # Main API log (INFO+)
├── api-service-errors.log       # API errors only (ERROR+)
├── video-worker.log             # Main worker log (INFO+)
└── video-worker-errors.log      # Worker errors only (ERROR+)
```

## 🔍 Error Detection

### GPU-Related Errors
**Keywords**: `cuda`, `gpu`, `out of memory`, `oom`, `nvidia`, `cudnn`

**Detection**:
- Automatic in transcription provider
- Logged with `🚨 GPU-related error detected!`
- Full traceback included

### Signal Handling
- **SIGTERM**: Process killed by system/user
  - Possible causes: OOM killer, manual kill, system shutdown
- **SIGINT**: Process interrupted
  - Possible causes: Ctrl+C, manual interrupt
- **SIGKILL**: Force killed
  - Possible causes: OOM killer, system crash, manual kill -9

## 📊 Resource Monitoring

### Before Shutdown
- Memory usage (RSS, VMS)
- Process information
- Signal source

### During Transcription
- GPU memory usage
- GPU utilization
- CUDA errors
- Processing time

## 🚨 GPU Overload Detection

### Symptoms
1. High GPU utilization (98%+) with low VRAM (9%)
2. Worker crashes during transcription
3. CUDA out of memory errors
4. Process killed by OOM killer

### Monitoring
```bash
# Check GPU usage
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

# Check worker errors
grep -i "gpu\|cuda\|oom\|out of memory" logs/video-worker-errors.log

# Check system logs
dmesg | grep -i "killed\|oom"
```

## 💡 Usage

### View Error Logs
```bash
# Worker errors
tail -f logs/video-worker-errors.log

# API errors
tail -f logs/api-service-errors.log

# All errors
grep -r "ERROR" logs/*.log | tail -20
```

### Monitor GPU Issues
```bash
# Check for GPU errors
grep -i "gpu\|cuda\|oom" logs/video-worker-errors.log

# Check worker crashes
grep -i "fatal\|crash\|signal" logs/video-worker-errors.log

# Check transcription errors
grep -i "transcription\|whisper" logs/video-worker-errors.log
```

## 🔄 Next Steps

1. ✅ Error logging implemented
2. ⚠️ Monitor error logs in production
3. ⚠️ Set up alerts for critical errors
4. ⚠️ Analyze error patterns
5. ⚠️ Implement automatic recovery

