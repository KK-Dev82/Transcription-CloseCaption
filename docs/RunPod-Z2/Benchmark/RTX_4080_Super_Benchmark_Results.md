# RTX 4080 Super - Benchmark Results

**Date**: 2025-12-08  
**GPU**: NVIDIA RTX 4080 Super (16GB VRAM)  
**Model**: Whisper Medium  
**Video**: v10-1.mp4 (600s / 10 minutes)  
**Concurrent Tasks**: 10

---

## ⚠️ Status: Partial Completion

**Note**: Benchmark completed 5/10 tasks. 5 tasks remain in pending status, likely due to queue processing issues or timeout.

---

## 📊 Performance Metrics (5 Completed Tasks)

| Metric | Value |
|--------|-------|
| **Total Tasks** | 10 |
| **Completed Tasks** | 5/10 ✅ |
| **Pending Tasks** | 5/10 ⏸️ |
| **Failed Tasks** | 0 |
| **Tasks with Text** | 4/5 |

---

## 📝 Transcription Text Quality (Completed Tasks)

### Summary
- **Tasks with Text**: 4/5 completed tasks
- **Average Text Length**: ~3,057 chars (~2,211 Thai chars)
- **Average Chunks**: 20 chunks per task

### Task Details

| Task # | Task ID (short) | Status | Text Length | Thai Chars | Chunks |
|--------|----------------|--------|-------------|------------|--------|
| 1 | 7952df69 | ⏸️ Pending | - | - | - |
| 2 | 8e62e377 | ✅ Completed | 3,821 | 2,764 | 20 |
| 3 | 392a05df | ⏸️ Pending | - | - | - |
| 4 | 9f9a32a4 | ✅ Completed | 0 | 0 | 0 |
| 5 | 50bd9e3a | ✅ Completed | 3,821 | 2,764 | 20 |
| 6 | 5c48d219 | ⏸️ Pending | - | - | - |
| 7 | 30e50a4d | ✅ Completed | 3,821 | 2,764 | 20 |
| 8 | ba9b3cdd | ⏸️ Pending | - | - | - |
| 9 | 109b20af | ✅ Completed | 3,821 | 2,764 | 20 |
| 10 | 454d1bad | ⏸️ Pending | - | - | - |

**Note**: Task 4 (9f9a32a4) completed but has no transcription text, indicating a potential issue with text saving.

---

## 💾 Resource Usage

| Metric | Value |
|--------|-------|
| **VRAM Usage** | ~1,914-2,010 MB |
| **VRAM Before** | ~1 MB |
| **VRAM Used** | ~1,913-2,009 MB |

---

## 🔍 Observations

1. **Partial Completion**: Only 5/10 tasks completed successfully
2. **Text Quality**: 4/5 completed tasks have transcription text with consistent length (~3,821 chars, ~2,764 Thai chars)
3. **VRAM Usage**: Similar to RTX 4000 Ada (~1,818 MB), indicating consistent model loading
4. **Pending Tasks**: 5 tasks remain in pending status, possibly due to:
   - Queue processing delays
   - Timeout issues
   - Resource constraints

---

## 📊 Comparison with RTX 4000 Ada

| Metric | RTX 4000 Ada | RTX 4080 Super |
|--------|--------------|---------------|
| **Completed Tasks** | 10/10 ✅ | 5/10 ⚠️ |
| **VRAM Usage** | ~1,818 MB | ~1,914-2,010 MB |
| **Text Quality** | 10/10 tasks | 4/5 tasks |
| **Avg Text Length** | 3,844 chars | 3,821 chars |
| **Avg Thai Chars** | 2,782 chars | 2,764 chars |

**Note**: RTX 4080 Super benchmark is incomplete. Full comparison requires all 10 tasks to complete.

---

## 📁 Result Files

- **Log**: `benchmark-results/concurrent-benchmark-rtx4080-medium-10tasks-20251208-165723.log`
- **Transcription Storage**: `storage/transcriptions/{task_id}/metadata.json`

---

## 🔄 Next Steps

1. **Investigate Pending Tasks**: Check why 5 tasks remain in pending status
2. **Re-run Benchmark**: Consider re-running the benchmark to get complete results
3. **Check Queue Status**: Verify RabbitMQ queue processing and DLQ status
4. **Compare Performance**: Once all tasks complete, compare with RTX 4000 Ada and RTX 5080

---

**Generated**: 2025-12-08 17:30 UTC  
**Status**: ⚠️ Incomplete - Requires re-run or investigation of pending tasks

