"""
HTTP Health Check Server สำหรับ Video Worker

เปิด HTTP port เพื่อให้ Main API ยิง health check ไปหา worker
ทำให้ RunPod เห็น inbound activity → ไม่ idle → ไม่ถูก SIGTERM
"""
import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional

logger = logging.getLogger(__name__)

# สร้าง FastAPI app สำหรับ health check
health_app = FastAPI(
    title="Video Worker Health Check",
    description="Health check endpoint สำหรับ Video Worker",
    version="1.0.0"
)

# Global state สำหรับ worker status
worker_status = {
    "running": False,
    "rabbitmq_connected": False,
    "consumers_registered": False,
    "active_tasks": 0,
    "uptime_seconds": 0
}

@health_app.get("/health")
async def health_check():
    """
    Health check endpoint สำหรับ Video Worker
    
    Returns:
        dict: สถานะสุขภาพของ worker
    """
    return {
        "status": "healthy" if worker_status["running"] else "stopped",
        "service": "video-worker",
        "rabbitmq_connected": worker_status["rabbitmq_connected"],
        "consumers_registered": worker_status["consumers_registered"],
        "active_tasks": worker_status["active_tasks"],
        "uptime_seconds": worker_status["uptime_seconds"],
        "timestamp": asyncio.get_event_loop().time()
    }

@health_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "video-worker-health-check",
        "status": "running",
        "endpoints": {
            "/health": "Health check endpoint"
        }
    }

def update_worker_status(
    running: Optional[bool] = None,
    rabbitmq_connected: Optional[bool] = None,
    consumers_registered: Optional[bool] = None,
    active_tasks: Optional[int] = None,
    uptime_seconds: Optional[float] = None
):
    """Update worker status สำหรับ health check"""
    if running is not None:
        worker_status["running"] = running
    if rabbitmq_connected is not None:
        worker_status["rabbitmq_connected"] = rabbitmq_connected
    if consumers_registered is not None:
        worker_status["consumers_registered"] = consumers_registered
    if active_tasks is not None:
        worker_status["active_tasks"] = active_tasks
    if uptime_seconds is not None:
        worker_status["uptime_seconds"] = uptime_seconds

async def start_health_server(port: int = 8030, host: str = "0.0.0.0"):
    """
    Start HTTP health check server
    
    Args:
        port: Port สำหรับ health check server (default: 8030)
        host: Host สำหรับ health check server (default: 0.0.0.0)
    """
    config = uvicorn.Config(
        app=health_app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,  # ปิด access log เพื่อลด noise
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    
    logger.info(f"🚀 Starting health check server on {host}:{port}")
    await server.serve()


