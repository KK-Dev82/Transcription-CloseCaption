"""
Batch Service - Manages batch transcription tasks
"""
from typing import Dict

# Store batch tasks in memory (in production, use Redis or database)
# Values are dict representations of BatchTaskStatus
batch_tasks_store: Dict[str, dict] = {}
