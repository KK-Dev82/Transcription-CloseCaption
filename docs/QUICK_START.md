# 🚀 Quick Start Guide

## 🌐 POD Server URLs

```
API Server:     https://n2l8ke53h14aaw-8010.proxy.runpod.net/
Webhook Server: https://n2l8ke53h14aaw-8020.proxy.runpod.net/
Monitoring:     https://n2l8ke53h14aaw-8030.proxy.runpod.net/
```

## ✅ แนะนำการใช้งาน

- **API Server (8010)**: Main API endpoints
  - `/api/upload/` - Upload files
  - `/api/transcribe/` - Start transcription
  - `/api/caption/` - Start close caption
  - `/api/tasks/{task_id}` - Get task status

- **Webhook Server (8020)**: รับ webhook callbacks
  - `/webhook` - Worker จะส่ง POST มาที่นี่เมื่อ transcription เสร็จ

- **Monitoring (8030)**: Optional - dashboard/monitoring

## 🚀 Start Services

```bash
# Start all services with nohup
bash scripts/start-all-nohup.sh

# Check logs
tail -f logs/api.log
tail -f logs/worker.log

# Stop all services
bash scripts/stop-all.sh
```

## 📮 Postman Testing

ดูคู่มือ: [POSTMAN_GUIDE.md](./POSTMAN_GUIDE.md)

### Quick Test

1. **Upload File**
   - Method: `POST`
   - URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/upload/`
   - Body: form-data → `file` (เลือกไฟล์)

2. **Start Transcription**
   - Method: `POST`
   - URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/transcribe/`
   - Body: JSON
   ```json
   {
     "file_path": "/path/to/file",
     "language": "th",
     "model_size": "base",
     "callback_url": "https://n2l8ke53h14aaw-8020.proxy.runpod.net/webhook"
   }
   ```

3. **Check Status**
   - Method: `GET`
   - URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/tasks/{task_id}`

## ⚛️ React Integration

ดูคู่มือ: [REACT_GUIDE.md](./REACT_GUIDE.md)

### Quick Setup

```javascript
const API_BASE_URL = 'https://n2l8ke53h14aaw-8010.proxy.runpod.net';
const WEBHOOK_BASE_URL = 'https://n2l8ke53h14aaw-8020.proxy.runpod.net';

// Upload file
const formData = new FormData();
formData.append('file', file);
const uploadResponse = await axios.post(`${API_BASE_URL}/api/upload/`, formData);

// Start transcription
const transcribeResponse = await axios.post(`${API_BASE_URL}/api/transcribe/`, {
  file_path: uploadResponse.data.file_path,
  language: 'th',
  model_size: 'base',
  callback_url: `${WEBHOOK_BASE_URL}/webhook`
});
```

## 🔔 Webhook Handler

Worker จะส่ง POST ไปยัง `callback_url` เมื่อเสร็จ:

```json
{
  "task_id": "uuid",
  "status": "completed",
  "full_text": "ข้อความที่แปลงแล้ว...",
  "segments": [...],
  "processing_time": 150.5
}
```

## 📚 Documentation

- [Postman Guide](./POSTMAN_GUIDE.md) - คู่มือการทดสอบด้วย Postman
- [React Guide](./REACT_GUIDE.md) - คู่มือการใช้งานกับ React
- [Testing Guide](./TESTING_GUIDE.md) - คู่มือการทดสอบทั่วไป
- [Answers](./ANSWERS.md) - คำตอบคำถามทั้งหมด

