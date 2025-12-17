# 🔍 Worker Consumer Issue Analysis & Long-term Solution

## 📋 ปัญหา

**อาการ**: Worker process มีอยู่ แต่ Consumers = 0 ทั้งหมด
- Queue มี messages (3 messages ใน transcription_request_queue)
- Worker process running (PID 116842)
- แต่ RabbitMQ ไม่มี consumers registered

## 🔍 สาเหตุที่เป็นไปได้

### 1. Worker Connection Issues

**ปัญหา**: Worker ไม่ได้ connect ไปที่ RabbitMQ หรือ connection หลุด

**สาเหตุ**:
- RabbitMQ connection timeout
- Network issues
- Credentials ผิด
- RabbitMQ server down

**ตรวจสอบ**:
```bash
# Check worker logs
tail -100 /tmp/video-worker.log | grep -i "rabbitmq\|connection\|error"

# Check RabbitMQ connection
python3 -c "
import pika
import os
from dotenv import load_dotenv
load_dotenv('env.runpod')
conn = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST'),
        port=int(os.getenv('RABBITMQ_PORT', '5672')),
        credentials=pika.PlainCredentials(
            os.getenv('RABBITMQ_USER'),
            os.getenv('RABBITMQ_PASSWORD')
        )
    )
)
print('✅ RabbitMQ connection OK')
conn.close()
"
```

### 2. Consumer Registration Failed

**ปัญหา**: Worker start แล้วแต่ consumers ไม่ได้ register

**สาเหตุ**:
- Consumer registration code มี error
- Queue declaration failed
- Permission issues

**ตรวจสอบ**:
```bash
# Check consumer registration in logs
tail -100 /tmp/video-worker.log | grep -i "consumer\|registered\|listening"
```

### 3. Worker Process Stuck

**ปัญหา**: Worker process มีอยู่แต่ไม่ได้ consume messages

**สาเหตุ**:
- Worker stuck ใน infinite loop
- Blocking operation
- Deadlock

**ตรวจสอบ**:
```bash
# Check worker CPU usage
ps aux | grep video_worker | grep -v grep

# Check if worker is responsive
kill -0 $(pgrep -f video_worker | head -1) && echo "Alive" || echo "Dead"
```

### 4. Multiple Worker Instances

**ปัญหา**: มี worker หลายตัว แต่ตัวที่ทำงานจริงไม่ได้ register consumers

**สาเหตุ**:
- Worker instances เก่ายังทำงานอยู่
- New worker ไม่ได้ start
- Race condition

**ตรวจสอบ**:
```bash
# Check all worker processes
ps aux | grep video_worker | grep -v grep

# Kill all and restart
pkill -f video_worker
bash scripts/pod/start-video-worker-daemon.sh
```

## ✅ แนวทางแก้ไขระยะยาว

### Solution 1: Worker Health Check & Auto-Restart

**สร้าง**: Worker health check script ที่ตรวจสอบ:
1. Worker process running
2. Consumers registered
3. RabbitMQ connection active

**Implementation**:
```bash
#!/bin/bash
# scripts/pod/worker-health-check.sh

check_worker_health() {
    # Check process
    if ! pgrep -f "python.*video_worker" > /dev/null; then
        return 1
    fi
    
    # Check consumers
    python3 << 'EOF'
import pika
import os
from dotenv import load_dotenv
load_dotenv('env.runpod')

try:
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST'),
            port=int(os.getenv('RABBITMQ_PORT', '5672')),
            credentials=pika.PlainCredentials(
                os.getenv('RABBITMQ_USER'),
                os.getenv('RABBITMQ_PASSWORD')
            )
        )
    )
    channel = conn.channel()
    
    # Check consumers for critical queues
    queues = ['transcription_request_queue', 'audio_extraction_queue']
    for queue in queues:
        method = channel.queue_declare(queue=queue, passive=True)
        if method.method.consumer_count == 0:
            print(f"❌ No consumers for {queue}")
            exit(1)
    
    conn.close()
    print("✅ All queues have consumers")
    exit(0)
except Exception as e:
    print(f"❌ Health check failed: {e}")
    exit(1)
EOF
}

# Run health check
if ! check_worker_health; then
    echo "⚠️  Worker unhealthy, restarting..."
    bash scripts/pod/restart-worker-only.sh
fi
```

