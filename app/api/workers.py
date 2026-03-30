"""
Workers API Endpoints
สำหรับดู status ของ RQ workers และ restart workers ที่ hung
"""

import os
import logging
import signal
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workers", tags=["Workers"])


def _get_redis_conn():
    from redis import Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return Redis.from_url(redis_url, decode_responses=False)


@router.get("/status")
async def get_workers_status() -> Dict:
    """
    📊 **Worker Status**

    แสดงรายการ RQ workers ทั้งหมด พร้อม current job และ state

    **Returns:**
    - `workers`: รายการ worker พร้อม state, current_job, pid
    - `total`: จำนวน worker ทั้งหมด
    - `busy`: จำนวน worker ที่กำลังทำงาน
    - `idle`: จำนวน worker ที่ว่าง
    """
    try:
        from rq import Worker
        conn = _get_redis_conn()
        all_workers = Worker.all(connection=conn)

        workers_list = []
        for w in all_workers:
            current_job = w.get_current_job()
            current_task_id = None
            current_task_source = None

            if current_job:
                # ดึง task_id จาก job args (arg[0] = task_id ใน process_transcription_job)
                try:
                    args = current_job.args or []
                    if args:
                        a0 = args[0]
                        current_task_id = a0.decode("utf-8") if isinstance(a0, bytes) else str(a0)
                except Exception:
                    pass

                # ดึง source จาก task storage
                if current_task_id:
                    try:
                        storage_type = os.getenv("STORAGE_TYPE", "sqlite").lower()
                        if storage_type == "sqlite":
                            from app.utils.storage_factory import get_storage
                            storage = get_storage()
                        else:
                            from app.utils.storage_factory import get_storage
                            storage = get_storage()
                        task_data = storage.load_transcription(current_task_id)
                        if task_data:
                            current_task_source = task_data.get("source")
                    except Exception:
                        pass

            workers_list.append({
                "name": w.name,
                "state": w.get_state(),
                "queues": [q.name for q in w.queues],
                "current_job_id": current_job.id if current_job else None,
                "current_task_id": current_task_id,
                "current_task_source": current_task_source,
                "started_at": w.birth_date.isoformat() if w.birth_date else None,
                "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None,
                "pid": w.pid,
                "successful_job_count": w.successful_job_count,
                "failed_job_count": w.failed_job_count,
                "total_working_time": round(w.total_working_time, 2),
            })

        busy = sum(1 for w in workers_list if w["state"] == "busy")
        idle = sum(1 for w in workers_list if w["state"] == "idle")

        return {
            "workers": workers_list,
            "total": len(workers_list),
            "busy": busy,
            "idle": idle,
        }

    except Exception as e:
        logger.error(f"Error getting worker status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class RestartRequest(BaseModel):
    worker_name: Optional[str] = None  # None = restart ทั้งหมด
    signal_name: str = "SIGTERM"       # SIGTERM = graceful, SIGKILL = force


@router.post("/restart")
async def restart_workers(request: RestartRequest = RestartRequest()) -> Dict:
    """
    🔄 **Restart Worker(s)**

    ส่ง signal ไปยัง worker process เพื่อ restart

    **Parameters:**
    - `worker_name`: ชื่อ worker ที่ต้องการ restart (ถ้าไม่ระบุ = ทั้งหมด)
    - `signal_name`: SIGTERM (graceful shutdown) หรือ SIGKILL (force kill)

    **Note:** Workers จะ restart โดย process manager (เช่น supervisord/systemd)
    หลังจากได้รับ signal
    """
    try:
        sig_map = {"SIGTERM": signal.SIGTERM, "SIGKILL": signal.SIGKILL, "SIGUSR1": signal.SIGUSR1}
        sig = sig_map.get(request.signal_name.upper())
        if sig is None:
            raise HTTPException(status_code=400, detail=f"Unknown signal: {request.signal_name}. Use SIGTERM or SIGKILL")

        from rq import Worker
        conn = _get_redis_conn()
        all_workers = Worker.all(connection=conn)

        if request.worker_name:
            targets = [w for w in all_workers if w.name == request.worker_name]
            if not targets:
                raise HTTPException(status_code=404, detail=f"Worker not found: {request.worker_name}")
        else:
            targets = all_workers

        results = []
        for w in targets:
            pid = w.pid
            if pid:
                try:
                    os.kill(pid, sig)
                    results.append({"worker": w.name, "pid": pid, "signal": request.signal_name, "success": True})
                    logger.info(f"✅ Sent {request.signal_name} to worker {w.name} (pid={pid})")
                except ProcessLookupError:
                    results.append({"worker": w.name, "pid": pid, "signal": request.signal_name, "success": False, "error": "Process not found"})
                except Exception as e:
                    results.append({"worker": w.name, "pid": pid, "signal": request.signal_name, "success": False, "error": str(e)})
            else:
                results.append({"worker": w.name, "pid": None, "signal": request.signal_name, "success": False, "error": "No PID available"})

        return {
            "signalled": sum(1 for r in results if r["success"]),
            "total": len(results),
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting workers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
