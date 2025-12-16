"""
Server Constants Configuration
สำหรับปรับเปลี่ยน IP และ Port ของ GPU Pod Container ได้ง่าย

⚠️ เมื่อ Port เปลี่ยน (เช่น restart container) ให้แก้ไขค่าที่นี่ได้เลย
"""
import os
from typing import Dict

# ============================================
# Internal Port Configuration (สำหรับ Dashboard ที่ทำงานบน Pod เดียวกัน)
# ============================================
# ถ้า Dashboard ทำงานบน Pod เดียวกันกับ Transcription Service
# สามารถใช้ internal port (localhost:8010) แทน external port
USE_INTERNAL_PORT = os.getenv("USE_INTERNAL_PORT", "false").lower() == "true"
INTERNAL_API_PORT = int(os.getenv("INTERNAL_API_PORT", "8010"))
INTERNAL_API_URL = f"http://localhost:{INTERNAL_API_PORT}"

# ============================================
# GPU Pod Server Configurations
# ============================================

# 4000-ada (Original)
# Note: Port 40133 is SSH port (-> :22), HTTP API port is 40134 (-> :8010)
SERVER_4000ADA_HOST = os.getenv("SERVER_4000ADA_HOST", "87.197.119.40")
SERVER_4000ADA_PORT = os.getenv("SERVER_4000ADA_PORT", "40134")
SERVER_4000ADA_API_URL = f"http://{SERVER_4000ADA_HOST}:{SERVER_4000ADA_PORT}"
SERVER_4000ADA_SSH = os.getenv("SERVER_4000ADA_SSH", "4000-ada")

# 4000-ada-sc (Secure - ใช้แทนเมื่อ 4000-ada GPU เต็ม)
# Note: 
#   - SSH: TCP Expose (port เปลี่ยนทุกครั้งหลัง restart)
#   - HTTP API: Priority 1) Internal Port (localhost:8010) -> 2) HTTP Expose (domain) -> 3) TCP Expose (IP:Port)
#   - ถ้า USE_INTERNAL_PORT=true: ใช้ http://localhost:8010 (เร็วที่สุด)
#   - ถ้าใช้ HTTP Expose: https://n2l8ke53h14aaw-8010.proxy.runpod.net (มี domain name, ไม่เปลี่ยน port)
#   - ถ้าใช้ TCP Expose: http://213.173.108.6:15599 (port เปลี่ยนทุกครั้งหลัง restart)
SERVER_4000ADA_SC_HOST = os.getenv("SERVER_4000ADA_SC_HOST", "213.173.108.6")
SERVER_4000ADA_SC_HTTP_EXPOSE = os.getenv("SERVER_4000ADA_SC_HTTP_EXPOSE", "https://n2l8ke53h14aaw-8010.proxy.runpod.net")
SERVER_4000ADA_SC_TCP_PORT = os.getenv("SERVER_4000ADA_SC_TCP_PORT", "15599")  # TCP Expose port (เปลี่ยนทุกครั้งหลัง restart)
SERVER_4000ADA_SC_USE_HTTP_EXPOSE = os.getenv("SERVER_4000ADA_SC_USE_HTTP_EXPOSE", "true").lower() == "true"

# Priority: Internal Port > HTTP Expose > TCP Expose
if USE_INTERNAL_PORT:
    # ใช้ internal port (เร็วที่สุด, ไม่ต้องผ่าน network)
    SERVER_4000ADA_SC_API_URL = INTERNAL_API_URL
    SERVER_4000ADA_SC_PORT = str(INTERNAL_API_PORT)
elif SERVER_4000ADA_SC_USE_HTTP_EXPOSE and SERVER_4000ADA_SC_HTTP_EXPOSE:
    # ใช้ HTTP Expose (มี domain name, ไม่เปลี่ยน port หลัง restart)
    SERVER_4000ADA_SC_API_URL = SERVER_4000ADA_SC_HTTP_EXPOSE
    SERVER_4000ADA_SC_PORT = "8010"  # Internal port (ไม่ใช่ external port)
else:
    # Fallback: ใช้ TCP Expose (port เปลี่ยนทุกครั้งหลัง restart)
    SERVER_4000ADA_SC_API_URL = f"http://{SERVER_4000ADA_SC_HOST}:{SERVER_4000ADA_SC_TCP_PORT}"
    SERVER_4000ADA_SC_PORT = SERVER_4000ADA_SC_TCP_PORT

SERVER_4000ADA_SC_SSH = os.getenv("SERVER_4000ADA_SC_SSH", "4000-ada-sc")

# 5080
SERVER_5080_HOST = os.getenv("SERVER_5080_HOST", "213.144.200.206")
SERVER_5080_PORT = os.getenv("SERVER_5080_PORT", "15267")
SERVER_5080_API_URL = f"http://{SERVER_5080_HOST}:{SERVER_5080_PORT}"
SERVER_5080_SSH = os.getenv("SERVER_5080_SSH", "5080")

# ============================================
# Server Config Dictionary
# ============================================
# Function to get API URL (ใช้ internal port ถ้า USE_INTERNAL_PORT=true)
def get_api_url(external_url: str, server_name: str = None) -> str:
    """
    Get API URL - ใช้ internal port ถ้า Dashboard ทำงานบน Pod เดียวกัน
    
    Args:
        external_url: External API URL (เช่น http://213.173.108.6:13264)
        server_name: Server name (optional, สำหรับ logging)
    
    Returns:
        API URL (internal หรือ external ตาม USE_INTERNAL_PORT)
    """
    if USE_INTERNAL_PORT:
        logger = logging.getLogger(__name__)
        logger.info(f"Using internal port for {server_name or 'server'}: {INTERNAL_API_URL}")
        return INTERNAL_API_URL
    return external_url

# Import logging for get_api_url
import logging

SERVERS: Dict[str, Dict[str, str]] = {
    "4000-ada": {
        "name": "4000-ada",
        "api_url": get_api_url(SERVER_4000ADA_API_URL, "4000-ada"),
        "host": SERVER_4000ADA_HOST,
        "port": SERVER_4000ADA_PORT,
        "ssh": SERVER_4000ADA_SSH,
        "color": "#0071e3",  # Apple Blue
        "internal_port": INTERNAL_API_PORT,
    },
    "4000-ada-sc": {
        "name": "4000-ada-sc",
        "api_url": get_api_url(SERVER_4000ADA_SC_API_URL, "4000-ada-sc"),
        "host": SERVER_4000ADA_SC_HOST,
        "port": SERVER_4000ADA_SC_PORT,
        "ssh": SERVER_4000ADA_SC_SSH,
        "color": "#5ac8fa",  # Apple Light Blue
        "internal_port": INTERNAL_API_PORT,
    },
    "5080": {
        "name": "5080",
        "api_url": get_api_url(SERVER_5080_API_URL, "5080"),
        "host": SERVER_5080_HOST,
        "port": SERVER_5080_PORT,
        "ssh": SERVER_5080_SSH,
        "color": "#34c759",  # Apple Green
        "internal_port": INTERNAL_API_PORT,
    },
}

# ============================================
# Default Active Server
# ============================================
# เปลี่ยนเป็น "4000-ada-sc" เมื่อ 4000-ada GPU เต็ม
DEFAULT_SERVER = os.getenv("DEFAULT_SERVER", "4000-ada-sc")

# ============================================
# Export for backward compatibility
# ============================================
__all__ = ["SERVERS", "DEFAULT_SERVER", "USE_INTERNAL_PORT", "INTERNAL_API_URL", "get_api_url"]

