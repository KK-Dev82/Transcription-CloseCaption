# คำแนะนำ Base Image สำหรับ GPU ต่างๆ

## 📋 สรุป

| GPU | Base Image | CUDA | PyTorch | Python | Scripts |
|-----|-----------|------|---------|--------|---------|
| **RTX 4080 Super** | `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | 11.8 | 2.1.0 | 3.10 | `install-dependencies.sh` |
| **RTX 4000 Ada** | `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | 11.8 | 2.1.0 | 3.10 | `install-dependencies.sh` |
| **RTX 5080** | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` ⭐ | 12.4.1 | 2.4.0 | 3.11 | `install-dependencies-cuda12.sh` |

## 🎯 เหตุผล

### RTX 4080 Super และ RTX 4000 Ada
- **ใช้ CUDA 11.8**: รองรับ Ada Lovelace architecture ได้ดี
- **PyTorch 2.1.0**: เสถียรและผ่านการทดสอบแล้ว
- **faster-whisper**: ทำงานได้ดีกับ CUDA 11.8

### RTX 5080 (Blackwell)
- **ต้องใช้ CUDA 12.x**: RTX 5080 ต้องการ CUDA 12.8+ เพื่อประสิทธิภาพเต็มที่
- **PyTorch 2.4.0**: รองรับ CUDA 12.x และ Blackwell architecture
- **CUDA 12.4.1**: รองรับ RTX 5080 ได้ดี (ใกล้เคียงกับ 12.8 ที่ต้องการ)

## 🚀 วิธีใช้งาน

### สำหรับ RTX 4080 Super และ RTX 4000 Ada

1. **ใช้ Base Image**:
   ```
   runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
   ```

2. **Install Dependencies**:
   ```bash
   bash scripts/pod/install-dependencies.sh
   ```

3. **Setup และ Start**:
   ```bash
   bash scripts/pod/setup-pod.sh
   bash scripts/pod/start-pod.sh
   ```

### สำหรับ RTX 5080

**ใช้ Base Image โดยตรง (แนะนำ - ใช้ Git pull)**

1. **ตั้งค่า Base Image ใน RunPod Template**:
   - เปลี่ยน Container Image จาก `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
   - เป็น `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

2. **Git Pull และ Setup** (เหมือนเดิม):
   ```bash
   cd /workspace
   git pull  # หรือ git clone ถ้ายังไม่มี
   cd transcription-service
   ```

3. **Install Dependencies** (ใช้ script สำหรับ CUDA 12.x):
   ```bash
   bash scripts/pod/install-dependencies-cuda12.sh
   ```

4. **Setup และ Start**:
   ```bash
   bash scripts/pod/setup-pod.sh
   bash scripts/pod/start-pod.sh
   ```

**หมายเหตุ**: `Dockerfile.runpod-rtx5080` ไม่จำเป็นถ้าใช้ Git pull ตรงๆ แต่จะมีประโยชน์ถ้าต้องการ build custom image ที่มี dependencies ติดตั้งไว้แล้ว

## ⚠️ ข้อควรระวัง

### Driver Requirements
- **RTX 4080/4000**: Driver 525.60.13+ (รองรับ Ada Lovelace)
- **RTX 5080**: Driver 550.54.15+ (รองรับ Blackwell)

### Dependencies Compatibility
- **CUDA 11.8**: faster-whisper 1.0.2, ctranslate2 4.4.0/4.5.0
- **CUDA 12.x**: faster-whisper 1.0.2+, ctranslate2 4.4.0+ (รองรับ CUDA 12.x)

### Requirements.txt
- สำหรับ RTX 5080: `requirements.txt` มี `torch==2.1.1` ซึ่งไม่เข้ากันกับ CUDA 12.x
- `install-dependencies-cuda12.sh` จะ override PyTorch เป็น 2.4.0 อัตโนมัติ

## 📊 การเปรียบเทียบ Performance

หลังจาก setup แล้ว สามารถรัน benchmark เพื่อเปรียบเทียบ:

```bash
# RTX 4080 Super
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4080

# RTX 4000 Ada
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx4000

# RTX 5080
bash scripts/benchmark/run-benchmark.sh uploads/test.mp4 medium rtx5080

# เปรียบเทียบผลลัพธ์
bash scripts/benchmark/compare-results.sh rtx4080 rtx4000 rtx5080
```

## 🔄 Migration Path

### ถ้าต้องการเปลี่ยนจาก CUDA 11.8 เป็น CUDA 12.x

1. **Backup Current Setup**:
   ```bash
   # Backup .env.runpod
   cp .env.runpod .env.runpod.backup
   ```

2. **Update Base Image** (ใน RunPod Template):
   - เปลี่ยนจาก `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
   - เป็น `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`

3. **Reinstall Dependencies**:
   ```bash
   rm .deps_installed
   bash scripts/pod/install-dependencies-cuda12.sh
   ```

4. **Restart Services**:
   ```bash
   bash scripts/pod/restart-pod.sh
   ```

## 📚 เอกสารที่เกี่ยวข้อง

- [GPU Performance Comparison Plan](./GPU_PERFORMANCE_COMPARISON_PLAN.md)
- [Benchmark Scripts README](../scripts/benchmark/README.md)
- [Pod Scripts README](../scripts/pod/README.md)

