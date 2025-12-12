"""
Dashboard Configuration
⚠️ DEPRECATED: ใช้ server_constants.py แทน
"""
# Import from server_constants for backward compatibility
# Support both relative (package) and absolute (direct run) imports
try:
    from .server_constants import SERVERS
except ImportError:
    from server_constants import SERVERS

# Keep for backward compatibility
__all__ = ["SERVERS"]

