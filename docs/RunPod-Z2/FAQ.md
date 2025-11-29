# ❓ FAQ - คำถามที่พบบ่อย

คำถามที่พบบ่อยเกี่ยวกับการใช้งาน Transcription Service บน RunPod และ HP Z2

---

## 🔄 ต้องเปิด Run Server ตลอดหรือไม่?

### คำตอบ: ขึ้นอยู่กับ RunPod Pod

**RunPod Pod:**
- ✅ **Pod ทำงานต่อเนื่อง** → Services ทำงานต่อเนื่อง
- ❌ **Pod terminate** → Services หยุดทำงาน
- 💰 **ค่าใช้จ่าย:** จ่ายตามเวลาที่ Pod ทำงาน

**วิธีจัดการ:**
- **Development/Testing:** Terminate Pod เมื่อไม่ใช้ (ประหยัดค่าใช้จ่าย)
- **Production:** Keep Pod running (services ทำงานต่อเนื่อง)

**Auto-start Services:**
- Custom Base Image จะ start services อัตโนมัติเมื่อ Pod เริ่มทำงาน
- ถ้า Pod restart, services จะ start ใหม่อัตโนมัติ

---

## 🐳 Custom Base Image ใช้ได้ไหม? CUDA มีไหม?

### คำตอบ: ใช้ได้ และมี CUDA

**Custom Base Image (`Dockerfile.runpod-base`):**
- ✅ **ใช้ได้** - สำหรับ RunPod Pod Container
- ✅ **มี CUDA** - จาก base image `nvidia/cuda:12.1.0-base-ubuntu22.04`
- ✅ **มี CUDA Runtime Libraries** - สำหรับรัน CUDA applications

**หมายเหตุ:**
- Custom Base Image ใช้เป็น **Container Environment** สำหรับ Pod
- ใน **Direct Mode**, services รันจาก source code ตรงๆ (ไม่ใช้ Docker containers)
- CUDA ถูก expose จาก host (RunPod) → Container → Services

**ตรวจสอบ CUDA:**
```bash
# ใน Pod Container
nvidia-smi  # ควรแสดง GPU information
python3 -c "import torch; print(torch.cuda.is_available())"  # ควรเป็น True
```

---

## 🖥️ Z2 ต้องปรับวิธีใช้ไหม?

### คำตอบ: ใช้วิธีเดียวกันได้ (Direct Mode)

**HP Z2 Workstation:**
- ✅ **ใช้ Direct Mode ได้** - รัน services จาก source code ตรงๆ
- ✅ **ใช้ script เดียวกัน** - `start-services-direct.sh`
- ⚠️ **ต้องมี prerequisites:**
  - NVIDIA drivers (ติดตั้งแล้ว)
  - `nvidia-container-toolkit` (สำหรับ Docker, ถ้าใช้)
  - CUDA Runtime Libraries (จาก Custom Base Image หรือติดตั้งแยก)

**ความแตกต่าง:**
- **RunPod:** Pod Container → Custom Base Image → Direct Mode
- **Z2:** Ubuntu 22.04 → Pull Custom Base Image (optional) → Direct Mode

**Setup Z2:**
```bash
# 1. Clone repository
cd /workspace
git clone <repo-url> transcription-service

# 2. Start services (ใช้ script เดียวกัน)
cd transcription-service
bash scripts/pod/start-services-direct.sh
```

**หมายเหตุ:** Z2 ไม่จำเป็นต้องใช้ Custom Base Image ถ้าติดตั้ง dependencies เองแล้ว

---

## 📊 ผลลัพธ์จาก test-runpod-gpu.sh

### สถานะปัจจุบัน

✅ **Services ทำงานได้แล้ว:**
- Redis: ✅ Running
- Whisper API: ✅ Healthy
- Main API: ✅ Healthy
- Video Worker: ✅ Running

✅ **GPU ทำงานได้:**
- RTX 4000 Ada Generation
- CUDA 12.7
- Memory: 20475 MiB

⚠️ **GPU ไม่ถูกใช้งาน:**
- "No running processes found" = ยังไม่ได้ทำ transcription
- **ปกติ** - GPU จะถูกใช้งานเมื่อมี transcription job

---

## 🔍 คำถามเพิ่มเติม

### Q: ทำไม GPU ไม่ถูกใช้งาน?

**A:** GPU จะถูกใช้งานเมื่อ:
1. มี transcription job
2. Whisper API ถูกเรียกใช้
3. Model ถูก load เข้า GPU memory

**ทดสอบ:**
```bash
# ส่ง transcription job
curl -X POST http://localhost:8001/api/transcription/upload \
  -F 'file=@test_audio.wav' \
  -F 'language=th' \
  -F 'model_size=small'

# ตรวจสอบ GPU usage
watch -n 1 nvidia-smi
```

---

### Q: ต้อง Build Custom Base Image ใหม่เมื่อไหร่?

**A:** Build ใหม่เมื่อ:
- เปลี่ยน system dependencies (apt packages)
- เปลี่ยน Python version
- เปลี่ยน CUDA version
- เปลี่ยน base image

**ไม่ต้อง Build เมื่อ:**
- อัปเดต Python code (`.py` files)
- อัปเดต `requirements.txt` (install ใหม่ได้)
- อัปเดต configuration

---

### Q: วิธี Stop Services?

**A:**
```bash
# Stop all services
pkill -f python
pkill -f redis

# หรือ stop แยก
pkill -f "python.*uvicorn.*app.main"  # Main API
pkill -f "python.*whisper_api"        # Whisper API
pkill -f "python.*video_worker"       # Video Worker
redis-cli shutdown                     # Redis
```

---

### Q: วิธี Restart Services?

**A:**
```bash
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

---

### Q: วิธีตรวจสอบว่า Services ทำงาน?

**A:**
```bash
# ตรวจสอบ processes
ps aux | grep -E "(python|redis)"

# ตรวจสอบ health
curl http://localhost:8001/health
curl http://localhost:8002/health
redis-cli ping

# ใช้ test script
bash scripts/pod/test-runpod-gpu.sh
```

---

### Q: วิธีอัปเดต Code?

**A:**
```bash
# วิธีที่ 1: ใช้ script (แนะนำ)
bash scripts/pod/update-code.sh staging

# วิธีที่ 2: Manual
cd /workspace/transcription-service
git pull origin staging
pip3 install --no-cache-dir -r requirements.txt
bash scripts/pod/start-services-direct.sh
```

---

## 🔗 Related Documents

- **Build vs Direct Mode:** [BUILD_VS_DIRECT_MODE.md](./BUILD_VS_DIRECT_MODE.md)
- **Update Code:** [UPDATE_CODE.md](./UPDATE_CODE.md)
- **Direct Mode Setup:** [DIRECT_MODE_SETUP.md](./DIRECT_MODE_SETUP.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

**Last Updated:** 2024-12-19

