"""
Realtime Caption Service สำหรับ Real-time Close Caption
รองรับการส่ง chunks ทันทีที่ประมวลผลเสร็จ พร้อม delay control
"""

import asyncio
import uuid
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
import aiohttp
import json
from collections import deque

from .file_service import FileService
from .whisper_service import WhisperService
from .video_service import VideoService
from .websocket_service import websocket_manager
from ..models.transcription import TranscriptionChunk
from ..utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class RealtimeCaptionSession:
    """Session สำหรับ real-time caption"""
    def __init__(self, session_id: str, user_id: str, file_path: str, 
                 language: str = "th", model_size: str = "base", 
                 chunk_duration: int = 5, delay_seconds: float = 0.0):
        self.session_id = session_id
        self.user_id = user_id
        self.file_path = file_path
        self.language = language
        self.model_size = model_size
        self.chunk_duration = chunk_duration
        self.delay_seconds = delay_seconds
        
        # Session state
        self.status = "pending"  # pending, processing, active, completed, failed
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        
        # Processing state
        self.current_chunk_index = 0
        self.total_chunks = 0
        self.progress = 0
        
        # Real-time data
        self.partial_text = ""
        self.chunks: List[Dict] = []
        self.chunk_queue: deque = deque()  # Queue สำหรับ delay control
        
        # Error handling
        self.error_message = None
        
    def to_dict(self) -> Dict:
        """แปลงเป็น dictionary สำหรับ JSON serialization"""
        logger.info(f"🔍 DEBUG_TO_DICT_1: Converting session {self.session_id} to dict")
        logger.info(f"🔍 DEBUG_TO_DICT_2: partial_text type: {type(self.partial_text)}, value: '{self.partial_text}'")
        
        # บังคับให้ partial_text เป็น string ก่อนบันทึก
        if not isinstance(self.partial_text, str):
            logger.warning("partial_text was %r, casting to str", type(self.partial_text))
            self.partial_text = str(self.partial_text) if self.partial_text is not None else ""
        
        logger.info(f"🔍 DEBUG_TO_DICT_3: After type check - partial_text: '{self.partial_text}' (type: {type(self.partial_text)})")
        
        result = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "file_path": self.file_path,
            "language": self.language,
            "model_size": self.model_size,
            "chunk_duration": self.chunk_duration,
            "delay_seconds": self.delay_seconds,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_chunk_index": self.current_chunk_index,
            "total_chunks": self.total_chunks,
            "progress": self.progress,
            "partial_text": self.partial_text,
            "chunks": self.chunks,
            "error_message": self.error_message
        }
        
        logger.info(f"🔍 DEBUG_TO_DICT_4: Final dict partial_text: '{result['partial_text']}' (type: {type(result['partial_text'])})")
        return result

