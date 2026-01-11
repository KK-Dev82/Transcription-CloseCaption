"""
SQLite Storage Service
ทดแทน JSON Storage สำหรับ staging/production deployment
"""

import sqlite3
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)

class SQLiteStorage:
    def __init__(self, db_path: str = "storage/database.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Thread-local storage สำหรับ connection
        self._local = threading.local()
        
        # Flag เพื่อป้องกัน recursion ใน auto-migration
        self._migrating_tasks = set()
        
        # สร้าง database และ tables
        self._init_database()
        
        logger.info(f"SQLite database initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """ดึง database connection สำหรับ thread ปัจจุบัน"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            
            # เปิด WAL mode สำหรับ better concurrent access
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")
            self._local.connection.execute("PRAGMA temp_store=MEMORY")
            
        return self._local.connection
    
    def _init_database(self):
        """สร้าง database tables"""
        conn = self._get_connection()
        
        # Transcriptions table - เพิ่ม fields สำหรับ compatibility กับ JSONStorage
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                task_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                file_path TEXT,
                file_url TEXT,
                file_name TEXT,
                language TEXT,
                total_duration REAL,
                full_text TEXT,
                original_text TEXT,
                corrected_text TEXT,
                partial_text TEXT,
                chunks_json TEXT,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                model_size TEXT,
                chunk_duration INTEGER,
                error_message TEXT,
                processing_time REAL,
                transcription_time REAL,
                audio_extraction_time REAL,
                text_correction_time REAL,
                current_stage TEXT,
                current_stage_description TEXT,
                stage_progress INTEGER,
                job_id TEXT,
                user_id TEXT,
                callback_url TEXT
            )
        """)
        
        # Captions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS captions (
                task_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                language TEXT,
                subtitle_format TEXT,
                subtitle_content TEXT,
                segments_json TEXT,
                status TEXT DEFAULT 'pending',
                model_size TEXT,
                error_message TEXT
            )
        """)
        
        # Video tasks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_tasks (
                task_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                type TEXT,
                status TEXT DEFAULT 'pending',
                input_file TEXT,
                input_files_json TEXT,
                output_file TEXT,
                output_format TEXT,
                quality TEXT,
                start_time REAL,
                end_time REAL,
                width INTEGER,
                height INTEGER,
                operations_json TEXT,
                results_json TEXT,
                error_message TEXT,
                progress REAL DEFAULT 0
            )
        """)
        
        # Live streams table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS live_streams (
                stream_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                language TEXT,
                model_size TEXT,
                total_audio_duration REAL DEFAULT 0,
                transcription_count INTEGER DEFAULT 0,
                last_transcription_json TEXT,
                error_message TEXT
            )
        """)
        
        # Segments table - สำหรับเก็บ segments แบบ streaming (ลด RAM usage)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES transcriptions(task_id) ON DELETE CASCADE
            )
        """)
        
        # Index สำหรับ query segments ตาม task_id และ start_time (สำหรับ caption seek)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_segments_task_id_start 
            ON segments(task_id, start_time)
        """)
        
        # Migrate existing table schema (add new columns if they don't exist)
        # ต้องทำก่อนสร้าง indexes เพื่อไม่ให้เกิด error
        try:
            # Check if table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcriptions'")
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                # Check if new columns exist, if not add them
                cursor = conn.execute("PRAGMA table_info(transcriptions)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                new_columns = {
                    'completed_at': 'TIMESTAMP',
                    'file_url': 'TEXT',
                    'file_name': 'TEXT',
                    'original_text': 'TEXT',
                    'corrected_text': 'TEXT',
                    'partial_text': 'TEXT',
                    'progress': 'INTEGER DEFAULT 0',
                    'processing_time': 'REAL',
                    'transcription_time': 'REAL',
                    'audio_extraction_time': 'REAL',
                    'text_correction_time': 'REAL',
                    'current_stage': 'TEXT',
                    'current_stage_description': 'TEXT',
                    'stage_progress': 'INTEGER',
                    'job_id': 'TEXT',
                    'user_id': 'TEXT',
                    'callback_url': 'TEXT'
                }
                
                for col_name, col_type in new_columns.items():
                    if col_name not in existing_columns:
                        logger.info(f"Adding column {col_name} to transcriptions table")
                        try:
                            conn.execute(f"ALTER TABLE transcriptions ADD COLUMN {col_name} {col_type}")
                        except Exception as e:
                            logger.warning(f"Failed to add column {col_name}: {e}")
                
                conn.commit()
        except Exception as e:
            logger.warning(f"Error migrating table schema: {e}")
        
        # Indexes สำหรับ performance (สร้างหลังจาก migrate schema แล้ว)
        # ใช้ IF NOT EXISTS และตรวจสอบว่า column มีอยู่ก่อน
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at)")
            
            # ตรวจสอบว่า column มีอยู่ก่อนสร้าง index
            cursor = conn.execute("PRAGMA table_info(transcriptions)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            if 'updated_at' in existing_columns:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_updated_at ON transcriptions(updated_at DESC)")
            if 'completed_at' in existing_columns:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_completed_at ON transcriptions(completed_at DESC)")
            # เพิ่ม index สำหรับ created_at (ถ้ายังไม่มี)
            if 'created_at' in existing_columns:
                # ตรวจสอบว่า index มีอยู่แล้วหรือไม่
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_transcriptions_created_at'")
                if not cursor.fetchone():
                    conn.execute("CREATE INDEX idx_transcriptions_created_at ON transcriptions(created_at DESC)")
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_captions_status ON captions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_tasks_status ON video_tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_tasks_type ON video_tasks(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_live_streams_status ON live_streams(status)")
            
            conn.commit()
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
            conn.rollback()
    
    # Transcription methods
    def save_transcription(self, task_id: str, transcription_data: Dict) -> str:
        """บันทึกข้อมูล transcription"""
        conn = self._get_connection()
        
        chunks_json = json.dumps(transcription_data.get("chunks", []), ensure_ascii=False)
        
        # Helper function to get UTC timestamp
        def get_utc_timestamp(value):
            """Convert value to UTC ISO format string"""
            if value is None:
                return None
            if isinstance(value, datetime):
                # Ensure timezone-aware
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            if isinstance(value, str):
                # Try to parse and ensure UTC
                try:
                    if 'Z' in value:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif '+' in value or value.count('-') > 2:
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = datetime.fromisoformat(value.replace('Z', ''))
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
                except:
                    return value
            if isinstance(value, (int, float)):
                # Assume timestamp
                try:
                    dt = datetime.fromtimestamp(value, tz=timezone.utc)
                    return dt.isoformat()
                except:
                    return None
            return value
        
        # Get created_at - preserve existing or use UTC now
        # หลีกเลี่ยง recursion: ถ้ากำลัง migrate อยู่ ไม่ต้อง load
        if task_id not in self._migrating_tasks:
            existing_data = self.load_transcription(task_id, skip_migration=True)
        else:
            existing_data = None
        created_at = transcription_data.get("created_at") or (existing_data.get("created_at") if existing_data else None)
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        else:
            created_at = get_utc_timestamp(created_at)
        
        # Get updated_at - use UTC now
        updated_at = transcription_data.get("updated_at")
        if updated_at is None:
            updated_at = datetime.now(timezone.utc).isoformat()
        else:
            updated_at = get_utc_timestamp(updated_at)
        
        # Get completed_at
        completed_at = transcription_data.get("completed_at")
        if completed_at:
            completed_at = get_utc_timestamp(completed_at)
        
        conn.execute("""
            INSERT OR REPLACE INTO transcriptions (
                task_id, created_at, updated_at, completed_at, file_path, file_url, file_name,
                language, total_duration, full_text, original_text, corrected_text, partial_text,
                chunks_json, status, progress, model_size, chunk_duration, error_message,
                processing_time, transcription_time, audio_extraction_time, text_correction_time,
                current_stage, current_stage_description, stage_progress,
                job_id, user_id, callback_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            created_at,
            updated_at,
            completed_at,
            transcription_data.get("file_path"),
            transcription_data.get("file_url"),
            transcription_data.get("file_name"),
            transcription_data.get("language"),
            transcription_data.get("total_duration"),
            transcription_data.get("full_text", ""),
            transcription_data.get("original_text"),
            transcription_data.get("corrected_text"),
            transcription_data.get("partial_text"),
            chunks_json,
            transcription_data.get("status", "completed"),
            transcription_data.get("progress", 0),
            transcription_data.get("model_size"),
            transcription_data.get("chunk_duration"),
            transcription_data.get("error_message"),
            transcription_data.get("processing_time"),
            transcription_data.get("transcription_time"),
            transcription_data.get("audio_extraction_time"),
            transcription_data.get("text_correction_time"),
            transcription_data.get("current_stage"),
            transcription_data.get("current_stage_description"),
            transcription_data.get("stage_progress"),
            transcription_data.get("job_id"),
            transcription_data.get("user_id"),
            transcription_data.get("callback_url")
        ))
        
        conn.commit()
        logger.info(f"บันทึก transcription: {task_id}")
        
        # ส่ง WebSocket notification สำหรับ realtime updates (ถ้ามี)
        # ใช้ threading เพื่อไม่ให้ block การบันทึก
        try:
            # ตรวจสอบว่าเป็น task ใหม่หรืออัปเดต
            is_new_task = existing_data is None or not existing_data
            
            # สร้าง task_data สำหรับ WebSocket notification
            task_data = {
                "task_id": task_id,
                "status": transcription_data.get("status", "pending"),
                "progress": transcription_data.get("progress", 0),
                "file_name": transcription_data.get("file_name"),
                "file_path": transcription_data.get("file_path"),
                "created_at": created_at,
                "updated_at": updated_at,
                "completed_at": completed_at,
                "language": transcription_data.get("language"),
                "total_duration": transcription_data.get("total_duration"),
                "current_stage": transcription_data.get("current_stage"),
                "current_stage_description": transcription_data.get("current_stage_description"),
            }
            
            # ส่ง notification แบบ async ใน background thread
            import threading
            thread = threading.Thread(
                target=self._notify_websocket_sync,
                args=(task_id, task_data, is_new_task),
                daemon=True
            )
            thread.start()
        except Exception as e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว
            logger.debug(f"Failed to send WebSocket notification for {task_id}: {e}")
        
        return task_id
    
    def _notify_websocket_sync(self, task_id: str, task_data: dict, is_new_task: bool):
        """Helper method สำหรับส่ง WebSocket notification (sync wrapper)"""
        try:
            import asyncio
            
            # สร้าง event loop ใหม่สำหรับ thread นี้
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # รัน async function
            loop.run_until_complete(self._notify_websocket(task_id, task_data, is_new_task))
        except Exception as e:
            logger.debug(f"WebSocket notification error: {e}")
    
    async def _notify_websocket(self, task_id: str, task_data: dict, is_new_task: bool):
        """
        Helper method สำหรับส่ง WebSocket notification (async)
        ส่ง notifications ตาม status เพื่อให้ frontend ได้รับ real-time updates
        """
        try:
            from ..services.websocket_service import websocket_manager
            
            status = task_data.get("status", "pending")
            progress = task_data.get("progress", 0)
            stage = task_data.get("current_stage", "")
            stage_description = task_data.get("current_stage_description", "")
            
            # ส่ง notifications ตาม status (ตามคำแนะนำ)
            if status == "completed":
                # ส่ง completed notification พร้อม results
                results = {
                    "text": task_data.get("full_text", "") or task_data.get("text", ""),
                    "chunks": task_data.get("chunks", []) or task_data.get("segments", []),
                    "duration": task_data.get("total_duration", 0),
                    "language": task_data.get("language", "th"),
                    "processing_time": task_data.get("processing_time", 0)
                }
                await websocket_manager.notify_transcription_completed(task_id, results)
                
                # ส่ง task list update สำหรับ history (backward compatibility)
                await websocket_manager.notify_task_list_update(task_id, task_data, "task.completed")
                
            elif status == "failed":
                # ส่ง failed notification
                error_message = task_data.get("error_message", task_data.get("error", "Unknown error"))
                await websocket_manager.notify_transcription_failed(task_id, error_message)
                
                # ส่ง task list update สำหรับ history (backward compatibility)
                await websocket_manager.notify_task_list_update(task_id, task_data, "task.failed")
                
            elif status in ["processing", "queued", "pending"]:
                # ส่ง progress update (rate-limited: เฉพาะเมื่อ progress เปลี่ยน >= 5% หรือ stage เปลี่ยน)
                # Note: Rate limiting จะทำใน caller (ไม่ต้องทำที่นี่)
                await websocket_manager.notify_transcription_progress(
                    task_id=task_id,
                    progress=progress,
                    status=status,
                    stage=stage or stage_description
                )
                
                # ส่ง task list update สำหรับ new tasks หรือ major updates
                if is_new_task:
                    await websocket_manager.notify_task_list_update(task_id, task_data, "task.created")
                elif progress > 0:  # Only update for significant changes
                    await websocket_manager.notify_task_list_update(task_id, task_data, "task.updated")
                    
            else:
                # Fallback: ส่ง generic update
                event_type = "task.created" if is_new_task else "task.updated"
                await websocket_manager.notify_task_list_update(task_id, task_data, event_type)
                
        except Exception as e:
            # ไม่ให้ WebSocket notification ทำให้การบันทึกล้มเหลว (non-critical)
            logger.debug(f"WebSocket notification error: {e}")
    
    def load_transcription(self, task_id: str, skip_migration: bool = False) -> Optional[Dict]:
        """
        โหลดข้อมูล transcription (return format compatible กับ JSONStorage)
        ถ้าไม่เจอใน SQLite จะลองอ่านจาก JSON เป็น fallback
        
        Args:
            task_id: Task ID
            skip_migration: ถ้า True จะไม่ทำ auto-migration (เพื่อป้องกัน recursion)
        """
        conn = self._get_connection()
        
        cursor = conn.execute(
            "SELECT * FROM transcriptions WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            # Fallback: ลองอ่านจาก JSON storage ถ้ามีไฟล์อยู่
            # แต่ไม่ทำ auto-migration ถ้า skip_migration=True หรือกำลัง migrate อยู่
            if skip_migration or task_id in self._migrating_tasks:
                try:
                    from .json_storage import JSONStorage
                    json_storage = JSONStorage()
                    json_data = json_storage.load_transcription(task_id)
                    if json_data:
                        logger.debug(f"📦 Found task {task_id} in JSON storage (skip migration)")
                        return json_data
                except Exception as e:
                    logger.debug(f"JSON fallback not available for task {task_id}: {e}")
                return None
            
            # Auto-migration (ถ้าไม่ skip)
            try:
                from .json_storage import JSONStorage
                json_storage = JSONStorage()
                json_data = json_storage.load_transcription(task_id)
                if json_data:
                    logger.info(f"📦 Found task {task_id} in JSON storage (fallback) - consider migrating to SQLite")
                    # ป้องกัน recursion: เพิ่ม task_id เข้า migrating set
                    self._migrating_tasks.add(task_id)
                    try:
                        self.save_transcription(task_id, json_data)
                        logger.info(f"✅ Auto-migrated task {task_id} from JSON to SQLite")
                    except Exception as migrate_error:
                        logger.warning(f"⚠️ Failed to auto-migrate task {task_id}: {migrate_error}")
                    finally:
                        # ลบ task_id ออกจาก migrating set
                        self._migrating_tasks.discard(task_id)
                    return json_data
            except Exception as e:
                logger.debug(f"JSON fallback not available for task {task_id}: {e}")
            
            return None
        
        try:
            # sqlite3.Row doesn't have .get() method, use dict() or direct access
            row_dict = dict(row) if hasattr(row, 'keys') else row
            chunks_json = row_dict.get('chunks_json') if isinstance(row_dict, dict) else (row['chunks_json'] if 'chunks_json' in row.keys() else None)
            chunks = json.loads(chunks_json) if chunks_json else []
        except Exception as e:
            logger.debug(f"Error parsing chunks_json: {e}")
            chunks = []
        
        # Helper function to safely get value from row (sqlite3.Row or dict)
        def get_row_value(key, default=None):
            if isinstance(row, dict):
                return row.get(key, default)
            elif hasattr(row, 'keys') and key in row.keys():
                return row[key]
            else:
                return default
        
        # Return format compatible กับ JSONStorage
        return {
            "task_id": row['task_id'],
            "created_at": get_row_value('created_at'),
            "updated_at": get_row_value('updated_at'),
            "completed_at": get_row_value('completed_at'),
            "file_path": get_row_value('file_path'),
            "file_url": get_row_value('file_url'),
            "file_name": get_row_value('file_name'),
            "language": get_row_value('language'),
            "total_duration": get_row_value('total_duration'),
            "chunks": chunks,
            "full_text": get_row_value('full_text', ''),
            "original_text": get_row_value('original_text'),
            "corrected_text": get_row_value('corrected_text'),
            "partial_text": get_row_value('partial_text'),
            "status": get_row_value('status', 'pending'),
            "progress": get_row_value('progress', 0),
            "model_size": get_row_value('model_size'),
            "chunk_duration": get_row_value('chunk_duration'),
            "error_message": get_row_value('error_message'),
            "processing_time": get_row_value('processing_time'),
            "transcription_time": get_row_value('transcription_time'),
            "audio_extraction_time": get_row_value('audio_extraction_time'),
            "text_correction_time": get_row_value('text_correction_time'),
            "current_stage": get_row_value('current_stage'),
            "current_stage_description": get_row_value('current_stage_description'),
            "stage_progress": get_row_value('stage_progress'),
            "job_id": get_row_value('job_id'),
            "user_id": get_row_value('user_id'),
            "callback_url": get_row_value('callback_url')
        }
    
    def list_all_transcriptions(self) -> List[Dict]:
        """ดึงรายการ transcription ทั้งหมด (return format compatible กับ JSONStorage)"""
        conn = self._get_connection()
        
        try:
            # Check if table exists and has required columns
            cursor = conn.execute("PRAGMA table_info(transcriptions)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if not columns:
                logger.warning("Transcriptions table does not exist")
                return []
            
            # Build SELECT query based on available columns
            # Use only columns that exist to avoid errors
            available_columns = [
                'task_id', 'created_at', 'updated_at', 'completed_at',
                'file_path', 'file_url', 'file_name', 'language', 'total_duration',
                'full_text', 'original_text', 'corrected_text', 'partial_text',
                'chunks_json', 'status', 'progress', 'model_size', 'chunk_duration',
                'error_message', 'processing_time', 'transcription_time',
                'audio_extraction_time', 'text_correction_time', 'current_stage',
                'current_stage_description', 'stage_progress', 'job_id', 'user_id', 'callback_url'
            ]
            
            # Filter to only columns that exist
            select_columns = [col for col in available_columns if col in columns]
            
            if not select_columns:
                logger.error("No valid columns found in transcriptions table")
                return []
            
            # Build query - use COALESCE for columns that might not exist
            select_clause = ", ".join(select_columns)
            
            # Determine order by column (use updated_at if available, else created_at)
            # Use COALESCE to fallback to created_at if updated_at is NULL
            # Convert to datetime for proper sorting (handle different formats)
            if 'updated_at' in columns and 'created_at' in columns:
                # Use COALESCE to prefer updated_at, fallback to created_at
                # Convert to datetime for proper sorting
                order_by = 'datetime(COALESCE(updated_at, created_at)) DESC, datetime(created_at) DESC'
            elif 'updated_at' in columns:
                order_by = 'datetime(updated_at) DESC'
            elif 'created_at' in columns:
                order_by = 'datetime(created_at) DESC'
            else:
                order_by = 'task_id DESC'  # Fallback
            
            # ใช้ LIMIT เพื่อลด load เมื่อมี tasks เยอะ (default: 1000 tasks)
            # ถ้าต้องการทั้งหมด ให้เรียกโดยไม่ระบุ limit
            max_tasks = int(os.getenv('SQLITE_MAX_TASKS_PER_QUERY', '1000'))
            cursor = conn.execute(f"""
                SELECT {select_clause} FROM transcriptions 
                ORDER BY {order_by}
                LIMIT {max_tasks}
            """)
            
            results = []
            for row in cursor.fetchall():
                try:
                    # Helper function to safely get value from row (sqlite3.Row or dict)
                    def get_row_val(key, default=None):
                        if isinstance(row, dict):
                            return row.get(key, default) if key in columns else default
                        elif hasattr(row, 'keys') and key in row.keys() and key in columns:
                            return row[key]
                        else:
                            return default
                    
                    chunks = []
                    chunks_json = get_row_val('chunks_json')
                    if chunks_json:
                        try:
                            chunks = json.loads(chunks_json)
                        except:
                            chunks = []
                    
                    # Return format compatible กับ JSONStorage
                    # Use helper function with default values for safety
                    result = {
                        "task_id": get_row_val('task_id', ''),
                        "created_at": get_row_val('created_at'),
                        "updated_at": get_row_val('updated_at'),
                        "completed_at": get_row_val('completed_at'),
                        "file_path": get_row_val('file_path'),
                        "file_url": get_row_val('file_url'),
                        "file_name": get_row_val('file_name'),
                        "language": get_row_val('language', 'th'),
                        "total_duration": get_row_val('total_duration'),
                        "chunks": chunks,
                        "full_text": get_row_val('full_text', ''),
                        "original_text": get_row_val('original_text'),
                        "corrected_text": get_row_val('corrected_text'),
                        "partial_text": get_row_val('partial_text'),
                        "status": get_row_val('status', 'pending'),
                        "progress": get_row_val('progress', 0),
                        "model_size": get_row_val('model_size'),
                        "chunk_duration": get_row_val('chunk_duration'),
                        "error_message": get_row_val('error_message'),
                        "processing_time": get_row_val('processing_time'),
                        "transcription_time": get_row_val('transcription_time'),
                        "audio_extraction_time": get_row_val('audio_extraction_time'),
                        "text_correction_time": get_row_val('text_correction_time'),
                        "current_stage": get_row_val('current_stage'),
                        "current_stage_description": get_row_val('current_stage_description'),
                        "stage_progress": get_row_val('stage_progress'),
                        "job_id": get_row_val('job_id'),
                        "user_id": get_row_val('user_id'),
                        "callback_url": get_row_val('callback_url')
                    }
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Error processing transcription row: {e}", exc_info=True)
                    continue
            
            # Fallback: เพิ่ม tasks จาก JSON storage ที่ยังไม่อยู่ใน SQLite
            # results is now a list of dicts, so we can use .get()
            sqlite_task_ids = {r.get('task_id') for r in results if r.get('task_id')}
            try:
                from .json_storage import JSONStorage
                json_storage = JSONStorage()
                json_tasks = json_storage.list_all_transcriptions()
                
                # เพิ่มเฉพาะ tasks ที่ยังไม่อยู่ใน SQLite
                for json_task in json_tasks:
                    task_id = json_task.get('task_id')
                    if task_id and task_id not in sqlite_task_ids:
                        logger.debug(f"📦 Found task {task_id} in JSON storage (not in SQLite) - adding to result")
                        results.append(json_task)
                        
                        # Optionally auto-migrate
                        try:
                            self.save_transcription(task_id, json_task)
                            logger.debug(f"✅ Auto-migrated task {task_id} from JSON to SQLite")
                        except Exception as migrate_error:
                            logger.debug(f"⚠️ Failed to auto-migrate task {task_id}: {migrate_error}")
                
                # Re-sort หลังจากรวมข้อมูล
                results.sort(key=lambda x: x.get('updated_at') or x.get('created_at') or '', reverse=True)
            except Exception as e:
                logger.debug(f"JSON fallback not available in list_all_transcriptions: {e}")
            
            return results
        except Exception as e:
            logger.error(f"Error listing transcriptions: {e}", exc_info=True)
            # Return empty list instead of crashing
            return []
    
    def search_transcription(self, task_id: str, query: str, case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription"""
        transcription = self.load_transcription(task_id)
        if not transcription:
            return []
        
        results = []
        query_pattern = query if case_sensitive else query.lower()
        
        for chunk in transcription.get("chunks", []):
            chunk_text = chunk.get("text", "")
            search_text = chunk_text if case_sensitive else chunk_text.lower()
            
            if query_pattern in search_text:
                matches = []
                start_pos = 0
                while True:
                    pos = search_text.find(query_pattern, start_pos)
                    if pos == -1:
                        break
                    matches.append(pos)
                    start_pos = pos + 1
                
                result = {
                    "start_time": chunk.get("start_time"),
                    "end_time": chunk.get("end_time"),
                    "text": chunk_text,
                    "confidence": chunk.get("confidence"),
                    "query": query,
                    "match_positions": matches,
                    "highlighted_text": self._highlight_text(chunk_text, query, matches)
                }
                results.append(result)
        
        return results
    
    def search_all_transcriptions(self, query: str, case_sensitive: bool = False) -> List[Dict]:
        """ค้นหาข้อความใน transcription ทั้งหมด"""
        conn = self._get_connection()
        
        # ใช้ SQLite FTS (Full-Text Search) หากต้องการ performance ดีขึ้น
        if case_sensitive:
            cursor = conn.execute(
                "SELECT task_id FROM transcriptions WHERE full_text LIKE ?",
                (f"%{query}%",)
            )
        else:
            cursor = conn.execute(
                "SELECT task_id FROM transcriptions WHERE LOWER(full_text) LIKE LOWER(?)",
                (f"%{query}%",)
            )
        
        all_results = []
        for row in cursor.fetchall():
            task_id = row['task_id']
            results = self.search_transcription(task_id, query, case_sensitive)
            
            for result in results:
                result["task_id"] = task_id
                all_results.append(result)
        
        return all_results
    
    def delete_transcription(self, task_id: str) -> bool:
        """ลบ transcription"""
        conn = self._get_connection()
        
        cursor = conn.execute("DELETE FROM transcriptions WHERE task_id = ?", (task_id,))
        conn.commit()
        
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"ลบ transcription: {task_id}")
        
        return deleted
    
    # Caption methods
    def save_caption(self, task_id: str, caption_data: Dict) -> str:
        """บันทึกข้อมูล caption"""
        conn = self._get_connection()
        
        segments_json = json.dumps(caption_data.get("segments", []), ensure_ascii=False)
        
        conn.execute("""
            INSERT OR REPLACE INTO captions (
                task_id, updated_at, file_path, language, subtitle_format,
                subtitle_content, segments_json, status, model_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            datetime.now().isoformat(),
            caption_data.get("file_path"),
            caption_data.get("language"),
            caption_data.get("subtitle_format"),
            caption_data.get("subtitle_content", ""),
            segments_json,
            caption_data.get("status", "completed"),
            caption_data.get("model_size")
        ))
        
        conn.commit()
        logger.info(f"บันทึก caption: {task_id}")
        return task_id
    
    def load_caption(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล caption"""
        conn = self._get_connection()
        
        cursor = conn.execute("SELECT * FROM captions WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        try:
            segments = json.loads(row['segments_json']) if row['segments_json'] else []
        except:
            segments = []
        
        return {
            "task_id": row['task_id'],
            "created_at": row['created_at'],
            "updated_at": row['updated_at'],
            "file_path": row['file_path'],
            "language": row['language'],
            "subtitle_format": row['subtitle_format'],
            "segments": segments,
            "subtitle_content": row['subtitle_content'],
            "status": row['status'],
            "model_size": row['model_size'],
            "error_message": row['error_message']
        }
    
    # Video task methods
    def save_video_task(self, task_id: str, video_data: Dict) -> str:
        """บันทึกข้อมูล video task"""
        conn = self._get_connection()
        
        input_files_json = json.dumps(video_data.get("input_files", []), ensure_ascii=False)
        operations_json = json.dumps(video_data.get("operations", []), ensure_ascii=False)
        results_json = json.dumps(video_data.get("results", {}), ensure_ascii=False)
        
        completed_at = None
        if video_data.get("completed_at"):
            completed_at = video_data["completed_at"]
        elif video_data.get("status") == "completed":
            completed_at = datetime.now().isoformat()
        
        conn.execute("""
            INSERT OR REPLACE INTO video_tasks (
                task_id, updated_at, completed_at, type, status, input_file,
                input_files_json, output_file, output_format, quality,
                start_time, end_time, width, height, operations_json,
                results_json, error_message, progress
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            datetime.now().isoformat(),
            completed_at,
            video_data.get("type"),
            video_data.get("status"),
            video_data.get("input_file"),
            input_files_json,
            video_data.get("output_file"),
            video_data.get("output_format"),
            video_data.get("quality"),
            video_data.get("start_time"),
            video_data.get("end_time"),
            video_data.get("width"),
            video_data.get("height"),
            operations_json,
            results_json,
            video_data.get("error_message"),
            video_data.get("progress", 0)
        ))
        
        conn.commit()
        logger.info(f"บันทึก video task: {task_id}")
        return task_id
    
    def load_video_task(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล video task"""
        conn = self._get_connection()
        
        cursor = conn.execute("SELECT * FROM video_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        try:
            input_files = json.loads(row['input_files_json']) if row['input_files_json'] else []
            operations = json.loads(row['operations_json']) if row['operations_json'] else []
            results = json.loads(row['results_json']) if row['results_json'] else {}
        except:
            input_files = []
            operations = []
            results = {}
        
        return {
            "task_id": row['task_id'],
            "created_at": row['created_at'],
            "updated_at": row['updated_at'],
            "completed_at": row['completed_at'],
            "type": row['type'],
            "status": row['status'],
            "input_file": row['input_file'],
            "input_files": input_files,
            "output_file": row['output_file'],
            "output_format": row['output_format'],
            "quality": row['quality'],
            "start_time": row['start_time'],
            "end_time": row['end_time'],
            "width": row['width'],
            "height": row['height'],
            "operations": operations,
            "results": results,
            "error_message": row['error_message'],
            "progress": row['progress']
        }
    
    def list_all_video_tasks(self) -> List[Dict]:
        """ดึงรายการ video tasks ทั้งหมด"""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            SELECT task_id, created_at, type, status, input_file, output_file,
                   output_format, quality, progress, error_message
            FROM video_tasks 
            ORDER BY created_at DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "task_id": row['task_id'],
                "created_at": row['created_at'],
                "type": row['type'],
                "status": row['status'],
                "input_file": row['input_file'],
                "output_file": row['output_file'],
                "output_format": row['output_format'],
                "quality": row['quality'],
                "progress": row['progress'],
                "error_message": row['error_message']
            })
        
        return results
    
    def delete_video_task(self, task_id: str) -> bool:
        """ลบ video task"""
        conn = self._get_connection()
        
        cursor = conn.execute("DELETE FROM video_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"ลบ video task: {task_id}")
        
        return deleted
    
    # Live stream methods
    def save_live_stream(self, stream_id: str, stream_data: Dict) -> str:
        """บันทึกข้อมูล live stream"""
        conn = self._get_connection()
        
        last_transcription_json = json.dumps(
            stream_data.get("last_transcription", {}), 
            ensure_ascii=False
        )
        
        ended_at = None
        if stream_data.get("ended_at"):
            ended_at = stream_data["ended_at"]
        elif stream_data.get("status") == "completed":
            ended_at = datetime.now().isoformat()
        
        conn.execute("""
            INSERT OR REPLACE INTO live_streams (
                stream_id, updated_at, ended_at, status, language, model_size,
                total_audio_duration, transcription_count, last_transcription_json,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stream_id,
            datetime.now().isoformat(),
            ended_at,
            stream_data.get("status", "active"),
            stream_data.get("language"),
            stream_data.get("model_size"),
            stream_data.get("total_audio_duration", 0),
            stream_data.get("transcription_count", 0),
            last_transcription_json,
            stream_data.get("error_message")
        ))
        
        conn.commit()
        logger.info(f"บันทึก live stream: {stream_id}")
        return stream_id
    
    def load_live_stream(self, stream_id: str) -> Optional[Dict]:
        """โหลดข้อมูล live stream"""
        conn = self._get_connection()
        
        cursor = conn.execute("SELECT * FROM live_streams WHERE stream_id = ?", (stream_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        try:
            last_transcription = json.loads(row['last_transcription_json']) if row['last_transcription_json'] else {}
        except:
            last_transcription = {}
        
        return {
            "stream_id": row['stream_id'],
            "created_at": row['created_at'],
            "updated_at": row['updated_at'],
            "ended_at": row['ended_at'],
            "status": row['status'],
            "language": row['language'],
            "model_size": row['model_size'],
            "total_audio_duration": row['total_audio_duration'],
            "transcription_count": row['transcription_count'],
            "last_transcription": last_transcription,
            "error_message": row['error_message']
        }
    
    # Utility methods
    def cleanup_old_files(self, max_age_hours: int = 24):
        """ลบข้อมูลเก่า"""
        conn = self._get_connection()
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        cutoff_datetime = datetime.fromtimestamp(cutoff_time).isoformat()
        
        # ลบ transcriptions เก่า
        cursor = conn.execute(
            "DELETE FROM transcriptions WHERE created_at < ?",
            (cutoff_datetime,)
        )
        transcription_deleted = cursor.rowcount
        
        # ลบ video tasks เก่า
        cursor = conn.execute(
            "DELETE FROM video_tasks WHERE created_at < ?",
            (cutoff_datetime,)
        )
        video_deleted = cursor.rowcount
        
        # ลบ captions เก่า
        cursor = conn.execute(
            "DELETE FROM captions WHERE created_at < ?",
            (cutoff_datetime,)
        )
        caption_deleted = cursor.rowcount
        
        # ลบ live streams เก่า
        cursor = conn.execute(
            "DELETE FROM live_streams WHERE created_at < ?",
            (cutoff_datetime,)
        )
        stream_deleted = cursor.rowcount
        
        conn.commit()
        
        logger.info(f"ลบข้อมูลเก่า: transcriptions={transcription_deleted}, "
                   f"videos={video_deleted}, captions={caption_deleted}, "
                   f"streams={stream_deleted}")
    
    def get_transcription_stats(self, task_id: str) -> Dict:
        """ดึงสถิติของ transcription"""
        transcription = self.load_transcription(task_id)
        if not transcription:
            return {}
        
        chunks = transcription.get("chunks", [])
        total_words = sum(len(chunk.get("text", "").split()) for chunk in chunks)
        total_chars = sum(len(chunk.get("text", "")) for chunk in chunks)
        
        return {
            "task_id": task_id,
            "total_chunks": len(chunks),
            "total_words": total_words,
            "total_characters": total_chars,
            "total_duration": transcription.get("total_duration"),
            "language": transcription.get("language"),
            "average_confidence": sum(
                chunk.get("confidence", 0) for chunk in chunks
            ) / len(chunks) if chunks else 0
        }
    
    def _highlight_text(self, text: str, query: str, positions: List[int]) -> str:
        """ไฮไลท์ข้อความที่ตรงกับคำค้นหา"""
        if not positions:
            return text
        
        positions.sort(reverse=True)
        highlighted = text
        for pos in positions:
            start = pos
            end = pos + len(query)
            highlighted = (
                highlighted[:start] + 
                f"**{highlighted[start:end]}**" + 
                highlighted[end:]
            )
        
        return highlighted
    
    def get_database_stats(self) -> Dict:
        """ดึงสถิติ database"""
        conn = self._get_connection()
        
        stats = {}
        
        # นับจำนวน records ในแต่ละ table
        tables = ['transcriptions', 'captions', 'video_tasks', 'live_streams']
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()['count']
            stats[table] = count
        
        # ขนาด database
        cursor = conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()['size']
        stats['database_size_bytes'] = db_size
        stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
        
        return stats
    
    def close(self):
        """ปิด database connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')
