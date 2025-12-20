# 🔄 System-Level Dependencies ที่ Reset เมื่อ Restart POD

## 📋 สรุป

Packages ที่ต้องติดตั้งที่ **system level** (ไม่สามารถติดตั้งที่ `/workspace` ได้) และจะ **reset ทุกครั้งเมื่อ restart POD container**:

---

## ❌ Packages ที่ Reset เมื่อ Restart POD

### 1. **FFmpeg** ✅ ถูกต้อง
- **สถานะ**: ต้องติดตั้งที่ system level (`apt-get install ffmpeg`)
- **ปัญหา**: หายไปหลัง restart POD
- **วิธีแก้**: ใช้ `scripts/pod/install-ffmpeg-persistent.sh` เพื่อติดตั้ง static binary ไปยัง `/workspace/.local/bin`
- **Location**:
  - System: `/usr/bin/ffmpeg` (หายหลัง restart)
  - Persistent: `/workspace/.local/bin/ffmpeg` (ไม่หาย)

### 2. **tzdata (Timezone Data)** ✅ ถูกต้อง
- **สถานะ**: ต้องติดตั้งที่ system level (`apt-get install tzdata`)
- **ปัญหา**: หายไปหลัง restart POD
- **วิธีแก้**: ใช้ `scripts/pod/install-timezone-persistent.sh` เพื่อ copy timezone data ไปยัง `/workspace/.local/share/zoneinfo`
- **Location**:
  - System: `/usr/share/zoneinfo` (หายหลัง restart)
  - Persistent: `/workspace/.local/share/zoneinfo` (ไม่หาย)
- **Environment Variable**: `TZDIR=/workspace/.local/share/zoneinfo`

### 3. **cuDNN Libraries** ✅ ถูกต้อง (Version Mismatch กับ CTranslate2)
- **สถานะ**: ติดตั้งใน container image แล้ว แต่มีปัญหา version mismatch
- **ปัญหา**:
  - Container มี **cuDNN 8.7** (8700)
  - CTranslate2 4.5.0+ ต้องการ **cuDNN 9**
  - ต้อง downgrade CTranslate2 เป็น **4.4.0** เพื่อรองรับ cuDNN 8
- **Location**:
  - System: `/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib` (อาจ reset)
  - PyTorch: `/usr/local/lib/python3.10/dist-packages/torch/lib` (มี cuDNN v8)
- **วิธีแก้**: ใช้ `scripts/pod/fix-ctranslate2-cudnn8.sh` เพื่อ downgrade CTranslate2
- **Script**: `scripts/pod/setup-cudnn-path.sh` สำหรับ setup `LD_LIBRARY_PATH`

### 4. **System Libraries อื่นๆ** (ถ้า container ไม่มี)
- `libmagic1` - สำหรับ `python-magic`
- `libsndfile1` - สำหรับ `soundfile`
- `libportaudio2` - สำหรับ audio processing
- `libasound2-dev` - สำหรับ audio
- `portaudio19-dev` - สำหรับ audio development

---

## 🔍 รายละเอียดเพิ่มเติม

### FFmpeg

**System Installation** (หายหลัง restart):
```bash
apt-get install -y ffmpeg
```

**Persistent Installation** (ไม่หาย):
```bash
bash scripts/pod/install-ffmpeg-persistent.sh
# ติดตั้งที่: /workspace/.local/bin/ffmpeg
# ใช้: export PATH="/workspace/.local/bin:$PATH"
```

### tzdata

**System Installation** (หายหลัง restart):
```bash
apt-get install -y tzdata
```

**Persistent Installation** (ไม่หาย):
```bash
bash scripts/pod/install-timezone-persistent.sh
# Copy ไป: /workspace/.local/share/zoneinfo
# ใช้: export TZDIR=/workspace/.local/share/zoneinfo
```

### cuDNN + CTranslate2

**ปัญหาที่พบ**:
- Container: cuDNN 8.7
- CTranslate2 4.5.0+ ต้องการ cuDNN 9
- **Solution**: Downgrade CTranslate2 เป็น 4.4.0

**Fix Script**:
```bash
bash scripts/pod/fix-ctranslate2-cudnn8.sh
```

**Setup LD_LIBRARY_PATH**:
```bash
bash scripts/pod/setup-cudnn-path.sh
source /tmp/cudnn-env.sh
```

---

## 📊 ตารางสรุป

| Package | System Location | Persistent Location | Reset เมื่อ Restart? | วิธีแก้ |
|---------|----------------|---------------------|---------------------|---------|
| **FFmpeg** | `/usr/bin/ffmpeg` | `/workspace/.local/bin/ffmpeg` | ✅ ใช่ | `install-ffmpeg-persistent.sh` |
| **tzdata** | `/usr/share/zoneinfo` | `/workspace/.local/share/zoneinfo` | ✅ ใช่ | `install-timezone-persistent.sh` |
| **cuDNN** | `/usr/local/lib/.../nvidia/cudnn/lib` | `/workspace/.local/nvidia/cudnn/lib` | ⚠️ อาจจะ | `setup-cudnn-path.sh` |
| **CTranslate2** | Python site-packages | `/workspace/.local/lib/python3.10/site-packages` | ❌ ไม่ (ถ้าใช้ `--user`) | `fix-ctranslate2-cudnn8.sh` |

---

## ✅ วิธีใช้งาน

### ครั้งแรก: ติดตั้ง Persistent Versions

```bash
# 1. ติดตั้ง FFmpeg persistent
bash scripts/pod/install-ffmpeg-persistent.sh

# 2. ติดตั้ง tzdata persistent
bash scripts/pod/install-timezone-persistent.sh

# 3. Fix CTranslate2 cuDNN compatibility
bash scripts/pod/fix-ctranslate2-cudnn8.sh

# 4. Setup cuDNN path
bash scripts/pod/setup-cudnn-path.sh
source /tmp/cudnn-env.sh
```

### หลังจาก Restart: Setup Environment

```bash
# Add to PATH และ environment variables
export PATH="/workspace/.local/bin:$PATH"
export TZDIR="/workspace/.local/share/zoneinfo"
source /tmp/cudnn-env.sh  # หรือ run setup-cudnn-path.sh อีกครั้ง
```

---

## 🎯 สรุป

**Packages ที่ reset เมื่อ restart POD**:
1. ✅ **FFmpeg** - ต้องติดตั้ง persistent version
2. ✅ **tzdata** - ต้อง copy ไป persistent volume
3. ✅ **cuDNN** - มี version mismatch กับ CTranslate2 (ต้อง downgrade CTranslate2)

**วิธีแก้**:
- ใช้ scripts ที่มี `-persistent` suffix สำหรับ FFmpeg และ tzdata
- ใช้ `fix-ctranslate2-cudnn8.sh` สำหรับ CTranslate2 compatibility
- ใช้ `setup-cudnn-path.sh` สำหรับ cuDNN library path

---

**Last Updated**: 2025-01-XX  
**Related Scripts**: 
- `scripts/pod/install-ffmpeg-persistent.sh`
- `scripts/pod/install-timezone-persistent.sh`
- `scripts/pod/fix-ctranslate2-cudnn8.sh`
- `scripts/pod/setup-cudnn-path.sh`

