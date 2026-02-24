"""
Upload Resources Proxy - Forward to Main API
สำหรับหน้า Upload Resources ใน Dashboard
"""
import logging
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from ..server_constants import INTERNAL_API_URL, USE_INTERNAL_PORT, SERVERS, DEFAULT_SERVER
except ImportError:
    from server_constants import INTERNAL_API_URL, USE_INTERNAL_PORT, SERVERS, DEFAULT_SERVER

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload-resources", tags=["upload-resources"])


def _get_main_api_url(server_name: str = None) -> str:
    main_url = os.getenv("MAIN_API_URL", "").strip().rstrip("/")
    if main_url:
        return main_url
    if USE_INTERNAL_PORT:
        return INTERNAL_API_URL
    server_name = server_name or DEFAULT_SERVER
    if server_name in SERVERS:
        return SERVERS[server_name]["api_url"].rstrip("/")
    return INTERNAL_API_URL


@router.get("/list")
async def list_uploaded_files(server: str = None):
    """Proxy ไปยัง Main API /api/video/list (ใช้ database)"""
    try:
        import aiohttp
        base_url = _get_main_api_url(server)
        url = f"{base_url}/api/video/list"
        params = {"use_database": "true"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    text = await r.text()
                    raise HTTPException(status_code=r.status, detail=text or "API Error")
                data = await r.json()
                # รวม videos และ audios เป็น list เดียว
                files = (data.get("videos") or []) + (data.get("audios") or [])
                return {
                    "files": files,
                    "total": data.get("total", len(files)),
                    "source": data.get("source", "unknown"),
                    "main_api_url": base_url,
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Upload resources list proxy error: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/preview")
async def preview_file(file_path: str = Query(..., description="Path ไปยังไฟล์ เช่น uploads/xxx.mp4"), server: str = None):
    """Proxy stream ไฟล์สำหรับ preview จาก Main API"""
    import aiohttp
    base_url = _get_main_api_url(server)
    url = f"{base_url}/api/upload/preview"
    params = {"file_path": file_path}
    filename = file_path.split("/")[-1] if "/" in file_path else file_path
    suffix = ("." + filename.split(".")[-1]) if "." in filename else ""
    media_types = {
        ".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
        ".ogg": "audio/ogg", ".flac": "audio/flac",
    }
    content_type = media_types.get(suffix.lower(), "application/octet-stream")

    async def generate():
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=120)) as r:
                if r.status != 200:
                    raise HTTPException(status_code=r.status, detail="Preview failed")
                async for chunk in r.content.iter_chunked(8192):
                    yield chunk

    try:
        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Preview proxy error: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/download")
async def download_file(file_path: str = Query(..., description="Path ไปยังไฟล์"), server: str = None):
    """Proxy ดาวน์โหลดไฟล์จาก Main API (Content-Disposition: attachment)"""
    import aiohttp
    base_url = _get_main_api_url(server)
    url = f"{base_url}/api/upload/download"
    params = {"file_path": file_path}
    filename = file_path.split("/")[-1] if "/" in file_path else file_path
    suffix = ("." + filename.split(".")[-1]) if "." in filename else ""
    media_types = {
        ".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska",
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
        ".ogg": "audio/ogg", ".flac": "audio/flac",
    }
    content_type = media_types.get(suffix.lower(), "application/octet-stream")

    async def generate():
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=300)) as r:
                if r.status != 200:
                    raise HTTPException(status_code=r.status, detail="Download failed")
                async for chunk in r.content.iter_chunked(8192):
                    yield chunk

    try:
        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Download proxy error: {e}")
        raise HTTPException(status_code=503, detail=str(e))


# --- Selection API (proxy to Main API /api/upload/selection/*) ---

class SelectionRequest(BaseModel):
    ids: Optional[List[int]] = None
    file_paths: Optional[List[str]] = None


class SelectionTranscribeRequest(SelectionRequest):
    language: str = "th"
    model_size: Optional[str] = None
    use_chunking: bool = False


async def _proxy_selection_post(server: str, path: str, body: dict):
    """Proxy POST request ไปยัง Main API selection endpoints"""
    import aiohttp
    base_url = _get_main_api_url(server)
    url = f"{base_url}/api/upload/selection/{path}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                text = await r.text()
                raise HTTPException(status_code=r.status, detail=text or "API Error")
            return await r.json()


async def _proxy_selection_download(server: str, body: dict):
    """Proxy POST download (returns ZIP stream)"""
    import aiohttp
    base_url = _get_main_api_url(server)
    url = f"{base_url}/api/upload/selection/download"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=300)) as r:
            if r.status != 200:
                text = await r.text()
                raise HTTPException(status_code=r.status, detail=text or "Download failed")
            content = await r.read()

    async def generate():
        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    return StreamingResponse(
        generate(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=selection.zip"},
    )


@router.post("/selection/info")
async def selection_info(req: SelectionRequest, server: str = None):
    """Proxy ดึงข้อมูลไฟล์ที่เลือก"""
    body = {"ids": req.ids, "file_paths": req.file_paths}
    return await _proxy_selection_post(server, "info", body)


@router.post("/selection/download")
async def selection_download(req: SelectionRequest, server: str = None):
    """Proxy ดาวน์โหลดไฟล์ที่เลือกเป็น ZIP"""
    body = {"ids": req.ids, "file_paths": req.file_paths}
    return await _proxy_selection_download(server, body)


@router.post("/selection/transcribe")
async def selection_transcribe(req: SelectionTranscribeRequest, server: str = None):
    """Proxy ส่งไฟล์ที่เลือกไป transcription"""
    body = {
        "ids": req.ids,
        "file_paths": req.file_paths,
        "language": req.language,
        "model_size": req.model_size,
        "use_chunking": req.use_chunking,
    }
    return await _proxy_selection_post(server, "transcribe", body)
