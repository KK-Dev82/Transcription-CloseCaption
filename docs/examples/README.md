# 📋 API Usage Examples

## 🎯 Overview

ตัวอย่างการใช้งาน Transcription API ในสถานการณ์ต่างๆ

## 🚀 Basic Examples

### 1. Simple Transcription

```bash
# 1. Upload file
curl -X POST -F "file=@meeting.mp4" \
  http://localhost:8001/upload/

# Response: {"file_path": "uploads/uuid_meeting.mp4", ...}

# 2. Start transcription
curl -X POST -H "Content-Type: application/json" \
  -d '{"file_path": "uploads/uuid_meeting.mp4", "language": "th"}' \
  http://localhost:8001/transcribe-enhanced/start

# Response: {"task_id": "task-uuid", ...}

# 3. Check progress
curl http://localhost:8001/progress/transcription/task-uuid

# 4. Get results
curl http://localhost:8001/transcribe-enhanced/status/task-uuid
```

### 2. Video Processing + Transcription

```bash
# Segment video and transcribe
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "file_path": "uploads/long_video.mp4",
    "language": "th", 
    "chunk_duration": 600,
    "model_size": "base"
  }' \
  http://localhost:8001/video/segment

# Monitor segmentation progress
curl http://localhost:8001/video/segment/task-uuid
```

### 3. Search in Transcription

```bash
# Search for specific words
curl -X POST -H "Content-Type: application/json" \
  -d '{"query": "การประชุม"}' \
  http://localhost:8001/transcribe/search/task-uuid

# Response with timestamps and matches
```

## 🐍 Python Examples

### Complete Workflow

```python
import requests
import time
import json
from pathlib import Path

class TranscriptionClient:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
    
    def upload_file(self, file_path):
        """Upload a video/audio file"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{self.base_url}/upload/", files=files)
            response.raise_for_status()
            return response.json()
    
    def start_transcription(self, file_path, language="th", model_size="base"):
        """Start enhanced transcription"""
        data = {
            "file_path": file_path,
            "language": language,
            "model_size": model_size,
            "chunk_duration": 30
        }
        response = requests.post(
            f"{self.base_url}/transcribe-enhanced/start",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_progress(self, task_id):
        """Get transcription progress"""
        response = requests.get(f"{self.base_url}/progress/transcription/{task_id}")
        response.raise_for_status()
        return response.json()
    
    def get_results(self, task_id):
        """Get transcription results"""
        response = requests.get(f"{self.base_url}/transcribe-enhanced/status/{task_id}")
        response.raise_for_status()
        return response.json()
    
    def search_text(self, task_id, query):
        """Search in transcription"""
        data = {"query": query}
        response = requests.post(
            f"{self.base_url}/transcribe/search/{task_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, task_id, poll_interval=5):
        """Wait for transcription to complete"""
        while True:
            progress = self.get_progress(task_id)
            print(f"Progress: {progress['progress']}% - {progress['stage']}")
            
            if progress['status'] == 'completed':
                return self.get_results(task_id)
            elif progress['status'] == 'failed':
                raise Exception("Transcription failed")
            
            time.sleep(poll_interval)

# Usage example
def main():
    client = TranscriptionClient()
    
    # 1. Upload file
    print("Uploading file...")
    upload_result = client.upload_file("meeting_recording.mp4")
    print(f"File uploaded: {upload_result['file_path']}")
    
    # 2. Start transcription
    print("Starting transcription...")
    task = client.start_transcription(upload_result['file_path'])
    task_id = task['task_id']
    print(f"Task started: {task_id}")
    
    # 3. Wait for completion
    print("Waiting for completion...")
    results = client.wait_for_completion(task_id)
    
    # 4. Display results
    print(f"Transcription completed!")
    print(f"Total chunks: {len(results['chunks'])}")
    print(f"Full text length: {len(results['text'])} characters")
    
    if results.get('thai_processing_stats'):
        stats = results['thai_processing_stats']
        print(f"Thai corrections: {stats['corrected_chunks']}/{stats['total_chunks']}")
        print(f"Correction rate: {stats['correction_rate']*100:.1f}%")
    
    # 5. Search for keywords
    search_terms = ["การประชุม", "โครงการ", "งบประมาณ"]
    for term in search_terms:
        search_results = client.search_text(task_id, term)
        if search_results['total_matches'] > 0:
            print(f"\nFound '{term}' {search_results['total_matches']} times:")
            for match in search_results['matches'][:3]:  # Show first 3 matches
                start_time = int(match['start_time'])
                end_time = int(match['end_time'])
                print(f"  {start_time//60:02d}:{start_time%60:02d}-{end_time//60:02d}:{end_time%60:02d}: {match['text'][:100]}...")

if __name__ == "__main__":
    main()
```

