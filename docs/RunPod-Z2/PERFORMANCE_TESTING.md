# 🧪 Performance Testing Guide

คู่มือการทดสอบ Performance ของ Transcription Service

---

## 📋 Overview

ทดสอบและวัดเวลาในการ transcription เพื่อ:
- ตรวจสอบว่า performance ตรงตามเป้าหมายหรือไม่
- เปรียบเทียบ performance ระหว่าง model sizes
- ตรวจสอบ GPU utilization

**เป้าหมาย:**
- 10 นาที video → ~1-2 นาที transcription (medium model + GPU 4080)
- 30 นาที video → ~3-5 นาที transcription
- 1 ชั่วโมง video → ~6-10 นาที transcription

---

## 🚀 วิธีทดสอบ

### Option 1: ใช้ Performance Test Script (แนะนำ)

**จาก RunPod Pod:**

```bash
# SSH เข้า Pod
ssh root@<pod-ip> -p <port>

# ไปที่ project directory
cd /workspace/transcription-service

# ทดสอบด้วย video file
bash scripts/pod/test-transcription-performance.sh /path/to/video.mp4 medium
```

**จาก Local Machine (MacOS):**

```bash
# ทดสอบด้วย video file (ใช้ RunPod HTTP Services URL)
bash scripts/pod/test-transcription-performance.sh \
  /path/to/video.mp4 \
  medium \
  https://xxxxx-8001.proxy.runpod.net
```

---

### Option 2: ใช้ Upload and Test Script

**จาก Local Machine:**

```bash
bash scripts/pod/upload-and-test.sh \
  /path/to/video.mp4 \
  <pod-ip> \
  8001 \
  medium
```

---

## 📊 Performance Metrics

Script จะแสดง:

### 1. File Information
- File size
- Video duration

### 2. Timing
- Upload time
- Transcription time
- Total time

### 3. Performance Metrics
- Ratio (transcription time / video duration)
- Speedup (video duration / transcription time)

### 4. GPU Usage
- GPU memory usage
- GPU utilization
- (ถ้าใช้ GPU)

### 5. Transcription Result
- Full text (แสดง 500 ตัวอักษรแรก)
- Word count
- Character count
- Chunk count

---

## 📈 Performance Rating

| Ratio | Rating | Description |
|-------|--------|-------------|
| ≤ 1x | ✅ Excellent | Transcription เร็วกว่า video duration |
| ≤ 2x | ✅ Good | Transcription ใช้เวลา 2x video duration |
| ≤ 5x | ⚠️ Acceptable | Transcription ใช้เวลา 5x video duration |
| > 5x | ⚠️ Slow | Transcription ใช้เวลามากกว่า 5x video duration |

---

## 🎯 Expected Performance (GPU 4080 + Medium Model)

| Video Duration | Expected Transcription Time | Ratio |
|----------------|----------------------------|-------|
| 5 seconds | 1-2 seconds | 0.2-0.4x |
| 10 minutes | 1-2 minutes | 0.1-0.2x |
| 30 minutes | 3-5 minutes | 0.1-0.17x |
| 1 hour | 6-10 minutes | 0.1-0.17x |

---

## 📋 Test Checklist

- [ ] Video file พร้อมใช้งาน
- [ ] API health check ผ่าน
- [ ] GPU ทำงาน (nvidia-smi)
- [ ] RabbitMQ connection ผ่าน
- [ ] Model ถูก download แล้ว (medium)
- [ ] Services ทำงาน (check-services.sh)

---

## 🔍 ตรวจสอบ Logs

**ระหว่าง Transcription:**

```bash
# Main API logs
tail -f /tmp/main-api.log

# Video Worker logs
tail -f /tmp/video-worker.log

# Whisper API logs
tail -f /tmp/whisper.log

# GPU usage
watch -n 1 nvidia-smi
```

---

## 📊 ตัวอย่างผลลัพธ์

```
🧪 Testing Transcription Performance

📋 Configuration:
   Video File: /path/to/video.mp4
   Model Size: medium
   API URL: http://localhost:8001

📊 File Information:
   Size: 50M
   Duration: 10m 30s (630 seconds)

⏱️  Timing:
   Upload time: 5s
   Transcription time: 90s
   Total time: 95s

📈 Performance Metrics:
   Video duration: 630s
   Transcription time: 90s
   Ratio (transcribe/video): 0.14x
   Speedup (video/transcribe): 7.00x

✅ Excellent! Transcription is faster than video duration
```

---

## 🔗 Related Documents

- **Test Script:** `scripts/pod/test-transcription-performance.sh`
- **Upload and Test:** `scripts/pod/upload-and-test.sh`
- **Check Services:** `scripts/pod/check-services.sh`

---

**Last Updated:** 2024-12-19

