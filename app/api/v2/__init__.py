"""
API v2 - Unified and Consolidated Endpoints
รวม API endpoints ที่ซ้ำซ้อนเข้าด้วยกัน

Changes:
- Unified task status endpoints (tasks, progress, polling)
- Unified task list endpoints (history, tasks, polling)
- Better filtering with query parameters
"""

from .unified_tasks import router as unified_tasks_router

__all__ = ["unified_tasks_router"]





