"""
API endpoints สำหรับจัดการ RabbitMQ queue
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
import logging
import pika
import uuid
import json
import time

from ..services.rabbitmq_service import RabbitMQService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["Queue Management"])

def get_rabbitmq_service():
    """Get a fresh RabbitMQ service instance with active connection"""
    service = RabbitMQService()
    service._ensure_connection()
    return service

@router.get("/info")
async def get_queue_info():
    """ดึงข้อมูล queue ทั้งหมด"""
    try:
        rabbitmq_service = get_rabbitmq_service()
        queue_info = rabbitmq_service.get_queue_info()
        return {
            "message": "ดึงข้อมูล queue สำเร็จ",
            "queues": queue_info
        }
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล queue: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

@router.get("/status")
async def get_queue_status():
    """
    ตรวจสอบสถานะ queue และบอกว่าสามารถรับ request ใหม่ได้หรือไม่
    
    Returns:
        - available: True ถ้ายังรับ request ได้
        - slots_available: จำนวน slots ที่ว่าง
        - estimated_wait_time: เวลาที่คาดว่าจะรอ (วินาที)
    """
    try:
        import os
        queue_info = rabbitmq_service.get_queue_info()
        
        # Get queue limits from env
        MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))
        MAX_QUEUE_EXTRACTION = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
        MAX_QUEUE_TRANSCRIBE = int(os.getenv('MAX_QUEUE_TRANSCRIBE', '20'))
        
        # Get current queue sizes
        request_queue_info = queue_info.get('transcription_request_queue', {})
        extraction_queue_info = queue_info.get('audio_extraction_queue', {})
        transcription_queue_info = queue_info.get('transcription_queue', {})
        
        request_size = request_queue_info.get('message_count', 0)
        extraction_size = extraction_queue_info.get('message_count', 0)
        transcription_size = transcription_queue_info.get('message_count', 0)
        
        # Calculate available slots
        request_slots = MAX_QUEUE_REQUEST - request_size
        extraction_slots = MAX_QUEUE_EXTRACTION - extraction_size
        transcription_slots = MAX_QUEUE_TRANSCRIBE - transcription_size
        
        # Determine if available (all queues must have slots)
        available = (
            request_slots > 0 and 
            extraction_slots > 0 and 
            transcription_slots > 0
        )
        
        # Estimate wait time based on queue sizes and processing rate
        # Assume: 2 concurrent GPU tasks, ~20 min per 40-min video
        # Throughput: ~6 tasks/hour = 10 min/task average
        estimated_wait_time = 0
        if not available:
            # Estimate based on longest queue
            bottleneck_size = max(request_size, extraction_size, transcription_size)
            bottleneck_max = max(MAX_QUEUE_REQUEST, MAX_QUEUE_EXTRACTION, MAX_QUEUE_TRANSCRIBE)
            
            # Rough estimate: 10 minutes per task, 2 concurrent = 5 min per task in queue
            estimated_wait_time = (bottleneck_size * 5 * 60)  # seconds
        
        return {
            "available": available,
            "queues": {
                "request": {
                    "current": request_size,
                    "max": MAX_QUEUE_REQUEST,
                    "available_slots": request_slots,
                    "percentage": round((request_size / MAX_QUEUE_REQUEST) * 100, 1)
                },
                "extraction": {
                    "current": extraction_size,
                    "max": MAX_QUEUE_EXTRACTION,
                    "available_slots": extraction_slots,
                    "percentage": round((extraction_size / MAX_QUEUE_EXTRACTION) * 100, 1)
                },
                "transcription": {
                    "current": transcription_size,
                    "max": MAX_QUEUE_TRANSCRIBE,
                    "available_slots": transcription_slots,
                    "percentage": round((transcription_size / MAX_QUEUE_TRANSCRIBE) * 100, 1)
                }
            },
            "estimated_wait_time_seconds": estimated_wait_time,
            "estimated_wait_time_minutes": round(estimated_wait_time / 60, 1),
            "recommendation": (
                "You can submit new requests" if available 
                else f"Queue is full. Please wait approximately {round(estimated_wait_time / 60, 1)} minutes before retrying."
            )
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting queue status: {str(e)}")

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

@router.post("/test-flow")
async def test_queue_flow(count: int = 1):
    """
    ทดสอบการส่ง message ผ่าน flow ทั้งหมด (transcription_request_queue → audio_extraction_queue → transcription_queue)
    
    ส่ง test message เป็น string เพื่อทดสอบว่าระบบรับและส่งต่อได้ถูกต้อง
    โดยไม่ทำการ process จริง (ไม่ใช้ resource)
    
    Args:
        count: จำนวน test messages ที่ต้องการส่ง (default: 1)
    
    Returns:
        List of task IDs ที่ส่งไป
    """
    try:
        import uuid
        import json
        import time
        
        task_ids = []
        results = []
        
        for i in range(count):
            test_task_id = f"test-{uuid.uuid4()}"
            task_ids.append(test_task_id)
            
            # สร้าง test message
            test_message = {
                "task_id": test_task_id,
                "task_type": "transcription_request",
                "test_mode": True,  # Flag เพื่อบอกว่าเป็น test message
                "test_message": f"Test message #{i+1}",
                "file_path": None,
                "file_url": None,
                "file_name": f"test_file_{i+1}.mp4",
                "language": "th",
                "model_size": "base",
                "chunk_duration": 30,
                "use_chunking": False,
                "display_mode": "full_text",
                "status": "pending",
                "created_at": time.time(),
                "callback_url": None,
                "job_id": None,
                "user_id": "test_user"
            }
            
            try:
                # ใช้ send_transcription_request_task method ซึ่งมี retry logic และ connection handling
                # แต่เราต้องส่ง test message โดยตรงผ่าน connection
                # ใช้ method ที่มีอยู่แล้วใน rabbitmq_service แต่ส่ง test message โดยตรง
                from ..services.rabbitmq_service import RabbitMQService
                test_rabbitmq = RabbitMQService()
                
                # ใช้ send_transcription_request_task method ซึ่งมี retry logic
                # แต่ส่ง test message โดยตรงผ่าน internal method
                # ใช้ retry logic จาก send_transcription_request_task (3 retries)
                max_retries = 3
                retry_delay = 1
                
                for attempt in range(max_retries):
                    try:
                        # Reset connection if retrying
                        if attempt > 0:
                            test_rabbitmq._reset_connection()
                            time.sleep(retry_delay * attempt)
                        
                        # Connect
                        test_rabbitmq._connect()
                        
                        # Verify connection
                        if not test_rabbitmq.connection or test_rabbitmq.connection.is_closed:
                            raise Exception("Connection is closed after connect")
                        if not test_rabbitmq.channel or test_rabbitmq.channel.is_closed:
                            raise Exception("Channel is closed after connect")
                        
                        # Publish test message
                        test_rabbitmq.channel.basic_publish(
                            exchange='',
                            routing_key=test_rabbitmq.transcription_request_queue,
                            body=json.dumps(test_message),
                            properties=pika.BasicProperties(
                                delivery_mode=2,  # Persistent
                                content_type='application/json',
                                priority=5
                            ),
                            mandatory=True
                        )
                        
                        # Success - break out of retry loop
                        break
                        
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Publish attempt {attempt + 1}/{max_retries} failed: {e}, retrying...")
                        else:
                            raise
                
                logger.info(f"✅ Test message #{i+1} sent to transcription_request_queue: {test_task_id}")
                results.append({
                    "task_id": test_task_id,
                    "status": "sent",
                    "queue": "transcription_request_queue",
                    "message": f"Test message #{i+1} sent successfully"
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to send test message #{i+1}: {e}")
                results.append({
                    "task_id": test_task_id,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "message": f"Sent {len([r for r in results if r['status'] == 'sent'])}/{count} test messages",
            "total": count,
            "successful": len([r for r in results if r['status'] == 'sent']),
            "failed": len([r for r in results if r['status'] == 'failed']),
            "task_ids": task_ids,
            "results": results,
            "note": "Test messages will flow through: transcription_request_queue → audio_extraction_queue → transcription_queue"
        }
        
    except Exception as e:
        logger.error(f"Error in test_queue_flow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error testing queue flow: {str(e)}")

@router.get("/check-task/{task_id}")
async def check_task_in_queue(task_id: str):
    """
    ตรวจสอบ task ที่ค้างใน queue
    
    ตรวจสอบ:
    1. Task status จาก storage
    2. Queue status (audio_extraction_queue, transcription_queue, etc.)
    3. Worker status
    4. File existence
    """
    try:
        from ..utils.storage_factory import get_storage
        import subprocess
        from pathlib import Path
        
        result = {
            "task_id": task_id,
            "storage": {},
            "queues": {},
            "worker": {},
            "file": {},
            "recommendations": []
        }
        
        # 1. ตรวจสอบจาก Storage
        storage = get_storage()
        task_data = storage.load_transcription(task_id)
        
        if task_data:
            result["storage"] = {
                "found": True,
                "status": task_data.get('status', 'unknown'),
                "progress": task_data.get('progress', 0),
                "created_at": task_data.get('created_at', 'N/A'),
                "updated_at": task_data.get('updated_at', 'N/A'),
                "current_stage": task_data.get('current_stage', 'N/A'),
                "stage_description": task_data.get('current_stage_description', 'N/A'),
                "file_path": task_data.get('file_path', 'N/A'),
                "error_message": task_data.get('error_message')
            }
        else:
            result["storage"] = {"found": False}
            result["recommendations"].append("⚠️ Task ไม่พบใน storage - อาจถูกลบหรือยังไม่ถูกสร้าง")
        
        # 2. ตรวจสอบ Queue Status
        queue_info = rabbitmq_service.get_queue_info()
        
        # ตรวจสอบ audio_extraction_queue
        audio_extraction_queue = queue_info.get('audio_extraction_queue', {})
        result["queues"]["audio_extraction_queue"] = {
            "messages_ready": audio_extraction_queue.get('message_count', 0),
            "consumers": audio_extraction_queue.get('consumer_count', 0),
            "unacked": audio_extraction_queue.get('messages_unacknowledged', 0)
        }
        
        if audio_extraction_queue.get('consumer_count', 0) == 0:
            result["recommendations"].append("❌ audio_extraction_queue ไม่มี consumer - ต้อง restart Video Worker")
        
        if audio_extraction_queue.get('messages_unacknowledged', 0) > 0:
            result["recommendations"].append("⚠️ มี messages ที่ยังไม่ acknowledged - อาจมี task ที่กำลัง process")
        
        # ตรวจสอบ transcription_queue
        transcription_queue = queue_info.get('transcription_queue', {})
        result["queues"]["transcription_queue"] = {
            "messages_ready": transcription_queue.get('message_count', 0),
            "consumers": transcription_queue.get('consumer_count', 0),
            "unacked": transcription_queue.get('messages_unacknowledged', 0)
        }
        
        # 3. ตรวจสอบ Worker Status
        try:
            worker_result = subprocess.run(
                ["pgrep", "-f", "python.*video_worker"],
                capture_output=True,
                text=True
            )
            if worker_result.returncode == 0:
                pids = worker_result.stdout.strip().split('\n')
                result["worker"] = {
                    "running": True,
                    "pids": pids
                }
            else:
                result["worker"] = {"running": False}
                result["recommendations"].append("❌ Video Worker ไม่ทำงาน - ต้อง restart")
        except Exception as e:
            result["worker"] = {"error": str(e)}
        
        # 4. ตรวจสอบ File
        if task_data and task_data.get('file_path'):
            file_path = task_data.get('file_path')
            if Path(file_path).exists():
                size = Path(file_path).stat().st_size / (1024 * 1024)  # MB
                result["file"] = {
                    "exists": True,
                    "path": file_path,
                    "size_mb": round(size, 2)
                }
            else:
                result["file"] = {
                    "exists": False,
                    "path": file_path
                }
                result["recommendations"].append("❌ ไฟล์ไม่พบ - Task อาจจะ fail แล้ว")
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking task: {str(e)}") 