from celery import Celery

import sys
from pathlib import Path

# Add app directory to path for imports (must be before importing config!)
sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings

celery_app = Celery(
    "legal_diff_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

