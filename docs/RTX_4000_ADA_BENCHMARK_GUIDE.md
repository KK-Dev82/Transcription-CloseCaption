# 🎯 RTX 4000 Ada - Benchmark Setup & Test Guide

## 📋 สรุป

คู่มือนี้สำหรับการทดสอบและรัน benchmark บน RTX 4000 Ada โดยไม่ conflict กับ RTX 4080 Super และ RTX 5080

---

## 🚀 วิธีใช้งาน

### วิธีที่ 1: Remote Setup & Test (แนะนำ)

```bash
# รัน script ที่จะ SSH เข้าไป setup และ test อัตโนมัติ
bash scripts/pod/run-benchmark-4000ada-remote.sh
```

**Script นี้จะทำ:**
- ✅ ตรวจสอบ SSH connection
- ✅ Git pull latest code
- ✅ ตรวจสอบ services
- ✅ ตรวจสอบ video
- ✅ Run test script

---

### วิธีที่ 2: SSH และรันเอง

#### Step 1: SSH เข้า Server

```bash
# ใช้ script helper
bash scripts/pod/ssh-4000ada.sh

# หรือ SSH โดยตรง
ssh 4000-ada
```

#### Step 2: ตรวจสอบและ Setup

```bash
cd /workspace/transcription-service

# Run test script (ตรวจสอบทุกอย่าง)
bash scripts/pod/test-benchmark-4000ada.sh
```

**Script นี้จะตรวจสอบ:**
- ✅ GPU (RTX 4000 Ada)
- ✅ Services (Redis, API, Video Worker)
- ✅ Video file (v10-1.mp4)
- ✅ Whisper model (medium)
- ✅ API endpoint

#### Step 3: Run Benchmark

```bash
# Run concurrent benchmark (10 tasks)
bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4000
```

---

## 🔧 การแก้ไขปัญหา

### ปัญหา: Port 8001/8010 ถูกใช้งานอยู่แล้ว

```bash
# ใช้ fix script
bash scripts/pod/fix-port-8001.sh

# หรือ restart services
bash scripts/pod/stop-pod.sh
bash scripts/pod/start-pod.sh
```

### ปัญหา: API ไม่ทำงาน (405 Not Allowed)

```bash
# ตรวจสอบ services
bash scripts/pod/check-pod.sh

# Restart services
bash scripts/pod/restart-pod.sh
```

### ปัญหา: Video ไม่มี

```bash
# Download video
bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4
```

### ปัญหา: bc command not found

✅ **แก้ไขแล้ว** - Script ใช้ `python3` หรือ `awk` แทน `bc` อัตโนมัติ

---

## 📊 ผลลัพธ์

### ตำแหน่งเก็บผลลัพธ์

```
benchmark-results/
└── concurrent-benchmark-rtx4000-medium-10tasks-YYYYMMDD-HHMMSS.json
```

### ตัวอย่างผลลัพธ์

```json
{
  "benchmark": {
    "gpu_name": "rtx4000",
    "model": "medium",
    "num_concurrent_tasks": 10
  },
  "performance": {
    "total_elapsed_time_seconds": 120.5,
    "avg_task_time_seconds": "12.05",
    "overall_speedup": "49.79",
    "tasks_per_hour": "298.51"
  },
  "resources": {
    "vram_used_mb": 4096
  }
}
```

---

## ⚠️ ข้อควรระวัง

### 1. ไม่ Conflict กับ GPU อื่น

✅ **Scripts ที่แก้ไขแล้ว:**
- `run-benchmark-concurrent.sh` - ใช้ auto-detect port (8001/8010)
- `run-benchmark.sh` - ใช้ auto-detect port
- `run-benchmark-batch.sh` - ใช้ auto-detect port

✅ **ไม่ใช้ bc command:**
- ใช้ `python3` หรือ `awk` แทน
- ทำงานได้กับทุก GPU

### 2. Port Configuration

- **Port 8001**: Main API (จาก `start-pod.sh`)
- **Port 8010**: Transcription Service (จาก `start-service-daemon.sh`)

Script จะ auto-detect port ที่ใช้งานได้อัตโนมัติ

### 3. GPU Name

ใช้ `rtx4000` สำหรับ RTX 4000 Ada (ไม่ใช่ `rtx4000ada`)

---

## 🔍 ตรวจสอบ Status

### ตรวจสอบ Services

```bash
bash scripts/pod/check-pod.sh
```

### ตรวจสอบ API Port

```bash
# Check port 8001
curl http://localhost:8001/health

# Check port 8010
curl http://localhost:8010/health
```

### ตรวจสอบ GPU

```bash
nvidia-smi
```

---

## 📝 คำสั่งที่ใช้บ่อย

```bash
# SSH เข้า server
bash scripts/pod/ssh-4000ada.sh

# ตรวจสอบและ test
bash scripts/pod/test-benchmark-4000ada.sh

# Run benchmark
bash scripts/pod/run-benchmark-concurrent.sh uploads/v10-1.mp4 10 medium rtx4000

# ตรวจสอบ services
bash scripts/pod/check-pod.sh

# Restart services
bash scripts/pod/restart-pod.sh

# ดู logs
tail -f /tmp/main-api.log
tail -f /tmp/video-worker.log
```

---

## 🎯 Next Steps

1. ✅ Run benchmark บน RTX 4000 Ada
2. ✅ เปรียบเทียบผลลัพธ์กับ RTX 4080 Super และ RTX 5080
3. ✅ วิเคราะห์ performance differences

```bash
# Compare results
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080
```

---

## 📚 เอกสารที่เกี่ยวข้อง

- [GPU Benchmark Setup Guide](./GPU_BENCHMARK_SETUP_GUIDE.md)
- [GPU Performance Comparison Plan](./GPU_PERFORMANCE_COMPARISON_PLAN.md)

