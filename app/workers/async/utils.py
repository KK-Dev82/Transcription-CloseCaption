"""
Helper Utilities (aio-pika - Async)

Helper functions สำหรับ worker: save chunk results, download files
ไม่มี maintenance thread เพราะใช้ async auto-reconnect
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)


class AsyncWorkerUtils:
    """Helper utilities สำหรับ async worker"""
    
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
            
            # อัปเดต total_tasks และ completed_tasks
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
                progress = int((completed_chunks / total_chunks) * 100)
            else:
                progress = 10 + int((completed_chunks / total_chunks) * 80)  # 10-90%
            
            parent_task['progress'] = progress
            parent_task['status'] = f"processing_chunk_{completed_chunks}_of_{total_chunks}"
            
            # Update detailed stage information
            parent_task['current_stage'] = 'transcribing'
            parent_task['current_stage_description'] = f'กำลังแปลงเสียง chunk {completed_chunks}/{total_chunks}'
            # คำนวณ stage_progress จาก chunks ที่เสร็จแล้ว
            stage_progress = int((completed_chunks / total_chunks) * 100) if total_chunks > 0 else 0
            parent_task['stage_progress'] = stage_progress
            
            # Save to storage
            self.worker.json_storage.save_transcription(parent_task_id, parent_task)
            
            logger.info(f"💾 Saved chunk {chunk_index+1}/{total_chunks} - Progress: {progress}% ({completed_chunks}/{total_chunks} completed, {completed_tasks}/{total_tasks} tasks)")
            
            # Check if all chunks completed
            if completed_chunks >= total_chunks:
                logger.info(f"🎉 All chunks completed for task {parent_task_id}!")
                parent_task['status'] = 'merging_results'
                parent_task['progress'] = 90
                parent_task['current_stage'] = 'merging'
                parent_task['current_stage_description'] = 'กำลังรวมผลลัพธ์จากทุกส่วน'
                parent_task['stage_progress'] = 0  # เริ่ม merging
                self.worker.json_storage.save_transcription(parent_task_id, parent_task)
                
        except Exception as e:
            logger.error(f"❌ Error saving chunk result: {e}", exc_info=True)
    
    async def download_audio_file_from_url(self, audio_file_url: str, chunk_id: str) -> str:
        """ดาวน์โหลด audio file จาก URL ที่ Backend ส่งมา (Backend จัดการ FileService)"""
        download_root = Path("temp") / f"audio_chunk_{chunk_id}"
        download_root.mkdir(parents=True, exist_ok=True)
        
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
        
        file_service_url = os.getenv('FILE_SERVICE_URL', 'http://localhost:8001')
        file_url = f"{file_service_url}/api/files/{audio_file_id}"
        destination = download_root / f"{audio_file_id}.wav"
        
        timeout = aiohttp.ClientTimeout(total=60)
        headers = {}
        
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
            
            try:
                os.chmod(destination, 0o644)
            except Exception as e:
                logger.warning(f"ไม่สามารถตั้งค่า permission: {e}")
            
            logger.info(f"ดาวน์โหลด audio file สำเร็จ: {destination}")
            return str(destination)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลด audio file: {e}")
            raise
    
    async def execute_chunk_transcription_async(self, chunk_task: Dict[str, Any]):
        """Execute chunk transcription async (สำหรับ asyncio tasks)"""
        chunk_index = chunk_task.get('chunk_index', 0)
        total_chunks = chunk_task.get('total_chunks', 0)
        parent_task_id = chunk_task.get('parent_task_id', 'unknown')
        
        logger.info(f"🔄 Starting chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
        
        try:
            await self.worker.processors.execute_chunk_transcription(chunk_task)
            logger.info(f"✅ Completed chunk {chunk_index+1}/{total_chunks} for task {parent_task_id}")
            
        except Exception as e:
            logger.error(f"❌ Error in chunk {chunk_index+1} transcription: {e}", exc_info=True)
        finally:
            # Clean up from active_chunks (หา delivery_tag จาก task หรือใช้ index)
            # Note: ใน async worker เราใช้ asyncio tasks แทน ThreadPoolExecutor
            # ดังนั้น active_chunks จะเก็บ asyncio.Task objects
            pass
    
    async def monitor_transcription_progress(self, task_id: str):
        """Monitor progress และ log updates (async version)"""
        last_progress = -1
        last_status = ""
        last_log_time = 0
        
        try:
            while True:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                try:
                    task_info = self.worker.json_storage.get_transcription(task_id)
                    if task_info:
                        current_progress = task_info.get('progress', 0)
                        current_status = task_info.get('status', '')
                        current_time = time.time()
                        
                        progress_changed = (current_progress != last_progress or current_status != last_status)
                        time_since_last_log = current_time - last_log_time
                        
                        if progress_changed or time_since_last_log >= 30:
                            if progress_changed:
                                logger.info(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status}")
                            else:
                                logger.debug(f"📊 Task {task_id}: Progress {current_progress}% - Status: {current_status} (heartbeat)")
                            
                            last_progress = current_progress
                            last_status = current_status
                            last_log_time = current_time
                    
                    # ถ้า task completed หรือ failed ให้หยุด monitoring
                    if task_info:
                        status = task_info.get('status', '')
                        if status in ['completed', 'failed']:
                            logger.info(f"📊 Task {task_id} finished with status: {status}")
                            break
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Error monitoring progress: {e}")
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logger.debug(f"Progress monitoring cancelled for task {task_id}")
            raise

