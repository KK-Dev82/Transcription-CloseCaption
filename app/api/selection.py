"""
Selection API - Endpoints สำหรับ Frontend ใช้งานกับ selection จาก /api/video/list
รองรับ ids หรือ file_paths จากรายการที่เลือก
"""
import io
import zipfile
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..utils.storage_factory import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload/selection", tags=["selection"])


class SelectionRequest(BaseModel):
    """Request สำหรับ selection จาก video list"""
    ids: Optional[List[int]] = None
    file_paths: Optional[List[str]] = None

    def get_file_paths(self) -> List[str]:
        """Resolve selection เป็น list ของ file_path"""
        if self.file_paths:
            return list(self.file_paths)
        if self.ids:
            return _resolve_ids_to_paths(self.ids)
        return []


def _resolve_ids_to_paths(ids: List[int]) -> List[str]:
    """Resolve database ids เป็น file_paths จาก video list"""
    storage = get_storage()
    if not hasattr(storage, "list_uploaded_files"):
        raise HTTPException(
            status_code=400,
            detail="ไม่รองรับการ resolve ids (storage ไม่มี list_uploaded_files)"
        )
    all_files = storage.list_uploaded_files(limit=5000, order_by="created_at", order_desc=True)
    id_set = set(ids)
    paths = []
    for f in all_files:
        fid = f.get("id")
        if fid is not None and fid in id_set:
            fp = f.get("file_path")
            if fp and Path(fp).exists():
                paths.append(fp)
    return paths


def _validate_selection(
    ids: Optional[List[int]], file_paths: Optional[List[str]]
) -> tuple[List[str], List[dict]]:
    """
    Validate และ resolve selection เป็น (file_paths, items_with_metadata)
    """
    if not ids and not file_paths:
        raise HTTPException(status_code=400, detail="ต้องระบุ ids หรือ file_paths อย่างใดอย่างหนึ่ง")
    if ids and file_paths:
        raise HTTPException(status_code=400, detail="ระบุได้แค่ ids หรือ file_paths อย่างใดอย่างหนึ่ง")

    uploads_resolved = Path("uploads").resolve()
    items = []

    if file_paths:
        for fp in file_paths:
            path = Path(fp)
            if not path.is_absolute():
                path = (Path.cwd() / path).resolve()
            try:
                path.relative_to(uploads_resolved)
            except ValueError:
                raise HTTPException(status_code=403, detail=f"Invalid path: {fp}")
            if not path.exists() or not path.is_file():
                raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์: {fp}")
            items.append({"file_path": str(path), "filename": path.name})
        return [item["file_path"] for item in items], items

    # ids
    storage = get_storage()
    if not hasattr(storage, "list_uploaded_files"):
        raise HTTPException(status_code=400, detail="ไม่รองรับ ids (ใช้ file_paths แทน)")
    all_files = storage.list_uploaded_files(limit=5000, order_by="created_at", order_desc=True)
    id_set = set(ids)
    paths = []
    for f in all_files:
        fid = f.get("id")
        if fid is not None and fid in id_set:
            fp = f.get("file_path")
            if fp and Path(fp).exists():
                paths.append(fp)
                items.append({
                    "id": fid,
                    "file_path": fp,
                    "filename": f.get("filename") or Path(fp).name,
                    "file_type": f.get("file_type", "video"),
                    "file_size": f.get("file_size"),
                    "duration": f.get("duration"),
                })
    if len(paths) != len(ids):
        found = set(f.get("id") for f in all_files if f.get("id") in id_set)
        missing = id_set - found
        logger.warning(f"Some ids not found: {missing}")
    return paths, items


def _get_file_info(file_path: str) -> dict:
    """ดึงข้อมูลไฟล์พื้นฐาน"""
    from ..services.file_service import FileService
    fs = FileService()
    path = Path(file_path)
    if not path.exists():
        return {"file_path": file_path, "filename": path.name, "error": "ไม่พบไฟล์"}
    info = fs.get_file_info(file_path)
    return {
        "file_path": file_path,
        "filename": path.name,
        "file_size": info.get("file_size"),
        "file_type": info.get("file_type"),
        "duration": info.get("duration"),
        "is_video": fs.is_video_file(file_path),
        "is_audio": fs.is_audio_file(file_path),
    }


