"""
SQLite Schema Initialization
Centralized schema initialization for SQLite database
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_sqlite_schema(db_path: str, connection: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """
    Ensure SQLite schema is initialized (create tables if not exist)
    
    Args:
        db_path: Path to SQLite database
        connection: Optional existing connection (will create new if None)
    
    Returns:
        sqlite3.Connection with schema initialized
    """
    if connection is None:
        db_path_obj = Path(db_path)
        db_path_obj.parent.mkdir(exist_ok=True)
        connection = sqlite3.connect(str(db_path), check_same_thread=False)
    
    # Set pragmas for better performance
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    
    # 1. Ensure transcriptions table exists (required for FK)
    connection.execute("""
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
            callback_url TEXT,
            enable_diarization INTEGER DEFAULT 0
        )
    """)
    # Migration: add enable_diarization if missing (สำหรับ DB ที่มีอยู่แล้ว)
    try:
        connection.execute("ALTER TABLE transcriptions ADD COLUMN enable_diarization INTEGER DEFAULT 0")
        connection.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            logger.debug(f"Schema migration enable_diarization: {e}")
    
    # 2. Ensure segments table exists (for streaming segments)
    connection.execute("""
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
    
    # 3. Ensure index exists for query performance
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_segments_task_id_start 
        ON segments(task_id, start_time)
    """)
    
    # 4. Webhook dead-letter table (failed deliveries ที่ retries หมดแล้ว)
    connection.execute("""
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
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dead_letter_resolved
        ON webhook_dead_letter(resolved, failed_at)
    """)

    connection.commit()
    logger.debug(f"SQLite schema ensured for {db_path}")

    return connection


