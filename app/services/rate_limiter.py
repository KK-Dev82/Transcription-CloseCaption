"""
Rate Limiter Service สำหรับจำกัดจำนวน Concurrent Requests
ใช้ Redis atomic operations เพื่อความปลอดภัยใน multi-process environment
"""
import os
import logging
from typing import Optional
from contextlib import contextmanager
from redis import Redis
from pathlib import Path

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

class RateLimiter:
    """Rate Limiter สำหรับจำกัดจำนวน concurrent requests"""
    
    def __init__(self, max_concurrent: int = 25, redis_url: Optional[str] = None):
        """
        Initialize Rate Limiter
        
        Args:
            max_concurrent: จำนวน concurrent requests สูงสุด (default: 25)
            redis_url: Redis URL (ถ้าไม่ระบุจะใช้ REDIS_URL จาก env)
        """
        self.max_concurrent = max_concurrent
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_conn: Optional[Redis] = None
        self.counter_key = "transcription:concurrent_requests"
        self._connect()
    
    def _connect(self):
        """เชื่อมต่อ Redis"""
        try:
            self.redis_conn = Redis.from_url(self.redis_url, decode_responses=True)
            self.redis_conn.ping()
            logger.info(f"✅ Rate Limiter connected to Redis: {self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis for rate limiting: {e}")
            raise
    
    def get_current_count(self) -> int:
        """ดึงจำนวน concurrent requests ปัจจุบัน"""
        try:
            count = self.redis_conn.get(self.counter_key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"❌ Error getting current count: {e}")
            return 0
    
    def increment(self) -> int:
        """
        เพิ่มจำนวน concurrent requests (atomic operation)
        Returns: จำนวน requests หลังเพิ่ม
        """
        try:
            # ใช้ INCR เพื่อ atomic increment
            count = self.redis_conn.incr(self.counter_key)
            # Set expiration (1 hour) เพื่อป้องกัน counter ค้าง
            self.redis_conn.expire(self.counter_key, 3600)
            return count
        except Exception as e:
            logger.error(f"❌ Error incrementing counter: {e}")
            raise
    
    def decrement(self) -> int:
        """
        ลดจำนวน concurrent requests (atomic operation)
        Returns: จำนวน requests หลังลด
        """
        try:
            # ใช้ DECR เพื่อ atomic decrement
            count = self.redis_conn.decr(self.counter_key)
            # ถ้าน้อยกว่า 0 ให้ reset เป็น 0
            if count < 0:
                self.redis_conn.set(self.counter_key, 0)
                return 0
            return count
        except Exception as e:
            logger.error(f"❌ Error decrementing counter: {e}")
            return 0
    
    def can_accept_request(self) -> bool:
        """
        ตรวจสอบว่าสามารถรับ request ใหม่ได้หรือไม่
        Returns: True ถ้ายังไม่ถึง limit, False ถ้าเกิน limit
        """
        current = self.get_current_count()
        return current < self.max_concurrent
    
    @contextmanager
    def acquire(self):
        """
        Context manager สำหรับ acquire/release request slot
        Usage:
            with rate_limiter.acquire():
                # process request
                pass
        """
        current_count = self.increment()
        
        if current_count > self.max_concurrent:
            # ถ้าเกิน limit ให้ลด counter กลับ
            self.decrement()
            raise RateLimitExceeded(
                current_count=current_count - 1,
                max_concurrent=self.max_concurrent
            )
        
        try:
            yield current_count
        finally:
            # ลด counter เมื่อ request เสร็จ (ไม่ว่าจะสำเร็จหรือล้มเหลว)
            self.decrement()


class RateLimitExceeded(Exception):
    """Exception เมื่อเกิน rate limit"""
    
    def __init__(self, current_count: int, max_concurrent: int):
        self.current_count = current_count
        self.max_concurrent = max_concurrent
        self.message = f"ถึงจำนวนจำกัดแล้ว (มี {current_count}/{max_concurrent} requests กำลังประมวลผล) โปรดรอซักครู่"
        super().__init__(self.message)


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter(max_concurrent: Optional[int] = None) -> RateLimiter:
    """
    Get or create Rate Limiter singleton instance
    
    Args:
        max_concurrent: จำนวน concurrent requests สูงสุด (ถ้าไม่ระบุจะใช้จาก env หรือ default 25)
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        if max_concurrent is None:
            max_concurrent = int(os.getenv('MAX_CONCURRENT_REQUESTS', '25'))
        _rate_limiter = RateLimiter(max_concurrent=max_concurrent)
    
    return _rate_limiter


