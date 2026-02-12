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