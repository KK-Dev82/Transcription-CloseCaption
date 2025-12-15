# Video Worker Crash Analysis

## 🔍 Root Cause: SIGTERM Signal

### Evidence
- **Last Log Entry**: `2025-12-15 18:43:52,633 - ได้รับ signal 15 กำลังปิด worker...`
- **Signal**: SIGTERM (15)
- **Status**: Worker shut down gracefully (not crash)

### Possible Causes

#### 1. OOM Killer (Most Likely)
- **Symptom**: Process killed by system due to memory pressure
- **Check**: `dmesg | grep -i "killed\|oom"`
- **Why**: GPU utilization 98% + low VRAM 9% = potential memory pressure

#### 2. Manual Kill
- **Symptom**: Someone/something killed the process
- **Check**: System logs, monitoring scripts
- **Why**: Worker Monitor or manual intervention

#### 3. System Shutdown/Restart
- **Symptom**: System-level event
- **Check**: System uptime, reboot logs
- **Why**: Container restart, pod restart

## 📊 GPU Utilization vs VRAM Issue

### Observation
- **GPU Utilization**: 98% (very high)
- **VRAM Usage**: 9% (very low)
- **Issue**: High compute but low memory usage

### Analysis
1. **High Utilization**: GPU is working hard (good)
2. **Low VRAM**: Model fits in memory (good)
3. **Problem**: May indicate:
   - GPU is processing but not efficiently using memory
   - Multiple small operations instead of batch processing
   - Memory fragmentation

### Why Worker Stopped
- **Not GPU OOM**: VRAM is only 9% used
- **Possible**: System memory (RAM) pressure
- **Possible**: Process killed by OOM killer due to RAM usage

## 🔧 Solutions Implemented

### 1. Separate Error Logging
- ✅ `logs/video-worker-errors.log` - Worker errors only
- ✅ `logs/video-worker.log` - All worker logs
- ✅ Enhanced signal handler logging
- ✅ Resource usage logging before shutdown

### 2. GPU Error Detection
- ✅ Detect CUDA/OOM errors
- ✅ Log GPU-related errors with full traceback
- ✅ Monitor GPU overload

### 3. Enhanced Signal Handling
- ✅ Log signal source and type
- ✅ Resource usage before shutdown
- ✅ Better error messages

## 📝 Next Steps

### 1. Monitor Error Logs
```bash
# Watch worker errors
tail -f logs/video-worker-errors.log

# Check for GPU errors
grep -i "gpu\|cuda\|oom" logs/video-worker-errors.log

# Check for crashes
grep -i "fatal\|crash\|signal" logs/video-worker-errors.log
```

### 2. Check System Memory
```bash
# Check RAM usage
free -h

# Check OOM killer
dmesg | grep -i "killed\|oom"

# Check process memory
ps aux --sort=-%mem | head -10
```

### 3. Monitor GPU Usage
```bash
# Continuous monitoring
watch -n 1 nvidia-smi

# Check GPU processes
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

## 🚨 Prevention

### 1. Resource Limits
- Set proper `GPU_CONCURRENCY` (2-3 for medium model)
- Monitor RAM usage
- Set memory limits if needed

### 2. Error Recovery
- Auto-restart on crash
- GPU error recovery
- Fallback to CPU if GPU fails

### 3. Monitoring
- Alert on high GPU utilization
- Alert on low VRAM usage
- Alert on worker crashes

## 📊 Log File Structure

```
logs/
├── api-service.log              # Main API log
├── api-service-errors.log       # API errors only
├── video-worker.log             # Main worker log
└── video-worker-errors.log      # Worker errors only (NEW)
```

## 💡 Debugging Commands

```bash
# Check worker status
ps aux | grep video_worker

# Check worker errors
tail -50 logs/video-worker-errors.log

# Check GPU status
nvidia-smi

# Check system memory
free -h

# Check OOM killer
dmesg | grep -i "killed\|oom" | tail -20

# Check worker logs for signals
grep -i "signal\|sigterm\|sigint" logs/video-worker.log | tail -10
```
