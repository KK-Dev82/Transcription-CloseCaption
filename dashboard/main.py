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

# Import and include routers
# Support both relative (package) and absolute (direct run) imports
try:
    from .routes import server_routes, batch_routes, cleanup_routes
except ImportError:
    # If relative import fails, try absolute import
    import sys
    from pathlib import Path
    dashboard_dir = Path(__file__).parent
    if str(dashboard_dir) not in sys.path:
        sys.path.insert(0, str(dashboard_dir))
    from routes import server_routes, batch_routes, cleanup_routes

app.include_router(server_routes.router)
app.include_router(batch_routes.router)
app.include_router(cleanup_routes.router)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main dashboard page"""
    try:
        from .server_constants import SERVERS
    except ImportError:
        from .config import SERVERS
    
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
