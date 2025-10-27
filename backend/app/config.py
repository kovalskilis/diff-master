from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
import os
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Legal Diff"
    APP_VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str
    
    # Redis & Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # LLM
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"  # or gpt-4-turbo-preview for OpenAI
    
    # Email
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@example.com"
    SMTP_FROM_NAME: str = "Legal Diff"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        # Try multiple possible locations for .env file
        env_file = [
            Path(__file__).parent.parent / ".env",  # backend/.env
            Path(__file__).parent.parent.parent / ".env",  # project root/.env
            ".env"  # current directory
        ]
        case_sensitive = True


settings = Settings()

