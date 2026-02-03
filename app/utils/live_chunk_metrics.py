"""
เก็บ metrics ของ Live Caption chunks (เวลาแปลง, รับจาก ws-event ที่ Main API)
ใช้สำหรับ endpoint GET /api/transcription/realtime/chunk-metrics?meeting_id=...
"""

from typing import Dict, List, Any
from datetime import datetime, timezone

# meeting_id -> list of chunk metrics (ล่าสุด 50 รายการ)
_live_chunk_metrics: Dict[str, List[Dict[str, Any]]] = {}
_MAX_PER_MEETING = 50


def append_metrics(meeting_id: str, data: Dict[str, Any]) -> None:
    """เก็บ metrics ของ chunk ที่ส่งกลับแล้ว (เรียกจาก internal ws-event)."""
    if not meeting_id:
        return
    data["received_at"] = datetime.now(timezone.utc).isoformat()
    if meeting_id not in _live_chunk_metrics:
        _live_chunk_metrics[meeting_id] = []
    _live_chunk_metrics[meeting_id].append(data)
    if len(_live_chunk_metrics[meeting_id]) > _MAX_PER_MEETING:
        _live_chunk_metrics[meeting_id] = _live_chunk_metrics[meeting_id][-_MAX_PER_MEETING:]


def get_metrics(meeting_id: str = None) -> Dict[str, Any]:
    """
    ดึง metrics สำหรับ meeting_id หรือทั้งหมด
    Returns: { "meeting_id": "...", "chunks": [...], "total_chunks": N, "summary": {...} }
    """
    if meeting_id:
        chunks = list(_live_chunk_metrics.get(meeting_id, []))
        chunks.sort(key=lambda x: (x.get("chunk_index", 0), x.get("received_at", "")))
        durations = [c.get("transcribe_duration_seconds") for c in chunks if c.get("transcribe_duration_seconds") is not None]
        summary = {}
        if durations:
            summary["transcribe_duration_avg_seconds"] = round(sum(durations) / len(durations), 3)
            summary["transcribe_duration_min_seconds"] = round(min(durations), 3)
            summary["transcribe_duration_max_seconds"] = round(max(durations), 3)
        return {
            "status": "success",
            "meeting_id": meeting_id,
            "total_chunks": len(chunks),
            "chunks": chunks,
            "summary": summary,
        }
    # all meetings
    all_chunks = []
    for mid, items in _live_chunk_metrics.items():
        for c in items:
            c = dict(c)
            c["meeting_id"] = mid
            all_chunks.append(c)
    all_chunks.sort(key=lambda x: x.get("received_at", ""), reverse=True)
    return {
        "status": "success",
        "total_chunks": len(all_chunks),
        "meetings": list(_live_chunk_metrics.keys()),
        "chunks": all_chunks[:100],
    }
