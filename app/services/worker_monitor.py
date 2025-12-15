"""
Worker Monitor Service - Auto-restart Video Worker เมื่อไม่ทำงาน
"""

import logging
import subprocess
import time
import asyncio
import os
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkerMonitor:
    """Monitor และ auto-restart Video Worker"""
    
    def __init__(self, check_interval: int = 60, max_restart_attempts: int = 5):
        """
        Args:
            check_interval: ตรวจสอบทุก N วินาที (default: 60)
            max_restart_attempts: จำนวนครั้งสูงสุดที่ restart ต่อชั่วโมง (default: 5)
        """
        self.check_interval = check_interval
        self.max_restart_attempts = max_restart_attempts
        self.restart_history = []  # [(timestamp, success), ...]
        self.running = False
        self._monitor_task = None
    
    def is_worker_running(self) -> bool:
        """ตรวจสอบว่า Video Worker กำลังทำงานอยู่หรือไม่"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "python.*video_worker"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() != ""
        except Exception as e:
            logger.warning(f"Error checking worker status: {e}")
            return False
    
    def get_queue_consumer_count(self, queue_name: str = "audio_extraction_queue") -> int:
        """ตรวจสอบจำนวน consumers ใน queue"""
        try:
            from .rabbitmq_service import RabbitMQService
            rabbitmq = RabbitMQService()
            queue_info = rabbitmq.get_queue_info()
            queue = queue_info.get(queue_name, {})
            return queue.get('consumer_count', 0)
        except Exception as e:
            logger.warning(f"Error checking queue consumers: {e}")
            return 0
    
    def should_restart(self) -> bool:
        """ตรวจสอบว่าควร restart worker หรือไม่"""
        # 1. ตรวจสอบว่า worker ทำงานอยู่หรือไม่
        if not self.is_worker_running():
            logger.warning("⚠️ Video Worker ไม่ทำงาน")
            return True
        
        # 2. ตรวจสอบว่า queue มี consumer หรือไม่
        # แต่ต้องรอให้ worker start เสร็จก่อน (worker ใช้เวลา ~10-15 วินาทีในการลงทะเบียน consumer)
        # ตรวจสอบว่า worker process ทำงานมานานแค่ไหน
        worker_age = self._get_worker_process_age()
        if worker_age < 20:  # ถ้า worker start มาไม่ถึง 20 วินาที ให้รอ
            logger.debug(f"⏳ Worker กำลัง start (age: {worker_age}s) - รอให้ลงทะเบียน consumer...")
            return False
        
        consumer_count = self.get_queue_consumer_count()
        if consumer_count == 0:
            logger.warning(f"⚠️ Queue ไม่มี consumer (consumer_count={consumer_count}, worker_age={worker_age}s)")
            return True
        
        return False
    
    def _get_worker_process_age(self) -> float:
        """ตรวจสอบว่า worker process ทำงานมานานแค่ไหน (วินาที)"""
        try:
            result = subprocess.run(
                ["ps", "-o", "etime=", "-p", str(self._get_worker_pid())],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse elapsed time (format: DD-HH:MM:SS or HH:MM:SS or MM:SS)
                etime = result.stdout.strip()
                parts = etime.split(':')
                if len(parts) == 3:  # DD-HH:MM:SS
                    days, hours, minutes = map(int, parts[0].split('-')) if '-' in parts[0] else (0, int(parts[0]), int(parts[1]))
                    seconds = int(parts[2])
                    return days * 86400 + hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    return int(parts[0]) * 60 + int(parts[1])
                else:
                    return int(parts[0])  # SS
            return 0
        except Exception as e:
            logger.debug(f"Error getting worker age: {e}")
            return 0
    
    def _get_worker_pid(self) -> Optional[int]:
        """หา PID ของ Video Worker"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "python.*video_worker"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split('\n')[0])
            return None
        except Exception:
            return None
    
    def can_restart(self) -> bool:
        """ตรวจสอบว่าสามารถ restart ได้หรือไม่ (จำกัดจำนวนครั้ง)"""
        now = datetime.now()
        # ลบ restart history ที่เก่ากว่า 1 ชั่วโมง
        self.restart_history = [
            ts for ts in self.restart_history
            if now - ts < timedelta(hours=1)
        ]
        
        # ตรวจสอบว่ายังไม่เกินจำนวนครั้งสูงสุด
        if len(self.restart_history) >= self.max_restart_attempts:
            logger.warning(
                f"⚠️ ถึงจำนวนครั้งสูงสุดในการ restart แล้ว ({self.max_restart_attempts} ครั้ง/ชั่วโมง)"
            )
            return False
        
        return True
    
    def restart_worker(self) -> bool:
        """Restart Video Worker"""
        try:
            logger.info("🔄 กำลัง restart Video Worker...")
            
            # หา script path
            script_path = Path(__file__).parent.parent.parent / "scripts" / "pod" / "restart-service-daemon.sh"
            
            if not script_path.exists():
                logger.error(f"❌ Script not found: {script_path}")
                return False
            
            # Execute restart script
            process = subprocess.Popen(
                ["bash", str(script_path), "8010"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(script_path.parent.parent.parent)
            )
            
            # Wait for completion (max 30 seconds)
            try:
                stdout, stderr = process.communicate(timeout=30)
                if process.returncode == 0:
                    logger.info("✅ Video Worker restarted successfully")
                    self.restart_history.append(datetime.now())
                    return True
                else:
                    logger.error(f"❌ Restart failed: {stderr.decode()}")
                    return False
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Restart script timeout - process may still be running")
                # Don't kill - let it continue
                self.restart_history.append(datetime.now())
                return True  # Assume success if script started
                
        except Exception as e:
            logger.error(f"❌ Error restarting worker: {e}", exc_info=True)
            return False
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🚀 Starting Worker Monitor...")
        logger.info(f"   Check interval: {self.check_interval} seconds")
        logger.info(f"   Max restart attempts: {self.max_restart_attempts} per hour")
        
        while self.running:
            try:
                if self.should_restart():
                    if self.can_restart():
                        logger.warning("⚠️ Worker health check failed - attempting restart...")
                        success = self.restart_worker()
                        if success:
                            logger.info("✅ Worker restart initiated")
                            # Wait longer after restart
                            await asyncio.sleep(30)
                        else:
                            logger.error("❌ Failed to restart worker")
                    else:
                        logger.error(
                            "❌ Cannot restart worker - exceeded max attempts. "
                            "Please check manually."
                        )
                else:
                    logger.debug("✅ Worker health check passed")
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def start(self):
        """Start monitoring (non-blocking)"""
        if self.running:
            logger.warning("Monitor is already running")
            return
        
        self.running = True
        self._monitor_task = asyncio.create_task(self.monitor_loop())
        logger.info("✅ Worker Monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("⏹️ Worker Monitor stopped")


# Global instance
_worker_monitor: Optional[WorkerMonitor] = None


def get_worker_monitor() -> WorkerMonitor:
    """Get or create global worker monitor instance"""
    global _worker_monitor
    if _worker_monitor is None:
        check_interval = int(os.getenv('WORKER_MONITOR_INTERVAL', '60'))
        max_attempts = int(os.getenv('WORKER_MONITOR_MAX_RESTARTS', '5'))
        _worker_monitor = WorkerMonitor(
            check_interval=check_interval,
            max_restart_attempts=max_attempts
        )
    return _worker_monitor

