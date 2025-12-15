# Run FFmpeg Test on Server

## 🚀 Quick Command

รันคำสั่งนี้บน server เพื่อทดสอบ FFmpeg installation:

```bash
ssh -p 13263 4000-ada-sc "cd /workspace/transcription-service && git pull origin staging && bash scripts/pod/ffmpeg-diagnostic.sh"
```

## 📋 Scripts Available

### 1. `ffmpeg-diagnostic.sh` (แนะนำ - เร็วที่สุด)
```bash
bash scripts/pod/ffmpeg-diagnostic.sh
```
- Minimal output
- Fast execution
- Saves to log file
- Shows summary

### 2. `test-ffmpeg-simple.sh`
```bash
bash scripts/pod/test-ffmpeg-simple.sh
```
- Simple output
- Tests network, tools, FFmpeg
- Runs installation scripts

### 3. `test-ffmpeg-install.sh`
```bash
bash scripts/pod/test-ffmpeg-install.sh
```
- Comprehensive test
- Detailed output
- All checks

## 📊 What Will Be Tested

1. **System Information**
   - Architecture
   - OS version
   - Current user

2. **Network Connectivity**
   - Ping test
   - GitHub HTTPS access

3. **Available Tools**
   - curl, wget, apt-get, tar

4. **Existing FFmpeg**
   - Persistent volume
   - System PATH
   - Common locations

5. **Installation Attempts**
   - Quick fix script
   - Main installation script

6. **Final Verification**
   - Check if FFmpeg is installed
   - Show version

## 📁 Output Location

Results will be saved to:
```
logs/ffmpeg-diagnostic-YYYYMMDD-HHMMSS.log
```

## 🔍 View Results

```bash
# View latest log
ls -lt logs/ffmpeg-diagnostic-*.log | head -1 | awk '{print $NF}' | xargs cat

# Or view all logs
cat logs/ffmpeg-diagnostic-*.log
```

## 🚨 If SSH Hangs

If SSH commands hang or timeout, try:

1. **Run script in background:**
```bash
ssh -p 13263 4000-ada-sc "cd /workspace/transcription-service && nohup bash scripts/pod/ffmpeg-diagnostic.sh > /tmp/ffmpeg-test.out 2>&1 &"
```

2. **Check results later:**
```bash
ssh -p 13263 4000-ada-sc "cat /tmp/ffmpeg-test.out"
```

3. **Or run directly on server:**
```bash
# SSH to server first
ssh -p 13263 4000-ada-sc

# Then run script
cd /workspace/transcription-service
bash scripts/pod/ffmpeg-diagnostic.sh
```

