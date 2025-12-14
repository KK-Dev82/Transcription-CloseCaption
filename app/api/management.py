"""
Management API Endpoints สำหรับการจัดการ Remote Server
แทนที่การใช้ SSH โดยตรง - ใช้ HTTP API แทน
"""

import logging
import subprocess
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/management", tags=["Management"])


class ExecuteCommandRequest(BaseModel):
    """Request สำหรับ execute command"""
    command: str = Field(..., description="Command to execute")
    timeout: Optional[int] = Field(30, description="Timeout in seconds")
    working_dir: Optional[str] = Field(None, description="Working directory")
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")


class ExecuteCommandResponse(BaseModel):
    """Response สำหรับ execute command"""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float


class SystemInfoResponse(BaseModel):
    """System information response"""
    hostname: str
    platform: str
    python_version: str
    disk_usage: Dict[str, Any]
    memory_usage: Dict[str, Any]
    cpu_info: Dict[str, Any]
    gpu_info: Optional[List[Dict[str, Any]]] = None


class LogRequest(BaseModel):
    """Request สำหรับ get logs"""
    log_file: Optional[str] = Field(None, description="Log file path (relative to logs/)")
    lines: int = Field(100, description="Number of lines to retrieve")
    follow: bool = Field(False, description="Follow log file (stream)")


@router.post("/execute", response_model=ExecuteCommandResponse)
async def execute_command(request: ExecuteCommandRequest):
    """
    Execute command on the server (แทนที่ SSH)
    
    ⚠️ Security: ควรจำกัด commands ที่อนุญาตให้ execute ได้
    """
    import time
    start_time = time.time()
    
    try:
        # Security: จำกัด commands ที่อนุญาต (whitelist)
        # TODO: เพิ่ม whitelist ของ commands ที่อนุญาต
        allowed_commands = [
            "nvidia-smi",
            "df", "du",
            "free", "top",
            "ps", "pgrep",
            "git", "git pull",
            "python", "python3",
            "bash", "sh",
        ]
        
        # ตรวจสอบว่า command อยู่ใน whitelist หรือไม่
        command_base = request.command.split()[0] if request.command else ""
        if not any(request.command.startswith(cmd) for cmd in allowed_commands):
            logger.warning(f"⚠️ Blocked command execution: {request.command}")
            raise HTTPException(
                status_code=403,
                detail=f"Command not allowed: {command_base}"
            )
        
        # Prepare environment
        env = os.environ.copy()
        if request.environment:
            env.update(request.environment)
        
        # Prepare working directory
        cwd = request.working_dir if request.working_dir else None
        
        # Execute command
        process = subprocess.Popen(
            request.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=request.timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            stderr = f"Command timeout after {request.timeout}s\n{stderr}"
        
        execution_time = time.time() - start_time
        
        logger.info(f"✅ Executed command: {request.command[:50]}... (exit_code={exit_code}, time={execution_time:.2f}s)")
        
        return ExecuteCommandResponse(
            success=exit_code == 0,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            execution_time=execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error executing command: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing command: {str(e)}"
        )


@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info():
    """Get system information (CPU, Memory, Disk, GPU)"""
    try:
        import platform
        import psutil
        import shutil
        
        # Hostname
        hostname = platform.node()
        
        # Platform
        platform_info = f"{platform.system()} {platform.release()}"
        
        # Python version
        python_version = platform.python_version()
        
        # Disk usage
        disk = shutil.disk_usage("/")
        disk_usage = {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": round((disk.used / disk.total) * 100, 2)
        }
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent_used": memory.percent
        }
        
        # CPU info
        cpu_info = {
            "count": psutil.cpu_count(logical=False),  # Physical cores
            "logical_count": psutil.cpu_count(logical=True),  # Logical cores
            "percent": psutil.cpu_percent(interval=1),
            "freq": {
                "current": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                "min": psutil.cpu_freq().min if psutil.cpu_freq() else None,
                "max": psutil.cpu_freq().max if psutil.cpu_freq() else None,
            }
        }
        
        # GPU info (nvidia-smi)
        gpu_info = None
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                gpu_info = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 7:
                            gpu_info.append({
                                "index": int(parts[0]),
                                "name": parts[1],
                                "memory_total_mb": int(parts[2]),
                                "memory_used_mb": int(parts[3]),
                                "memory_free_mb": int(parts[4]),
                                "utilization_percent": int(parts[5]),
                                "temperature_c": int(parts[6])
                            })
        except Exception as gpu_error:
            logger.debug(f"Could not get GPU info: {gpu_error}")
            gpu_info = None
        
        return SystemInfoResponse(
            hostname=hostname,
            platform=platform_info,
            python_version=python_version,
            disk_usage=disk_usage,
            memory_usage=memory_usage,
            cpu_info=cpu_info,
            gpu_info=gpu_info
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting system info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting system info: {str(e)}"
        )


