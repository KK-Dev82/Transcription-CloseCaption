# 🔌 Port Configuration Guide - RunPod

## 📋 สรุปการตั้งค่า Port

### สำหรับ 4080s (80.15.7.37)

#### Port Forwarding (Direct TCP)
- **SSH**: `80.15.7.37:41433 -> :22`
- **Main API**: `80.15.7.37:41434 -> :8010`

#### HTTP Services (Proxied by RunPod)
- **Port 8001**: HTTP Service (Ready) - อาจ proxy ไปยัง port 8010
- **Port 8002**: HTTP Service (Ready) - อาจ proxy ไปยัง port 8010
- **Port 8888**: Jupyter Lab (Not ready)

---

### สำหรับ 4000-ada (87.197.119.40)

#### Port Forwarding (Direct TCP)
- **SSH**: `87.197.119.40:40111 -> :22`
- **Main API**: `87.197.119.40:40112 -> :8010`

---

## 🎯 การใช้งาน

### 1. Main API (Transcription Service)

**Port ที่ใช้**: `8010` (Direct TCP)

**URL สำหรับ API Calls**:
- **4080s**: `http://80.15.7.37:41434/` หรือ `http://80.15.7.37:8010/` (ถ้าใช้ direct TCP)
- **4000-ada**: `http://87.197.119.40:40112/` หรือ `http://87.197.119.40:8010/` (ถ้าใช้ direct TCP)

**Health Check**:
```bash
# 4080s
curl http://80.15.7.37:41434/health
# หรือ
curl http://80.15.7.37:8010/health

# 4000-ada
curl http://87.197.119.40:40112/health
# หรือ
curl http://87.197.119.40:8010/health
```

**API Endpoints**:
- Health: `/health`
- Transcribe: `/transcribe/`
- Get Task: `/transcribe/{task_id}`
- Queue Stats: `/queue/stats`
- Docs: `/docs`

---

### 2. Concurrency Monitor (HTML)

**Static File Path**: `/static/concurrency-monitor.html`

**URL สำหรับเข้าถึง**:

#### Option 1: ผ่าน Direct TCP (Port 8010)
- **4080s**: `http://80.15.7.37:41434/static/concurrency-monitor.html`
- **4000-ada**: `http://87.197.119.40:40112/static/concurrency-monitor.html`

#### Option 2: ผ่าน HTTP Service (ถ้า RunPod proxy ไปยัง 8010)
- **4080s**: 
  - `http://80.15.7.37:8001/static/concurrency-monitor.html` (ถ้า proxy ไปยัง 8010)
  - `http://80.15.7.37:8002/static/concurrency-monitor.html` (ถ้า proxy ไปยัง 8010)
- **4000-ada**: 
  - ใช้ Direct TCP เท่านั้น (ไม่มี HTTP Service)

---

## ⚠️ หมายเหตุสำคัญ

### Port 8001
- **ถูกใช้โดย**: nginx (vscode server) บน Pod
- **ไม่ควรใช้**: สำหรับ Main API
- **อาจใช้ได้**: ถ้า RunPod HTTP Service proxy ไปยัง port 8010

### Port 8010
- **ใช้สำหรับ**: Main API (Transcription Service)
- **Type**: Direct TCP (ไม่ผ่าน proxy)
- **ต้องเปิด**: ใน RunPod Dashboard → Ports → Add Port 8010

---

## 🔧 การตรวจสอบ

### 1. ตรวจสอบว่า Main API ทำงานบน port 8010

```bash
# บน Pod
curl http://localhost:8010/health

# จากภายนอก (4080s)
curl http://80.15.7.37:41434/health

# จากภายนอก (4000-ada)
curl http://87.197.119.40:40112/health
```

### 2. ตรวจสอบว่า Static Files ถูก serve

```bash
# บน Pod
curl http://localhost:8010/static/concurrency-monitor.html | head -20

# จากภายนอก (4080s)
curl http://80.15.7.37:41434/static/concurrency-monitor.html | head -20

# จากภายนอก (4000-ada)
curl http://87.197.119.40:40112/static/concurrency-monitor.html | head -20
```

### 3. ตรวจสอบว่า HTTP Service (8001/8002) proxy ไปยัง 8010 หรือไม่

```bash
# ทดสอบ port 8001
curl http://80.15.7.37:8001/health

# ทดสอบ port 8002
curl http://80.15.7.37:8002/health
```

**ถ้าได้ response จาก Main API** = HTTP Service proxy ไปยัง 8010 แล้ว ✅  
**ถ้าได้ 502 Bad Gateway** = HTTP Service ไม่ได้ proxy ไปยัง 8010 ❌

---

## 📝 สรุป

### สำหรับ 4080s:
1. **Main API**: ใช้ port **8010** (Direct TCP)
2. **เข้าถึงจากภายนอก**: `http://80.15.7.37:41434/` (Direct TCP) หรือ `http://80.15.7.37:8001/` (ถ้า HTTP Service proxy)
3. **Concurrency Monitor**: `http://80.15.7.37:41434/static/concurrency-monitor.html` หรือ `http://80.15.7.37:8001/static/concurrency-monitor.html`

### สำหรับ 4000-ada:
1. **Main API**: ใช้ port **8010** (Direct TCP)
2. **เข้าถึงจากภายนอก**: `http://87.197.119.40:40112/` (Direct TCP)
3. **Concurrency Monitor**: `http://87.197.119.40:40112/static/concurrency-monitor.html`

---

**อัปเดต**: 2025-12-09  
**Port Configuration**: 8010 (Direct TCP) ✅

