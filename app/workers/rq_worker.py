"""
RQ Worker Module - Persistent Transcription Service
Init TranscriptionService ครั้งเดียวตอน import แทน init ทุก job
"""
import asyncio
import json
import logging
import os
from typing import Dict, Optional
from redis import Redis

logger = logging.getLogger(__name__)

# ============================================================================
# Persistent Services (Init ครั้งเดียวตอน worker start)
# ============================================================================

# Redis connection pool (reuse connections)
# FIX: ใช้ global thread-local แทนการสร้างใหม่ทุกครั้ง
import threading
_thread_local = threading.local()

def get_redis_connection(decode_responses=True):
    """Get or create persistent Redis connection (per worker process)"""
    # ใช้ thread-local storage เพื่อให้แต่ละ worker process มี connection ของตัวเอง
    # FIX: ใช้ global _thread_local แทนการสร้างใหม่ทุกครั้ง (ลด connection leak)
    if not hasattr(_thread_local, 'redis_conn'):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        # ใช้ connection pool เพื่อ reuse connections
        # FIX: ลด max_connections เหลือ 1-2 ต่อ process (RQ เป็น process-based)
        from redis.connection import ConnectionPool
        pool = ConnectionPool.from_url(
            redis_url,
            max_connections=2,  # ลดจาก 10 → 2 เพื่อลด RAM/FD
            decode_responses=decode_responses,
            health_check_interval=30
        )
        _thread_local.redis_conn = Redis(connection_pool=pool)
        logger.debug("✅ Redis connection initialized (per worker thread)")
    
    return _thread_local.redis_conn

# Init TranscriptionService ครั้งเดียว
# จะถูก init เมื่อ module ถูก import (ตอน worker start)
_transcription_service = None
_event_loop = None

def get_transcription_service():
    """Get or create persistent TranscriptionService instance"""
    global _transcription_service
    if _transcription_service is None:
        logger.info("🚀 Initializing persistent TranscriptionService (one-time init)...")
        # FIX: Log environment variables เพื่อตรวจสอบ GPU configuration
        cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES', 'not set')
        logger.info(f"🔍 ENV CUDA_VISIBLE_DEVICES={cuda_visible}")
        logger.info(f"🔍 ENV WHISPER_DEVICE={os.getenv('WHISPER_DEVICE', 'not set')}")
        logger.info(f"🔍 ENV NUM_GPUS={os.getenv('NUM_GPUS', 'not set')}")
        
        # ตรวจสอบ GPU ที่ใช้จริง
        try:
            import torch
            if torch.cuda.is_available():
                if cuda_visible != 'not set':
                    # CUDA_VISIBLE_DEVICES กำหนด GPU ที่เห็น
                    visible_gpu = int(cuda_visible) if cuda_visible.isdigit() else 0
                    logger.info(f"🔍 GPU Configuration: CUDA_VISIBLE_DEVICES={cuda_visible} → Worker sees GPU {visible_gpu}")
                    logger.info(f"🔍 torch.cuda.device_count()={torch.cuda.device_count()}")
                    if torch.cuda.device_count() > 0:
                        logger.info(f"🔍 torch.cuda.get_device_name(0)={torch.cuda.get_device_name(0)}")
                else:
                    logger.warning(f"⚠️  CUDA_VISIBLE_DEVICES not set - worker may use wrong GPU!")
        except ImportError:
            logger.debug("torch not available for GPU check")
        except Exception as e:
            logger.warning(f"⚠️  Cannot check GPU: {e}")
        from app.services.transcription_service import TranscriptionService
        _transcription_service = TranscriptionService()
        logger.info("✅ TranscriptionService initialized (will be reused for all jobs)")
        
        # FIX: Log provider device info หลัง init
        try:
            provider = _transcription_service.whisper_service.provider
            logger.info(f"🔍 Provider: {provider.provider_name}")
            if hasattr(provider, 'base_device'):
                logger.info(f"🔍 Provider base_device: {provider.base_device}")
            if hasattr(provider, 'compute_type'):
                logger.info(f"🔍 Provider compute_type: {provider.compute_type}")
        except Exception as e:
            logger.warning(f"⚠️  Cannot log provider info: {e}")
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
# Helper Functions for Webhook & Stage Reporting
# ============================================================================

