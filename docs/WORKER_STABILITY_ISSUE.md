# Worker Stability Issue

## ปัญหา

Worker หยุดทำงานบ่อย (ถูก kill ด้วย SIGTERM - signal 15)

### อาการ

1. Worker process หายไป (PID ไม่ running)
2. Consumers = 0 (ทั้งหมด)
3. Messages ค้างใน queue
4. Worker logs แสดง "ได้รับ signal 15 กำลังปิด worker..."

### สาเหตุที่เป็นไปได้

1. **Health Check Auto-Restart**: Health check script อาจ restart worker ถ้า health check fail
2. **Manual Restart**: มี scripts หลายตัวที่ kill worker:
   - `restart-worker-only.sh`
   - `restart-service-daemon.sh`
   - `stop-pod.sh`
3. **RabbitMQ Connection Issues**: Worker อาจ disconnect จาก RabbitMQ บ่อย
4. **System Resource Issues**: Memory หรือ CPU issues
5. **Signal Handler**: Worker อาจได้รับ SIGTERM จาก system หรือ process manager

### การแก้ไขชั่วคราว

1. **Restart Worker**:
   ```bash
   bash scripts/pod/restart-worker-only.sh
   ```

2. **ตรวจสอบ Status**:
   ```bash
   bash scripts/pod/worker-health-check.sh
   ```

3. **ตรวจสอบ Logs**:
   ```bash
   tail -f logs/video-worker.log
   tail -f logs/video-worker-errors.log
   ```

### การแก้ไขระยะยาว

1. **ปรับปรุง Health Check**: ตรวจสอบว่า health check ไม่ restart worker บ่อยเกินไป
2. **ปรับปรุง Signal Handling**: เพิ่ม logging เพื่อติดตามว่าใครเป็นคนส่ง signal
3. **ปรับปรุง RabbitMQ Reconnection**: ให้ worker reconnect อัตโนมัติเมื่อ connection หลุด
4. **Monitoring**: เพิ่ม monitoring เพื่อแจ้งเตือนเมื่อ worker หยุดทำงาน

### หมายเหตุ

- Worker มี infinite retry loop สำหรับ connection แต่ถ้าได้รับ SIGTERM จะ exit
- Health check script มี auto-restart ถ้า health check fail
- ควรตรวจสอบว่าใครเป็นคนส่ง SIGTERM ให้ worker

