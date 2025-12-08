# คู่มือ Setup และ Benchmark สำหรับ GPU 3 ตัว

## 📋 สรุป

คู่มือนี้สรุปขั้นตอนการเตรียมและทดสอบ Performance บน GPU 3 ตัว:
- **RTX 4080 Super**
- **RTX 4000 Ada**
- **RTX 5080**

## 🚀 ขั้นตอน Setup (ทำครั้งเดียวต่อ GPU)

### สำหรับ RTX 4080 Super และ RTX 4000 Ada

#### 1. ตั้งค่า Base Image ใน RunPod Template
- **Container Image**: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
- (ไม่ต้องเปลี่ยน - ใช้ default)

#### 2. SSH เข้า Pod และ Git Pull
```bash
ssh <pod-host>
cd /workspace/transcription-service
git pull
```

#### 3. Install Dependencies
```bash
bash scripts/pod/install-dependencies.sh
```

#### 4. Setup Pod
```bash
bash scripts/pod/setup-pod.sh
```

#### 5. Start Services
```bash
bash scripts/pod/start-pod.sh
```

#### 6. ตรวจสอบ Status
```bash
bash scripts/pod/check-pod.sh
```

---

### สำหรับ RTX 5080

#### 1. ตั้งค่า Base Image ใน RunPod Template
- **เปลี่ยน Container Image** เป็น: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

#### 2. SSH เข้า Pod และ Git Pull
```bash
ssh <pod-host>
cd /workspace/transcription-service
git pull
```

#### 3. Install Dependencies (สำคัญ!)
```bash
bash scripts/pod/install-dependencies-cuda12.sh  # ⚠️ ใช้ script สำหรับ CUDA 12.x
```

#### 4. Setup Pod
```bash
bash scripts/pod/setup-pod.sh
```

#### 5. Start Services
```bash
bash scripts/pod/start-pod.sh
```

#### 6. ตรวจสอบ Status
```bash
bash scripts/pod/check-pod.sh
```

---

## 📥 Download Videos (ทำครั้งเดียว)

### Download Video เดียว
```bash
bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4
```

### Download 10 Videos (v10-1.mp4 ถึง v10-10.mp4)
```bash
bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4
```

**ผลลัพธ์**: Videos จะถูกเก็บไว้ที่ `uploads/v10-1.mp4` ถึง `uploads/v10-10.mp4`

---

## 🤖 Download Model (ถ้าจำเป็น)

Model จะถูก download อัตโนมัติเมื่อใช้งานครั้งแรก แต่ถ้าต้องการ pre-download:

### สำหรับ faster-whisper
```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('medium')"
```

Model จะถูกเก็บไว้ที่: `~/.cache/huggingface/hub/`

---

## 🧪 Run Benchmark

### Benchmark Video เดียว
```bash
# RTX 4080 Super
bash scripts/benchmark/run-benchmark.sh uploads/v10-1.mp4 medium rtx4080

# RTX 4000 Ada
bash scripts/benchmark/run-benchmark.sh uploads/v10-1.mp4 medium rtx4000

# RTX 5080
bash scripts/benchmark/run-benchmark.sh uploads/v10-1.mp4 medium rtx5080
```

### Benchmark 10 Videos (Batch)
```bash
# RTX 4080 Super
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4080

# RTX 4000 Ada
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4000

# RTX 5080
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx5080
```

**หรือใช้ pattern:**
```bash
bash scripts/pod/run-benchmark-batch.sh uploads/v10-*.mp4 medium rtx4080
```

---

## 📊 เปรียบเทียบผลลัพธ์

### ดูผลลัพธ์จาก GPU หลายตัว
```bash
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080
```

---

## 📁 ตำแหน่งเก็บผลลัพธ์

### Benchmark Results
- **Directory**: `benchmark-results/`
- **Format**: JSON files
- **Naming**: `benchmark-<gpu-name>-<model>-<timestamp>.json`

**ตัวอย่าง:**
```
benchmark-results/
├── benchmark-rtx4080-medium-20250115-120000.json
├── benchmark-rtx4080-medium-20250115-120000.log
├── benchmark-rtx4000-medium-20250115-130000.json
├── benchmark-rtx4000-medium-20250115-130000.log
├── benchmark-rtx5080-medium-20250115-140000.json
└── benchmark-rtx5080-medium-20250115-140000.log
```

### วิธี Export ผลลัพธ์

#### 1. Copy ทั้ง directory
```bash
# จาก Pod
scp -r <pod-host>:/workspace/transcription-service/benchmark-results ./
```

