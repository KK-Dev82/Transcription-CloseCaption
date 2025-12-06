"""
Sync Workers - ใช้ pika (blocking) สำหรับ RabbitMQ
"""
from .video_worker import VideoWorkerSync

__all__ = ['VideoWorkerSync']

