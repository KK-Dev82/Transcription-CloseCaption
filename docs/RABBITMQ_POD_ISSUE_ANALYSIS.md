# RabbitMQ และ Pod Container Issue Analysis

## สรุปผลการตรวจสอบ

### 1. RabbitMQ Configuration

- **Host**: `178.128.105.100` (Remote server - ไม่ใช่ localhost)
- **Port**: `5672`
- **User**: `senate`
- **Heartbeat**: `1800s` (30 minutes)
- **Connection Status**: ✅ Connection successful

### 2. ปัญหาที่พบ

#### A. Remote RabbitMQ Server
- RabbitMQ อยู่บน remote server (178.128.105.100)
- อาจมี network issues ระหว่าง Pod Container กับ RabbitMQ server
- ไม่สามารถ ping ได้ (อาจเป็น firewall หรือ network policy)

#### B. RabbitMQ Server Restart
- ตามที่เคยรายงาน: RabbitMQ server อาจ restart เนื่องจาก:
  - Bitcoin mining spyware (ksftmp) ทำให้ RAM เต็ม
  - RabbitMQ restart เอง
  - Connection หลุด

#### C. Connection Monitoring
- Worker มี connection monitor (`_monitor_connection_and_reconnect`)
- ตรวจสอบ connection state ทุก 5 วินาที
- แต่ไม่เห็น reconnection logs ในช่วงที่ worker หยุดทำงาน

### 3. สาเหตุที่เป็นไปได้

#### สาเหตุที่ 1: RabbitMQ Server Restart
```
Timeline:
- 03:52:32: Batch 1 sent
- 03:52:42: Batch 2 sent
- 03:52:53: Batch 3 sent
- 03:53:03: Batch 4 sent
- 03:53:03: Worker received SIGTERM (signal 15)
- 03:53:14: Batch 5 sent (worker already stopped)
```

**สมมติฐาน**: RabbitMQ server restart → Connection หลุด → Worker ไม่สามารถ reconnect ได้ทัน → Worker exit

#### สาเหตุที่ 2: Network Connectivity Issues
- Remote RabbitMQ server อาจมี network issues
- Connection timeout หรือ heartbeat timeout
- Firewall หรือ network policy block connection

#### สาเหตุที่ 3: Pod Container Resource Issues
- Pod Container อาจมี resource limits
- Memory หรือ CPU issues
- Container restart

### 4. หลักฐาน

#### A. Connection Logs
```
2025-12-17 10:51:46,258 - ✅ Connected to RabbitMQ successfully
2025-12-17 10:51:51,027 - 🔍 Started connection monitor
2025-12-17 10:53:03,814 - ได้รับ signal 15 กำลังปิด worker...
```

**ไม่พบ**:
- Connection error logs
- Reconnection attempts
- Network timeout errors

#### B. Worker Behavior
- Worker มี infinite retry loop (`while True:`)
- แต่ exit หลังจากได้รับ SIGTERM
- ไม่ restart อัตโนมัติ (เพราะ `worker.running = False`)

### 5. การแก้ไขที่แนะนำ

#### A. เพิ่ม RabbitMQ Connection Resilience
1. **เพิ่ม reconnection retry logic**
   - Retry connection หลายครั้ง
   - Exponential backoff
   - Log reconnection attempts

2. **ปรับปรุง connection monitoring**
   - ตรวจสอบ connection state บ่อยขึ้น
   - Handle reconnection เร็วขึ้น
   - Re-register consumers อัตโนมัติ

3. **เพิ่ม connection health check**
   - Ping RabbitMQ server เป็นระยะ
   - Monitor connection quality
   - Alert เมื่อ connection มีปัญหา

#### B. ปรับปรุง Error Handling
1. **Handle RabbitMQ server restart**
   - Detect server restart
   - Auto-reconnect และ re-register consumers
   - ไม่ exit worker เมื่อ connection หลุด

2. **เพิ่ม logging**
   - Log connection state changes
   - Log reconnection attempts
   - Log network errors

#### C. ปรับปรุง Pod Container
1. **ตรวจสอบ resource limits**
   - Memory limits
   - CPU limits
   - Network limits

2. **เพิ่ม health checks**
   - RabbitMQ connection health
   - Network connectivity
   - Resource usage

### 6. ขั้นตอนถัดไป

1. ✅ ตรวจสอบ RabbitMQ server logs
2. ✅ ตรวจสอบ network connectivity
3. ⏳ เพิ่ม connection resilience
4. ⏳ ปรับปรุง error handling
5. ⏳ เพิ่ม monitoring และ alerting

### 7. หมายเหตุ

- Worker ใช้ `connect_robust` ซึ่งควร auto-reconnect
- แต่ worker exit หลังจากได้รับ SIGTERM
- อาจเป็นเพราะ RabbitMQ server restart → Connection หลุด → Worker ไม่สามารถ handle ได้ → Exit

