"""
RQ Worker Module - Persistent Transcription Service
Init TranscriptionService ครั้งเดียวตอน import แทน init ทุก job
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timezone
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

async def send_ws_event_via_http(task_id: str = None, meeting_id: str = None, message: dict = None):
    """
    Send WebSocket event via HTTP callback to Main API
    
    Args:
        task_id: Task ID (for transcription tasks)
        meeting_id: Meeting ID (for live-chunk events)
        message: Message payload
    """
    if not task_id and not meeting_id:
        logger.warning("⚠️  send_ws_event_via_http: missing task_id or meeting_id")
        return
    
    if not message:
        logger.warning("⚠️  send_ws_event_via_http: missing message")
        return
    
    try:
        import aiohttp
        from datetime import datetime
        
        MAIN_API_URL = os.getenv('MAIN_API_URL', 'http://localhost:8010')
        
        payload = {
            "message": message
        }
        if task_id:
            payload["task_id"] = task_id
        if meeting_id:
            payload["meeting_id"] = meeting_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MAIN_API_URL}/api/internal/ws-event",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ WS event sent via HTTP: {task_id or meeting_id}")
                else:
                    response_text = await response.text()
                    logger.warning(f"⚠️  WS event failed: {response.status} - {response_text}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to send WS event via HTTP: {e}", exc_info=True)

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
        json_storage: deprecated, ignored — ใช้ storage factory แทน
    """
    try:
        from datetime import datetime, timezone
        from app.utils.storage_factory import get_storage

        storage = get_storage()

        # โหลด task data
        task_data = storage.load_transcription(task_id)
        if not task_data:
            task_data = {}

        # Completed/Failed status guard - ห้าม overwrite status ที่เสร็จแล้วด้วย processing
        existing_status = task_data.get("status", "")
        if existing_status in ("completed", "failed", "cancelled") and status in ("processing", "queued", "pending", "on_hold"):
            logger.debug(f"⏭️ Skip stage update for {task_id}: existing status={existing_status} (final), new={status}")
            return

        # Monotonic progress guard - ห้าม progress ย้อนกลับ (ยกเว้น failed หรือ task ใหม่)
        old_progress = task_data.get("progress", 0)
        if progress < old_progress and status not in ["failed", "cancelled", "stopped"]:
            logger.warning(f"⚠️  Progress would decrease from {old_progress}% to {progress}% for {task_id}, keeping {old_progress}%")
            progress = old_progress

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
                logger.info(f"📡 WebSocket: Sending progress update for {task_id}: {progress}% - {stage or stage_description} ({status})")
                await websocket_manager.notify_transcription_progress(
                    task_id=task_id,
                    progress=progress,
                    status=status,
                    stage=stage or stage_description
                )
                # เก็บ last progress สำหรับ rate limiting
                conn.setex(last_progress_key, 3600, str(progress))  # TTL 1 hour
                logger.info(f"✅ WebSocket: Progress update sent for {task_id}")
            else:
                logger.debug(f"⏭️  WebSocket: Skipping progress update for {task_id} (rate limited: {progress}% vs {last_progress}%)")
        except Exception as e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว (non-critical)
            logger.warning(f"⚠️  WebSocket notification failed (non-critical): {e}")
        
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


def _do_claim_and_enqueue_next_chunk(
    conn, main_task_id: str, chunks_metadata_key: str, inflight_key: str,
    enqueued_guard_prefix: str, inflight_limit: int, ttl_seconds: int
) -> bool:
    """Claim next chunk index และ enqueue — ใช้ทั้งจาก chunk completion และ Resume/On Hold release"""
    try:
        from app.workers.lua_scripts import CLAIM_NEXT_CHUNK_INDEX_SCRIPT
        claim_script = conn.register_script(CLAIM_NEXT_CHUNK_INDEX_SCRIPT)
        result = claim_script(
            keys=[chunks_metadata_key, inflight_key, enqueued_guard_prefix],
            args=[inflight_limit, ttl_seconds]
        )
        claimed_index = result[0] if result and len(result) >= 2 else None
        inflight_after = result[1] if result and len(result) >= 2 else None
        if claimed_index is None:
            return False
        chunks_metadata_str = conn.get(chunks_metadata_key)
        if not chunks_metadata_str:
            return False
        chunks_metadata = json.loads(chunks_metadata_str)
        chunk_paths = chunks_metadata.get("chunk_paths", [])
        total_chunks = chunks_metadata.get("total_chunks", 0)
        if claimed_index >= len(chunk_paths):
            return False
        from app.services.redis_queue_service import get_redis_queue_service
        from app.services.close_caption_config import get_transcription_model_display
        queue_service = get_redis_queue_service()
        language = chunks_metadata.get("language", "th")
        model_size = chunks_metadata.get("model_size") or get_transcription_model_display()
        chunk_duration = chunks_metadata.get("chunk_duration", 150)
        source = chunks_metadata.get("source", "upload")
        num_gpus = int(os.getenv('NUM_GPUS', '1'))
        next_chunk_path = chunk_paths[claimed_index]
        next_chunk_task_id = f"{main_task_id}_chunk_{claimed_index}"
        gpu_index = claimed_index % num_gpus
        worker_gpu = f'gpu{gpu_index}'
        queue_service.enqueue_transcription(
            task_id=next_chunk_task_id,
            file_path=next_chunk_path,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration,
            priority=False,
            worker_gpu=worker_gpu,
            source=source
        )
        logger.debug(f"📤 Enqueued chunk {claimed_index + 1}/{total_chunks} (inflight: {inflight_after})")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Error in claim+enqueue: {e}", exc_info=True)
        return False


