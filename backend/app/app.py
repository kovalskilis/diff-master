import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Ensure this file can import modules without the 'app.' prefix by adding the
# current package directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

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
from sqlalchemy.exc import IntegrityError
import traceback


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_db_and_tables()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes
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

# API routes
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(workspace.router, prefix="/api", tags=["workspace"])
app.include_router(edits.router, prefix="/api", tags=["edits"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(diff.router, prefix="/api", tags=["diff"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(versions.router, prefix="/api", tags=["versions"])


# Friendly error handlers (RU)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    def simplify_loc(loc):
        # Drop leading 'body'/'query' where present
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        return ".".join(str(p) for p in loc)

    errors = [
        {
            "field": simplify_loc(err.get("loc", [])),
            "message": err.get("msg", "Некорректное значение"),
            "type": err.get("type", "validation_error"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "message": "Проверьте корректность введенных данных",
            "errors": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = "Произошла ошибка"

    # Heuristics for common registration/auth cases
    if request.url.path.startswith("/auth") and exc.status_code == 400:
        if isinstance(detail, str):
            if "already exists" in detail.lower():
                message = "Пользователь с таким email уже зарегистрирован"
            elif "login_bad_credentials" in detail.lower() or "bad credentials" in detail.lower():
                message = "Неверный email или пароль"
            elif "invalid password" in detail.lower():
                message = "Пароль не соответствует требованиям безопасности"
            else:
                message = detail
        else:
            message = "Некорректные данные для аутентификации/регистрации"
    else:
        if isinstance(detail, str):
            message = detail

    return JSONResponse(status_code=exc.status_code, content={"message": message})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    err_str = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    if "user" in err_str and ("duplicate" in err_str.lower() or "already exists" in err_str.lower()):
        return JSONResponse(status_code=400, content={"message": "Пользователь с таким email уже зарегистрирован"})
    return JSONResponse(status_code=400, content={"message": "Нарушение ограничений базы данных"})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    text = str(exc)
    if "password cannot be longer than 72 bytes" in text:
        return JSONResponse(status_code=400, content={"message": "Пароль не может быть длиннее 72 символов"})
    return JSONResponse(status_code=400, content={"message": text or "Некорректные данные"})


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, loop="asyncio")