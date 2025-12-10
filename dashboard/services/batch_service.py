"""
Batch Service - Manages batch transcription tasks
"""
import logging
from typing import Dict, List
import asyncio

logger = logging.getLogger(__name__)

# Import SERVERS config
try:
    from ..config import SERVERS
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import SERVERS

# Store batch tasks in memory (in production, use Redis or database)
# Values are dict representations of BatchTaskStatus
batch_tasks_store: Dict[str, dict] = {}
