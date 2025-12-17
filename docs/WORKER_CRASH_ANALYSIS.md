# 🔍 Worker Crash Analysis: ทำไม Worker ถึงดับบ่อย

## 📋 สรุปปัญหา

**อาการ**: Worker process ดับบ่อย (ถูก terminate ด้วย signal 15 - SIGTERM)

**สาเหตุที่เป็นไปได้**:
1. **External Termination** - ถูก terminate จาก restart scripts
2. **RabbitMQ Connection Loss** - Connection หลุดและไม่ reconnect
3. **TranscriptionService Errors** - Exception ที่ไม่ถูก handle
4. **Resource Exhaustion** - Memory/GPU issues

## 🔍 การวิเคราะห์

### 1. Signal 15 (SIGTERM) - External Termination

**พบใน logs**:
```
ได้รับ signal 15 กำลังปิด worker...
```

**สาเหตุ**:
- Restart scripts ส่ง SIGTERM
- System shutdown
- Manual kill commands

**ตรวจสอบ**:
```bash
# Check restart scripts
ps aux | grep -E "restart|kill|pkill" | grep -v grep

# Check if worker daemon is killing workers
ps aux | grep "start-video-worker-daemon"
```

### 2. RabbitMQ Connection Issues

**ปัญหาที่เป็นไปได้**:
- Connection timeout
- Network issues
- RabbitMQ server restart
- Heartbeat timeout

**Current Implementation**:
```python
# app/workers/async/connection.py
self.connection = await aio_pika.connect_robust(
    url,
    heartbeat=self.heartbeat  # Default: 1800s (30 min)
)
```

**Issues**:
- `connect_robust` มี auto-reconnect แต่ถ้า connection หลุดนาน worker อาจ exit
- Heartbeat timeout อาจทำให้ connection ถูก close

### 3. TranscriptionService Errors

**ปัญหาที่เป็นไปได้**:
- Unhandled exceptions
- GPU errors
- Memory errors
- File I/O errors

**Current Error Handling**:
```python
# app/workers/async/video_worker.py
except Exception as e:
    logger.error(f"❌ Fatal error in worker: {e}", exc_info=True)
    logger.warning("💡 Worker will retry in 30 seconds...")
    await asyncio.sleep(30)
```

**Issues**:
- Exception ใน handlers อาจทำให้ worker crash
- GPU errors อาจไม่ถูก catch

## ✅ แนวทางแก้ไข

### Solution 1: Improve RabbitMQ Connection Resilience

**แก้ไข**: `app/workers/async/connection.py`

**เพิ่ม**:
1. Better reconnection logic
2. Connection health monitoring
3. Automatic recovery

```python
async def connect(self, max_retries: int = 10, retry_delay: int = 5) -> bool:
    """Connect with improved error handling"""
    url = f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"
    
    for attempt in range(max_retries):
        try:
            # Use connect_robust for auto-reconnect
            self.connection = await aio_pika.connect_robust(
                url,
                heartbeat=self.heartbeat,
                client_properties={
                    'connection_name': f'video_worker_{os.getpid()}'
                }
            )
            
            # Setup connection callbacks
            self.connection.add_close_callback(self._on_connection_close)
            self.connection.add_reconnect_callback(self._on_connection_reconnect)
            
            self.channel = await self.connection.channel()
            
            # Declare queues
            await self._declare_exchanges()
            await self._declare_legacy_queues()
            await self._declare_quorum_queues()
            
            logger.info("✅ Connected to RabbitMQ successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect after {max_retries} attempts")
                return False
    
    return False

def _on_connection_close(self, connection, exception):
    """Handle connection close"""
    logger.warning(f"⚠️ RabbitMQ connection closed: {exception}")
    # Worker will retry in main loop

def _on_connection_reconnect(self, connection):
    """Handle reconnection"""
    logger.info("✅ RabbitMQ connection reconnected")
```

### Solution 2: Better Exception Handling in Handlers

**แก้ไข**: `app/workers/async/handlers.py`

**เพิ่ม**:
1. Try-catch ในทุก handler
2. Proper error logging
3. Message acknowledgment handling

```python
async def _process_transcription_request_task(self, message: aio_pika.IncomingMessage):
    """Process transcription request with better error handling"""
    task_id = None
    try:
        async with message.process():
            # Parse message
            task_data = json.loads(message.body.decode())
            task_id = task_data.get('task_id')
            
            # Process task
            await self._handle_transcription_request(task_data)
            
    except Exception as e:
        logger.error(f"❌ Error processing transcription request {task_id}: {e}", exc_info=True)
        
        # Update task status
        try:
            if task_id:
                await self._update_task_status(task_id, 'failed', str(e))
        except Exception as update_error:
            logger.error(f"❌ Failed to update task status: {update_error}")
        
        # Re-raise to let worker handle
        raise
```

### Solution 3: Worker Health Monitoring

**สร้าง**: Worker health check ที่ตรวจสอบ:
1. Process alive
2. RabbitMQ connection active
3. Consumers registered
4. No stuck tasks

**Implementation**: `scripts/pod/worker-health-check.sh` (already created)

### Solution 4: Prevent External Termination

**แก้ไข**: Restart scripts ให้ไม่ kill worker ถ้ายัง healthy

```bash
# In restart scripts
check_worker_health() {
    # Check if worker is actually processing
    if pgrep -f "python.*video_worker" > /dev/null; then
        # Check consumers
        python3 << 'EOF'
        # Check consumers code
        EOF
        
        if [ $? -eq 0 ]; then
            return 0  # Healthy, don't restart
        fi
    fi
    return 1  # Unhealthy, can restart
}

# Before killing worker
if check_worker_health; then
    echo "Worker is healthy, skipping restart"
    exit 0
fi
```

## 🎯 Recommended Solutions

### Priority 1: Improve Connection Resilience
- Better reconnection logic
- Connection health monitoring
- Automatic recovery

### Priority 2: Better Error Handling
- Try-catch ใน handlers
- Proper error logging
- Graceful degradation

### Priority 3: Health Monitoring
- Worker health check script
- Auto-restart on failure
- Prevent unnecessary restarts

### Priority 4: Logging & Debugging
- Better error logs
- Connection state logging
- Performance metrics

## 📝 Implementation Checklist

- [ ] Improve RabbitMQ connection resilience
- [ ] Add connection callbacks
- [ ] Better exception handling in handlers
- [ ] Worker health monitoring
- [ ] Prevent external termination
- [ ] Better logging
- [ ] Performance monitoring

## 🔧 Quick Fixes (Now)

1. **Check restart scripts**: ตรวจสอบว่าไม่มี script ที่ kill worker บ่อย
2. **Monitor logs**: ดู error logs เพื่อหาสาเหตุ
3. **Check RabbitMQ**: ตรวจสอบ RabbitMQ connection stability
4. **Worker health check**: ใช้ health check script ที่สร้างไว้

## 📊 Monitoring

### Key Metrics to Monitor:
1. Worker uptime
2. Connection failures
3. Exception rates
4. Message processing rate
5. Consumer registration status

### Alerts:
- Worker down > 1 minute
- Connection failures > 3 in 5 minutes
- Exception rate > 10%
- Consumers = 0


