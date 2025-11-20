# เปรียบเทียบการ Build: Local Script vs GitHub Actions

## 🔍 สรุปปัญหา

Images ใน ACR มีเฉพาะ `arm64` แต่ Staging server ต้องการ `linux/amd64` ทำให้เกิด error:
```
no matching manifest for linux/amd64 in the manifest list entries
```

## 📊 เปรียบเทียบทั้งสองวิธี

### 1. Local Build Script (`build-and-push-acr.sh`)

#### ✅ ข้อดี:
- Build จากเครื่อง local (เร็วกว่า ไม่ต้องรอ CI/CD)
- ไม่มีปัญหา disk space (เหมือน GitHub Actions)
- ควบคุมได้ง่าย

#### ❌ ข้อเสีย:
- **บน Mac M1/M2 (ARM64)**: Docker Buildx อาจ build เป็น `arm64` แทน `linux/amd64` แม้จะระบุ `--platform linux/amd64`
- ต้องมี Docker, Azure CLI ติดตั้งบนเครื่อง
- ต้อง login ACR เอง

#### 🔧 วิธีทำงาน:
```bash
# สร้าง buildx builder ด้วย docker-container driver
docker buildx create --use --name acr-builder --driver docker-container

# Build และ push (ระบุ --platform linux/amd64)
docker buildx build --platform linux/amd64 --push ...
```

#### ⚠️ ปัญหา:
- Builder อาจไม่ support cross-platform compilation ได้ถูกต้อง
- QEMU emulation บน Mac อาจทำงานไม่สมบูรณ์
- ผลลัพธ์: Images เป็น `arm64` แทน `linux/amd64`

---

### 2. GitHub Actions (`build-simple.yml`)

#### ✅ ข้อดี:
- **Build บน `ubuntu-latest` (AMD64)** → Build เป็น `linux/amd64` โดยอัตโนมัติ
- ไม่ต้องติดตั้ง Docker บนเครื่อง local
- Automated workflow (trigger เมื่อ push code)
- ประวัติการ build ใน GitHub

#### ❌ ข้อเสีย:
- ❌ **ตอนนี้ DISABLED** เนื่องจากปัญหา disk space ใน GitHub Actions runner
- ใช้เวลานานกว่า (ต้องรอ CI/CD)
- ต้อง configure secrets (ACR_USERNAME, ACR_PASSWORD)

#### 🔧 วิธีทำงาน:
```yaml
# Build บน ubuntu-latest (AMD64)
- uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64
    push: true
```

#### ✅ ผลลัพธ์:
- Images จะเป็น `linux/amd64` ถูกต้อง 100% (เพราะ build บน AMD64)

---

## 🎯 วิธีแก้ไขปัญหา

### วิธีที่ 1: แก้ไข Local Build Script (แนะนำ)

แก้ไข `build-and-push-acr.sh` ให้แน่ใจว่า build เป็น `linux/amd64`:

```bash
# 1. สร้าง builder ใหม่ด้วย multi-platform support
docker buildx rm acr-builder 2>/dev/null || true
docker buildx create --use --name acr-builder \
    --driver docker-container \
    --bootstrap \
    --platform linux/amd64,linux/arm64

# 2. Build ด้วย --load=false และ --platform linux/amd64
docker buildx build \
    --platform linux/amd64 \
    --load=false \
    --push \
    ...
```

### วิธีที่ 2: ใช้ GitHub Actions (แนะนำถ้าไม่มีปัญหา disk space)

Enable `build-simple.yml` กลับมา และแก้ปัญหา disk space:
- เพิ่ม cleanup steps
- ลด cache size
- ใช้ `.dockerignore` เพื่อลด build context

### วิธีที่ 3: Build บน Linux Server โดยตรง

SSH เข้า Linux server (AMD64) แล้ว build จากที่นั่น:
```bash
# บน Linux server
./scripts/build-and-push-acr.sh
```

---

## 🔍 ตรวจสอบ Manifest

ตรวจสอบว่า image มี platform ถูกต้อง:

```bash
# Login ACR
az acr login --name kksenateacr

# ตรวจสอบ manifest
docker manifest inspect kksenateacr.azurecr.io/kk-transcription:alpha-dev

# ควรเห็น:
# "platform": {
#   "architecture": "amd64",
#   "os": "linux"
# }
```

---

## 📋 Checklist ก่อน Build

- [ ] ตรวจสอบ Docker buildx builder รองรับ multi-platform
- [ ] ระบุ `--platform linux/amd64` อย่างชัดเจน
- [ ] ตรวจสอบ manifest หลัง build ว่าเป็น `amd64`
- [ ] Staging server เป็น `linux/amd64`

---

## 🚀 คำแนะนำ

**ถ้า build จาก Mac M1/M2:**
1. ใช้วิธีที่ 1 (แก้ไข script ให้แน่ใจว่า cross-compile ถูกต้อง)
2. หรือ SSH เข้า Linux server แล้ว build จากที่นั่น (วิธีที่ 3)

**ถ้า build จาก Linux/AMD64:**
- ใช้ Local Build Script ได้เลย ไม่มีปัญหา

**ถ้าไม่ต้องการ build local:**
- Enable GitHub Actions และแก้ปัญหา disk space

---

## 📝 หมายเหตุ

- Docker Buildx บน Mac M1/M2 ใช้ QEMU emulation สำหรับ cross-platform build
- QEMU emulation อาจทำงานไม่สมบูรณ์กับบาง build process
- วิธีที่แน่นอนที่สุดคือ build บน platform เป้าหมายโดยตรง (AMD64)