**Schedule**: Run every 5 minutes via cron
```bash
# Add to crontab
*/5 * * * * /workspace/transcription-service/scripts/pod/worker-health-check.sh
```

### Solution 2: Improve Worker Startup Script

**แก้ไข**: `scripts/pod/start-video-worker-daemon.sh`

**เพิ่ม**:
1. Wait for consumers to register
2. Verify consumers after startup
3. Retry if consumers not registered

```bash
# After starting worker
sleep 10

# Verify consumers
python3 << 'EOF'
import pika
import os
import sys
from dotenv import load_dotenv
load_dotenv('env.runpod')

try:
    conn = pika.BlockingConnection(...)
    channel = conn.channel()
    method = channel.queue_declare('transcription_request_queue', passive=True)
    if method.method.consumer_count > 0:
        print("✅ Consumers registered")
        sys.exit(0)
    else:
        print("❌ No consumers registered")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "⚠️  Consumers not registered, retrying..."
    # Retry logic
fi
```

### Solution 3: Worker Monitoring & Alerting

**สร้าง**: Monitoring script ที่:
1. Monitor worker status
2. Alert when consumers = 0
3. Auto-restart if needed

**Implementation**:
```python
# scripts/pod/monitor_worker.py
import pika
import os
import time
import subprocess
from dotenv import load_dotenv

load_dotenv('env.runpod')

def check_consumers():
    """Check if workers have registered consumers"""
    try:
        conn = pika.BlockingConnection(...)
        channel = conn.channel()
        
        queues = ['transcription_request_queue', 'audio_extraction_queue']
        for queue in queues:
            method = channel.queue_declare(queue=queue, passive=True)
            if method.method.consumer_count == 0:
                return False
        return True
    except Exception as e:
        print(f"Error checking consumers: {e}")
        return False

def restart_worker():
    """Restart worker"""
    subprocess.run(['bash', 'scripts/pod/restart-worker-only.sh'])

# Main loop
while True:
    if not check_consumers():
        print("⚠️  No consumers detected, restarting worker...")
        restart_worker()
        time.sleep(30)  # Wait for restart
    else:
        print("✅ Workers healthy")
    time.sleep(60)  # Check every minute
```

### Solution 4: Improve Error Handling in Worker

**แก้ไข**: `app/workers/async/video_worker.py`

**เพิ่ม**:
1. Better error handling for connection failures
2. Retry logic for consumer registration
3. Health check endpoint

```python
# In video_worker.py
async def start_worker():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Connect to RabbitMQ
            connection = await connect_to_rabbitmq()
            
            # Register consumers
            await register_consumers(connection)
            
            # Verify consumers
            if await verify_consumers():
                logger.info("✅ Workers started successfully")
                return
            else:
                raise Exception("Consumers not registered")
                
        except Exception as e:
            retry_count += 1
            logger.error(f"Failed to start worker (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                await asyncio.sleep(10)
            else:
                logger.error("Max retries reached, exiting")
                raise
```

## 🎯 Recommended Long-term Solution

### Combined Approach:

1. **Worker Health Check Script** (Solution 1)
   - Run every 5 minutes
   - Auto-restart if unhealthy

2. **Improved Startup Script** (Solution 2)
   - Verify consumers after startup
   - Retry if failed

3. **Worker Monitoring** (Solution 3)
   - Continuous monitoring
   - Alert on issues

4. **Better Error Handling** (Solution 4)
   - Retry logic in worker
   - Better logging

## 📝 Implementation Priority

1. **Immediate**: Restart worker manually
2. **Short-term**: Add health check script
3. **Medium-term**: Improve startup script
4. **Long-term**: Add monitoring & better error handling

## 🔧 Quick Fix (Now)

```bash
# Kill all workers
pkill -f video_worker

# Restart worker
bash scripts/pod/restart-worker-only.sh

# Verify consumers
python3 << 'EOF'
import pika
import os
from dotenv import load_dotenv
load_dotenv('env.runpod')
conn = pika.BlockingConnection(...)
channel = conn.channel()
method = channel.queue_declare('transcription_request_queue', passive=True)
print(f"Consumers: {method.method.consumer_count}")
conn.close()
EOF
```


