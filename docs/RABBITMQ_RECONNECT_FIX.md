# 🔄 RabbitMQ Reconnection & Consumer Re-registration Fix

## 📋 ปัญหา

เมื่อ RabbitMQ server restart (เนื่องจาก memory เต็มจาก spyware/bitcoin mining):
1. ✅ `connect_robust` จะ reconnect อัตโนมัติ
2. ❌ แต่ consumers **ไม่ได้ re-register** อัตโนมัติ
3. ❌ Worker จะไม่ consume messages แม้ว่า connection จะ reconnect แล้ว

## ✅ การแก้ไข

### 1. เพิ่ม Connection Callbacks

**ไฟล์**: `app/workers/async/connection.py`

**เพิ่ม**:
- `_on_connection_close()` - จัดการเมื่อ connection หลุด
- `_on_connection_reconnect()` - จัดการเมื่อ reconnect (recreate channel, re-declare queues)
- `set_reconnect_callback()` - ตั้งค่า callback เพื่อ re-register consumers

```python
def _on_connection_close(self, connection, exception):
    """Handle connection close event"""
    logger.warning(f"⚠️ RabbitMQ connection closed: {exception}")
    # Channel will be invalidated, need to recreate after reconnect
    self.channel = None
    self.media_exchange = None
    self.transcription_exchange = None

async def _on_connection_reconnect(self, connection):
    """Handle reconnection event - recreate channel and re-register consumers"""
    logger.info("🔄 RabbitMQ connection reconnected, recreating channel and re-registering consumers...")
    
    try:
        # Recreate channel
        self.channel = await self.connection.channel()
        logger.info("✅ Channel recreated after reconnect")
        
        # Re-declare exchanges
        await self._declare_exchanges()
        logger.info("✅ Exchanges re-declared after reconnect")
        
        # Re-declare queues
        await self._declare_legacy_queues()
        await self._declare_quorum_queues()
        logger.info("✅ Queues re-declared after reconnect")
        
        # Call re-register consumers callback if set
        if self.on_reconnect_callback:
            logger.info("🔄 Re-registering consumers after reconnect...")
            await self.on_reconnect_callback()
            logger.info("✅ Consumers re-registered after reconnect")
        else:
            logger.warning("⚠️ No reconnect callback set - consumers may not be re-registered")
            
    except Exception as e:
        logger.error(f"❌ Error during reconnection setup: {e}", exc_info=True)
        # Don't raise - let connect_robust handle retry
```

### 2. Setup Reconnect Callback ใน Worker

**ไฟล์**: `app/workers/async/video_worker.py`

**เพิ่ม**:
- Reconnect callback เพื่อ re-register consumers หลังจาก reconnect

```python
# Setup reconnect callback to re-register consumers after RabbitMQ restart
async def re_register_consumers():
    """Re-register consumers after reconnection"""
    try:
        logger.info("🔄 Re-registering consumers after RabbitMQ reconnect...")
        # Update consumer manager with new channel
        self.consumers.update_channel(self.connection.channel)
        # Re-register all consumers
        await self.consumers.setup_consumers()
        logger.info("✅ All consumers re-registered after RabbitMQ reconnect")
    except Exception as e:
        logger.error(f"❌ Failed to re-register consumers after reconnect: {e}", exc_info=True)
        # Don't raise - let worker retry in main loop

# Set reconnect callback
self.connection.set_reconnect_callback(re_register_consumers)
```

### 3. เพิ่ม Method ใน ConsumerManager

**ไฟล์**: `app/workers/async/consumers.py`

**เพิ่ม**:
- `update_channel()` - อัปเดต channel หลังจาก reconnect

```python
def update_channel(self, new_channel):
    """Update channel after reconnection"""
    self.channel = new_channel
    # Clear queues as they need to be re-declared with new channel
    self.queues.clear()
```

## 🔄 Flow เมื่อ RabbitMQ Restart

