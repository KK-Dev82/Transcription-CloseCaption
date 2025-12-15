"""
Transcription Service Dashboard
Mini project สำหรับ monitor และ control transcription service
"""
import os
import sys
import logging
from pathlib import Path

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
        # management_routes might not exist yet
        from routes import server_routes, batch_routes, cleanup_routes
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

app.include_router(server_routes.router)
app.include_router(batch_routes.router)
app.include_router(cleanup_routes.router)
if management_routes:
    app.include_router(management_routes.router)

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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main dashboard page"""
    # Support both relative (package) and absolute (direct run) imports
    try:
        from .server_constants import SERVERS
    except ImportError:
        # If relative import fails, try absolute import
        try:
            from server_constants import SERVERS
        except ImportError:
            from config import SERVERS
    
    # Inject server configs to frontend
    server_configs_js = "window.SERVER_CONFIGS = " + str({
        k: {"name": v["name"], "api_url": v["api_url"]}
        for k, v in SERVERS.items()
    }).replace("'", '"') + ";"
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "server_configs_js": server_configs_js
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "8020"))
    uvicorn.run(app, host="0.0.0.0", port=port)