#### 2. Copy ไฟล์เฉพาะ
```bash
# Copy JSON files
scp <pod-host>:/workspace/transcription-service/benchmark-results/*.json ./
```

#### 3. ใช้ tar เพื่อ compress
```bash
# ใน Pod
cd /workspace/transcription-service
tar -czf benchmark-results.tar.gz benchmark-results/

# Copy tar file
scp <pod-host>:/workspace/transcription-service/benchmark-results.tar.gz ./
```

---

## 🔄 Restart Services (ถ้าจำเป็น)

### Restart ทั้งหมด
```bash
bash scripts/pod/restart-pod.sh
```

### Restart แยก
```bash
# Stop
bash scripts/pod/stop-pod.sh

# Start
bash scripts/pod/start-pod.sh
```

---

## 📋 Checklist สำหรับแต่ละ GPU

### RTX 4080 Super / RTX 4000 Ada
- [ ] Base Image: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
- [ ] Git pull
- [ ] `bash scripts/pod/install-dependencies.sh`
- [ ] `bash scripts/pod/setup-pod.sh`
- [ ] `bash scripts/pod/start-pod.sh`
- [ ] `bash scripts/pod/check-pod.sh` (ตรวจสอบ)
- [ ] Download videos
- [ ] Run benchmark
- [ ] Export results

### RTX 5080
- [ ] Base Image: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` ⚠️
- [ ] Git pull
- [ ] `bash scripts/pod/install-dependencies-cuda12.sh` ⚠️
- [ ] `bash scripts/pod/setup-pod.sh`
- [ ] `bash scripts/pod/start-pod.sh`
- [ ] `bash scripts/pod/check-pod.sh` (ตรวจสอบ)
- [ ] Download videos
- [ ] Run benchmark
- [ ] Export results

---

## 🎯 สรุปคำสั่งสำหรับ Benchmark 10 Videos

### สำหรับ RTX 4080 Super
```bash
# 1. Download videos
bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4

# 2. Run benchmark
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4080

# 3. Export results
scp -r <pod-host>:/workspace/transcription-service/benchmark-results ./benchmark-results-rtx4080
```

### สำหรับ RTX 4000 Ada
```bash
# 1. Download videos (ถ้ายังไม่มี)
bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4

# 2. Run benchmark
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx4000

# 3. Export results
scp -r <pod-host>:/workspace/transcription-service/benchmark-results ./benchmark-results-rtx4000
```

### สำหรับ RTX 5080
```bash
# 1. Download videos (ถ้ายังไม่มี)
bash scripts/pod/download-multiple-videos.sh https://korrakang.com/video/v10- 1 10 .mp4

# 2. Run benchmark
bash scripts/pod/run-benchmark-batch.sh uploads/v10-{1..10}.mp4 medium rtx5080

# 3. Export results
scp -r <pod-host>:/workspace/transcription-service/benchmark-results ./benchmark-results-rtx5080
```

---

## 📊 เปรียบเทียบผลลัพธ์ (หลังได้ผลลัพธ์จากทั้ง 3 GPU)

### วิธีที่ 1: ใช้ Compare Script (ใน Pod)
```bash
# Copy results จาก GPU ทั้งหมดมาไว้ใน Pod เดียวกัน
# แล้วรัน:
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080
```

### วิธีที่ 2: เปรียบเทียบด้วยมือ (Local)
1. Export results จากทั้ง 3 GPU
2. เปิด JSON files และเปรียบเทียบ metrics:
   - `elapsed_time_seconds`
   - `speedup`
   - `throughput_videos_per_hour`
   - `vram_used_mb`

---

## ⚠️ ข้อควรระวัง

1. **ใช้ GPU Name ที่สอดคล้องกัน**: `rtx4080`, `rtx4000`, `rtx5080`
2. **ใช้ Video เดียวกัน**: เพื่อการเปรียบเทียบที่ยุติธรรม
3. **ใช้ Model เดียวกัน**: `medium` (หรือ `large-v3`)
4. **ตรวจสอบ API Running**: `bash scripts/pod/check-pod.sh` ก่อนรัน benchmark

---

## 📚 เอกสารที่เกี่ยวข้อง

- [GPU Base Image Recommendations](./GPU_BASE_IMAGE_RECOMMENDATIONS.md)
- [RTX 5080 Setup Guide](./RTX5080_SETUP_GUIDE.md)
- [GPU Performance Comparison Plan](./GPU_PERFORMANCE_COMPARISON_PLAN.md)
- [Benchmark Scripts README](../scripts/benchmark/README.md)

