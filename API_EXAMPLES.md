# 💻 API Examples - ตัวอย่างการใช้งานจริง

> **ตัวอย่าง code พร้อมใช้งาน** สำหรับ API v2

---

## 📋 สารบัญ

1. [JavaScript/TypeScript Examples](#javascript)
2. [Python Examples](#python)
3. [cURL Examples](#curl)
4. [React Hooks Examples](#react)

---

## <a name="javascript"></a>🟨 JavaScript/TypeScript Examples

### 1. ดึงสถานะ Task

```typescript
// ฟังก์ชันสำหรับดึงสถานะ task
async function getTaskStatus(
  taskId: string,
  format: 'full' | 'progress' | 'minimal' = 'full'
): Promise<any> {
  const response = await fetch(
    `http://localhost:8001/api/v2/tasks/${taskId}?format=${format}`
  )
  
  if (!response.ok) {
    throw new Error(`Failed to fetch task: ${response.statusText}`)
  }
  
  return await response.json()
}

// การใช้งาน
const task = await getTaskStatus('abc-123', 'full')
console.log('Task status:', task.status)
console.log('Progress:', task.progress)
```

---

### 2. Polling Task Status

```typescript
// ฟังก์ชัน polling แบบ smart (ใช้ format=minimal)
async function pollTaskUntilComplete(
  taskId: string,
  onProgress?: (progress: number) => void
): Promise<any> {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        // ใช้ format=minimal เพื่อความเร็ว
        const response = await fetch(
          `http://localhost:8001/api/v2/tasks/${taskId}?format=minimal`
        )
        
        const task = await response.json()
        
        // Update progress callback
        if (onProgress) {
          onProgress(task.progress)
        }
        
        // ถ้าเสร็จแล้ว
        if (task.status === 'completed') {
          clearInterval(interval)
          
          // ดึงข้อมูลแบบเต็ม
          const fullResponse = await fetch(
            `http://localhost:8001/api/v2/tasks/${taskId}?format=full`
          )
          const fullTask = await fullResponse.json()
          
          resolve(fullTask)
        }
        
        // ถ้า error
        if (task.status === 'failed') {
          clearInterval(interval)
          reject(new Error(task.error || 'Task failed'))
        }
        
      } catch (error) {
        clearInterval(interval)
        reject(error)
      }
    }, 2000) // Poll ทุก 2 วินาที
  })
}

// การใช้งาน
const result = await pollTaskUntilComplete('abc-123', (progress) => {
  console.log(`Progress: ${progress}%`)
})

console.log('Task completed:', result)
```

---

### 3. ดึงรายการ Tasks พร้อม Filters

```typescript
interface TaskListOptions {
  status?: 'completed' | 'failed' | 'processing' | 'pending'
  date?: string // YYYY-MM-DD
  daysAgo?: number
  active?: boolean
  filenameContains?: string
  language?: string
  limit?: number
  offset?: number
  sort?: 'created_at' | 'updated_at' | 'filename'
  order?: 'asc' | 'desc'
}

async function getTasks(options: TaskListOptions = {}): Promise<any> {
  // Build query string
  const params = new URLSearchParams()
  
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, String(value))
    }
  })
  
  const response = await fetch(
    `http://localhost:8001/api/v2/tasks?${params.toString()}`
  )
  
  if (!response.ok) {
    throw new Error(`Failed to fetch tasks: ${response.statusText}`)
  }
  
  return await response.json()
}

// การใช้งาน - ตัวอย่างต่างๆ

// 1. ดึงทั้งหมด
const allTasks = await getTasks({ limit: 20 })

// 2. ดึง active tasks
const activeTasks = await getTasks({ active: true })

// 3. ดึง tasks ที่เสร็จแล้ว 7 วันที่ผ่านมา
const recentCompleted = await getTasks({
  status: 'completed',
  daysAgo: 7
})

// 4. ค้นหาตาม filename
const meetingTasks = await getTasks({
  filenameContains: 'meeting',
  limit: 10
})

