# 🎯 Resource Management Strategy สำหรับ 25 Concurrent Tasks

## 📊 สถานะปัจจุบัน

### Current Implementation
```python
# GPU Concurrency Control (Semaphore-based)
GPU_CONCURRENCY = 25  # Fixed limit: 25 concurrent GPU tasks
gpu_semaphore = threading.Semaphore(GPU_CONCURRENCY)

# Queue Limits (Admission Control)
MAX_QUEUE_REQUEST = 51
MAX_QUEUE_EXTRACTION = 80
MAX_QUEUE_TRANSCRIBE = 30
```

### ข้อดีของ Semaphore-based Approach
- ✅ **Simple & Stable**: ง่ายต่อการ implement และ maintain
- ✅ **Predictable**: รู้แน่ชัดว่าจะมีกี่ tasks พร้อมกัน
- ✅ **Prevents Overload**: ป้องกัน GPU memory overflow
- ✅ **Fair Scheduling**: Tasks ได้ resource เท่าๆ กัน

## 🤔 คำถาม: Dynamic Resource Allocation

### Option 1: Dynamic Resource Division (1 task = 80%, 25 tasks = 3.2% each)

**แนวคิด**: แบ่ง resource ตามจำนวน tasks ที่กำลังทำงาน

#### ข้อดี
- ✅ **Flexible**: Resource เปลี่ยนแปลงตาม workload
- ✅ **Efficient**: ใช้ resource อย่างเต็มที่

#### ข้อเสีย
- ❌ **Complex**: ซับซ้อนมากในการ implement
- ❌ **GPU Memory**: Model ต้อง load ทั้งตัว (ไม่สามารถแบ่งได้)
- ❌ **Unpredictable**: ยากต่อการ predict performance
- ❌ **Fairness**: Tasks อาจได้ resource ไม่เท่ากัน
- ❌ **Overhead**: ต้อง monitor และ adjust ตลอดเวลา

#### Implementation Challenges
```python
# ❌ ไม่สามารถทำได้ง่ายๆ
# GPU memory ไม่สามารถแบ่งแบบ dynamic ได้
# Model ต้อง load ทั้งตัว (~1-2GB per instance)

# CPU สามารถทำได้แต่ซับซ้อน
import cgroups
# ต้องใช้ cgroups หรือ systemd limits
# ต้อง monitor CPU usage และ adjust limits
```

### Option 2: Fixed Limit with Monitoring (แนะนำ) ⭐

**แนวคิด**: ใช้ fixed limit แต่ monitor และ adjust ตามความต้องการ

#### ข้อดี
- ✅ **Simple**: ง่ายต่อการ implement
- ✅ **Stable**: เสถียรและ predictable
- ✅ **Prevents Overload**: ป้องกัน overload ได้ดี
- ✅ **Scalable**: สามารถเพิ่ม limit ได้ตาม GPU memory

#### Implementation
```python
# Current: Fixed limit
GPU_CONCURRENCY = 25

# Enhanced: Adaptive limit based on GPU memory
def get_adaptive_gpu_concurrency():
    """Calculate GPU concurrency based on available VRAM"""
    import subprocess
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=memory.total,memory.free', '--format=csv,noheader'],
        capture_output=True, text=True
    )
    # Parse and calculate optimal concurrency
    # Return max concurrent tasks based on available VRAM
    pass
```

## 🎯 แนะนำ: Hybrid Approach

### Strategy 1: Fixed Limit with Safety Buffer (ปัจจุบัน) ✅

```python
# Fixed limit based on GPU memory
GPU_CONCURRENCY = 25  # สำหรับ RTX 4000 Ada 20GB

# Safety buffer: ใช้แค่ 80% ของ available memory
# 25 tasks × 0.7GB = 17.5GB (เหลือ 2.5GB buffer)
```

**ข้อดี**:
- ✅ Simple และเสถียร
- ✅ ป้องกัน OOM
- ✅ Predictable performance

### Strategy 2: Adaptive Limit with Monitoring ⭐ (แนะนำสำหรับ Production)

