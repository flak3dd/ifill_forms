"""
Celery application for background job processing.
"""
from celery import Celery
from .config import settings

celery_app = Celery(
    "formforge",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["backend.job_manager"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
)

