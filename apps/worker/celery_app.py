"""Celery application configuration."""

from celery import Celery
import os

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
