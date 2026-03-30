"""
On Hold Release Service
Trigger การ release tasks ที่ on_hold เมื่อ record_backlog == 0

ปัญหา: _try_release_on_hold_tasks ใน rq_worker ถูกเรียกเฉพาะเมื่อ chunk เสร็จ
→ ถ้าทุก task on_hold (ไม่มี chunk รัน) จะไม่มี trigger → ค้างตลอด

แก้: เรียก try_release_on_hold_tasks() เป็นระยะจาก StuckTaskMonitor
"""
import os
import json
import logging
from redis import Redis

logger = logging.getLogger(__name__)


def try_release_on_hold_tasks() -> int:
    """
    ตรวจสอบ record_backlog == 0 แล้ว release tasks ที่ on_hold
    เรียกได้จาก StuckTaskMonitor (periodic) หรือที่อื่น
    
    Returns: จำนวน tasks ที่ release ได้
    """
    released = 0
    try:
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            return 0
        
        conn = Redis.from_url(redis_url, decode_responses=True)
        from app.services.redis_queue_service import get_redis_queue_service
        queue_svc = get_redis_queue_service()
        
        if queue_svc.get_record_backlog_count() > 0:
            return 0
        
        task_ids = conn.smembers("tasks:on_hold")
        if not task_ids:
            return 0
        
        ttl_seconds = int(os.getenv('REDIS_CHUNK_TTL_SECONDS', '43200'))
        
        for main_task_id in task_ids:
            if conn.get(f"task:{main_task_id}:paused"):
                continue
            if _do_claim_and_enqueue_next_chunk(
                conn, main_task_id, queue_svc, ttl_seconds
            ):
                conn.srem("tasks:on_hold", main_task_id)
                conn.delete(f"task:{main_task_id}:on_hold")
                _update_task_stage(main_task_id)
                released += 1
                logger.info(f"▶️ Released task {main_task_id} from On Hold (periodic trigger)")
        
        return released
    except Exception as e:
        logger.warning(f"⚠️ Error releasing on_hold tasks: {e}", exc_info=True)
        return released


def _do_claim_and_enqueue_next_chunk(conn, main_task_id: str, queue_svc, ttl_seconds: int) -> bool:
    """Claim next chunk และ enqueue"""
    try:
        from app.workers.lua_scripts import CLAIM_NEXT_CHUNK_INDEX_SCRIPT
        from app.services.close_caption_config import get_transcription_model_display
        
        chunks_metadata_key = f"task:{main_task_id}:chunks_metadata"
        inflight_key = f"task:{main_task_id}:inflight_chunks"
        enqueued_guard_prefix = f"task:{main_task_id}:enqueued"
        inflight_limit = int(os.getenv('CHUNK_INFLIGHT_LIMIT_PER_JOB', '2'))
        
        claim_script = conn.register_script(CLAIM_NEXT_CHUNK_INDEX_SCRIPT)
        result = claim_script(
            keys=[chunks_metadata_key, inflight_key, enqueued_guard_prefix],
            args=[inflight_limit, ttl_seconds]
        )
        claimed_index = result[0] if result and len(result) >= 2 else None
        if claimed_index is None:
            return False
        
        chunks_metadata_str = conn.get(chunks_metadata_key)
        if not chunks_metadata_str:
            return False
        chunks_metadata = json.loads(chunks_metadata_str)
        chunk_paths = chunks_metadata.get("chunk_paths", [])
        if claimed_index >= len(chunk_paths):
            return False
        
        language = chunks_metadata.get("language", "th")
        model_size = chunks_metadata.get("model_size") or get_transcription_model_display()
        chunk_duration = chunks_metadata.get("chunk_duration", 150)
        source = chunks_metadata.get("source", "upload")
        num_gpus = int(os.getenv('NUM_GPUS', '1'))
        
        next_chunk_path = chunk_paths[claimed_index]
        next_chunk_task_id = f"{main_task_id}_chunk_{claimed_index}"
        gpu_index = claimed_index % num_gpus
        worker_gpu = f'gpu{gpu_index}'
        
        queue_svc.enqueue_transcription(
            task_id=next_chunk_task_id,
            file_path=next_chunk_path,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration,
            priority=False,
            worker_gpu=worker_gpu,
            source=source
        )
        return True
    except Exception as e:
        logger.warning(f"⚠️ Error claim+enqueue for {main_task_id}: {e}")
        return False


def _update_task_stage(task_id: str):
    """อัปเดต task status เป็น processing"""
    try:
        from app.utils.storage_factory import get_storage
        storage = get_storage()

        from datetime import datetime, timezone
        task = storage.load_transcription(task_id)
        if not task:
            return
        task["status"] = "processing"
        task["current_stage"] = "transcribing"
        task["current_stage_description"] = "กำลังแปลงเสียงเป็นข้อความ (ต่อจาก On Hold)"
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        storage.save_transcription(task_id, task)
    except Exception as e:
        logger.warning(f"⚠️ Error updating task stage for {task_id}: {e}")
