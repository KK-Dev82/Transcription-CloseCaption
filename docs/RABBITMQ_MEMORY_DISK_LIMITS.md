# RabbitMQ Memory and Disk Limits Configuration

## 📋 Overview

RabbitMQ จะบล็อก publish ทั้งระบบเมื่อ memory หรือ disk ใกล้เต็ม เพื่อป้องกันระบบล่ม

## ⚠️ ปัญหาที่อาจเกิดขึ้น

1. **Memory Alarm:**
   - RabbitMQ ใช้ memory เกิน `vm_memory_high_watermark`
   - RabbitMQ จะบล็อก publish ทั้งระบบ
   - API จะได้ timeout หรือ error

2. **Disk Alarm:**
   - Disk space ต่ำกว่า `disk_free_limit`
   - RabbitMQ จะบล็อก publish ทั้งระบบ
   - API จะได้ timeout หรือ error

## 🔧 การตั้งค่า

### 1. ตั้งค่า Memory Limit

**ผ่าน RabbitMQ Management UI:**
1. เข้า http://178.128.105.100:15672
2. ไปที่ Admin → Policies
3. ตั้ง `vm_memory_high_watermark` = 0.4 (40% ของ RAM)

**ผ่าน RabbitMQ Config File:**
```bash
# /etc/rabbitmq/rabbitmq.conf
vm_memory_high_watermark.relative = 0.4
```

**ผ่าน Environment Variable:**
```bash
# docker-compose.yml หรือ .env
RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.4
```

### 2. ตั้งค่า Disk Limit

**ผ่าน RabbitMQ Management UI:**
1. เข้า http://178.128.105.100:15672
2. ไปที่ Admin → Policies
3. ตั้ง `disk_free_limit` = 2GB (หรือตาม disk space)

**ผ่าน RabbitMQ Config File:**
```bash
# /etc/rabbitmq/rabbitmq.conf
disk_free_limit.absolute = 2GB
```

**ผ่าน Environment Variable:**
```bash
# docker-compose.yml หรือ .env
RABBITMQ_DISK_FREE_LIMIT=2GB
```

## 📊 Monitoring

### ตรวจสอบ Memory Usage

```bash
# ผ่าน RabbitMQ Management API
curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/overview | jq '.object_totals'

# ตรวจสอบ memory
curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/nodes | jq '.[0].mem_used'
```

### ตรวจสอบ Disk Usage

```bash
# ตรวจสอบ disk space
df -h /var/lib/rabbitmq

# ตรวจสอบ queue sizes
curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/queues | jq '.[] | {name: .name, messages: .messages, memory: .memory}'
```

## 🚨 Alerts

### เมื่อ Memory Alarm เกิดขึ้น

1. **ตรวจสอบ queue sizes:**
   ```bash
   curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/queues | jq '.[] | select(.messages > 0) | {name: .name, messages: .messages, memory: .memory}'
   ```

2. **Purge old queues:**
   ```bash
   # ผ่าน Management UI หรือ API
   curl -X DELETE -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/queues/%2F/transcription_request_queue/contents
   ```

3. **Restart RabbitMQ (ถ้าจำเป็น):**
   ```bash
   sudo systemctl restart rabbitmq-server
   ```

### เมื่อ Disk Alarm เกิดขึ้น

1. **ตรวจสอบ disk space:**
   ```bash
   df -h /var/lib/rabbitmq
   ```

2. **Clean up old data:**
   ```bash
   # ลบ old queues
   # ลบ old logs
   # ลบ old messages
   ```

3. **เพิ่ม disk space หรือลด disk_free_limit**

## 📝 Recommended Settings

### สำหรับ Production (16GB RAM, 100GB Disk)

```bash
# Memory: 40% of RAM = 6.4GB
vm_memory_high_watermark.relative = 0.4

# Disk: 2GB free minimum
disk_free_limit.absolute = 2GB
```

### สำหรับ Development (8GB RAM, 50GB Disk)

```bash
# Memory: 50% of RAM = 4GB
vm_memory_high_watermark.relative = 0.5

# Disk: 1GB free minimum
disk_free_limit.absolute = 1GB
```

## 🔍 Troubleshooting

### RabbitMQ บล็อก publish

1. **ตรวจสอบ alarms:**
   ```bash
   curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/nodes | jq '.[0].mem_alarm, .[0].disk_free_alarm'
   ```

2. **ตรวจสอบ queue sizes:**
   ```bash
   curl -u senate:qP2VtHz6fAX4xDksEpMrLT http://178.128.105.100:15672/api/queues | jq '.[] | select(.messages > 0) | {name: .name, messages: .messages}'
   ```

3. **Purge queues ถ้าจำเป็น:**
   ```bash
   # ใช้ scripts/pod/restart-service-daemon.sh (จะ purge queues อัตโนมัติ)
   ```

## 📚 Related Documentation

- `docs/ADMISSION_CONTROL_ARCHITECTURE.md` - Admission control architecture
- `docs/ARCHITECTURE_RECOMMENDATIONS_ANALYSIS.md` - Architecture recommendations
- `scripts/pod/restart-service-daemon.sh` - Service restart script (includes queue purge)