// 5. Complex filter
const complexFilter = await getTasks({
  status: 'completed',
  language: 'th',
  daysAgo: 7,
  filenameContains: 'test',
  limit: 20,
  sort: 'updated_at',
  order: 'desc'
})
```

---

### 4. Upload ไฟล์

```typescript
// Upload ไฟล์
async function uploadFile(file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch('http://localhost:8001/api/upload/', {
    method: 'POST',
    body: formData
  })
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`)
  }
  
  return await response.json()
}

// Upload จาก URL
async function uploadFromURL(url: string): Promise<any> {
  const formData = new FormData()
  formData.append('url', url)
  
  const response = await fetch('http://localhost:8001/api/upload/', {
    method: 'POST',
    body: formData
  })
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`)
  }
  
  return await response.json()
}

// การใช้งาน
const fileInput = document.querySelector('input[type="file"]')
const file = fileInput.files[0]
const uploadResult = await uploadFile(file)

console.log('File uploaded:', uploadResult.file_path)
```

---

### 5. เริ่ม Transcription และรอผลลัพธ์

```typescript
// Workflow สมบูรณ์: Upload → Start → Poll → Get Result
async function transcribeFile(file: File): Promise<any> {
  // 1. Upload file
  console.log('Uploading file...')
  const uploadResult = await uploadFile(file)
  
  // 2. Start transcription
  console.log('Starting transcription...')
  const startResponse = await fetch('http://localhost:8001/api/transcribe/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_path: uploadResult.file_path,
      language: 'th',
      model_size: 'base'
    })
  })
  
  const { task_id } = await startResponse.json()
  
  // 3. Poll until complete
  console.log('Waiting for transcription...')
  const result = await pollTaskUntilComplete(task_id, (progress) => {
    console.log(`Progress: ${progress}%`)
  })
  
  return result
}

// การใช้งาน
const file = document.querySelector('input[type="file"]').files[0]
const result = await transcribeFile(file)

console.log('Transcription text:', result.result.text)
console.log('Segments:', result.result.segments)
```

---

## <a name="python"></a>🐍 Python Examples

### 1. ดึงสถานะ Task

```python
import requests
from typing import Optional, Literal

def get_task_status(
    task_id: str,
    format: Literal['full', 'progress', 'minimal'] = 'full'
) -> dict:
    """ดึงสถานะ task"""
    url = f'http://localhost:8001/api/v2/tasks/{task_id}'
    params = {'format': format}
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    return response.json()

# การใช้งาน
task = get_task_status('abc-123', format='full')
print(f"Status: {task['status']}")
print(f"Progress: {task['progress']}%")
```

---

### 2. Polling Task

```python
import time
from typing import Callable, Optional

def poll_task_until_complete(
    task_id: str,
    on_progress: Optional[Callable[[int], None]] = None,
    interval: int = 2
) -> dict:
    """Poll task จนกว่าจะเสร็จ"""
    while True:
        # ใช้ format=minimal เพื่อความเร็ว
        task = get_task_status(task_id, format='minimal')
        
        # Update progress
        if on_progress:
            on_progress(task['progress'])
        
        # ตรวจสอบสถานะ
        if task['status'] == 'completed':
            # ดึงข้อมูลแบบเต็ม
            return get_task_status(task_id, format='full')
        
        if task['status'] == 'failed':
            raise Exception(f"Task failed: {task.get('error', 'Unknown error')}")
        
        time.sleep(interval)

# การใช้งาน
def show_progress(progress: int):
    print(f"Progress: {progress}%")

result = poll_task_until_complete('abc-123', on_progress=show_progress)
print(f"Completed: {result['result']['text']}")
```

---

### 3. ดึงรายการ Tasks

```python
from typing import Optional

def get_tasks(
    status: Optional[str] = None,
    date: Optional[str] = None,
    days_ago: Optional[int] = None,
    active: Optional[bool] = None,
    filename_contains: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = 'updated_at',
    order: str = 'desc'
) -> dict:
    """ดึงรายการ tasks พร้อม filters"""
    url = 'http://localhost:8001/api/v2/tasks'
    
    params = {
        'limit': limit,
        'offset': offset,
        'sort': sort,
        'order': order
    }
    
    # เพิ่ม optional filters
    if status:
        params['status'] = status
    if date:
        params['date'] = date
    if days_ago:
        params['days_ago'] = days_ago
    if active is not None:
        params['active'] = active
    if filename_contains:
        params['filename_contains'] = filename_contains
    if language:
        params['language'] = language
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    return response.json()

