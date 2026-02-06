from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import sys
import os
import signal
import threading
import time

from app.api import jobs, templates, selectors, logs, auth, hebrew_names
from app.utils.logger import get_logger
from app.utils.port_finder import get_dynamic_cors_origins

logger = get_logger(__name__)

# Heartbeat tracking for auto-shutdown
_last_heartbeat = time.time()
_heartbeat_timeout = 30  # seconds - shutdown if no heartbeat for this long
_heartbeat_enabled = False  # Only enable after first heartbeat received

# Determine frontend path based on execution mode
if getattr(sys, 'frozen', False):
    # Running as compiled executable (PyInstaller)
    _APP_DIR = Path(sys._MEIPASS)
    FRONTEND_PATH = _APP_DIR / 'frontend' / 'dist'
else:
    # Development mode
    FRONTEND_PATH = Path(__file__).parent.parent.parent / 'frontend' / 'dist'

app = FastAPI(
    title="JobiAI",
    description="LinkedIn Job Application Bot API",
    version="1.0.0",
    redirect_slashes=False,
)

# CORS middleware for frontend - dynamically configured
cors_origins = get_dynamic_cors_origins()
logger.info(f"CORS enabled for origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(selectors.router, prefix="/api/selectors", tags=["Selectors"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(hebrew_names.router, prefix="/api/hebrew-names", tags=["Hebrew Names"])


@app.get("/api")
async def api_root():
    """API root endpoint - use /api for API status check."""
    return {"message": "JobiAI API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/heartbeat")
async def heartbeat():
    """Frontend sends this periodically to indicate it's still open."""
    global _last_heartbeat, _heartbeat_enabled
    _last_heartbeat = time.time()
    _heartbeat_enabled = True
    return {"status": "ok"}


@app.post("/api/shutdown")
async def shutdown():
    """
    Shutdown the server. Called when frontend tab is closed.
    Kills both backend (self) and frontend (node) processes.
    """
    logger.info("Shutdown requested - closing JobiAI...")

    def do_shutdown():
        time.sleep(0.5)  # Give time for response to be sent

        # Kill frontend (node/vite on port 5173)
        if sys.platform == 'win32':
            os.system('taskkill /F /IM node.exe >nul 2>&1')
        else:
            os.system('pkill -f "vite"')

        # Kill self
        os._exit(0)

    threading.Thread(target=do_shutdown, daemon=True).start()
    return {"status": "shutting_down"}


def _heartbeat_checker():
    """Background thread that checks for heartbeat timeout."""
    global _last_heartbeat, _heartbeat_enabled
    while True:
        time.sleep(10)  # Check every 10 seconds
        if _heartbeat_enabled:
            elapsed = time.time() - _last_heartbeat
            if elapsed > _heartbeat_timeout:
                logger.info(f"No heartbeat for {elapsed:.0f}s - auto-shutdown triggered")
                # Kill frontend first
                if sys.platform == 'win32':
                    os.system('taskkill /F /IM node.exe >nul 2>&1')
                else:
                    os.system('pkill -f "vite"')
                os._exit(0)


@app.on_event("startup")
async def startup_event():
    logger.info("JobiAI API starting up...")
    # Initialize database tables (for SQLite on first run)
    from app.database import init_db
    await init_db()
    logger.info("Database initialized")

    # Start heartbeat checker thread (for auto-shutdown when browser closes)
    heartbeat_thread = threading.Thread(target=_heartbeat_checker, daemon=True)
    heartbeat_thread.start()
    logger.info("Heartbeat checker started (auto-shutdown enabled)")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("JobiAI API shutting down...")


# --- Static Frontend Serving (for desktop app mode) ---
# Mount frontend static files if the dist folder exists
# This allows running without a separate frontend server

if FRONTEND_PATH.exists():
    logger.info(f"Serving frontend from: {FRONTEND_PATH}")

    # Mount static assets (JS, CSS, images)
    assets_path = FRONTEND_PATH / 'assets'
    if assets_path.exists():
        app.mount('/assets', StaticFiles(directory=str(assets_path)), name='assets')

    # Serve other static files (favicon, etc.)
    @app.get('/favicon.ico')
    async def favicon():
        favicon_path = FRONTEND_PATH / 'favicon.ico'
        if favicon_path.exists():
            return FileResponse(str(favicon_path))
        return FileResponse(str(FRONTEND_PATH / 'index.html'))

    @app.get('/vite.svg')
    async def vite_svg():
        svg_path = FRONTEND_PATH / 'vite.svg'
        if svg_path.exists():
            return FileResponse(str(svg_path))
        return {"error": "not found"}

    # Root route serves frontend index.html
    @app.get('/')
    async def serve_root():
        return FileResponse(str(FRONTEND_PATH / 'index.html'))

    # Catch-all route for SPA - must be last!
    # This handles client-side routing (React Router)
    @app.get('/{path:path}')
    async def serve_frontend(path: str):
        # Skip API routes (they're handled by routers above)
        if path.startswith('api/'):
            return {"error": "not found"}

        # Try to serve the exact file if it exists
        file_path = FRONTEND_PATH / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

        # For all other routes, serve index.html (SPA routing)
        return FileResponse(str(FRONTEND_PATH / 'index.html'))
else:
    logger.info(f"Frontend not found at {FRONTEND_PATH} - API-only mode")

    # Only serve API root when no frontend
    @app.get('/')
    async def root_no_frontend():
        return {"message": "JobiAI API", "status": "running", "note": "Frontend not available"}
