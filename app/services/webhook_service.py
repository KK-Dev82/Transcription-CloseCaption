"""
Webhook Service สำหรับส่ง real-time notifications
แทนการใช้ polling ให้ frontend รอรับ callback
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable
import aiohttp
import hashlib
import hmac
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.subscriptions: Dict[str, Dict] = {}
        self.retry_attempts = 3
        self.retry_delay = 5  # seconds
        self.timeout = 10  # seconds
        
    def subscribe(self, subscription_id: str, webhook_url: str, 
                 events: List[str], secret: Optional[str] = None,
                 headers: Optional[Dict[str, str]] = None) -> Dict:
        """
        สมัครรับ webhook notifications
        
        Args:
            subscription_id: ID ของการสมัคร
            webhook_url: URL ที่จะส่ง webhook
            events: รายการ events ที่ต้องการรับ
            secret: Secret key สำหรับ signature verification
            headers: Custom headers
        """
        try:
            # Validate URL
            parsed = urlparse(webhook_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid webhook URL")
            
            subscription = {
                "id": subscription_id,
                "url": webhook_url,
                "events": events,
                "secret": secret,
                "headers": headers or {},
                "created_at": datetime.now(),
                "active": True,
                "success_count": 0,
                "error_count": 0,
                "last_success": None,
                "last_error": None
            }
            
            self.subscriptions[subscription_id] = subscription
            logger.info(f"Webhook subscription created: {subscription_id} -> {webhook_url}")
            
            return {
                "subscription_id": subscription_id,
                "status": "active",
                "events": events,
                "message": "Webhook subscription created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create webhook subscription: {e}")
            raise
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """ยกเลิกการสมัครรับ webhook"""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            logger.info(f"Webhook subscription removed: {subscription_id}")
            return True
        return False
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict]:
        """ดูข้อมูลการสมัครรับ webhook"""
        return self.subscriptions.get(subscription_id)
    
    def list_subscriptions(self) -> List[Dict]:
        """ดูรายการการสมัครทั้งหมด"""
        return list(self.subscriptions.values())
    
    async def send_webhook(self, event_type: str, data: Dict, 
                          task_id: Optional[str] = None) -> Dict:
        """
        ส่ง webhook notification ไปยัง subscribers
        
        Args:
            event_type: ประเภทของ event
            data: ข้อมูลที่จะส่ง
            task_id: Task ID (optional)
        """
        results = []
        
        # หา subscriptions ที่สนใจ event นี้
        relevant_subs = [
            sub for sub in self.subscriptions.values()
            if sub["active"] and (event_type in sub["events"] or "*" in sub["events"])
        ]
        
        if not relevant_subs:
            logger.debug(f"No subscribers for event: {event_type}")
            return {"sent": 0, "results": []}
        
        # สร้าง payload
        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        if task_id:
            payload["task_id"] = task_id
        
        # ส่ง webhook แบบ concurrent
        tasks = []
        for subscription in relevant_subs:
            task = asyncio.create_task(
                self._send_single_webhook(subscription, payload)
            )
            tasks.append(task)
        
        # รอผลลัพธ์
        webhook_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # รวมผลลัพธ์
        for i, result in enumerate(webhook_results):
            subscription = relevant_subs[i]
            
            if isinstance(result, Exception):
                result = {
                    "subscription_id": subscription["id"],
                    "success": False,
                    "error": str(result)
                }
            
            results.append(result)
        
        successful = sum(1 for r in results if r.get("success", False))
        
        logger.info(f"Webhook sent for {event_type}: {successful}/{len(results)} successful")
        
        return {
            "event": event_type,
            "sent": len(results),
            "successful": successful,
            "results": results
        }
    
    async def _send_single_webhook(self, subscription: Dict, payload: Dict) -> Dict:
        """ส่ง webhook ไปยัง subscription เดียว"""
        subscription_id = subscription["id"]
        url = subscription["url"]
        
        try:
            # สร้าง headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "TranscriptionService-Webhook/1.0",
                **subscription.get("headers", {})
            }
            
            # สร้าง signature ถ้ามี secret
            if subscription.get("secret"):
                signature = self._create_signature(payload, subscription["secret"])
                headers["X-Webhook-Signature"] = signature
            
            # ส่ง HTTP request พร้อม retry
            for attempt in range(self.retry_attempts):
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                        async with session.post(url, json=payload, headers=headers) as response:
                            response_text = await response.text()
                            
                            if response.status < 400:
                                # Success
                                subscription["success_count"] += 1
                                subscription["last_success"] = datetime.now()
                                
                                return {
                                    "subscription_id": subscription_id,
                                    "success": True,
                                    "status_code": response.status,
                                    "response": response_text[:200],  # First 200 chars
                                    "attempt": attempt + 1
                                }
                            else:
                                # HTTP error
                                if attempt == self.retry_attempts - 1:
                                    raise aiohttp.ClientResponseError(
                                        request_info=response.request_info,
                                        history=response.history,
                                        status=response.status,
                                        message=response_text
                                    )
                                
                                # Retry after delay
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                
                except aiohttp.ClientError as e:
                    if attempt == self.retry_attempts - 1:
                        raise e
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        except Exception as e:
            # Failed after all retries
            subscription["error_count"] += 1
            subscription["last_error"] = datetime.now()

            logger.error(f"Webhook failed for {subscription_id}: {str(e)}")

            # บันทึกลง dead-letter table
            self._save_to_dead_letter(subscription, payload, str(e))

            return {
                "subscription_id": subscription_id,
                "success": False,
                "error": str(e),
                "attempts": self.retry_attempts
            }
    
    def _save_to_dead_letter(self, subscription: Dict, payload: Dict, error: str) -> None:
        """บันทึก webhook failure ลง dead-letter table"""
        try:
            import sqlite3
            import os
            from pathlib import Path
            db_path = os.getenv("SQLITE_DB_PATH", "storage/database.db")
            Path(db_path).parent.mkdir(exist_ok=True)
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_dead_letter (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    event_type TEXT,
                    payload TEXT,
                    webhook_url TEXT,
                    failed_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    resolved INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO webhook_dead_letter
                    (id, task_id, event_type, payload, webhook_url, failed_at, retry_count, last_error, resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                str(uuid.uuid4()),
                payload.get("task_id"),
                payload.get("event"),
                json.dumps(payload),
                subscription.get("url"),
                datetime.now().isoformat(),
                self.retry_attempts,
                error[:500],
            ))
            conn.commit()
            conn.close()
            logger.info(f"📬 Saved webhook failure to dead-letter: {subscription.get('url')}")
        except Exception as dl_err:
            logger.warning(f"Could not save to dead-letter: {dl_err}")

    def _create_signature(self, payload: Dict, secret: str) -> str:
        """สร้าง HMAC signature สำหรับ webhook verification"""
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """ตรวจสอบ webhook signature"""
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        expected = f"sha256={expected_signature}"
        
        return hmac.compare_digest(expected, signature)
    
    # Event helper methods
    async def notify_transcription_started(self, task_id: str, file_path: str, language: str):
        """แจ้งเตือนเมื่อเริ่ม transcription"""
        await self.send_webhook("transcription.started", {
            "task_id": task_id,
            "file_path": file_path,
            "language": language,
            "status": "started"
        }, task_id)
    
    async def notify_transcription_progress(self, task_id: str, progress: int, 
                                          status: str, stage: str):
        """แจ้งเตือน progress update"""
        await self.send_webhook("transcription.progress", {
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "stage": stage
        }, task_id)
    
    async def notify_transcription_completed(self, task_id: str, results: Dict):
        """แจ้งเตือนเมื่อ transcription เสร็จ"""
        await self.send_webhook("transcription.completed", {
            "task_id": task_id,
            "status": "completed",
            "text_length": len(results.get("text", "")),
            "chunks_count": len(results.get("chunks", [])),
            "processing_stats": results.get("thai_processing_stats")
        }, task_id)
    
    async def notify_transcription_failed(self, task_id: str, error: str):
        """แจ้งเตือนเมื่อ transcription ล้มเหลว"""
        await self.send_webhook("transcription.failed", {
            "task_id": task_id,
            "status": "failed",
            "error": error
        }, task_id)
    
    async def notify_file_uploaded(self, file_path: str, file_info: Dict):
        """แจ้งเตือนเมื่อมีไฟล์ใหม่ถูกอัปโหลด"""
        await self.send_webhook("file.uploaded", {
            "file_path": file_path,
            "filename": file_info.get("filename"),
            "file_size": file_info.get("file_size"),
            "file_type": file_info.get("file_type"),
            "duration": file_info.get("duration")
        })
    
    def get_stats(self) -> Dict:
        """สถิติการใช้งาน webhook"""
        total_subs = len(self.subscriptions)
        active_subs = sum(1 for sub in self.subscriptions.values() if sub["active"])
        total_success = sum(sub["success_count"] for sub in self.subscriptions.values())
        total_errors = sum(sub["error_count"] for sub in self.subscriptions.values())
        
        return {
            "total_subscriptions": total_subs,
            "active_subscriptions": active_subs,
            "total_webhooks_sent": total_success + total_errors,
            "successful_webhooks": total_success,
            "failed_webhooks": total_errors,
            "success_rate": total_success / max(1, total_success + total_errors)
        }


# Global webhook service instance
webhook_service = WebhookService()