# การใช้งาน
# 1. ดึง active tasks
active_tasks = get_tasks(active=True)

# 2. ดึง tasks ที่เสร็จแล้ว 7 วันที่ผ่านมา
recent = get_tasks(status='completed', days_ago=7)

# 3. ค้นหาตาม filename
meetings = get_tasks(filename_contains='meeting')

# 4. Complex filter
results = get_tasks(
    status='completed',
    language='th',
    days_ago=7,
    filename_contains='test',
    limit=20
)

print(f"Found {results['total_count']} tasks")
for task in results['tasks']:
    print(f"- {task['filename']}: {task['status']}")
```

---

### 4. Upload ไฟล์

```python
def upload_file(file_path: str) -> dict:
    """Upload ไฟล์"""
    url = 'http://localhost:8001/api/upload/'
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files)
    
    response.raise_for_status()
    return response.json()

def upload_from_url(file_url: str) -> dict:
    """Upload จาก URL"""
    url = 'http://localhost:8001/api/upload/'
    
    data = {'url': file_url}
    response = requests.post(url, data=data)
    
    response.raise_for_status()
    return response.json()

# การใช้งาน
result = upload_file('/path/to/video.mp4')
print(f"Uploaded: {result['file_path']}")
```

---

### 5. Workflow สมบูรณ์

```python
def transcribe_file(file_path: str, language: str = 'th') -> dict:
    """Workflow: Upload → Start → Poll → Result"""
    
    # 1. Upload
    print("Uploading file...")
    upload_result = upload_file(file_path)
    
    # 2. Start transcription
    print("Starting transcription...")
    start_url = 'http://localhost:8001/api/transcribe/'
    start_data = {
        'file_path': upload_result['file_path'],
        'language': language,
        'model_size': 'base'
    }
    
    response = requests.post(start_url, json=start_data)
    response.raise_for_status()
    task_id = response.json()['task_id']
    
    # 3. Poll until complete
    print("Waiting for transcription...")
    result = poll_task_until_complete(
        task_id,
        on_progress=lambda p: print(f"Progress: {p}%")
    )
    
    return result

# การใช้งาน
result = transcribe_file('/path/to/video.mp4', language='th')
print(f"Text: {result['result']['text']}")
print(f"Segments: {len(result['result']['segments'])}")
```

---

## <a name="curl"></a>🌐 cURL Examples

### 1. ดึงสถานะ Task

```bash
# Full data
curl http://localhost:8001/api/v2/tasks/abc-123?format=full

# Progress tracking
curl http://localhost:8001/api/v2/tasks/abc-123?format=progress

# Minimal (polling)
curl http://localhost:8001/api/v2/tasks/abc-123?format=minimal
```

---

### 2. ดึงรายการ Tasks

```bash
# ทั้งหมด
curl "http://localhost:8001/api/v2/tasks?limit=20"

# Active tasks
curl "http://localhost:8001/api/v2/tasks?active=true"

# ตามวันที่
curl "http://localhost:8001/api/v2/tasks?date=2025-12-29"

# Complex filter
curl "http://localhost:8001/api/v2/tasks?status=completed&days_ago=7&language=th"
```

---

### 3. Upload ไฟล์

```bash
# Upload ไฟล์
curl -X POST http://localhost:8001/api/upload/ \
  -F "file=@/path/to/video.mp4"

# Upload จาก URL
curl -X POST http://localhost:8001/api/upload/ \
  -F "url=https://example.com/video.mp4"
```

---

### 4. เริ่ม Transcription

```bash
curl -X POST http://localhost:8001/api/transcribe/ \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/uploads/video.mp4",
    "language": "th",
    "model_size": "base"
  }'
```

---

## <a name="react"></a>⚛️ React Hooks Examples

### 1. useTaskStatus Hook

```typescript
import { useState, useEffect } from 'react'

interface UseTaskStatusOptions {
  format?: 'full' | 'progress' | 'minimal'
  pollingInterval?: number
  autoRefresh?: boolean
}

