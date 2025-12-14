"""
SQLite Storage Service
ทดแทน JSON Storage สำหรับ staging/production deployment
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

class SQLiteStorage:
    def __init__(self, db_path: str = "storage/database.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Thread-local storage สำหรับ connection
        self._local = threading.local()
        
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
        
        # Indexes สำหรับ performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_updated_at ON transcriptions(updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_completed_at ON transcriptions(completed_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_captions_status ON captions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_video_tasks_status ON video_tasks(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_video_tasks_type ON video_tasks(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_live_streams_status ON live_streams(status)")
        
        # Migrate existing table schema (add new columns if they don't exist)
        try:
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
                    conn.execute(f"ALTER TABLE transcriptions ADD COLUMN {col_name} {col_type}")
            
            conn.commit()
        except Exception as e:
            logger.warning(f"Error migrating table schema: {e}")
        
        conn.commit()
    
    # Transcription methods
    def save_transcription(self, task_id: str, transcription_data: Dict) -> str:
        """บันทึกข้อมูล transcription"""
        conn = self._get_connection()
        
        chunks_json = json.dumps(transcription_data.get("chunks", []), ensure_ascii=False)
        
        conn.execute("""
            INSERT OR REPLACE INTO transcriptions (
                task_id, updated_at, file_path, language, total_duration,
                full_text, chunks_json, status, model_size, chunk_duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            datetime.now().isoformat(),
            transcription_data.get("file_path"),
            transcription_data.get("language"),
            transcription_data.get("total_duration"),
            transcription_data.get("full_text", ""),
            chunks_json,
            transcription_data.get("status", "completed"),
            transcription_data.get("model_size"),
            transcription_data.get("chunk_duration")
        ))
        
        conn.commit()
        logger.info(f"บันทึก transcription: {task_id}")
        return task_id
    
    def load_transcription(self, task_id: str) -> Optional[Dict]:
        """โหลดข้อมูล transcription (return format compatible กับ JSONStorage)"""
        conn = self._get_connection()
        
        cursor = conn.execute(
            "SELECT * FROM transcriptions WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        try:
            chunks = json.loads(row['chunks_json']) if row.get('chunks_json') else []
        except:
            chunks = []
        
        # Return format compatible กับ JSONStorage
        return {
            "task_id": row['task_id'],
            "created_at": row.get('created_at'),
            "updated_at": row.get('updated_at'),
            "completed_at": row.get('completed_at'),
            "file_path": row.get('file_path'),
            "file_url": row.get('file_url'),
            "file_name": row.get('file_name'),
            "language": row.get('language'),
            "total_duration": row.get('total_duration'),
            "chunks": chunks,
            "full_text": row.get('full_text', ''),
            "original_text": row.get('original_text'),
            "corrected_text": row.get('corrected_text'),
            "partial_text": row.get('partial_text'),
            "status": row.get('status', 'pending'),
            "progress": row.get('progress', 0),
            "model_size": row.get('model_size'),
            "chunk_duration": row.get('chunk_duration'),
            "error_message": row.get('error_message'),
            "processing_time": row.get('processing_time'),
            "transcription_time": row.get('transcription_time'),
            "audio_extraction_time": row.get('audio_extraction_time'),
            "text_correction_time": row.get('text_correction_time'),
            "current_stage": row.get('current_stage'),
            "current_stage_description": row.get('current_stage_description'),
            "stage_progress": row.get('stage_progress'),
            "job_id": row.get('job_id'),
            "user_id": row.get('user_id'),
            "callback_url": row.get('callback_url')
        }
    
    def list_all_transcriptions(self) -> List[Dict]:
        """ดึงรายการ transcription ทั้งหมด (return format compatible กับ JSONStorage)"""
        conn = self._get_connection()
        
        # Load full data (compatible with JSONStorage format)
        cursor = conn.execute("""
            SELECT * FROM transcriptions 
            ORDER BY updated_at DESC, created_at DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            try:
                chunks = json.loads(row['chunks_json']) if row.get('chunks_json') else []
            except:
                chunks = []
            
            # Return format compatible กับ JSONStorage
            result = {
                "task_id": row['task_id'],
                "created_at": row.get('created_at'),
                "updated_at": row.get('updated_at'),
                "completed_at": row.get('completed_at'),
                "file_path": row.get('file_path'),
                "file_url": row.get('file_url'),
                "file_name": row.get('file_name'),
                "language": row.get('language'),
                "total_duration": row.get('total_duration'),
                "chunks": chunks,
                "full_text": row.get('full_text', ''),
                "original_text": row.get('original_text'),
                "corrected_text": row.get('corrected_text'),
                "partial_text": row.get('partial_text'),
                "status": row.get('status', 'pending'),
                "progress": row.get('progress', 0),
                "model_size": row.get('model_size'),
                "chunk_duration": row.get('chunk_duration'),
                "error_message": row.get('error_message'),
                "processing_time": row.get('processing_time'),
                "transcription_time": row.get('transcription_time'),
                "audio_extraction_time": row.get('audio_extraction_time'),
                "text_correction_time": row.get('text_correction_time'),
                "current_stage": row.get('current_stage'),
                "current_stage_description": row.get('current_stage_description'),
                "stage_progress": row.get('stage_progress'),
                "job_id": row.get('job_id'),
                "user_id": row.get('user_id'),
                "callback_url": row.get('callback_url')
            }
            results.append(result)
        
        return results
    
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
