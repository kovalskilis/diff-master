import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_db_and_tables
from config import settings
from api.health.endpoint import health
from api import (
    documents,
    workspace,
    edits,
    search,
    diff,
    export,
    versions,
)
from exceptions.handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.APP.RUN_CREATE_DB_ON_STARTUP:
        await create_db_and_tables()
        print("✅ База данных инициализирована")
    yield
    print("🛑 Приложение останавливается")


app = FastAPI(
    title=settings.APP.NAME,
    description="API для анализа изменений в документах с использованием LLM",
    version=settings.APP.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры с prefix="/api" - endpoints определяют полный путь после /api
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(workspace.router, prefix="/api", tags=["workspace"])
app.include_router(edits.router, prefix="/api", tags=["edits"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(diff.router, prefix="/api", tags=["diff"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(versions.router, prefix="/api", tags=["versions"])
app.include_router(health, prefix="/api", tags=["health"])

register_exception_handlers(app)


@app.get("/")
async def root():
    return {
        "app": settings.APP.NAME,
        "version": settings.APP.VERSION,
        "status": "running"
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.APP.ADDRESS,
        port=settings.APP.PORT,
    )
