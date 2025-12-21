"""
RTMP Stream Service สำหรับ Dashboard
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
    
    from app.services.rtmp import RTMPStreamService
    
    if RTMPStreamService:
        logger.info("✅ Imported RTMPStreamService from app.services.rtmp")
    else:
        logger.warning("RTMPStreamService is not available (optional feature)")
        RTMPStreamService = None
except ImportError as e:
    logger.warning(f"Could not import RTMPStreamService from app.services.rtmp: {e}")
    RTMPStreamService = None

# Export service instance
if RTMPStreamService:
    rtmp_stream_service = RTMPStreamService()
else:
    rtmp_stream_service = None

