"""
RQ Worker Module - Persistent Transcription Service
Init TranscriptionService ครั้งเดียวตอน import แทน init ทุก job
"""
import asyncio
import json
import logging
import os
from typing import Dict
from redis import Redis

logger = logging.getLogger(__name__)

# ============================================================================
# Persistent Services (Init ครั้งเดียวตอน worker start)
# ============================================================================

# Redis connection pool (reuse connections)
_redis_conn = None

def get_redis_connection(decode_responses=True):
    """Get or create persistent Redis connection (per worker process)"""
    # ใช้ thread-local storage เพื่อให้แต่ละ worker process มี connection ของตัวเอง
    import threading
    thread_local = threading.local()
    
    if not hasattr(thread_local, 'redis_conn'):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        # ใช้ connection pool เพื่อ reuse connections
        from redis.connection import ConnectionPool
        pool = ConnectionPool.from_url(redis_url, max_connections=10, decode_responses=decode_responses)
        thread_local.redis_conn = Redis(connection_pool=pool)
        logger.debug("✅ Redis connection initialized (per worker thread)")
    
    return thread_local.redis_conn

# Init TranscriptionService ครั้งเดียว
# จะถูก init เมื่อ module ถูก import (ตอน worker start)
_transcription_service = None
_event_loop = None

def get_transcription_service():
    """Get or create persistent TranscriptionService instance"""
    global _transcription_service
    if _transcription_service is None:
        logger.info("🚀 Initializing persistent TranscriptionService (one-time init)...")
        from app.services.transcription_service import TranscriptionService
        _transcription_service = TranscriptionService()
        logger.info("✅ TranscriptionService initialized (will be reused for all jobs)")
    return _transcription_service

def get_event_loop():
    """Get or create persistent event loop"""
    global _event_loop
    if _event_loop is None:
        # ใช้ new_event_loop เสมอใน worker process (ไม่ใช้ get_event_loop)
        # เพื่อป้องกันปัญหา event loop conflict
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
        logger.info("✅ Event loop initialized (will be reused for all jobs)")
    return _event_loop

# ============================================================================
# Worker Functions
# ============================================================================

