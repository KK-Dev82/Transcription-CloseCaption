"""
FFmpeg Burn-in Service สำหรับ Dashboard
Import จาก app/services/rtmp/ (optional)
"""

import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import from app/services/rtmp (optional)
try:
    # Add parent directory to path
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from app.services.rtmp import FFmpegBurninService
    
    if FFmpegBurninService:
        logger.info("✅ Imported FFmpegBurninService from app.services.rtmp")
    else:
        logger.warning("FFmpegBurninService is not available (optional feature)")
        FFmpegBurninService = None
except ImportError as e:
    logger.warning(f"Could not import FFmpegBurninService from app.services.rtmp: {e}")
    FFmpegBurninService = None

# Export service instance
if FFmpegBurninService:
    ffmpeg_burnin_service = FFmpegBurninService()
else:
    ffmpeg_burnin_service = None

