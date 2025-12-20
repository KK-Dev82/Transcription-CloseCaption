# 📋 เปรียบเทียบ Build Scripts

## 🔍 ความแตกต่างระหว่าง Scripts ทั้ง 3 ตัว

### 1. `build-and-push-base-new.sh`

**Dockerfile**: `Dockerfile.base-new`  
**Base Image**: `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`  
**Output Image**: `kksenateacr.azurecr.io/kk-transcription-base:latest`

**Features**:
- ✅ **Complete Dependencies** - มี dependencies ทั้งหมดติดตั้งไว้แล้ว
- ✅ **PyTorch Official Image** - ใช้ PyTorch Official Image (devel)
- ✅ **Ready to Use** - ไม่ต้อง install dependencies หลัง restart POD

**เหมาะสำหรับ**: Production ที่ต้องการ dependencies ครบถ้วน

---

### 2. `build-and-push-runpod-base.sh`

**Dockerfiles**:
- `Dockerfile.runpod-base` → `kk-transcription-runpod-base`
- `Dockerfile.runpod-template` → **`kk-transcription-faster-whisper-runpod-template`** ⭐ (ชื่อใหม่)

**Base Images**:
- `Dockerfile.runpod-base`: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`
- `Dockerfile.runpod-template`: `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`

**Output Images**:
- `kksenateacr.azurecr.io/kk-transcription-runpod-base:latest`
- `kksenateacr.azurecr.io/kk-transcription-faster-whisper-runpod-template:latest` ⭐

**Features**:
- ⚠️ **Minimal Dependencies** - มีแค่ dependencies พื้นฐาน
- ⚠️ **ต้อง Install** - ต้องรัน `install-dependencies.sh` หลัง restart POD
- ✅ **RunPod Optimized** - Template image optimized สำหรับ RunPod
- ✅ **Build เร็ว** - Build เร็วกว่า (~5-10 นาที)

**Usage**:
```bash
# Build template image (ชื่อใหม่)
bash scripts/pod/build-and-push-runpod-base.sh template

# Build base image
bash scripts/pod/build-and-push-runpod-base.sh base

# Build ทั้งสอง
bash scripts/pod/build-and-push-runpod-base.sh all
```

**เหมาะสำหรับ**: Development หรือเมื่อต้องการ minimal image

---

### 3. `build-and-push-runpod-complete.sh`

**Dockerfile**: `Dockerfile.runpod-complete`  
**Base Image**: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`  
**Output Image**: `kksenateacr.azurecr.io/kk-transcription-runpod-complete:latest`

**Features**:
- ✅ **Complete Dependencies** - มี dependencies ทั้งหมดติดตั้งไว้แล้ว
- ✅ **Runtime Image** - ใช้ runtime image (เล็กกว่า devel)
- ✅ **Ready to Use** - ไม่ต้อง install dependencies หลัง restart POD

**เหมาะสำหรับ**: Production ที่ต้องการ dependencies ครบถ้วนแต่ใช้ runtime image

---

## 📊 ตารางเปรียบเทียบ

| Script | Dockerfile | Base Image | Output Image | Dependencies | Build Time |
|--------|-----------|------------|--------------|--------------|------------|
| `build-and-push-base-new.sh` | `Dockerfile.base-new` | `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | `kk-transcription-base` | ✅ Complete | ~20-30 นาที |
| `build-and-push-runpod-base.sh` (base) | `Dockerfile.runpod-base` | `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` | `kk-transcription-runpod-base` | ⚠️ Minimal | ~5-10 นาที |
| `build-and-push-runpod-base.sh` (template) | `Dockerfile.runpod-template` | `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | **`kk-transcription-faster-whisper-runpod-template`** ⭐ | ⚠️ Minimal | ~5-10 นาที |
| `build-and-push-runpod-complete.sh` | `Dockerfile.runpod-complete` | `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` | `kk-transcription-runpod-complete` | ✅ Complete | ~20-30 นาที |

---

## 🎯 แนะนำ

### สำหรับ Production (ต้องการ dependencies ครบ):
- ✅ **`build-and-push-base-new.sh`** - ใช้ PyTorch Official + Complete Dependencies
- ✅ **`build-and-push-runpod-complete.sh`** - ใช้ Runtime Image + Complete Dependencies

### สำหรับ Development (ต้องการ minimal):
- ⚠️ **`build-and-push-runpod-base.sh template`** - Minimal Dependencies (ต้อง install เอง)
  - **ชื่อใหม่**: `kk-transcription-faster-whisper-runpod-template` ⭐

---

## ✅ การเปลี่ยนแปลง

**เปลี่ยนชื่อ Image**:
- **เดิม**: `kk-transcription-runpod-template`
- **ใหม่**: `kk-transcription-faster-whisper-runpod-template` ⭐

**Script**: `build-and-push-runpod-base.sh` (template build)

---

**Last Updated**: 2025-01-XX

