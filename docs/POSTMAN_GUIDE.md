# 📮 คู่มือการทดสอบด้วย Postman

## 🌐 POD Server URLs

```
API Server:     https://n2l8ke53h14aaw-8010.proxy.runpod.net/
Webhook Server: https://n2l8ke53h14aaw-8020.proxy.runpod.net/
Monitoring:     https://n2l8ke53h14aaw-8030.proxy.runpod.net/
```

**⚠️ หมายเหตุ:**
- Port 8001 ถูกใช้โดย RunPod Nginx/Proxy (ห้ามใช้)
- Port 8888 ถูกใช้โดย Jupyter Lab (ห้ามใช้)
- API Server รันที่ port 8010 (internal)
- RunPod HTTP Expose จะ auto-map port เดียวกัน (8010 → 8010)
- **ไม่ต้องตั้งค่า port mapping เพิ่มเติม**

## 📋 API Endpoints

### 1. Upload File

**Method:** `POST`  
**URL:** `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/upload/`

**Headers:**
```
Content-Type: multipart/form-data
```

**Body (form-data):**
```
⚠️  สำคัญ: ต้องตั้งค่า Key เป็น "file" (ไม่ใช่ "Key" หรือ "Value")

1. คลิก "Body" tab
2. เลือก "form-data"
3. เพิ่ม key-value pair:
   - Key: file (พิมพ์ "file" ลงในช่อง Key)
   - Type: File (คลิก dropdown ทางขวาของ Key แล้วเลือก "File")
   - Value: [คลิก "Select Files" แล้วเลือกไฟล์ video.mp4 หรือ audio.wav]

ตัวอย่าง:
┌─────────┬──────────┬─────────────────────┐
│ Key     │ Type     │ Value               │
├─────────┼──────────┼─────────────────────┤
│ file    │ File     │ trimmed_short.mp4   │
└─────────┴──────────┴─────────────────────┘

❌ ผิด:
   Key: "Key" หรือ "Value"
   Type: Text

✅ ถูก:
   Key: "file"
   Type: File
```

**Response:**
```json
{
  "file_id": "uuid",
  "filename": "video.mp4",
  "file_path": "/workspace/transcription-service/uploads/video.mp4",
  "file_size": 12345678,
  "file_type": "video",
  "duration": 600.0,
  "uploaded_at": "2025-01-15T10:30:00Z",
  "status": "uploaded"
}
```

---

### 2. Start Transcription

**Method:** `POST`  
**URL:** `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/transcribe/`

**Headers:**
```
⚠️  สำคัญ: ต้องเพิ่ม Content-Type header!

1. ไปที่ "Headers" tab
2. เพิ่ม header:
   Key: Content-Type
   Value: application/json
```

**Body (raw JSON):**
```
⚠️  สำคัญ: ต้องเลือก "raw" และ "JSON"!

1. ไปที่ "Body" tab
2. เลือก "raw" (ไม่ใช่ form-data)
3. เลือก "JSON" จาก dropdown (ไม่ใช่ Text หรือ JavaScript)
4. วาง JSON ด้านล่าง:
```

```json
{
  "file_path": "uploads/e0c676d0-5d12-4fea-b2e1-fcc33921957e_trimmed_short.mp4",
  "language": "th",
  "model_size": "base",
  "callback_url": "https://n2l8ke53h14aaw-8020.proxy.runpod.net/webhook"
}
```

**⚠️ หมายเหตุ:**
- `file_path` ต้องเป็น relative path จาก project root (เช่น `uploads/...`)
- ไม่ต้องใส่ `/workspace/transcription-service/` นำหน้า

**Response:**
```json
{
  "task_id": "uuid",
  "status": "queued",
  "message": "Transcription started"
}
```

---

### 3. Start Close Caption

**Method:** `POST`  
**URL:** `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/caption/`

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "file_path": "/workspace/transcription-service/uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "subtitle_format": "srt"
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "status": "queued",
  "message": "Caption generation started"
}
```

---

### 4. Get Task Status

**Method:** `GET`  
**URL:** `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/tasks/{task_id}`

**Response:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "full_text": "ข้อความที่แปลงแล้ว...",
  "segments": [
    {
      "start": 0.0,
      "end": 5.0,
      "text": "ข้อความส่วนแรก"
    }
  ],
  "processing_time": 150.5
}
```

