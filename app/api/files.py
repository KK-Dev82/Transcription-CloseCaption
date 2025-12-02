from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


class FileUploadedRequest(BaseModel):
    """Request model สำหรับรับ notification เมื่อมีการ upload ไฟล์"""
    file_id: str
    file_url: str  # URL ที่ Pod เข้าถึงได้ (ผ่าน Frontend Proxy)
    file_name: str
    uploaded_at: Optional[datetime] = None


@router.post("/uploaded")
async def notify_file_uploaded(request: FileUploadedRequest):
    """
    รับ notification เมื่อมีการ upload ไฟล์ (จาก Backend TUS)
    
    **URL Format:** 
    - `file_url` จะเป็น URL ที่ Pod เข้าถึงได้ผ่าน Frontend Proxy
    - ตัวอย่าง: `http://10.200.22.62/fileservice/api/files/{fileId}`
    
    **Flow:**
    1. Backend upload → FileService
    2. Backend ส่ง URL มาที่ Pod (endpoint นี้)
    3. Pod เก็บ URL ไว้ใช้ต่อไป (download เมื่อต้องการ)
    
    **หมายเหตุ:**
    - Endpoint นี้เป็น optional notification
    - Pod จะ download จาก URL เมื่อต้องการใช้จริง (transcription/trim)
    - ถ้า notification ไม่สำเร็จ ก็ไม่เป็นไร - Pod จะใช้ URL จาก Backend เมื่อต้องการ
    """
    try:
        logger.info(
            "📥 Received file upload notification: file_id={file_id}, file_name={file_name}, file_url={file_url}",
            extra={
                "file_id": request.file_id,
                "file_name": request.file_name,
                "file_url": request.file_url
            }
        )
        
        # Optional: บันทึกข้อมูลไฟล์ใน Pod (cache/pre-warm)
        # หรือไม่ต้องทำอะไรเลย - เพียงแค่ acknowledge
        
        # TODO: ถ้าต้องการ pre-warm สามารถทำได้ที่นี่
        # เช่น: download metadata, pre-load ไปยัง cache, etc.
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "File upload notification received",
                "file_id": request.file_id,
                "file_url": request.file_url
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling file upload notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error handling notification: {str(e)}")