async def _update_task_stage_and_webhook(
    task_id: str,
    progress: int,
    status: str,
    stage: str,
    stage_description: str,
    stage_progress: Optional[int] = None,
    json_storage=None
):
    """
    Helper function สำหรับอัปเดต stage และส่ง webhook progress
    
    Args:
        task_id: Task ID
        progress: Overall progress (0-100)
        status: Task status
        stage: Current stage (e.g., "extracting_audio", "transcribing", "merging")
        stage_description: Stage description in Thai
        stage_progress: Progress within current stage (0-100), optional
        json_storage: JSONStorage instance (will create if None) - สำหรับ backward compatibility
    """
    try:
        # FIX: ใช้ SQLiteStorage เป็นหลัก (ตาม STORAGE_TYPE)
        # Note: os is already imported at module level (line 8)
        from datetime import datetime, timezone
        
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        
        if storage_type == 'sqlite':
            # ใช้ SQLiteStorage
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
            
            # โหลด task data
            task_data = storage.load_transcription(task_id, skip_migration=True)
            if not task_data:
                task_data = {}
            
            # อัปเดต stage information
            task_data["progress"] = progress
            task_data["status"] = status
            task_data["current_stage"] = stage
            task_data["current_stage_description"] = stage_description
            if stage_progress is not None:
                task_data["stage_progress"] = stage_progress
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # บันทึก
            storage.save_transcription(task_id, task_data)
        else:
            # Fallback to JSONStorage
            if json_storage is None:
                from app.utils.json_storage import JSONStorage
                json_storage = JSONStorage()
            
            # โหลด task data
            task_dir = json_storage.storage_dir / "transcriptions" / task_id
            metadata_path = task_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
            else:
                task_data = {}
            
            # อัปเดต stage information
            task_data["progress"] = progress
            task_data["status"] = status
            task_data["current_stage"] = stage
            task_data["current_stage_description"] = stage_description
            if stage_progress is not None:
                task_data["stage_progress"] = stage_progress
            
            # บันทึก
            json_storage.save_transcription(task_id, task_data)
        
        # ส่ง webhook progress (ถ้ามี callback_url)
        callback_url = task_data.get("callback_url")
        if callback_url:
            try:
                from app.services.webhook_service import webhook_service
                await webhook_service.notify_transcription_progress(
                    task_id=task_id,
                    progress=progress,
                    status=status,
                    stage=stage
                )
            except Exception as e:
                logger.warning(f"⚠️  Failed to send webhook progress: {e}")
        
        # ส่ง WebSocket notification (real-time updates)
        # Rate limiting: ส่งเมื่อ progress เปลี่ยน >= 5% หรือ stage เปลี่ยน
        try:
            from app.services.websocket_service import websocket_manager
            
            # ตรวจสอบว่า progress เปลี่ยนพอหรือไม่ (rate limiting)
            last_progress_key = f"task:{task_id}:ws_last_progress"
            conn = get_redis_connection(decode_responses=True)
            last_progress_str = conn.get(last_progress_key)
            last_progress = int(last_progress_str) if last_progress_str else -1
            
            # ส่งเมื่อ progress เปลี่ยน >= 5% หรือ stage เปลี่ยน หรือเป็นสถานะใหม่
            progress_changed = abs(progress - last_progress) >= 5
            should_notify = progress_changed or (status in ["completed", "failed", "queued", "processing"] and progress == 0)
            
            if should_notify:
                await websocket_manager.notify_transcription_progress(
                    task_id=task_id,
                    progress=progress,
                    status=status,
                    stage=stage or stage_description
                )
                # เก็บ last progress สำหรับ rate limiting
                conn.setex(last_progress_key, 3600, str(progress))  # TTL 1 hour
        except Exception as e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว (non-critical)
            logger.debug(f"WebSocket notification failed (non-critical): {e}")
        
        logger.debug(f"📊 Task {task_id}: {stage} - Progress {progress}%")
        
    except Exception as e:
        logger.warning(f"⚠️  Error updating task stage: {e}")

def _update_task_stage_sync(
    task_id: str,
    progress: int,
    status: str,
    stage: str,
    stage_description: str,
    stage_progress: Optional[int] = None,
    json_storage=None
):
    """
    Synchronous version สำหรับใช้ใน sync context (rq worker)
    """
    try:
        loop = get_event_loop()
        loop.run_until_complete(
            _update_task_stage_and_webhook(
                task_id, progress, status, stage, stage_description, stage_progress, json_storage
            )
        )
    except Exception as e:
        logger.warning(f"⚠️  Error in sync stage update: {e}")

