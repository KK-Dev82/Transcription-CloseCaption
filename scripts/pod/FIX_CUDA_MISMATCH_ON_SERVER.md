# 🔧 แก้ปัญหา CUDA Version Mismatch บน Server

## 📋 ปัญหา

**Base image ใช้ CUDA 12.1 แต่ PyTorch และ CT2 ใช้ CUDA 11.8**

แม้ CUDA 12.1 จะ backward compatible แต่ CUDA runtime libraries อาจไม่ตรงกัน ทำให้เกิดการค้าง (freeze) ตอน transcription

## ✅ วิธีแก้ไข (ไม่ต้อง Build Image ใหม่)

### Option 1: อัพเกรดเป็น CUDA 12.1 (แนะนำ) ⭐

อัพเกรด PyTorch และ CT2 เป็นเวอร์ชันที่รองรับ CUDA 12.1

#### วิธีทำ:

```bash
# ใน container บน RunPod server
cd /workspace/transcription-service

# รันสคริปต์แก้ไข
bash scripts/pod/fix-cuda-mismatch-on-server.sh
```

หรือทำ manual:

```bash
# 1. Uninstall packages ปัจจุบัน
pip3 uninstall -y torch torchaudio ctranslate2 faster-whisper

# 2. Install PyTorch สำหรับ CUDA 12.1
pip3 install --no-cache-dir \
    torch==2.1.1 \
    torchaudio==2.1.1 \
    --index-url https://download.pytorch.org/whl/cu121

# 3. Reinstall ctranslate2 (จะ auto-detect CUDA 12.1)
pip3 install --no-cache-dir --upgrade --force-reinstall \
    "ctranslate2>=4.5.0"

# 4. Reinstall faster-whisper
pip3 install --no-cache-dir \
    "faster-whisper==1.0.2"
```

#### ตรวจสอบผล:

```bash
python3 << 'PYEOF'
import torch
import ctranslate2
import faster_whisper

print(f"PyTorch: {torch.__version__}")
print(f"PyTorch CUDA: {torch.version.cuda}")
print(f"CTranslate2: {ctranslate2.__version__}")
print(f"Faster-Whisper: {faster_whisper.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
PYEOF
```

**คาดหวัง:** PyTorch CUDA ควรเป็น 12.1

---

### Option 2: ใช้ CPU Mode (เสถียรที่สุด)

ถ้าไม่ต้องการแก้ CUDA หรืออัพเกรดไม่ได้ ให้ใช้ CPU mode

#### วิธีทำ:

```bash
# ตั้ง environment variables
export WHISPER_DEVICE=cpu
export CT2_FORCE_CPU=1

# หรือแก้ไขใน .env หรือ config
echo "WHISPER_DEVICE=cpu" >> .env.runpod
echo "CT2_FORCE_CPU=1" >> .env.runpod
```

**ข้อดี:**
- ✅ เสถียร ไม่มีปัญหา CUDA version mismatch
- ✅ ใช้ได้ทันที

**ข้อเสีย:**
- ⚠️ ช้ากว่า GPU mode ประมาณ 3-5 เท่า
- ⚠️ ใช้ CPU resources เพิ่มขึ้น

---

### Option 3: ตั้ง CUDA Compatibility Mode

ใช้ CUDA backward compatibility ผ่าน environment variables

#### วิธีทำ:

```bash
export CUDA_MODULE_LOADING=LAZY
export CUDA_CACHE_DISABLE=0
export CT2_USE_CUDA_GRAPH=0
export CUDA_LAUNCH_BLOCKING=0

# ลองใช้ compute type อื่น
export CT2_COMPUTE_TYPE=float32  # แทน float16
```

เพิ่มใน `.env.runpod`:

```bash
cat >> .env.runpod << 'EOF'
CUDA_MODULE_LOADING=LAZY
CUDA_CACHE_DISABLE=0
CT2_USE_CUDA_GRAPH=0
CUDA_LAUNCH_BLOCKING=0
CT2_COMPUTE_TYPE=float32
EOF
```

---

### Option 4: Clean CUDA Cache

บางครั้ง CUDA cache อาจทำให้เกิดปัญหา

