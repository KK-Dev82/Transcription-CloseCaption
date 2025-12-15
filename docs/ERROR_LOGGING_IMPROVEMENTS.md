# Error Logging Improvements

## 📋 Overview

เพิ่ม error logging แยกสำหรับ Main API, Video Worker, และ Transcription Process เพื่อช่วยในการ debug และ monitor

## 🔧 Implementation

### 1. Video Worker Error Logging

**Location**: `app/workers/async/video_worker.py`

**Changes**:
- ✅ Separate error log file: `logs/video-worker-errors.log`
- ✅ Main log file: `logs/video-worker.log`
- ✅ Console output: stdout
- ✅ Enhanced signal handler logging
- ✅ GPU error detection

**Error Log Format**:
```
%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s
%(pathname)s:%(lineno)d
%(funcName)s
%(exc_info)s
```

### 2. Main API Error Logging

**Location**: `app/main.py`

**Already Implemented**:
- ✅ Separate error log: `logs/api-service-errors.log`
- ✅ Main log: `logs/api-service.log`
- ✅ Global exception handler
- ✅ Signal handlers

### 3. Transcription Process Error Logging

**Location**: `app/services/whisper_providers/faster_whisper_provider.py`

**To Be Added**:
- GPU OOM error detection
- CUDA error handling
- Memory usage logging
- Transcription error tracking

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
- Keywords: `cuda`, `gpu`, `out of memory`, `oom`, `nvidia`, `cudnn`
- Detection: Automatic in worker exception handler
- Action: Logged with `🚨 GPU-related error detected!`

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
```python
# Check GPU usage
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv

# Check worker errors
grep -i "gpu\|cuda\|oom\|out of memory" logs/video-worker-errors.log

# Check system logs
dmesg | grep -i "killed\|oom"
```

## 🔄 Next Steps

1. ✅ Video Worker error logging
2. ⚠️ Transcription GPU error handling
3. ⚠️ GPU memory monitoring
4. ⚠️ Automatic GPU error recovery
5. ⚠️ Resource usage alerts

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
```

