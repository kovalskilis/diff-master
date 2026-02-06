import sys
import os
from pathlib import Path

# Explicitly load .env file BEFORE any imports
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[2] / ".env"

# Debug: read and print .env content
print(f"[Celery] .env path: {env_path}")
print(f"[Celery] .env exists: {env_path.exists()}")
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
        print(f"[Celery] .env content preview:")
        for line in content.split('\n')[:10]:
            if 'KEY' in line or 'DEEPSEEK' in line:
                print(f"  {line[:50]}...")

load_dotenv(env_path, override=True)
print(f"[Celery] DEEPSEEK_API_KEY from env: {os.getenv('DEEPSEEK_API_KEY', 'NOT FOUND')[:20]}...")

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