function useTaskStatus(
  taskId: string,
  options: UseTaskStatusOptions = {}
) {
  const {
    format = 'full',
    pollingInterval = 5000,
    autoRefresh = true
  } = options
  
  const [task, setTask] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    
    const fetchTask = async () => {
      try {
        const response = await fetch(
          `http://localhost:8001/api/v2/tasks/${taskId}?format=${format}`
        )
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        
        const data = await response.json()
        setTask(data)
        setError(null)
        
        // ถ้าเสร็จแล้ว หยุด polling
        if (data.status === 'completed' || data.status === 'failed') {
          if (interval) clearInterval(interval)
        }
        
      } catch (err) {
        setError(err as Error)
      } finally {
        setLoading(false)
      }
    }
    
    // Fetch ครั้งแรก
    fetchTask()
    
    // Auto-refresh ถ้าเปิดใช้งาน
    if (autoRefresh) {
      interval = setInterval(fetchTask, pollingInterval)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [taskId, format, pollingInterval, autoRefresh])
  
  return { task, loading, error }
}

// การใช้งาน
function TaskDetail({ taskId }: { taskId: string }) {
  const { task, loading, error } = useTaskStatus(taskId, {
    format: 'full',
    autoRefresh: true,
    pollingInterval: 3000
  })
  
  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  if (!task) return null
  
  return (
    <div>
      <h2>{task.filename}</h2>
      <p>Status: {task.status}</p>
      <p>Progress: {task.progress}%</p>
      
      {task.status === 'completed' && (
        <div>
          <h3>Result:</h3>
          <p>{task.result.text}</p>
        </div>
      )}
    </div>
  )
}
```

---

### 2. useTaskList Hook

```typescript
interface UseTaskListOptions {
  status?: string
  active?: boolean
  daysAgo?: number
  limit?: number
  autoRefresh?: boolean
  refreshInterval?: number
}

function useTaskList(options: UseTaskListOptions = {}) {
  const [tasks, setTasks] = useState<any[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  
  const fetchTasks = async () => {
    try {
      const params = new URLSearchParams()
      
      if (options.status) params.append('status', options.status)
      if (options.active !== undefined) params.append('active', String(options.active))
      if (options.daysAgo) params.append('days_ago', String(options.daysAgo))
      if (options.limit) params.append('limit', String(options.limit))
      
      const response = await fetch(
        `http://localhost:8001/api/v2/tasks?${params.toString()}`
      )
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const data = await response.json()
      setTasks(data.tasks)
      setTotalCount(data.total_count)
      setError(null)
      
    } catch (err) {
      setError(err as Error)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchTasks()
    
    let interval: NodeJS.Timeout | null = null
    
    if (options.autoRefresh) {
      interval = setInterval(fetchTasks, options.refreshInterval || 10000)
    }
    
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [
    options.status,
    options.active,
    options.daysAgo,
    options.limit,
    options.autoRefresh,
    options.refreshInterval
  ])
  
  return { tasks, totalCount, loading, error, refresh: fetchTasks }
}

// การใช้งาน
function TaskList() {
  const { tasks, totalCount, loading, error, refresh } = useTaskList({
    status: 'completed',
    limit: 20,
    autoRefresh: true,
    refreshInterval: 10000
  })
  
  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  
  return (
    <div>
      <h2>Tasks ({totalCount})</h2>
      <button onClick={refresh}>Refresh</button>
      
      <ul>
        {tasks.map((task) => (
          <li key={task.task_id}>
            {task.filename} - {task.status} ({task.progress}%)
          </li>
        ))}
      </ul>
    </div>
  )
}
```

---

## 🎓 สรุป

ตัวอย่างเหล่านี้แสดงวิธีการใช้งาน API v2 ในภาษาต่างๆ:

- ✅ **JavaScript/TypeScript** - สำหรับ web applications
- ✅ **Python** - สำหรับ backend scripts, automation
- ✅ **cURL** - สำหรับ testing และ debugging
- ✅ **React Hooks** - สำหรับ React applications

**Copy & Paste พร้อมใช้งาน!** 🚀





