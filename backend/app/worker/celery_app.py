import sys
import os
from pathlib import Path

# Only load .env file if NOT running inside Docker (DISABLE_DOTENV != 1)
if os.getenv("DISABLE_DOTENV") != "1":
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    print(f"[Celery] Loading .env from: {env_path}")
    if env_path.exists():
        load_dotenv(env_path, override=True)
else:
    print("[Celery] DISABLE_DOTENV=1, using Docker environment variables")

from celery import Celery

# Add app directory to path for imports (must be before importing config!)
sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings
print(f"[Celery] DEEPSEEK_API_KEY from settings: {'set' if settings.DEEPSEEK_API_KEY else 'not set'}")

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

