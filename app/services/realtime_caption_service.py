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
                 chunk_duration: int = 10, delay_seconds: float = 0.0):
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
        return {
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
    
    def __init__(self):
        self.file_service = FileService()
        self.whisper_service = WhisperService()
        self.video_service = VideoService()
        self.json_storage = JSONStorage()
        self.websocket_manager = websocket_manager
        
        # Active sessions
        self.active_sessions: Dict[str, RealtimeCaptionSession] = {}
        self.chunk_broadcaster = ChunkBroadcaster(websocket_manager)
        
        # API server URL
        environment = os.getenv('ENVIRONMENT', 'development')
        if environment == 'development':
            self.api_server_url = "http://transcription-api-dev:8001"
        elif environment == 'staging':
            self.api_server_url = "http://transcription-api-staging:8001"
        elif environment == 'local':
            self.api_server_url = "http://api:8001"
        else:  # production
            self.api_server_url = "http://transcription-api:8001"
    
    async def start_realtime_caption(self, user_id: str, file_path: str, 
                                   language: str = "th", model_size: str = "base",
                                   chunk_duration: int = 10, delay_seconds: float = 0.0) -> str:
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
            
            for i, chunk_path in enumerate(chunks):
                if session.status == "stopped":
                    break
                
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
                            chunk_data = {
                                "start_time": segment.get("start", 0) + (i * session.chunk_duration),
                                "end_time": segment.get("end", 0) + (i * session.chunk_duration),
                                "text": segment.get("text", ""),
                                "confidence": segment.get("avg_logprob"),
                                "chunk_index": i,
                                "processed_at": datetime.now().isoformat()
                            }
                            
                            # เพิ่มใน session
                            session.chunks.append(chunk_data)
                            session.partial_text += " " + chunk_data["text"]
                            session.partial_text = session.partial_text.strip()
                            
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
                    logger.error(f"❌ Error processing chunk {i}: {e}")
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
            
            # เสร็จสิ้น
            session.status = "completed"
            session.completed_at = datetime.now()
            
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
