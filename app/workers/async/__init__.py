"""
Async Workers - ใช้ aio-pika (async) สำหรับ RabbitMQ
"""
from .video_worker import VideoWorkerAsync

__all__ = ['VideoWorkerAsync']

