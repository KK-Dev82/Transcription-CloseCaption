"""
Video Worker Wrapper - เลือกใช้ worker ตาม VIDEO_WORKER_TYPE environment variable

Usage:
    VIDEO_WORKER_TYPE=pika    # ใช้ worker เดิม (blocking - pika)
    VIDEO_WORKER_TYPE=async   # ใช้ worker ใหม่ (async - aio-pika)

Default: pika (backward compatible)
"""
import os
import sys
import logging
from pathlib import Path

# เพิ่ม app directory เข้าไปใน Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass

logger = logging.getLogger(__name__)

# ตรวจสอบ worker type จาก environment variable
WORKER_TYPE = os.getenv('VIDEO_WORKER_TYPE', 'pika').lower()

if WORKER_TYPE == 'async':
    logger.info("🔧 Using Async Worker (aio-pika)")
    try:
        # ใช้ importlib เพราะ 'async' เป็น keyword ใน Python
        import importlib
        async_module = importlib.import_module('app.workers.async.video_worker')
        VideoWorker = async_module.VideoWorkerAsync
    except ImportError as e:
        logger.error(f"❌ Failed to import async worker: {e}")
        logger.warning("⚠️ Falling back to pika worker")
        from app.workers.sync.video_worker import VideoWorkerPika as VideoWorker
        WORKER_TYPE = 'pika'
else:
    logger.info("🔧 Using Pika Worker (blocking)")
    try:
        from app.workers.sync.video_worker import VideoWorkerPika as VideoWorker
    except ImportError as e:
        logger.error(f"❌ Failed to import pika worker: {e}")
        logger.error("💡 Make sure app/workers/sync/video_worker.py exists")
        sys.exit(1)

def main():
    """Main function สำหรับรัน worker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting Video Worker (Type: {WORKER_TYPE.upper()})")
    logger.info("=" * 80)
    
    worker = VideoWorker()
    
    if WORKER_TYPE == 'async':
        import asyncio
        logger.info("🔄 Running async worker...")
        try:
            asyncio.run(worker.start())
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน async worker: {e}", exc_info=True)
    else:
        logger.info("🔄 Running pika worker...")
        try:
            worker.run()
        except KeyboardInterrupt:
            logger.info("ได้รับ interrupt signal")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน pika worker: {e}", exc_info=True)
        finally:
            if hasattr(worker, 'cleanup'):
                worker.cleanup()

if __name__ == "__main__":
    main() 
