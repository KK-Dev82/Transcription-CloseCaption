#!/usr/bin/env python3
"""
Immediate Redis Cleanup Script
ลบ Redis keys ที่ค้างอยู่ทันที (ไม่รอ TTL)

Usage:
    python scripts/cleanup_redis_immediate.py
    python scripts/cleanup_redis_immediate.py --dry-run  # แค่ดูว่าจะลบอะไร
"""
import os
import sys
import redis
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_redis_keys(redis_url: str, dry_run: bool = False) -> Dict:
    """
    Cleanup Redis keys ที่ค้างอยู่
    
    Args:
        redis_url: Redis connection URL
        dry_run: ถ้า True จะแค่แสดงว่าจะลบอะไร ไม่ลบจริง
    
    Returns:
        Dict with cleanup statistics
    """
    conn = redis.from_url(redis_url, decode_responses=True)
    
    stats = {
        "task_keys_deleted": 0,
        "chunk_keys_deleted": 0,
        "rq_jobs_cleaned": 0,
        "total_keys_before": conn.dbsize(),
        "errors": []
    }
    
    logger.info("=" * 70)
    logger.info("🧹 Starting Immediate Redis Cleanup")
    logger.info(f"   Dry run: {dry_run}")
    logger.info(f"   Total keys before: {stats['total_keys_before']}")
    logger.info("=" * 70)
    logger.info("")
    
    # 1. Cleanup task keys ที่ไม่มี TTL หรือ TTL มากกว่า 1 ชั่วโมง
    logger.info("📋 Step 1: Cleaning up task keys...")
    try:
        task_keys = conn.keys("task:*")
        logger.info(f"   Found {len(task_keys)} task keys")
        
        deleted_task_keys = []
        for key in task_keys:
            ttl = conn.ttl(key)
            # ลบถ้าไม่มี TTL หรือ TTL มากกว่า 1 ชั่วโมง (3600s)
            if ttl == -1 or ttl > 3600:
                if not dry_run:
                    conn.delete(key)
                deleted_task_keys.append(key)
                stats["task_keys_deleted"] += 1
        
        if deleted_task_keys:
            logger.info(f"   {'Would delete' if dry_run else 'Deleted'} {len(deleted_task_keys)} task keys")
            if len(deleted_task_keys) <= 10:
                for key in deleted_task_keys:
                    logger.info(f"      - {key}")
            else:
                for key in deleted_task_keys[:5]:
                    logger.info(f"      - {key}")
                logger.info(f"      ... and {len(deleted_task_keys) - 5} more")
        else:
            logger.info("   No task keys to delete")
    except Exception as e:
        error_msg = f"Error cleaning task keys: {e}"
        logger.error(f"   ❌ {error_msg}")
        stats["errors"].append(error_msg)
    
    logger.info("")
    
    # 2. Cleanup chunk keys
    logger.info("📦 Step 2: Cleaning up chunk keys...")
    try:
        chunk_keys = conn.keys("task:*:chunk:*")
        logger.info(f"   Found {len(chunk_keys)} chunk keys")
        
        deleted_chunk_keys = []
        for key in chunk_keys:
            ttl = conn.ttl(key)
            # ลบถ้าไม่มี TTL หรือ TTL มากกว่า 1 ชั่วโมง
            if ttl == -1 or ttl > 3600:
                if not dry_run:
                    conn.delete(key)
                deleted_chunk_keys.append(key)
                stats["chunk_keys_deleted"] += 1
        
        if deleted_chunk_keys:
            logger.info(f"   {'Would delete' if dry_run else 'Deleted'} {len(deleted_chunk_keys)} chunk keys")
        else:
            logger.info("   No chunk keys to delete")
    except Exception as e:
        error_msg = f"Error cleaning chunk keys: {e}"
        logger.error(f"   ❌ {error_msg}")
        stats["errors"].append(error_msg)
    
    logger.info("")
    
    # 3. Cleanup RQ finished/failed jobs (เก่ากว่า 1 ชั่วโมง)
    logger.info("📊 Step 3: Cleaning up RQ jobs...")
    try:
        from rq import Queue
        from rq.registry import FinishedJobRegistry, FailedJobRegistry
        from rq.job import Job
        
        # Cleanup finished jobs
        finished_registry = FinishedJobRegistry(connection=conn)
        finished_job_ids = finished_registry.get_job_ids()
        logger.info(f"   Found {len(finished_job_ids)} finished jobs")
        
        cutoff_time = datetime.now() - timedelta(hours=1)
        cleaned_finished = 0
        for job_id in finished_job_ids:
            try:
                job = Job.fetch(job_id, connection=conn)
                if job.ended_at and job.ended_at < cutoff_time:
                    if not dry_run:
                        finished_registry.remove(job_id, ttl=-1)
                        job.delete()
                    cleaned_finished += 1
            except Exception as e:
                pass  # Job อาจถูกลบไปแล้ว
        
        if cleaned_finished > 0:
            logger.info(f"   {'Would clean' if dry_run else 'Cleaned'} {cleaned_finished} finished jobs")
        
        # Cleanup failed jobs
        failed_registry = FailedJobRegistry(connection=conn)
        failed_job_ids = failed_registry.get_job_ids()
        logger.info(f"   Found {len(failed_job_ids)} failed jobs")
        
        cleaned_failed = 0
        for job_id in failed_job_ids:
            try:
                job = Job.fetch(job_id, connection=conn)
                if job.ended_at and job.ended_at < cutoff_time:
                    if not dry_run:
                        failed_registry.remove(job_id, ttl=-1)
                        job.delete()
                    cleaned_failed += 1
            except Exception as e:
                pass  # Job อาจถูกลบไปแล้ว
        
        if cleaned_failed > 0:
            logger.info(f"   {'Would clean' if dry_run else 'Cleaned'} {cleaned_failed} failed jobs")
        
        stats["rq_jobs_cleaned"] = cleaned_finished + cleaned_failed
        
        if stats["rq_jobs_cleaned"] == 0:
            logger.info("   No RQ jobs to clean")
    except Exception as e:
        error_msg = f"Error cleaning RQ jobs: {e}"
        logger.error(f"   ❌ {error_msg}")
        stats["errors"].append(error_msg)
    
    logger.info("")
    
    # 4. Summary
    stats["total_keys_after"] = conn.dbsize() if not dry_run else stats["total_keys_before"]
    stats["total_deleted"] = stats["task_keys_deleted"] + stats["chunk_keys_deleted"]
    
    logger.info("=" * 70)
    logger.info("📊 Cleanup Summary")
    logger.info("=" * 70)
    logger.info(f"   Task keys deleted: {stats['task_keys_deleted']}")
    logger.info(f"   Chunk keys deleted: {stats['chunk_keys_deleted']}")
    logger.info(f"   RQ jobs cleaned: {stats['rq_jobs_cleaned']}")
    logger.info(f"   Total keys before: {stats['total_keys_before']}")
    logger.info(f"   Total keys after: {stats['total_keys_after']}")
    logger.info(f"   Keys freed: {stats['total_keys_before'] - stats['total_keys_after']}")
    if stats["errors"]:
        logger.warning(f"   Errors: {len(stats['errors'])}")
        for error in stats["errors"]:
            logger.warning(f"      - {error}")
    logger.info("=" * 70)
    
    return stats


def main():
    """Main function"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv or '-d' in sys.argv
    
    if dry_run:
        logger.info("🔍 DRY RUN MODE - No keys will be deleted")
        logger.info("")
    
    try:
        stats = cleanup_redis_keys(redis_url, dry_run=dry_run)
        
        if dry_run:
            logger.info("")
            logger.info("💡 To actually delete keys, run without --dry-run flag")
            logger.info("   python scripts/cleanup_redis_immediate.py")
        else:
            logger.info("")
            logger.info("✅ Cleanup completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
