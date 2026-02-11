"""
FE Live Caption (CC) temp storage: เก็บไฟล์ชั่วคราวสำหรับ streaming audio transcription
ย้ายจาก project root ไป storage/cc_temp เพื่อป้องกัน storage เต็ม
"""

import os
import time
from pathlib import Path


def get_cc_temp_dir() -> Path:
    """คืน path ของ storage/cc_temp (สำหรับ temp files ของ FE CC)"""
    base = os.getenv("FE_CC_TEMP_DIR", "storage/cc_temp")
    return Path(base).resolve()


def ensure_cc_temp_dir() -> Path:
    """สร้าง storage/cc_temp ถ้ายังไม่มี"""
    d = get_cc_temp_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def cleanup_cc_temp(max_age_hours: float = 1.0) -> dict:
    """
    ลบไฟล์ processed_tmp_*.wav และ typhoon_proc_*.wav ที่เก่ากว่า max_age_hours
    คืน dict: {"deleted": int, "bytes_freed": int, "errors": int}
    """
    temp_dir = get_cc_temp_dir()
    project_root = Path.cwd()
    deleted = 0
    bytes_freed = 0
    errors = 0
    cutoff = time.time() - (max_age_hours * 3600)

    dirs_to_scan = [temp_dir]
    # ตรวจสอบ project root ด้วย (เผื่อ legacy typhoon_asr สร้างไฟล์ไว้)
    if project_root != temp_dir:
        dirs_to_scan.append(project_root)

    # processed_tmp*.wav (stem จาก /tmp/tmpXXX → processed_tmpXXX)
    patterns = ("processed_tmp*.wav", "typhoon_proc_*.wav")

    for scan_dir in dirs_to_scan:
        if not scan_dir.exists():
            continue
        for pattern in patterns:
            for f in scan_dir.glob(pattern):
                try:
                    stat = f.stat()
                    if stat.st_mtime < cutoff:
                        sz = stat.st_size
                        f.unlink()
                        deleted += 1
                        bytes_freed += sz
                except Exception:
                    errors += 1

    return {"deleted": deleted, "bytes_freed": bytes_freed, "errors": errors}
