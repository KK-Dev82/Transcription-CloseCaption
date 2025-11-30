# 📥 Video Download Guide

คู่มือการ Download และจัดการ Video Files บน Pod

---

## 📋 Overview

เนื่องจาก Pod Container อาจ restart ทำให้ permission เปลี่ยน และการ SSH เข้า Pod เพื่อ copy ไฟล์ค่อนข้างวุ่นวาย จึงแนะนำให้ใช้ script สำหรับ download/copy video files

**2 วิธีหลัก:**
1. **Download จาก URL:** ใช้ `download-video.sh` (รันบน Pod)
2. **Upload จาก Local Machine:** ใช้ `download-video-from-local.sh` (รันบน MacOS)

---

## 🚀 วิธีที่ 1: Download จาก URL (บน Pod)

**ใช้เมื่อ:**
- Video อยู่บน URL (HTTP/HTTPS)
- ต้องการ download โดยตรงบน Pod

**ขั้นตอน:**

```bash
# SSH เข้า Pod
ssh root@<pod-ip> -p <port>

# ไปที่ project directory
cd /workspace/transcription-service

# Download video จาก URL
bash scripts/pod/download-video.sh https://example.com/video.mp4 uploads/

# หรือ download ไปที่ test-files
bash scripts/pod/download-video.sh https://example.com/video.mp4 test-files/
```

**Output:**
- ไฟล์จะถูก download ไปที่ `uploads/` หรือ `test-files/`
- Permission จะถูกตั้งค่าให้ถูกต้องอัตโนมัติ
- แสดง file size และ duration (ถ้ามี ffprobe)

---

## 🚀 วิธีที่ 2: Upload จาก Local Machine (MacOS)

**ใช้เมื่อ:**
- Video อยู่บน Local Machine (MacOS)
- ต้องการ upload ผ่าน SCP

**ขั้นตอน:**

```bash
# จาก Local Machine (MacOS)
cd /Users/athip-ch/Work/Korrakang/KK_Client_Work/KSC/บันทึกการประชุม-สว/Code/transcription-close-caption-service

# Upload video ไปยัง Pod
bash scripts/pod/download-video-from-local.sh \
  /path/to/video.mp4 \
  <pod-ip> \
  <pod-ssh-port> \
  uploads/
```

**ตัวอย่าง:**
```bash
bash scripts/pod/download-video-from-local.sh \
  ~/Downloads/test-video.mp4 \
  205.196.17.108 \
  13027 \
  uploads/
```

**Output:**
- ไฟล์จะถูก upload ไปที่ `/workspace/transcription-service/uploads/`
- Permission จะถูกตั้งค่าให้ถูกต้องอัตโนมัติ
- ตรวจสอบ file size เพื่อยืนยันว่า upload สำเร็จ

---

## 📁 Directory Structure

```
/workspace/transcription-service/
├── uploads/          # สำหรับ video files ที่จะใช้ transcription
├── test-files/       # สำหรับ test videos
├── storage/          # สำหรับ transcription results
└── temp/             # สำหรับ temporary files
```

**แนะนำ:**
- ใช้ `uploads/` สำหรับ video files ที่จะใช้ transcription
- ใช้ `test-files/` สำหรับ test videos

---

## 🔧 Permission Issues

**ปัญหา:** Permission เปลี่ยนหลัง restart Pod

**แก้ไข:**

```bash
# บน Pod
cd /workspace/transcription-service

# Fix permissions
chmod -R 644 uploads/* test-files/* 2>/dev/null || true
chmod 755 uploads test-files 2>/dev/null || true
```

**หรือใช้ script:**
```bash
# Script จะจัดการ permission อัตโนมัติ
bash scripts/pod/download-video.sh <source> <dest>
```

---

## 🧪 ทดสอบ Transcription หลัง Download

```bash
# บน Pod
cd /workspace/transcription-service

# ทดสอบ transcription
bash scripts/pod/test-transcription-performance.sh uploads/video.mp4 large
```

---

## 📊 ตัวอย่างการใช้งาน

### Download จาก URL:
```bash
# บน Pod
bash scripts/pod/download-video.sh \
  https://example.com/meeting-video.mp4 \
  uploads/
```

### Upload จาก Local:
```bash
# จาก MacOS
bash scripts/pod/download-video-from-local.sh \
  ~/Downloads/meeting-video.mp4 \
  205.196.17.108 \
  13027 \
  uploads/
```

### ทดสอบ Transcription:
```bash
# บน Pod
bash scripts/pod/test-transcription-performance.sh \
  uploads/meeting-video.mp4 \
  large
```

---

## 🔗 Related Documents

- **Performance Testing:** `docs/RunPod-Z2/PERFORMANCE_TESTING.md`
- **Model Recommendations:** `docs/RunPod-Z2/MODEL_RECOMMENDATIONS.md`
- **Test Scripts:** `scripts/pod/README.md`

---

**Last Updated:** 2024-12-19