@router.get("/logs")
async def get_logs(
    log_file: Optional[str] = Query(None, description="Log file name (relative to logs/)"),
    lines: int = Query(100, description="Number of lines to retrieve"),
    tail: bool = Query(True, description="Get tail of file")
):
    """Get log file contents"""
    try:
        logs_dir = Path("logs")
        if not logs_dir.exists():
            raise HTTPException(status_code=404, detail="Logs directory not found")
        
        # Default log file
        if not log_file:
            # Try to find the most recent log file
            log_files = list(logs_dir.glob("*.log"))
            if not log_files:
                raise HTTPException(status_code=404, detail="No log files found")
            log_file = max(log_files, key=lambda p: p.stat().st_mtime).name
        
        log_path = logs_dir / log_file
        if not log_path.exists():
            raise HTTPException(status_code=404, detail=f"Log file not found: {log_file}")
        
        # Read log file
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # Get last N lines if tail=True
        if tail and len(all_lines) > lines:
            log_lines = all_lines[-lines:]
        else:
            log_lines = all_lines[:lines]
        
        return {
            "log_file": log_file,
            "total_lines": len(all_lines),
            "returned_lines": len(log_lines),
            "lines": log_lines,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting logs: {str(e)}"
        )


@router.get("/scripts")
async def list_scripts():
    """List available management scripts"""
    try:
        scripts_dir = Path("scripts/pod")
        if not scripts_dir.exists():
            return {"scripts": [], "message": "Scripts directory not found"}
        
        scripts = []
        for script_file in scripts_dir.glob("*.sh"):
            stat = script_file.stat()
            scripts.append({
                "name": script_file.name,
                "path": str(script_file.relative_to(Path.cwd())),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "executable": os.access(script_file, os.X_OK)
            })
        
        return {
            "scripts": sorted(scripts, key=lambda x: x["name"]),
            "count": len(scripts)
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing scripts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing scripts: {str(e)}"
        )


@router.post("/scripts/{script_name}/execute")
async def execute_script(
    script_name: str,
    args: Optional[List[str]] = Body(None, description="Script arguments")
):
    """Execute a management script"""
    try:
        scripts_dir = Path("scripts/pod")
        script_path = scripts_dir / script_name
        
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Script not found: {script_name}")
        
        if not script_path.suffix == ".sh":
            raise HTTPException(status_code=400, detail="Only .sh scripts are allowed")
        
        # Security: ตรวจสอบว่า script อยู่ใน scripts/pod directory
        if not str(script_path.resolve()).startswith(str(scripts_dir.resolve())):
            raise HTTPException(status_code=403, detail="Script path not allowed")
        
        # Prepare command
        cmd = ["bash", str(script_path)]
        if args:
            cmd.extend(args)
        
        # Execute script
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(scripts_dir.parent.parent)  # Project root
        )
        
        # Don't wait - return immediately (scripts may take time)
        return {
            "success": True,
            "message": f"Script {script_name} execution started",
            "process_id": process.pid,
            "script": script_name,
            "args": args or []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error executing script: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing script: {str(e)}"
        )

