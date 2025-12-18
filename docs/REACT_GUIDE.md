# ⚛️ คู่มือการใช้งานกับ React

## 🌐 POD Server URLs

```javascript
const API_BASE_URL = 'https://n2l8ke53h14aaw-8010.proxy.runpod.net';
const WEBHOOK_BASE_URL = 'https://n2l8ke53h14aaw-8020.proxy.runpod.net';
```

## 📦 Installation

```bash
npm install axios
# หรือ
yarn add axios
```

## 🔧 API Service

### `src/services/transcriptionService.js`

```javascript
import axios from 'axios';

const API_BASE_URL = 'https://n2l8ke53h14aaw-8010.proxy.runpod.net';
const WEBHOOK_BASE_URL = 'https://n2l8ke53h14aaw-8020.proxy.runpod.net';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const transcriptionService = {
  // Upload file
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await axios.post(
      `${API_BASE_URL}/api/upload/`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    
    return response.data;
  },

  // Start transcription
  async startTranscription(filePath, options = {}) {
    const {
      language = 'th',
      modelSize = 'base',
      callbackUrl = `${WEBHOOK_BASE_URL}/webhook`,
    } = options;

    const response = await api.post('/api/transcribe/', {
      file_path: filePath,
      language,
      model_size: modelSize,
      callback_url: callbackUrl,
    });

    return response.data;
  },

  // Start close caption
  async startCaption(filePath, options = {}) {
    const {
      language = 'th',
      modelSize = 'base',
      subtitleFormat = 'srt',
    } = options;

    const response = await api.post('/api/caption/', {
      file_path: filePath,
      language,
      model_size: modelSize,
      subtitle_format: subtitleFormat,
    });

    return response.data;
  },

  // Get task status
  async getTaskStatus(taskId) {
    const response = await api.get(`/api/tasks/${taskId}`);
    return response.data;
  },

  // List all tasks
  async listTasks(params = {}) {
    const { limit = 20, offset = 0, status } = params;
    const response = await api.get('/api/tasks/', {
      params: { limit, offset, status },
    });
    return response.data;
  },
};
```

## 🎣 React Hook

### `src/hooks/useTranscription.js`

```javascript
import { useState, useEffect, useCallback } from 'react';
import { transcriptionService } from '../services/transcriptionService';

export const useTranscription = () => {
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [fullText, setFullText] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Upload file
  const uploadFile = useCallback(async (file) => {
    try {
      setLoading(true);
      setError(null);
      const result = await transcriptionService.uploadFile(file);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Start transcription
  const startTranscription = useCallback(async (filePath, options) => {
    try {
      setLoading(true);
      setError(null);
      const result = await transcriptionService.startTranscription(filePath, options);
      setTaskId(result.task_id);
      setStatus(result.status);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll task status
  const pollStatus = useCallback(async (taskId) => {
    try {
      const result = await transcriptionService.getTaskStatus(taskId);
      setStatus(result.status);
      setProgress(result.progress || 0);
      
      if (result.status === 'completed') {
        setFullText(result.full_text || '');
      } else if (result.status === 'failed') {
        setError(result.error_message || 'Transcription failed');
      }
      
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }, []);

  // Auto-poll when taskId changes
  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      const result = await pollStatus(taskId);
      
      // Stop polling if completed or failed
      if (result.status === 'completed' || result.status === 'failed') {
        clearInterval(interval);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [taskId, pollStatus]);

  return {
    taskId,
    status,
    progress,
    fullText,
    error,
    loading,
    uploadFile,
    startTranscription,
    pollStatus,
  };
};
```

## 🎨 React Component

### `src/components/TranscriptionUploader.jsx`

