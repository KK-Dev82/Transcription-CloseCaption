"""
Chunk Group Validator
ตรวจสอบ file_paths ก่อนเริ่ม job
"""
import os
from pathlib import Path
from typing import List, Tuple

from fastapi import HTTPException

from app.services.video_service import VideoService


def validate_chunk_group_request(
    file_paths: List[str],
    max_duration_seconds: int = None,
    max_files: int = None,
    min_files: int = 2
) -> Tuple[List[str], List[float]]:
    """
    Validate file_paths สำหรับ chunk group

    Returns:
        (validated_paths, durations) — paths ที่ผ่าน validation และ duration ของแต่ละไฟล์

    Raises:
        HTTPException 400/404: ถ้า validation ไม่ผ่าน
    """
    max_duration = max_duration_seconds or int(os.getenv("CHUNK_GROUP_MAX_DURATION_SECONDS", "2100"))
    max_files_limit = max_files or int(os.getenv("CHUNK_GROUP_MAX_FILES", "20"))

    if len(file_paths) < min_files:
        raise HTTPException(
            status_code=400,
            detail=f"chunk_group ต้องมีอย่างน้อย {min_files} ไฟล์ (ได้รับ {len(file_paths)} ไฟล์)"
        )
    if len(file_paths) > max_files_limit:
        raise HTTPException(
            status_code=400,
            detail=f"chunk_group จำกัดไม่เกิน {max_files_limit} ไฟล์ (ได้รับ {len(file_paths)} ไฟล์)"
        )

    video_service = VideoService()
    durations = []

    for fp in file_paths:
        path = Path(fp)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {fp}")

        info = video_service.get_video_info(fp)
        duration = info.get("duration", 0)
        durations.append(duration)

        if duration > max_duration:
            raise HTTPException(
                status_code=400,
                detail=f"ไฟล์ {fp} ยาว {duration/60:.1f} นาที เกินขีดจำกัด {max_duration/60:.0f} นาที"
            )

    return file_paths, durations
