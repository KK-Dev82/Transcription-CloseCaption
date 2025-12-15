# Video Worker FFmpeg Setup

## 📋 ปัญหา

ทุกครั้งที่ restart Pod Container, video-worker มีปัญหาเพราะ **FFmpeg ไม่ได้ติดตั้ง** หรือ **หายไปหลัง restart**

## 🔍 สาเหตุ

1. **Pod Container ไม่มี FFmpeg pre-installed**
   - RunPod containers อาจจะไม่มี FFmpeg ติดตั้งมาให้
   - เมื่อ restart container, FFmpeg ที่ติดตั้งไว้จะหายไป (ถ้าไม่ persistent)

2. **Start Script ไม่ได้ตรวจสอบ FFmpeg**
   - `start-service-daemon.sh` ไม่ได้ตรวจสอบหรือติดตั้ง FFmpeg ก่อน start worker
   - Worker พยายามใช้ FFmpeg แต่ไม่พบ → Error

3. **FFmpeg เป็น System Dependency**
   - FFmpeg เป็น system package (ไม่ใช่ Python package)
   - ต้องติดตั้งผ่าน `apt-get` (Ubuntu/Debian)
   - Python `ffmpeg-python` library เป็นแค่ wrapper

## ✅ วิธีแก้ไข

### 1. เพิ่ม FFmpeg Check ใน Start Scripts

**ไฟล์ที่แก้ไข:**
- `scripts/pod/start-service-daemon.sh`
- `scripts/pod/restart-service-daemon.sh`

**การเปลี่ยนแปลง:**
- เพิ่มการตรวจสอบ FFmpeg ก่อน start video-worker
- Auto-install FFmpeg ถ้าไม่พบ
- แสดง warning ถ้าไม่สามารถติดตั้งได้

### 2. FFmpeg Installation Logic

```bash
# Check FFmpeg installation
if ! command -v ffmpeg > /dev/null 2>&1; then
    echo "❌ FFmpeg not found - installing..."
    if command -v apt-get > /dev/null 2>&1; then
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq ffmpeg > /dev/null 2>&1
        # Verify installation
        if command -v ffmpeg > /dev/null 2>&1; then
            echo "✅ FFmpeg installed successfully"
        else
            echo "❌ FFmpeg installation failed"
        fi
    fi
else
    echo "✅ FFmpeg already installed"
fi
```

### 3. ตรวจสอบ ffprobe

- `ffprobe` มักจะมาพร้อมกับ FFmpeg
- ใช้สำหรับ probe video metadata
- ตรวจสอบว่ามีหรือไม่

## 🔧 Dependencies

### System Dependencies
- **FFmpeg**: สำหรับ video/audio processing
- **ffprobe**: สำหรับ video metadata probing

### Python Dependencies
- **ffmpeg-python**: Python wrapper สำหรับ FFmpeg (ติดตั้งผ่าน pip)

## 📝 Installation Order

1. **System Dependencies** (FFmpeg)
   ```bash
   apt-get install -y ffmpeg
   ```

2. **Python Dependencies**
   ```bash
   pip install --user ffmpeg-python
   ```

## 🚨 Troubleshooting

### FFmpeg Not Found
```bash
# Check if FFmpeg is installed
which ffmpeg
ffmpeg -version

# Install if missing
apt-get update
apt-get install -y ffmpeg
```

### FFmpeg Installation Failed
- ตรวจสอบ network connection
- ตรวจสอบ apt-get permissions
- ตรวจสอบ disk space

### Video Worker Still Fails
- ตรวจสอบ logs: `tail -f logs/video-worker-errors.log`
- ตรวจสอบ FFmpeg path: `which ffmpeg`
- ตรวจสอบ Python ffmpeg-python: `python3 -c "import ffmpeg"`

## ✅ Verification

### After Restart
```bash
# Check FFmpeg
ffmpeg -version

# Check ffprobe
ffprobe -version

# Check Python wrapper
python3 -c "import ffmpeg; print(ffmpeg.__version__)"
```

### Test Video Worker
```bash
# Check worker logs
tail -f logs/video-worker.log

# Check for FFmpeg errors
grep -i "ffmpeg\|ffprobe" logs/video-worker-errors.log
```

## 📊 Impact

### Before Fix
- ❌ Video worker fails after Pod restart
- ❌ FFmpeg errors in logs
- ❌ Audio extraction fails
- ❌ Video processing fails

### After Fix
- ✅ FFmpeg auto-installed on restart
- ✅ Video worker starts successfully
- ✅ Audio extraction works
- ✅ Video processing works

## 🔄 Next Steps

1. ✅ Added FFmpeg check to start scripts
2. ⚠️ Consider adding FFmpeg to Dockerfile (if using Docker)
3. ⚠️ Consider persistent FFmpeg installation (if Pod supports it)
4. ⚠️ Add FFmpeg version check to health endpoint

