# ลบทั้งหมด
./scripts/utility/clear-cc-temp.sh 0

# ลบเฉพาะไฟล์เก่ากว่า 2 ชั่วโมง
./scripts/utility/clear-cc-temp.sh 2

### Restart (เมื่อแก้ไข config หรือต้องการ restart services)

```bash
./scripts/pod/restart-main-api.sh && ./scripts/pod/restart-rq-workers.sh
```


# ดู log Thai/Fuzzy/merging (ทุก CPU worker)
grep -h -E "Fuzzy|Thai|merging|Processed|🔤|🇹🇭" /tmp/rq-worker-cpu-*.log

# follow แบบ real-time — ดูทุก CPU (ใช้ -F รองรับ log truncate)
tail -F /tmp/rq-worker-cpu-{0,1,2,3,4,5,6,7}.log 2>/dev/null | grep -E "Fuzzy|Thai|merging|Processed|🔤|🇹🇭" --line-buffered

# ถ้ารู้ว่า task อยู่ worker ไหน (เช่น cpu-5): tail -F /tmp/rq-worker-cpu-5.log


# ตรวจสอบสถานะ
bash scripts/pod/check-pod.sh

# ถ้า Preprocess workers หยุดอีก
bash scripts/pod/restart-rq-workers.sh

# State DMON
## watch (แนะนำ)	
watch -n 1 './scripts/watch_resources.sh --once'

## loop ใน script	
./scripts/watch_resources.sh 1

## พร้อม log	
./scripts/watch_resources.sh 1 --log /tmp/resources.csv

# วิเคราะห์ Bottleneck (ใช้เวลาที่ไหนมาก)
python scripts/analyze_bottleneck.py --limit 10
