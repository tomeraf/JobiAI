from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import sys

from app.api import jobs, templates, selectors, logs, auth, hebrew_names
from app.utils.logger import get_logger
from app.utils.port_finder import get_dynamic_cors_origins

logger = get_logger(__name__)

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


@app.on_event("startup")
async def startup_event():
    logger.info("JobiAI API starting up...")
    # Initialize database tables (for SQLite on first run)
    from app.database import init_db
    await init_db()
    logger.info("Database initialized")


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
