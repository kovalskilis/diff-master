import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.health.endpoint import health
from config import settings
from database import create_db_and_tables
from auth import auth_backend, fastapi_users
from schemas.user import UserRead, UserCreate, UserUpdate
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
    yield
    pass


def prepare_app():
    app = FastAPI(
        title=settings.APP.NAME,
        version=settings.APP.VERSION,
        lifespan=lifespan
    )
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )

    app.include_router(documents.router, prefix="/api", tags=["documents"])
    app.include_router(workspace.router, prefix="/api", tags=["workspace"])
    app.include_router(edits.router, prefix="/api", tags=["edits"])
    app.include_router(search.router, prefix="/api", tags=["search"])
    app.include_router(diff.router, prefix="/api", tags=["diff"])
    app.include_router(export.router, prefix="/api", tags=["export"])
    app.include_router(versions.router, prefix="/api", tags=["versions"])
    app.include_router(health, prefix='/api', tags=['health'])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    return app

app = prepare_app()

@app.get("/")
async def root():
    return {
        "app": settings.APP.NAME,
        "version": settings.APP.VERSION,
        "status": "running"
    }


def start_service():
    uvicorn.run(
        app,
        host=settings.APP.ADDRESS,
        port=settings.APP.PORT,
    )

if __name__ == "__main__":
    start_service()