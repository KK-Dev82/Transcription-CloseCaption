"""
Transcription Service Dashboard
Mini project สำหรับ monitor และ control transcription service
"""
import os
import sys
import logging
from pathlib import Path

# โหลด .env.runpod จาก project root (สำหรับ MAIN_API_URL, USE_INTERNAL_PORT)
try:
    from dotenv import load_dotenv
    proj_root = Path(__file__).parent.parent
    for name in (".env.runpod", ".env"):
        env_file = proj_root / name
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Transcription Service Dashboard")

# Templates and static files
templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"
templates_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

# Create empty index.html in static if doesn't exist
if not (static_dir / "index.html").exists():
    (static_dir / "index.html").write_text("")

templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount SQLite Admin (phpLiteAdmin) if exists
sqlite_admin_dir = Path(__file__).parent / "sqlite_admin"
if sqlite_admin_dir.exists() and (sqlite_admin_dir / "phpliteadmin.php").exists():
    app.mount("/sqlite-admin", StaticFiles(directory=str(sqlite_admin_dir)), name="sqlite_admin")
    logger.info(f"✅ SQLite Admin mounted at /sqlite-admin")

# Import and include routers
# Support both relative (package) and absolute (direct run) imports
server_routes = None
batch_routes = None
cleanup_routes = None
management_routes = None

try:
    from .routes import server_routes, batch_routes, cleanup_routes, management_routes
except ImportError:
    # If relative import fails, try absolute import
    import sys
    from pathlib import Path
    dashboard_dir = Path(__file__).parent
    if str(dashboard_dir) not in sys.path:
        sys.path.insert(0, str(dashboard_dir))
    try:
        from routes import server_routes, batch_routes, cleanup_routes, management_routes
    except ImportError:
        # Try importing individually
        try:
            from routes import server_routes
        except ImportError:
            server_routes = None
        try:
            from routes import batch_routes
        except ImportError:
            batch_routes = None
        try:
            from routes import cleanup_routes
        except ImportError:
            cleanup_routes = None
        try:
            from routes import management_routes
        except ImportError:
            management_routes = None

# Try to import sqlite_admin_routes (optional)
try:
    from .routes import sqlite_admin_routes
except ImportError:
    try:
        from routes import sqlite_admin_routes
    except ImportError:
        sqlite_admin_routes = None

# Try to import live_streaming_routes (optional)
try:
    from .routes import live_streaming_routes
except ImportError:
    try:
        from routes import live_streaming_routes
    except ImportError:
        live_streaming_routes = None

# Try to import rtmp_streaming_routes (optional)
try:
    from .routes import rtmp_streaming_routes
except ImportError:
    try:
        from routes import rtmp_streaming_routes
    except ImportError:
        rtmp_streaming_routes = None

# Try to import webhook_routes (optional)
try:
    from .routes import webhook_routes
except ImportError:
    try:
        from routes import webhook_routes
    except ImportError:
        webhook_routes = None

# Monitoring proxy (lightweight - for Resource check only)
try:
    from .routes import monitoring_proxy_routes
except ImportError:
    try:
        from routes import monitoring_proxy_routes
    except ImportError:
        monitoring_proxy_routes = None

if monitoring_proxy_routes:
    app.include_router(monitoring_proxy_routes.router)
    logger.info("✅ Monitoring proxy routes included (lightweight)")

if server_routes:
    app.include_router(server_routes.router)
    logger.info("✅ Server routes included")
if batch_routes:
    app.include_router(batch_routes.router)
    logger.info("✅ Batch routes included")
if cleanup_routes:
    app.include_router(cleanup_routes.router)
    logger.info("✅ Cleanup routes included")
if management_routes:
    app.include_router(management_routes.router)
    logger.info("✅ Management routes included")

# Include Webhook router (for receiving callbacks)
if webhook_routes:
    try:
        app.include_router(webhook_routes.router)
        logger.info("✅ Webhook routes included")
    except Exception as e:
        logger.debug(f"Webhook routes not available: {e}")

# Include SQLite Admin router (if available)
if sqlite_admin_routes:
    try:
        app.include_router(sqlite_admin_routes.router)
        logger.info("✅ SQLite Admin routes included")
    except Exception as e:
        logger.debug(f"SQLite Admin routes not available: {e}")

# Include Live Streaming router (if available)
if live_streaming_routes:
    try:
        app.include_router(live_streaming_routes.router)
        logger.info("✅ Live Streaming routes included")
    except Exception as e:
        logger.debug(f"Live Streaming routes not available: {e}")

# Include RTMP Streaming router (if available)
if rtmp_streaming_routes:
    try:
        app.include_router(rtmp_streaming_routes.router)
        logger.info("✅ RTMP Streaming routes included")
    except Exception as e:
        logger.debug(f"RTMP Streaming routes not available: {e}")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Index - links to Status และ Logs"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Status page - Health, CPU, RAM, GPU"""
    return templates.TemplateResponse("status.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Logs page - CPU, GPU, FE CC, Transcription"""
    return templates.TemplateResponse("logs.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "8020"))
    uvicorn.run(app, host="0.0.0.0", port=port)
