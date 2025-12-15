# FFmpeg Installation Strategy

## 📋 Strategy: Dual Installation Approach

ระบบจะพยายามติดตั้ง FFmpeg ใน 2 วิธีตามลำดับ:

### 1. Persistent Volume (Priority 1)
**Location:** `/workspace/.local/bin/ffmpeg`

**ข้อดี:**
- ✅ Persist หลัง Pod restart
- ✅ ไม่ต้องติดตั้งใหม่ทุกครั้ง

**ข้อจำกัด:**
- อาจไม่รองรับในบาง container environments
- ต้องมี network access สำหรับ download

### 2. System Package (Fallback)
**Location:** `/usr/bin/ffmpeg` (system PATH)

**ข้อดี:**
- ✅ ทำงานได้ทันที (ถ้า container รองรับ)
- ✅ ไม่ต้อง download binary

**ข้อจำกัด:**
- ❌ หายไปหลัง Pod restart
- ต้องติดตั้งใหม่ทุกครั้ง

## 🔄 Installation Flow

```
1. Check persistent volume (/workspace/.local/bin/ffmpeg)
   ↓ (not found)
2. Check system PATH (which ffmpeg)
   ↓ (not found)
3. Try install to persistent volume
   ↓ (failed or not supported)
4. Fallback to system installation (apt-get)
   ↓ (success)
5. Use system FFmpeg (will be lost after restart)
```

## 📝 Implementation

### Start Scripts
- `start-service-daemon.sh`
- `restart-service-daemon.sh`

**Logic:**
1. ตรวจสอบ persistent volume ก่อน
2. ตรวจสอบ system PATH
3. ถ้าไม่พบ → ลองติดตั้ง persistent volume
4. ถ้า persistent volume ล้มเหลว → fallback ไป system installation
5. Worker PATH จะรวมทั้ง persistent และ system locations

### Worker PATH Configuration

```bash
# Priority order:
PATH="/workspace/.local/bin:/usr/bin:/usr/local/bin:$PATH"
```

Worker จะหา FFmpeg ตามลำดับ:
1. `/workspace/.local/bin/ffmpeg` (persistent)
2. `/usr/bin/ffmpeg` (system)
3. `/usr/local/bin/ffmpeg` (system)

## ✅ Benefits

### Before
- ❌ ติดตั้งเฉพาะ persistent volume
- ❌ ล้มเหลวถ้า persistent volume ไม่รองรับ
- ❌ Video worker ไม่ทำงาน

### After
- ✅ รองรับทั้ง persistent volume และ system package
- ✅ Fallback อัตโนมัติ
- ✅ Video worker ทำงานได้เสมอ (ถ้ามี network)

## 🚨 Container Limitations

### ถ้า Container ไม่รองรับ Persistent Volume
- ระบบจะใช้ system installation แทน
- FFmpeg จะหายไปหลัง restart
- ต้องติดตั้งใหม่ทุกครั้ง (auto-install ใน start script)

### ถ้า Container ไม่มี Network Access
- ไม่สามารถ download static binary ได้
- ไม่สามารถใช้ apt-get ได้
- ต้อง manual installation

## 🔧 Manual Installation (if needed)

### Option 1: Upload Static Binary
```bash
# On local machine
wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-amd64

# Upload to Pod
scp -P 13263 ffmpeg-linux-amd64 4000-ada-sc:/workspace/.local/bin/ffmpeg
ssh -p 13263 4000-ada-sc "chmod +x /workspace/.local/bin/ffmpeg"
```

### Option 2: Use Existing FFmpeg
```bash
# If FFmpeg exists in container
ssh -p 13263 4000-ada-sc "cp \$(which ffmpeg) /workspace/.local/bin/ffmpeg && chmod +x /workspace/.local/bin/ffmpeg"
```

## 📊 Summary

| Method | Location | Persists? | Auto-install? |
|--------|----------|-----------|---------------|
| **Persistent Volume** | `/workspace/.local/bin/ffmpeg` | ✅ Yes | ✅ Yes |
| **System Package** | `/usr/bin/ffmpeg` | ❌ No | ✅ Yes (fallback) |

**Result:** ระบบจะพยายามติดตั้ง FFmpeg ให้เสมอ ไม่ว่าจะใช้วิธีไหนก็ตาม

