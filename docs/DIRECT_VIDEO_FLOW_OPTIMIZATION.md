# Direct Video Flow Optimization

## 📋 สรุป Direct Video Flow (Standalone)

### Current Flow (Sequential - ช้า) ❌
```
Client → Transcription API → RabbitMQ (transcription_queue)
                              ↓
                         Video Worker
                              ↓
                    [Audio Extraction] ✅
                              ↓
                    [Chunking (30s)] ✅
                              ↓
                    [Sequential Processing] ❌ (ช้า, GPU 24%)
                              ↓
                    [Merge Results]
```

### Recommended Flow (Parallel - เร็ว) ✅
```
Client → Transcription API → [Audio Extraction] ✅
                              ↓
                         [Chunking (30-60s)] ✅
                              ↓
                    RabbitMQ (transcription_chunk_queue) ✅
                              ↓
                    [Parallel Workers] ✅ (GPU 80-100%)
                              ↓
                    [Merge Results]
```

---

## 🎯 คำตอบ: Direct Video Flow ต้องมีอะไรบ้าง?

### ✅ 1. Audio Extraction (ต้องมี)
- **Direct Video Flow**: Transcription Service ต้อง extract audio เอง
- **ไม่มี Media Processor** → ต้องจัดการเอง
- **Code**: `video_service.extract_audio_chunks()` หรือ `file_service.create_chunks()`

### ✅ 2. Chunking (ต้องมี)
- **Full Transcription**: 30-60s chunks (ไม่ใช่ 3s)
- **Close Caption (3s)**: ให้ Media Processor จัดการ (ไม่ใช่ Direct Flow)
- **Code**: `extract_audio_chunks(local_file_path, chunk_duration=30)`

### ✅ 3. Queue-based Parallel Processing (แนะนำ)
- **Current**: Sequential processing (ช้า)
- **Recommended**: ส่ง chunks ไปยัง queue → Workers process แบบ parallel
- **Benefits**:
  - GPU utilization สูงขึ้น (80-100%)
  - เร็วกว่า real-time (0.5-1.0x)
  - Auto-balancing
  - Scalable

### ✅ 4. RabbitMQ Management (ต้องมี)
- **Queue**: `transcription_chunk_queue` (ใหม่)
- **Workers**: Multiple workers with `prefetch_count=5-10`
- **Auto-balancing**: RabbitMQ จัดการเอง

---

## 🔧 Implementation Plan

### Phase 1: สร้าง Chunk Queue และ Handler

#### 1.1 เพิ่ม Queue ใน RabbitMQ Service
```python
# app/services/rabbitmq_service.py
def send_chunk_transcription_task(self, chunk_task: Dict) -> str:
    """ส่ง chunk transcription task ไปยัง queue"""
    self._ensure_connection()
    self.channel.queue_declare(queue='transcription_chunk_queue', durable=True)
    
    self.channel.basic_publish(
        exchange='',
        routing_key='transcription_chunk_queue',
        body=json.dumps(chunk_task),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Persistent
            content_type='application/json'
        )
    )
    return chunk_task.get('task_id')
```

#### 1.2 แก้ไข `_process_transcription()` ให้ส่ง chunks ไปยัง queue
```python
# app/services/transcription_service.py
async def _process_transcription(...):
    # ... audio extraction และ chunking ...
    
    # แทนที่จะ process chunks ตรงๆ
    # ส่งแต่ละ chunk ไปยัง queue
    for i, chunk_path in enumerate(chunks):
        chunk_task = {
            "task_id": f"{task_id}_chunk_{i}",
            "parent_task_id": task_id,
            "chunk_path": chunk_path,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "chunk_duration": chunk_duration,
            "model_size": model_size,
            "language": language,
            "file_path": local_file_path,
            "file_name": file_name,
            "created_at": datetime.now().isoformat()
        }
        self.rabbitmq_service.send_chunk_transcription_task(chunk_task)
    
    # Update task status
    task.status = "processing_chunks"
    task.progress = 10
    self.json_storage.save_transcription(task_id, task.__dict__)
```

