from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .base import BaseAppException


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    def simplify_loc(loc):
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


async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = "Произошла ошибка"

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


async def integrity_error_handler(request: Request, exc: IntegrityError):
    err_str = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    if "user" in err_str and ("duplicate" in err_str.lower() or "already exists" in err_str.lower()):
        return JSONResponse(status_code=400, content={"message": "Пользователь с таким email уже зарегистрирован"})
    return JSONResponse(status_code=400, content={"message": "Нарушение ограничений базы данных"})


async def value_error_handler(request: Request, exc: ValueError):
    text = str(exc)
    if "password cannot be longer than 72 bytes" in text:
        return JSONResponse(status_code=400, content={"message": "Пароль не может быть длиннее 72 символов"})
    return JSONResponse(status_code=400, content={"message": text or "Некорректные данные"})


async def base_app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(
        status_code=exc.status,
        content={"message": exc.message, "reason": exc.reason},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(BaseAppException, base_app_exception_handler)


