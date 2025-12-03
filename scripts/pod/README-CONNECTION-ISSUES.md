# 🔍 คู่มือตรวจสอบปัญหา Connection Issues

## 🔍 ปัญหาที่พบบ่อย

### 1. Server disconnected
```
⚠️  Task X: Poll error - Server disconnected
```

### 2. Connection reset by peer
```
⚠️  Task X: Poll error - [Errno 104] Connection reset by peer
```

---

## 🚀 วิธีตรวจสอบ

### วิธีที่ 1: ใช้ Diagnostic Script (แนะนำ)

```bash
# SSH เข้า Pod
ssh pytorch-pod

# รัน diagnostic script
bash scripts/pod/check-connection-issues.sh
```

**Script นี้จะตรวจสอบ**:
- ✅ Service Status (running, CPU, Memory)
- ✅ Active Connections (จำนวน connections ที่เปิดอยู่)
- ✅ System Resources (Memory, CPU Load, File Descriptors)
- ✅ Log Analysis (Connection errors ใน logs)
- ✅ Network Statistics (TCP sockets, TIME_WAIT)
- ✅ Recommendations (คำแนะนำการแก้ไข)

---

### วิธีที่ 2: ตรวจสอบด้วยตนเอง

#### 1. ตรวจสอบ Service Status

```bash
# SSH เข้า Pod
ssh pytorch-pod

# ตรวจสอบ service
bash scripts/pod/check-service-status.sh

# หรือตรวจสอบด้วยตนเอง
ps aux | grep uvicorn
curl http://localhost:8010/health
```

#### 2. ตรวจสอบ Logs

```bash
# ดู logs ล่าสุด
tail -100 /tmp/transcription-service.log

# ดู connection errors
tail -1000 /tmp/transcription-service.log | grep -iE "disconnect|connection reset|error"

# Follow logs real-time
tail -f /tmp/transcription-service.log
```

#### 3. ตรวจสอบ Connections

```bash
# ตรวจสอบจำนวน connections
netstat -an | grep ":8010" | grep ESTABLISHED | wc -l

# หรือใช้ ss
ss -an | grep ":8010" | grep ESTAB | wc -l

# ดู connections ทั้งหมด
netstat -an | grep ":8010"
```

#### 4. ตรวจสอบ System Resources

```bash
# Memory
free -h

# CPU Load
top
# หรือ
cat /proc/loadavg

# File Descriptors (ถ้า service กำลังรัน)
PID=$(pgrep -f "uvicorn.*app.main:app.*8010" | head -1)
ls -1 /proc/$PID/fd | wc -l
```

---

## 🔧 สาเหตุและการแก้ไข

### 1. Server Overload (50 Concurrent Requests)

**อาการ**:
- Server disconnected
- Connection reset by peer
- Service ไม่ตอบสนอง

**สาเหตุ**:
- 50 requests พร้อมกันทำให้ server รับไม่ไหว
- Memory หรือ CPU หมด
- File descriptors หมด

**วิธีแก้ไข**:

```bash
# Option 1: เพิ่ม Resources
# - เพิ่ม Memory สำหรับ container
# - เพิ่ม CPU cores

# Option 2: ลด Concurrent Requests
# - ลดจาก 50 เป็น 20-30
# - เพิ่ม delay ระหว่าง requests

# Option 3: Scale Service
# - ใช้ Load Balancer
# - ใช้ Multiple Service Instances
```

### 2. Connection Timeout

**อาการ**:
- Connection reset by peer
- Server disconnected หลัง polling นาน

**สาเหตุ**:
- Client timeout น้อยเกินไป
- Server processing time นาน
- Network latency สูง

**วิธีแก้ไข**:

```bash
# เพิ่ม timeout ใน client
# (ใน test-50-concurrency.py)
poll_interval=5  # เพิ่มเป็น 10
timeout=60       # เพิ่มเป็น 120
```

### 3. Service Crash หรือ Restart

**อาการ**:
- Server disconnected ทันที
- Connection reset by peer

**วิธีตรวจสอบ**:

