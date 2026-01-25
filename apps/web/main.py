"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from pathlib import Path
from dotenv import load_dotenv

from packages.database.connection import init_database, create_tables
from packages.common.redis_cache import init_redis_cache
from packages.common.logging import setup_logging, get_logger

# Load environment variables from the project root
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Setup logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# Initialize Redis BEFORE importing API modules
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_db = int(os.getenv("REDIS_DB", "0"))
redis_password = os.getenv("REDIS_PASSWORD")

try:
    init_redis_cache(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password
    )
    logger.info("Redis cache initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Redis cache: {e}")

# Now safe to import API modules
from apps.web.api import resume
from apps.web.api import preferences
from apps.web.api import jobs
from apps.web.api import scoring
from apps.web.api import decision
from apps.web.api import artifacts
from apps.web.api import apply
from apps.web.api import outcomes
from apps.web.api import user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting application...")
    
    # Initialize database
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        init_database(database_url, echo=os.getenv("DEBUG", "false").lower() == "true")
        logger.info("Database initialized")
    
    # Initialize Redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    redis_password = os.getenv("REDIS_PASSWORD")
    
    init_redis_cache(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password
    )
    logger.info("Redis cache initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="JobForge AI",
    description="Intelligent job application agent",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(resume.router, prefix="/api/v1")
app.include_router(preferences.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(scoring.router, prefix="/api/v1")
app.include_router(decision.router, prefix="/api/v1")
app.include_router(artifacts.router, prefix="/api/v1")
app.include_router(apply.router, prefix="/api/v1")
app.include_router(outcomes.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "JobForge AI API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Check database connection
        "redis": "connected"  # TODO: Check Redis connection
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
