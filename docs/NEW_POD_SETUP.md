# 🚀 New Pod Setup Guide

## Overview

คู่มือสำหรับ setup Pod ใหม่ เริ่มตั้งแต่ clone repository, download model, และทดสอบกับวิดีโอทั้ง 3 ตัว

## Prerequisites

- SSH access to RunPod server
- SSH key configured (`~/.ssh/id_ed25519`)
- SSH config updated (see below)

## SSH Configuration

SSH config has been updated:
```
Host calm-pink-turtle
     HostName 87.197.127.62
     Port 41031
     User root
     IdentityFile ~/.ssh/id_ed25519
```

## Step-by-Step Setup

### Step 1: Clone Repository and Setup

```bash
cd /path/to/transcription-close-caption-service
bash scripts/pod/setup-new-pod.sh
```

**สคริปต์จะทำ:**
1. Clone repository จาก GitHub: `https://github.com/KK-Dev82/Transcription-CloseCaption.git`
2. Run `setup-pod.sh` เพื่อ setup dependencies และ configuration
3. Download Whisper model `medium` (ใช้เวลา ~2-5 นาที)

### Step 2: Download Test Videos

```bash
bash scripts/pod/download-test-videos.sh
```

**วิดีโอที่จะ download:**
- `v05-1.mp4` (5 วินาที) - จาก `https://korrakang.com/video/v05-1.mp4`
- `v10-1.mp4` (10 นาที) - จาก `https://korrakang.com/video/v10-1.mp4`
- `v60-1.mp4` (60 นาที) - จาก `https://korrakang.com/video/v60-1.mp4`

### Step 3: Start Services

```bash
# บน RunPod server
cd /workspace/transcription-service
bash scripts/pod/start-pod.sh
```

**หรือจาก local:**
```bash
ssh calm-pink-turtle "cd /workspace/transcription-service && bash scripts/pod/start-pod.sh"
```

### Step 4: Test Transcription

```bash
# ทดสอบกับวิดีโอทั้ง 3 ตัว
bash scripts/pod/test-all-videos.sh medium
```

**สคริปต์จะ:**
- ทดสอบกับ `v05-1.mp4` (timeout: 30 วินาที)
- ทดสอบกับ `v10-1.mp4` (timeout: 3 นาที)
- ทดสอบกับ `v60-1.mp4` (timeout: 10 นาที)
- แสดงสรุปผลการทดสอบ

## Manual Testing

### Test Individual Video

```bash
# บน RunPod server
cd /workspace/transcription-service
bash scripts/pod/test-transcription.sh uploads/v10-1.mp4 medium
```

### Test with Timeout (3 minutes)

```bash
bash scripts/pod/test-3min-timeout.sh medium
```

## Expected Results

### v05-1.mp4 (5 seconds)
- **Expected time:** < 10 seconds
- **Speed:** ≥ 0.5x real-time

### v10-1.mp4 (10 minutes)
- **Expected time:** 1-2 minutes
- **Speed:** ≥ 5x real-time
- **GPU Utilization:** ≥ 80%

### v60-1.mp4 (60 minutes)
- **Expected time:** 10-15 minutes
- **Speed:** ≥ 4x real-time
- **GPU Utilization:** ≥ 80%

## Troubleshooting

### Connection Issues

```bash
# Test SSH connection
ssh calm-pink-turtle "echo 'Connection OK'"

# If connection fails, check:
# 1. IP and port are correct
# 2. SSH key is correct
# 3. Pod is running on RunPod dashboard
```

### Service Issues

```bash
# Check services status
ssh calm-pink-turtle "cd /workspace/transcription-service && bash scripts/pod/check-pod.sh"

# Check logs
ssh calm-pink-turtle "tail -f /tmp/video-worker.log"
ssh calm-pink-turtle "tail -f /tmp/main-api.log"
```

### Model Download Issues

```bash
# Manual model download
ssh calm-pink-turtle "cd /workspace/transcription-service && python3 -c 'import whisper; whisper.load_model(\"medium\")'"
```

### Video Download Issues

```bash
# Manual video download
ssh calm-pink-turtle "cd /workspace/transcription-service && bash scripts/pod/download-video.sh https://korrakang.com/video/v10-1.mp4 uploads/"
```

## Quick Reference

```bash
# Setup everything
bash scripts/pod/setup-new-pod.sh

# Download videos
bash scripts/pod/download-test-videos.sh

# Start services (on server)
cd /workspace/transcription-service && bash scripts/pod/start-pod.sh

# Test all videos
bash scripts/pod/test-all-videos.sh medium

# Test single video with timeout
bash scripts/pod/test-3min-timeout.sh medium
```

## Notes

- **Model:** `medium` is recommended for RTX 4080 Super (16GB)
- **Workers:** Default is 5, but can be adjusted in `.env.runpod`
- **Parallel Processing:** Enabled by default (`WHISPER_USE_THREAD_LOCAL=true`)
- **Timeout:** If transcription takes longer than expected, check GPU utilization and adjust `TRANSCRIPTION_MAX_WORKERS`

