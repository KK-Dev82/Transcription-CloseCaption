# 📊 Capacity Check: 25 × 30-minute Videos (300MB each)

## 📋 Requirements

- **Files**: 25 video files
- **Size**: 300MB per file
- **Duration**: 30 minutes per video
- **Total Size**: 7.5GB source files

## 💾 Disk Space Requirements

### Source Files
- 25 files × 300MB = **7.5 GB**

### Audio Extraction
- WAV files: ~15% of video size = 45MB per file
- 25 files × 45MB = **1.125 GB**

### Temporary Files
- Chunks, temp processing: ~1 GB
- **Total Temporary**: ~1 GB

### **Total Disk Space Needed**: ~9.6 GB

### Available Disk Space
- `/workspace`: 263TB available ✅
- **Status**: ✅ **SUFFICIENT**

## 🎮 GPU Memory Requirements

### Per Task
- Base model: ~0.7GB per task
- 25 tasks × 0.7GB = **17.5 GB**

### Available GPU Memory
- Total: ~20GB (RTX 4000 Ada)
- **Status**: ✅ **SUFFICIENT** (17.5GB used, 2.5GB buffer)

## ⏱️ Processing Time Estimates

### Audio Extraction (25 parallel)
- Per file: ~2-3 minutes
- **Total**: ~3 minutes (all 25 parallel)

### Transcription (25 parallel)
- Per 30-min video: ~15-20 minutes
- **Total**: ~18-20 minutes (all 25 parallel)

### **Total Processing Time**: ~20 minutes

## 📊 Queue Capacity

### Current Configuration
```bash
MAX_QUEUE_REQUEST=51      # ✅ 25 tasks < 51
MAX_QUEUE_EXTRACTION=80   # ✅ 25 tasks < 80
MAX_QUEUE_TRANSCRIBE=30   # ✅ 25 tasks < 30
```

### Worker Capacity
```bash
GPU_CONCURRENCY=25                    # ✅ 25 tasks
AUDIO_EXTRACTION_MAX_WORKERS=25       # ✅ 25 parallel
TRANSCRIPTION_MAX_WORKERS=25          # ✅ 25 parallel
```

**Status**: ✅ **ALL QUEUES SUFFICIENT**

## ✅ Capacity Analysis

### 1. Disk Space
- **Required**: ~9.6 GB
- **Available**: 263TB
- **Status**: ✅ **SUFFICIENT**

### 2. GPU Memory
- **Required**: 17.5 GB
- **Available**: ~20 GB
- **Status**: ✅ **SUFFICIENT** (2.5GB buffer)

### 3. Queue Limits
- **Request Queue**: 25 < 51 ✅
- **Extraction Queue**: 25 < 80 ✅
- **Transcription Queue**: 25 < 30 ✅
- **Status**: ✅ **ALL SUFFICIENT**

### 4. Worker Capacity
- **GPU Concurrency**: 25 = 25 ✅
- **Audio Extraction Workers**: 25 = 25 ✅
- **Transcription Workers**: 25 = 25 ✅
- **Status**: ✅ **SUFFICIENT**

## ⚠️ Potential Issues

### 1. Disk Space (if SAVE_TEMP_FILES=save)
- **Issue**: Temp files จะไม่ถูกลบ
- **Impact**: ใช้ disk space เพิ่มขึ้น
- **Solution**: ใช้ `SAVE_TEMP_FILES=not_save` หรือ cleanup หลังเสร็จ

### 2. Processing Time
- **Issue**: 25 × 30-min videos อาจใช้เวลานาน
- **Estimate**: ~20 minutes (parallel)
- **Solution**: Monitor progress และ timeout settings

### 3. Memory Leaks
- **Issue**: Long-running tasks อาจมี memory leaks
- **Solution**: Monitor worker memory usage

## ✅ Final Verdict

### **✅ SYSTEM IS READY**

**All Requirements Met**:
- ✅ Disk space: Sufficient (263TB available)
- ✅ GPU memory: Sufficient (20GB available, 17.5GB needed)
- ✅ Queue limits: All sufficient
- ✅ Worker capacity: All sufficient
- ✅ Processing time: Acceptable (~20 minutes)

### Recommendations

1. **Monitor Disk Space**
   ```bash
   df -h /workspace
   # Clean temp files if needed
   ```

2. **Monitor GPU Memory**
   ```bash
   nvidia-smi
   # Watch for OOM errors
   ```

3. **Monitor Queue Status**
   ```bash
   curl http://localhost:8010/queue/status
   ```

4. **Set Timeout Appropriately**
   ```bash
   TRANSCRIPTION_TASK_TIMEOUT_SECONDS=3600  # 1 hour
   ```

5. **Consider Cleanup**
   - Use `SAVE_TEMP_FILES=not_save` to save disk space
   - Or cleanup temp files after processing

## 🚀 Ready to Test

**System is ready to process 25 × 30-minute videos (300MB each) concurrently!**



