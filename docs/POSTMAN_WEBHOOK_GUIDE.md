# 🔔 คู่มือ Webhook ใน Postman

## ❓ Webhook ใช้ใน Postman ได้ไหม?

**คำตอบสั้นๆ:** Postman ไม่สามารถรับ Webhook ได้โดยตรง (เพราะ Postman เป็น client tool ไม่ใช่ server)

**แต่มีทางเลือก:**

---

## ✅ ทางเลือกที่ 1: ใช้ Check Status (แนะนำสำหรับ Postman)

### วิธีใช้

1. **Start Transcription** → เก็บ `task_id`
2. **Get Task Status** → Poll status เป็นระยะ
3. **Auto-run** → ตั้งค่าให้ run อัตโนมัติทุก 2-5 วินาที

### ตัวอย่าง Collection Runner

```
📁 Transcription Flow
  📄 1. Upload File
  📄 2. Start Transcription
  📄 3. Get Task Status (Auto-run every 2s)
```

### Test Script สำหรับ Auto-poll

**ใน Request "Get Task Status":**

```javascript
// Pre-request Script
var pollCount = parseInt(pm.environment.get("poll_count") || "0") + 1;
pm.environment.set("poll_count", pollCount.toString());

// Test Script
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

var jsonData = pm.response.json();
var status = jsonData.status;
var pollCount = parseInt(pm.environment.get("poll_count") || "0");
var maxPolls = 30; // 30 ครั้ง = 60 วินาที (ถ้า poll ทุก 2 วินาที)

if (status === "completed") {
    pm.test("✅ Task completed", function () {
        pm.expect(jsonData).to.have.property('full_text');
        console.log("Full text:", jsonData.full_text.substring(0, 100) + "...");
    });
    postman.setNextRequest(null); // Stop
} else if (status === "failed") {
    pm.test("❌ Task failed", function () {
        pm.expect(jsonData).to.have.property('error_message');
    });
    postman.setNextRequest(null); // Stop
} else if (pollCount < maxPolls) {
    // Continue polling
    console.log(`Polling... (${pollCount}/${maxPolls}) - Status: ${status}`);
    setTimeout(function() {
        postman.setNextRequest("Get Task Status");
    }, 2000); // Wait 2 seconds
} else {
    pm.test("⏱️ Timeout", function () {
        pm.expect.fail("Task did not complete within timeout");
    });
    postman.setNextRequest(null); // Stop
}
```

---

## ✅ ทางเลือกที่ 2: ใช้ Webhook.site (ง่ายที่สุด)

### วิธีใช้

1. ไปที่ https://webhook.site
2. Copy **Unique URL** ที่ได้ (เช่น: `https://webhook.site/unique-id`)
3. ใช้ URL นี้เป็น `callback_url` ใน Start Transcription request
4. Worker จะส่ง POST ไปยัง webhook.site
5. ดู webhook payload ใน webhook.site dashboard

### ตัวอย่าง Request

```json
{
  "file_path": "/workspace/transcription-service/uploads/video.mp4",
  "language": "th",
  "model_size": "base",
  "callback_url": "https://webhook.site/your-unique-id"
}
```

### ข้อดี
- ✅ ง่ายที่สุด
- ✅ ไม่ต้อง setup server
- ✅ เห็น webhook payload ทันที
- ✅ มี history ของ webhooks

---

## ✅ ทางเลือกที่ 3: ใช้ Postman Mock Server

### วิธีใช้

1. สร้าง Mock Server ใน Postman
2. ตั้งค่า endpoint: `POST /webhook`
3. ใช้ Mock Server URL เป็น `callback_url`
4. Worker จะส่ง POST ไปยัง Mock Server
5. ดู webhook payload ใน Mock Server logs

### ขั้นตอน

1. **สร้าง Mock Server:**
   - Postman → Mock Servers → Create Mock Server
   - Method: `POST`
   - Path: `/webhook`
   - Response: `200 OK`

2. **ใช้ Mock Server URL:**
   ```json
   {
     "callback_url": "https://your-mock-server-url.postman.co/webhook"
   }
   ```

3. **ดู Webhook:**
   - Postman → Mock Servers → View Requests
   - เห็น POST requests ที่ส่งมา

---

## ✅ ทางเลือกที่ 4: ใช้ ngrok (สำหรับ Local Testing)

### วิธีใช้

1. **Setup ngrok:**
   ```bash
   ngrok http 8002
   ```

2. **ได้ Public URL:**
   ```
   https://abc123.ngrok.io
   ```

3. **สร้าง Webhook Endpoint ใน Postman:**
   - ใช้ Postman's **Interceptor** หรือ **Proxy**
   - หรือสร้าง simple server รับ webhook

4. **ใช้ ngrok URL:**
   ```json
   {
     "callback_url": "https://abc123.ngrok.io/webhook"
   }
   ```

---

## 📊 เปรียบเทียบ

| วิธี | ง่าย | Real-time | เหมาะสำหรับ |
|------|------|-----------|-------------|
| **Check Status** | ⭐⭐⭐ | ⚠️ Polling | Postman Testing |
| **Webhook.site** | ⭐⭐⭐ | ✅ | Quick Testing |
| **Mock Server** | ⭐⭐ | ✅ | Postman Pro |
| **ngrok** | ⭐ | ✅ | Local Development |

---

## 💡 คำแนะนำ

### สำหรับ Postman Testing
- ✅ **ใช้ Check Status** + Auto-run (ง่ายที่สุด)
- ✅ **หรือใช้ Webhook.site** (ถ้าต้องการทดสอบ webhook จริงๆ)

### สำหรับ Production/Backend
- ✅ **ใช้ Webhook** (Backend server รับ callback)
- ✅ **หรือใช้ WebSocket** (Real-time updates)

---

## 🧪 ตัวอย่าง Workflow

### Workflow 1: Check Status (Postman)

```
1. Upload File
   ↓
2. Start Transcription (เก็บ task_id)
   ↓
3. Get Task Status (Auto-run every 2s)
   ↓
4. ดูผลลัพธ์เมื่อ status = "completed"
```

### Workflow 2: Webhook.site

```
1. เปิด webhook.site → Copy URL
   ↓
2. Upload File
   ↓
3. Start Transcription (ใช้ webhook.site URL)
   ↓
4. ดู webhook payload ใน webhook.site dashboard
```

---

## 📝 ตัวอย่าง Postman Collection

### Collection Structure

```
📁 Transcription Service
  📁 Upload
    📄 Upload File
  📁 Transcription
    📄 Start Transcription
    📄 Get Task Status (Auto-poll)
  📁 Webhook (Optional)
    📄 Webhook.site Test
    📄 Mock Server Test
```

### Environment Variables

```json
{
  "api_url": "https://n2l8ke53h14aaw-8010.proxy.runpod.net",
  "webhook_url": "https://webhook.site/your-unique-id",
  "task_id": "",
  "file_path": "",
  "poll_count": "0",
  "max_polls": "30"
}
```

