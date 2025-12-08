# RTX 4000 Ada - Benchmark Results

**Date**: 2025-12-08  
**GPU**: NVIDIA RTX 4000 Ada Generation  
**Model**: Whisper Medium  
**Video**: v10-1.mp4 (600s / 10 minutes)  
**Concurrent Tasks**: 10

---

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| **Total Elapsed Time** | 245.00s (4.08 minutes) |
| **Successful Tasks** | 10/10 ✅ |
| **Failed Tasks** | 0 |
| **Avg Task Time** | 24.50s |
| **Overall Speedup** | 24.49x |
| **Tasks Per Hour** | 146.94 |
| **Video Duration** | 600s (10.0 minutes) |

---

## 💾 Resource Usage

| Metric | Value |
|--------|-------|
| **VRAM Before** | 0 MB |
| **VRAM After** | 1818 MB |
| **VRAM Used** | 1818 MB |

---

## 📝 Task Details

### Task Completion Times

| Task # | Task ID (short) | Created At | Completed At | Duration |
|--------|----------------|------------|--------------|----------|
| 1 | 90c7a7aa | 23:02:20 | 23:02:47 | ~27s |
| 2 | 131b1eac | 23:02:21 | 23:03:11 | ~50s |
| 3 | 93c35cc3 | 23:02:23 | 23:03:34 | ~71s |
| 4 | be88cec9 | 23:02:24 | 23:03:58 | ~94s |
| 5 | c847b3a3 | 23:02:26 | 23:04:21 | ~115s |
| 6 | 3f47f70d | 23:02:27 | 23:04:45 | ~138s |
| 7 | 31d3c51c | 23:02:29 | 23:05:08 | ~159s |
| 8 | c8598587 | 23:02:30 | 23:05:32 | ~182s |
| 9 | a2c83f7d | 23:02:32 | 23:05:55 | ~203s |
| 10 | 1191f5af | 23:02:33 | 23:06:19 | ~226s |

**Note**: Tasks were processed sequentially (one after another), not truly parallel.

---

## 📄 Transcription Text Quality

### Text Samples (to be verified)

_Text samples from each task will be added after verification_

---

## 📁 Result Files

- **JSON**: `benchmark-results/concurrent-benchmark-rtx4000-medium-10tasks-20251208-160215.json`
- **Log**: `benchmark-results/concurrent-benchmark-rtx4000-medium-10tasks-20251208-160215.log`

---

## 🔍 Observations

1. **Performance**: 24.49x speedup means processing 10 minutes of audio in ~24.5 seconds per task
2. **Sequential Processing**: Tasks appear to be processed one at a time rather than truly concurrent
3. **VRAM Usage**: Consistent VRAM usage of ~1818 MB during processing
4. **Success Rate**: 100% success rate (10/10 tasks completed)

---

## 📊 Comparison Ready

This benchmark result is ready for comparison with:
- RTX 4080 Super
- RTX 5080

---

**Generated**: 2025-12-08 16:06 UTC

