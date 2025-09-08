"""
Webhook API Endpoints
สำหรับจัดการ webhook subscriptions และ notifications
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict
import logging
import uuid

from ..services.webhook_service import webhook_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

class WebhookSubscriptionRequest(BaseModel):
    url: HttpUrl
    events: List[str]
    secret: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

class WebhookSubscriptionResponse(BaseModel):
    subscription_id: str
    url: str
    events: List[str]
    status: str
    created_at: str
    success_count: int
    error_count: int

class WebhookTestRequest(BaseModel):
    subscription_id: str
    event_type: str = "test"
    test_data: Optional[Dict] = None

@router.post("/subscribe")
async def create_webhook_subscription(request: WebhookSubscriptionRequest):
    """
    สมัครรับ webhook notifications
    
    **Supported Events:**
    - `transcription.started` - เริ่ม transcription
    - `transcription.progress` - progress updates (ทุก 10% หรือเปลี่ยน stage)
    - `transcription.completed` - transcription เสร็จ
    - `transcription.failed` - transcription ล้มเหลว
    - `file.uploaded` - มีไฟล์ใหม่ถูกอัปโหลด
    - `*` - รับทุก events
    
    **Webhook Payload Format:**
    ```json
    {
      "event": "transcription.completed",
      "timestamp": "2024-01-15T10:30:00Z",
      "task_id": "task-uuid",
      "data": {
        "task_id": "task-uuid",
        "status": "completed",
        "text_length": 1500,
        "chunks_count": 50
      }
    }
    ```
    
    **Security:**
    - ถ้าระบุ `secret` จะมี `X-Webhook-Signature` header
    - Signature format: `sha256=<hmac_hex>`
    """
    try:
        subscription_id = str(uuid.uuid4())
        
        result = webhook_service.subscribe(
            subscription_id=subscription_id,
            webhook_url=str(request.url),
            events=request.events,
            secret=request.secret,
            headers=request.headers
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to create webhook subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/subscribe/{subscription_id}")
async def delete_webhook_subscription(subscription_id: str):
    """ยกเลิกการสมัครรับ webhook"""
    try:
        success = webhook_service.unsubscribe(subscription_id)
        
        if success:
            return {
                "subscription_id": subscription_id,
                "status": "deleted",
                "message": "Webhook subscription deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Subscription not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete webhook subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscribe/{subscription_id}")
async def get_webhook_subscription(subscription_id: str):
    """ดูข้อมูลการสมัครรับ webhook"""
    try:
        subscription = webhook_service.get_subscription(subscription_id)
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return {
            "subscription_id": subscription["id"],
            "url": subscription["url"],
            "events": subscription["events"],
            "active": subscription["active"],
            "created_at": subscription["created_at"].isoformat(),
            "success_count": subscription["success_count"],
            "error_count": subscription["error_count"],
            "last_success": subscription["last_success"].isoformat() if subscription["last_success"] else None,
            "last_error": subscription["last_error"].isoformat() if subscription["last_error"] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get webhook subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscriptions")
async def list_webhook_subscriptions():
    """ดูรายการการสมัครรับ webhook ทั้งหมด"""
    try:
        subscriptions = webhook_service.list_subscriptions()
        
        result = []
        for sub in subscriptions:
            result.append({
                "subscription_id": sub["id"],
                "url": sub["url"],
                "events": sub["events"],
                "active": sub["active"],
                "created_at": sub["created_at"].isoformat(),
                "success_count": sub["success_count"],
                "error_count": sub["error_count"]
            })
        
        return {
            "subscriptions": result,
            "total": len(result)
        }
        
    except Exception as e:
        logger.error(f"Failed to list webhook subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def test_webhook(request: WebhookTestRequest):
    """
    ทดสอบการส่ง webhook
    
    ส่ง test event ไปยัง subscription เพื่อทดสอบการเชื่อมต่อ
    """
    try:
        subscription = webhook_service.get_subscription(request.subscription_id)
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        test_data = request.test_data or {
            "message": "This is a test webhook",
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        # ส่ง test webhook
        result = await webhook_service.send_webhook(
            event_type=request.event_type,
            data=test_data
        )
        
        return {
            "subscription_id": request.subscription_id,
            "test_result": result,
            "message": "Test webhook sent"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_webhook_stats():
    """สถิติการใช้งาน webhook"""
    try:
        stats = webhook_service.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get webhook stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-signature")
async def verify_webhook_signature(
    payload: str = Body(...),
    signature: str = Body(...),
    secret: str = Body(...)
):
    """
    ตรวจสอบ webhook signature
    
    ใช้สำหรับทดสอบการตรวจสอบ signature ในฝั่ง receiver
    """
    try:
        is_valid = webhook_service.verify_signature(payload, signature, secret)
        
        return {
            "valid": is_valid,
            "message": "Signature is valid" if is_valid else "Invalid signature"
        }
        
    except Exception as e:
        logger.error(f"Failed to verify signature: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Webhook Events Documentation
@router.get("/events")
async def get_webhook_events():
    """รายการ webhook events ที่รองรับ"""
    return {
        "events": {
            "transcription.started": {
                "description": "เริ่ม transcription process",
                "payload_example": {
                    "task_id": "task-uuid",
                    "file_path": "uploads/video.mp4",
                    "language": "th",
                    "status": "started"
                }
            },
            "transcription.progress": {
                "description": "Progress update (ทุก 10% หรือเปลี่ยน stage)",
                "payload_example": {
                    "task_id": "task-uuid",
                    "progress": 45,
                    "status": "processing_chunk_5_of_10",
                    "stage": "กำลังประมวลผล chunk 5/10"
                }
            },
            "transcription.completed": {
                "description": "Transcription เสร็จสมบูรณ์",
                "payload_example": {
                    "task_id": "task-uuid",
                    "status": "completed",
                    "text_length": 1500,
                    "chunks_count": 50,
                    "processing_stats": {
                        "total_chunks": 50,
                        "corrected_chunks": 15,
                        "correction_rate": 0.3
                    }
                }
            },
            "transcription.failed": {
                "description": "Transcription ล้มเหลว",
                "payload_example": {
                    "task_id": "task-uuid",
                    "status": "failed",
                    "error": "Audio extraction failed"
                }
            },
            "file.uploaded": {
                "description": "มีไฟล์ใหม่ถูกอัปโหลด",
                "payload_example": {
                    "file_path": "uploads/video.mp4",
                    "filename": "meeting_record.mp4",
                    "file_size": 1048576,
                    "file_type": ".mp4",
                    "duration": 600.0
                }
            }
        },
        "special_events": {
            "*": "รับทุก events (wildcard)"
        },
        "webhook_format": {
            "event": "event_type",
            "timestamp": "ISO 8601 timestamp",
            "task_id": "task UUID (if applicable)",
            "data": "event-specific data"
        },
        "security": {
            "signature_header": "X-Webhook-Signature",
            "signature_format": "sha256=<hmac_hex>",
            "algorithm": "HMAC-SHA256"
        }
    }