def _try_release_on_hold_tasks(conn, ttl_seconds: int):
    """เมื่อ record_backlog == 0 ให้ enqueue chunk ถัดไปของ tasks ที่ on_hold"""
    try:
        from app.services.redis_queue_service import get_redis_queue_service
        queue_svc = get_redis_queue_service()
        if queue_svc.get_record_backlog_count() > 0:
            return
        task_ids = conn.smembers("tasks:on_hold")
        if not task_ids:
            return
        for main_task_id in task_ids:
            main_task_id = main_task_id.decode() if isinstance(main_task_id, bytes) else main_task_id
            if conn.get(f"task:{main_task_id}:paused"):
                continue
            conn.srem("tasks:on_hold", main_task_id)
            conn.delete(f"task:{main_task_id}:on_hold")
            chunks_metadata_key = f"task:{main_task_id}:chunks_metadata"
            inflight_key = f"task:{main_task_id}:inflight_chunks"
            enqueued_guard_prefix = f"task:{main_task_id}:enqueued"
            inflight_limit = int(os.getenv('CHUNK_INFLIGHT_LIMIT_PER_JOB', '2'))
            if _do_claim_and_enqueue_next_chunk(
                conn, main_task_id, chunks_metadata_key, inflight_key,
                enqueued_guard_prefix, inflight_limit, ttl_seconds
            ):
                _update_task_stage_sync(
                    task_id=main_task_id,
                    progress=50,
                    status="processing",
                    stage="transcribing",
                    stage_description="กำลังแปลงเสียงเป็นข้อความ (ต่อจาก On Hold)",
                    stage_progress=None,
                    json_storage=None
                )
                logger.info(f"▶️ Released task {main_task_id} from On Hold")
    except Exception as e:
        logger.warning(f"⚠️  Error releasing on_hold tasks: {e}", exc_info=True)


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
        
        from app.utils.storage_factory import get_storage
        storage = get_storage()
        task_data = storage.load_transcription(task_id)
        
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
                logger.info(f"📡 WebSocket: Sending completed notification for {task_id}")
                await websocket_manager.notify_transcription_completed(task_id, results)
                logger.info(f"✅ WebSocket: Completed notification sent for {task_id}")
            elif status == "failed":
                logger.info(f"📡 WebSocket: Sending failed notification for {task_id}: {error_message or 'Unknown error'}")
                await websocket_manager.notify_transcription_failed(task_id, error_message or "Unknown error")
                logger.info(f"✅ WebSocket: Failed notification sent for {task_id}")
        except Exception as ws_e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว (non-critical)
            logger.warning(f"⚠️  WebSocket notification failed (non-critical): {ws_e}")
        
        # ส่ง webhook callback (เฉพาะเมื่อมี callback_url)
        callback_url = task_data.get("callback_url")
        if callback_url:
            try:
                from app.models.transcription import TranscriptionResponse
                from app.services.transcription_service import TranscriptionService
                
                # สร้าง TranscriptionResponse object สำหรับ _send_callback
                from app.services.close_caption_config import get_transcription_model_display
                model_size_val = task_data.get("model_size") or get_transcription_model_display()
                # ดึง chunks จาก task_data (อาจอยู่ใน "chunks" หรือ "segments")
                chunks_data = task_data.get("chunks") or task_data.get("segments") or []
                # แปลงเป็น TranscriptionChunk objects ถ้าจำเป็น
                from app.models.transcription import TranscriptionChunk
                parsed_chunks = []
                for c in chunks_data:
                    if isinstance(c, dict):
                        try:
                            parsed_chunks.append(TranscriptionChunk(
                                start_time=c.get("start_time", 0),
                                end_time=c.get("end_time", 0),
                                text=c.get("text", ""),
                                confidence=c.get("confidence"),
                            ))
                        except Exception:
                            pass

                task = TranscriptionResponse(
                    task_id=task_id,
                    status=status,
                    file_path=task_data.get("file_path"),
                    language=task_data.get("language", "th"),
                    model_size=model_size_val,
                    created_at=datetime.fromisoformat(task_data.get("created_at", datetime.now(timezone.utc).isoformat()).replace('Z', '+00:00')),
                    callback_url=callback_url,
                    progress=task_data.get("progress", 100 if status == "completed" else 0),
                    full_text=task_data.get("full_text", "") or task_data.get("text", ""),
                    total_duration=task_data.get("total_duration", 0),
                    source=task_data.get("source"),
                    chunks=parsed_chunks if parsed_chunks else None,
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
    # Fix: fallback model_size ที่ไม่ใช่ standard name เป็น env WHISPER_MODEL
    _standard = {"tiny", "base", "small", "medium", "large", "large-v1", "large-v2", "large-v3", "turbo", "large-v3-turbo"}
    if model_size and model_size.lower() not in _standard and not model_size.startswith("models--") and "/" not in model_size:
        from app.services.close_caption_config import get_transcription_model_display
        original = model_size
        model_size = get_transcription_model_display()
        logger.info(f"🔄 Model override: '{original}' → '{model_size}' (from env)")

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
            # วัด RAM/CPU ก่อนเริ่ม GPU chunk (สำหรับตรวจสอบการใช้งานทรัพยากร)
            ram_mb_chunk_before = cpu_chunk_before = None
            try:
                import psutil
                proc = psutil.Process()
                ram_mb_chunk_before = proc.memory_info().rss / (1024 * 1024)
                cpu_chunk_before = psutil.cpu_percent(interval=0.1)
            except Exception:
                pass
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
            
            # FIX: Log phase timings สำหรับ chunk job
            phase_timings = {
                'chunk_transcribe_time': chunk_transcribe_time,
                't_chunk_transcribe_start': datetime.now(timezone.utc).isoformat(),
                't_chunk_transcribe_end': datetime.now(timezone.utc).isoformat()
            }
            logger.info(f"📊 Chunk Phase Timings:")
            logger.info(f"   Transcribe: {chunk_transcribe_time:.2f}s")
            # วัด RAM/CPU หลังจบ chunk transcription
            try:
                import psutil
                proc = psutil.Process()
                ram_mb_chunk_after = proc.memory_info().rss / (1024 * 1024)
                cpu_chunk_after = psutil.cpu_percent(interval=0.1)
                if ram_mb_chunk_before is not None and ram_mb_chunk_after is not None:
                    logger.info(f"📊 Chunk resources: RAM {ram_mb_chunk_after:.1f} MB (delta: {ram_mb_chunk_after - ram_mb_chunk_before:+.1f} MB) | CPU before/after: {cpu_chunk_before or '-'}% / {cpu_chunk_after or '-'}%")
            except Exception:
                pass
            
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
            
            # FIX: Decrement inflight counter เมื่อ chunk เสร็จ (atomic)
            inflight_key = f"task:{main_task_id}:inflight_chunks"
            guard_key = f"task:{main_task_id}:enqueued:{chunk_index}"
            try:
                from app.workers.lua_scripts import DECR_INFLIGHT_SCRIPT
                decr_script = conn.register_script(DECR_INFLIGHT_SCRIPT)
                new_inflight = decr_script(keys=[inflight_key, guard_key], args=[ttl_seconds])
                logger.debug(f"📉 Decremented inflight counter for {main_task_id}: {new_inflight}")
            except Exception as e:
                # Fallback: ใช้ DECR ธรรมดา
                logger.warning(f"⚠️  Failed to use Lua script for inflight decrement, using DECR: {e}")
                try:
                    new_inflight = conn.decr(inflight_key)
                    conn.expire(inflight_key, ttl_seconds)
                except Exception as fallback_error:
                    logger.warning(f"⚠️  Failed to decrement inflight counter: {fallback_error}")
            
            # FIX: Windowed/JIT Enqueue - atomic claim next chunk index
            chunks_metadata_key = f"task:{main_task_id}:chunks_metadata"
            enqueued_guard_prefix = f"task:{main_task_id}:enqueued"
            inflight_limit = int(os.getenv('CHUNK_INFLIGHT_LIMIT_PER_JOB', '2'))
            
            # Pause: User หยุดชั่วคราว — ไม่ enqueue chunk ถัดไป
            paused_key = f"task:{main_task_id}:paused"
            if conn.get(paused_key):
                logger.info(f"⏸️ Task {main_task_id} is paused — skipping next chunk enqueue")
                _update_task_stage_sync(
                    task_id=main_task_id,
                    progress=int((done_count / int(conn.get(f"task:{main_task_id}:total_chunks") or 1)) * 50) + 40,
                    status="paused",
                    stage="paused",
                    stage_description="หยุดชั่วคราว (รอ Resume)",
                    stage_progress=int((done_count / int(conn.get(f"task:{main_task_id}:total_chunks") or 1)) * 100),
                    json_storage=None
                )
                # ยังต้อง try_release_on_hold_tasks สำหรับ tasks อื่น
                _try_release_on_hold_tasks(conn, ttl_seconds)
                # Skip claim+enqueue
            else:
                # On Hold: Record backlog > 0 — hold Upload chunks รอ Record เสร็จก่อน
                chunks_metadata_str = conn.get(chunks_metadata_key)
                if chunks_metadata_str:
                    chunks_meta = json.loads(chunks_metadata_str)
                    source = chunks_meta.get("source", "upload")
                    if source == "upload" and os.getenv('ENABLE_ON_HOLD_FOR_RECORD', 'false').lower() in ('1', 'true', 'yes'):
                        from app.services.redis_queue_service import get_redis_queue_service
                        queue_svc = get_redis_queue_service()
                        record_backlog = queue_svc.get_record_backlog_count()
                        if record_backlog > 0:
                            on_hold_key = f"task:{main_task_id}:on_hold"
                            conn.setex(on_hold_key, ttl_seconds, "1")
                            conn.sadd("tasks:on_hold", main_task_id)
                            conn.expire("tasks:on_hold", ttl_seconds)
                            logger.info(f"⏳ Task {main_task_id} On Hold (record_backlog={record_backlog}) — รอ Record เสร็จ")
                            _update_task_stage_sync(
                                task_id=main_task_id,
                                progress=int((done_count / int(conn.get(f"task:{main_task_id}:total_chunks") or 1)) * 50) + 40,
                                status="on_hold",
                                stage="on_hold",
                                stage_description="รอ Record เสร็จก่อน",
                                stage_progress=int((done_count / int(conn.get(f"task:{main_task_id}:total_chunks") or 1)) * 100),
                                json_storage=None
                            )
                            _try_release_on_hold_tasks(conn, ttl_seconds)
                            # Skip claim+enqueue
                        else:
                            _do_claim_and_enqueue_next_chunk(
                                conn, main_task_id, chunks_metadata_key, inflight_key,
                                enqueued_guard_prefix, inflight_limit, ttl_seconds
                            )
                            _try_release_on_hold_tasks(conn, ttl_seconds)
                    else:
                        _do_claim_and_enqueue_next_chunk(
                            conn, main_task_id, chunks_metadata_key, inflight_key,
                            enqueued_guard_prefix, inflight_limit, ttl_seconds
                        )
                        _try_release_on_hold_tasks(conn, ttl_seconds)
                else:
                    _try_release_on_hold_tasks(conn, ttl_seconds)
            
            # ตรวจสอบว่าทุก chunks เสร็จแล้วหรือยัง
            total_key = f"task:{main_task_id}:total_chunks"
            total_chunks = conn.get(total_key)
            if total_chunks:
                total_chunks = int(total_chunks)
                
                # อัปเดต progress (40% base + 50% for chunks = 40-90%)
                chunk_progress = int((done_count / total_chunks) * 50) + 40
                chunk_progress = min(chunk_progress, 90)  # ไม่เกิน 90% (เหลือ 10% สำหรับ aggregator)
                
                # FIX: อัปเดต progress ใน SQLite เมื่อ chunk เสร็จ (rate limited เพื่อไม่ให้ SQLite ทำงานหนักเกินไป)
                # Rate limiting: อัปเดตทุก 2 chunks หรือเมื่อ progress เปลี่ยน >= 5% หรือเมื่อ chunks เสร็จหมด
                # เพื่อลด load บน SQLite แต่ยังคงให้ progress update ที่เพียงพอ
                should_update_progress = (
                    done_count % 2 == 0 or  # ทุก 2 chunks
                    done_count >= total_chunks or  # เมื่อเสร็จหมด
                    chunk_progress % 5 == 0  # เมื่อ progress เปลี่ยน >= 5%
                )
                
                if should_update_progress:
                    try:
                        # ใช้ sync version เพื่อไม่ให้ block chunk processing
                        _update_task_stage_sync(
                            task_id=main_task_id,
                            progress=chunk_progress,
                            status="processing",
                            stage="transcribing",
                            stage_description=f"กำลังแปลงเสียงเป็นข้อความ ({done_count}/{total_chunks} ส่วนเสร็จ)",
                            stage_progress=int((done_count / total_chunks) * 100),
                            json_storage=None  # จะใช้ storage ที่ถูกต้องภายใน function
                        )
                        logger.debug(f"📊 Updated progress for {main_task_id}: {chunk_progress}% ({done_count}/{total_chunks} chunks)")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to update progress in SQLite (non-critical): {e}")
                
                # ส่ง WebSocket notification สำหรับ chunk completed (optional, granular update)
                # Rate limiting: ส่งทุก 2 chunks หรือเมื่อ chunks เสร็จหมด (ลดจาก 3 → 2 เพื่อให้ progress update บ่อยขึ้น)
                try:
                    from app.services.websocket_service import websocket_manager
                    if done_count % 2 == 0 or done_count >= total_chunks:
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
            
            # วัด RAM/CPU ก่อนเริ่ม aggregator (สำหรับตรวจสอบการใช้งานทรัพยากร)
            ram_mb_agg_before = cpu_agg_before = None
            try:
                import psutil
                proc = psutil.Process()
                ram_mb_agg_before = proc.memory_info().rss / (1024 * 1024)
                cpu_agg_before = psutil.cpu_percent(interval=0.1)
            except Exception:
                pass
            
            logger.info(f"📊 Processing aggregator job (using Redis atomic counter)")
            
            # ใช้ storage factory
            from app.utils.storage_factory import get_storage
            storage = get_storage()

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
            
            # FIX: อัปเดต stage: transcribing (ไม่ hardcode progress=40 ถ้า DB ตอนนั้นสูงกว่าแล้ว)
            # ตรวจสอบ progress ปัจจุบันก่อน
            existing_task = storage.load_transcription(main_task_id)
            
            # ใช้ progress สูงสุดระหว่าง 40 กับ progress ที่มีอยู่ (ป้องกัน progress ย้อนกลับ)
            current_progress = existing_task.get("progress", 0) if existing_task else 0
            initial_progress = max(40, current_progress)  # อย่างน้อย 40% แต่ไม่ต่ำกว่าค่าปัจจุบัน
            
            _update_task_stage_sync(
                task_id=main_task_id,
                progress=initial_progress,
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
            t_fetch_start = time.time()

            # Diarization: โหลด task + diarization ถ้าเปิด
            enable_diarization = False
            diarization_segments = None
            _td = (storage.load_transcription(main_task_id) if storage else {}) or {}
            enable_diarization = bool(_td.get("enable_diarization", False))
            if enable_diarization:
                ds = conn.get(f"task:{main_task_id}:diarization")
                if ds:
                    diarization_segments = json.loads(ds)
                    logger.info(f"📢 Diarization: {len(diarization_segments)} segments for /newSpeaker")
                else:
                    enable_diarization = False
            
            merged_text_parts = []
            all_segments_for_diarization = [] if enable_diarization else None
            total_duration = total_chunks * chunk_duration
            last_segment_end = 0.0
            
            # Setup SQLite connection for streaming segments
            import sqlite3
            from pathlib import Path
            from app.utils.sqlite_schema import ensure_sqlite_schema
            # os already imported at top level
            
            # SQLite segments table (เฉพาะ SQLite mode — Postgres เก็บใน TranscriptionResults.SegmentsJson)
            sqlite_conn = None
            segments_batch = None
            _storage_type = os.getenv('STORAGE_TYPE', 'sqlite').lower()
            if _storage_type == 'sqlite':
                db_path = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
                sqlite_conn = ensure_sqlite_schema(db_path)
                insert_stmt = """
                    INSERT INTO segments (task_id, idx, start_time, end_time, text, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                segments_batch = []
                batch_size = 100
            
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
                    
                    segments = chunk_result.get('segments', [])
                    if segments:
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
                            
                            if seg_text:
                                if sqlite_conn and segments_batch is not None:
                                    segments_batch.append((main_task_id, processed_count * 1000 + seg_idx, start_time, end_time, seg_text, confidence))
                                    if len(segments_batch) >= batch_size:
                                        sqlite_conn.executemany(insert_stmt, segments_batch)
                                        sqlite_conn.commit()
                                        segments_batch.clear()
                                last_segment_end = max(last_segment_end, end_time)
                                if all_segments_for_diarization is not None:
                                    all_segments_for_diarization.append({"start": start_time, "end": end_time, "text": seg_text})
                    
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
            logger.warning(f"✅ Processed {processed_count}/{total_chunks} chunks (took {phase_timings['fetch_chunks_time']:.2f}s), finalizing merge...")
            
            # Build merged result
            if enable_diarization and diarization_segments and all_segments_for_diarization:
                from app.services.diarization_service import build_text_with_speaker_markers
                full_text = build_text_with_speaker_markers(all_segments_for_diarization, diarization_segments)
                logger.info(f"📢 Applied /newSpeaker (len={len(full_text)})")
            else:
                full_text = " ".join(merged_text_parts).strip()
            del merged_text_parts
            if all_segments_for_diarization is not None:
                del all_segments_for_diarization
            import gc
            gc.collect()
            
            merged_result = {
                "text": full_text,
                "total_duration": last_segment_end if last_segment_end > 0 else total_duration,
                "language": language
            }
            
            # Apply Thai processor (PyThaiNLP + Attacut) — ปิดได้ผ่าน ENABLE_THAI_PROCESSING_FOR_TRANSCRIPTION
            if language == "th" and os.getenv("ENABLE_THAI_PROCESSING_FOR_TRANSCRIPTION", "true").lower() == "true":
                t_thai_start = time.time()
                logger.warning(f"🇹🇭 Applying Thai processor... (text len={len(merged_result.get('text',''))})")
                merged_result = transcription_service.whisper_service._apply_thai_processing(merged_result)
                t_thai_end = time.time()
                phase_timings['thai_processing_time'] = t_thai_end - t_thai_start
                logger.warning(f"✅ Thai processing completed (took {phase_timings['thai_processing_time']:.2f}s)")

                # Fuzzy Match (ชื่อคน + คำศัพท์) — เปิด/ปิดได้ผ่าน FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION
                if os.getenv("FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION", "true").lower() == "true":
                    try:
                        from app.services.fuzzy_match_service import apply_fuzzy_match
                        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
                        t_fuzzy_start = time.time()
                        before_text = merged_result.get("text", "")
                        fuzzy_timeout = int(os.getenv("FUZZY_MATCH_TIMEOUT_SECONDS", "60"))
                        logger.warning(f"🔤 Applying Fuzzy match... (text len={len(before_text)}, timeout={fuzzy_timeout}s)")
                        ex = ThreadPoolExecutor(max_workers=1)
                        try:
                            future = ex.submit(apply_fuzzy_match, before_text)
                            try:
                                merged_result["text"] = future.result(timeout=fuzzy_timeout)
                            except FuturesTimeoutError:
                                logger.warning(f"⚠️ Fuzzy match timeout ({fuzzy_timeout}s), using original text")
                                merged_result["text"] = before_text
                        finally:
                            ex.shutdown(wait=False)  # อย่ารอ thread ที่ค้าง — ให้ main ทำงานต่อ
                        phase_timings['fuzzy_match_time'] = time.time() - t_fuzzy_start
                        if before_text != merged_result["text"]:
                            logger.warning(f"✅ Fuzzy match applied (took {phase_timings.get('fuzzy_match_time', 0):.2f}s)")
                        else:
                            logger.warning(f"✅ Fuzzy match ran (took {phase_timings.get('fuzzy_match_time', 0):.2f}s, no changes)")
                    except Exception as fuzzy_e:
                        logger.warning(f"⚠️ Fuzzy match error: {fuzzy_e}")
                        if "before_text" in locals():
                            merged_result["text"] = before_text
            
            t_merge_end = time.time()
            phase_timings['t_merge_end'] = datetime.now(timezone.utc).isoformat()
            phase_timings['merge_time'] = t_merge_end - t_merge_start
            
            # อัปเดต main task จาก storage (ใช้ storage factory)
            from app.utils.storage_factory import get_storage
            storage = get_storage()
            task_data = storage.load_transcription(main_task_id)
            if not task_data:
                task_data = {}
            
            # FIX: บันทึก phase timings และคำนวณ total time
            t_aggregator_end = time.time()
            phase_timings['t_aggregator_end'] = datetime.now(timezone.utc).isoformat()
            phase_timings['total_aggregator_time'] = t_aggregator_end - t_aggregator_start
            
            # รวม phase timings จาก preprocess (ถ้ามี)
            if 'phase_timings' in task_data and isinstance(task_data.get('phase_timings'), dict):
                preprocess_timings = task_data['phase_timings'].get('preprocess', {})
                # คำนวณ total time จาก start ถึง aggregator end
                if preprocess_timings and 't_start' in preprocess_timings:
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
            
            # บันทึก aggregator phase timings
            if 'phase_timings' not in task_data:
                task_data['phase_timings'] = {}
            task_data['phase_timings']['aggregator'] = phase_timings

            # บันทึกกลับไป storage
            storage.save_transcription(main_task_id, task_data)
            
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
            
            # FIX: Log phase timings แบบละเอียดเพื่อวิเคราะห์ bottleneck
            logger.info(f"📊 Aggregator Phase Timings:")
            logger.info(f"   Wait chunks: {phase_timings.get('wait_chunks_time', 0):.2f}s")
            logger.info(f"   Fetch chunks: {phase_timings.get('fetch_chunks_time', 0):.2f}s")
            logger.info(f"   Merge: {phase_timings.get('merge_time', 0):.2f}s")
            if 'thai_processing_time' in phase_timings:
                logger.info(f"   Thai processing: {phase_timings['thai_processing_time']:.2f}s")
            logger.info(f"   Total aggregator: {phase_timings['total_aggregator_time']:.2f}s")
            if 'total_end_to_end_time' in phase_timings:
                logger.info(f"   Total end-to-end: {phase_timings['total_end_to_end_time']:.2f}s ({phase_timings['total_end_to_end_time']/60:.2f} minutes)")
            
            # FIX: Log phase timings รวมจาก preprocess (ถ้ามี) เพื่อวิเคราะห์ bottleneck ทั้งหมด
            if 'phase_timings' in task_data and isinstance(task_data.get('phase_timings'), dict):
                preprocess_timings = task_data['phase_timings'].get('preprocess', {})
                if preprocess_timings:
                    logger.info(f"📊 Combined Phase Timings (Preprocess + Aggregator):")
                    logger.info(f"   Preprocess - Extract: {preprocess_timings.get('extract_time', 0):.2f}s")
                    logger.info(f"   Preprocess - Chunk: {preprocess_timings.get('chunk_time', 0):.2f}s")
                    logger.info(f"   Preprocess - Enqueue: {preprocess_timings.get('enqueue_time', 0):.2f}s")
                    logger.info(f"   Preprocess - Total: {preprocess_timings.get('total_preprocess_time', 0):.2f}s")
                    logger.info(f"   Aggregator - Wait: {phase_timings.get('wait_chunks_time', 0):.2f}s")
                    logger.info(f"   Aggregator - Fetch: {phase_timings.get('fetch_chunks_time', 0):.2f}s")
                    logger.info(f"   Aggregator - Merge: {phase_timings.get('merge_time', 0):.2f}s")
                    logger.info(f"   Aggregator - Total: {phase_timings.get('total_aggregator_time', 0):.2f}s")
                    if 'total_end_to_end_time' in phase_timings:
                        logger.info(f"   🎯 Total End-to-End: {phase_timings['total_end_to_end_time']:.2f}s ({phase_timings['total_end_to_end_time']/60:.2f} minutes)")
                        
                        # FIX: คำนวณและ log percentage ของแต่ละ phase เพื่อห bottleneck
                        total_time = phase_timings['total_end_to_end_time']
                        if total_time > 0:
                            logger.info(f"📈 Phase Breakdown (% of total time):")
                            logger.info(f"   Preprocess: {((preprocess_timings.get('total_preprocess_time', 0) / total_time) * 100):.1f}%")
                            logger.info(f"   Wait chunks: {((phase_timings.get('wait_chunks_time', 0) / total_time) * 100):.1f}%")
                            logger.info(f"   Fetch chunks: {((phase_timings.get('fetch_chunks_time', 0) / total_time) * 100):.1f}%")
                            logger.info(f"   Merge: {((phase_timings.get('merge_time', 0) / total_time) * 100):.1f}%")
                            if 'thai_processing_time' in phase_timings:
                                logger.info(f"   Thai processing: {((phase_timings['thai_processing_time'] / total_time) * 100):.1f}%")
                            # Note: Chunk transcription time ไม่รวมใน total_end_to_end เพราะมันทำงาน parallel
                            logger.info(f"   (Chunk transcription runs in parallel, not included in breakdown)")
            
            # วัด RAM/CPU หลังจบ aggregator
            try:
                import psutil
                proc = psutil.Process()
                ram_mb_agg_after = proc.memory_info().rss / (1024 * 1024)
                cpu_agg_after = psutil.cpu_percent(interval=0.1)
                if ram_mb_agg_before is not None and ram_mb_agg_after is not None:
                    logger.info(f"📊 Aggregator resources: RAM {ram_mb_agg_after:.1f} MB (delta: {ram_mb_agg_after - ram_mb_agg_before:+.1f} MB) | CPU before/after: {cpu_agg_before or '-'}% / {cpu_agg_after or '-'}%")
            except Exception:
                pass
            
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
                "segments_stored_in": "postgres"
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

        # FIX: เมื่อ CHUNK job ล้มเหลว ต้อง decr inflight + incr done_chunks + บันทึก chunk ว่าง
        # มิฉะนั้น inflight ค้าง → ไม่มี chunk ถัดไปถูก enqueue และ aggregator รอไม่จบ
        if "_chunk_" in task_id:
            try:
                main_task_id = task_id.rsplit("_chunk_", 1)[0]
                chunk_index = int(task_id.rsplit("_chunk_", 1)[1])
                conn = get_redis_connection(decode_responses=True)
                ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
                # บันทึก chunk result ว่าง (ให้ aggregator merge ต่อได้)
                chunk_result_key = f"task:{main_task_id}:chunk:{chunk_index}"
                empty_result = json.dumps({"text": "", "segments": [], "processing_time": 0, "error": str(e)})
                conn.setex(chunk_result_key, ttl_seconds, empty_result)
                # incr done_chunks เพื่อให้ aggregator นับครบ
                done_key = f"task:{main_task_id}:done_chunks"
                conn.incr(done_key)
                conn.expire(done_key, ttl_seconds)
                # decr inflight เพื่อให้ chunk ถัดไปถูก enqueue ได้
                inflight_key = f"task:{main_task_id}:inflight_chunks"
                guard_key = f"task:{main_task_id}:enqueued:{chunk_index}"
                try:
                    from app.workers.lua_scripts import DECR_INFLIGHT_SCRIPT
                    decr_script = conn.register_script(DECR_INFLIGHT_SCRIPT)
                    decr_script(keys=[inflight_key, guard_key], args=[ttl_seconds])
                except Exception as decr_err:
                    try:
                        conn.decr(inflight_key)
                        conn.expire(inflight_key, ttl_seconds)
                    except Exception:
                        pass
                logger.warning(f"⚠️ Chunk {chunk_index} failed; recorded empty result and freed inflight so next chunk can run")
            except Exception as chunk_cleanup_err:
                logger.error(f"❌ Failed to cleanup chunk on error: {chunk_cleanup_err}", exc_info=True)
        
        # บันทึก error status และส่ง WebSocket notification (สำหรับ full job ไม่ใช่ chunk)
        try:
            from datetime import datetime, timezone
            # os already imported at module level (line 8)
            # สำหรับ chunk job ไม่ต้อง mark main task เป็น failed (เรา record empty chunk แล้ว)
            if "_chunk_" not in task_id:
                from app.utils.storage_factory import get_storage
                storage = get_storage()
                task_data = storage.load_transcription(task_id) or {}
                task_data["status"] = "failed"
                task_data["error_message"] = str(e)
                task_data["current_stage"] = "failed"
                task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
                task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                storage.save_transcription(task_id, task_data)
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
    
    # FIX: Release on_hold tasks ก่อนเริ่ม preprocess (trigger อัตโนมัติเมื่อมี job ใหม่ เช่น Resubmit)
    # แก้ปัญหา: task on_hold ค้างเมื่อ Main API ไม่รัน (StuckTaskMonitor อยู่ที่ API)
    try:
        from app.services.on_hold_release import try_release_on_hold_tasks
        released = try_release_on_hold_tasks()
        if released > 0:
            logger.info(f"▶️ Released {released} on_hold task(s) (preprocess trigger)")
    except Exception as e:
        logger.debug(f"On-hold release at preprocess start: {e}")
    
    # FIX: เพิ่ม phase-based timing metrics
    import time
    from datetime import datetime, timezone
    phase_timings = {}
    t_start = time.time()
    phase_timings['t_start'] = datetime.now(timezone.utc).isoformat()
    
    try:
        from app.services.video_service import VideoService
        from app.services.redis_queue_service import get_redis_queue_service
        # os already imported at top level
        import json
        from redis import Redis
        
        from app.utils.storage_factory import get_storage
        storage = get_storage()
        task_data = storage.load_transcription(task_id)
        if not task_data:
            task_data = {}

        video_service = VideoService()
        queue_service = get_redis_queue_service()
        
        # FIX: บันทึก file_path, file_name, language, model_size ลง task_data
        task_data["file_path"] = file_path
        task_data["file_name"] = os.path.basename(file_path) if file_path else None
        task_data["language"] = language
        task_data["model_size"] = model_size
        task_data["chunk_duration"] = chunk_duration
        if not task_data.get("created_at"):
            task_data["created_at"] = datetime.now(timezone.utc).isoformat()
        if not task_data.get("task_id"):
            task_data["task_id"] = task_id
        if "status" not in task_data:
            task_data["status"] = "processing"
        
        # FIX: บันทึก task_data ลง storage ทันที (รวม model_size) เพื่อป้องกัน fallback เป็น "base"
        # กรณี transcription_enhanced บันทึกไว้แค่ JSON แต่ STORAGE_TYPE=sqlite
        storage.save_transcription(task_id, task_data)
        
        # อัปเดต stage: preprocessing
        _update_task_stage_sync(
            task_id=task_id,
            progress=10,
            status="processing",
            stage="preprocessing",
            stage_description="กำลังเตรียมไฟล์และแยกเสียง",
            stage_progress=0
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
            stage_progress=0
        )
        audio_path = video_service.extract_audio(file_path, task_id=task_id)
        t_extract_end = time.time()
        phase_timings['t_extract_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['extract_time'] = t_extract_end - t_extract_start
        logger.info(f"✅ Audio extracted: {audio_path} (took {phase_timings['extract_time']:.2f}s)")

        # 1.5 Diarization (optional)
        enable_diarization = task_data.get("enable_diarization", False)
        if enable_diarization:
            t_diar_start = time.time()
            _update_task_stage_sync(
                task_id=task_id, progress=20, status="processing", stage="diarization",
                stage_description="กำลังแยกผู้พูด", stage_progress=0
            )
            try:
                from app.services.diarization_service import diarize
                conn_d = get_redis_connection(decode_responses=True)
                ttl = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
                diar_result = diarize(audio_path)
                conn_d.setex(f"task:{task_id}:diarization", ttl, json.dumps(diar_result))
                phase_timings['diarization_time'] = time.time() - t_diar_start
                logger.info(f"✅ Diarization: {len(diar_result)} segments ({phase_timings['diarization_time']:.2f}s)")
            except Exception as de:
                logger.warning(f"⚠️ Diarization failed: {de}", exc_info=True)
                get_redis_connection(decode_responses=True).delete(f"task:{task_id}:diarization")
        
        # 2. Create chunks (หรือ full file ถ้า use_chunking=false)
        use_chunking = task_data.get("use_chunking", True)
        if use_chunking is None:
            use_chunking = os.getenv("TRANSCRIPTION_USE_CHUNKING", "true").lower() in ("1", "true", "yes")
        if not use_chunking:
            chunk_duration = 36000  # 10 ชม. = 1 chunk (full file)
            logger.info(f"📦 Full-file mode (use_chunking=false): ไม่แบ่ง chunk")
        elif task_data.get("source") == "video_record":
            chunk_duration = int(os.getenv("RECORD_CHUNK_DURATION", "120"))
            logger.info(f"📦 Record mode: ใช้ RECORD_CHUNK_DURATION={chunk_duration}s")
        t_chunk_start = time.time()
        logger.info(f"📦 Creating chunks from {audio_path} (chunk_duration={chunk_duration}s)...")
        _update_task_stage_sync(
            task_id=task_id,
            progress=25,
            status="processing",
            stage="chunking",
            stage_description="กำลังแบ่งไฟล์เป็นส่วนๆ" if use_chunking else "ใช้ไฟล์เต็ม (ไม่แบ่ง)",
            stage_progress=0
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
            stage_progress=0
        )
        
        # 3. Enqueue chunk jobs ไปยัง GPU queues (Fan-out)
        # FIX: Windowed/JIT Enqueue - enqueue แค่ N chunks แรก แล้ว enqueue ถัดไปเมื่อ chunk เสร็จ
        t_enqueue_start = time.time()
        
        # FIX: ห้าม auto-detect - ใช้ NUM_GPUS อย่างเดียวเพื่อป้องกัน queue mismatch
        num_gpus = int(os.getenv('NUM_GPUS', '0'))
        if num_gpus <= 0:
            error_msg = "NUM_GPUS is not set or invalid. Please set NUM_GPUS environment variable."
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        logger.info(f"📊 Using {num_gpus} GPUs from NUM_GPUS environment variable")
        
        # Windowed enqueue: enqueue แค่ N chunks แรก (ไม่ใช่ทั้งหมด)
        # ค่าเริ่มต้น: 4 chunks (สามารถปรับได้ผ่าน env var)
        initial_window_size = int(os.getenv('CHUNK_ENQUEUE_WINDOW_SIZE', '4'))
        source = task_data.get("source", "upload")
        
        # On Hold ตั้งแต่ preprocess: ถ้า Record รออยู่ ให้ไม่ enqueue Upload chunks เลย (ปล่อย slot ให้ Record)
        # ป้องกันกรณี "ติด Job" — Upload chunks รอ slot ไม่ได้รัน → On Hold ไม่เกิด
        if source == "upload" and os.getenv('ENABLE_ON_HOLD_FOR_RECORD', 'false').lower() in ('1', 'true', 'yes'):
            record_backlog = queue_service.get_record_backlog_count()
            logger.debug(f"📊 Preprocess {task_id}: record_backlog={record_backlog}")
            if record_backlog > 0:
                logger.info(f"⏳ Task {task_id} On Hold ตั้งแต่ preprocess (record_backlog={record_backlog}) — ไม่ enqueue chunks")
                conn = get_redis_connection(decode_responses=True)
                ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
                conn.setex(f"task:{task_id}:on_hold", ttl_seconds, "1")
                conn.sadd("tasks:on_hold", task_id)
                conn.expire("tasks:on_hold", ttl_seconds)
                enqueued_count = 0
                chunks_metadata = {
                    "chunk_paths": chunks,
                    "next_chunk_index": 0,
                    "total_chunks": total_chunks,
                    "chunk_duration": chunk_duration,
                    "language": language,
                    "model_size": model_size,
                    "source": source,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                conn.setex(f"task:{task_id}:chunks_metadata", ttl_seconds, json.dumps(chunks_metadata))
                conn.setex(f"task:{task_id}:total_chunks", ttl_seconds, str(total_chunks))
                conn.setex(f"task:{task_id}:done_chunks", ttl_seconds, "0")
                conn.set(f"task:{task_id}:inflight_chunks", "0")
                conn.expire(f"task:{task_id}:inflight_chunks", ttl_seconds)
                _update_task_stage_sync(
                    task_id=task_id,
                    progress=35,
                    status="on_hold",
                    stage="on_hold",
                    stage_description="รอ Record เสร็จก่อน",
                    stage_progress=0
                )
                chunk_data = []
                # ข้ามไปยัง aggregator enqueue (ยังต้อง enqueue aggregator)
            else:
                chunk_data = []
                enqueued_count = 0
                logger.info(f"📝 Enqueueing {min(initial_window_size, total_chunks)}/{total_chunks} chunks initially (windowed enqueue)...")
                for i in range(min(initial_window_size, total_chunks)):
                    chunk_path = chunks[i]
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
                        worker_gpu=worker_gpu,
                        source=source
                    )
                    chunk_data.append({
                        "i": i,
                        "job_id": job_id,
                        "chunk_task_id": chunk_task_id,
                        "chunk_path": chunk_path,
                        "worker_gpu": worker_gpu
                    })
                    enqueued_count += 1
                    logger.debug(f"   Chunk {i+1}/{total_chunks} enqueued to {worker_gpu}")
        else:
            chunk_data = []
            enqueued_count = 0
            logger.info(f"📝 Enqueueing {min(initial_window_size, total_chunks)}/{total_chunks} chunks initially (windowed enqueue)...")
            for i in range(min(initial_window_size, total_chunks)):
                chunk_path = chunks[i]
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
                    worker_gpu=worker_gpu,
                    source=source
                )
                chunk_data.append({
                    "i": i,
                    "job_id": job_id,
                    "chunk_task_id": chunk_task_id,
                    "chunk_path": chunk_path,
                    "worker_gpu": worker_gpu
                })
                enqueued_count += 1
                logger.debug(f"   Chunk {i+1}/{total_chunks} enqueued to {worker_gpu}")
        
        # เก็บ metadata สำหรับ windowed enqueue (ข้ามถ้า On Hold — set ไว้แล้ว)
        # - next_chunk_index: chunk ถัดไปที่จะ enqueue
        # - chunks: รายการ chunk paths ทั้งหมด
        conn = get_redis_connection(decode_responses=True)
        ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))  # Default: 12 hours
        
        # เก็บ chunk paths ทั้งหมดไว้ใน Redis (สำหรับ enqueue ถัดไป)
        source = task_data.get("source", "upload")
        chunks_metadata = {
            "chunk_paths": chunks,  # เก็บ paths ทั้งหมด
            "next_chunk_index": enqueued_count,  # chunk ถัดไปที่จะ enqueue
            "total_chunks": total_chunks,
            "chunk_duration": chunk_duration,
            "language": language,
            "model_size": model_size,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.setex(
            f"task:{task_id}:chunks_metadata",
            ttl_seconds,
            json.dumps(chunks_metadata)
        )
        
        t_enqueue_end = time.time()
        phase_timings['t_enqueue_chunks_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['enqueue_time'] = t_enqueue_end - t_enqueue_start
        logger.info(f"✅ Enqueued {enqueued_count}/{total_chunks} chunks initially (windowed, remaining will be enqueued as chunks complete)")
        
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
        
        # FIX: ตั้งค่า inflight counter สำหรับ fairness
        # เริ่มต้นที่จำนวน chunks ที่ enqueue แล้ว (initial window)
        # ใช้ SET แทน setex เพื่อให้ INCR/DECR ใช้งานได้ถูกต้อง
        inflight_key = f"task:{task_id}:inflight_chunks"
        conn.set(inflight_key, str(enqueued_count))
        conn.expire(inflight_key, ttl_seconds)
        
        # ตั้ง guard keys สำหรับ chunks ที่ enqueue แล้ว (ป้องกัน enqueue ซ้ำ)
        enqueued_guard_prefix = f"task:{task_id}:enqueued"
        for i in range(enqueued_count):
            guard_key = f"{enqueued_guard_prefix}:{i}"
            conn.setex(guard_key, ttl_seconds, '1')
        
        logger.debug(f"✅ Initialized inflight counter: {enqueued_count}, guards: {enqueued_count}")
        
        t_end = time.time()
        phase_timings['t_end'] = datetime.now(timezone.utc).isoformat()
        phase_timings['total_preprocess_time'] = t_end - t_start
        
        # FIX: บันทึก phase timings ลง task_data (เก็บไว้ใน 'preprocess' key เพื่อแยกจาก aggregator)
        if 'phase_timings' not in task_data:
            task_data['phase_timings'] = {}
        task_data['phase_timings']['preprocess'] = phase_timings
        
        # บันทึกลง storage
        storage.save_transcription(task_id, task_data)
        
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
            from app.utils.storage_factory import get_storage
            from datetime import datetime, timezone
            storage = get_storage()
            task_data = storage.load_transcription(task_id) or {}
            task_data["status"] = "failed"
            task_data["error_message"] = str(e)
            task_data["current_stage"] = "failed"
            task_data["current_stage_description"] = f"เกิดข้อผิดพลาด: {str(e)}"
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            storage.save_transcription(task_id, task_data)
            
            # ส่ง failure callback (webhook + WebSocket)
            # _send_completion_callback จะส่งทั้ง WebSocket notification และ webhook callback
            loop = get_event_loop()
            loop.run_until_complete(_send_completion_callback(task_id, "failed", str(e)))
        except Exception as save_error:
            logger.error(f"❌ Failed to save error status: {save_error}")
        raise


def process_preprocess_job_chunk_group(
    task_id: str,
    file_paths: List[str],
    language: str,
    model_size: str,
) -> Dict:
    """
    Preprocess โหมด chunk group:
    - ข้าม extract_audio, create_chunks
    - ใช้ file_paths เป็น chunks โดยตรง
    - Convert เป็น 16k mono ถ้าจำเป็น
    - Enqueue chunk jobs ไป GPU + aggregator
    """
    logger.info(f"🔧 RQ Worker: Starting chunk group preprocess job {task_id}")
    logger.info(f"   Files: {len(file_paths)}")
    
    import time
    from datetime import datetime, timezone
    
    try:
        from app.services.video_service import VideoService
        from app.services.redis_queue_service import get_redis_queue_service
        import json
        from redis import Redis
        
        from app.utils.storage_factory import get_storage
        storage = get_storage()
        task_data = storage.load_transcription(task_id)
        if not task_data:
            task_data = {}

        video_service = VideoService()
        queue_service = get_redis_queue_service()
        
        task_data["file_path"] = file_paths[0]
        task_data["file_name"] = f"{Path(file_paths[0]).parent.name} ({len(file_paths)} chunks)"
        task_data["file_paths"] = file_paths
        task_data["chunk_group"] = True
        task_data["language"] = language
        task_data["model_size"] = model_size
        if not task_data.get("created_at"):
            task_data["created_at"] = datetime.now(timezone.utc).isoformat()
        if not task_data.get("task_id"):
            task_data["task_id"] = task_id
        if "status" not in task_data:
            task_data["status"] = "processing"
        
        storage.save_transcription(task_id, task_data)
        
        _update_task_stage_sync(
            task_id=task_id,
            progress=10,
            status="processing",
            stage="preprocessing_chunk_group",
            stage_description=f"กำลังเตรียม {len(file_paths)} ไฟล์",
            stage_progress=0
        )
        
        # Convert เป็น 16k mono ถ้าจำเป็น (ข้ามถ้าเป็น WAV 16k แล้ว)
        chunks = []
        for i, fp in enumerate(file_paths):
            if video_service._is_already_wav_16k_mono(fp):
                chunks.append(fp)
                logger.debug(f"   Chunk {i}: skip convert (already WAV 16k): {fp}")
            else:
                converted = video_service.extract_audio(fp, task_id=f"{task_id}_cg{i}")
                chunks.append(converted)
                logger.debug(f"   Chunk {i}: converted to 16k mono: {converted}")
        
        total_chunks = len(chunks)
        chunk_duration = int(os.getenv("RECORD_CHUNK_DURATION", "120")) if task_data.get("source") == "video_record" else 150
        
        _update_task_stage_sync(
            task_id=task_id,
            progress=25,
            status="processing",
            stage="enqueueing",
            stage_description=f"กำลังส่ง {total_chunks} ส่วนไปประมวลผล",
            stage_progress=0
        )
        
        num_gpus = int(os.getenv('NUM_GPUS', '0'))
        if num_gpus <= 0:
            raise RuntimeError("NUM_GPUS is not set or invalid.")
        
        initial_window_size = int(os.getenv('CHUNK_ENQUEUE_WINDOW_SIZE', '4'))
        enqueued_count = 0
        chunk_data = []
        conn = get_redis_connection(decode_responses=True)
        ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
        
        source = task_data.get("source", "upload")
        for i in range(min(initial_window_size, total_chunks)):
            chunk_path = chunks[i]
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
                worker_gpu=worker_gpu,
                source=source
            )
            chunk_data.append({
                "i": i,
                "job_id": job_id,
                "chunk_task_id": chunk_task_id,
                "chunk_path": chunk_path,
                "worker_gpu": worker_gpu
            })
            enqueued_count += 1
        
        source = task_data.get("source", "upload")
        chunks_metadata = {
            "chunk_paths": chunks,
            "next_chunk_index": enqueued_count,
            "total_chunks": total_chunks,
            "chunk_duration": chunk_duration,
            "language": language,
            "model_size": model_size,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.setex(
            f"task:{task_id}:chunks_metadata",
            ttl_seconds,
            json.dumps(chunks_metadata)
        )
        
        aggregator_task_id = f"{task_id}_aggregator"
        queue_service.enqueue_aggregator(
            task_id=aggregator_task_id,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration
        )
        
        conn.setex(
            f"task:{task_id}:chunk_jobs",
            ttl_seconds,
            json.dumps({
                "chunk_duration": chunk_duration,
                "total_chunks": total_chunks,
                "chunks": chunk_data
            })
        )
        conn.setex(f"task:{task_id}:total_chunks", ttl_seconds, str(total_chunks))
        conn.setex(f"task:{task_id}:done_chunks", ttl_seconds, "0")
        inflight_key = f"task:{task_id}:inflight_chunks"
        conn.set(inflight_key, str(enqueued_count))
        conn.expire(inflight_key, ttl_seconds)
        enqueued_guard_prefix = f"task:{task_id}:enqueued"
        for i in range(enqueued_count):
            conn.setex(f"{enqueued_guard_prefix}:{i}", ttl_seconds, '1')
        
        storage.save_transcription(task_id, task_data)
        
        try:
            from app.services.websocket_service import websocket_manager
            loop = get_event_loop()
            loop.run_until_complete(
                websocket_manager.notify_transcription_started(
                    task_id=task_id,
                    file_path=file_paths[0],
                    language=language
                )
            )
        except Exception as e:
            logger.debug(f"WebSocket started notification failed: {e}")
        
        logger.info(f"✅ Chunk group preprocess job {task_id} completed ({total_chunks} chunks)")
        return {
            "task_id": task_id,
            "total_chunks": total_chunks,
            "chunk_data": chunk_data,
        }
        
    except Exception as e:
        logger.error(f"❌ Chunk group preprocess job {task_id} failed: {e}", exc_info=True)
        try:
            from app.utils.storage_factory import get_storage
            storage = get_storage()
            task_data = storage.load_transcription(task_id) or {}
            task_data["status"] = "failed"
            task_data["error_message"] = str(e)
            task_data["current_stage"] = "failed"
            task_data["current_stage_description"] = str(e)
            task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            storage.save_transcription(task_id, task_data)
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

def process_live_chunk_job(
    session_id: str,
    meeting_id: str,
    chunk_index: int,
    start_time: float,
    duration: float,
    audio_path: str,
    model_size: Optional[str] = None
) -> Dict:
    """
    RQ Worker function สำหรับ live chunk transcription (Priority Queue)
    
    Args:
        session_id: Session ID
        meeting_id: Meeting ID
        chunk_index: Chunk index
        start_time: Start time in seconds
        duration: Duration in seconds
        audio_path: Path to audio file
        model_size: Model size (optional, will use default if not provided)
    
    Returns:
        Result dictionary with status
    """
    import time
    job_start_time = time.time()
    
    # วัด RAM/CPU ก่อนเริ่ม job (สำหรับตรวจสอบการใช้งานทรัพยากร)
    ram_mb_before = cpu_percent_before = None
    try:
        import psutil
        proc = psutil.Process()
        ram_mb_before = proc.memory_info().rss / (1024 * 1024)
        cpu_percent_before = psutil.cpu_percent(interval=0.1)
    except Exception as e:
        logger.debug(f"Could not get initial resource stats: {e}")
    
    # ใช้ default model จาก env (โมเดลเดียวกับ WHISPER_MODEL/CC_MODEL_SIZE)
    if not model_size:
        from app.services.close_caption_config import get_default_whisper_model, whisper_model_to_display
        model_size = whisper_model_to_display(get_default_whisper_model())
    
    logger.info(f"🚀 RQ Worker: Starting live chunk job {session_id}")
    logger.info(f"   Meeting: {meeting_id}, Chunk: {chunk_index}, Start: {start_time}s, Duration: {duration}s")
    logger.info(f"   Audio: {audio_path}, Model: {model_size}")
    logger.info(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    try:
        # Import async function from API module
        from app.api.realtime_transcription import process_live_chunk_background
        
        # ใช้ persistent event loop
        loop = get_event_loop()
        logger.info(f"✅ Using persistent event loop (instance: {id(loop)})")
        
        # เรียก async function
        result = loop.run_until_complete(
            process_live_chunk_background(
                session_id=session_id,
                meeting_id=meeting_id,
                chunk_index=chunk_index,
                start_time=start_time,
                duration=duration,
                audio_path=audio_path,
                model_size=model_size  # ส่ง model_size ไป background function
            )
        )
        
        job_end_time = time.time()
        job_duration = job_end_time - job_start_time
        
        # วัด RAM/CPU หลังจบ job
        ram_mb_after = cpu_percent_after = None
        try:
            import psutil
            proc = psutil.Process()
            ram_mb_after = proc.memory_info().rss / (1024 * 1024)
            cpu_percent_after = psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.debug(f"Could not get final resource stats: {e}")
        
        logger.info(f"✅ Live chunk job {session_id} completed successfully")
        logger.info(f"   Duration: {job_duration:.2f}s, Meeting: {meeting_id}, Chunk: {chunk_index}")
        if ram_mb_before is not None and ram_mb_after is not None:
            delta_mb = ram_mb_after - ram_mb_before
            logger.info(f"   RAM: {ram_mb_after:.1f} MB (delta: {delta_mb:+.1f} MB) | CPU before/after: {cpu_percent_before or '-'}% / {cpu_percent_after or '-'}%")
        
        return {
            "status": "completed",
            "session_id": session_id,
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "duration": job_duration,
            "ram_mb": round(ram_mb_after, 2) if ram_mb_after is not None else None,
            "ram_delta_mb": round(ram_mb_after - ram_mb_before, 2) if (ram_mb_after is not None and ram_mb_before is not None) else None,
            "cpu_percent_after": round(cpu_percent_after, 1) if cpu_percent_after is not None else None,
        }
        
    except Exception as e:
        job_end_time = time.time()
        job_duration = job_end_time - job_start_time
        
        logger.error(f"❌ Error processing live chunk job {session_id}: {e}", exc_info=True)
        logger.error(f"   Duration: {job_duration:.2f}s, Meeting: {meeting_id}, Chunk: {chunk_index}")
        
        return {
            "status": "failed",
            "session_id": session_id,
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "error": str(e),
            "duration": job_duration
        }

logger.info("✅ RQ Worker module loaded")

