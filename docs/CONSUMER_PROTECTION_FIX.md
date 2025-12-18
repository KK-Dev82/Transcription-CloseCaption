# Consumer Protection Fix - ป้องกันไม่ให้ Consumers หายไป

## ปัญหาเดิม

1. **Connection Monitor ช้า**: ตรวจสอบทุก 5 วินาที → อาจ miss reconnection events
2. **No Retry Logic**: Re-register consumers ล้มเหลว → consumers หายไป
3. **No Health Check**: ไม่ตรวจสอบว่า connection และ channel พร้อมก่อน re-register
4. **No Proactive Monitoring**: ไม่ตรวจสอบ consumers ว่ายังทำงานอยู่

## การแก้ไข

### 1. ปรับปรุง Connection Monitor (video_worker.py)

**เดิม:**
- ตรวจสอบทุก 5 วินาที
- Detect reconnection: closed → open
- No retry logic

**ใหม่:**
- ตรวจสอบทุก **1 วินาที** (เร็วขึ้น 5 เท่า)
- Track consecutive closed state
- Retry re-registration **5 ครั้ง** ถ้าล้มเหลว
- Proactive consumer health check ทุก 10 วินาที

```python
async def _monitor_connection_and_reconnect(self):
    # Check every 1 second (faster detection)
    await asyncio.sleep(1)
    
    # Track consecutive closed state
    if current_state == "closed":
        consecutive_closed_count += 1
    else:
        if consecutive_closed_count > 0:
            # Connection just reconnected
            # Re-register with retry
            success = await self._re_register_consumers_with_retry(max_retries=5, retry_delay=1)
```

### 2. เพิ่ม Consumer Re-registration Retry

**ใหม่:**
- Retry **5 ครั้ง** ใน connection monitor
- Retry **3 ครั้ง** ใน reconnect callback
- Delay ระหว่าง retry (1 วินาที)

```python
async def _re_register_consumers_with_retry(self, max_retries: int = 5, retry_delay: int = 1) -> bool:
    for attempt in range(max_retries):
        try:
            if await self.connection.handle_reconnection():
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    return False
```

### 3. เพิ่ม Connection Health Check

**ใหม่:**
- ตรวจสอบ connection และ channel ก่อน re-register
- Test channel ด้วย lightweight operation
- Return False ถ้าไม่ healthy

```python
async def check_connection_health(self) -> bool:
    # Check connection
    if not self.connection or self.connection.is_closed:
        return False
    
    # Check channel
    if not self.channel or self.channel.is_closed:
        return False
    
    # Test channel with lightweight operation
    try:
        test_queue = await self.channel.get_queue('transcription_request_queue', ensure=False)
        return True
    except Exception:
        # Try declaring a test queue
        try:
            test_queue = await self.channel.declare_queue('_health_check_temp', auto_delete=True, durable=False)
            await test_queue.delete()
            return True
        except Exception:
            return False
```

### 4. Proactive Consumer Health Monitoring

**ใหม่:**
- ตรวจสอบ consumers ทุก 10 วินาที
- Re-register consumers ถ้า connection health check fail

```python
async def _check_consumer_health(self):
    # Check every 10 seconds
    if current_time - self._last_consumer_health_check < 10:
        return
    
    # Check connection health
    if await self.connection.check_connection_health():
        # Connection is healthy
        pass
    else:
        # Try to re-register consumers proactively
        await self._re_register_consumers_with_retry(max_retries=3, retry_delay=1)
```

### 5. ปรับปรุง Reconnection Handling

**เดิม:**
- Recreate channel ทันที
- No stabilization wait
- No cleanup old channel

**ใหม่:**
- Wait 0.3 วินาที สำหรับ connection stabilization
- Close old channel ก่อน recreate (cleanup)
- Double-check connection state

```python
async def handle_reconnection(self):
    # Wait for connection to stabilize
    await asyncio.sleep(0.3)
    
    # Double-check connection is still ready
    if not self.connection or self.connection.is_closed:
        return False
    
    # Close old channel if exists (cleanup)
    if self.channel and not self.channel.is_closed:
        try:
            await self.channel.close()
        except Exception:
            pass
    
    # Recreate channel
    self.channel = await self.connection.channel()
```