class ChunkBroadcaster:
    """Broadcaster สำหรับส่ง chunks แบบ real-time"""
    
    def __init__(self, websocket_manager):
        self.websocket_manager = websocket_manager
        self.active_sessions: Dict[str, RealtimeCaptionSession] = {}
        
    async def broadcast_chunk(self, session_id: str, chunk_data: Dict):
        """ส่ง chunk ไปยัง user ทันที"""
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found for chunk broadcast")
            return
            
        session = self.active_sessions[session_id]
        
        # สร้าง message สำหรับ WebSocket
        message = {
            "type": "caption.chunk",
            "session_id": session_id,
            "chunk_index": session.current_chunk_index,
            "chunk_data": chunk_data,
            "timestamp": datetime.now().isoformat(),
            "delay_seconds": session.delay_seconds
        }
        
        # ส่งไปยัง user
        await self.websocket_manager.send_to_user(session.user_id, message)
        
        logger.info(f"📡 Broadcasted chunk {session.current_chunk_index} to user {session.user_id}")
    
    async def broadcast_progress(self, session_id: str, progress: int, status: str):
        """ส่ง progress update"""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        
        message = {
            "type": "caption.progress",
            "session_id": session_id,
            "progress": progress,
            "status": status,
            "current_chunk": session.current_chunk_index,
            "total_chunks": session.total_chunks,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.websocket_manager.send_to_user(session.user_id, message)
    
    async def broadcast_completed(self, session_id: str, final_data: Dict):
        """ส่งข้อมูลเมื่อเสร็จสิ้น"""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        
        message = {
            "type": "caption.completed",
            "session_id": session_id,
            "status": "completed",
            "total_chunks": len(session.chunks),
            "total_text_length": len(session.partial_text),
            "final_data": final_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.websocket_manager.send_to_user(session.user_id, message)
    
    async def broadcast_error(self, session_id: str, error: str):
        """ส่ง error message"""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        
        message = {
            "type": "caption.error",
            "session_id": session_id,
            "status": "failed",
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.websocket_manager.send_to_user(session.user_id, message)

class RealtimeCaptionService:
    """Service หลักสำหรับ real-time close caption"""
    
    def safe_join_text(self, a, b) -> str:
        """
        ต่อสตริงแบบกันตาย + ตัดช่องว่างเกิน
        """
        sa = "" if a is None else (a if isinstance(a, str) else str(a))
        sb = "" if b is None else (b if isinstance(b, str) else str(b))
        s = (sa + " " + sb).strip()
        return s
    
    def __init__(self):
        # ลายเซ็นเวอร์ชันโค้ด
        SERVICE_VERSION = "realtime_caption_service@2025-09-18T15:10Z"
        logger.info("Loaded %s", SERVICE_VERSION)
        
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.video_service = VideoService()
        self.json_storage = JSONStorage()
        self.websocket_manager = websocket_manager
        
        # Active sessions
        self.active_sessions: Dict[str, RealtimeCaptionSession] = {}
        self.chunk_broadcaster = ChunkBroadcaster(websocket_manager)
        
        # API server URL
        # ใน Docker compose, services ใช้ container name หรือ service name
        environment = os.getenv('ENVIRONMENT', 'development')
        api_server_env = os.getenv('API_SERVER_URL')  # อนุญาตให้ override ผ่าน environment variable
        
        if api_server_env:
            self.api_server_url = api_server_env
        elif environment == 'development':
            self.api_server_url = "http://transcription-api-dev:8001"
        elif environment == 'staging':
            # ใน docker-compose.staging.yml container name คือ "transcription-api"
            # แต่ service name คือ "api" ซึ่งสามารถใช้ได้เหมือนกันใน Docker network
            self.api_server_url = "http://api:8001"  # ใช้ service name แทน container name
        elif environment == 'local':
            self.api_server_url = "http://api:8001"
        else:  # production
            self.api_server_url = "http://transcription-api:8001"
    
    async def start_realtime_caption(self, user_id: str, file_path: str, 
                                   language: str = "th", model_size: str = "base",
                                   chunk_duration: int = 5, delay_seconds: float = 0.0) -> str:
        """เริ่ม real-time caption session"""
        
        # สร้าง session
        session_id = str(uuid.uuid4())
        session = RealtimeCaptionSession(
            session_id=session_id,
            user_id=user_id,
            file_path=file_path,
            language=language,
            model_size=model_size,
            chunk_duration=chunk_duration,
            delay_seconds=delay_seconds
        )
        
        self.active_sessions[session_id] = session
        self.chunk_broadcaster.active_sessions[session_id] = session
        
        # เริ่มการประมวลผลแบบ async
        asyncio.create_task(self._process_realtime_caption(session_id))
        
        logger.info(f"🎬 Started real-time caption session: {session_id} for user {user_id}")
        return session_id
    
    async def stop_realtime_caption(self, session_id: str) -> bool:
        """หยุด real-time caption session"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session.status = "stopped"
        session.completed_at = datetime.now()
        
        # ส่ง stop message
        await self.chunk_broadcaster.websocket_manager.send_to_user(session.user_id, {
            "type": "caption.stopped",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # ลบ session
        del self.active_sessions[session_id]
        if session_id in self.chunk_broadcaster.active_sessions:
            del self.chunk_broadcaster.active_sessions[session_id]
        
        logger.info(f"⏹️ Stopped real-time caption session: {session_id}")
        return True
    
    async def update_delay(self, session_id: str, delay_seconds: float) -> bool:
        """อัปเดต delay time"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session.delay_seconds = delay_seconds
        
        # ส่ง delay update message
        await self.chunk_broadcaster.websocket_manager.send_to_user(session.user_id, {
            "type": "caption.delay_updated",
            "session_id": session_id,
            "delay_seconds": delay_seconds,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"⏱️ Updated delay for session {session_id}: {delay_seconds}s")
        return True
    
    def get_session(self, session_id: str) -> Optional[RealtimeCaptionSession]:
        """ดึงข้อมูล session"""
        return self.active_sessions.get(session_id)
    
    def get_user_sessions(self, user_id: str) -> List[RealtimeCaptionSession]:
        """ดึง sessions ของ user"""
        return [session for session in self.active_sessions.values() 
                if session.user_id == user_id]
    
    async def _process_realtime_caption(self, session_id: str):
        """ประมวลผล real-time caption"""
        session = self.active_sessions[session_id]
        session.status = "processing"
        session.started_at = datetime.now()
        
        # 🔍 DEBUG: ตรวจสอบข้อมูลที่เข้ามา
        logger.info(f"🔍 DEBUG_INPUT_1: session_id={session_id} (type: {type(session_id)})")
        logger.info(f"🔍 DEBUG_INPUT_2: session.file_path={session.file_path} (type: {type(session.file_path)})")
        logger.info(f"🔍 DEBUG_INPUT_3: session.chunk_duration={session.chunk_duration} (type: {type(session.chunk_duration)})")
        logger.info(f"🔍 DEBUG_INPUT_4: session.language={session.language} (type: {type(session.language)})")
        logger.info(f"🔍 DEBUG_INPUT_5: session.model_size={session.model_size} (type: {type(session.model_size)})")
        
        try:
            # ตรวจสอบไฟล์
            if not Path(session.file_path).exists():
                raise FileNotFoundError(f"ไฟล์ไม่พบ: {session.file_path}")
            
            # สร้าง audio chunks
            logger.info(f"🎵 Creating audio chunks for session {session_id}...")
            chunks = self.video_service.extract_audio_chunks(
                session.file_path, session.chunk_duration
            )
            
            session.total_chunks = len(chunks)
            
            # ส่งเริ่มต้น message
            await self.chunk_broadcaster.websocket_manager.send_to_user(session.user_id, {
                "type": "caption.started",
                "session_id": session_id,
                "total_chunks": session.total_chunks,
                "chunk_duration": session.chunk_duration,
                "delay_seconds": session.delay_seconds,
                "timestamp": datetime.now().isoformat()
            })
            
            # แปลงเสียงแต่ละ chunk แบบ real-time
            logger.info(f"🎤 Processing {len(chunks)} chunks for real-time caption...")
            
            # การันตีชนิดก่อนเข้าลูป
            if not isinstance(session.partial_text, str):
                logger.warning("partial_text type=%r -> casting to str: %r", type(session.partial_text), session.partial_text)
                session.partial_text = str(session.partial_text)
            
            for i, chunk_path in enumerate(chunks):
                if session.status == "stopped":
                    break
                
                # 🔍 DEBUG: ตรวจสอบข้อมูลก่อนประมวลผล
                logger.info(f"🔍 DEBUG_CHUNK_1: i={i} (type: {type(i)})")
                logger.info(f"🔍 DEBUG_CHUNK_2: chunk_path={chunk_path} (type: {type(chunk_path)})")
                logger.info(f"🔍 DEBUG_CHUNK_3: session.model_size={session.model_size} (type: {type(session.model_size)})")
                logger.info(f"🔍 DEBUG_CHUNK_4: session.language={session.language} (type: {type(session.language)})")
                
                try:
                    logger.info(f"🔄 Processing chunk {i+1}/{len(chunks)}")
                    
                    # แปลงเสียง
                    result = self.whisper_service.transcribe_file(
                        chunk_path, session.model_size, session.language, 
                        use_thai_processor=True
                    )
                    
                    if result and "segments" in result and result["segments"]:
                        # สร้าง chunk data
                        for segment in result["segments"]:
                            # 🔍 DEBUG: ตรวจสอบ segment data
                            logger.info(f"🔍 DEBUG_SEGMENT_1: segment={segment}")
                            logger.info(f"🔍 DEBUG_SEGMENT_2: segment.get('start', 0)={segment.get('start', 0)} (type: {type(segment.get('start', 0))})")
                            logger.info(f"🔍 DEBUG_SEGMENT_3: segment.get('end', 0)={segment.get('end', 0)} (type: {type(segment.get('end', 0))})")
                            logger.info(f"🔍 DEBUG_SEGMENT_4: segment.get('text', '')={segment.get('text', '')} (type: {type(segment.get('text', ''))})")
                            logger.info(f"🔍 DEBUG_SEGMENT_5: i={i} (type: {type(i)})")
                            logger.info(f"🔍 DEBUG_SEGMENT_6: session.chunk_duration={session.chunk_duration} (type: {type(session.chunk_duration)})")
                            
                            # แปลง time format จาก '00:00:00,000' เป็น float
                            def parse_time_to_seconds(time_str):
                                """แปลง time string เป็น seconds (float)"""
                                if isinstance(time_str, (int, float)):
                                    return float(time_str)
                                
                                if isinstance(time_str, str):
                                    # แปลง '00:00:05,300' เป็น 5.3
                                    try:
                                        # แยกส่วน time และ milliseconds
                                        if ',' in time_str:
                                            time_part, ms_part = time_str.split(',')
                                        else:
                                            time_part, ms_part = time_str, '000'
                                        
                                        # แยก hh:mm:ss
                                        time_components = time_part.split(':')
                                        if len(time_components) == 3:
                                            hours, minutes, seconds = map(int, time_components)
                                            total_seconds = hours * 3600 + minutes * 60 + seconds
                                            # เพิ่ม milliseconds
                                            milliseconds = int(ms_part)
                                            return total_seconds + (milliseconds / 1000.0)
                                    except (ValueError, IndexError):
                                        pass
                                
                                return 0.0
                            
                            start_seconds = parse_time_to_seconds(segment.get("start", 0))
                            end_seconds = parse_time_to_seconds(segment.get("end", 0))
                            
                            chunk_data = {
                                "start_time": start_seconds + (i * session.chunk_duration),
                                "end_time": end_seconds + (i * session.chunk_duration),
                                "text": segment.get("text", ""),
                                "confidence": segment.get("avg_logprob"),
                                "chunk_index": i,
                                "processed_at": datetime.now().isoformat()
                            }
                            
                            # เพิ่มใน session
                            session.chunks.append(chunk_data)
                            
                            # ตรวจสอบและแปลง text เป็น string
                            raw_text = chunk_data.get("text", "")
                            if not isinstance(raw_text, str):
                                logger.warning("segment.text type=%r -> casting to str: %r", type(raw_text), raw_text)
                            text_value = str(raw_text) if raw_text is not None else ""
                            
                            # Close Caption: ไม่ต้องต่อข้อความทุก Chunk
                            # แค่เก็บ Chunk ไว้ใน session.chunks
                            # Frontend จะแสดงข้อความตามเวลาของแต่ละ Chunk
                            
                            # คำนวณ duration อย่างปลอดภัย
                            start_time = float(chunk_data.get('start_time', 0))
                            end_time = float(chunk_data.get('end_time', 0))
                            duration = end_time - start_time
                            
                            logger.info(f"🎬 Close Caption Chunk {i+1}: '{text_value}' (duration: {duration:.1f}s)")
                            
                            # ส่ง chunk ทันที (ไม่รอ delay)
                            await self.chunk_broadcaster.broadcast_chunk(session_id, chunk_data)
                            
                            # อัปเดต progress
                            session.current_chunk_index = i + 1
                            session.progress = int((i + 1) / len(chunks) * 100)
                            
                            # ส่ง progress update
                            await self.chunk_broadcaster.broadcast_progress(
                                session_id, session.progress, "processing"
                            )
                    
                    logger.info(f"✅ Completed chunk {i+1}/{len(chunks)} - Progress: {session.progress}%")
                    
                except Exception as e:
                    logger.error(f"❌ DEBUG_ERROR_1: Error processing chunk {i}: {e}")
                    logger.error(f"❌ DEBUG_ERROR_2: Error type: {type(e)}")
                    logger.error(f"❌ DEBUG_ERROR_3: Error args: {e.args}")
                    logger.error(f"❌ DEBUG_ERROR_4: Session partial_text: '{session.partial_text}' (type: {type(session.partial_text)})")
                    logger.error(f"❌ DEBUG_ERROR_5: Session chunks count: {len(session.chunks)}")
                    # ส่ง error chunk
                    error_chunk = {
                        "start_time": i * session.chunk_duration,
                        "end_time": (i + 1) * session.chunk_duration,
                        "text": f"[Error: {str(e)}]",
                        "confidence": None,
                        "chunk_index": i,
                        "processed_at": datetime.now().isoformat(),
                        "error": True
                    }
                    session.chunks.append(error_chunk)
                    await self.chunk_broadcaster.broadcast_chunk(session_id, error_chunk)
            
            # เสร็จสิ้น - ไม่รวมข้อความทั้งหมดจาก chunks
            session.status = "completed"
            session.completed_at = datetime.now()
            
            # Comment การรวมข้อความทั้งหมดจาก chunks (Close Caption)
            # total_text = ""
            # for chunk in session.chunks:
            #     if chunk.get("text"):
            #         total_text += " " + str(chunk["text"])
            # session.partial_text = total_text.strip()
            
            # แค่เก็บ chunks ไว้ใน session.partial_text เป็น JSON string
            import json
            session.partial_text = json.dumps([chunk for chunk in session.chunks if chunk.get("text")], ensure_ascii=False, indent=2)
            
            logger.info(f"🎬 Close Caption Complete: {len(session.chunks)} chunks, {len(session.partial_text)} characters")
            
            # ส่งข้อมูลสุดท้าย
            final_data = {
                "total_chunks": len(session.chunks),
                "total_text": session.partial_text,
                "total_duration": len(chunks) * session.chunk_duration,
                "language": session.language,
                "model_size": session.model_size
            }
            
            await self.chunk_broadcaster.broadcast_completed(session_id, final_data)
            
            # บันทึกลง storage
            self.json_storage.save_transcription(session_id, session.to_dict())
            
            logger.info(f"🎉 Real-time caption completed: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Real-time caption failed {session_id}: {e}")
            session.status = "failed"
            session.error_message = str(e)
            session.completed_at = datetime.now()
            
            await self.chunk_broadcaster.broadcast_error(session_id, str(e))
        
        finally:
            # ลบ temp files
            if 'chunks' in locals():
                try:
                    self.file_service.cleanup_temp_files(chunks)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp files: {cleanup_error}")

# Global service instance
realtime_caption_service = RealtimeCaptionService()