```javascript
import React, { useState } from 'react';
import { useTranscription } from '../hooks/useTranscription';

const TranscriptionUploader = () => {
  const [file, setFile] = useState(null);
  const [filePath, setFilePath] = useState(null);
  const {
    taskId,
    status,
    progress,
    fullText,
    error,
    loading,
    uploadFile,
    startTranscription,
  } = useTranscription();

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;

    try {
      const result = await uploadFile(file);
      setFilePath(result.file_path);
      alert('Upload successful!');
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
  };

  const handleStartTranscription = async () => {
    if (!filePath) return;

    try {
      await startTranscription(filePath, {
        language: 'th',
        modelSize: 'base',
      });
      alert('Transcription started!');
    } catch (err) {
      alert(`Transcription failed: ${err.message}`);
    }
  };

  return (
    <div className="transcription-uploader">
      <h2>Transcription Service</h2>

      {/* File Upload */}
      <div className="upload-section">
        <input
          type="file"
          accept="video/*,audio/*"
          onChange={handleFileChange}
          disabled={loading}
        />
        <button onClick={handleUpload} disabled={loading || !file}>
          Upload File
        </button>
      </div>

      {/* Start Transcription */}
      {filePath && (
        <div className="transcription-section">
          <button
            onClick={handleStartTranscription}
            disabled={loading || !!taskId}
          >
            Start Transcription
          </button>
        </div>
      )}

      {/* Status */}
      {taskId && (
        <div className="status-section">
          <p>Task ID: {taskId}</p>
          <p>Status: {status}</p>
          {progress > 0 && <p>Progress: {progress}%</p>}
          {status === 'completed' && (
            <div className="result">
              <h3>Transcription Result:</h3>
              <p>{fullText}</p>
            </div>
          )}
          {error && <p className="error">Error: {error}</p>}
        </div>
      )}

      {loading && <p>Loading...</p>}
    </div>
  );
};

export default TranscriptionUploader;
```

## 🔔 Webhook Handler (Backend)

### สำหรับรับ Webhook จาก Transcription Service

```javascript
// backend/routes/webhook.js
const express = require('express');
const router = express.Router();

router.post('/webhook', async (req, res) => {
  const { task_id, status, full_text, segments } = req.body;

  if (status === 'completed') {
    console.log(`✅ Transcription completed: ${task_id}`);
    console.log(`Full text: ${full_text.substring(0, 100)}...`);
    
    // Save to database
    // await saveTranscription(task_id, full_text, segments);
    
    // Notify frontend (WebSocket, SSE, etc.)
    // io.emit('transcription_completed', { task_id, full_text });
  } else if (status === 'failed') {
    console.log(`❌ Transcription failed: ${task_id}`);
  }

  res.json({ status: 'received' });
});

module.exports = router;
```

## 🎯 Complete Example

### `src/App.js`

```javascript
import React from 'react';
import TranscriptionUploader from './components/TranscriptionUploader';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Transcription Service</h1>
      </header>
      <main>
        <TranscriptionUploader />
      </main>
    </div>
  );
}

export default App;
```

## 🎨 CSS Example

### `src/App.css`

```css
.transcription-uploader {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.upload-section,
.transcription-section {
  margin: 20px 0;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.status-section {
  margin: 20px 0;
  padding: 20px;
  background-color: #f5f5f5;
  border-radius: 8px;
}

.result {
  margin-top: 20px;
  padding: 15px;
  background-color: #e8f5e9;
  border-radius: 4px;
}

.error {
  color: #d32f2f;
  font-weight: bold;
}

button {
  padding: 10px 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin: 5px;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background-color: #1565c0;
}
```

## 📝 Environment Variables

### `.env`

```env
REACT_APP_API_BASE_URL=https://n2l8ke53h14aaw-8010.proxy.runpod.net
REACT_APP_WEBHOOK_BASE_URL=https://n2l8ke53h14aaw-8020.proxy.runpod.net
```

### Usage

```javascript
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;
const WEBHOOK_BASE_URL = process.env.REACT_APP_WEBHOOK_BASE_URL;
```

## ⚠️ หมายเหตุ

1. **CORS**: ต้องตั้ง CORS headers ใน API server
2. **Webhook**: ต้องมี public URL สำหรับ callback
3. **Polling**: ใช้ polling สำหรับ real-time updates (หรือใช้ WebSocket)
4. **Error Handling**: จัดการ errors ให้ดี

