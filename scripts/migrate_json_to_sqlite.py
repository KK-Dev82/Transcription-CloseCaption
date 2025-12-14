#!/usr/bin/env python3
"""
Migration Script: JSON Storage → SQLite Storage
ย้ายข้อมูล transcription tasks จาก JSON files ไป SQLite database
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.json_storage import JSONStorage
from app.utils.sqlite_storage import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_transcriptions(json_storage: JSONStorage, sqlite_storage: SQLiteStorage) -> Dict[str, int]:
    """Migrate all transcriptions from JSON to SQLite"""
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    logger.info("🔄 Starting migration from JSON to SQLite...")
    
    # Get all transcriptions from JSON storage
    transcriptions = json_storage.list_all_transcriptions()
    stats['total'] = len(transcriptions)
    
    logger.info(f"📊 Found {stats['total']} transcriptions to migrate")
    
    for idx, transcription in enumerate(transcriptions, 1):
        task_id = transcription.get('task_id')
        if not task_id:
            logger.warning(f"⚠️  Skipping transcription #{idx}: No task_id")
            stats['skipped'] += 1
            continue
        
        try:
            # Check if already exists in SQLite
            existing = sqlite_storage.load_transcription(task_id)
            if existing:
                logger.debug(f"⏭️  Task {task_id} already exists in SQLite, skipping...")
                stats['skipped'] += 1
                continue
            
            # Prepare data for SQLite
            # SQLiteStorage expects specific fields
            migration_data = {
                'task_id': task_id,
                'file_path': transcription.get('file_path'),
                'language': transcription.get('language', 'th'),
                'total_duration': transcription.get('total_duration'),
                'full_text': transcription.get('full_text', ''),
                'chunks': transcription.get('chunks', []),
                'status': transcription.get('status', 'pending'),
                'model_size': transcription.get('model_size', 'medium'),
                'chunk_duration': transcription.get('chunk_duration'),
                'error_message': transcription.get('error_message'),
                'created_at': transcription.get('created_at'),
                'updated_at': transcription.get('updated_at'),
                'completed_at': transcription.get('completed_at'),
                'progress': transcription.get('progress', 0),
                'processing_time': transcription.get('processing_time'),
                'transcription_time': transcription.get('transcription_time'),
                'audio_extraction_time': transcription.get('audio_extraction_time'),
                'text_correction_time': transcription.get('text_correction_time'),
                'current_stage': transcription.get('current_stage'),
                'current_stage_description': transcription.get('current_stage_description'),
                'stage_progress': transcription.get('stage_progress'),
            }
            
            # Save to SQLite using direct connection (bypass save_transcription to include all fields)
            conn = sqlite_storage._get_connection()
            
            chunks_json = json.dumps(migration_data.get('chunks', []), ensure_ascii=False)
            
            # Insert with all fields
            conn.execute("""
                INSERT OR REPLACE INTO transcriptions (
                    task_id, created_at, updated_at, file_path, language, total_duration,
                    full_text, chunks_json, status, model_size, chunk_duration, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                migration_data['task_id'],
                migration_data.get('created_at') or datetime.now().isoformat(),
                migration_data.get('updated_at') or datetime.now().isoformat(),
                migration_data.get('file_path'),
                migration_data.get('language'),
                migration_data.get('total_duration'),
                migration_data.get('full_text', ''),
                chunks_json,
                migration_data.get('status', 'pending'),
                migration_data.get('model_size'),
                migration_data.get('chunk_duration'),
                migration_data.get('error_message')
            ))
            
            conn.commit()
            
            stats['success'] += 1
            if idx % 100 == 0:
                logger.info(f"✅ Migrated {idx}/{stats['total']} transcriptions...")
        
        except Exception as e:
            logger.error(f"❌ Failed to migrate task {task_id}: {e}")
            stats['failed'] += 1
    
    logger.info(f"✅ Migration completed!")
    logger.info(f"   Total: {stats['total']}")
    logger.info(f"   Success: {stats['success']}")
    logger.info(f"   Failed: {stats['failed']}")
    logger.info(f"   Skipped: {stats['skipped']}")
    
    return stats

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate JSON storage to SQLite')
    parser.add_argument('--json-dir', default='storage', help='JSON storage directory')
    parser.add_argument('--sqlite-db', default='storage/database.db', help='SQLite database path')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no actual migration)')
    
    args = parser.parse_args()
    
    # Initialize storages
    json_storage = JSONStorage(args.json_dir)
    sqlite_storage = SQLiteStorage(args.sqlite_db)
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be migrated")
        transcriptions = json_storage.list_all_transcriptions()
        logger.info(f"📊 Would migrate {len(transcriptions)} transcriptions")
        return
    
    # Perform migration
    stats = migrate_transcriptions(json_storage, sqlite_storage)
    
    if stats['failed'] > 0:
        logger.warning(f"⚠️  {stats['failed']} transcriptions failed to migrate")
        sys.exit(1)
    
    logger.info("🎉 Migration completed successfully!")

if __name__ == '__main__':
    main()

