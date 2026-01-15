"""
Logging Configuration with Rotation
- Detailed transcription logs
- Log rotation (by size and time)
"""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime

def setup_logging():
    """
    Setup logging configuration with rotation
    """
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Get log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Main API log file (rotating by size: 10MB, keep 5 backups)
    main_api_log = logs_dir / "main-api.log"
    main_api_handler = RotatingFileHandler(
        main_api_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_api_handler.setLevel(logging.DEBUG)
    main_api_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    main_api_handler.setFormatter(main_api_formatter)
    root_logger.addHandler(main_api_handler)
    
    # Transcription log file (rotating by time: daily, keep 7 days)
    transcription_log = logs_dir / "transcription.log"
    transcription_handler = TimedRotatingFileHandler(
        transcription_log,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    transcription_handler.setLevel(logging.DEBUG)
    transcription_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    transcription_handler.setFormatter(transcription_formatter)
    
    # Add transcription handler to specific loggers
    transcription_loggers = [
        'app.api.realtime_transcription',
        'app.workers.rq_worker',
        'app.services.whisper_service',
        'app.services.whisper_providers.faster_whisper_provider',
        'app.services.transcription_service'
    ]
    
    for logger_name in transcription_loggers:
        logger = logging.getLogger(logger_name)
        logger.addHandler(transcription_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True  # Also propagate to root logger
    
    # Live-chunk specific log file (rotating by size: 10MB, keep 5 backups)
    live_chunk_log = logs_dir / "live-chunk.log"
    live_chunk_handler = RotatingFileHandler(
        live_chunk_log,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    live_chunk_handler.setLevel(logging.DEBUG)
    live_chunk_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    live_chunk_handler.setFormatter(live_chunk_formatter)
    
    # Add live-chunk handler to specific loggers
    live_chunk_loggers = [
        'app.api.realtime_transcription',
        'app.workers.rq_worker',
        'app.api.internal',
        'app.services.websocket_service'
    ]
    
    for logger_name in live_chunk_loggers:
        logger = logging.getLogger(logger_name)
        logger.addHandler(live_chunk_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
    
    logging.info(f"✅ Logging configured: level={log_level}, logs_dir={logs_dir}")
    logging.info(f"   - Main API: {main_api_log} (rotating, 10MB, 5 backups)")
    logging.info(f"   - Transcription: {transcription_log} (daily rotation, 7 days)")
    logging.info(f"   - Live-chunk: {live_chunk_log} (rotating, 10MB, 5 backups)")