#### 1.3 เพิ่ม Chunk Handler ใน Video Worker
```python
# app/workers/video_worker.py
def setup_consumers(self):
    # ... existing consumers ...
    
    # Chunk transcription consumer (ใหม่)
    self.channel.basic_consume(
        queue='transcription_chunk_queue',
        on_message_callback=self._process_chunk_transcription_task,
        auto_ack=False
    )

def _process_chunk_transcription_task(self, ch, method, properties, body):
    """ประมวลผล chunk transcription task"""
    try:
        chunk_task = json.loads(body.decode('utf-8'))
        parent_task_id = chunk_task['parent_task_id']
        chunk_path = chunk_task['chunk_path']
        chunk_index = chunk_task['chunk_index']
        total_chunks = chunk_task['total_chunks']
        
        logger.info(f"Processing chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
        
        # Transcribe chunk
        result = self.transcription_service.whisper_service.transcribe_file(
            chunk_path,
            chunk_task['model_size'],
            chunk_task['language'],
            use_thai_processor=True
        )
        
        # Save chunk result
        self._save_chunk_result(parent_task_id, chunk_index, result, chunk_task)
        
        # Check if all chunks completed
        if self._all_chunks_completed(parent_task_id, total_chunks):
            self._merge_and_finalize(parent_task_id)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing chunk: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def _save_chunk_result(self, parent_task_id: str, chunk_index: int, result: Dict, chunk_task: Dict):
    """บันทึกผลลัพธ์ของ chunk"""
    # Load parent task
    parent_task = self.json_storage.get_transcription(parent_task_id)
    if not parent_task:
        logger.error(f"Parent task {parent_task_id} not found")
        return
    
    # Initialize chunks array if not exists
    if 'chunks' not in parent_task:
        parent_task['chunks'] = [None] * chunk_task['total_chunks']
    
    # Save chunk result
    chunk_duration = chunk_task.get('chunk_duration', 30)
    start_time = chunk_index * chunk_duration
    end_time = start_time + chunk_duration
    
    chunk_data = {
        "start_time": start_time,
        "end_time": end_time,
        "text": result.get("text", ""),
        "segments": result.get("segments", []),
        "confidence": result.get("avg_logprob")
    }
    
    parent_task['chunks'][chunk_index] = chunk_data
    
    # Update progress
    completed_chunks = sum(1 for c in parent_task['chunks'] if c is not None)
    progress = 10 + int((completed_chunks / chunk_task['total_chunks']) * 80)
    parent_task['progress'] = progress
    parent_task['status'] = f"processing_chunk_{completed_chunks}_of_{chunk_task['total_chunks']}"
    
    # Save to storage
    self.json_storage.save_transcription(parent_task_id, parent_task)
    
    logger.info(f"✅ Saved chunk {chunk_index+1}/{chunk_task['total_chunks']} - Progress: {progress}%")

def _all_chunks_completed(self, parent_task_id: str, total_chunks: int) -> bool:
    """ตรวจสอบว่า chunks ทั้งหมดเสร็จแล้วหรือยัง"""
    parent_task = self.json_storage.get_transcription(parent_task_id)
    if not parent_task:
        return False
    
    chunks = parent_task.get('chunks', [])
    completed = sum(1 for c in chunks if c is not None)
    return completed >= total_chunks

def _merge_and_finalize(self, parent_task_id: str):
    """รวมผลลัพธ์และ finalize task"""
    parent_task = self.json_storage.get_transcription(parent_task_id)
    if not parent_task:
        logger.error(f"Parent task {parent_task_id} not found for merging")
        return
    
    chunks = parent_task.get('chunks', [])
    
    # Merge text
    full_text = " ".join([chunk.get('text', '') for chunk in chunks if chunk])
    
    # Update task
    parent_task['full_text'] = full_text
    parent_task['status'] = 'completed'
    parent_task['progress'] = 100
    parent_task['completed_at'] = datetime.now().isoformat()
    
    # Save final result
    self.json_storage.save_transcription(parent_task_id, parent_task)
    
    logger.info(f"✅ Merged and finalized task {parent_task_id}")
    
    # Send callback if needed
    if parent_task.get('callback_url'):
        # ... send webhook callback ...
        pass
```

---

## 📊 Performance Comparison

### Current (Sequential):
- GPU utilization: 24%
- Speed: 1.7x real-time (ช้า)
- วีดิโอ 10 นาที → 17 นาที

### After Optimization (Parallel):
- GPU utilization: 80-100%
- Speed: 0.5-1.0x real-time (เร็ว)
- วีดิโอ 10 นาที → 5-10 นาที

---

## 🎯 Summary

### Direct Video Flow ต้องมี:

1. ✅ **Audio Extraction** - Transcription Service จัดการเอง
2. ✅ **Chunking (30-60s)** - Transcription Service จัดการเอง
3. ✅ **Queue-based Parallel** - ส่ง chunks ไปยัง `transcription_chunk_queue`
4. ✅ **RabbitMQ Management** - Workers process chunks แบบ parallel

### ไม่ต้องมี:
- ❌ Media Processor (สำหรับ Direct Flow)
- ❌ Backend (สำหรับ Direct Flow)

### Key Point:
**Direct Video Flow = Standalone = Transcription Service จัดการเองทั้งหมด**
- Audio extraction ✅
- Chunking ✅
- Queue management ✅
- Parallel processing ✅

