# 📝 Async Handlers Implementation Note

**วันที่**: 2025-12-05

## ⚠️ สถานะ

Async handlers.py ยังไม่ได้สร้าง เนื่องจากไฟล์ใหญ่มาก (~750 lines, 9 handlers)

## 📋 Pattern ที่ต้องใช้

สำหรับ async handlers กับ aio-pika:

```python
import aio_pika
from aio_pika import IncomingMessage

async def handler(message: IncomingMessage):
    async with message.process():
        try:
            # Parse message
            task_data = json.loads(message.body.decode('utf-8'))
            
            # Process task
            await worker.processors.execute_task(task_data)
            
            # Auto-ack on success (via message.process())
            
        except Exception as e:
            # Auto-nack on error (via message.process())
            logger.error(f"Error: {e}")
            raise  # Raise to trigger nack
```

## 🔄 ความแตกต่าง

### Sync (pika)
- `def handler(ch, method, properties, body):`
- Manual ack: `ch.basic_ack(delivery_tag=method.delivery_tag)`
- Manual nack: `ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)`
- ต้องใช้ event loop management
- ต้องใช้ threads

### Async (aio-pika)
- `async def handler(message: IncomingMessage):`
- Auto-ack/nack: `async with message.process():`
- ไม่ต้องใช้ event loop management
- ไม่ต้องใช้ threads

---

**Next Steps**: สร้าง handlers.py ที่สมบูรณ์ (9 handlers)

