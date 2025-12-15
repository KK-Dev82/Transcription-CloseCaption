# FFmpeg Installation Test Guide

## 🧪 Test Script

สร้าง test script สำหรับทดสอบและ debug FFmpeg installation:

**ไฟล์:** `scripts/pod/test-ffmpeg-install.sh`

## 📋 วิธีใช้งาน

### 1. Pull Latest Changes

```bash
ssh -p 13263 4000-ada-sc "cd /workspace/transcription-service && git pull origin staging"
```

### 2. Run Test Script

```bash
ssh -p 13263 4000-ada-sc "cd /workspace/transcription-service && bash scripts/pod/test-ffmpeg-install.sh"
```

## 🔍 Test Script จะตรวจสอบ

### Step 1: System Information
- Architecture
- OS version
- Current user
- Install directory

### Step 2: Network Connectivity
- DNS resolution
- Ping test
- HTTPS to GitHub

### Step 3: Available Tools
- curl, wget, apt-get, tar, gzip

### Step 4: Check Existing FFmpeg
- Persistent volume
- System PATH
- Common locations

### Step 5: Test Quick Fix Script
- Run `quick-fix-ffmpeg.sh`
- Show results

### Step 6: Test Main Installation Script
- Run `install-ffmpeg-persistent.sh`
- Show results

### Step 7: Final Verification
- Check if FFmpeg is installed
- Show version and test command

## 📊 Expected Output

### Success Case
```
✅ FFmpeg installation successful!
Location: /workspace/.local/bin/ffmpeg
Version: 6.0.1
```

### Failure Case
```
❌ FFmpeg installation failed
💡 Next steps:
   1. Check network connectivity
   2. Check permissions
   3. Try manual download and upload
```

## 🚨 Common Issues & Solutions

### Issue 1: Network Connectivity Failed
**Symptoms:**
```
❌ DNS: Failed
❌ Ping: Failed
❌ HTTPS to GitHub: Failed
```

**Solution:**
- Container อาจไม่มี internet access
- ใช้ manual download & upload

### Issue 2: Tools Not Available
**Symptoms:**
```
❌ curl: Not found
❌ wget: Not found
```

**Solution:**
- Install tools: `apt-get install -y curl wget`
- หรือใช้ manual download

### Issue 3: Permissions Denied
**Symptoms:**
```
❌ Cannot write to /workspace/.local/bin
```

**Solution:**
```bash
chmod 755 /workspace/.local/bin
chown $(whoami) /workspace/.local/bin
```

## 📝 Next Steps After Test

1. **If Success:**
   - FFmpeg is installed in persistent volume
   - Add to PATH in worker startup script
   - Test video worker

2. **If Failed:**
   - Check test output for specific errors
   - Try manual installation
   - Check network/permissions

## 🔧 Manual Installation (if auto-install fails)

```bash
# On local machine
wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-amd64

# Upload to Pod
scp -P 13263 ffmpeg-linux-amd64 4000-ada-sc:/workspace/.local/bin/ffmpeg

# Set permissions
ssh -p 13263 4000-ada-sc "chmod +x /workspace/.local/bin/ffmpeg"

# Verify
ssh -p 13263 4000-ada-sc "/workspace/.local/bin/ffmpeg -version"
```

