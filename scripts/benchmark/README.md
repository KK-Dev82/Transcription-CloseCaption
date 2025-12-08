# Benchmark Scripts สำหรับการเปรียบเทียบ GPU Performance

Scripts สำหรับรัน benchmark และเปรียบเทียบผลลัพธ์ระหว่าง GPU หลายตัว

## 📋 Scripts

### 1. `run-benchmark.sh`
รัน benchmark บน GPU ตัวเดียว

**วิธีใช้งาน:**
```bash
bash scripts/benchmark/run-benchmark.sh <video-path> [model] [gpu-name]
```

**ตัวอย่าง:**
```bash
# ใช้ GPU auto-detect
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium

# ระบุ GPU name
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 large-v3 rtx4080
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4000
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 large-v3 rtx5080
```

**ผลลัพธ์:**
- JSON file: `benchmark-results/benchmark-<gpu>-<model>-<timestamp>.json`
- Log file: `benchmark-results/benchmark-<gpu>-<model>-<timestamp>.log`

### 2. `compare-results.sh`
เปรียบเทียบผลลัพธ์จาก GPU หลายตัว

**วิธีใช้งาน:**
```bash
bash scripts/benchmark/compare-results.sh [gpu1] [gpu2] [gpu3]
```

**ตัวอย่าง:**
```bash
# เปรียบเทียบ 3 GPU
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080

# เปรียบเทียบ 2 GPU
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000
```

**ผลลัพธ์:**
- แสดงตารางเปรียบเทียบ Performance และ Resource Usage

## 🚀 Quick Start

### 1. เตรียม Test Video
```bash
# Download หรือ copy video ไปที่ uploads/
cp /path/to/test-video.mp4 uploads/test.mp4
```

### 2. รัน Benchmark บนแต่ละ GPU

**บน RTX 4080 Super (Baseline):**
```bash
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4080
```

**บน RTX 4000 Ada:**
```bash
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4000
```

**บน RTX 5080:**
```bash
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx5080
```

### 3. เปรียบเทียบผลลัพธ์
```bash
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080
```

## 📊 Metrics ที่เก็บ

### Performance Metrics
- **Elapsed Time**: เวลาที่ใช้ในการ transcribe (วินาที)
- **Speedup**: อัตราเร็วเทียบกับ realtime (x)
- **Realtime Ratio**: อัตราส่วนเวลาที่ใช้ต่อเวลาวิดีโอ
- **Throughput**: จำนวนวิดีโอต่อชั่วโมง (videos/hour)

### Resource Metrics
- **VRAM Used**: VRAM ที่ใช้ (MB)
- **VRAM After**: VRAM หลังเสร็จสิ้น (MB)

## 📁 โครงสร้างไฟล์

```
benchmark-results/
├── benchmark-rtx4080-medium-20240101-120000.json
├── benchmark-rtx4080-medium-20240101-120000.log
├── benchmark-rtx4000-medium-20240101-130000.json
├── benchmark-rtx4000-medium-20240101-130000.log
├── benchmark-rtx5080-medium-20240101-140000.json
└── benchmark-rtx5080-medium-20240101-140000.log
```

## ⚠️ ข้อควรระวัง

1. **ใช้ Video เดียวกัน**: เพื่อการเปรียบเทียบที่ยุติธรรม ควรใช้ video เดียวกันบนทุก GPU
2. **ใช้ Model เดียวกัน**: ใช้ Whisper model เดียวกัน (medium, large-v3, etc.)
3. **API ต้อง Running**: ตรวจสอบว่า Main API ทำงานอยู่ (`bash scripts/pod/check-pod.sh`)
4. **GPU Name**: ใช้ชื่อ GPU ที่สอดคล้องกัน (rtx4080, rtx4000, rtx5080)

## 🔍 Troubleshooting

### API ไม่ทำงาน
```bash
# ตรวจสอบ status
bash scripts/pod/check-pod.sh

# Start services
bash scripts/pod/start-pod.sh
```

### ไม่พบผลลัพธ์
```bash
# ตรวจสอบว่า benchmark-results/ มีไฟล์หรือไม่
ls -la benchmark-results/

# ตรวจสอบ logs
tail -f benchmark-results/benchmark-*.log
```

### GPU ไม่ถูก detect
```bash
# ตรวจสอบ GPU
nvidia-smi

# ระบุ GPU name เอง
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4080
```

## 📚 เอกสารที่เกี่ยวข้อง

- [GPU Performance Comparison Plan](../../docs/GPU_PERFORMANCE_COMPARISON_PLAN.md)
- [Pod Scripts README](../pod/README.md)

