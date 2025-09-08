# 🔔 Webhook Documentation

## 🎯 Overview

Webhook system ช่วยให้ Frontend ไม่ต้อง polling เพื่อเช็ค progress แต่จะได้รับ notification แบบ real-time เมื่อมี event เกิดขึ้น

## 🚀 Quick Start

### 1. สมัครรับ Webhook

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhook",
    "events": ["transcription.completed", "transcription.failed"],
    "secret": "your-secret-key"
  }' \
  http://localhost:8001/webhook/subscribe
```

**Response:**
```json
{
  "subscription_id": "uuid-here",
  "status": "active",
  "events": ["transcription.completed", "transcription.failed"],
  "message": "Webhook subscription created successfully"
}
```

### 2. รับ Webhook Notifications

เมื่อ transcription เสร็จ จะได้รับ HTTP POST ไปที่ URL ที่กำหนด:

```json
{
  "event": "transcription.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "task_id": "task-uuid",
  "data": {
    "task_id": "task-uuid",
    "status": "completed",
    "text_length": 1500,
    "chunks_count": 50,
    "processing_stats": {
      "total_chunks": 50,
      "corrected_chunks": 15,
      "correction_rate": 0.3
    }
  }
}
```

## 📋 Supported Events

| Event | Description | When Triggered |
|-------|-------------|----------------|
| `transcription.started` | เริ่ม transcription | เมื่อเริ่มประมวลผลไฟล์ |
| `transcription.progress` | Progress update | ทุก 10% หรือเปลี่ยน stage |
| `transcription.completed` | Transcription เสร็จ | เมื่อประมวลผลเสร็จสมบูรณ์ |
| `transcription.failed` | Transcription ล้มเหลว | เมื่อเกิดข้อผิดพลาด |
| `file.uploaded` | ไฟล์ถูกอัปโหลด | เมื่อมีไฟล์ใหม่ |
| `*` | ทุก events | Wildcard สำหรับรับทุก events |

## 🔐 Security

### Signature Verification

เมื่อระบุ `secret` จะมี `X-Webhook-Signature` header:

```
X-Webhook-Signature: sha256=<hmac_hex>
```

### ตรวจสอบ Signature (Node.js)

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload, 'utf8')
    .digest('hex');
  
  const expected = `sha256=${expectedSignature}`;
  
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}

// Express.js middleware
app.use('/webhook', express.raw({ type: 'application/json' }));

app.post('/webhook', (req, res) => {
  const signature = req.headers['x-webhook-signature'];
  const payload = req.body.toString();
  
  if (!verifyWebhookSignature(payload, signature, 'your-secret')) {
    return res.status(401).send('Invalid signature');
  }
  
  const data = JSON.parse(payload);
  console.log('Webhook received:', data.event);
  
  res.status(200).send('OK');
});
```

### ตรวจสอบ Signature (Python)

```python
import hmac
import hashlib

def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    expected = f"sha256={expected_signature}"
    
    return hmac.compare_digest(expected, signature)

# Flask example
from flask import Flask, request

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data(as_text=True)
    
    if not verify_webhook_signature(payload, signature, 'your-secret'):
        return 'Invalid signature', 401
    
    data = request.get_json()
    print(f"Webhook received: {data['event']}")
    
    return 'OK', 200
```

## 📊 API Endpoints

### Subscribe to Webhook

```http
POST /webhook/subscribe
Content-Type: application/json

{
  "url": "https://your-app.com/webhook",
  "events": ["transcription.completed"],
  "secret": "optional-secret-key",
  "headers": {
    "Authorization": "Bearer token",
    "Custom-Header": "value"
  }
}
```

### List Subscriptions

```http
GET /webhook/subscriptions
```

### Get Subscription Details

```http
GET /webhook/subscribe/{subscription_id}
```

### Delete Subscription

```http
DELETE /webhook/subscribe/{subscription_id}
```

### Test Webhook

