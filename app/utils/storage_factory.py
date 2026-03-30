"""
Storage Factory
สำหรับเลือกใช้ storage backend (JSON, SQLite, หรือ PostgreSQL) ตาม environment
"""

import os
import logging
from typing import Union

from .json_storage import JSONStorage
from .sqlite_storage import SQLiteStorage

logger = logging.getLogger(__name__)

class StorageFactory:
    """Factory สำหรับสร้าง storage instance"""

    @staticmethod
    def create_storage() -> Union[JSONStorage, SQLiteStorage, "PostgresStorage"]:
        """สร้าง storage instance ตาม environment variable"""

        storage_type = os.getenv('STORAGE_TYPE', 'json').lower()

        if storage_type == 'postgres':
            from .postgres_storage import PostgresStorage
            database_url = os.getenv('POSTGRES_URL')
            if not database_url:
                raise ValueError("POSTGRES_URL environment variable is required when STORAGE_TYPE=postgres")
            sqlite_db_path = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
            logger.info(f"Using PostgreSQL storage (SQLite delegate: {sqlite_db_path})")
            return PostgresStorage(database_url, sqlite_db_path)

        elif storage_type == 'sqlite':
            db_path = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
            logger.info(f"Using SQLite storage: {db_path}")
            return SQLiteStorage(db_path)

        elif storage_type == 'json':
            storage_dir = os.getenv('JSON_STORAGE_DIR', 'storage')
            logger.info(f"Using JSON storage: {storage_dir}")
            return JSONStorage(storage_dir)

        else:
            logger.warning(f"Unknown storage type '{storage_type}', falling back to JSON storage")
            return JSONStorage()

    @staticmethod
    def get_storage_info() -> dict:
        """ดึงข้อมูลเกี่ยวกับ storage ที่ใช้"""
        storage_type = os.getenv('STORAGE_TYPE', 'json').lower()

        info = {
            "storage_type": storage_type,
            "environment": os.getenv('ENVIRONMENT', 'development')
        }

        if storage_type == 'postgres':
            postgres_url = os.getenv('POSTGRES_URL', '')
            # ซ่อน password
            if '@' in postgres_url:
                info["database_host"] = postgres_url.split('@')[-1]
            info["sqlite_delegate_path"] = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
        elif storage_type == 'sqlite':
            info["database_path"] = os.getenv('SQLITE_DB_PATH', 'storage/database.db')
        else:
            info["storage_directory"] = os.getenv('JSON_STORAGE_DIR', 'storage')

        return info

# สร้าง global storage instance
def get_storage() -> Union[JSONStorage, SQLiteStorage]:
    """ดึง storage instance (singleton pattern)"""
    if not hasattr(get_storage, '_instance'):
        get_storage._instance = StorageFactory.create_storage()
    return get_storage._instance

# สำหรับ reset storage instance (ใช้ใน testing)
def reset_storage():
    """Reset storage instance"""
    if hasattr(get_storage, '_instance'):
        if hasattr(get_storage._instance, 'close'):
            get_storage._instance.close()
        delattr(get_storage, '_instance')
