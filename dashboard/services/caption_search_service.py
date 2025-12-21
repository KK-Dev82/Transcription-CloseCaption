"""
Caption Search Service สำหรับ Dashboard
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
    
    from app.services.rtmp import CaptionSearchService
    
    if CaptionSearchService:
        logger.info("✅ Imported CaptionSearchService from app.services.rtmp")
    else:
        logger.warning("CaptionSearchService is not available (optional feature)")
        CaptionSearchService = None
except ImportError as e:
    logger.warning(f"Could not import CaptionSearchService from app.services.rtmp: {e}")
    CaptionSearchService = None

# Export service instance
if CaptionSearchService:
    caption_search_service = CaptionSearchService()
else:
    caption_search_service = None

