# 🔌 Redis Connection Guide

คู่มือการแก้ปัญหา Redis connection ที่ทำให้ startup หน่วง

## 📋 สรุปการปรับปรุง

ตามคำแนะนำจากผู้เชี่ยวชาญ เราได้ปรับปรุง:

### ✅ 1. ลด Timeout
- **Quick check**: 1 วินาที (sync client)
- **Async connect**: 3 วินาที (ลดจาก 30s)
- **Ping timeout**: 3 วินาที (ลดจาก 30s)

### ✅ 2. ไม่ Block Startup
- WebSocket bootstrap ทำงานเป็น **background task**
- Main API start ทันที → Redis/Subscriber ตามมาทีหลัง
- ถ้า Redis ไม่พร้อม → แอปยังรันได้ (แค่ไม่มี realtime events)

### ✅ 3. Fail Fast
- ปิด `retry_on_timeout` เพื่อ fail fast
- Quick check ด้วย sync client ก่อน (เร็วกว่า async)
- Retry แบบ backoff ใน background

### ✅ 4. รองรับ TLS (rediss://)
- `redis.from_url()` รองรับ `rediss://` อัตโนมัติ
- ไม่ต้อง config SSL เอง

---

## 🔍 วิธีตรวจสอบปัญหา Redis Connection

### 1. ตรวจสอบ REDIS_URL

```bash
# ดู REDIS_URL (ระวังอย่าแปะ password ตรงๆ)
echo $REDIS_URL | sed 's/:[^@]*@/:****@/'

# ตรวจสอบว่าเป็น redis:// หรือ rediss://
echo $REDIS_URL | grep -E "^redis[s]?://"
```

**หมายเหตุ:**
- `redis://` = ไม่ใช้ TLS
- `rediss://` = ใช้ TLS (Redis Cloud/Redis.io ใช้แบบนี้)

### 2. ตรวจสอบ Network Connectivity

#### ไม่ใช้ TLS (redis://)
```bash
# แยก host และ port จาก REDIS_URL
# ตัวอย่าง: redis://host:6379
nc -vz <host> <port>

# ตัวอย่าง
nc -vz redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com 12345
```

#### ใช้ TLS (rediss://)
```bash
# ตรวจสอบ TLS connection
openssl s_client -connect <host>:<port> -servername <host>

# ตัวอย่าง
openssl s_client -connect redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com:12345 \
  -servername redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com
```

### 3. ตรวจสอบ DNS

```bash
# ตรวจสอบว่า resolve hostname ได้หรือไม่
nslookup <redis-host>

# หรือ
dig <redis-host>
```

### 4. ตรวจสอบ Firewall/Outbound

```bash
# ตรวจสอบว่า outbound connection ไป Redis ได้หรือไม่
# (จาก container/server ที่รัน API)

# ถ้าใช้ TLS
timeout 5 openssl s_client -connect <host>:<port> -servername <host> </dev/null

# ถ้าไม่ใช้ TLS
timeout 5 nc -vz <host> <port>
```

---

## 🐛 แก้ปัญหาตามอาการ

### อาการ: Startup ค้างที่ "Waiting for application startup"

**สาเหตุที่เป็นไปได้:**
1. Redis timeout ยาว (แก้แล้ว: ลดเป็น 3s)
2. Network/TLS issue
3. DNS resolve ช้า
4. Firewall block

**วิธีแก้:**
```bash
# 1. Skip WebSocket initialization ชั่วคราว
SKIP_WEBSOCKET=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8010

# 2. ตรวจสอบ network
nc -vz <redis-host> <port>

# 3. ตรวจสอบ TLS (ถ้าใช้ rediss://)
openssl s_client -connect <host>:<port> -servername <host>
```

### อาการ: "Redis connection timeout"

**สาเหตุ:**
- Network latency สูง
- TLS handshake ช้า
- Firewall/NAT block

**วิธีแก้:**
1. ตรวจสอบ network connectivity (ดูด้านบน)
2. ตรวจสอบ REDIS_URL ถูกต้องหรือไม่
3. ตรวจสอบ firewall rules
4. ลองใช้ `SKIP_WEBSOCKET=true` ชั่วคราว

### อาการ: "Redis not available (quick check failed)"

**สาเหตุ:**
- Redis server ไม่พร้อม
- Network ไม่ถึง
- Auth ผิด

**วิธีแก้:**
1. ตรวจสอบ Redis server status
2. ตรวจสอบ REDIS_URL (username/password)
3. ตรวจสอบ network connectivity

---

## 📊 Log Messages ที่ควรรู้

### ✅ สำเร็จ
```
✅ Redis availability check passed (sync quick check)
🔄 Connecting Redis for WebSocket: rediss://...
✅ Redis connected for WebSocket pub/sub
✅ Redis subscriber started for WS notifications
```

### ⚠️ Warning (ยังรันได้)
```
⚠️ Redis not available (quick check failed in 1s): ...
   This might be network/TLS/auth issue. Continuing without Redis pub/sub.
⏱️ Redis connection timeout (3s) - continuing without Redis pub/sub
⚠️ Redis subscriber start failed: ... (will retry in background)
```

### ❌ Error (ควรแก้)
```
❌ Redis connection failed: ConnectionError: ...
❌ WebSocket bootstrap failed: ...
```

---

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL (redis:// หรือ rediss://) | - |
| `SKIP_WEBSOCKET` | ข้าม WebSocket initialization | `false` |
| `TRANSCRIPTION_MOCK_MODE` | ใช้ Mock Mode (ข้าม websocket และ services) | `false` |

---

## 🚀 Best Practices

### 1. ใช้ Background Task
- ✅ WebSocket bootstrap ทำงานเป็น background task
- ✅ Main API start ทันที
- ✅ Redis/Subscriber ตามมาทีหลัง

### 2. Fail Fast
- ✅ Timeout สั้น (3-5s)
- ✅ Quick check ก่อน (1s)
- ✅ ไม่ retry ตอน startup

### 3. Graceful Degradation
- ✅ ถ้า Redis ไม่พร้อม → แอปยังรันได้
- ✅ แค่ไม่มี realtime events
- ✅ API endpoints ยังทำงานได้

### 4. Retry Strategy
- ✅ Retry ใน background (backoff)
- ✅ ไม่ block startup
- ✅ Log warnings เพื่อ debug

---

## 📝 Checklist สำหรับ Production

- [ ] REDIS_URL ถูกต้อง (redis:// หรือ rediss://)
- [ ] Network connectivity ไป Redis ได้
- [ ] TLS certificate ถูกต้อง (ถ้าใช้ rediss://)
- [ ] Firewall rules อนุญาต outbound connection
- [ ] DNS resolve ได้
- [ ] Auth credentials ถูกต้อง
- [ ] Connection pool size เหมาะสม
- [ ] Timeout settings เหมาะสม (3-5s)

---

## 🔗 References

- [Redis Python Client](https://redis-py.readthedocs.io/)
- [Redis Async Client](https://redis.readthedocs.io/en/latest/connections.html#asyncio-connections)
- [Redis Cloud Documentation](https://redis.io/docs/cloud/)

---

## 💡 Tips

1. **Test จาก Container/Server เดียวกัน**: ใช้ `nc` หรือ `openssl` จากที่เดียวกับที่รัน API
2. **ดู Logs**: ตรวจสอบ log messages เพื่อหาสาเหตุ
3. **Skip ชั่วคราว**: ใช้ `SKIP_WEBSOCKET=true` เพื่อ debug
4. **ตรวจสอบ Network ก่อน**: ใช้ `nc` หรือ `openssl` เพื่อตรวจสอบ connectivity