```http
POST /webhook/test
Content-Type: application/json

{
  "subscription_id": "uuid",
  "event_type": "test",
  "test_data": {
    "message": "Test webhook"
  }
}
```

### Webhook Statistics

```http
GET /webhook/stats
```

### Supported Events List

```http
GET /webhook/events
```

## 🔄 Frontend Integration Examples

### React Hook for Webhooks

```typescript
import { useEffect, useState } from 'react';

interface WebhookSubscription {
  subscriptionId: string;
  url: string;
  events: string[];
}

export function useWebhookSubscription(
  webhookUrl: string,
  events: string[],
  secret?: string
) {
  const [subscription, setSubscription] = useState<WebhookSubscription | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const subscribe = async () => {
      try {
        const response = await fetch('/api/webhook/subscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            url: webhookUrl,
            events,
            secret,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to subscribe to webhook');
        }

        const data = await response.json();
        setSubscription({
          subscriptionId: data.subscription_id,
          url: webhookUrl,
          events,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    };

    if (webhookUrl && events.length > 0) {
      subscribe();
    }

    // Cleanup on unmount
    return () => {
      if (subscription) {
        fetch(`/api/webhook/subscribe/${subscription.subscriptionId}`, {
          method: 'DELETE',
        }).catch(console.error);
      }
    };
  }, [webhookUrl, events, secret]);

  return { subscription, error };
}
```

### Webhook Handler Service

```typescript
class WebhookHandler {
  private subscriptions = new Map<string, Function>();

  async subscribe(url: string, events: string[], secret?: string) {
    const response = await fetch('/api/webhook/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url, events, secret }),
    });

    return response.json();
  }

  async unsubscribe(subscriptionId: string) {
    const response = await fetch(`/api/webhook/subscribe/${subscriptionId}`, {
      method: 'DELETE',
    });

    return response.json();
  }

  // For development/testing - simulate receiving webhooks
  simulateWebhook(event: string, data: any) {
    const handlers = this.subscriptions.get(event) || [];
    handlers.forEach((handler: Function) => handler(data));
  }

  onWebhook(event: string, handler: Function) {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, []);
    }
    this.subscriptions.get(event)!.push(handler);
  }
}

// Usage
const webhookHandler = new WebhookHandler();

// Subscribe to events
webhookHandler.onWebhook('transcription.completed', (data) => {
  console.log('Transcription completed!', data);
  // Update UI, show notification, etc.
});

webhookHandler.onWebhook('transcription.progress', (data) => {
  console.log(`Progress: ${data.progress}%`);
  // Update progress bar
});
```

## 🌐 Complete Integration Example

### Backend Webhook Receiver (Express.js)

```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();

// Middleware to capture raw body for signature verification
app.use('/api/webhook', express.raw({ type: 'application/json' }));

// Webhook verification middleware
function verifyWebhook(secret) {
  return (req, res, next) => {
    const signature = req.headers['x-webhook-signature'];
    
    if (!signature) {
      return res.status(401).json({ error: 'Missing signature' });
    }

    const payload = req.body.toString();
    const expectedSignature = crypto
      .createHmac('sha256', secret)
      .update(payload, 'utf8')
      .digest('hex');
    
    const expected = `sha256=${expectedSignature}`;
    
    if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    req.webhookData = JSON.parse(payload);
    next();
  };
}

// Webhook endpoint
app.post('/api/webhook', verifyWebhook('your-secret-key'), (req, res) => {
  const { event, data, task_id } = req.webhookData;

  console.log(`Received webhook: ${event}`, data);

  switch (event) {
    case 'transcription.started':
      // Handle transcription started
      console.log(`Transcription started for task: ${task_id}`);
      break;

    case 'transcription.progress':
      // Handle progress update
      console.log(`Progress: ${data.progress}% - ${data.stage}`);
      // Emit to WebSocket clients
      io.emit('transcription:progress', { task_id, progress: data.progress });
      break;

    case 'transcription.completed':
      // Handle completion
      console.log(`Transcription completed: ${data.text_length} characters`);
      // Emit to WebSocket clients
      io.emit('transcription:completed', { task_id, data });
      break;

    case 'transcription.failed':
      // Handle failure
      console.error(`Transcription failed: ${data.error}`);
      // Emit error to WebSocket clients
      io.emit('transcription:failed', { task_id, error: data.error });
      break;

    case 'file.uploaded':
      // Handle file upload
      console.log(`File uploaded: ${data.filename}`);
      break;

    default:
      console.log(`Unknown event: ${event}`);
  }

  res.status(200).json({ received: true });
});

app.listen(3000, () => {
  console.log('Webhook receiver running on port 3000');
});
```

