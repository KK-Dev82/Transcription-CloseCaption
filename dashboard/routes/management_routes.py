"""
Management API routes - Proxy to remote server Management API
ใช้สำหรับจัดการ remote server ผ่าน API แทน SSH
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Support both relative and absolute imports
try:
    from ..server_constants import SERVERS
except ImportError:
    try:
        from ..config import SERVERS
    except ImportError:
        import sys
        from pathlib import Path
        dashboard_dir = Path(__file__).parent.parent
        if str(dashboard_dir) not in sys.path:
            sys.path.insert(0, str(dashboard_dir))
        try:
            from server_constants import SERVERS
        except ImportError:
            from config import SERVERS

logger = logging.getLogger(__name__)
router = APIRouter()


class ExecuteCommandRequest(BaseModel):
    command: str
    timeout: Optional[int] = 30


@router.post("/api/server/{server_name}/management/execute")
async def execute_command(server_name: str, request: ExecuteCommandRequest):
    """Execute command on remote server via Management API"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "command": request.command,
                "timeout": request.timeout or 30
            }
            
            async with session.post(
                f"{api_url}/api/management/execute",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=request.timeout + 10 if request.timeout else 40)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Management API returned {response.status}: {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Management API error: {error_text[:200]}"
                    )
    except aiohttp.ClientError as e:
        logger.error(f"Error calling management API on {server_name}: {e}")
        raise HTTPException(status_code=503, detail=f"Connection error: {str(e)}")
    except Exception as e:
        logger.error(f"Error executing command on {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/server/{server_name}/management/system-info")
async def get_system_info(server_name: str):
    """Get system info (CPU, RAM, Disk, GPU) from remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/api/management/system-info",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"System info API returned {response.status}: {error_text}")
                    return {"error": f"API returned {response.status}: {error_text[:200]}"}
    except aiohttp.ClientError as e:
        logger.error(f"Error getting system info from {server_name}: {e}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error getting system info from {server_name}: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/api/server/{server_name}/management/logs")
async def get_logs(server_name: str, log_type: str = "service", lines: int = 100):
    """Get logs from remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            params = {"log_type": log_type, "lines": lines}
            async with session.get(
                f"{api_url}/api/management/logs",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Logs API returned {response.status}: {error_text}")
                    return {"error": f"API returned {response.status}: {error_text[:200]}"}
    except aiohttp.ClientError as e:
        logger.error(f"Error getting logs from {server_name}: {e}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error getting logs from {server_name}: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/api/server/{server_name}/management/scripts")
async def list_scripts(server_name: str):
    """List available management scripts on remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{api_url}/api/management/scripts",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Scripts API returned {response.status}: {error_text}")
                    return {"error": f"API returned {response.status}: {error_text[:200]}"}
    except aiohttp.ClientError as e:
        logger.error(f"Error listing scripts from {server_name}: {e}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error listing scripts from {server_name}: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/api/server/{server_name}/management/scripts/{script_name}/execute")
async def execute_script(server_name: str, script_name: str):
    """Execute a management script on remote server"""
    if server_name not in SERVERS:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found")
    
    server_config = SERVERS[server_name]
    api_url = server_config["api_url"]
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/api/management/scripts/{script_name}/execute",
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Script execution API returned {response.status}: {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Script execution error: {error_text[:200]}"
                    )
    except aiohttp.ClientError as e:
        logger.error(f"Error executing script on {server_name}: {e}")
        raise HTTPException(status_code=503, detail=f"Connection error: {str(e)}")
    except Exception as e:
        logger.error(f"Error executing script on {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

