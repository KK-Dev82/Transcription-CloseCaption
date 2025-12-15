# FFmpeg Persistent Installation

## 📋 ปัญหา

**ทำไมต้องติดตั้ง FFmpeg ทุกครั้ง?**
- FFmpeg เป็น system package (ติดตั้งผ่าน `apt-get`)
- ติดตั้งที่ `/usr/bin/ffmpeg` ซึ่งไม่ใช่ persistent volume
- เมื่อ Pod Container restart, system packages ที่ติดตั้งใหม่จะหายไป
- `/workspace` เป็น persistent volume แต่ FFmpeg binary ต้องอยู่ใน PATH

## ✅ วิธีแก้ไข

### 1. ติดตั้ง FFmpeg Static Binary ไปยัง Persistent Volume

**Location:** `/workspace/.local/bin/ffmpeg`

**ข้อดี:**
- ✅ Persist หลัง Pod restart
- ✅ ไม่ต้องใช้ root permissions
- ✅ Static binary ทำงานได้ทันที
- ✅ ไม่ต้องติดตั้ง dependencies

### 2. Installation Script

**ไฟล์:** `scripts/pod/install-ffmpeg-persistent.sh`

**การทำงาน:**
1. Download FFmpeg static binary จาก GitHub
2. เก็บไว้ที่ `/workspace/.local/bin/`
3. Set executable permissions
4. Add to PATH

### 3. Auto-Installation in Start Scripts

**ไฟล์ที่แก้ไข:**
- `scripts/pod/start-service-daemon.sh`
- `scripts/pod/restart-service-daemon.sh`

**Priority:**
1. **Persistent Volume** (`/workspace/.local/bin/ffmpeg`) - ตรวจสอบก่อน
2. **System PATH** (`/usr/bin/ffmpeg`) - fallback
3. **Auto-install** - ถ้าไม่พบทั้งสองที่

## 🔧 Usage

### Manual Installation

```bash
# Install FFmpeg to persistent volume
bash scripts/pod/install-ffmpeg-persistent.sh
```

### Auto-Installation

FFmpeg จะถูกตรวจสอบและติดตั้งอัตโนมัติเมื่อ:
- Start service: `bash scripts/pod/start-service-daemon.sh`
- Restart service: `bash scripts/pod/restart-service-daemon.sh`

### Verify Installation

```bash
# Check if FFmpeg is in persistent volume
ls -lh /workspace/.local/bin/ffmpeg

# Check version
/workspace/.local/bin/ffmpeg -version

# Check PATH
echo $PATH | grep -o '/workspace/.local/bin'
```

## 📊 Comparison

| Method | Location | Persists? | Requires Root? |
|--------|----------|-----------|----------------|
| **apt-get** | `/usr/bin/ffmpeg` | ❌ No | ✅ Yes |
| **Static Binary** | `/workspace/.local/bin/ffmpeg` | ✅ Yes | ❌ No |

## 🎯 Benefits

### Before Fix
- ❌ FFmpeg หายไปหลัง Pod restart
- ❌ ต้องติดตั้งใหม่ทุกครั้ง
- ❌ ใช้ system packages (ไม่ persist)
- ❌ อาจต้อง root permissions

### After Fix
- ✅ FFmpeg persist หลัง Pod restart
- ✅ ติดตั้งครั้งเดียว ใช้ได้ตลอด
- ✅ ใช้ persistent volume (`/workspace`)
- ✅ ไม่ต้อง root permissions

## 🔍 Technical Details

### FFmpeg Static Binary

**Source:** GitHub releases (eugeneware/ffmpeg-static)
- **URL:** `https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-{arch}`
- **Architectures:** `amd64`, `arm64`
- **Size:** ~50-100MB (static binary)

### PATH Configuration

```bash
# Add to PATH
export PATH="/workspace/.local/bin:$PATH"

# Verify
which ffmpeg
# Should output: /workspace/.local/bin/ffmpeg
```

### Worker Environment

Video worker จะได้รับ PATH ที่รวม persistent bin:

```bash
PATH="/workspace/.local/bin:/workspace/.local/bin:$PATH"
```

## 🚨 Troubleshooting

### FFmpeg Not Found After Restart

```bash
# Check if binary exists
ls -lh /workspace/.local/bin/ffmpeg

# Check permissions
chmod +x /workspace/.local/bin/ffmpeg

# Re-install
bash scripts/pod/install-ffmpeg-persistent.sh
```

### Download Failed

```bash
# Manual download
cd /workspace/.local/bin
wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-amd64
mv ffmpeg-linux-amd64 ffmpeg
chmod +x ffmpeg
```

### Architecture Mismatch

```bash
# Check architecture
uname -m

# Download correct binary
# x86_64 -> amd64
# aarch64/arm64 -> arm64
```

## 📝 Next Steps

1. ✅ Created installation script
2. ✅ Updated start scripts to check persistent volume first
3. ✅ Added PATH configuration for worker
4. ⚠️ Test on Pod to verify persistence
5. ⚠️ Consider adding to Dockerfile (if using Docker)

