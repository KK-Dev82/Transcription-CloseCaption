"""
SQLite Admin Routes
สำหรับ serve phpLiteAdmin ผ่าน FastAPI
"""

import os
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.responses import StreamingResponse
import subprocess

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sqlite-admin", tags=["sqlite-admin"])

# Path to sqlite_admin directory
DASHBOARD_DIR = Path(__file__).parent.parent
SQLITE_ADMIN_DIR = DASHBOARD_DIR / "sqlite_admin"
PHPLITEADMIN_FILE = SQLITE_ADMIN_DIR / "phpliteadmin.php"
CONFIG_FILE = SQLITE_ADMIN_DIR / "config.php"


@router.get("/")
async def sqlite_admin_index():
    """Redirect to phpliteadmin.php"""
    if not PHPLITEADMIN_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="SQLite Admin not installed. Run: bash scripts/pod/install-sqlite-admin.sh"
        )
    
    return HTMLResponse(content='<script>window.location.href="/sqlite-admin/phpliteadmin.php";</script>')


@router.get("/phpliteadmin.php")
async def phpliteadmin(request: Request):
    """
    Serve phpLiteAdmin through PHP
    หรือ proxy ไปที่ remote server ถ้า Dashboard อยู่ที่ local
    """
    # ตรวจสอบว่า Dashboard อยู่ที่ local หรือ server
    # ถ้า PHPLITEADMIN_FILE ไม่มี ให้ proxy ไปที่ remote server
    if not PHPLITEADMIN_FILE.exists() or PHPLITEADMIN_FILE.stat().st_size == 0:
        # Proxy ไปที่ remote server (ใช้ server แรกใน SERVERS)
        try:
            from ..server_constants import SERVERS
            if SERVERS:
                # ใช้ server แรก
                first_server = list(SERVERS.keys())[0]
                server_config = SERVERS[first_server]
                api_url = server_config["api_url"]
                
                # แปลง api_url เป็น dashboard URL (เปลี่ยน port)
                # เช่น http://213.173.108.6:13264 -> http://213.173.108.6:8020
                import re
                dashboard_url = re.sub(r':\d+$', ':8020', api_url)
                
                # Proxy request
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    proxy_url = f"{dashboard_url}/sqlite-admin/phpliteadmin.php"
                    if request.url.query:
                        proxy_url += f"?{request.url.query}"
                    
                    async with session.get(proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            content = await response.text()
                            return HTMLResponse(content=content)
                        else:
                            raise HTTPException(
                                status_code=404,
                                detail=f"SQLite Admin not available on remote server. Run: bash scripts/pod/install-sqlite-admin.sh on server"
                            )
        except Exception as e:
            logger.error(f"Error proxying SQLite Admin: {e}", exc_info=True)
            raise HTTPException(
                status_code=404,
                detail="SQLite Admin not installed. Run: bash scripts/pod/install-sqlite-admin.sh"
            )
    
    # Check if PHP is available
    try:
        php_version = subprocess.check_output(["php", "--version"], stderr=subprocess.STDOUT).decode()
        logger.debug(f"PHP available: {php_version.split()[0]}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise HTTPException(
            status_code=500,
            detail="PHP is not installed. Install with: sudo apt-get install php php-cli php-sqlite3"
        )
    
    # Execute PHP file
    try:
        # Change to sqlite_admin directory
        os.chdir(str(SQLITE_ADMIN_DIR))
        
        # Execute PHP with phpliteadmin.php
        result = subprocess.run(
            ["php", "-f", str(PHPLITEADMIN_FILE)],
            capture_output=True,
            text=True,
            cwd=str(SQLITE_ADMIN_DIR),
            env=dict(os.environ, REQUEST_METHOD="GET", QUERY_STRING=request.url.query or "")
        )
        
        if result.returncode != 0:
            logger.error(f"PHP execution error: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"PHP execution error: {result.stderr[:200]}"
            )
        
        # Return HTML response
        return HTMLResponse(content=result.stdout)
        
    except Exception as e:
        logger.error(f"Error executing phpLiteAdmin: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing phpLiteAdmin: {str(e)}"
        )


@router.get("/config.php")
async def get_config():
    """Get configuration file (read-only)"""
    if not CONFIG_FILE.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    
    return FileResponse(
        path=str(CONFIG_FILE),
        media_type="text/plain",
        filename="config.php"
    )


@router.get("/status")
async def admin_status():
    """Check SQLite Admin installation status"""
    status = {
        "installed": PHPLITEADMIN_FILE.exists(),
        "php_available": False,
        "config_exists": CONFIG_FILE.exists(),
        "admin_dir": str(SQLITE_ADMIN_DIR),
        "database_path": None
    }
    
    # Check PHP
    try:
        subprocess.check_output(["php", "--version"], stderr=subprocess.STDOUT)
        status["php_available"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Get database path from config if exists
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                # Extract directory from config
                import re
                match = re.search(r"\$directory\s*=\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    db_dir = match.group(1)
                    status["database_path"] = f"{db_dir}/database.db"
        except Exception as e:
            logger.debug(f"Error reading config: {e}")
    
    return status

