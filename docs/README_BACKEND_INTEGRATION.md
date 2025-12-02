# 📚 Backend Integration Documentation

เอกสารทั้งหมดสำหรับการเชื่อมต่อ Transcription Service กับ Backend Local

---

## 📖 เอกสารทั้งหมด

### 1. **BACKEND_INTEGRATION.md** - คู่มือ Integration
   - Flow การทำงาน
   - API Endpoints
   - Request/Response formats
   - Configuration guide

### 2. **BACKEND_LOCAL_SETUP.md** - คู่มือ Setup
   - Prerequisites
   - Configuration สำหรับแต่ละ service
   - Quick Start guide
   - Testing steps

---

## 🚀 Quick Start

### 1. อ่านเอกสาร

เริ่มจาก: **BACKEND_LOCAL_SETUP.md**

### 2. ตั้งค่า Configuration

- Backend: `appsettings.Development.json`
- Transcription Service: `.env`

### 3. เริ่ม Services

```bash
# Backend
cd senate-backend && dotnet run

# Transcription Service
cd transcription-close-caption-service
source scripts/pod/setup-gpu-env.sh  # ถ้าใช้ GPU
python -m uvicorn app.main:app --port 8001
```

### 4. ทดสอบ

```bash
# Test integration
bash scripts/test/test-backend-integration.sh
```

---

## 📋 Flow Summary

```
1. Frontend → Backend: Upload + Start transcription
2. Backend → Transcription Service: POST /transcribe/
3. Transcription Service: Process transcription
4. Transcription Service → Backend: POST callback_url
5. Backend: Save to database + Notify Frontend
```

---

## 🔗 Related Documentation

- **ENVIRONMENT_SUMMARY.md** - Environment configuration
- **BACKEND_INTEGRATION.md** - Integration guide
- **BACKEND_LOCAL_SETUP.md** - Setup guide

---

## 🧪 Test Scripts

1. **test-backend-integration.sh** - ทดสอบการเชื่อมต่อ
2. **test-transcription-callback.sh** - ทดสอบ callback flow

---

**Last Updated**: 2025-12-02

