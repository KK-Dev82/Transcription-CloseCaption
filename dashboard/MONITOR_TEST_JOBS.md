# 📊 Monitor Test Jobs - คู่มือการใช้งาน

สคริปต์สำหรับติดตาม Logs และวิเคราะห์ผลลัพธ์ Transcription Jobs จากหน้า Test

## 🎯 วัตถุประสงค์

- ติดตาม status ของ transcription tasks จนกว่าจะเสร็จสมบูรณ์
- วิเคราะห์ผลลัพธ์: เวลาที่ใช้, คุณภาพภาษาไทย, อัตราความสำเร็จ
- เก็บผลลัพธ์เป็น JSON สำหรับการวิเคราะห์ต่อไป
- **ไม่รบกวนการ process ที่กำลังทำงาน** (read-only)

## 📋 วิธีใช้งาน

### 1. Monitor Tasks จาก Task IDs

```bash
cd dashboard
python monitor_test_jobs.py --server 4000-ada-sc --task-ids task1,task2,task3
```

### 2. Monitor Tasks จาก Batch ID

```bash
python monitor_test_jobs.py --server 4000-ada-sc --batch-id batch-123
```

### 3. Monitor Latest N Tasks

```bash
python monitor_test_jobs.py --server 4000-ada-sc --count 50
```

### 4. ตั้งค่า Custom Interval

```bash
python monitor_test_jobs.py --server 4000-ada-sc --count 50 --interval 5
```

## ⚙️ Options

- `--server` (required): Server name (4000-ada-sc, 4000-ada, 5080)
- `--task-ids`: Comma-separated task IDs
- `--batch-id`: Batch ID จาก batch transcription
- `--count`: Monitor latest N tasks
- `--dashboard-url`: Dashboard URL (default: http://localhost:8020)
- `--interval`: Check interval ในวินาที (default: 10)

## 📊 ผลลัพธ์ที่ได้

### 1. Console Output

สคริปต์จะแสดง:
- Progress ของ tasks (completed, failed, processing, pending)
- Elapsed time
- Analysis report เมื่อเสร็จสิ้น

### 2. JSON File

ผลลัพธ์จะถูกบันทึกเป็น JSON ที่:
```
dashboard/monitoring_results/test_results_{server}_{timestamp}.json
```

ไฟล์ JSON ประกอบด้วย:
- Task IDs และ task data ทั้งหมด
- Analysis results
- Processing times
- Text quality metrics
- Thai text analysis

## 📈 Analysis Report

Report จะแสดง:

### ✅ Success Metrics
- Total tasks, Completed, Failed
- Success rate

### ⏱️ Performance Metrics
- Processing times (average, min, max)
- Audio extraction times
- Transcription times
- Video durations

### 📝 Text Quality
- Average text length
- Thai character ratio
- Chunk counts

### ❌ Error Analysis
- Error messages
- Failed task IDs

## 💡 ตัวอย่างการใช้งาน

### ตัวอย่าง 1: Monitor Test Jobs จากหน้า Test

1. ไปที่หน้า Test ใน Dashboard
2. เลือก Server และ Video
3. ตั้งค่า Count (เช่น 50)
4. กด Start Test
5. Copy Task IDs ที่แสดงในหน้า Test
6. รันสคริปต์:

```bash
python monitor_test_jobs.py --server 4000-ada-sc --task-ids <task_ids>
```

### ตัวอย่าง 2: Monitor Batch Transcription

```bash
# เริ่ม batch transcription จาก Dashboard
# Copy batch ID ที่ได้
python monitor_test_jobs.py --server 4000-ada-sc --batch-id <batch_id>
```

### ตัวอย่าง 3: Monitor Latest Tasks

```bash
# Monitor latest 50 tasks
python monitor_test_jobs.py --server 4000-ada-sc --count 50
```

## 🔍 การวิเคราะห์ผลลัพธ์

### ดู JSON Results

```bash
cat monitoring_results/test_results_4000-ada-sc_20241212_143022.json | jq '.analysis'
```

### วิเคราะห์ Thai Text Quality

```bash
cat monitoring_results/test_results_*.json | jq '.analysis.thai_text_quality'
```

### ดู Processing Times

```bash
cat monitoring_results/test_results_*.json | jq '.analysis.processing_times'
```

## ⚠️ หมายเหตุ

- สคริปต์จะรอจนกว่า tasks ทั้งหมดจะเสร็จ (completed หรือ failed)
- Timeout: 1 ชั่วโมง (สามารถปรับได้ในโค้ด)
- สคริปต์เป็น read-only ไม่รบกวนการ process
- ต้องมี Dashboard ทำงานอยู่ที่ `http://localhost:8020`

## 🐛 Troubleshooting

### Error: Server not found
- ตรวจสอบว่า server name ถูกต้อง (4000-ada-sc, 4000-ada, 5080)
- ตรวจสอบ `server_constants.py`

### Error: Cannot connect to Dashboard
- ตรวจสอบว่า Dashboard ทำงานอยู่: `curl http://localhost:8020/health`
- ตรวจสอบ `--dashboard-url` parameter

### Error: No tasks found
- ตรวจสอบว่า task IDs ถูกต้อง
- ตรวจสอบว่า tasks ยังอยู่ในระบบ

## 📝 ตัวอย่าง Output

```
================================================================================
  Monitoring 50 tasks on 4000-ada-sc
================================================================================
[14:30:22] Dashboard: http://localhost:8020
[14:30:22] Server API: http://213.173.108.6:10889
[14:30:22] Check interval: 10 seconds

[14:30:32] Progress: 5/50 finished (✅ 3 completed, ❌ 2 failed, ⏳ 20 processing, 📋 25 pending) | Elapsed: 0m 10s
[14:30:42] Progress: 15/50 finished (✅ 12 completed, ❌ 3 failed, ⏳ 15 processing, 📋 20 pending) | Elapsed: 0m 20s
...

================================================================================
📊 TRANSCRIPTION TEST RESULTS ANALYSIS
================================================================================

Server: 4000-ada-sc
Total Tasks: 50
✅ Completed: 45
❌ Failed: 5
Success Rate: 90.0%

⏱️  Processing Times:
   Average: 45.32s
   Min: 12.5s
   Max: 120.3s

🇹🇭 Thai Text Quality:
   Tasks with Thai text: 45/45
   Thai character ratio: 85.2%
   Total Thai characters: 125,430

✅ Monitoring complete! Results saved to: monitoring_results/test_results_4000-ada-sc_20241212_143022.json
```

