# 🔧 คู่มือแก้ไขปัญหา CTranslate2 ไม่สามารถใช้ GPU ได้

## ⚠️ ปัญหาที่พบ

หลังติดตั้ง `apt update && apt-get install -y ffmpeg` และ `pip3 install -r requirements.txt` แล้ว:
- ❌ ctranslate2 ไม่พบ CUDA support (`No module named 'ctranslate2._cuda'`)
- ❌ ระบบ fallback เป็น CPU → ใช้ RAM มากและช้า
- ❌ `LD_LIBRARY_PATH` ไม่ถูกตั้งค่า

---

## 🔍 สาเหตุ

1. **ctranslate2 wheel ที่ติดตั้งไม่มี CUDA support**
   - ctranslate2 4.4.0 มีหลาย wheel versions (CPU-only และ CUDA)
   - ถ้า pip ติดตั้ง CPU-only wheel → ไม่มี CUDA support

2. **LD_LIBRARY_PATH ไม่ถูกตั้งค่า**
   - ctranslate2 ต้องการ cuDNN libraries ใน `LD_LIBRARY_PATH`
   - Main API และ RQ workers ต้องตั้งค่า `LD_LIBRARY_PATH` ก่อน import ctranslate2

---

## ✅ วิธีแก้ไข

### 1. ตั้งค่า LD_LIBRARY_PATH ใน Main API

เพิ่มใน `app/main.py` ก่อน import services:

```python
# ตั้งค่า LD_LIBRARY_PATH สำหรับ cuDNN และ CTranslate2
import os
cudnn_path = "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
system_path = "/usr/lib/x86_64-linux-gnu"
cuda_path = "/usr/local/cuda-12.1/lib64"
ctranslate2_path = "/usr/local/lib/python3.10/dist-packages/ctranslate2.libs"

new_ld_path = f"{cudnn_path}:{system_path}:{cuda_path}:{ctranslate2_path}"
if os.getenv('LD_LIBRARY_PATH'):
    new_ld_path = f"{new_ld_path}:{os.getenv('LD_LIBRARY_PATH')}"

os.environ['LD_LIBRARY_PATH'] = new_ld_path
```

### 2. ตรวจสอบ ctranslate2 CUDA Support

```bash
# ตรวจสอบว่า ctranslate2 มี CUDA support หรือไม่
python3 -c "import ctranslate2; print(ctranslate2.get_supported_compute_types('cuda'))"

# ถ้าได้ [] → ไม่มี CUDA support
# ถ้าได้ ['float16', 'float32', ...] → มี CUDA support
```

### 3. Reinstall ctranslate2 ด้วย CUDA Support

```bash
# Uninstall ctranslate2
pip3 uninstall -y ctranslate2

# Reinstall ctranslate2 (pip จะเลือก CUDA wheel อัตโนมัติถ้ามี CUDA)
pip3 install ctranslate2==4.4.0

# หรือบังคับใช้ CUDA wheel
pip3 install ctranslate2==4.4.0 --no-cache-dir
```

### 4. ตรวจสอบ cuDNN Libraries

```bash
# ตรวจสอบว่า cuDNN libraries มีอยู่หรือไม่
ls -la /usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib/libcudnn*.so.8

# ควรเห็น:
# - libcudnn.so.8
# - libcudnn_ops_infer.so.8
# - libcudnn_cnn_infer.so.8
# - และอื่นๆ
```

### 5. ตั้งค่า Environment Variables

เพิ่มใน startup script หรือ `.env.runpod`:

```bash
export LD_LIBRARY_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/lib/x86_64-linux-gnu:/usr/local/cuda-12.1/lib64:/usr/local/lib/python3.10/dist-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}"
```

---

## 🔧 Quick Fix Script

สร้างไฟล์ `scripts/fix-ctranslate2-gpu.sh`:

```bash
#!/bin/bash
# Fix CTranslate2 GPU support

set -e

echo "🔧 Fixing CTranslate2 GPU Support..."

# 1. ตั้งค่า LD_LIBRARY_PATH
export LD_LIBRARY_PATH="/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/lib/x86_64-linux-gnu:/usr/local/cuda-12.1/lib64:/usr/local/lib/python3.10/dist-packages/ctranslate2.libs:${LD_LIBRARY_PATH:-}"

# 2. Reinstall ctranslate2
echo "📦 Reinstalling ctranslate2..."
pip3 uninstall -y ctranslate2
pip3 install ctranslate2==4.4.0 --no-cache-dir

# 3. ตรวจสอบ CUDA support
echo "🔍 Checking CUDA support..."
python3 << 'PYTHON'
import os
os.environ['LD_LIBRARY_PATH'] = '/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib:/usr/lib/x86_64-linux-gnu:/usr/local/cuda-12.1/lib64:/usr/local/lib/python3.10/dist-packages/ctranslate2.libs'

import ctranslate2
cuda_types = ctranslate2.get_supported_compute_types('cuda')
if cuda_types:
    print(f"✅ CUDA support available: {cuda_types}")
else:
    print("❌ CUDA support NOT available")
PYTHON

echo "✅ Done!"
```

---

## 📋 Checklist

- [ ] ตั้งค่า `LD_LIBRARY_PATH` ใน main.py
- [ ] ตั้งค่า `LD_LIBRARY_PATH` ใน RQ worker startup script
- [ ] Reinstall ctranslate2 (ถ้าจำเป็น)
- [ ] ตรวจสอบ cuDNN libraries
- [ ] ตรวจสอบ CUDA support
- [ ] Restart services

---

## ⚠️ หมายเหตุ

1. **Order ของ LD_LIBRARY_PATH สำคัญ!**
   - cuDNN path ต้องมาก่อน
   - System path (`/usr/lib/x86_64-linux-gnu`) จำเป็นสำหรับ CTranslate2

2. **ctranslate2 CUDA wheel**
   - pip จะเลือก CUDA wheel อัตโนมัติถ้า detect CUDA ได้
   - ถ้ายังไม่ได้ → ลอง reinstall

3. **ตรวจสอบหลัง restart**
   - ตรวจสอบ logs ว่าใช้ GPU หรือ CPU
   - ตรวจสอบ `nvidia-smi` ว่าเห็น processes
