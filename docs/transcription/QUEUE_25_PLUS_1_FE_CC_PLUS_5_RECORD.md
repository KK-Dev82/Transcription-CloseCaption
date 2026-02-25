# Queue Configuration: 25 Upload + 1 FE CC + 5 Record

## สรุป

| ประเภท | Limit | ความหมาย |
|--------|-------|----------|
| **Upload** | 25 | รับได้สูงสุด 25 tasks, เต็มแล้วได้ 429 |
| **FE CC** | รับได้ตลอด | ไม่นับ limit, priority สูงสุด |
| **Record** | +5 | รับได้อีก 5 เมื่อ Upload เต็ม (25+5=30 total) |

## พฤติกรรม

- **Upload เต็ม 25**: Upload ใหม่ → 429
- **Record**: รับได้แม้ Upload เต็ม (รวมสูงสุด 30)
- **FE CC**: รับได้ตลอด ไม่ถูก rate limit

## การส่ง Request

```json
// Upload (default)
{ "file_path": "...", "language": "th" }

// Record
{ "file_path": "...", "language": "th", "source": "video_record" }

// FE CC
{ "file_path": "...", "language": "th", "source": "fe_cc" }
```

## Environment Variables

| ตัวแปร | ค่า | หมายเหตุ |
|--------|-----|----------|
| `MAX_CONCURRENT_REQUESTS` | 25 | Upload max |
| `MAX_CONCURRENT_RECORD_SLOTS` | 5 | Record +5 เมื่อ Upload เต็ม |
| `MAX_PREPROCESS_QUEUE_SIZE` | 25 | Preprocess queue (Upload) |
| `MAX_PREPROCESS_QUEUE_VIDEO_RECORD_SLOTS` | 5 | Preprocess queue (Record) |

FE CC ไป priority queue (หรือ preprocess_video_record เมื่อ source=fe_cc) ไม่นับ limit
