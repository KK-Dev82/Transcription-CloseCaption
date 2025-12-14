#!/usr/bin/env python3
"""
Fix SQLite Schema Script
แก้ไข SQLite database schema ที่มีปัญหา (เช่น column ไม่มี)
"""

import sqlite3
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_sqlite_schema(db_path: str):
    """Fix SQLite database schema"""
    db_file = Path(db_path)
    
    if not db_file.exists():
        logger.info(f"Database file does not exist: {db_path}")
        logger.info("Will be created automatically when service starts")
        return
    
    logger.info(f"🔧 Fixing SQLite schema: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # Check if transcriptions table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transcriptions'")
        if not cursor.fetchone():
            logger.info("Transcriptions table does not exist - will be created on next service start")
            conn.close()
            return
        
        # Get existing columns
        cursor = conn.execute("PRAGMA table_info(transcriptions)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Existing columns: {existing_columns}")
        
        # Columns to add
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
        
        added_count = 0
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    conn.execute(f"ALTER TABLE transcriptions ADD COLUMN {col_name} {col_type}")
                    logger.info(f"  ✅ Added column: {col_name}")
                    added_count += 1
                except Exception as e:
                    logger.warning(f"  ⚠️  Failed to add column {col_name}: {e}")
        
        conn.commit()
        
        if added_count > 0:
            logger.info(f"✅ Schema fixed: Added {added_count} columns")
        else:
            logger.info("✅ Schema is already up to date")
        
        # Create indexes if they don't exist
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_status ON transcriptions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at ON transcriptions(created_at)")
            
            if 'updated_at' in existing_columns or 'updated_at' in new_columns:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_updated_at ON transcriptions(updated_at)")
            if 'completed_at' in existing_columns or 'completed_at' in new_columns:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_transcriptions_completed_at ON transcriptions(completed_at)")
            
            conn.commit()
            logger.info("✅ Indexes created/verified")
        except Exception as e:
            logger.warning(f"⚠️  Error creating indexes: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error fixing schema: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix SQLite database schema')
    parser.add_argument('--db-path', default='storage/database.db', help='SQLite database path')
    
    args = parser.parse_args()
    
    fix_sqlite_schema(args.db_path)
    logger.info("🎉 Schema fix completed!")

if __name__ == '__main__':
    main()