### 6. ปรับปรุง Reconnect Callback

**เดิม:**
- No retry logic
- Fail → consumers หายไป

**ใหม่:**
- Retry **3 ครั้ง**
- Wait 0.2 วินาที สำหรับ channel ready
- Log warnings สำหรับแต่ละ attempt

```python
async def re_register_consumers():
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Wait for channel to be ready
            await asyncio.sleep(0.2)
            
            # Update and re-register
            self.consumers.update_channel(self.connection.channel)
            await self.consumers.setup_consumers()
            return  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
```

## ผลลัพธ์ที่คาดหวัง

### ✅ ปรับปรุง
1. **Detection เร็วขึ้น**: 1 วินาที แทน 5 วินาที → detect reconnection เร็วขึ้น 5 เท่า
2. **Retry Logic**: Re-register consumers ล้มเหลว → retry อัตโนมัติ
3. **Health Check**: ตรวจสอบ connection และ channel ก่อน re-register
4. **Proactive Monitoring**: ตรวจสอบ consumers ว่ายังทำงานอยู่
5. **Better Reconnection**: Wait for stabilization, cleanup old channel

### 📊 เปรียบเทียบ

| ด้าน | เดิม | ใหม่ |
|------|------|------|
| Detection Interval | 5 วินาที | 1 วินาที |
| Retry Logic | ไม่มี | 5 ครั้ง (monitor) + 3 ครั้ง (callback) |
| Health Check | ไม่มี | มี (connection + channel) |
| Proactive Monitoring | ไม่มี | ทุก 10 วินาที |
| Reconnection Handling | Basic | Improved (stabilization + cleanup) |

### 🎯 ผลลัพธ์

1. **Consumers จะไม่หายไปบ่อย**
   - Retry logic → re-register สำเร็จแม้มีปัญหา
   - Health check → re-register เฉพาะเมื่อพร้อม
   - Proactive monitoring → detect และแก้ไขก่อนปัญหา

2. **Re-register consumers อัตโนมัติเมื่อ reconnect**
   - Detect reconnection เร็วขึ้น (1 วินาที)
   - Retry อัตโนมัติถ้าล้มเหลว
   - Health check ก่อน re-register

3. **Detect และแก้ไขปัญหาเร็วขึ้น**
   - Connection monitor เร็วขึ้น
   - Proactive health check
   - Better error handling

## การทดสอบ

### 1. ทดสอบ Connection Reconnect
```bash
# Restart RabbitMQ server
# ตรวจสอบว่า consumers re-register อัตโนมัติ
```

### 2. ทดสอบ Retry Logic
```bash
# Simulate reconnection failure
# ตรวจสอบว่า retry หลายครั้ง
```

### 3. ทดสอบ Health Check
```bash
# Simulate unhealthy connection
# ตรวจสอบว่าไม่ re-register ถ้าไม่ healthy
```

### 4. ทดสอบ Proactive Monitoring
```bash
# ตรวจสอบว่า consumer health check ทำงานทุก 10 วินาที
```

## ไฟล์ที่แก้ไข

1. `app/workers/async/video_worker.py`
   - `_monitor_connection_and_reconnect()` - ปรับปรุง connection monitor
   - `_re_register_consumers_with_retry()` - เพิ่ม retry logic
   - `_check_consumer_health()` - เพิ่ม proactive monitoring
   - `re_register_consumers()` - เพิ่ม retry logic ใน callback

2. `app/workers/async/connection.py`
   - `handle_reconnection()` - ปรับปรุง reconnection handling
   - `check_connection_health()` - เพิ่ม health check

## สรุป

การแก้ไขนี้จะช่วยป้องกันไม่ให้ consumers หายไปโดย:
- **Detection เร็วขึ้น** (1 วินาที แทน 5 วินาที)
- **Retry logic** (5 ครั้ง + 3 ครั้ง)
- **Health check** (ตรวจสอบก่อน re-register)
- **Proactive monitoring** (ตรวจสอบทุก 10 วินาที)
- **Better reconnection** (stabilization + cleanup)

Consumers จะ re-register อัตโนมัติเมื่อ reconnect และจะไม่หายไปบ่อยอีกต่อไป!



