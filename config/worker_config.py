"""
Worker Configuration (Python Format)

Alternative configuration format using Python instead of .env file
Can be used by importing this module directly
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# ============================================================================
# Environment & Storage
# ============================================================================
ENVIRONMENT = os.getenv('ENVIRONMENT', 'runpod')
STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'json')
JSON_STORAGE_DIR = os.getenv('JSON_STORAGE_DIR', str(BASE_DIR / 'storage'))

# ============================================================================
# RabbitMQ Configuration
# ============================================================================
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', '178.128.105.100')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'senate')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'qP2VtHz6fAX4xDksEpMrLT')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')

RABBITMQ_HEARTBEAT_TIMEOUT = int(os.getenv('RABBITMQ_HEARTBEAT_TIMEOUT', '1800'))
RABBITMQ_BLOCKED_TIMEOUT = int(os.getenv('RABBITMQ_BLOCKED_TIMEOUT', '600'))
RABBITMQ_CONNECTION_CHECK_INTERVAL = int(os.getenv('RABBITMQ_CONNECTION_CHECK_INTERVAL', '30'))

# ============================================================================
# Redis Configuration
# ============================================================================
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# ============================================================================
# Whisper Provider Configuration
# ============================================================================
WHISPER_PROVIDER = os.getenv('WHISPER_PROVIDER', 'faster-whisper')
WHISPER_API_URL = os.getenv('WHISPER_API_URL', 'http://localhost:8002')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'medium')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'cuda')
WHISPER_USE_THREAD_LOCAL = os.getenv('WHISPER_USE_THREAD_LOCAL', 'false').lower() == 'true'

WHISPER_COMPUTE_TYPE = os.getenv('WHISPER_COMPUTE_TYPE', 'float16')
WHISPER_BATCH_SIZE = int(os.getenv('WHISPER_BATCH_SIZE', '32'))

# ============================================================================
# GPU Configuration
# ============================================================================
CUDA_VISIBLE_DEVICES = os.getenv('CUDA_VISIBLE_DEVICES', '0')
WHISPER_CUBLAS = int(os.getenv('WHISPER_CUBLAS', '1'))

GPU_TRANSCRIPTION_MAX_RETRIES = int(os.getenv('GPU_TRANSCRIPTION_MAX_RETRIES', '3'))
GPU_TRANSCRIPTION_RETRY_DELAY = float(os.getenv('GPU_TRANSCRIPTION_RETRY_DELAY', '5.0'))

# ============================================================================
# Timezone
# ============================================================================
TZ = os.getenv('TZ', 'Asia/Bangkok')
TZDIR = os.getenv('TZDIR', '/usr/share/zoneinfo')

# ============================================================================
# Queue Limits
# ============================================================================
MAX_QUEUE_REQUEST = int(os.getenv('MAX_QUEUE_REQUEST', '51'))  # 50 video + 1 close caption
MAX_QUEUE_EXTRACTION = int(os.getenv('MAX_QUEUE_EXTRACTION', '80'))
MAX_QUEUE_TRANSCRIBE = int(os.getenv('MAX_QUEUE_TRANSCRIBE', '20'))
RETRY_AFTER_SECONDS = int(os.getenv('RETRY_AFTER_SECONDS', '30'))
TRANSCRIPTION_MAX_QUEUE_SIZE = int(os.getenv('TRANSCRIPTION_MAX_QUEUE_SIZE', '50'))

# ============================================================================
# Audio Extraction Configuration
# ============================================================================
AUDIO_EXTRACTION_MAX_WORKERS = int(os.getenv('AUDIO_EXTRACTION_MAX_WORKERS', '3'))
EXTRACT_POOL_SIZE = int(os.getenv('EXTRACT_POOL_SIZE', '4'))
FFMPEG_PROC_SEM = int(os.getenv('FFMPEG_PROC_SEM', '3'))
EXTRACT_TASK_TIMEOUT = int(os.getenv('EXTRACT_TASK_TIMEOUT', '900'))
AUDIO_EXTRACTION_PREFETCH_COUNT = int(os.getenv('AUDIO_EXTRACTION_PREFETCH_COUNT', '1'))

# ============================================================================
# Transcription Configuration
# ============================================================================
TRANSCRIPTION_MAX_WORKERS = int(os.getenv('TRANSCRIPTION_MAX_WORKERS', '5'))
TRANSCRIPTION_QUEUE_PREFETCH_COUNT = int(os.getenv('TRANSCRIPTION_QUEUE_PREFETCH_COUNT', '1'))
TRANSCRIPTION_PREFETCH_COUNT = int(os.getenv('TRANSCRIPTION_PREFETCH_COUNT', '5'))
TRANSCRIPTION_REQUEST_PREFETCH_COUNT = int(os.getenv('TRANSCRIPTION_REQUEST_PREFETCH_COUNT', '1'))

# Task Timeout Configuration
TRANSCRIPTION_TASK_TIMEOUT_SECONDS = int(os.getenv('TRANSCRIPTION_TASK_TIMEOUT_SECONDS', '3600'))
TASK_TIMEOUT_SECONDS = int(os.getenv('TASK_TIMEOUT_SECONDS', '1800'))
TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS = int(os.getenv('TRANSCRIPTION_PROCESSING_TIMEOUT_SECONDS', '1800'))

# Stuck Task Detection Configuration
STUCK_TASK_THRESHOLD_SECONDS = int(os.getenv('STUCK_TASK_THRESHOLD_SECONDS', '600'))
STUCK_TASK_CHECK_INTERVAL_SECONDS = int(os.getenv('STUCK_TASK_CHECK_INTERVAL_SECONDS', '60'))

# ============================================================================
# Final Architecture Settings
# ============================================================================
GPU_CONCURRENCY = int(os.getenv('GPU_CONCURRENCY', '2'))
ALLOW_CPU_FALLBACK = os.getenv('ALLOW_CPU_FALLBACK', 'false').lower() == 'true'
USE_QUORUM_QUEUES = os.getenv('USE_QUORUM_QUEUES', 'true').lower() == 'true'
ENABLE_DLX = os.getenv('ENABLE_DLX', 'true').lower() == 'true'
USE_3QUEUE_ARCHITECTURE = os.getenv('USE_3QUEUE_ARCHITECTURE', 'true').lower() == 'true'

# ============================================================================
# Cleanup Service Configuration
# ============================================================================
CLEANUP_INTERVAL_SECONDS = int(os.getenv('CLEANUP_INTERVAL_SECONDS', '3600'))
TEMP_FOLDER_MAX_AGE_HOURS = int(os.getenv('TEMP_FOLDER_MAX_AGE_HOURS', '24'))
DISK_SPACE_WARNING_THRESHOLD_GB = float(os.getenv('DISK_SPACE_WARNING_THRESHOLD_GB', '10.0'))
DISK_SPACE_CRITICAL_THRESHOLD_GB = float(os.getenv('DISK_SPACE_CRITICAL_THRESHOLD_GB', '5.0'))

# ============================================================================
# Worker Type
# ============================================================================
VIDEO_WORKER_TYPE = os.getenv('VIDEO_WORKER_TYPE', 'async')

# ============================================================================
# Backend API Configuration
# ============================================================================
BACKEND_API_BASE_URL = os.getenv('BACKEND_API_BASE_URL', 'http://localhost:5173')
BACKEND_URL = os.getenv('BACKEND_URL', BACKEND_API_BASE_URL)
FILE_SERVICE_URL = os.getenv('FILE_SERVICE_URL', 'http://localhost:5182')

# ============================================================================
# Configuration Summary
# ============================================================================
def get_config_summary():
    """Get configuration summary for logging"""
    return {
        'environment': ENVIRONMENT,
        'rabbitmq_host': RABBITMQ_HOST,
        'whisper_provider': WHISPER_PROVIDER,
        'whisper_model': WHISPER_MODEL,
        'gpu_concurrency': GPU_CONCURRENCY,
        'transcription_timeout': TRANSCRIPTION_TASK_TIMEOUT_SECONDS,
        'stuck_task_threshold': STUCK_TASK_THRESHOLD_SECONDS,
        'worker_type': VIDEO_WORKER_TYPE,
    }

