#!/usr/bin/env python3
"""
Script สำหรับรัน Video Worker
"""

import os
import sys
import logging
import signal
from pathlib import Path

# เพิ่ม app directory เข้าไปใน Python path
sys.path.append(str(Path(__file__).parent))

from app.workers.video_worker import VideoWorker

def setup_logging():
    """ตั้งค่า logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('worker.log')
        ]
    )

def main():
    """Main function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("เริ่มต้น Video Worker...")
    
    # สร้าง worker
    worker = VideoWorker()
    
    try:
        # รัน worker
        worker.run()
    except KeyboardInterrupt:
        logger.info("ได้รับ interrupt signal")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน worker: {e}")
    finally:
        logger.info("Video Worker ปิดตัวลง")

if __name__ == "__main__":
    main() 