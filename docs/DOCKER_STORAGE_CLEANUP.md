# 🧹 Docker Storage Cleanup Guide

## ❌ ปัญหา

เมื่อ build Docker image บน macOS พบ error:
```
ERROR: failed to build: failed to solve: Internal: error committing ...: 
write /var/lib/docker/buildkit/containerd-overlayfs/metadata_v2.db: input/output error
```

**สาเหตุ**: Docker storage เต็ม

---

## ✅ วิธีแก้ไข

### 1. ตรวจสอบ Docker Storage Usage

```bash
docker system df
```

### 2. Cleanup Docker Storage

#### วิธีที่ 1: Cleanup ทั้งหมด (แนะนำ)

```bash
# ลบ containers, images, networks, build cache ที่ไม่ได้ใช้
docker system prune -a --volumes

# หรือแค่ build cache
docker builder prune -a
```

#### วิธีที่ 2: Cleanup เฉพาะ Build Cache

```bash
# ลบ build cache ทั้งหมด
docker builder prune -a -f

# ลบ build cache ที่เก่ากว่า 24 ชั่วโมง
docker builder prune --filter "until=24h"
```

#### วิธีที่ 3: ลบ Images ที่ไม่ได้ใช้

```bash
# ดู images ทั้งหมด
docker images

# ลบ images ที่ไม่ได้ tag (dangling)
docker image prune -a

# ลบ images เฉพาะที่ต้องการ
docker rmi <image-id>
```

### 3. ตรวจสอบ Disk Space

```bash
# macOS
df -h

# ตรวจสอบ Docker Desktop disk usage
# ไปที่ Docker Desktop > Settings > Resources > Advanced
# ดู Disk image size และ Disk space used
```

---

## 🔧 Build สำหรับ RunPod

### Platform Mismatch

**macOS (M1/M2)**: ARM64 (linux/arm64)  
**RunPod**: AMD64 (linux/amd64)

### วิธีแก้ไข

Script `build-and-push-base-new.sh` จะ auto-detect architecture และใช้ `--platform=linux/amd64` อัตโนมัติ

```bash
# Build script จะตรวจสอบ architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    docker build --platform=linux/amd64 ...
fi
```

---

## 📋 Checklist

- [ ] ตรวจสอบ Docker storage: `docker system df`
- [ ] Cleanup build cache: `docker builder prune -a`
- [ ] Cleanup unused images: `docker image prune -a`
- [ ] ตรวจสอบ disk space: `df -h`
- [ ] Build ด้วย `--platform=linux/amd64` (auto-detect)

---

## ⚠️ หมายเหตุ

### Build Cache

- Docker จะใช้ cache จาก layer ที่ไม่เปลี่ยน
- แต่ถ้า platform ต่างกัน (ARM64 vs AMD64) cache อาจไม่ใช้ได้
- ต้อง build ใหม่ทั้งหมดเมื่อเปลี่ยน platform

### Storage Management

- Build cross-platform (ARM64 → AMD64) ใช้ storage มากกว่า
- แนะนำให้ cleanup build cache หลัง build เสร็จ
- ใช้ `docker system prune` เป็นประจำ

---

**Last Updated**: 2025-01-XX  
**Issue**: Docker storage full, I/O error  
**Solution**: Cleanup build cache + use --platform=linux/amd64

