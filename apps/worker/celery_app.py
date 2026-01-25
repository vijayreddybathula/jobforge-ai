"""Celery application configuration."""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Redis cache BEFORE importing tasks
from packages.common.redis_cache import init_redis_cache

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
except Exception as e:
    print(f"Warning: Failed to initialize Redis cache: {e}")

# Get Redis URL from environment
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

# Create Celery app
celery_app = Celery(
    "jobforge_worker",
    broker=broker_url,
    backend=result_backend,
    include=[
        "apps.worker.tasks.job_ingestion",
        "apps.worker.tasks.jd_parsing",
        "apps.worker.tasks.scoring"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
)
