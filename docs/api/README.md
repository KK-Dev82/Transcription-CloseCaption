# 📚 API Reference Documentation

## 🎯 Overview

Transcription & Close Caption Service API v1.2.0 - ระบบแปลงเสียงเป็นข้อความและสร้าง close caption แบบ real-time

**Base URL:** `http://localhost:8001`

**Swagger UI:** `http://localhost:8001/docs`

**ReDoc:** `http://localhost:8001/redoc`

## 🚀 Quick Start

### 1. Upload File
```bash
curl -X POST -F "file=@video.mp4" \
  http://localhost:8001/upload/
```

### 2. Start Enhanced Transcription
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"file_path":"uploads/uuid_video.mp4", "language":"th"}' \
  http://localhost:8001/transcribe-enhanced/start
```

### 3. Track Progress
```bash
curl http://localhost:8001/progress/transcription/{task_id}
```

## 📋 API Endpoints

### 🔼 File Upload
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload/` | POST | อัปโหลดไฟล์วิดีโอ/เสียง |
| `/upload/{file_id}/info` | GET | ดูข้อมูลไฟล์ |

**Supported Formats:**
- **Video:** `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`
- **Audio:** `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.m4a`
- **Max Size:** 2GB

### ⚡ Enhanced Transcription (Recommended)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcribe-enhanced/start` | POST | เริ่ม transcription แบบเร็ว + แม่นยำ |
| `/transcribe-enhanced/status/{task_id}` | GET | ดูสถานะ + Thai processing |
| `/transcribe-enhanced/apply-thai-processing/{task_id}` | POST | ใช้ Thai processing manual |
| `/transcribe-enhanced/compare/{task_id}` | GET | เปรียบเทียบก่อน/หลังแก้ไข |

### 📊 Progress Tracking
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/progress/transcription/{task_id}` | GET | ดู progress แบบ real-time |
| `/progress/all-active` | GET | ดู active tasks ทั้งหมด |
| `/progress/stats` | GET | สถิติการประมวลผล |

### 🎬 Video Processing
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/video/upload` | POST | อัปโหลดวิดีโอ |
| `/video/segment` | POST | แบ่งวิดีโอ + transcription |
| `/video/trim` | POST | ตัดวิดีโอ |
| `/video/merge` | POST | รวมวิดีโอ |
| `/video/convert` | POST | แปลงรูปแบบ |
| `/video/resize` | POST | เปลี่ยนขนาด |

### 📝 Regular Transcription
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcribe/start` | POST | เริ่ม transcription ปกติ |
| `/transcribe/status/{task_id}` | GET | ดูสถานะ |
| `/transcribe/text/{task_id}` | GET | ดึงข้อความ |
| `/transcribe/chunks/{task_id}` | GET | ดึง chunks พร้อม timestamps |
| `/transcribe/search/{task_id}` | POST | ค้นหาคำ |

### 📺 Caption Generation
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/caption/generate` | POST | สร้าง captions/subtitles |
| `/caption/status/{task_id}` | GET | ดูสถานะ |
| `/caption/subtitle/{task_id}` | GET | ดาวน์โหลด SRT |

### 🇹🇭 Thai Text Processing
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/thai/correct-text` | POST | แก้ไขข้อความภาษาไทย |
| `/thai/process-chunks` | POST | ประมวลผล chunks |
| `/thai/test-corrections` | GET | ทดสอบการแก้ไข |
| `/thai/dictionary-stats` | GET | สถิติพจนานุกรม |
| `/thai/add-corrections` | POST | เพิ่มการแก้ไขแบบกำหนดเอง |

### 🔴 Live Streaming
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/live/start` | POST | เริ่ม live streaming session |
| `/live/stop/{stream_id}` | POST | หยุด live streaming |
| `/live/status/{stream_id}` | GET | ดูสถานะ live stream |
| `/live/active` | GET | ดู active streams |
| `/live/ws/{stream_id}` | WebSocket | Real-time updates |

### 🔧 System
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | ข้อมูลระบบและ endpoints |
| `/health` | GET | ตรวจสอบสถานะระบบ |
| `/stats` | GET | สถิติการใช้งาน |

## 🔄 Workflow Examples

### Basic Transcription Flow
1. **Upload** → `/upload/` → Get `file_path`
2. **Start** → `/transcribe-enhanced/start` → Get `task_id`
3. **Monitor** → `/progress/transcription/{task_id}` → Check progress
4. **Results** → `/transcribe-enhanced/status/{task_id}` → Get transcription

### Video Segmentation Flow
1. **Upload** → `/upload/` → Get `file_path`
2. **Segment** → `/video/segment` → Get `task_id`
3. **Monitor** → `/video/segment/{task_id}` → Check progress
4. **Search** → `/transcribe/search/{task_id}` → Find keywords

### Caption Generation Flow
1. **Complete Transcription** → Get `transcription_task_id`
2. **Generate** → `/caption/generate` → Get `caption_task_id`
3. **Download** → `/caption/subtitle/{caption_task_id}` → Get SRT file

## 📄 Response Formats

### Success Response
```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "progress": 100,
  "data": { ... }
}
```

### Error Response
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Progress Response
```json
{
  "task_id": "uuid",
  "status": "processing_chunk_3_of_10",
  "progress": 35,
  "stage": "กำลังประมวลผล chunk 3/10",
  "elapsed_formatted": "2:45",
  "estimated_remaining_formatted": "5:20"
}
```

## 🚨 Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - ข้อมูลไม่ถูกต้อง |
| 404 | Not Found - ไม่พบ task/file |
| 413 | Payload Too Large - ไฟล์ใหญ่เกิน 2GB |
| 422 | Unprocessable Entity - รูปแบบไฟล์ไม่รองรับ |
| 500 | Internal Server Error - ข้อผิดพลาดระบบ |

## 🔧 Rate Limiting

- **Upload:** 10 files/minute
- **Transcription:** 5 concurrent tasks
- **Progress API:** 60 requests/minute
- **Search:** 100 requests/minute

## 📝 Notes for Frontend

1. **File Upload:** ใช้ FormData สำหรับ multipart/form-data
2. **Progress:** ใช้ polling ทุก 2-3 วินาที
3. **Error Handling:** ตรวจสอบ status_code และ detail
4. **Timeouts:** ตั้ง timeout สำหรับ long-running tasks
5. **WebSocket:** ใช้สำหรับ real-time updates

## 🔗 Related Documentation

- [Frontend Integration Guide](../frontend/integration.md)
- [Deployment Guide](../deployment/README.md)
- [Examples](../examples/README.md)