#### วิธีทำ:

```bash
# ลบ PyTorch CUDA cache
python3 << 'PYEOF'
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    print("✓ ลบ PyTorch CUDA cache แล้ว")
PYEOF

# ลบ CUDA kernel cache
rm -rf ~/.nv/ComputeCache 2>/dev/null || true
rm -rf /root/.nv/ComputeCache 2>/dev/null || true

# Restart services
bash scripts/pod/restart-pod-services.sh
```

---

## 🔍 ทดสอบหลังแก้ไข

```bash
# ทดสอบ GPU
export CT2_USE_CUDA_GRAPH=0
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export CUDA_VISIBLE_DEVICES=0

python3 << 'PYEOF'
from faster_whisper import WhisperModel
import sys

print("กำลังทดสอบ tiny model...")
try:
    m = WhisperModel('tiny',
                    device='cuda',
                    compute_type='float16',
                    num_workers=1,
                    cpu_threads=4)
    print("✓ โหลดโมเดลสำเร็จ")
    
    # ทดสอบ transcription
    segs, info = m.transcribe(
        '/tmp/test.wav',  # เปลี่ยนเป็นไฟล์เสียงจริง
        language='th',
        vad_filter=False,
        without_timestamps=True,
        beam_size=1,
        temperature=0.0
    )
    
    # ลองดึงผลลัพธ์
    first = next(segs)
    print(f"✓ ได้ผลลัพธ์: {first.text[:50]}")
    print("✅ GPU transcription ทำงานได้ปกติ!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF
```

---

## 📊 เปรียบเทียบตัวเลือก

| ตัวเลือก | ความเร็ว | เสถียร | ความซับซ้อน | แนะนำ |
|---------|---------|--------|------------|-------|
| **Option 1: อัพเกรด** ⭐ | ⚡⚡⚡ | ✅✅✅ | 🟡 ปานกลาง | ✅ **แนะนำ** |
| Option 2: CPU Mode | 🐢 | ✅✅✅ | 🟢 ง่าย | สำหรับ fallback |
| Option 3: Compatibility | ⚡⚡ | ✅✅ | 🟢 ง่าย | ลองก่อนอัพเกรด |
| Option 4: Clean Cache | ⚡⚡⚡ | ✅✅ | 🟢 ง่าย | ทำก่อนลองวิธีอื่น |

---

## ⚠️ หมายเหตุ

1. **Option 1 (อัพเกรด)** ใช้เวลานานที่สุด (~5-10 นาที) แต่แก้ปัญหาได้ถาวร
2. **Option 2 (CPU Mode)** ใช้ได้ทันที แต่ช้ากว่า
3. **Option 3-4** เป็นวิธีเบาๆ ลองก่อน ถ้าไม่ได้ค่อยใช้ Option 1

---

## 🚀 ขั้นตอนแนะนำ

1. **ลอง Option 4 (Clean Cache)** ก่อน - ใช้เวลาน้อยที่สุด
2. **ลอง Option 3 (Compatibility Mode)** - ตั้ง environment variables
3. **ถ้ายังไม่ได้ → ใช้ Option 1 (อัพเกรด)** - แก้ปัญหาถาวร
4. **ถ้าอัพเกรดไม่ได้ → ใช้ Option 2 (CPU Mode)** - เป็น fallback

---

## 📝 หลังแก้ไข

หลังจากแก้ไขแล้ว ควร:

1. **Restart services:**
   ```bash
   bash scripts/pod/restart-pod-services.sh
   ```

2. **ทดสอบ transcription** ด้วยวิดีโอจริง

3. **ตรวจสอบ logs** ว่าทำงานปกติ

4. **บันทึกการแก้ไข** เพื่อใช้ในครั้งหน้า

---

## 🔗 ดูเพิ่มเติม

- `scripts/pod/fix-cuda-mismatch-on-server.sh` - สคริปต์อัพเกรดอัตโนมัติ
- `scripts/pod/fix-cuda-mismatch-alternative.sh` - ทางเลือกอื่นๆ
- `DOCKER_IMAGE_COMPARISON.md` - เปรียบเทียบ base images

