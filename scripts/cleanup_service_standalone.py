#!/usr/bin/env python3
"""
Standalone Cleanup Service
รัน cleanup เป็น service แยกจาก API เพื่อให้แน่ใจว่าทำงานเสมอ
เหมาะสำหรับ deployment ที่แยก process (API vs RQ worker)

Usage:
    python -m scripts.cleanup_service_standalone
    หรือ
    python scripts/cleanup_service_standalone.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env.runpod if exists
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env.runpod"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass
except Exception:
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main cleanup service loop"""
    logger.info("=" * 70)
    logger.info("🧹 Starting Standalone Cleanup Service")
    logger.info("=" * 70)
    
    try:
        from app.services.cleanup_service import cleanup_service
        
        # Run startup cleanup first
        logger.info("🧹 Running startup cleanup...")
        await cleanup_service.cleanup_on_startup()
        
        # Start periodic cleanup task
        cleanup_service.start_periodic_cleanup()
        logger.info("✅ Periodic cleanup started")
        
        # Keep service running
        logger.info("🔄 Cleanup service is running...")
        logger.info("💡 Press Ctrl+C to stop")
        
        # Wait indefinitely (until interrupted)
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, stopping cleanup service...")
            cleanup_service.stop_periodic_cleanup()
            logger.info("✅ Cleanup service stopped")
            
    except Exception as e:
        logger.error(f"❌ Error in cleanup service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Cleanup service interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