async def _send_completion_callback(task_id: str, status: str = "completed", error_message: Optional[str] = None):
    """
    ส่ง callback (webhook) และ WebSocket notification เมื่อ transcription เสร็จหรือล้มเหลว
    
    Args:
        task_id: Task ID
        status: "completed" or "failed"
        error_message: Error message (if failed)
    
    Note:
        - WebSocket notification ถูกส่งเสมอ (ไม่ต้องรอ callback_url)
        - Webhook callback ถูกส่งเฉพาะเมื่อมี callback_url
    """
    try:
        from datetime import datetime, timezone
        # os already imported at module level (line 8)
        
        # ใช้ storage ที่ถูกต้องตาม STORAGE_TYPE
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        
        if storage_type == 'sqlite':
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
            task_data = storage.load_transcription(task_id, skip_migration=True)
        else:
            from app.utils.json_storage import JSONStorage
            json_storage = JSONStorage()
            task_data = json_storage.load_transcription(task_id)
        
        if not task_data:
            logger.warning(f"⚠️  Task data not found for {task_id}")
            return
        
        # ส่ง WebSocket notification เสมอ (ไม่ต้องรอ callback_url)
        try:
            from app.services.websocket_service import websocket_manager
            
            if status == "completed":
                results = {
                    "text": task_data.get("full_text", "") or task_data.get("text", ""),
                    "chunks": task_data.get("chunks", []) or task_data.get("segments", []),
                    "duration": task_data.get("total_duration", 0),
                    "language": task_data.get("language", "th"),
                    "processing_time": task_data.get("processing_time", 0)
                }
                await websocket_manager.notify_transcription_completed(task_id, results)
                logger.debug(f"📡 WebSocket: Sent completed notification for {task_id}")
            elif status == "failed":
                await websocket_manager.notify_transcription_failed(task_id, error_message or "Unknown error")
                logger.debug(f"📡 WebSocket: Sent failed notification for {task_id}")
        except Exception as ws_e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว (non-critical)
            logger.debug(f"WebSocket notification failed (non-critical): {ws_e}")
        
        # ส่ง webhook callback (เฉพาะเมื่อมี callback_url)
        callback_url = task_data.get("callback_url")
        if callback_url:
            try:
                from app.models.transcription import TranscriptionResponse
                from app.services.transcription_service import TranscriptionService
                
                # สร้าง TranscriptionResponse object สำหรับ _send_callback
                task = TranscriptionResponse(
                    task_id=task_id,
                    status=status,
                    file_path=task_data.get("file_path"),
                    language=task_data.get("language", "th"),
                    model_size=task_data.get("model_size", "base"),
                    created_at=datetime.fromisoformat(task_data.get("created_at", datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00')),
                    callback_url=callback_url,
                    progress=task_data.get("progress", 100 if status == "completed" else 0),
                    full_text=task_data.get("full_text", "") or task_data.get("text", ""),
                    total_duration=task_data.get("total_duration", 0)
                )
                
                if status == "completed":
                    completed_at = task_data.get("completed_at")
                    if completed_at:
                        task.completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                else:
                    task.error_message = error_message
                
                # ใช้ _send_callback จาก TranscriptionService
                transcription_service = TranscriptionService()
                await transcription_service._send_callback(task, status)
                logger.debug(f"📡 Webhook: Sent {status} callback for {task_id}")
            except Exception as webhook_e:
                logger.warning(f"⚠️  Failed to send webhook callback: {webhook_e}")
        
    except Exception as e:
        logger.warning(f"⚠️  Failed to send completion callback: {e}")

# ============================================================================
# Worker Functions
# ============================================================================

def process_transcription_job(
    task_id: str,
    file_path: str,
    language: str,
    model_size: str,
    chunk_duration: int = 150
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
            # FIX: เพิ่ม timing metrics สำหรับ chunk transcription
            import time
            from datetime import datetime, timezone
            t_chunk_transcribe_start = time.time()
            logger.info(f"📦 Processing single chunk (chunk job)")
            # ใช้ provider.transcribe() (async) แทน transcribe() ที่ไม่มี
            transcription_result = loop.run_until_complete(
                transcription_service.whisper_service.provider.transcribe(
                    audio_path=file_path,
                    language=language,
                    model_size=model_size
                )
            )
            t_chunk_transcribe_end = time.time()
            chunk_transcribe_time = t_chunk_transcribe_end - t_chunk_transcribe_start
            logger.info(f"✅ Chunk transcription completed (took {chunk_transcribe_time:.2f}s)")
            
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
            # TTL 12 hours (43200 seconds) - เพียงพอสำหรับ aggregator และลด memory usage
            ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))  # Default: 12 hours
            chunk_index = int(task_id.rsplit("_chunk_", 1)[1])
            chunk_result_key = f"task:{main_task_id}:chunk:{chunk_index}"
            conn.setex(
                chunk_result_key,
                ttl_seconds,
                json.dumps(result)
            )
            
            # Atomic increment done_chunks counter
            done_key = f"task:{main_task_id}:done_chunks"
            done_count = conn.incr(done_key)
            conn.expire(done_key, ttl_seconds)
            
            # ตรวจสอบว่าทุก chunks เสร็จแล้วหรือยัง
            total_key = f"task:{main_task_id}:total_chunks"
            total_chunks = conn.get(total_key)
            if total_chunks:
                total_chunks = int(total_chunks)
                
                # อัปเดต progress (40% base + 50% for chunks = 40-90%)
                chunk_progress = int((done_count / total_chunks) * 50) + 40
                chunk_progress = min(chunk_progress, 90)  # ไม่เกิน 90% (เหลือ 10% สำหรับ aggregator)
                
                # ส่ง WebSocket notification สำหรับ chunk completed (optional, granular update)
                # Rate limiting: ส่งทุก 3 chunks หรือเมื่อ chunks เสร็จหมด
                try:
                    from app.services.websocket_service import websocket_manager
                    if done_count % 3 == 0 or done_count >= total_chunks:
                        loop = get_event_loop()
                        loop.run_until_complete(
                            websocket_manager.broadcast_task_update(main_task_id, {
                                "type": "transcription.chunk_completed",
                                "chunk_index": chunk_index,
                                "total_chunks": total_chunks,
                                "done_chunks": done_count,
                                "progress": chunk_progress,
                                "status": "processing",
                                "stage": "transcribing"
                            })
                        )
                except Exception as e:
                    logger.debug(f"WebSocket chunk notification failed (non-critical): {e}")
                
                if done_count >= total_chunks:
                    # ทุก chunks เสร็จแล้ว - trigger aggregator (ถ้ายังไม่ถูก trigger)
                    aggregator_trigger_key = f"task:{main_task_id}:aggregator_triggered"
                    if not conn.exists(aggregator_trigger_key):
                        # TTL 12 hours (43200 seconds) - เพียงพอสำหรับ aggregator
                        ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))  # Default: 12 hours
                        conn.setex(aggregator_trigger_key, ttl_seconds, "1")
                        logger.info(f"✅ All {total_chunks} chunks completed for {main_task_id}, aggregator will process")
            
            logger.info(f"✅ Chunk {chunk_index} completed ({done_count}/{total_chunks if total_chunks else '?'} done)")
        elif is_aggregator_job:
            # Aggregator job: ใช้ Redis atomic counter (ไม่ polling)
            # FIX: เพิ่ม timing metrics สำหรับ aggregator
            import time
            from datetime import datetime, timezone
            phase_timings = {}
            t_aggregator_start = time.time()
            phase_timings['t_aggregator_start'] = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"📊 Processing aggregator job (using Redis atomic counter)")
            
            # FIX: สร้าง json_storage ก่อนใช้งาน
            from app.utils.json_storage import JSONStorage
            json_storage = JSONStorage()
            
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
                    chunk_duration = chunk_metadata.get("chunk_duration", 150)
                else:
                    raise ValueError(f"Chunk data not found for {main_task_id}")
            else:
                total_chunks = int(total_chunks)
                # ดึง chunk_duration จาก chunk_jobs metadata
                chunk_data_key = f"task:{main_task_id}:chunk_jobs"
                chunk_data_str = conn.get(chunk_data_key)
                if chunk_data_str:
                    chunk_metadata = json.loads(chunk_data_str)
                    chunk_duration = chunk_metadata.get("chunk_duration", 150)
                else:
                    chunk_duration = 150
            
            logger.info(f"📊 Waiting for {total_chunks} chunks to complete (using atomic counter)...")
            
            # อัปเดต stage: transcribing
            _update_task_stage_sync(
                task_id=main_task_id,
                progress=40,
                status="processing",
                stage="transcribing",
                stage_description=f"กำลังแปลงเสียงเป็นข้อความ (0/{total_chunks} ส่วนเสร็จ)",
                stage_progress=0,
                json_storage=json_storage
            )
            
            # รอ chunks เสร็จด้วย atomic counter (ไม่ polling jobs)
            start_wait_time = time.time()
            max_wait_time = 3600  # 1 hour
            wait_interval = 0.5  # เริ่มต้น 0.5s
            last_progress_update = 0
            
            while True:
                done_key = f"task:{main_task_id}:done_chunks"
                done_count = conn.get(done_key)
                done_count = int(done_count) if done_count else 0
                
                # อัปเดต progress ทุก 5% หรือทุก 5 วินาที
                current_progress = int((done_count / total_chunks) * 50) + 40  # 40-90%
                if current_progress != last_progress_update or (time.time() - start_wait_time) % 5 < wait_interval:
                    _update_task_stage_sync(
                        task_id=main_task_id,
                        progress=current_progress,
                        status="processing",
                        stage="transcribing",
                        stage_description=f"กำลังแปลงเสียงเป็นข้อความ ({done_count}/{total_chunks} ส่วนเสร็จ)",
                        stage_progress=int((done_count / total_chunks) * 100),
                        json_storage=json_storage
                    )
                    last_progress_update = current_progress
                
                if done_count >= total_chunks:
                    t_wait_end = time.time()
                    phase_timings['t_wait_chunks_end'] = datetime.now(timezone.utc).isoformat()
                    phase_timings['wait_chunks_time'] = t_wait_end - start_wait_time
                    logger.info(f"✅ All {total_chunks} chunks completed (done: {done_count}, waited {phase_timings['wait_chunks_time']:.2f}s)")
                    break
                
                if time.time() - start_wait_time > max_wait_time:
                    logger.error(f"⏰ Timeout waiting for chunks (done: {done_count}/{total_chunks})")
                    break
                
                logger.debug(f"⏳ Waiting... ({done_count}/{total_chunks} done)")
                time.sleep(wait_interval)
                if wait_interval < 2.0:
                    wait_interval = min(wait_interval * 1.2, 2.0)
            
            # อัปเดต stage: merging
            _update_task_stage_sync(
                task_id=main_task_id,
                progress=90,
                status="processing",
                stage="merging",
                stage_description="กำลังรวมผลลัพธ์",
                stage_progress=0,
                json_storage=json_storage
            )
            
            # FIX: Streaming Merge to SQLite - ไม่เก็บ segments ใน memory
            # หลักการ: Process ทีละ chunk → stream segments ลง SQLite → ลบ chunk data ทันที
            t_fetch_start = time.time()
            
            # Initialize accumulator (เก็บแค่ text, ไม่เก็บ segments)
            merged_text_parts = []
            total_duration = total_chunks * chunk_duration
            last_segment_end = 0.0
            
            # Setup SQLite connection for streaming segments
            import sqlite3
            from pathlib import Path
            from app.utils.sqlite_schema import ensure_sqlite_schema
            # os already imported at top level
            
            # Check if using SQLite storage
            storage_type = os.getenv('STORAGE_TYPE', 'json').lower()
            if storage_type == 'sqlite':
                db_path = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
                # Use centralized schema initialization
                sqlite_conn = ensure_sqlite_schema(db_path)
                
                # Prepare bulk insert statement
                insert_stmt = """
                    INSERT INTO segments (task_id, idx, start_time, end_time, text, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                segments_batch = []
                batch_size = 100  # Insert in batches
            else:
                sqlite_conn = None
                segments_batch = None
            
            # Process chunks ทีละตัว (sorted by index)
            processed_count = 0
            for i in range(total_chunks):
                chunk_result_key = f"task:{main_task_id}:chunk:{i}"
                chunk_result_str = conn.get(chunk_result_key)
                
                # Prepare chunk data (minimal structure)
                if chunk_result_str:
                    chunk_result = json.loads(chunk_result_str)
                    start_offset = i * chunk_duration
                    
                    # Collect text
                    chunk_text = (chunk_result.get('text') or '').strip()
                    if chunk_text:
                        merged_text_parts.append(chunk_text)
                    
                    # Stream segments to SQLite (don't store in memory)
                    segments = chunk_result.get('segments', [])
                    if segments and sqlite_conn:
                        for seg_idx, seg in enumerate(segments):
                            if not isinstance(seg, dict):
                                continue
                            
                            # Adjust timestamps - convert to float if string format (e.g., "00:02:30,016")
                            start_val = seg.get("start", 0) or 0
                            end_val = seg.get("end", 0) or 0
                            
                            # Convert string timestamps to float if needed
                            if isinstance(start_val, str):
                                # Parse format like "00:02:30,016" or "00:02:30.016"
                                try:
                                    parts = start_val.replace(',', '.').split(':')
                                    if len(parts) == 3:
                                        start_val = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                                    else:
                                        start_val = float(start_val)
                                except:
                                    start_val = 0.0
                            else:
                                start_val = float(start_val) if start_val else 0.0
                            
                            if isinstance(end_val, str):
                                try:
                                    parts = end_val.replace(',', '.').split(':')
                                    if len(parts) == 3:
                                        end_val = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                                    else:
                                        end_val = float(end_val)
                                except:
                                    end_val = 0.0
                            else:
                                end_val = float(end_val) if end_val else 0.0
                            
                            start_time = start_val + start_offset
                            end_time = end_val + start_offset
                            seg_text = (seg.get("text") or "").strip()
                            confidence = seg.get("confidence")
                            
                            if seg_text:  # Only store non-empty segments
                                segments_batch.append((
                                    main_task_id,
                                    processed_count * 1000 + seg_idx,  # Global index
                                    start_time,
                                    end_time,
                                    seg_text,
                                    confidence
                                ))
                                last_segment_end = max(last_segment_end, end_time)
                                
                                # Bulk insert every batch_size segments
                                if len(segments_batch) >= batch_size:
                                    sqlite_conn.executemany(insert_stmt, segments_batch)
                                    sqlite_conn.commit()
                                    segments_batch.clear()
                    
                    # Clear chunk_result immediately (don't keep in memory)
                    del chunk_result
                    del segments
                else:
                    # Chunk ไม่พบ (อาจล้มเหลว)
                    logger.warning(f"⚠️  Chunk {i} not found in Redis")
                
                processed_count += 1
                
                # Periodic GC every 5 chunks to prevent accumulation
                if processed_count % 5 == 0:
                    import gc
                    gc.collect()
            
            # Final bulk insert for remaining segments
            if sqlite_conn and segments_batch:
                sqlite_conn.executemany(insert_stmt, segments_batch)
                sqlite_conn.commit()
                segments_batch.clear()
                sqlite_conn.close()
                logger.info(f"✅ Streamed segments to SQLite for {main_task_id}")
            
            t_fetch_end = time.time()
            phase_timings['t_fetch_chunks_end'] = datetime.now(timezone.utc).isoformat()
            phase_timings['fetch_chunks_time'] = t_fetch_end - t_fetch_start
            
            # Final merge processing (cleanup text, calculate total_duration)
            t_merge_start = time.time()
            logger.info(f"✅ Processed {processed_count}/{total_chunks} chunks incrementally (took {phase_timings['fetch_chunks_time']:.2f}s), finalizing merge...")
            
            # Build merged result (text only, no segments in memory)
            full_text = " ".join(merged_text_parts).strip()
            del merged_text_parts
            import gc
            gc.collect()
            
            merged_result = {
                "text": full_text,
                "total_duration": last_segment_end if last_segment_end > 0 else total_duration,
                "language": language
            }
            
            # Apply Thai processor
            if language == "th":
                t_thai_start = time.time()
                logger.info(f"🇹🇭 Applying Thai processor...")
                merged_result = transcription_service.whisper_service._apply_thai_processing(merged_result)
                t_thai_end = time.time()
                phase_timings['thai_processing_time'] = t_thai_end - t_thai_start
                logger.info(f"✅ Thai processing completed (took {phase_timings['thai_processing_time']:.2f}s)")
            
            t_merge_end = time.time()
            phase_timings['t_merge_end'] = datetime.now(timezone.utc).isoformat()
            phase_timings['merge_time'] = t_merge_end - t_merge_start
            
            # อัปเดต main task จาก storage (รองรับทั้ง SQLite และ JSON)
            # Note: os is already imported at module level (line 8)
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            
            if storage_type == 'sqlite':
                from app.utils.sqlite_storage import SQLiteStorage
                storage = SQLiteStorage()
                task_data = storage.load_transcription(main_task_id, skip_migration=True)
                if not task_data:
                    task_data = {}
            else:
                from app.utils.json_storage import JSONStorage
                json_storage = JSONStorage()
                task_dir = json_storage.storage_dir / "transcriptions" / main_task_id
                metadata_path = task_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                else:
                    task_data = {}
            
            # FIX: บันทึก phase timings และคำนวณ total time
            t_aggregator_end = time.time()
            phase_timings['t_aggregator_end'] = datetime.now(timezone.utc).isoformat()
            phase_timings['total_aggregator_time'] = t_aggregator_end - t_aggregator_start
            
            # รวม phase timings จาก preprocess (ถ้ามี)
            if 'phase_timings' in task_data:
                preprocess_timings = task_data['phase_timings']
                # คำนวณ total time จาก start ถึง aggregator end
                if 't_start' in preprocess_timings:
                    try:
                        t_start_dt = datetime.fromisoformat(preprocess_timings['t_start'].replace('Z', '+00:00'))
                        t_end_dt = datetime.fromisoformat(phase_timings['t_aggregator_end'].replace('Z', '+00:00'))
                        total_time = (t_end_dt - t_start_dt).total_seconds()
                        phase_timings['total_end_to_end_time'] = total_time
                    except:
                        pass
            
            # อัปเดต stage: finalizing
            _update_task_stage_sync(
                task_id=main_task_id,
                progress=95,
                status="processing",
                stage="finalizing",
                stage_description="กำลังจัดเก็บข้อมูล",
                stage_progress=100,
                json_storage=None  # จะใช้ storage ที่ถูกต้องภายใน function
            )
            
            # อัปเดต task data
            task_data["status"] = "completed"
            task_data["progress"] = 100
            task_data["full_text"] = merged_result.get("text", "")
            task_data["total_duration"] = merged_result.get("total_duration", 0)
            task_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            task_data["current_stage"] = "completed"
            task_data["current_stage_description"] = "เสร็จสิ้น"
            task_data["stage_progress"] = 100
            
            # FIX: ไม่เก็บ segments ใน task_data (เก็บใน SQLite แล้ว)
            # ถ้าใช้ SQLite: segments อยู่ใน segments table แล้ว
            # ถ้าใช้ JSON: ยังต้องเก็บ chunks (backward compatibility)
            if storage_type != 'sqlite':
                # Fallback: ถ้ายังใช้ JSON storage ต้องเก็บ chunks (แต่ไม่ควรใช้)
                logger.warning(f"⚠️  Using JSON storage - segments not stored in SQLite")
            
            # บันทึก aggregator phase timings
            if 'phase_timings' not in task_data:
                task_data['phase_timings'] = {}
            task_data['phase_timings']['aggregator'] = phase_timings
            
            # บันทึกกลับไป storage (ใช้ storage ที่ถูกต้องตาม STORAGE_TYPE)
            if storage_type == 'sqlite':
                storage.save_transcription(main_task_id, task_data)
            else:
                json_storage.save_transcription(main_task_id, task_data)
            
            # ส่ง completion callback (webhook + WebSocket)
            # _send_completion_callback จะส่งทั้ง WebSocket notification และ webhook callback
            loop = get_event_loop()
            loop.run_until_complete(_send_completion_callback(main_task_id, "completed"))
            
            # FIX: ลบ merged_result หลังบันทึกแล้ว เพื่อลด memory
            # (ไม่ต้องลบ segments เพราะไม่ได้เก็บใน memory แล้ว)
            del merged_result
            import gc
            gc.collect()  # Force garbage collection
            logger.info(f"✅ Main task {main_task_id} updated in storage")
            logger.info(f"📊 Aggregator Phase Timings:")
            logger.info(f"   Wait chunks: {phase_timings.get('wait_chunks_time', 0):.2f}s")
            logger.info(f"   Fetch chunks: {phase_timings.get('fetch_chunks_time', 0):.2f}s")
            logger.info(f"   Merge: {phase_timings.get('merge_time', 0):.2f}s")
            if 'thai_processing_time' in phase_timings:
                logger.info(f"   Thai processing: {phase_timings['thai_processing_time']:.2f}s")
            logger.info(f"   Total aggregator: {phase_timings['total_aggregator_time']:.2f}s")
            if 'total_end_to_end_time' in phase_timings:
                logger.info(f"   Total end-to-end: {phase_timings['total_end_to_end_time']:.2f}s ({phase_timings['total_end_to_end_time']/60:.2f} minutes)")
            
            # Cleanup Redis keys หลัง aggregator เสร็จ (ลด memory usage)
            logger.info(f"🧹 Cleaning up Redis keys for {main_task_id}...")
            try:
                # ลบ chunk result keys
                for i in range(total_chunks):
                    chunk_result_key = f"task:{main_task_id}:chunk:{i}"
                    conn.delete(chunk_result_key)
                
                # ลบ counter keys
                conn.delete(f"task:{main_task_id}:done_chunks")
                conn.delete(f"task:{main_task_id}:total_chunks")
                conn.delete(f"task:{main_task_id}:chunk_jobs")
                conn.delete(f"task:{main_task_id}:aggregator_triggered")
                
                logger.info(f"✅ Cleaned up Redis keys for {main_task_id}")
            except Exception as e:
                logger.warning(f"⚠️  Error cleaning up Redis keys: {e}")
            
            # Cleanup files หลัง aggregator เสร็จ (ไม่จำเป็นต้องเก็บไฟล์ original หรือ chunk wav)
            logger.info(f"🧹 Cleaning up files for {main_task_id}...")
            try:
                import shutil
                from pathlib import Path
                
                # 1. ลบ chunk wav files
                chunk_dir = Path("temp/chunks") / main_task_id
                if chunk_dir.exists():
                    shutil.rmtree(chunk_dir)
                    logger.info(f"✅ Deleted chunk directory: {chunk_dir}")
                
                # 2. ลบ extracted audio file
                # ตรวจสอบทั้ง temp/audio_{task_id}.wav และ uploads/audio_{task_id}.wav
                audio_paths = [
                    Path("temp") / f"audio_{main_task_id}.wav",
                    Path("uploads") / f"audio_{main_task_id}.wav"
                ]
                for audio_path in audio_paths:
                    if audio_path.exists():
                        audio_path.unlink()
                        logger.info(f"✅ Deleted audio file: {audio_path}")
                
                # 3. ลบ original video file (ถ้า download จาก URL)
                # ตรวจสอบไฟล์ใน uploads ที่มี task_id ในชื่อ
                uploads_dir = Path("uploads")
                if uploads_dir.exists():
                    task_files = list(uploads_dir.glob(f"*{main_task_id}*"))
                    for task_file in task_files:
                        # ไม่ลบ metadata.json หรือไฟล์อื่นที่ไม่ใช่ media files
                        if task_file.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.wav', '.mp3']:
                            task_file.unlink()
                            logger.info(f"✅ Deleted original file: {task_file}")
                
                logger.info(f"✅ Cleaned up files for {main_task_id}")
            except Exception as e:
                logger.warning(f"⚠️  Error cleaning up files: {e}")
            
            # Return summary (ไม่ return segments เพราะเก็บใน SQLite แล้ว)
            result = {
                "status": "completed",
                "task_id": main_task_id,
                "text": task_data.get("full_text", ""),
                "total_duration": task_data.get("total_duration", 0),
                "segments_stored_in": "sqlite" if storage_type == 'sqlite' else "json"
            }
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
        
        # บันทึก error status และส่ง WebSocket notification
        try:
            from datetime import datetime, timezone
            # os already imported at module level (line 8)
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            
            if storage_type == 'sqlite':
                from app.utils.sqlite_storage import SQLiteStorage
                storage = SQLiteStorage()
                task_data = storage.load_transcription(task_id, skip_migration=True) or {}
                task_data["status"] = "failed"
                task_data["error_message"] = str(e)
                task_data["current_stage"] = "failed"
                task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
                task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                storage.save_transcription(task_id, task_data)
            else:
                from app.utils.json_storage import JSONStorage
                json_storage = JSONStorage()
                task_data = json_storage.load_transcription(task_id) or {}
                task_data["status"] = "failed"
                task_data["error_message"] = str(e)
                task_data["current_stage"] = "failed"
                task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
                json_storage.save_transcription(task_id, task_data)
            
            # ส่ง failure callback (webhook + WebSocket)
            loop = get_event_loop()
            loop.run_until_complete(_send_completion_callback(task_id, "failed", str(e)))
        except Exception as save_error:
            logger.error(f"❌ Failed to save error status: {save_error}")
        
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
    chunk_duration: int = 150
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
    
    # FIX: เพิ่ม phase-based timing metrics
    import time
    from datetime import datetime, timezone
    phase_timings = {}
    t_start = time.time()
    phase_timings['t_start'] = datetime.now(timezone.utc).isoformat()
    
    try:
        from app.services.video_service import VideoService
        from app.services.redis_queue_service import get_redis_queue_service
        from app.utils.json_storage import JSONStorage
        # os already imported at top level
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
        
        # FIX: บันทึก file_path, file_name, language, model_size ลง task_data
        task_data["file_path"] = file_path
        task_data["file_name"] = os.path.basename(file_path) if file_path else None
        task_data["language"] = language
        task_data["model_size"] = model_size
        task_data["chunk_duration"] = chunk_duration
        
        # อัปเดต stage: preprocessing
        _update_task_stage_sync(
            task_id=task_id,
            progress=10,
            status="processing",
            stage="preprocessing",
            stage_description="กำลังเตรียมไฟล์และแยกเสียง",
            stage_progress=0,
            json_storage=json_storage
        )
        
        # 1. Extract audio
        t_extract_start = time.time()
        logger.info(f"🎵 Extracting audio from {file_path}...")
        _update_task_stage_sync(
            task_id=task_id,
            progress=15,
            status="processing",
            stage="extracting_audio",
            stage_description="กำลังแยกเสียงจากวิดีโอ",
            stage_progress=0,
            json_storage=json_storage
        )
        audio_path = video_service.extract_audio(file_path, task_id=task_id)
        t_extract_end = time.time()
        phase_timings['t_extract_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['extract_time'] = t_extract_end - t_extract_start
        logger.info(f"✅ Audio extracted: {audio_path} (took {phase_timings['extract_time']:.2f}s)")
        
        # 2. Create chunks
        t_chunk_start = time.time()
        logger.info(f"📦 Creating chunks from {audio_path}...")
        _update_task_stage_sync(
            task_id=task_id,
            progress=25,
            status="processing",
            stage="chunking",
            stage_description="กำลังแบ่งไฟล์เป็นส่วนๆ",
            stage_progress=0,
            json_storage=json_storage
        )
        chunks = video_service.create_chunks(audio_path, chunk_duration, task_id=task_id)
        total_chunks = len(chunks)
        t_chunk_end = time.time()
        phase_timings['t_chunk_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['chunk_time'] = t_chunk_end - t_chunk_start
        logger.info(f"✅ Created {total_chunks} chunks (took {phase_timings['chunk_time']:.2f}s)")
        
        # อัปเดต stage: enqueueing
        _update_task_stage_sync(
            task_id=task_id,
            progress=30,
            status="processing",
            stage="enqueueing",
            stage_description=f"กำลังส่ง {total_chunks} ส่วนไปประมวลผล",
            stage_progress=0,
            json_storage=json_storage
        )
        
        # 3. Enqueue chunk jobs ไปยัง GPU queues (Fan-out)
        t_enqueue_start = time.time()
        logger.info(f"📝 Enqueueing {total_chunks} chunks to GPU queues...")
        # FIX: ห้าม auto-detect - ใช้ NUM_GPUS อย่างเดียวเพื่อป้องกัน queue mismatch
        num_gpus = int(os.getenv('NUM_GPUS', '0'))
        if num_gpus <= 0:
            error_msg = "NUM_GPUS is not set or invalid. Please set NUM_GPUS environment variable."
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        logger.info(f"📊 Using {num_gpus} GPUs from NUM_GPUS environment variable")
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
        
        t_enqueue_end = time.time()
        phase_timings['t_enqueue_chunks_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['enqueue_time'] = t_enqueue_end - t_enqueue_start
        logger.info(f"✅ Enqueued {len(chunk_data)} chunks to GPU queues (took {phase_timings['enqueue_time']:.2f}s)")
        
        # 4. Enqueue aggregator job
        t_aggregator_enqueue_start = time.time()
        aggregator_task_id = f"{task_id}_aggregator"
        aggregator_job_id = queue_service.enqueue_aggregator(
            task_id=aggregator_task_id,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration
        )
        t_aggregator_enqueue_end = time.time()
        phase_timings['t_aggregator_enqueued'] = datetime.now(timezone.utc).isoformat()
        phase_timings['aggregator_enqueue_time'] = t_aggregator_enqueue_end - t_aggregator_enqueue_start
        
        # เก็บ chunk metadata ไว้ใน Redis
        # TTL 12 hours (43200 seconds) - เพียงพอสำหรับ aggregator และลด memory usage
        # สำหรับ use-case 50 งาน/วัน ไม่ต้องเก็บนาน 24h
        conn = get_redis_connection(decode_responses=True)
        ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))  # Default: 12 hours
        conn.setex(
            f"task:{task_id}:chunk_jobs",
            ttl_seconds,
            json.dumps({
                "chunk_duration": chunk_duration,
                "total_chunks": total_chunks,
                "chunks": chunk_data
            })
        )
        
        # ตั้งค่า Redis atomic counters สำหรับ aggregator
        conn.setex(f"task:{task_id}:total_chunks", ttl_seconds, str(total_chunks))
        conn.setex(f"task:{task_id}:done_chunks", ttl_seconds, "0")  # เริ่มต้นที่ 0
        
        t_end = time.time()
        phase_timings['t_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['total_preprocess_time'] = t_end - t_start
        
        # บันทึก phase timings ลง task_data
        task_data['phase_timings'] = phase_timings
        
        # ใช้ storage ที่ถูกต้องตาม STORAGE_TYPE
        storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
        if storage_type == 'sqlite':
            from app.utils.sqlite_storage import SQLiteStorage
            storage = SQLiteStorage()
            storage.save_transcription(task_id, task_data)
        else:
            json_storage.save_transcription(task_id, task_data)
        
        logger.info(f"✅ Aggregator job enqueued: {aggregator_job_id}")
        logger.info(f"✅ Preprocess job {task_id} completed")
        
        # ส่ง WebSocket notification สำหรับ task started (หลังจาก preprocess เสร็จ)
        try:
            from app.services.websocket_service import websocket_manager
            loop = get_event_loop()
            loop.run_until_complete(
                websocket_manager.notify_transcription_started(
                    task_id=task_id,
                    file_path=file_path,
                    language=language
                )
            )
            logger.debug(f"📡 WebSocket: Sent started notification for {task_id}")
        except Exception as e:
            logger.debug(f"WebSocket started notification failed (non-critical): {e}")
        logger.info(f"📊 Phase Timings:")
        logger.info(f"   Extract: {phase_timings['extract_time']:.2f}s")
        logger.info(f"   Chunk: {phase_timings['chunk_time']:.2f}s")
        logger.info(f"   Enqueue: {phase_timings['enqueue_time']:.2f}s")
        logger.info(f"   Total preprocess: {phase_timings['total_preprocess_time']:.2f}s")
        
        return {
            "task_id": task_id,
            "total_chunks": total_chunks,
            "chunk_data": chunk_data,
            "phase_timings": phase_timings
        }
        
    except Exception as e:
        logger.error(f"❌ RQ Worker: Error in preprocess job {task_id}: {e}", exc_info=True)
        # อัปเดต task status เป็น failed
        try:
            # ใช้ storage ที่ถูกต้องตาม STORAGE_TYPE
            storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if storage_type == 'sqlite':
                from app.utils.sqlite_storage import SQLiteStorage
                from datetime import datetime, timezone
                storage = SQLiteStorage()
                task_data = storage.load_transcription(task_id, skip_migration=True) or {}
                task_data["status"] = "failed"
                task_data["error_message"] = str(e)
                task_data["current_stage"] = "failed"
                task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
                task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                storage.save_transcription(task_id, task_data)
            else:
                from app.utils.json_storage import JSONStorage
                json_storage = JSONStorage()
                task_data = {}
                task_data["status"] = "failed"
                task_data["error_message"] = str(e)
                task_data["current_stage"] = "failed"
                task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
                json_storage.save_transcription(task_id, task_data)
            
            # ส่ง failure callback (webhook + WebSocket)
            # _send_completion_callback จะส่งทั้ง WebSocket notification และ webhook callback
            loop = get_event_loop()
            loop.run_until_complete(_send_completion_callback(task_id, "failed", str(e)))
        except Exception as save_error:
            logger.error(f"❌ Failed to save error status: {save_error}")
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
            # os already imported at top level
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