### Batch Processing

```python
import os
import concurrent.futures
from pathlib import Path

def process_file(file_path):
    """Process a single file"""
    client = TranscriptionClient()
    
    try:
        # Upload
        upload_result = client.upload_file(file_path)
        
        # Start transcription
        task = client.start_transcription(upload_result['file_path'])
        
        # Wait for completion
        results = client.wait_for_completion(task['task_id'])
        
        # Save results
        output_file = f"transcripts/{Path(file_path).stem}.json"
        os.makedirs("transcripts", exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Completed: {file_path} -> {output_file}")
        return {"file": file_path, "status": "success", "output": output_file}
        
    except Exception as e:
        print(f"❌ Failed: {file_path} - {str(e)}")
        return {"file": file_path, "status": "error", "error": str(e)}

def batch_process(input_folder, max_workers=3):
    """Process multiple files in parallel"""
    # Find all video/audio files
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
    supported_extensions = video_extensions | audio_extensions
    
    files = []
    for ext in supported_extensions:
        files.extend(Path(input_folder).glob(f"*{ext}"))
        files.extend(Path(input_folder).glob(f"*{ext.upper()}"))
    
    print(f"Found {len(files)} files to process")
    
    # Process files in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_file, file): file for file in files}
        
        for future in concurrent.futures.as_completed(future_to_file):
            result = future.result()
            results.append(result)
    
    # Summary
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - successful
    
    print(f"\n📊 Batch Processing Summary:")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    return results

# Usage
if __name__ == "__main__":
    results = batch_process("input_videos/", max_workers=2)
```

## 🌐 JavaScript/Node.js Examples

### Express.js Integration

```javascript
const express = require('express');
const multer = require('multer');
const axios = require('axios');

const app = express();
const upload = multer({ dest: 'uploads/' });

// Transcription API client
class TranscriptionAPI {
  constructor(baseURL = 'http://localhost:8001') {
    this.baseURL = baseURL;
    this.axios = axios.create({ baseURL });
  }

  async uploadFile(filePath, originalName) {
    const FormData = require('form-data');
    const fs = require('fs');
    
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath), originalName);
    
    const response = await this.axios.post('/upload/', form, {
      headers: form.getHeaders(),
    });
    
    return response.data;
  }

  async startTranscription(filePath, options = {}) {
    const response = await this.axios.post('/transcribe-enhanced/start', {
      file_path: filePath,
      language: options.language || 'th',
      model_size: options.modelSize || 'base',
      chunk_duration: options.chunkDuration || 30,
    });
    
    return response.data;
  }

  async getProgress(taskId) {
    const response = await this.axios.get(`/progress/transcription/${taskId}`);
    return response.data;
  }

  async getResults(taskId) {
    const response = await this.axios.get(`/transcribe-enhanced/status/${taskId}`);
    return response.data;
  }
}

const api = new TranscriptionAPI();

// Routes
app.post('/api/transcribe', upload.single('file'), async (req, res) => {
  try {
    // Upload to transcription service
    const uploadResult = await api.uploadFile(req.file.path, req.file.originalname);
    
    // Start transcription
    const task = await api.startTranscription(uploadResult.file_path, {
      language: req.body.language || 'th',
      modelSize: req.body.modelSize || 'base',
    });
    
    res.json({
      success: true,
      taskId: task.task_id,
      message: 'Transcription started successfully',
    });
    
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

app.get('/api/progress/:taskId', async (req, res) => {
  try {
    const progress = await api.getProgress(req.params.taskId);
    res.json(progress);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/results/:taskId', async (req, res) => {
  try {
    const results = await api.getResults(req.params.taskId);
    res.json(results);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
```

