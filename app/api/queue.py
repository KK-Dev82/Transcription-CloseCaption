"""
API endpoints สำหรับจัดการ RabbitMQ queue
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging

from ..services.rabbitmq_service import RabbitMQService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["Queue Management"])
rabbitmq_service = RabbitMQService()

@router.get("/info")
async def get_queue_info():
    """ดึงข้อมูล queue ทั้งหมด"""
    try:
        queue_info = rabbitmq_service.get_queue_info()
        return {
            "message": "ดึงข้อมูล queue สำเร็จ",
            "queues": queue_info
        }
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.post("/purge/{queue_name}")
async def purge_queue(queue_name: str):
    """ลบ messages ทั้งหมดใน queue"""
    try:
        success = rabbitmq_service.purge_queue(queue_name)
        if success:
            return {
                "message": f"ลบ messages ใน queue {queue_name} เรียบร้อย",
                "queue_name": queue_name
            }
        else:
            raise HTTPException(status_code=400, detail=f"ไม่สามารถลบ queue {queue_name}")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบ queue: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/health")
async def check_queue_health():
    """ตรวจสอบสถานะของ RabbitMQ"""
    try:
        # ตรวจสอบการเชื่อมต่อ
        queue_info = rabbitmq_service.get_queue_info()
        
        # ตรวจสอบว่ามี queue ทั้งหมดหรือไม่
        expected_queues = [
            'video_trim_queue',
            'video_merge_queue', 
            'video_convert_queue',
            'video_resize_queue'
        ]
        
        available_queues = list(queue_info.keys())
        missing_queues = [q for q in expected_queues if q not in available_queues]
        
        if missing_queues:
            return {
                "status": "warning",
                "message": f"ขาด queue: {', '.join(missing_queues)}",
                "available_queues": available_queues,
                "missing_queues": missing_queues
            }
        else:
            return {
                "status": "healthy",
                "message": "RabbitMQ ทำงานปกติ",
                "available_queues": available_queues,
                "queue_info": queue_info
            }
            
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบ RabbitMQ: {e}")
        return {
            "status": "error",
            "message": f"ไม่สามารถเชื่อมต่อ RabbitMQ: {str(e)}",
            "available_queues": [],
            "missing_queues": expected_queues
        }

@router.get("/stats")
async def get_queue_stats():
    """ดึงสถิติของ queue"""
    try:
        queue_info = rabbitmq_service.get_queue_info()
        
        total_messages = sum(q['message_count'] for q in queue_info.values())
        total_consumers = sum(q['consumer_count'] for q in queue_info.values())
        
        stats = {
            "total_queues": len(queue_info),
            "total_messages": total_messages,
            "total_consumers": total_consumers,
            "queue_details": queue_info
        }
        
        return {
            "message": "ดึงสถิติ queue สำเร็จ",
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติ queue: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}") 