def process_transcription_job(
    task_id: str,
    file_path: str,
    language: str,
    model_size: str,
    chunk_duration: int = 90
) -> Dict:
    """
    RQ Worker function - ใช้ persistent TranscriptionService
    
    Args:
        task_id: Task ID
        file_path: Path to audio/video file
        language: Language code
        model_size: Whisper model size
        chunk_duration: Chunk duration in seconds
    
    Returns:
        Transcription result dictionary
    """
    logger.info(f"🚀 RQ Worker: Starting transcription job {task_id}")
    logger.info(f"   File: {file_path}")
    logger.info(f"   Model: {model_size}, Language: {language}, Chunk: {chunk_duration}s")
    
    try:
        # ใช้ persistent service (ไม่ init ใหม่)
        transcription_service = get_transcription_service()
        logger.info(f"✅ Using persistent TranscriptionService (instance: {id(transcription_service)})")
        loop = get_event_loop()
        logger.info(f"✅ Using persistent event loop (instance: {id(loop)})")
        
        # สร้าง task object สำหรับ worker (worker instance ไม่มี task ใน tasks dict)
        from app.models.transcription import TranscriptionResponse
        from datetime import datetime, timezone
        
        task = TranscriptionResponse(
            task_id=task_id,
            status="processing",
            file_path=file_path,
            language=language,
            model_size=model_size,
            created_at=datetime.now(timezone.utc),
            progress=0
        )
        
        # เพิ่ม task เข้า service.tasks (เพื่อให้ _process_transcription ทำงานได้)
        transcription_service.tasks[task_id] = task
        
        # ตรวจสอบว่าเป็น chunk job, aggregator job หรือ full job
        # ถ้า task_id มี "_chunk_" แสดงว่าเป็น chunk job (ไม่ต้อง chunking อีก)
        # ถ้า task_id มี "_aggregator" แสดงว่าเป็น aggregator job (รอ chunks แล้ว merge)
        is_chunk_job = "_chunk_" in task_id
        is_aggregator_job = "_aggregator" in task_id
        
        if is_chunk_job:
            # Chunk job: transcribe chunk เดียวโดยตรง (ไม่ต้อง chunking)
            logger.info(f"📦 Processing single chunk (chunk job)")
            # ใช้ provider.transcribe() (async) แทน transcribe() ที่ไม่มี
            transcription_result = loop.run_until_complete(
                transcription_service.whisper_service.provider.transcribe(
                    audio_path=file_path,
                    language=language,
                    model_size=model_size
                )
            )
            
            # Convert TranscriptionResult to dict
            if hasattr(transcription_result, 'text'):
                result = {
                    "text": transcription_result.text,
                    "segments": transcription_result.segments if hasattr(transcription_result, 'segments') else [],
                    "processing_time": transcription_result.processing_time if hasattr(transcription_result, 'processing_time') else 0
                }
            elif hasattr(transcription_result, 'to_dict'):
                result = transcription_result.to_dict()
            else:
                # Fallback: ถ้าเป็น dict อยู่แล้ว
                result = transcription_result if isinstance(transcription_result, dict) else {"text": "", "segments": [], "processing_time": 0}
            
            # Update Redis atomic counter เมื่อ chunk เสร็จ
            # ดึง main task_id (เอา _chunk_X ออก)
            main_task_id = task_id.rsplit("_chunk_", 1)[0]
            conn = get_redis_connection(decode_responses=True)
            
            # เก็บ chunk result ใน Redis
            chunk_index = int(task_id.rsplit("_chunk_", 1)[1])
            chunk_result_key = f"task:{main_task_id}:chunk:{chunk_index}"
            conn.setex(
                chunk_result_key,
                3600,  # TTL 1 hour
                json.dumps(result)
            )
            
            # Atomic increment done_chunks counter
            done_key = f"task:{main_task_id}:done_chunks"
            done_count = conn.incr(done_key)
            conn.expire(done_key, 3600)  # TTL 1 hour
            
            # ตรวจสอบว่าทุก chunks เสร็จแล้วหรือยัง
            total_key = f"task:{main_task_id}:total_chunks"
            total_chunks = conn.get(total_key)
            if total_chunks:
                total_chunks = int(total_chunks)
                if done_count >= total_chunks:
                    # ทุก chunks เสร็จแล้ว - trigger aggregator (ถ้ายังไม่ถูก trigger)
                    aggregator_trigger_key = f"task:{main_task_id}:aggregator_triggered"
                    if not conn.exists(aggregator_trigger_key):
                        conn.setex(aggregator_trigger_key, 3600, "1")
                        logger.info(f"✅ All {total_chunks} chunks completed for {main_task_id}, aggregator will process")
            
            logger.info(f"✅ Chunk {chunk_index} completed ({done_count}/{total_chunks if total_chunks else '?'} done)")
        elif is_aggregator_job:
            # Aggregator job: ใช้ Redis atomic counter (ไม่ polling)
            logger.info(f"📊 Processing aggregator job (using Redis atomic counter)")
            
            conn = get_redis_connection(decode_responses=True)
            
            # ดึง main task_id (เอา _aggregator ออก)
            main_task_id = task_id.replace("_aggregator", "")
            
            # ดึง total_chunks และ chunk_duration
            total_key = f"task:{main_task_id}:total_chunks"
            total_chunks = conn.get(total_key)
            if not total_chunks:
                # Fallback: ดึงจาก chunk_jobs metadata
                chunk_data_key = f"task:{main_task_id}:chunk_jobs"
                chunk_data_str = conn.get(chunk_data_key)
                if chunk_data_str:
                    chunk_metadata = json.loads(chunk_data_str)
                    total_chunks = chunk_metadata.get("total_chunks", 0)
                    chunk_duration = chunk_metadata.get("chunk_duration", 90)
                else:
                    raise ValueError(f"Chunk data not found for {main_task_id}")
            else:
                total_chunks = int(total_chunks)
                # ดึง chunk_duration จาก chunk_jobs metadata
                chunk_data_key = f"task:{main_task_id}:chunk_jobs"
                chunk_data_str = conn.get(chunk_data_key)
                if chunk_data_str:
                    chunk_metadata = json.loads(chunk_data_str)
                    chunk_duration = chunk_metadata.get("chunk_duration", 90)
                else:
                    chunk_duration = 90
            
            logger.info(f"📊 Waiting for {total_chunks} chunks to complete (using atomic counter)...")
            
            # รอ chunks เสร็จด้วย atomic counter (ไม่ polling jobs)
            import time
            start_wait_time = time.time()
            max_wait_time = 3600  # 1 hour
            wait_interval = 0.5  # เริ่มต้น 0.5s
            
            while True:
                done_key = f"task:{main_task_id}:done_chunks"
                done_count = conn.get(done_key)
                done_count = int(done_count) if done_count else 0
                
                if done_count >= total_chunks:
                    logger.info(f"✅ All {total_chunks} chunks completed (done: {done_count})")
                    break
                
                if time.time() - start_wait_time > max_wait_time:
                    logger.error(f"⏰ Timeout waiting for chunks (done: {done_count}/{total_chunks})")
                    break
                
                logger.debug(f"⏳ Waiting... ({done_count}/{total_chunks} done)")
                time.sleep(wait_interval)
                if wait_interval < 2.0:
                    wait_interval = min(wait_interval * 1.2, 2.0)
            
            # ดึง chunk results จาก Redis (ไม่ต้อง polling jobs)
            completed_chunks = {}
            for i in range(total_chunks):
                chunk_result_key = f"task:{main_task_id}:chunk:{i}"
                chunk_result_str = conn.get(chunk_result_key)
                
                if chunk_result_str:
                    chunk_result = json.loads(chunk_result_str)
                    # Shift segment timestamps ด้วย offset
                    segments = chunk_result.get('segments', [])
                    start_offset = i * chunk_duration
                    
                    adjusted_segments = []
                    for seg in segments:
                        adjusted_seg = seg.copy() if isinstance(seg, dict) else {}
                        if "start" in adjusted_seg:
                            adjusted_seg["start"] = adjusted_seg["start"] + start_offset
                        if "end" in adjusted_seg:
                            adjusted_seg["end"] = adjusted_seg["end"] + start_offset
                        adjusted_segments.append(adjusted_seg)
                    
                    completed_chunks[i] = {
                        "index": i,
                        "text": chunk_result.get('text', ''),
                        "segments": adjusted_segments,
                        "start_time": start_offset,
                        "end_time": start_offset + chunk_duration,
                        "transcribe_time": chunk_result.get('processing_time', 0)
                    }
                else:
                    # Chunk ไม่พบ (อาจล้มเหลว) - สร้าง empty result
                    logger.warning(f"⚠️  Chunk {i} not found in Redis")
                    completed_chunks[i] = {
                        "index": i,
                        "text": "",
                        "segments": [],
                        "start_time": i * chunk_duration,
                        "end_time": (i + 1) * chunk_duration,
                        "transcribe_time": 0
                    }
            
            # Merge results
            chunk_results = [completed_chunks[i] for i in sorted(completed_chunks.keys())]
            logger.info(f"✅ Retrieved {len(chunk_results)}/{total_chunks} chunks, merging...")
            
            merged_result = transcription_service.whisper_service.merge_transcriptions(
                chunk_results,
                chunk_duration
            )
            
            # Apply Thai processor
            if language == "th":
                logger.info(f"🇹🇭 Applying Thai processor...")
                merged_result = transcription_service.whisper_service._apply_thai_processing(merged_result)
            
            # อัปเดต main task จาก storage (ไม่ใช้ in-memory tasks dict)
            from app.utils.json_storage import JSONStorage
            json_storage = JSONStorage()
            
            # โหลด main task จาก storage
            task_dir = json_storage.storage_dir / "transcriptions" / main_task_id
            metadata_path = task_dir / "metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
            else:
                task_data = {}
            
            # อัปเดต task data
            task_data["status"] = "completed"
            task_data["progress"] = 100
            task_data["full_text"] = merged_result.get("text", "")
            segments = merged_result.get("segments", [])
            if segments:
                task_data["chunks"] = [
                    {
                        "start_time": seg.get("start", 0),
                        "end_time": seg.get("end", 0),
                        "text": seg.get("text", ""),
                        "confidence": seg.get("confidence")
                    }
                    for seg in segments
                ]
            task_data["total_duration"] = merged_result.get("total_duration", 0)
            from datetime import datetime, timezone
            task_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # บันทึกกลับไป storage
            json_storage.save_transcription(main_task_id, task_data)
            logger.info(f"✅ Main task {main_task_id} updated in storage")
            
            result = merged_result
        else:
            # Full job: ใช้ _process_transcription (จะ chunking เอง) - สำหรับ backward compatibility
            logger.info(f"📝 Processing full transcription job (legacy mode)")
            result = loop.run_until_complete(
                transcription_service._process_transcription(
                    task_id=task_id,
                    file_path=file_path,
                    language=language,
                    model_size=model_size,
                    chunk_duration=chunk_duration,
                    use_chunking=True  # ใช้ chunking เสมอ
                )
            )
        
        # ถ้า result เป็น None (เกิด error) ให้ return error dict
        if result is None:
            logger.warning(f"⚠️  _process_transcription returned None for {task_id}")
            # ลองดึง result จาก task object
            if task_id in transcription_service.tasks:
                task = transcription_service.tasks[task_id]
                result = {
                    "text": getattr(task, 'full_text', ''),
                    "segments": [],
                    "processing_time": 0,
                    "status": task.status,
                    "error": getattr(task, 'error_message', None)
                }
            else:
                result = {
                    "text": "",
                    "segments": [],
                    "processing_time": 0,
                    "status": "failed",
                    "error": "Task processing returned None"
                }
        
        # ลบ task จาก memory เพื่อป้องกัน memory leak
        if task_id in transcription_service.tasks:
            del transcription_service.tasks[task_id]
            logger.debug(f"🧹 Cleaned up task {task_id} from memory")
        
        logger.info(f"✅ RQ Worker: Completed transcription job {task_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ RQ Worker: Error processing job {task_id}: {e}", exc_info=True)
        # ลบ task แม้เกิด error
        try:
            transcription_service = get_transcription_service()
            if task_id in transcription_service.tasks:
                del transcription_service.tasks[task_id]
        except:
            pass
        raise

