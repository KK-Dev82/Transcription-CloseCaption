"""
Server Constants Configuration
สำหรับปรับเปลี่ยน IP และ Port ของ GPU Pod Container ได้ง่าย

⚠️ เมื่อ Port เปลี่ยน (เช่น restart container) ให้แก้ไขค่าที่นี่ได้เลย
"""
import os
from typing import Dict

# ============================================
# GPU Pod Server Configurations
# ============================================

# 4000-ada (Original)
SERVER_4000ADA_HOST = os.getenv("SERVER_4000ADA_HOST", "87.197.119.40")
SERVER_4000ADA_PORT = os.getenv("SERVER_4000ADA_PORT", "40133")
SERVER_4000ADA_API_URL = f"http://{SERVER_4000ADA_HOST}:{SERVER_4000ADA_PORT}"
SERVER_4000ADA_SSH = os.getenv("SERVER_4000ADA_SSH", "4000-ada")

# 4000-ada-sc (Secure - ใช้แทนเมื่อ 4000-ada GPU เต็ม)
SERVER_4000ADA_SC_HOST = os.getenv("SERVER_4000ADA_SC_HOST", "213.173.108.6")
SERVER_4000ADA_SC_PORT = os.getenv("SERVER_4000ADA_SC_PORT", "10889")
SERVER_4000ADA_SC_API_URL = f"http://{SERVER_4000ADA_SC_HOST}:{SERVER_4000ADA_SC_PORT}"
SERVER_4000ADA_SC_SSH = os.getenv("SERVER_4000ADA_SC_SSH", "4000-ada-sc")

# 5080
SERVER_5080_HOST = os.getenv("SERVER_5080_HOST", "213.144.200.206")
SERVER_5080_PORT = os.getenv("SERVER_5080_PORT", "15267")
SERVER_5080_API_URL = f"http://{SERVER_5080_HOST}:{SERVER_5080_PORT}"
SERVER_5080_SSH = os.getenv("SERVER_5080_SSH", "5080")

# ============================================
# Server Config Dictionary
# ============================================
SERVERS: Dict[str, Dict[str, str]] = {
    "4000-ada": {
        "name": "4000-ada",
        "api_url": SERVER_4000ADA_API_URL,
        "host": SERVER_4000ADA_HOST,
        "port": SERVER_4000ADA_PORT,
        "ssh": SERVER_4000ADA_SSH,
        "color": "#0071e3",  # Apple Blue
    },
    "4000-ada-sc": {
        "name": "4000-ada-sc",
        "api_url": SERVER_4000ADA_SC_API_URL,
        "host": SERVER_4000ADA_SC_HOST,
        "port": SERVER_4000ADA_SC_PORT,
        "ssh": SERVER_4000ADA_SC_SSH,
        "color": "#5ac8fa",  # Apple Light Blue
    },
    "5080": {
        "name": "5080",
        "api_url": SERVER_5080_API_URL,
        "host": SERVER_5080_HOST,
        "port": SERVER_5080_PORT,
        "ssh": SERVER_5080_SSH,
        "color": "#34c759",  # Apple Green
    },
}

# ============================================
# Default Active Server
# ============================================
# เปลี่ยนเป็น "4000-ada-sc" เมื่อ 4000-ada GPU เต็ม
DEFAULT_SERVER = os.getenv("DEFAULT_SERVER", "4000-ada")

# ============================================
# Export for backward compatibility
# ============================================
__all__ = ["SERVERS", "DEFAULT_SERVER"]

