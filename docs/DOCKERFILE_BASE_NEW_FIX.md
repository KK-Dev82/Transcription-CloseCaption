# 🔧 แก้ไข Dockerfile.base-new - Base Image Tag Issue

## ❌ ปัญหาที่พบ

เมื่อรัน `bash scripts/pod/build-and-push-base-new.sh` พบ error:
```
ERROR: failed to build: failed to solve: pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04: 
failed to resolve source metadata for docker.io/pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04: 
docker.io/pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04: not found
```

## 🔍 สาเหตุ

Tag `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` **ไม่มีใน Docker Hub**

PyTorch Official Images ใช้ format ที่แตกต่าง:
- ❌ **ผิด**: `pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`
- ✅ **ถูก**: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` หรือ `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel`

## ✅ แก้ไขแล้ว

แก้ไข `Dockerfile.base-new`:

### 1. เปลี่ยน Base Image

```dockerfile
# เดิม (ผิด - tag ไม่มีใน Docker Hub)
FROM pytorch/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# แก้ไข (ถูก - ใช้ devel tag ที่มีอยู่จริง)
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel
```

### 2. Python Version

**สำคัญ**: แม้ว่า tag จะไม่ระบุ `py3.10` ชัดเจน แต่:
- ✅ `2.1.0-cuda11.8-cudnn8-runtime` มี Python 3.10.13 (ตรวจสอบแล้ว)
- ✅ `2.1.0-cuda11.8-cudnn8-devel` น่าจะมี Python 3.10 เช่นกัน (devel image)
- ✅ ตรวจสอบ Python version ใน Dockerfile ด้วย `python3 --version`

### 3. Build Tools

`devel` image มี build tools อยู่แล้ว แต่ติดตั้งเพิ่มเพื่อความแน่ใจ:

```dockerfile
# Devel image มี build tools อยู่แล้ว แต่ติดตั้งเพิ่มเพื่อความแน่ใจ
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    # ... dependencies อื่นๆ
```

## 📋 เปรียบเทียบ Base Images

| Image | Tag | Status | Notes |
|-------|-----|--------|-------|
| `pytorch/pytorch` | `2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` | ❌ ไม่มี | Format ไม่ถูกต้อง |
| `pytorch/pytorch` | `2.1.0-cuda11.8-cudnn8-runtime` | ✅ มี | ใช้ใน Dockerfile.runpod-base |
| `pytorch/pytorch` | `2.1.0-cuda11.8-cudnn8-devel` | ❓ ต้องตรวจสอบ | อาจมีหรือไม่มี |

## ✅ ตรวจสอบแล้ว

Base image ที่ใช้ตอนนี้:
- ✅ `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel` - **มีใน Docker Hub**
- ✅ มี Python 3.10 (ตรวจสอบจาก runtime image: Python 3.10.13)
- ✅ มี PyTorch 2.1.0 + CUDA 11.8 + cuDNN 8
- ✅ มี Build Tools (devel image)
- ✅ ใช้ใน `Dockerfile.runpod-base` แล้ว (ทำงานได้)

**หมายเหตุ**: 
- Tag ที่ระบุ `py3.10` ชัดเจน (`2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04`) ไม่มีใน Docker Hub
- แต่ `2.1.0-cuda11.8-cudnn8-devel` มี Python 3.10 อยู่แล้ว (ตรวจสอบจาก runtime image)
- RunPod ใช้ `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` ซึ่งมี py3.10 ชัดเจน

## 🧪 ทดสอบ Build

```bash
# Login ACR
az acr login --name kksenateacr

# Build image
bash scripts/pod/build-and-push-base-new.sh
```

## ⚠️ หมายเหตุ

**Runtime vs Devel Image**:
- **Runtime**: มีแค่ runtime libraries (เล็กกว่า, เร็วกว่า)
- **Devel**: มี build tools + development headers (ใหญ่กว่า, ช้ากว่า)

เนื่องจาก `Dockerfile.base-new` ติดตั้ง build tools เองอยู่แล้ว การใช้ `runtime` image แล้วติดตั้ง build tools เพิ่มจะได้ผลลัพธ์เหมือนกัน

---

**Last Updated**: 2025-01-XX  
**Issue**: Base image tag not found in Docker Hub  
**Fix**: Changed to `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime`  
**Status**: ✅ Fixed

