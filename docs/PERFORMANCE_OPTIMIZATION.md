# 🚀 Performance Optimization Guide

## เป้าหมาย

**วิดีโอ 10 นาที → Transcription ใช้เวลาไม่เกิน 1-2 นาที**
- Speed: ≥5x real-time
- GPU Utilization: ≥80%

## ปัญหาที่พบ

### 1. GPU Utilization ต่ำ (20-50%)
**สาเหตุ:**
- `TRANSCRIPTION_MAX_WORKERS` ต่ำเกินไป
- ใช้ sequential processing (`WHISPER_USE_THREAD_LOCAL=false`)
- Model lock ทำให้ chunks ถูกประมวลผลแบบ sequential

**ผลกระทบ:**
- GPU ไม่ได้ใช้เต็มที่
- Transcription ช้า (ไม่ถึง 5x real-time)

### 2. Transcription ใช้เวลานานเกิน 3 นาที
**สาเหตุ:**
- GPU utilization ต่ำ
- Workers น้อยเกินไป
- Model lock contention

## วิธีแก้ไข

### Step 1: ปรับ TRANSCRIPTION_MAX_WORKERS

**สำหรับ RTX 4080 Super (16GB):**

| Model | Recommended Workers | GPU Memory Usage |
|-------|---------------------|------------------|
| base | 8-10 | ~2.4-3GB |
| small | 6-8 | ~6-8GB |
| medium | 3-4 | ~7.2-9.6GB |
| large-v3 | 2-3 | ~6-9GB |

**คำนวณ:**
```
Required Memory = Model Size × Workers + Overhead (~500MB)
```

**ตัวอย่าง:**
```bash
# medium model (~2.4GB)
TRANSCRIPTION_MAX_WORKERS=4  # 2.4GB × 4 = 9.6GB ✅

# large-v3 model (~3GB)
TRANSCRIPTION_MAX_WORKERS=3  # 3GB × 3 = 9GB ✅
```

### Step 2: ใช้ Parallel Processing

```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=4  # ปรับตาม model
TRANSCRIPTION_PREFETCH_COUNT=20
```

### Step 3: ตรวจสอบ GPU Memory

```bash
# ตรวจสอบ GPU memory ก่อนตั้งค่า
nvidia-smi

# ตั้งค่า workers ให้เหมาะสม
# ถ้า GPU memory เต็ม → ลด workers
# ถ้า GPU utilization ต่ำ → เพิ่ม workers
```

## Recommended Configuration

### สำหรับ medium model (RTX 4080 Super 16GB)

```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=4
TRANSCRIPTION_PREFETCH_COUNT=20
WHISPER_MODEL=medium
```

**Expected Performance:**
- GPU Utilization: 80-95%
- Speed: 5-8x real-time
- 10-minute video: 1-2 minutes

### สำหรับ large-v3 model (RTX 4080 Super 16GB)

```bash
WHISPER_USE_THREAD_LOCAL=true
TRANSCRIPTION_MAX_WORKERS=3
TRANSCRIPTION_PREFETCH_COUNT=15
WHISPER_MODEL=large-v3
```

**Expected Performance:**
- GPU Utilization: 70-90%
- Speed: 4-6x real-time
- 10-minute video: 1.5-2.5 minutes

## Testing

```bash
# ทดสอบกับวิดีโอ v10-1.mp4 (timeout 3 นาที)
bash scripts/pod/test-3min-timeout.sh medium

# ถ้า timeout → มีปัญหา → ต้องปรับปรุง
# ถ้าเสร็จใน 3 นาที → ตรวจสอบ GPU utilization
```

## Troubleshooting

### ถ้า Transcription ใช้เวลานานเกิน 3 นาที

1. **ตรวจสอบ GPU Utilization**
   ```bash
   watch -n 1 'nvidia-smi'
   ```
   - ถ้า < 50% → เพิ่ม `TRANSCRIPTION_MAX_WORKERS`
   - ถ้า > 95% → ลด `TRANSCRIPTION_MAX_WORKERS` (อาจเกิด OOM)

2. **ตรวจสอบ Configuration**
   ```bash
   cat .env.runpod | grep -E 'TRANSCRIPTION_MAX_WORKERS|WHISPER_USE_THREAD_LOCAL'
   ```
   - ต้องมี `WHISPER_USE_THREAD_LOCAL=true`
   - `TRANSCRIPTION_MAX_WORKERS` ต้องเหมาะสมกับ model

3. **ตรวจสอบ Logs**
   ```bash
   tail -f /tmp/video-worker.log | grep -E 'Starting chunk|Completed chunk|ERROR|CUDA'
   ```
   - ดูว่า chunks ถูกประมวลผลแบบ parallel หรือไม่
   - ตรวจสอบ errors

4. **ตรวจสอบ GPU Memory**
   ```bash
   nvidia-smi
   ```
   - ถ้า memory เต็ม → ลด workers
   - ถ้า memory ว่าง → เพิ่ม workers

## Quick Fix Script

```bash
# ปรับปรุงประสิทธิภาพอัตโนมัติ
bash scripts/pod/optimize-gpu-performance.sh
```

## สรุป

**เป้าหมาย:**
- ✅ วิดีโอ 10 นาที → Transcription ≤ 2 นาที
- ✅ GPU Utilization ≥ 80%
- ✅ Speed ≥ 5x real-time

**Configuration ที่แนะนำ:**
- `WHISPER_USE_THREAD_LOCAL=true` (parallel processing)
- `TRANSCRIPTION_MAX_WORKERS=4` (medium model) หรือ `3` (large-v3)
- `TRANSCRIPTION_PREFETCH_COUNT=20`

**Testing:**
- ทดสอบกับวิดีโอ v10-1.mp4
- Timeout: 3 นาที
- ถ้าไม่เสร็จ → มีปัญหา → ต้องปรับปรุง