def process_preprocess_job(
    task_id: str,
    file_path: str,
    language: str,
    model_size: str,
    chunk_duration: int = 90
) -> Dict:
    """
    RQ Worker function สำหรับ preprocessing (extract audio + chunking)
    ทำงานใน CPU queue เพื่อไม่ให้ API timeout
    
    Args:
        task_id: Task ID
        file_path: Path to video/audio file
        language: Language code
        model_size: Whisper model size
        chunk_duration: Chunk duration in seconds
    
    Returns:
        Dict with chunk metadata
    """
    logger.info(f"🔧 RQ Worker: Starting preprocess job {task_id}")
    logger.info(f"   File: {file_path}")
    
    try:
        from app.services.video_service import VideoService
        from app.services.redis_queue_service import get_redis_queue_service
        from app.utils.json_storage import JSONStorage
        import os
        import json
        from redis import Redis
        
        json_storage = JSONStorage()
        video_service = VideoService()
        queue_service = get_redis_queue_service()
        
        # อัปเดต progress
        task_dir = json_storage.storage_dir / "transcriptions" / task_id
        metadata_path = task_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
        else:
            task_data = {}
        
        task_data["status"] = "processing"
        task_data["progress"] = 10
        json_storage.save_transcription(task_id, task_data)
        
        # 1. Extract audio
        logger.info(f"🎵 Extracting audio from {file_path}...")
        audio_path = video_service.extract_audio(file_path, task_id=task_id)
        logger.info(f"✅ Audio extracted: {audio_path}")
        
        task_data["progress"] = 20
        json_storage.save_transcription(task_id, task_data)
        
        # 2. Create chunks
        logger.info(f"📦 Creating chunks from {audio_path}...")
        chunks = video_service.create_chunks(audio_path, chunk_duration, task_id=task_id)
        total_chunks = len(chunks)
        logger.info(f"✅ Created {total_chunks} chunks")
        
        task_data["progress"] = 30
        json_storage.save_transcription(task_id, task_data)
        
        # 3. Enqueue chunk jobs ไปยัง GPU queues (Fan-out)
        logger.info(f"📝 Enqueueing {total_chunks} chunks to GPU queues...")
        num_gpus = int(os.getenv('NUM_GPUS', '4'))
        chunk_data = []
        
        for i, chunk_path in enumerate(chunks):
            chunk_task_id = f"{task_id}_chunk_{i}"
            gpu_index = i % num_gpus
            worker_gpu = f'gpu{gpu_index}'
            
            job_id = queue_service.enqueue_transcription(
                task_id=chunk_task_id,
                file_path=chunk_path,
                language=language,
                model_size=model_size,
                chunk_duration=chunk_duration,
                priority=False,
                worker_gpu=worker_gpu
            )
            chunk_data.append({
                "i": i,
                "job_id": job_id,
                "chunk_task_id": chunk_task_id,
                "chunk_path": chunk_path,
                "worker_gpu": worker_gpu
            })
            logger.debug(f"   Chunk {i+1}/{total_chunks} enqueued to {worker_gpu}")
        
        logger.info(f"✅ Enqueued {len(chunk_data)} chunks to GPU queues")
        
        # 4. Enqueue aggregator job
        aggregator_task_id = f"{task_id}_aggregator"
        aggregator_job_id = queue_service.enqueue_aggregator(
            task_id=aggregator_task_id,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration
        )
        
        # เก็บ chunk metadata ไว้ใน Redis
        conn = get_redis_connection(decode_responses=True)
        conn.setex(
            f"task:{task_id}:chunk_jobs",
            3600,  # TTL 1 hour
            json.dumps({
                "chunk_duration": chunk_duration,
                "total_chunks": total_chunks,
                "chunks": chunk_data
            })
        )
        
        # ตั้งค่า Redis atomic counters สำหรับ aggregator
        conn.setex(f"task:{task_id}:total_chunks", 3600, str(total_chunks))
        conn.setex(f"task:{task_id}:done_chunks", 3600, "0")  # เริ่มต้นที่ 0
        
        logger.info(f"✅ Aggregator job enqueued: {aggregator_job_id}")
        logger.info(f"✅ Preprocess job {task_id} completed")
        
        return {
            "task_id": task_id,
            "total_chunks": total_chunks,
            "chunk_data": chunk_data
        }
        
    except Exception as e:
        logger.error(f"❌ RQ Worker: Error in preprocess job {task_id}: {e}", exc_info=True)
        # อัปเดต task status เป็น failed
        try:
            task_data["status"] = "failed"
            task_data["error_message"] = str(e)
            json_storage.save_transcription(task_id, task_data)
        except:
            pass
        raise

