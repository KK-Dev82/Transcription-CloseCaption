# 🔧 Troubleshooting: Connectivity Issues

คู่มือแก้ไขปัญหาเมื่อไม่สามารถเชื่อมต่อจาก External (MacOS) ไปยัง RunPod

---

## ❌ อาการ

```bash
# จาก MacOS
curl 205.196.17.108:8001/health
# curl: (7) Failed to connect to 205.196.17.108 port 8001

curl 205.196.17.108:8002/health
# curl: (7) Failed to connect to 205.196.17.108 port 8002
```

แต่ใน RunPod Connect Tab:
- Port 8002 → whisper: **Ready** ✅
- Port 8001 → api: **Not Ready** ⚠️

---

## 🔍 วิธีตรวจสอบ

### Step 1: SSH เข้า Pod และตรวจสอบ Services

```bash
# SSH เข้า Pod
ssh root@205.196.17.108 -p 13027

# ตรวจสอบ services
bash scripts/pod/check-services.sh
```

**หรือตรวจสอบด้วยตนเอง:**

```bash
# ตรวจสอบ processes
ps aux | grep -E "(python|redis|whisper)" | grep -v grep

# ตรวจสอบ listening ports
netstat -tuln | grep -E "(8001|8002)" || ss -tuln | grep -E "(8001|8002)"

# ตรวจสอบ health (local)
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## 🛠️ วิธีแก้ไข

### Issue 1: Services ยังไม่ Start

**อาการ:**
- `ps aux | grep python` ไม่พบ processes
- `netstat -tuln | grep 8001` ไม่มีผลลัพธ์

**แก้ไข:**

```bash
# SSH เข้า Pod
ssh root@205.196.17.108 -p 13027

# Start services
cd /workspace/transcription-service
bash scripts/pod/start-services-direct.sh
```

**ตรวจสอบ:**

```bash
# ตรวจสอบ logs
tail -f /tmp/main-api.log
tail -f /tmp/whisper.log

# ตรวจสอบ health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

### Issue 2: Services Start แล้วแต่ไม่ได้ Listen ที่ 0.0.0.0

**อาการ:**
- `ps aux | grep python` พบ processes
- `netstat -tuln | grep 8001` แสดง `127.0.0.1:8001` แทน `0.0.0.0:8001`

**แก้ไข:**

```bash
# Stop services
bash scripts/pod/stop-services.sh

# ตรวจสอบว่า start-services-direct.sh ใช้ --host 0.0.0.0
grep -n "0.0.0.0" scripts/pod/start-services-direct.sh

# Start services ใหม่
bash scripts/pod/start-services-direct.sh
```

**ตรวจสอบ:**

```bash
# ตรวจสอบ listening address
netstat -tuln | grep 8001
# ควรเห็น: 0.0.0.0:8001 หรือ :::8001
```

---

### Issue 3: Services Start แล้วแต่ Health Check Fail

**อาการ:**
- `ps aux | grep python` พบ processes
- `netstat -tuln | grep 8001` แสดง `0.0.0.0:8001`
- แต่ `curl http://localhost:8001/health` fail

**แก้ไข:**

```bash
# ตรวจสอบ logs
tail -f /tmp/main-api.log
tail -f /tmp/whisper.log

# ตรวจสอบ errors
grep -i error /tmp/main-api.log
grep -i error /tmp/whisper.log

# Restart services
bash scripts/pod/stop-services.sh
bash scripts/pod/start-services-direct.sh
```

---

### Issue 4: RunPod HTTP Services ไม่ทำงาน

**อาการ:**
- Services start แล้วและ listen ที่ 0.0.0.0
- `curl http://localhost:8001/health` ทำงาน
- แต่ RunPod Connect Tab แสดง "Not Ready"

**แก้ไข:**

1. **ตรวจสอบ RunPod Template Configuration:**
   - ไปที่ RunPod Console → Templates
   - ตรวจสอบว่า HTTP Ports ถูกตั้งค่า: `8001,8002`

2. **Restart Pod:**
   - ไปที่ RunPod Console → Pods
   - Stop Pod
   - Start Pod ใหม่

3. **ตรวจสอบ Firewall:**
   - RunPod อาจมี firewall ที่ block connections
   - ตรวจสอบใน RunPod Settings

---

## 🌐 วิธีเข้าถึงจาก External

### Option 1: ใช้ RunPod HTTP Services (แนะนำ)

**จาก RunPod Connect Tab:**
- คลิกที่ External Link ของ Port 8001 หรือ 8002
- RunPod จะให้ URL แบบ: `https://xxxxx-8001.proxy.runpod.net`

**ตัวอย่าง:**

```bash
# ใช้ URL จาก RunPod HTTP Services
curl https://xxxxx-8001.proxy.runpod.net/health
curl https://xxxxx-8002.proxy.runpod.net/health
```

---

### Option 2: ใช้ Direct TCP (ถ้าเปิดไว้)

**จาก RunPod Connect Tab:**
- ดูที่ "Direct TCP Ports"
- ใช้ IP และ Port ที่แสดง

**ตัวอย่าง:**

```bash
# ใช้ Direct TCP (ถ้าเปิดไว้)
curl http://205.196.17.108:8001/health
curl http://205.196.17.108:8002/health
```

**หมายเหตุ:** Direct TCP อาจถูก firewall block

---

## 📋 Checklist

- [ ] Services start แล้ว (`ps aux | grep python`)
- [ ] Services listen ที่ `0.0.0.0` (`netstat -tuln | grep 8001`)
- [ ] Health check ผ่าน (local): `curl http://localhost:8001/health`
- [ ] RunPod HTTP Services เปิดอยู่ (Connect Tab)
- [ ] ใช้ URL จาก RunPod HTTP Services (ไม่ใช่ direct IP)

---

## 🔗 Related Documents

- **Check Services:** `scripts/pod/check-services.sh`
- **Start Services:** `scripts/pod/start-services-direct.sh`
- **Stop Services:** `scripts/pod/stop-services.sh`

---

**Last Updated:** 2024-12-19

