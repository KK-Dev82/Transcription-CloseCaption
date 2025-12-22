# 🚀 4 GPU Setup Guide

## 📋 Overview

ระบบได้รับการอัพเดตให้รองรับ **4 GPUs** แทน 2 GPUs เพื่อเพิ่ม throughput และลดเวลา transcription

---

## ✅ Changes Made

### 1. RedisQueueService (`app/services/redis_queue_service.py`)

**Before (2 GPUs):**
```python
self.queues = {
    'gpu0': Queue('transcription_gpu0', ...),
    'gpu1': Queue('transcription_gpu1', ...),
    'default': Queue('transcription_default', ...),
}
```

**After (4 GPUs - Dynamic):**
```python
num_gpus = int(os.getenv('NUM_GPUS', '4'))
self.queues = {
    'default': Queue('transcription_default', ...),
}
for i in range(num_gpus):
    gpu_key = f'gpu{i}'
    queue_name = f'transcription_gpu{i}'
    self.queues[gpu_key] = Queue(queue_name, ...)
```

**Features:**
- ✅ Dynamic queue creation based on `NUM_GPUS`
- ✅ Supports any number of GPUs (2, 4, 6, 8, etc.)
- ✅ Queues: `gpu0`, `gpu1`, `gpu2`, `gpu3`, `default`, `priority`

---

### 2. Start Script (`scripts/pod/start-rq-workers.sh`)

**Before (2 GPUs - Hardcoded):**
```bash
# Worker GPU 0
CUDA_VISIBLE_DEVICES=0 rq worker transcription_gpu0 ...

# Worker GPU 1
CUDA_VISIBLE_DEVICES=1 rq worker transcription_gpu1 ...
```

**After (4 GPUs - Dynamic):**
```bash
NUM_GPUS=${NUM_GPUS:-4}
for i in $(seq 0 $((NUM_GPUS - 1))); do
    CUDA_VISIBLE_DEVICES=$i \
        rq worker transcription_gpu$i ...
done
```

**Features:**
- ✅ Dynamic worker creation based on `NUM_GPUS`
- ✅ Each worker listens to its GPU-specific queue + `transcription_default`
- ✅ Priority worker on GPU 0

---

## 🔧 Required Environment Variables

### Required

1. **`REDIS_URL`**
   - Redis connection URL
   - Example: `redis://default:password@host:port`
   - **Must be set before starting workers**

2. **`NUM_GPUS`**
   - Number of GPUs available
   - Default: `4`
   - **Must be set to 4 for 4 GPU setup**

### Optional

- `RQ_PRELOAD_MODEL`: `true` (recommended for faster first job)
- `LD_LIBRARY_PATH`: cuDNN library path
- `WHISPER_MODEL_SIZE`: Model size (default: `base`)

---

## 🚀 Setup Steps

### 1. Set Environment Variables

```bash
# In .env.runpod or export
export NUM_GPUS=4
export REDIS_URL="redis://default:password@host:port"
export RQ_PRELOAD_MODEL=true
```

### 2. Verify GPU Detection

```bash
nvidia-smi --list-gpus
# Should show 4 GPUs: GPU 0, GPU 1, GPU 2, GPU 3
```

### 3. Start Workers

```bash
# Load environment variables
source .env.runpod  # or set manually

# Start 4 GPU workers
bash scripts/pod/start-rq-workers.sh
```

**Expected Output:**
```
✅ RQ Workers started successfully!
Workers:
  - GPU 0: transcription_gpu0, transcription_default
  - GPU 1: transcription_gpu1, transcription_default
  - GPU 2: transcription_gpu2, transcription_default
  - GPU 3: transcription_gpu3, transcription_default
  - Priority: transcription_priority (GPU 0)
```

### 4. Verify Workers

```bash
# Check worker processes
ps aux | grep "rq worker"

# Check worker logs
tail -f /tmp/rq-worker-gpu0.log
tail -f /tmp/rq-worker-gpu1.log
tail -f /tmp/rq-worker-gpu2.log
tail -f /tmp/rq-worker-gpu3.log
```

### 5. Monitor Queues

```bash
rq info --url $REDIS_URL
```

---

## 📊 Expected Performance

### Before (2 GPUs)
- 5 videos (30 min each): ~10 minutes
- Throughput: ~24.6× realtime per 2 GPUs

### After (4 GPUs)
- 5 videos (30 min each): ~5 minutes (target)
- Throughput: ~49× realtime per 4 GPUs
- **2× improvement expected**

---

## 🔍 Troubleshooting

### Issue: Workers not starting

**Check:**
1. `NUM_GPUS` is set to 4
2. `REDIS_URL` is correct and accessible
3. GPUs are detected: `nvidia-smi --list-gpus`

### Issue: Jobs not distributed

**Check:**
1. All 4 workers are running: `ps aux | grep "rq worker"`
2. Queues are created: `rq info --url $REDIS_URL`
3. Jobs are enqueued to `transcription_default` (round-robin)

### Issue: GPU not used

**Check:**
1. `CUDA_VISIBLE_DEVICES` is set correctly in worker logs
2. Worker logs show model loading on correct GPU
3. `nvidia-smi` shows GPU utilization

---

## 📝 Notes

- **Round-Robin**: Jobs are distributed to `transcription_default` queue, which is consumed by all workers (round-robin)
- **Priority Queue**: Priority jobs go to `transcription_priority` queue (GPU 0)
- **Persistent Workers**: Each worker loads model once at startup (if `RQ_PRELOAD_MODEL=true`)
- **Dynamic Scaling**: Can easily scale to 6, 8, or more GPUs by changing `NUM_GPUS`

---

## ✅ Verification Checklist

- [ ] `NUM_GPUS=4` is set
- [ ] `REDIS_URL` is set and accessible
- [ ] 4 GPUs detected: `nvidia-smi --list-gpus`
- [ ] 4 workers started: `ps aux | grep "rq worker" | wc -l` = 4
- [ ] All workers healthy: Check logs for errors
- [ ] Queues created: `rq info` shows 4 GPU queues
- [ ] Test job succeeds: Send test transcription job

