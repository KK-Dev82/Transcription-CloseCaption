# ลบทั้งหมด
./scripts/utility/clear-cc-temp.sh 0

# ลบเฉพาะไฟล์เก่ากว่า 2 ชั่วโมง
./scripts/utility/clear-cc-temp.sh 2

### Restart (เมื่อแก้ไข config หรือต้องการ restart services)

```bash
./scripts/pod/restart-main-api.sh && ./scripts/pod/restart-rq-workers.sh
```