1. **RabbitMQ Restart** → Connection หลุด
2. **`_on_connection_close()`** → Log warning, clear channel/exchanges
3. **`connect_robust` auto-reconnect** → Connection reconnect อัตโนมัติ
4. **`_on_connection_reconnect()`** → 
   - Recreate channel
   - Re-declare exchanges
   - Re-declare queues
   - Call `re_register_consumers()` callback
5. **`re_register_consumers()`** →
   - Update consumer manager channel
   - Re-register all consumers
6. **✅ Worker กลับมาทำงานปกติ** → Consumers เริ่ม consume messages อีกครั้ง

## 📊 Log Messages

เมื่อ RabbitMQ restart จะเห็น logs แบบนี้:

```
⚠️ RabbitMQ connection closed: <exception>
🔄 RabbitMQ connection reconnected, recreating channel and re-registering consumers...
✅ Channel recreated after reconnect
✅ Exchanges re-declared after reconnect
✅ Queues re-declared after reconnect
🔄 Re-registering consumers after reconnect...
✅ Consumer registered for transcription_request_queue
✅ Consumer registered for audio_extraction_queue
...
✅ All consumers re-registered after RabbitMQ reconnect
✅ Consumers re-registered after reconnect
```

## 🧪 การทดสอบ

### 1. ทดสอบ Manual Restart RabbitMQ

```bash
# Restart RabbitMQ server
sudo systemctl restart rabbitmq-server

# ตรวจสอบ logs
tail -f logs/video-worker.log | grep -E "reconnect|re-register|Consumer registered"
```

### 2. ทดสอบ Connection Loss

```bash
# Block RabbitMQ port temporarily
sudo iptables -A INPUT -p tcp --dport 5672 -j DROP

# Wait 10 seconds
sleep 10

# Unblock
sudo iptables -D INPUT -p tcp --dport 5672 -j DROP

# ตรวจสอบ logs
tail -f logs/video-worker.log | grep -E "reconnect|re-register"
```

### 3. ตรวจสอบ Consumers

```bash
# ตรวจสอบ consumers ใน RabbitMQ Management UI
# หรือใช้ rabbitmqadmin
rabbitmqadmin list queues name consumers
```

## ✅ ผลลัพธ์

หลังจากแก้ไข:
- ✅ Worker จะ reconnect อัตโนมัติเมื่อ RabbitMQ restart
- ✅ Consumers จะ re-register อัตโนมัติหลังจาก reconnect
- ✅ Worker จะกลับมาทำงานปกติโดยไม่ต้อง restart
- ✅ Messages จะถูก consume ต่อเนื่องแม้ว่า RabbitMQ จะ restart

## 📝 Notes

1. **`connect_robust`** - มี auto-reconnect แต่ต้อง re-register consumers เอง
2. **Connection callbacks** - ใช้เพื่อ detect reconnection และ re-register consumers
3. **Channel recreation** - Channel ต้องสร้างใหม่หลังจาก reconnect
4. **Queue re-declaration** - Queues ต้อง re-declare หลังจาก reconnect

## 🔧 Troubleshooting

### Consumers ไม่ re-register

**ตรวจสอบ**:
1. Logs - ดูว่า `_on_connection_reconnect()` ถูกเรียกหรือไม่
2. Callback - ตรวจสอบว่า `set_reconnect_callback()` ถูกเรียกหรือไม่
3. Channel - ตรวจสอบว่า channel ถูก recreate หรือไม่

**แก้ไข**:
- ตรวจสอบ logs: `tail -f logs/video-worker.log | grep reconnect`
- Restart worker: `bash scripts/pod/restart-worker-only.sh`

### Connection ไม่ reconnect

**ตรวจสอบ**:
1. RabbitMQ server - ตรวจสอบว่า RabbitMQ ทำงานอยู่
2. Network - ตรวจสอบ network connectivity
3. Heartbeat - ตรวจสอบ heartbeat timeout

**แก้ไข**:
- ตรวจสอบ RabbitMQ: `rabbitmqctl status`
- ตรวจสอบ network: `ping <rabbitmq_host>`
- เพิ่ม heartbeat timeout ใน `env.runpod`: `RABBITMQ_HEARTBEAT_TIMEOUT=1800`

