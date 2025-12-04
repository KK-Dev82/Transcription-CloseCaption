"""
Control API Endpoints สำหรับการควบคุม Service
"""

import logging
import subprocess
import os
import signal
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/control", tags=["Control"])

# เก็บ process ของ test ที่กำลังรัน
_running_test_process: Optional[subprocess.Popen] = None
_test_lock = asyncio.Lock()


class ServiceStatusResponse(BaseModel):
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class TestRequest(BaseModel):
    video_file: str
    num_concurrent: int = 5
    api_url: Optional[str] = None
    model_size: str = "medium"
    language: str = "th"


class TestStatusResponse(BaseModel):
    is_running: bool
    pid: Optional[int] = None
    video_file: Optional[str] = None
    num_concurrent: Optional[int] = None


@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """ตรวจสอบสถานะของ Service"""
    try:
        api_running = False
        worker_running = False
        
        # ตรวจสอบ API Service
        api_pid = None
        if os.getenv('ENVIRONMENT') == 'runpod':
            # บน RunPod ตรวจสอบผ่าน process
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "uvicorn.*app.main:app.*8010"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    api_pid = int(result.stdout.strip().split('\n')[0])
                    api_running = True
            except Exception:
                pass
        else:
            # บน local ตรวจสอบผ่าน health check
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8010/health', timeout=2) as resp:
                        if resp.status == 200:
                            api_running = True
            except Exception:
                pass
        
        # ตรวจสอบ Video Worker
        try:
            result = subprocess.run(
                ["pgrep", "-f", "python.*video_worker"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                worker_pid = int(result.stdout.strip().split('\n')[0])
                worker_running = True
        except Exception:
            pass
        
        if api_running and worker_running:
            return ServiceStatusResponse(
                status="running",
                message="Service is running",
                details={
                    "api_running": api_running,
                    "worker_running": worker_running,
                    "api_pid": api_pid
                }
            )
        else:
            return ServiceStatusResponse(
                status="partial",
                message="Some services are not running",
                details={
                    "api_running": api_running,
                    "worker_running": worker_running
                }
            )
            
    except Exception as e:
        logger.error(f"Error checking service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart", response_model=ServiceStatusResponse)
async def restart_service():
    """Restart Service"""
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "pod" / "restart-service-daemon.sh"
        
        if not script_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Restart script not found"
            )
        
        # Run restart script in background
        process = subprocess.Popen(
            ["bash", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(script_path.parent.parent.parent)
        )
        
        # Don't wait for completion - return immediately
        return ServiceStatusResponse(
            status="restarting",
            message="Service restart initiated",
            details={
                "script": str(script_path),
                "process_id": process.pid
            }
        )
        
    except Exception as e:
        logger.error(f"Error restarting service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=ServiceStatusResponse)
async def start_service():
    """Start Service"""
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "pod" / "start-service-daemon.sh"
        
        if not script_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Start script not found"
            )
        
        # Check if already running
        status = await get_service_status()
        if status.status == "running":
            return ServiceStatusResponse(
                status="already_running",
                message="Service is already running",
                details=status.details
            )
        
        # Run start script in background
        process = subprocess.Popen(
            ["bash", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(script_path.parent.parent.parent)
        )
        
        return ServiceStatusResponse(
            status="starting",
            message="Service start initiated",
            details={
                "script": str(script_path),
                "process_id": process.pid
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos")
async def list_video_files():
    """ดึงรายการไฟล์วิดีโอใน uploads directory"""
    try:
        from ..services.file_service import FileService
        file_service = FileService()
        
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return {"videos": []}
        
        videos = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                if file_service.is_video_file(str(file_path)):
                    stat = file_path.stat()
                    videos.append({
                        "filename": file_path.name,
                        "file_path": f"uploads/{file_path.name}",
                        "file_size": stat.st_size,
                        "file_type": file_path.suffix.lower(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # เรียงตามวันที่แก้ไขล่าสุด
        videos.sort(key=lambda x: x["modified_at"], reverse=True)
        
        return {"videos": videos, "total": len(videos)}
        
    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=Dict[str, Any])
async def start_test(request: TestRequest):
    """เริ่มการทดสอบ Concurrency และ return task IDs ทันที"""
    try:
        project_root = Path(__file__).parent.parent.parent
        
        # ตรวจสอบว่าไฟล์ video มีอยู่หรือไม่
        video_path = Path(request.video_file)
        if not video_path.is_absolute():
            # ถ้าเป็น relative path ให้หาจาก uploads
            video_path = project_root / "uploads" / request.video_file
        
        if not video_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video file not found: {video_path}"
            )
        
        # ใช้ video_file name เท่านั้น
        video_file_name = Path(request.video_file).name
        file_path_str = str(video_path)
        
        # Import transcription service เพื่อเรียก transcription โดยตรง
        from ..services.transcription_service import TranscriptionService
        transcription_service = TranscriptionService()
        
        # เรียก transcription API โดยตรงเพื่อดึง task IDs
        task_ids = []
        
        async def create_task(index: int):
            try:
                task_id = await transcription_service.start_transcription(
                    file_path=file_path_str,
                    file_name=video_file_name,
                    language=request.language,
                    model_size=request.model_size,
                    use_chunking=False
                )
                return task_id
            except Exception as e:
                logger.error(f"Error creating task {index}: {e}")
                return None
        
        # ส่ง requests พร้อมกัน (จำกัด concurrent requests)
        semaphore = asyncio.Semaphore(min(request.num_concurrent, 10))  # จำกัด concurrent API calls
        
        async def create_task_with_semaphore(index: int):
            async with semaphore:
                return await create_task(index)
        
        tasks = [create_task_with_semaphore(i) for i in range(request.num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # เก็บ task IDs ที่สำเร็จ
        for result in results:
            if isinstance(result, str) and result:
                task_ids.append(result)
        
        logger.info(f"✅ Created {len(task_ids)} transcription tasks out of {request.num_concurrent} requests")
        
        if len(task_ids) == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to create any transcription tasks"
            )
        
        return {
            "status": "started",
            "message": f"Test started - {len(task_ids)} tasks created",
            "video_file": video_file_name,
            "num_concurrent": request.num_concurrent,
            "task_ids": task_ids,
            "requested": request.num_concurrent,
            "created": len(task_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-test", response_model=Dict[str, Any])
async def stop_test():
    """หยุดการทดสอบที่กำลังรัน"""
    global _running_test_process
    
    async with _test_lock:
        if _running_test_process is None:
            raise HTTPException(
                status_code=404,
                detail="No test is currently running"
            )
        
        try:
            # ตรวจสอบว่า process ยังทำงานอยู่หรือไม่
            if _running_test_process.poll() is None:
                # Process ยังทำงานอยู่ - ส่ง SIGTERM
                _running_test_process.terminate()
                
                # รอให้ process หยุด (max 5 วินาที)
                try:
                    _running_test_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # ถ้ายังไม่หยุด ให้ force kill
                    _running_test_process.kill()
                    _running_test_process.wait()
                
                pid = _running_test_process.pid
                _running_test_process = None
                
                return {
                    "status": "stopped",
                    "message": "Test stopped successfully",
                    "pid": pid
                }
            else:
                # Process เสร็จแล้ว
                pid = _running_test_process.pid
                _running_test_process = None
                
                return {
                    "status": "already_stopped",
                    "message": "Test was already completed",
                    "pid": pid
                }
                
        except Exception as e:
            logger.error(f"Error stopping test: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/status", response_model=TestStatusResponse)
async def get_test_status():
    """ตรวจสอบสถานะของ Test"""
    global _running_test_process
    
    async with _test_lock:
        if _running_test_process is None:
            return TestStatusResponse(
                is_running=False,
                pid=None,
                video_file=None,
                num_concurrent=None
            )
        
        # ตรวจสอบว่า process ยังทำงานอยู่หรือไม่
        if _running_test_process.poll() is None:
            # ยังทำงานอยู่
            return TestStatusResponse(
                is_running=True,
                pid=_running_test_process.pid,
                video_file=None,  # TODO: เก็บข้อมูลไว้
                num_concurrent=None  # TODO: เก็บข้อมูลไว้
            )
        else:
            # เสร็จแล้ว
            _running_test_process = None
            return TestStatusResponse(
                is_running=False,
                pid=None,
                video_file=None,
                num_concurrent=None
            )

