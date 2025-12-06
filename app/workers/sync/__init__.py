"""
Sync Workers - ใช้ pika (blocking) สำหรับ RabbitMQ
"""
from .video_worker import VideoWorkerPika

__all__ = ['VideoWorkerPika']

