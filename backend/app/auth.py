import uuid
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users import exceptions
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from models.user import User
from database import get_async_session
from config import settings
from services.email_service import EmailService


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")
        # Immediately send verification token after registration
        try:
            await self.request_verify(user, request)
        except Exception as e:
            print(f"Failed to send verification email: {e}")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")
        # Send email with token
        try:
            verify_link = f"http://localhost:8000/auth/verify?token={token}"
            subject = "Подтверждение email"
            text = (
                "Здравствуйте!\n\n"
                "Для подтверждения email перейдите по ссылке:\n"
                f"{verify_link}\n\n"
                "Если вы не регистрировались, просто проигнорируйте это письмо."
            )
            html = (
                f"<p>Здравствуйте!</p>"
                f"<p>Для подтверждения email нажмите на ссылку: <a href=\"{verify_link}\">Подтвердить</a></p>"
                f"<p>Если ссылка не открывается, используйте токен: <code>{token}</code></p>"
            )
            await EmailService.send_email(user.email, subject, text, html)
        except Exception as e:
            print(f"Failed to send verification email via SMTP: {e}")

    async def validate_password(self, password: str, user: Optional[User] = None) -> None:
        # Enforce bcrypt 72-byte limit and basic policy
        if len(password) > 72:
            raise exceptions.InvalidPasswordException("Пароль не может быть длиннее 72 символов")
        if len(password) < 8:
            raise exceptions.InvalidPasswordException("Пароль должен содержать минимум 8 символов")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.SECRET_KEY, 
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Enforce email verification across protected endpoints
current_active_user = fastapi_users.current_user(active=True, verified=True)