### Real-time Progress with WebSocket

```javascript
const WebSocket = require('ws');

class RealtimeTranscription {
  constructor(apiBaseURL = 'http://localhost:8001') {
    this.api = new TranscriptionAPI(apiBaseURL);
  }

  async startWithProgress(filePath, originalName, onProgress) {
    try {
      // Upload file
      const uploadResult = await this.api.uploadFile(filePath, originalName);
      
      // Start transcription
      const task = await this.api.startTranscription(uploadResult.file_path);
      const taskId = task.task_id;
      
      // Poll for progress
      const pollProgress = async () => {
        try {
          const progress = await this.api.getProgress(taskId);
          onProgress(progress);
          
          if (progress.status === 'completed') {
            const results = await this.api.getResults(taskId);
            onProgress({ ...progress, results });
            return;
          } else if (progress.status === 'failed') {
            onProgress({ ...progress, error: 'Transcription failed' });
            return;
          }
          
          // Continue polling
          setTimeout(pollProgress, 2000);
        } catch (error) {
          onProgress({ error: error.message });
        }
      };
      
      // Start polling
      setTimeout(pollProgress, 1000);
      
      return taskId;
      
    } catch (error) {
      onProgress({ error: error.message });
    }
  }
}

// Usage example
const transcription = new RealtimeTranscription();

transcription.startWithProgress('video.mp4', 'video.mp4', (progress) => {
  if (progress.error) {
    console.error('Error:', progress.error);
  } else if (progress.results) {
    console.log('✅ Transcription completed!');
    console.log('Text:', progress.results.text.substring(0, 100) + '...');
  } else {
    console.log(`Progress: ${progress.progress}% - ${progress.stage}`);
  }
});
```

## 🔄 Advanced Use Cases

### 1. Meeting Minutes Generator

```python
def generate_meeting_minutes(task_id):
    """Generate structured meeting minutes from transcription"""
    client = TranscriptionClient()
    
    # Get transcription results
    results = client.get_results(task_id)
    
    # Search for key topics
    topics = {
        "agenda": ["วาระ", "ระเบียบวาระ", "หัวข้อ"],
        "decisions": ["ตัดสินใจ", "มติ", "สรุป", "เห็นชอบ"],
        "action_items": ["มอบหมาย", "ดำเนินการ", "รับผิดชอบ"],
        "next_meeting": ["ประชุมครั้งต่อไป", "นัดหมาย", "กำหนดการ"]
    }
    
    minutes = {
        "meeting_date": "2024-01-15",
        "duration": f"{len(results['chunks']) * 30 // 60} minutes",
        "sections": {}
    }
    
    for section, keywords in topics.items():
        section_content = []
        for keyword in keywords:
            search_results = client.search_text(task_id, keyword)
            for match in search_results['matches']:
                section_content.append({
                    "time": f"{int(match['start_time'])//60:02d}:{int(match['start_time'])%60:02d}",
                    "content": match['text']
                })
        minutes["sections"][section] = section_content
    
    return minutes
```

### 2. Subtitle Generator

```python
def generate_subtitles(task_id, max_chars_per_line=50):
    """Generate SRT subtitles from transcription"""
    client = TranscriptionClient()
    results = client.get_results(task_id)
    
    srt_content = []
    
    for i, chunk in enumerate(results['chunks'], 1):
        start_time = chunk['start_time']
        end_time = chunk['end_time']
        text = chunk['text']
        
        # Format time for SRT (HH:MM:SS,mmm)
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')
        
        # Break long text into multiple lines
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= max_chars_per_line:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # Add to SRT
        srt_content.append(f"{i}")
        srt_content.append(f"{format_time(start_time)} --> {format_time(end_time)}")
        srt_content.extend(lines)
        srt_content.append("")  # Empty line
    
    return "\n".join(srt_content)

# Save subtitles
srt_content = generate_subtitles(task_id)
with open("subtitles.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)
```

### 3. Content Analysis