# ============================================================================
# Module Initialization
# ============================================================================

# Pre-initialize services เมื่อ module ถูก import
# จะทำให้ worker process มี model พร้อมใช้ทันที
logger.info("📦 Loading RQ Worker module...")

def warmup_model():
    """Warmup model + GPU เพื่อให้ job แรกเร็วขึ้น"""
    try:
        logger.info("🔥 Warming up model and GPU...")
        transcription_service = get_transcription_service()
        loop = get_event_loop()
        
        # สร้างไฟล์เสียงสั้นๆ สำหรับ warmup (1-2 วินาที)
        # ใช้ wave module (built-in) แทน scipy
        import tempfile
        import wave
        import struct
        
        # สร้างไฟล์เสียงว่าง 1 วินาที (16kHz mono, 16-bit)
        sample_rate = 16000
        duration = 1.0  # 1 second
        num_samples = int(sample_rate * duration)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            warmup_file = tmp_file.name
        
        try:
            # เขียน WAV file
            with wave.open(warmup_file, 'wb') as wav_file:
                wav_file.setnchannels(1)  # mono
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(sample_rate)
                # เขียน silence (zero samples)
                silence = struct.pack('<h', 0) * num_samples
                wav_file.writeframes(silence)
            
            # Warmup: transcribe ไฟล์สั้นๆ
            logger.info("🔥 Running warmup transcription...")
            result = loop.run_until_complete(
                transcription_service.whisper_service.provider.transcribe(
                    audio_path=warmup_file,
                    language="th",
                    model_size="base"
                )
            )
            logger.info("✅ Warmup completed - GPU and model are ready")
        finally:
            # ลบไฟล์ warmup
            import os
            try:
                os.unlink(warmup_file)
            except:
                pass
    except Exception as e:
        logger.warning(f"⚠️  Warmup failed: {e} (will continue without warmup)")

try:
    # Pre-init service (optional - จะ init เมื่อ job แรกมาถึงก็ได้)
    # แต่ถ้า pre-init จะทำให้ job แรกเร็วขึ้น
    if os.getenv('RQ_PRELOAD_MODEL', 'false').lower() == 'true':
        logger.info("🔧 Pre-loading model (RQ_PRELOAD_MODEL=true)...")
        get_transcription_service()
        logger.info("✅ Model pre-loaded")
        
        # Warmup model + GPU
        warmup_model()
    else:
        logger.info("ℹ️  Model will be loaded on first job (lazy loading)")
except Exception as e:
    logger.warning(f"⚠️  Failed to pre-load model: {e} (will load on first job)")

logger.info("✅ RQ Worker module loaded")

