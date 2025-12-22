"""
RQ Worker Module - Persistent Transcription Service
Init TranscriptionService ครั้งเดียวตอน import แทน init ทุก job
"""
import asyncio
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)

# ============================================================================
# Persistent Services (Init ครั้งเดียวตอน worker start)
# ============================================================================

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
        try:
            # พยายามใช้ existing loop ก่อน
            _event_loop = asyncio.get_event_loop()
            if _event_loop.is_closed():
                _event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_event_loop)
        except RuntimeError:
            # ถ้าไม่มี loop ให้สร้างใหม่
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
        
        # ตรวจสอบว่าเป็น chunk job หรือ full job
        # ถ้า task_id มี "_chunk_" แสดงว่าเป็น chunk job (ไม่ต้อง chunking อีก)
        is_chunk_job = "_chunk_" in task_id
        
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
        else:
            # Full job: ใช้ _process_transcription (จะ chunking เอง)
            logger.info(f"📝 Processing full transcription job")
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
        
        logger.info(f"✅ RQ Worker: Completed transcription job {task_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ RQ Worker: Error processing job {task_id}: {e}", exc_info=True)
        raise

# ============================================================================
# Module Initialization
# ============================================================================

# Pre-initialize services เมื่อ module ถูก import
# จะทำให้ worker process มี model พร้อมใช้ทันที
logger.info("📦 Loading RQ Worker module...")
try:
    # Pre-init service (optional - จะ init เมื่อ job แรกมาถึงก็ได้)
    # แต่ถ้า pre-init จะทำให้ job แรกเร็วขึ้น
    if os.getenv('RQ_PRELOAD_MODEL', 'false').lower() == 'true':
        logger.info("🔧 Pre-loading model (RQ_PRELOAD_MODEL=true)...")
        get_transcription_service()
        logger.info("✅ Model pre-loaded")
    else:
        logger.info("ℹ️  Model will be loaded on first job (lazy loading)")
except Exception as e:
    logger.warning(f"⚠️  Failed to pre-load model: {e} (will load on first job)")

logger.info("✅ RQ Worker module loaded")

