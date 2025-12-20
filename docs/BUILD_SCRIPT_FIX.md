# 🔧 แก้ไข Build Script - Path Issue

## ❌ ปัญหาที่พบ

เมื่อรัน `bash scripts/pod/build-and-push-base-new.sh` พบ error:
```
❌ Dockerfile not found: Dockerfile.base-new
```

## 🔍 สาเหตุ

`PROJECT_DIR` ถูกคำนวณผิด:
- **ผิด**: `SCRIPT_DIR/..` → `/workspace/transcription-service/scripts`
- **ถูก**: `SCRIPT_DIR/../..` → `/workspace/transcription-service`

## ✅ แก้ไขแล้ว

แก้ไข `scripts/pod/build-and-push-base-new.sh`:
```bash
# เดิม (ผิด)
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# แก้ไข (ถูก)
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
```

## ✅ ตรวจสอบแล้ว

```bash
# ตอนนี้ script พบ Dockerfile แล้ว
📋 Build Configuration:
   ACR: kksenateacr
   Image: kksenateacr.azurecr.io/kk-transcription-base
   Dockerfile: Dockerfile.base-new
   Version: 20251220-084414
```

## ⚠️ หมายเหตุ

**Docker ไม่มีใน RunPod Container**:
- Script ทำงานถูกต้องแล้ว (พบ Dockerfile)
- แต่ต้อง run บนเครื่องที่มี Docker (เช่น Azure Cloud Shell, Local Machine, หรือ GitHub Actions)

---

**Last Updated**: 2025-01-XX  
**Commit**: Fixed PROJECT_DIR path calculation