class SelectionInfoRequest(BaseModel):
    ids: Optional[List[int]] = None
    file_paths: Optional[List[str]] = None


@router.post("/info")
async def selection_info(req: SelectionInfoRequest):
    """
    ดึงข้อมูลไฟล์ที่เลือกจาก video list

    Body: { "ids": [1, 2, 3] } หรือ { "file_paths": ["uploads/xxx.mp4", ...] }
    """
    if req.ids is None and req.file_paths is None:
        raise HTTPException(status_code=400, detail="ต้องระบุ ids หรือ file_paths")
    try:
        paths, items = _validate_selection(req.ids, req.file_paths)
        if not paths:
            return {"items": [], "total": 0, "message": "ไม่พบไฟล์ที่ตรงกับ selection"}
        # Enrich with file_service info
        from ..services.file_service import FileService
        fs = FileService()
        for item in items:
            fp = item.get("file_path")
            if fp and Path(fp).exists():
                info = fs.get_file_info(fp)
                item.update({
                    "file_size": item.get("file_size") or info.get("file_size"),
                    "duration": item.get("duration") or info.get("duration"),
                    "file_type": item.get("file_type") or info.get("file_type"),
                    "is_video": fs.is_video_file(fp),
                    "is_audio": fs.is_audio_file(fp),
                })
        return {"items": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Selection info error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class SelectionDownloadRequest(BaseModel):
    ids: Optional[List[int]] = None
    file_paths: Optional[List[str]] = None


@router.post("/download")
async def selection_download(req: SelectionDownloadRequest):
    """
    ดาวน์โหลดไฟล์ที่เลือกเป็น ZIP

    Body: { "ids": [1, 2, 3] } หรือ { "file_paths": ["uploads/xxx.mp4", ...] }
    """
    if req.ids is None and req.file_paths is None:
        raise HTTPException(status_code=400, detail="ต้องระบุ ids หรือ file_paths")
    try:
        paths, items = _validate_selection(req.ids, req.file_paths)
        if not paths:
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์ที่ตรงกับ selection")

        # สร้าง ZIP ใน memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                fp = item.get("file_path")
                name = item.get("filename") or Path(fp).name
                path = Path(fp)
                if path.exists() and path.is_file():
                    zf.write(fp, arcname=name)

        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=selection.zip"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Selection download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class SelectionTranscribeRequest(BaseModel):
    ids: Optional[List[int]] = None
    file_paths: Optional[List[str]] = None
    language: str = "th"
    model_size: Optional[str] = None
    use_chunking: bool = False


@router.post("/transcribe")
async def selection_transcribe(req: SelectionTranscribeRequest):
    """
    ส่งไฟล์ที่เลือกไป transcription

    Body: {
      "ids": [1, 2, 3] หรือ "file_paths": ["uploads/xxx.mp4", ...],
      "language": "th",
      "model_size": "base",
      "use_chunking": false
    }
    """
    if req.ids is None and req.file_paths is None:
        raise HTTPException(status_code=400, detail="ต้องระบุ ids หรือ file_paths")
    try:
        paths, items = _validate_selection(req.ids, req.file_paths)
        if not paths:
            raise HTTPException(status_code=404, detail="ไม่พบไฟล์ที่ตรงกับ selection")

        from app.api.transcribe import TranscriptionRequest, start_transcription

        task_ids = []
        for fp in paths:
            tr_req = TranscriptionRequest(
                file_path=fp,
                language=req.language,
                model_size=req.model_size or "base",
                use_chunking=req.use_chunking,
            )
            result = await start_transcription(tr_req)
            task_ids.append(result["task_id"])

        return {
            "task_ids": task_ids,
            "total": len(task_ids),
            "message": f"ส่ง {len(task_ids)} ไฟล์ไป transcription แล้ว",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Selection transcribe error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