```python
def analyze_content(task_id):
    """Analyze transcription content for insights"""
    client = TranscriptionClient()
    results = client.get_results(task_id)
    
    # Word frequency analysis
    import re
    from collections import Counter
    
    # Clean and tokenize text
    text = results['text'].lower()
    words = re.findall(r'\b[\u0E00-\u0E7F]+\b', text)  # Thai words only
    
    # Remove common stop words
    stop_words = {'และ', 'ที่', 'ใน', 'เป็น', 'มี', 'ของ', 'จะ', 'ได้', 'แล้ว', 'นะ', 'ครับ', 'ค่ะ'}
    words = [word for word in words if word not in stop_words and len(word) > 1]
    
    word_freq = Counter(words)
    
    # Topic detection (simple keyword-based)
    topics = {
        'technology': ['เทคโนโลยี', 'ระบบ', 'ซอฟต์แวร์', 'แอป', 'เว็บไซต์'],
        'business': ['ธุรกิจ', 'การตลาด', 'ลูกค้า', 'ขาย', 'รายได้'],
        'project': ['โครงการ', 'แผน', 'เป้าหมาย', 'กำหนดการ', 'งบประมาณ'],
        'meeting': ['ประชุม', 'วาระ', 'มติ', 'สรุป', 'นัดหมาย']
    }
    
    topic_scores = {}
    for topic, keywords in topics.items():
        score = sum(word_freq.get(keyword, 0) for keyword in keywords)
        topic_scores[topic] = score
    
    return {
        'total_words': len(words),
        'unique_words': len(word_freq),
        'most_common_words': word_freq.most_common(10),
        'topic_scores': topic_scores,
        'dominant_topic': max(topic_scores, key=topic_scores.get),
        'processing_stats': results.get('thai_processing_stats', {})
    }
```

## 📊 Performance Testing

```python
import time
import statistics

def benchmark_transcription(file_paths, iterations=3):
    """Benchmark transcription performance"""
    client = TranscriptionClient()
    
    results = []
    
    for file_path in file_paths:
        file_results = []
        
        for i in range(iterations):
            print(f"Testing {file_path} - Run {i+1}/{iterations}")
            
            start_time = time.time()
            
            # Upload
            upload_result = client.upload_file(file_path)
            upload_time = time.time() - start_time
            
            # Transcribe
            transcribe_start = time.time()
            task = client.start_transcription(upload_result['file_path'])
            final_results = client.wait_for_completion(task['task_id'])
            transcribe_time = time.time() - transcribe_start
            
            total_time = time.time() - start_time
            
            file_results.append({
                'upload_time': upload_time,
                'transcribe_time': transcribe_time,
                'total_time': total_time,
                'chunks': len(final_results['chunks']),
                'duration': upload_result.get('duration', 0),
                'processing_speed': upload_result.get('duration', 0) / transcribe_time if transcribe_time > 0 else 0
            })
        
        # Calculate averages
        avg_result = {
            'file': file_path,
            'avg_upload_time': statistics.mean([r['upload_time'] for r in file_results]),
            'avg_transcribe_time': statistics.mean([r['transcribe_time'] for r in file_results]),
            'avg_total_time': statistics.mean([r['total_time'] for r in file_results]),
            'avg_processing_speed': statistics.mean([r['processing_speed'] for r in file_results]),
            'iterations': iterations
        }
        
        results.append(avg_result)
    
    return results

# Run benchmark
test_files = ['short_video.mp4', 'medium_video.mp4', 'long_video.mp4']
benchmark_results = benchmark_transcription(test_files)

for result in benchmark_results:
    print(f"\n📊 {result['file']}:")
    print(f"  Upload: {result['avg_upload_time']:.2f}s")
    print(f"  Transcribe: {result['avg_transcribe_time']:.2f}s") 
    print(f"  Total: {result['avg_total_time']:.2f}s")
    print(f"  Speed: {result['avg_processing_speed']:.2f}x realtime")
```

## 🔗 Related Documentation

- [API Reference](../api/README.md)
- [Frontend Integration](../frontend/integration.md)
- [Deployment Guide](../deployment/README.md)