---

### 5. List All Tasks

**Method:** `GET`  
**URL:** `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/tasks/`

**Query Parameters:**
```
?limit=20&offset=0&status=completed
```

---

## 🔄 Workflow ใน Postman

### Step 1: Upload File
1. สร้าง Request ใหม่: `Upload File`
2. Method: `POST`
3. URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/upload/`
4. Body → form-data
5. Key: `file` (Type: File) → เลือกไฟล์
6. Send → เก็บ `file_path` จาก response

### Step 2: Start Transcription
1. สร้าง Request ใหม่: `Start Transcription`
2. Method: `POST`
3. URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/transcribe/`
4. Body → raw → JSON
5. ใส่ `file_path` จาก Step 1
6. ใส่ `callback_url`: `https://n2l8ke53h14aaw-8020.proxy.runpod.net/webhook`
7. Send → เก็บ `task_id` จาก response

### Step 3: Check Status (Optional)
1. สร้าง Request ใหม่: `Get Task Status`
2. Method: `GET`
3. URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/tasks/{task_id}`
4. Replace `{task_id}` ด้วย task_id จาก Step 2
5. Send → ดู status และ progress

### Step 4: Receive Webhook (หรือใช้ Check Status)

**⚠️ หมายเหตุ:** Postman ไม่สามารถรับ Webhook ได้โดยตรง (เพราะ Postman เป็น client tool ไม่ใช่ server)

**ทางเลือก:**

#### Option A: ใช้ Check Status (แนะนำสำหรับ Postman)
1. สร้าง Request ใหม่: `Get Task Status`
2. Method: `GET`
3. URL: `https://n2l8ke53h14aaw-8010.proxy.runpod.net/api/tasks/{task_id}`
4. ใช้ **Auto-run** หรือ **Collection Runner** เพื่อ poll status อัตโนมัติ
5. หรือใช้ **Postman Monitor** เพื่อ check status เป็นระยะ

#### Option B: ใช้ Postman Mock Server (สำหรับทดสอบ Webhook)
1. สร้าง Mock Server ใน Postman
2. ตั้งค่า endpoint: `POST /webhook`
3. ใช้ Mock Server URL เป็น `callback_url`
4. Worker จะส่ง POST ไปยัง Mock Server
5. ดู webhook payload ใน Mock Server logs

#### Option C: ใช้ Webhook Testing Tools
- **Webhook.site**: https://webhook.site (ได้ unique URL สำหรับรับ webhook)
- **RequestBin**: https://requestbin.com (คล้าย webhook.site)
- ใช้ URL จาก tools เหล่านี้เป็น `callback_url`

---

## 📝 Postman Collection

### Environment Variables

สร้าง Environment ชื่อ `POD Server`:

```json
{
  "api_url": "https://n2l8ke53h14aaw-8010.proxy.runpod.net",
  "webhook_url": "https://n2l8ke53h14aaw-8020.proxy.runpod.net",
  "monitoring_url": "https://n2l8ke53h14aaw-8030.proxy.runpod.net"
}
```

### Collection Structure

```
📁 Transcription Service
  📁 Upload
    📄 Upload File
  📁 Transcription
    📄 Start Transcription
    📄 Get Task Status
    📄 List Tasks
  📁 Caption
    📄 Start Caption
    📄 Get Caption Status
  📁 Webhook
    📄 Webhook Receiver (Test)
```

---

## 🧪 Test Scripts (Postman)

### Pre-request Script (Start Transcription)

```javascript
// ใช้ file_path จาก environment variable
pm.environment.set("file_path", pm.response.json().file_path);
```

### Test Script (Start Transcription)

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has task_id", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('task_id');
    pm.environment.set("task_id", jsonData.task_id);
});
```

### Test Script (Get Task Status)

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Task is completed", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.equal("completed");
    pm.expect(jsonData).to.have.property('full_text');
});
```

---

## 🔔 Webhook vs Check Status

