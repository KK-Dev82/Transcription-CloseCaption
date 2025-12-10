"""
Cleanup Service - Manages cleanup progress tracking
"""
from typing import Dict, Any

# Store cleanup progress in memory
# In production, consider using Redis or database
cleanup_progress_store: Dict[str, Dict[str, Any]] = {}