```bash
# ตรวจสอบ service PID
ps aux | grep uvicorn

# ตรวจสอบ logs สำหรับ crash
tail -200 /tmp/transcription-service.log | grep -iE "error|exception|traceback|killed"

# ตรวจสอบ memory/CPU ก่อน crash
dmesg | tail -50
```

**วิธีแก้ไข**:

```bash
# Restart service
bash scripts/pod/start-service-daemon.sh

# หรือ stop แล้ว start ใหม่
kill $(pgrep -f "uvicorn.*app.main:app.*8010")
bash scripts/pod/start-service-daemon.sh
```

### 4. Network Issues

**อาการ**:
- Connection reset by peer
- Network is unreachable

**วิธีตรวจสอบ**:

```bash
# ตรวจสอบ network connectivity
ping -c 3 80.15.7.37

# ตรวจสอบ firewall
iptables -L -n | grep 8010

# ตรวจสอบ port forwarding
curl -v http://localhost:8010/health
curl -v http://80.15.7.37:41462/health
```

**วิธีแก้ไข**:
- ตรวจสอบ RunPod port mapping (41462 -> 8010)
- ตรวจสอบ firewall rules
- ตรวจสอบ network configuration

### 5. Resource Exhaustion

**อาการ**:
- Memory usage สูง
- File descriptors หมด
- CPU usage สูง

**วิธีตรวจสอบ**:

```bash
# Memory
free -h

# File descriptors
PID=$(pgrep -f "uvicorn.*app.main:app.*8010" | head -1)
FD_COUNT=$(ls -1 /proc/$PID/fd | wc -l)
FD_LIMIT=$(ulimit -n)
echo "File descriptors: $FD_COUNT / $FD_LIMIT"

# CPU
top -p $PID
```

**วิธีแก้ไข**:

```bash
# Option 1: เพิ่ม limits
# ใน start-service-daemon.sh
ulimit -n 4096

# Option 2: Restart service
bash scripts/pod/start-service-daemon.sh

# Option 3: Optimize service
# - ลด concurrent processing
# - เพิ่ม connection pooling
```

---

## 📊 Diagnostic Checklist

เมื่อพบปัญหา "Server disconnected" หรือ "Connection reset":

- [ ] ตรวจสอบ service status: `bash scripts/pod/check-service-status.sh`
- [ ] ตรวจสอบ logs: `tail -100 /tmp/transcription-service.log`
- [ ] ตรวจสอบ connections: `netstat -an | grep ":8010"`
- [ ] ตรวจสอบ resources: `free -h && top`
- [ ] ตรวจสอบ network: `curl http://localhost:8010/health`
- [ ] รัน diagnostic script: `bash scripts/pod/check-connection-issues.sh`

---

## 💡 Best Practices

### สำหรับ Concurrency Testing

1. **เริ่มจากจำนวนน้อย**: เริ่มจาก 10-20 requests แล้วค่อยเพิ่ม
2. **Monitor Resources**: ตรวจสอบ CPU/Memory ระหว่าง test
3. **Add Delays**: เพิ่ม delay ระหว่าง requests ถ้าจำเป็น
4. **Check Logs**: Monitor logs real-time ระหว่าง test
5. **Test Incrementally**: ทดสอบทีละขั้น (10, 20, 30, 50)

### สำหรับ Production

1. **Set Limits**: จำกัด concurrent connections
2. **Monitor Resources**: ใช้ monitoring tools
3. **Auto-restart**: Setup service auto-restart ถ้า crash
4. **Load Balancing**: ใช้ load balancer สำหรับ multiple instances
5. **Graceful Degradation**: Handle overload gracefully

---

## 🔗 Related Scripts

- `check-service-status.sh` - ตรวจสอบ service status
- `check-connection-issues.sh` - ตรวจสอบ connection issues (ใหม่)
- `start-service-daemon.sh` - Start service
- `diagnose-transcription.sh` - ตรวจสอบ transcription task

---

**Last Updated**: 2025-12-02  
**Script**: `scripts/pod/check-connection-issues.sh`