### Webhook (สำหรับ Production/Backend)
- ✅ **เหมาะสำหรับ**: Backend server, Production
- ✅ **ข้อดี**: Real-time, ไม่ต้อง poll
- ❌ **ข้อเสีย**: Postman ไม่สามารถรับได้โดยตรง
- 💡 **วิธีใช้ใน Postman**: ใช้ Mock Server หรือ Webhook.site

### Check Status (สำหรับ Postman Testing)
- ✅ **เหมาะสำหรับ**: Testing, Development, Postman
- ✅ **ข้อดี**: ใช้ได้ทันทีใน Postman
- ⚠️ **ข้อเสีย**: ต้อง poll (check status เป็นระยะ)
- 💡 **วิธีใช้**: Auto-run หรือ Collection Runner

### ตัวอย่าง: Auto-poll Status ใน Postman

**Test Script (Start Transcription):**
```javascript
// เก็บ task_id
var jsonData = pm.response.json();
pm.environment.set("task_id", jsonData.task_id);

// ตั้งค่า polling
pm.environment.set("poll_count", 0);
pm.environment.set("max_polls", 30); // 30 ครั้ง (60 วินาที ถ้า poll ทุก 2 วินาที)
```

**Pre-request Script (Get Task Status):**
```javascript
// เพิ่ม poll count
var pollCount = parseInt(pm.environment.get("poll_count") || "0") + 1;
pm.environment.set("poll_count", pollCount.toString());
```

**Test Script (Get Task Status):**
```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

var jsonData = pm.response.json();
var status = jsonData.status;
var pollCount = parseInt(pm.environment.get("poll_count") || "0");
var maxPolls = parseInt(pm.environment.get("max_polls") || "30");

if (status === "completed") {
    pm.test("Task completed", function () {
        pm.expect(jsonData).to.have.property('full_text');
    });
    // Stop polling
    postman.setNextRequest(null);
} else if (status === "failed") {
    pm.test("Task failed", function () {
        pm.expect(jsonData).to.have.property('error_message');
    });
    postman.setNextRequest(null);
} else if (pollCount < maxPolls) {
    // Continue polling (auto-run again in 2 seconds)
    setTimeout(function() {
        postman.setNextRequest("Get Task Status");
    }, 2000);
} else {
    pm.test("Timeout - Max polls reached", function () {
        pm.expect.fail("Task did not complete within timeout");
    });
    postman.setNextRequest(null);
}
```

---

## ⚠️ หมายเหตุ

1. **File Path**: ใช้ path ที่ return จาก upload endpoint
2. **Webhook URL**: ต้องเป็น public URL (ใช้ ngrok สำหรับ local testing)
3. **Timeout**: Transcription อาจใช้เวลานาน (10 นาที = ~150 วินาที)
4. **CORS**: ถ้าเรียกจาก browser อาจต้องตั้ง CORS headers
5. **Webhook in Postman**: ใช้ Mock Server หรือ Webhook.site แทน
6. **Check Status**: ใช้ Auto-run หรือ Collection Runner สำหรับ polling

---

## ❌ Troubleshooting: 502 Bad Gateway

### สาเหตุที่เป็นไปได้

1. **API Server ไม่ได้รัน**
   ```bash
   # ตรวจสอบ
   ps aux | grep uvicorn
   
   # Start API
   bash scripts/start-all-nohup.sh
   ```

2. **Proxy Configuration**
   - ตรวจสอบว่า RunPod proxy ชี้ไปยัง port 8001
   - ตรวจสอบว่า API server รันอยู่

3. **Import Errors**
   - ตรวจสอบ logs/api-error.log
   - แก้ไข import errors

### วิธีแก้ไข

1. **Restart API Server**
   ```bash
   bash scripts/stop-all.sh
   bash scripts/start-all-nohup.sh
   ```

2. **ทดสอบ Localhost**
   ```bash
   curl http://127.0.0.1:8001/health
   curl http://127.0.0.1:8001/api/upload/list
   ```

3. **ตรวจสอบ Logs**
   ```bash
   tail -f logs/api.log
   tail -f logs/api-error.log
   ```

4. **ทดสอบ Upload (Localhost)**
   ```bash
   curl -X POST http://127.0.0.1:8001/api/upload/ \
     -F 'file=@test.mp4'
   ```

ดูคู่มือเพิ่มเติม: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

