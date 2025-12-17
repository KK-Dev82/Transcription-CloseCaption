# 🎬 คำแนะนำสำหรับการทดสอบ Real Video Files

## 📋 Test Scenario: 25 × 30-minute Videos (300MB each)

### ✅ System Readiness: **READY**

## 📊 Resource Analysis

### Disk Space
- **Required**: ~9.4 GB
- **Available**: 263TB
- **Status**: ✅ **MORE THAN SUFFICIENT**

### GPU Memory
- **Required**: 17.5 GB (25 tasks × 0.7GB)
- **Available**: 19.67 GB
- **Status**: ✅ **SUFFICIENT** (2.17GB buffer)

### Processing Time
- **Audio Extraction**: ~3 minutes (25 parallel)
- **Transcription**: ~18 minutes (25 parallel)
- **Total**: ~18-20 minutes

## ⚙️ Configuration Status

### Queue Limits
- ✅ `MAX_QUEUE_REQUEST=51` (25 tasks < 51)
- ✅ `MAX_QUEUE_EXTRACTION=80` (25 tasks < 80)
- ✅ `MAX_QUEUE_TRANSCRIBE=30` (25 tasks < 30)

### Worker Capacity
- ✅ `GPU_CONCURRENCY=25` (25 tasks = 25)
- ✅ `AUDIO_EXTRACTION_MAX_WORKERS=25` (25 parallel)
- ✅ `TRANSCRIPTION_MAX_WORKERS=25` (25 parallel)

## ⚠️ Important Considerations

### 1. Disk Space Management

**Current Setting**: `SAVE_TEMP_FILES=save`

**Impact**:
- Temp files จะไม่ถูกลบอัตโนมัติ
- 25 files × ~45MB audio = ~1.1GB temp files
- อาจใช้ disk space เพิ่มขึ้น

**Recommendation**:
```bash
# Option 1: Keep temp files (for debugging)
SAVE_TEMP_FILES=save

# Option 2: Auto cleanup (save disk space)
SAVE_TEMP_FILES=not_save
```

### 2. Processing Time

**Estimate**: ~18-20 minutes for all 25 files

**Factors**:
- Video complexity
- Audio quality
- GPU performance
- System load

**Recommendation**:
- Set timeout: `TRANSCRIPTION_TASK_TIMEOUT_SECONDS=3600` (1 hour)
- Monitor progress via API

### 3. Memory Monitoring

**Watch for**:
- GPU memory usage (should stay < 20GB)
- Worker memory leaks
- System memory usage

**Commands**:
```bash
# Monitor GPU
watch -n 1 nvidia-smi

# Monitor worker
ps aux | grep video_worker
```

## 🚀 Test Execution Plan

### Phase 1: Single File Test
1. Test with 1 × 30-min video
2. Verify processing time
3. Check disk space usage
4. Monitor GPU memory

### Phase 2: Small Batch Test
1. Test with 5 × 30-min videos
2. Verify parallel processing
3. Check queue flow
4. Monitor resource usage

### Phase 3: Full Test (25 files)
1. Send all 25 files
2. Monitor progress
3. Check completion
4. Verify all results

## 📝 Pre-Test Checklist

- [ ] Verify worker is running
- [ ] Check disk space (> 10GB free)
- [ ] Check GPU memory (> 18GB free)
- [ ] Verify queue limits
- [ ] Set appropriate timeouts
- [ ] Prepare monitoring tools

## ✅ Final Verdict

### **✅ SYSTEM IS READY FOR 25 × 30-MINUTE VIDEOS**

**All Requirements Met**:
- ✅ Disk space: Sufficient (263TB available)
- ✅ GPU memory: Sufficient (19.67GB available)
- ✅ Queue limits: All sufficient
- ✅ Worker capacity: All sufficient
- ✅ Configuration: All correct

**Ready to proceed with real video test!**



