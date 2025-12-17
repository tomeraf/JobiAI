from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, templates, selectors, logs, auth, hebrew_names
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="JobiAI",
    description="LinkedIn Job Application Bot API",
    version="1.0.0",
    redirect_slashes=False,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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


@app.get("/")
async def root():
    return {"message": "JobiAI API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    logger.info("JobiAI API starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("JobiAI API shutting down...")