### Frontend Integration (React)

```tsx
import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';

const TranscriptionApp: React.FC = () => {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle');
  const [results, setResults] = useState<any>(null);

  useEffect(() => {
    // Connect to WebSocket for real-time updates
    const socket = io('http://localhost:3000');

    socket.on('transcription:progress', ({ task_id, progress }) => {
      if (task_id === taskId) {
        setProgress(progress);
        setStatus('processing');
      }
    });

    socket.on('transcription:completed', ({ task_id, data }) => {
      if (task_id === taskId) {
        setProgress(100);
        setStatus('completed');
        setResults(data);
      }
    });

    socket.on('transcription:failed', ({ task_id, error }) => {
      if (task_id === taskId) {
        setStatus('failed');
        console.error('Transcription failed:', error);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [taskId]);

  const startTranscription = async (file: File) => {
    // 1. Subscribe to webhook
    const webhookResponse = await fetch('/api/webhook/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: 'https://your-app.com/api/webhook',
        events: ['transcription.*'],
        secret: 'your-secret-key'
      })
    });

    // 2. Upload file
    const formData = new FormData();
    formData.append('file', file);
    
    const uploadResponse = await fetch('http://localhost:8001/upload/', {
      method: 'POST',
      body: formData
    });
    
    const uploadData = await uploadResponse.json();

    // 3. Start transcription
    const transcribeResponse = await fetch('http://localhost:8001/transcribe-enhanced/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_path: uploadData.file_path,
        language: 'th'
      })
    });

    const transcribeData = await transcribeResponse.json();
    setTaskId(transcribeData.task_id);
    setStatus('started');
  };

  return (
    <div>
      <h1>Transcription with Webhooks</h1>
      
      {status === 'idle' && (
        <input
          type="file"
          accept=".mp4,.mp3,.wav"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) startTranscription(file);
          }}
        />
      )}

      {status !== 'idle' && (
        <div>
          <p>Status: {status}</p>
          <p>Progress: {progress}%</p>
          
          {status === 'completed' && results && (
            <div>
              <h3>Results:</h3>
              <p>Text length: {results.text_length}</p>
              <p>Chunks: {results.chunks_count}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
```

## ⚡ Benefits of Webhooks vs Polling

| Aspect | Polling | Webhooks |
|--------|---------|----------|
| **Real-time** | ❌ Delayed (2-5s) | ✅ Instant |
| **Server Load** | ❌ High (constant requests) | ✅ Low (event-driven) |
| **Bandwidth** | ❌ High (repeated requests) | ✅ Low (only when needed) |
| **Battery Usage** | ❌ High (mobile) | ✅ Low |
| **Complexity** | ✅ Simple | ⚠️ Medium |
| **Reliability** | ✅ High | ⚠️ Needs retry logic |

## 🚨 Best Practices

1. **Always verify signatures** เพื่อความปลอดภัย
2. **Handle retries gracefully** - webhook จะ retry 3 ครั้ง
3. **Return 200 status** เพื่อหยุด retry
4. **Process asynchronously** - ไม่ให้ webhook timeout
5. **Log all webhooks** สำหรับ debugging
6. **Use HTTPS** ใน production
7. **Implement idempotency** - handle duplicate webhooks

## 🔗 Related Documentation

- [API Reference](../api/README.md)
- [Frontend Integration](../frontend/integration.md)
- [Examples](../examples/README.md)
