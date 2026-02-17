"""
Lightweight Monitoring Proxy - Forward to Main API (8010)
ใช้สำหรับ Dashboard เบา (port 8020) สำหรับตรวจสอบ Resource เท่านั้น
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

import os

try:
    from ..server_constants import INTERNAL_API_URL, USE_INTERNAL_PORT, SERVERS, DEFAULT_SERVER
except ImportError:
    from server_constants import INTERNAL_API_URL, USE_INTERNAL_PORT, SERVERS, DEFAULT_SERVER

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor", tags=["monitor"])

def _get_main_api_url(server_name: str = None) -> str:
    """
    Main API URL สำหรับ proxy
    ลำดับความสำคัญ: MAIN_API_URL > USE_INTERNAL_PORT (localhost) > SERVERS config
    """
    # 1) กำหนดเอง - ใช้ได้เมื่อ RunPod proxy URL เปลี่ยนทุกครั้ง (เช่น u2ighk0n70zzv4-8010.proxy.runpod.net)
    main_url = os.getenv("MAIN_API_URL", "").strip().rstrip("/")
    if main_url:
        return main_url
    # 2) Localhost - เมื่อ Dashboard และ Main API อยู่ pod เดียวกัน
    if USE_INTERNAL_PORT:
        return INTERNAL_API_URL
    # 3) จาก config (อาจเป็น URL เก่าถ้า restart pod แล้ว)
    server_name = server_name or DEFAULT_SERVER
    if server_name in SERVERS:
        return SERVERS[server_name]["api_url"].rstrip("/")
    return INTERNAL_API_URL


async def _fetch_json(url: str, params: dict = None, timeout: int = 10):
    """Fetch JSON using aiohttp (no extra deps)"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            return await r.json()


@router.get("/health")
async def proxy_health(server: str = None):
    """Health check from Main API"""
    try:
        url = f"{_get_main_api_url(server)}/health"
        return await _fetch_json(url, timeout=3)
    except Exception as e:
        logger.warning(f"Health proxy error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@router.get("/system")
async def proxy_system(server: str = None):
    """CPU, RAM, GPU from Main API /api/monitoring/system"""
    try:
        url = f"{_get_main_api_url(server)}/api/monitoring/system"
        return await _fetch_json(url, timeout=5)
    except Exception as e:
        logger.warning(f"System proxy error: {e}")
        raise HTTPException(503, detail=str(e))


@router.get("/stats")
async def proxy_stats(server: str = None):
    """Redis + Queues + System from Main API /api/monitoring/"""
    try:
        url = f"{_get_main_api_url(server)}/api/monitoring/"
        return await _fetch_json(url, timeout=10)
    except Exception as e:
        logger.warning(f"Stats proxy error: {e}")
        raise HTTPException(503, detail=str(e))


@router.get("/logs")
async def proxy_logs_list(server: str = None):
    """List available logs from Main API"""
    try:
        url = f"{_get_main_api_url(server)}/api/logs/"
        return await _fetch_json(url, timeout=4)
    except Exception as e:
        logger.warning(f"Logs list proxy error: {e}")
        raise HTTPException(503, detail=str(e))


@router.get("/logs/{log_name}")
async def proxy_log_content(log_name: str, lines: int = 100, tail: bool = True, server: str = None):
    """Get log content from Main API"""
    try:
        url = f"{_get_main_api_url(server)}/api/logs/{log_name}"
        params = {"lines": lines, "tail": str(tail).lower()}
        return await _fetch_json(url, params=params, timeout=8)
    except Exception as e:
        logger.warning(f"Log proxy error: {e}")
        raise HTTPException(503, detail=str(e))
