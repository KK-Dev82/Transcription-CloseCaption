# FFmpeg Container Troubleshooting

## 📋 ปัญหา: FFmpeg Installation Fails in Container

### อาการ
```
❌ Failed to install FFmpeg
⚠️  Failed to download from GitHub
⚠️  Failed to install FFmpeg via apt-get
```

## 🔍 สาเหตุที่เป็นไปได้

### 1. Network Issues
- Container ไม่มี internet access
- Firewall block GitHub/apt repositories
- DNS resolution fails

### 2. Permissions Issues
- ไม่มีสิทธิ์ install system packages
- ไม่มีสิทธิ์ write ไปยัง `/workspace/.local/bin`

### 3. Repository Issues
- apt repositories ไม่พร้อม
- Package lists ไม่ update ได้

### 4. Architecture Mismatch
- Binary architecture ไม่ตรงกับ container
- Static binary ไม่ compatible

## ✅ วิธีแก้ไข

### Method 1: Manual Download and Upload

**Step 1: Download on Local Machine**
```bash
# Download FFmpeg static binary
wget https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0.1/ffmpeg-linux-amd64

# Or use alternative source
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
```

**Step 2: Upload to Pod**
```bash
# Upload to persistent volume
scp -P 13263 ffmpeg-linux-amd64 4000-ada-sc:/workspace/.local/bin/ffmpeg

# Or if using tar
scp -P 13263 ffmpeg-release-amd64-static.tar.xz 4000-ada-sc:/tmp/
ssh -p 13263 4000-ada-sc "cd /workspace/.local/bin && tar -xf /tmp/ffmpeg-release-amd64-static.tar.xz --strip-components=1 && chmod +x ffmpeg"
```

**Step 3: Verify**
```bash
ssh -p 13263 4000-ada-sc "/workspace/.local/bin/ffmpeg -version"
```

### Method 2: Use Existing FFmpeg in Container

**Check if FFmpeg exists:**
```bash
ssh -p 13263 4000-ada-sc "find /usr -name ffmpeg 2>/dev/null"
ssh -p 13263 4000-ada-sc "find /opt -name ffmpeg 2>/dev/null"
ssh -p 13263 4000-ada-sc "which ffmpeg"
```

**If found, copy to persistent volume:**
```bash
ssh -p 13263 4000-ada-sc "cp $(which ffmpeg) /workspace/.local/bin/ffmpeg && chmod +x /workspace/.local/bin/ffmpeg"
```

### Method 3: Fix Network/Permissions

**Check network:**
```bash
ssh -p 13263 4000-ada-sc "ping -c 1 8.8.8.8"
ssh -p 13263 4000-ada-sc "curl -I https://github.com"
```

**Check permissions:**
```bash
ssh -p 13263 4000-ada-sc "ls -ld /workspace/.local/bin"
ssh -p 13263 4000-ada-sc "touch /workspace/.local/bin/test && rm /workspace/.local/bin/test"
```

**Fix permissions if needed:**
```bash
ssh -p 13263 4000-ada-sc "chmod 755 /workspace/.local/bin"
```

### Method 4: Use Conda/Mamba (if available)

```bash
ssh -p 13263 4000-ada-sc "conda install -c conda-forge ffmpeg -y"
# Then copy to persistent volume
ssh -p 13263 4000-ada-sc "cp $(conda info --base)/bin/ffmpeg /workspace/.local/bin/ffmpeg"
```

## 🔧 Debugging

### Check Installation Script
```bash
# Run with verbose output
bash -x scripts/pod/install-ffmpeg-persistent.sh
```

### Check Network Connectivity
```bash
# Test DNS
nslookup github.com

# Test HTTP
curl -I https://github.com

# Test apt repositories
apt-get update -v
```

### Check Container Environment
```bash
# Check architecture
uname -m

# Check OS
cat /etc/os-release

# Check available tools
which curl wget apt-get
```

## 📝 Quick Fix Script

```bash
#!/bin/bash
# Quick fix: Manual FFmpeg installation

INSTALL_DIR="/workspace/.local/bin"
mkdir -p "$INSTALL_DIR"

# Method 1: Try to find existing FFmpeg
if command -v ffmpeg > /dev/null 2>&1; then
    FFMPEG_PATH=$(which ffmpeg)
    cp "$FFMPEG_PATH" "$INSTALL_DIR/ffmpeg"
    chmod +x "$INSTALL_DIR/ffmpeg"
    echo "✅ Copied existing FFmpeg to $INSTALL_DIR"
    exit 0
fi

# Method 2: Try apt-get with verbose output
if command -v apt-get > /dev/null 2>&1; then
    echo "Trying apt-get..."
    apt-get update
    apt-get install -y ffmpeg
    if command -v ffmpeg > /dev/null 2>&1; then
        cp $(which ffmpeg) "$INSTALL_DIR/ffmpeg"
        chmod +x "$INSTALL_DIR/ffmpeg"
        echo "✅ Installed via apt-get and copied to $INSTALL_DIR"
        exit 0
    fi
fi

echo "❌ All methods failed - use manual installation"
```

## 🚨 Common Issues

### Issue 1: "Failed to download from GitHub"
**Solution:** Use manual download and upload method

### Issue 2: "apt-get install failed"
**Possible causes:**
- No network access
- No permissions
- Repository issues

**Solution:**
- Check network: `ping 8.8.8.8`
- Check permissions: `id`
- Try manual installation

### Issue 3: "Binary not executable"
**Solution:**
```bash
chmod +x /workspace/.local/bin/ffmpeg
```

### Issue 4: "FFmpeg not found in PATH"
**Solution:**
```bash
export PATH="/workspace/.local/bin:$PATH"
# Or add to .bashrc
echo 'export PATH="/workspace/.local/bin:$PATH"' >> ~/.bashrc
```

## ✅ Verification

After installation:
```bash
# Check binary exists
ls -lh /workspace/.local/bin/ffmpeg

# Check version
/workspace/.local/bin/ffmpeg -version

# Test functionality
/workspace/.local/bin/ffmpeg -f lavfi -i testsrc=duration=1:size=320x240:rate=1 test.mp4
rm -f test.mp4
```

## 📊 Next Steps

1. ✅ Improved installation script with multiple sources
2. ⚠️ Test on Pod to verify network access
3. ⚠️ Consider pre-installing FFmpeg in Docker image
4. ⚠️ Add FFmpeg to persistent volume backup

