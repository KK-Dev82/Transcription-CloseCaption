"""
Helper Utilities (Pika - Blocking)

Helper functions สำหรับ worker: save chunk results, download files, connection maintenance
"""
import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)


class WorkerUtils:
    """Helper utilities สำหรับ worker"""
    
    def __init__(self, worker):
        """
        Initialize worker utils
        
        Args:
            worker: Worker instance ที่มี services, storage, connection, etc.
        """
        self.worker = worker
    
    def save_chunk_result(self, parent_task_id: str, chunk_index: int, chunk_data: Dict, total_chunks: int):
        """บันทึกผลลัพธ์ของ chunk ลง storage"""
        try:
            from datetime import datetime, timezone
            
            # Load parent task
            parent_task = self.worker.json_storage.get_transcription(parent_task_id)
            if not parent_task:
                logger.error(f"Parent task {parent_task_id} not found")
                return
            
            # Initialize chunks array if not exists
            if 'chunks' not in parent_task:
                parent_task['chunks'] = [None] * total_chunks
            
            # Ensure chunks array has correct size
            while len(parent_task['chunks']) < total_chunks:
                parent_task['chunks'].append(None)
            
            # Save chunk result
            parent_task['chunks'][chunk_index] = chunk_data
            
            # Update progress
            completed_chunks = sum(1 for c in parent_task['chunks'] if c is not None)
            
            # อัปเดต total_chunks และ completed_chunks
            parent_task['total_chunks'] = total_chunks
            parent_task['completed_chunks'] = completed_chunks
            
            # อัปเดต updated_at ทุกครั้งที่บันทึก chunk result (เพื่อให้ updated_at ไม่เท่ากับ created_at)
            parent_task['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # อัปเดต total_tasks และ completed_tasks
            # total_tasks = 1 (audio extraction, ถ้ามีและไม่เป็น null) + total_chunks (transcription chunks)
            # ถ้าเป็น audio file โดยตรง audio_extraction_time จะเป็น None → total_tasks = total_chunks (ไม่มี audio extraction task)
            audio_extraction_done = parent_task.get('audio_extraction_time') is not None
            total_tasks = (1 if audio_extraction_done else 0) + total_chunks
            completed_tasks = (1 if audio_extraction_done else 0) + completed_chunks
            parent_task['total_tasks'] = total_tasks
            parent_task['completed_tasks'] = completed_tasks
            
            # สร้าง task_breakdown ถ้ายังไม่มี
            if 'task_breakdown' not in parent_task:
                parent_task['task_breakdown'] = []
            
            # เพิ่ม transcription chunk task ใน task_breakdown
            chunk_processing_time = chunk_data.get('processing_time', 0)
            chunk_task_exists = any(
                t.get('type') == 'transcription_chunk' and t.get('chunk_index') == chunk_index
                for t in parent_task['task_breakdown']
            )
            if not chunk_task_exists:
                parent_task['task_breakdown'].append({
                    'type': 'transcription_chunk',
                    'chunk_index': chunk_index,
                    'status': 'completed',
                    'time': chunk_processing_time,
                    'completed_at': datetime.now().isoformat()
                })
            
            # ตรวจสอบ display_mode เพื่อคำนวณ progress
            display_mode = parent_task.get('display_mode', 'full_text')
            if display_mode == 'realtime_chunks':
                # Realtime chunks: progress = (completed_chunks / total_chunks) * 100
                # 100% = All chunks completed, % per chunk = 100 / total_chunks
                progress = int((completed_chunks / total_chunks) * 100)
            else:
                # Full text (default): progress = 10 + (completed_chunks / total_chunks) * 80
                # 10% = starting, 10-90% = processing chunks, 90-100% = merging/finalizing
                progress = 10 + int((completed_chunks / total_chunks) * 80)  # 10-90%
            
            parent_task['progress'] = progress
            parent_task['status'] = f"processing_chunk_{completed_chunks}_of_{total_chunks}"
            
            # อัปเดต updated_at ทุกครั้งที่บันทึก chunk result (เพื่อให้ updated_at ไม่เท่ากับ created_at)
            parent_task['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Save to storage
            self.worker.json_storage.save_transcription(parent_task_id, parent_task)
            
            logger.info(f"💾 Saved chunk {chunk_index+1}/{total_chunks} - Progress: {progress}% ({completed_chunks}/{total_chunks} completed, {completed_tasks}/{total_tasks} tasks)")
            
            # Check if all chunks completed
            if completed_chunks >= total_chunks:
                logger.info(f"🎉 All chunks completed for task {parent_task_id}!")
                parent_task['status'] = 'merging_results'
                parent_task['progress'] = 90
                self.worker.json_storage.save_transcription(parent_task_id, parent_task)
                
        except Exception as e:
            logger.error(f"❌ Error saving chunk result: {e}", exc_info=True)
    
    async def download_audio_file_from_url(self, audio_file_url: str, chunk_id: str) -> str:
        """ดาวน์โหลด audio file จาก URL ที่ Backend ส่งมา (Backend จัดการ FileService)"""
        download_root = Path("temp") / f"audio_chunk_{chunk_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
        # ใช้ URL ที่ Backend ส่งมา (Backend เป็นผู้จัดการ FileService)
        destination = download_root / f"{chunk_id}.wav"
        
        timeout = aiohttp.ClientTimeout(total=60)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(audio_file_url) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ดาวน์โหลด audio file ไม่สำเร็จ (status: {response.status}): {body}")
                    
                    async with aiofiles.open(destination, 'wb') as file_obj:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await file_obj.write(chunk)
            
            # ตั้งค่า permission
            try:
                os.chmod(destination, 0o644)
            except Exception as e:
                logger.warning(f"ไม่สามารถตั้งค่า permission: {e}")
            
            logger.info(f"ดาวน์โหลด audio file สำเร็จ: {destination}")
            return str(destination)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด audio file: {e}")
            raise
    
    async def download_audio_file_from_fileservice(self, audio_file_id: str, chunk_id: str) -> str:
        """ดาวน์โหลด audio file จาก FileService โดยใช้ file ID"""
        download_root = Path("temp") / f"audio_chunk_{chunk_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
        # Download file จาก FileService API
        file_service_url = os.getenv('FILE_SERVICE_URL', 'http://localhost:8001')
        file_url = f"{file_service_url}/api/files/{audio_file_id}"
        destination = download_root / f"{audio_file_id}.wav"
        
        timeout = aiohttp.ClientTimeout(total=60)
        headers = {}
        
        # เพิ่ม headers สำหรับ authentication (ถ้ามี)
        file_service_tenant_id = os.getenv('FILE_SERVICE_TENANT_ID')
        file_service_api_key = os.getenv('FILE_SERVICE_API_KEY')
        if file_service_tenant_id:
            headers['X-Tenant-Id'] = file_service_tenant_id
        if file_service_api_key:
            headers['X-Api-Key'] = file_service_api_key
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(file_url, headers=headers) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RuntimeError(f"ดาวน์โหลด audio file ไม่สำเร็จ (status: {response.status}): {body}")
                    
                    async with aiofiles.open(destination, 'wb') as file_obj:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await file_obj.write(chunk)
            
            # ตั้งค่า permission
            try:
                os.chmod(destination, 0o644)
            except Exception as e:
                logger.warning(f"ไม่สามารถตั้งค่า permission: {e}")
            
            logger.info(f"ดาวน์โหลด audio file สำเร็จ: {destination}")
            return str(destination)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด audio file: {e}")
            raise
    
    def execute_chunk_transcription_sync(self, chunk_task: Dict[str, Any], ch, delivery_tag):
        """Execute chunk transcription in a synchronous way (for ThreadPoolExecutor)"""
        chunk_index = chunk_task.get('chunk_index', 0)
        total_chunks = chunk_task.get('total_chunks', 0)
        parent_task_id = chunk_task.get('parent_task_id', 'unknown')
        thread_name = threading.current_thread().name
        
        logger.info(f"🔄 [Thread {thread_name}] Starting chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
        
        try:
            # สร้าง event loop ใหม่สำหรับ thread นี้ (ไม่ใช้ asyncio.run() เพราะอาจมี conflict)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.worker.processors.execute_chunk_transcription(chunk_task))
                logger.info(f"✅ [Thread {thread_name}] Completed chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            finally:
                loop.close()
                asyncio.set_event_loop(None)  # Clear event loop for the thread
            
            # Clean up
            if delivery_tag in self.worker.active_chunks:
                del self.worker.active_chunks[delivery_tag]
                logger.info(f"🧹 [Thread {thread_name}] Cleaned up chunk {chunk_index+1} (remaining active: {len(self.worker.active_chunks)})")
                
        except Exception as e:
            logger.error(f"❌ [Thread {thread_name}] Error in chunk {chunk_index+1} transcription: {e}", exc_info=True)
            # Clean up
            if delivery_tag in self.worker.active_chunks:
                del self.worker.active_chunks[delivery_tag]
    
    def maintain_connection(self):
        """Background thread เพื่อ maintain RabbitMQ connection"""
        check_interval = int(os.getenv('RABBITMQ_CONNECTION_CHECK_INTERVAL', '30'))  # 30 วินาที
        
        logger.info(f"🔄 Starting connection maintenance thread (check interval: {check_interval}s)")
        
        while self.worker._maintenance_thread_running and self.worker.running:
            try:
                time.sleep(check_interval)
                
                if not self.worker.running or not self.worker._maintenance_thread_running:
                    break
                
                # ตรวจสอบ connection health
                connection_ok = False
                try:
                    if self.worker.connection.connection and not self.worker.connection.connection.is_closed:
                        # Process data events เพื่อส่ง heartbeat
                        self.worker.connection.connection.process_data_events(time_limit=0.1)
                        connection_ok = True
                except (AttributeError, Exception) as e:
                    logger.warning(f"⚠️ Connection check failed: {e}")
                    connection_ok = False
                
                # ถ้า connection ไม่ดี ให้ reconnect
                if not connection_ok:
                    logger.warning("⚠️ Connection lost detected by maintenance thread, attempting to reconnect...")
                    
                    # Try to reconnect
                    if self.worker.connection.connect(max_retries=5, retry_delay=5):
                        logger.info("✅ Reconnected to RabbitMQ successfully (via maintenance thread)")
                        # Re-setup consumers after reconnection
                        self.worker.consumers.setup_consumers()
                        logger.info("✅ Consumers re-registered (via maintenance thread)")
                        # Reconnect publish channel
                        self.worker.connection._connect_publish_channel()
                    else:
                        logger.warning("⚠️ Failed to reconnect (maintenance thread will retry later)")
                
                # ตรวจสอบ publish connection
                publish_connection_ok = False
                try:
                    if self.worker.connection.publish_connection and not self.worker.connection.publish_connection.is_closed:
                        if self.worker.connection.publish_channel and not self.worker.connection.publish_channel.is_closed:
                            # Try a simple operation to verify connection
                            self.worker.connection.publish_connection.process_data_events(time_limit=0.001)
                            publish_connection_ok = True
                except (AttributeError, Exception) as e:
                    logger.warning(f"⚠️ Publish connection check failed: {e}")
                    publish_connection_ok = False
                
                # ถ้า publish connection ไม่ดี ให้ reconnect
                if not publish_connection_ok:
                    logger.warning("⚠️ Publish connection lost, attempting to reconnect...")
                    try:
                        self.worker.connection._connect_publish_channel()
                        logger.info("✅ Publish channel reconnected successfully (via maintenance thread)")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to reconnect publish channel: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error in connection maintenance thread: {e}", exc_info=True)
                # Continue loop even if error occurs
                time.sleep(check_interval)
        
        logger.info("🛑 Connection maintenance thread stopped")
    
    def start_maintenance_thread(self):
        """Start background thread สำหรับ maintain connection"""
        if self.worker._maintenance_thread_running:
            logger.warning("⚠️ Maintenance thread already running")
            return
        
        self.worker._maintenance_thread_running = True
        self.worker._maintenance_thread = threading.Thread(
            target=self.maintain_connection,
            daemon=True,
            name="connection-maintenance"
        )
        self.worker._maintenance_thread.start()
        logger.info("✅ Connection maintenance thread started")
    
    def stop_maintenance_thread(self):
        """Stop background thread สำหรับ maintain connection"""
        if not self.worker._maintenance_thread_running:
            return
        
        self.worker._maintenance_thread_running = False
        
        # Wait for thread to finish
        if hasattr(self.worker, '_maintenance_thread') and self.worker._maintenance_thread:
            try:
                self.worker._maintenance_thread.join(timeout=5)
                logger.info("✅ Connection maintenance thread stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping maintenance thread: {e}")