```python
# Monitor GPU memory และ adjust limit dynamically
class AdaptiveGPUConcurrency:
    def __init__(self, base_limit=25, min_limit=10, max_limit=30):
        self.base_limit = base_limit
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.current_limit = base_limit
    
    def update_limit(self):
        """Update limit based on GPU memory usage"""
        available_vram = self.get_available_vram()
        model_memory = 0.7  # GB per task (base model)
        
        # Calculate optimal limit
        optimal = int(available_vram * 0.8 / model_memory)  # 80% safety
        optimal = max(self.min_limit, min(optimal, self.max_limit))
        
        if optimal != self.current_limit:
            logger.info(f"Adjusting GPU concurrency: {self.current_limit} → {optimal}")
            self.current_limit = optimal
        
        return self.current_limit
    
    def get_available_vram(self):
        """Get available VRAM in GB"""
        # Use nvidia-smi or pynvml
        pass
```

**ข้อดี**:
- ✅ Adaptive ตาม GPU memory
- ✅ ป้องกัน OOM
- ✅ ใช้ resource อย่างมีประสิทธิภาพ

### Strategy 3: Queue-based Throttling

```python
# Throttle based on queue size
def should_accept_task():
    queue_size = get_queue_size('transcription_queue')
    max_queue = MAX_QUEUE_TRANSCRIBE
    
    # Reject if queue is > 80% full
    if queue_size > max_queue * 0.8:
        return False
    
    return True
```

## 📊 เปรียบเทียบ

| Strategy | Complexity | Stability | Efficiency | Recommended |
|----------|-----------|-----------|------------|-------------|
| **Dynamic Division** | ❌ Very High | ⚠️ Low | ✅ High | ❌ No |
| **Fixed Limit** | ✅ Low | ✅ High | ⚠️ Medium | ✅ Yes (Current) |
| **Adaptive Limit** | ⚠️ Medium | ✅ High | ✅ High | ⭐ Yes (Recommended) |
| **Queue Throttling** | ✅ Low | ✅ High | ⚠️ Medium | ✅ Yes (Additional) |

## 🎯 คำแนะนำสำหรับ Production

### 1. ใช้ Fixed Limit + Safety Buffer (ปัจจุบัน) ✅

```bash
# env.runpod
GPU_CONCURRENCY=25  # Fixed limit
MAX_QUEUE_TRANSCRIBE=30  # Queue limit
```

**เหตุผล**:
- ✅ Simple และเสถียร
- ✅ ป้องกัน overload
- ✅ Predictable performance
- ✅ ง่ายต่อการ debug

### 2. เพิ่ม Monitoring และ Alerts

```python
# Monitor GPU memory usage
def monitor_gpu_usage():
    """Monitor and alert if GPU usage is high"""
    vram_used = get_gpu_memory_used()
    vram_total = get_gpu_memory_total()
    usage_percent = (vram_used / vram_total) * 100
    
    if usage_percent > 90:
        logger.warning(f"⚠️ GPU memory usage high: {usage_percent:.1f}%")
        # Send alert
```

### 3. เพิ่ม Queue-based Admission Control

```python
# Reject tasks if queue is too full
if queue_size > MAX_QUEUE_TRANSCRIBE * 0.8:
    raise HTTPException(503, "Queue is nearly full")
```

### 4. (Optional) Adaptive Limit สำหรับ Advanced Use Cases

```python
# Only if needed for dynamic workloads
adaptive_concurrency = AdaptiveGPUConcurrency(
    base_limit=25,
    min_limit=10,
    max_limit=30
)
```

## ✅ สรุป

### คำตอบ: **ไม่ควรใช้ Dynamic Division**

**เหตุผล**:
1. **GPU Memory**: Model ต้อง load ทั้งตัว ไม่สามารถแบ่งได้
2. **Complexity**: ซับซ้อนมากและยากต่อการ maintain
3. **Stability**: อาจทำให้ระบบไม่เสถียร
4. **Fairness**: Tasks อาจได้ resource ไม่เท่ากัน

### แนะนำ: **ใช้ Fixed Limit + Monitoring**

**Strategy**:
1. ✅ **Fixed Limit**: `GPU_CONCURRENCY=25` (ตาม GPU memory)
2. ✅ **Safety Buffer**: ใช้แค่ 80% ของ available memory
3. ✅ **Queue Limits**: ป้องกัน overload
4. ✅ **Monitoring**: Monitor GPU usage และ alert
5. ⭐ **Optional**: Adaptive limit สำหรับ advanced use cases

**ผลลัพธ์**:
- ✅ เสถียรและ predictable
- ✅ ป้องกัน overload
- ✅ ง่ายต่อการ maintain
- ✅ ใช้ resource อย่างมีประสิทธิภาพ



