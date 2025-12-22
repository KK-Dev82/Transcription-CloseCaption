"""
Workers package สำหรับการประมวลผลวิดีโอแบบ asynchronous
"""

# Lazy import: ไม่ import จนกว่าจะเรียกใช้จริงๆ
# เพื่อลด noise ใน logs เมื่อ module ถูก import แต่ไม่ได้ใช้ (เช่น RQ worker)
def __getattr__(name):
    """Lazy import VideoWorker class"""
    if name == 'VideoWorker':
        from .video_worker import VideoWorker
        return VideoWorker
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
 
__all__ = ['VideoWorker'] 