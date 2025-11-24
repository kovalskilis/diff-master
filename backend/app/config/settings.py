from typing import List
from pathlib import Path
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

ENV_FILES = [
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[1] / ".env",
    ".env",
]

COMMON_MODEL_CONFIG = SettingsConfigDict(
    env_file=[] if os.getenv("DISABLE_DOTENV") == "1" else ENV_FILES,
    case_sensitive=True,
    extra="ignore",
)


class AppSettings(BaseSettings):
    NAME: str = "diff-master"
    VERSION: str = "0.1.0"
    ADDRESS: str = "0.0.0.0"
    PORT: int = 8000
    ROOT_PATH: str = "/api"
    RUN_CREATE_DB_ON_STARTUP: bool = False

    model_config = SettingsConfigDict(env_prefix="APP_", **COMMON_MODEL_CONFIG)


class DatabaseSettings(BaseSettings):
    URL: str

    model_config = SettingsConfigDict(env_prefix="DATABASE_", **COMMON_MODEL_CONFIG)


class CelerySettings(BaseSettings):
    BROKER_URL: str
    RESULT_BACKEND: str

    model_config = SettingsConfigDict(env_prefix="CELERY_", **COMMON_MODEL_CONFIG)


class SecuritySettings(BaseSettings):
    SECRET_KEY: str = Field(validation_alias=AliasChoices("SECURITY_SECRET_KEY", "SECRET_KEY"))
    ALGORITHM: str = Field(default="HS256", validation_alias=AliasChoices("SECURITY_ALGORITHM", "ALGORITHM"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 7,
        validation_alias=AliasChoices("SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"),
    )

    model_config = SettingsConfigDict(env_prefix="SECURITY_", **COMMON_MODEL_CONFIG)


class LLMSettings(BaseSettings):
    OPENAI_API_KEY: str = Field(default="", validation_alias=AliasChoices("LLM_OPENAI_API_KEY", "OPENAI_API_KEY"))
    DEEPSEEK_API_KEY: str = Field(default="", validation_alias=AliasChoices("LLM_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"))
    DEEPSEEK_BASE_URL: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("LLM_DEEPSEEK_BASE_URL", "DEEPSEEK_BASE_URL"),
    )
    LLM_MODEL: str = Field(default="deepseek-chat", validation_alias=AliasChoices("LLM_LLM_MODEL", "LLM_MODEL"))

    model_config = SettingsConfigDict(env_prefix="LLM_", **COMMON_MODEL_CONFIG)


class SMTPSettings(BaseSettings):
    HOST: str = "smtp.example.com"
    PORT: int = 587
    USER: str = ""
    PASSWORD: str = ""
    FROM: str = "noreply@example.com"
    FROM_NAME: str = "Legal Diff"

    model_config = SettingsConfigDict(env_prefix="SMTP_", **COMMON_MODEL_CONFIG)


class CORSSettings(BaseSettings):
    ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "BACKEND_CORS_ORIGINS"),
    )

    @property
    def origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_prefix="CORS_", **COMMON_MODEL_CONFIG)


class Settings(BaseSettings):
    APP: AppSettings = Field(default_factory=AppSettings)
    DATABASE: DatabaseSettings = Field(default_factory=DatabaseSettings)
    CELERY: CelerySettings = Field(default_factory=CelerySettings)
    SECURITY: SecuritySettings = Field(default_factory=SecuritySettings)
    LLM: LLMSettings = Field(default_factory=LLMSettings)
    SMTP: SMTPSettings = Field(default_factory=SMTPSettings)
    CORS: CORSSettings = Field(default_factory=CORSSettings)

    model_config = COMMON_MODEL_CONFIG

    @property
    def APP_NAME(self) -> str:
        return self.APP.NAME

    @property
    def APP_VERSION(self) -> str:
        return self.APP.VERSION

    @property
    def DATABASE_URL(self) -> str:
        return self.DATABASE.URL

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.CELERY.BROKER_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.CELERY.RESULT_BACKEND

    @property
    def SECRET_KEY(self) -> str:
        return self.SECURITY.SECRET_KEY

    @property
    def ALGORITHM(self) -> str:
        return self.SECURITY.ALGORITHM

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.SECURITY.ACCESS_TOKEN_EXPIRE_MINUTES

    @property
    def OPENAI_API_KEY(self) -> str:
        return self.LLM.OPENAI_API_KEY

    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return self.LLM.DEEPSEEK_API_KEY

    @property
    def DEEPSEEK_BASE_URL(self) -> str:
        return self.LLM.DEEPSEEK_BASE_URL

    @property
    def LLM_MODEL(self) -> str:
        return self.LLM.LLM_MODEL

    @property
    def SMTP_HOST(self) -> str:
        return self.SMTP.HOST

    @property
    def SMTP_PORT(self) -> int:
        return self.SMTP.PORT

    @property
    def SMTP_USER(self) -> str:
        return self.SMTP.USER

    @property
    def SMTP_PASSWORD(self) -> str:
        return self.SMTP.PASSWORD

    @property
    def SMTP_FROM(self) -> str:
        return self.SMTP.FROM

    @property
    def SMTP_FROM_NAME(self) -> str:
        return self.SMTP.FROM_NAME

    @property
    def BACKEND_CORS_ORIGINS(self) -> str:
        return self.CORS.ORIGINS

    @property
    def cors_origins_list(self) -> List[str]:
        return self.CORS.origins_list


settings = Settings()